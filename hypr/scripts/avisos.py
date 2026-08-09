#!/usr/bin/env python3
"""
Historial de notificaciones: lo que pasó por la pantalla mientras no mirabas.

Una notificación sale seis segundos y se va para siempre. Si estabas jugando,
leyendo o simplemente mirando a otro lado, se perdió — y no queda forma de saber
qué era ni quién lo mandó.

Esto lo graba todo y lo deja donde puedas volver a mirarlo:

    avisos listar          lo de esta sesión, lo último arriba
    avisos ver 12          uno entero, sin recortar
    avisos guardar 12      apartarlo para hablarlo otro día
    avisos guardados       lo apartado, que sobrevive al reinicio
    avisos menu            lo mismo, con el ratón (SUPER+H)
    avisos --demonio       el grabador (lo lanza autostart.conf)

DÓNDE VIVE, Y POR QUÉ AHÍ
-------------------------
El historial de la sesión va a `$XDG_RUNTIME_DIR`, que es un tmpfs en modo 700
que systemd **borra al cerrar la última sesión**. O sea que «se guarda hasta que
cierro sesión y luego desaparece» no necesita ni una línea de código de limpieza,
ni un cron, ni acordarse: lo hace el sistema. Y al ser tmpfs, un aviso con un
código de dos factores o el asunto de un correo nunca toca el disco.

Lo que **guardas a mano** sí baja a `~/.local/share`, porque justamente lo que le
pides es que sobreviva. Es la única parte que queda escrita, y por eso es la
única que eliges tú, una por una.

POR QUÉ ESPIANDO EL BUS Y NO PREGUNTÁNDOLE A MAKO
-------------------------------------------------
mako 1.11 tiene su propio historial (`makoctl history -j`) y no vale para esto,
por tres razones medidas, no supuestas:

  1. **No trae la hora.** Sus campos son id, app_name, app_icon, category,
     desktop_entry, summary, body, urgency y actions. Un historial sin «cuándo»
     es media cosa.
  2. Es un búfer **en memoria de 5** (`max-history`) que muere con mako.
  3. `makoctl restore` **saca** cosas de ese búfer: está pensado como pila de
     deshacer, no como archivo. Compartirlo con SUPER+CTRL+N sería pelearse por
     la misma lista.

Así que se escucha el bus directamente. Ventaja de fondo: esto no sustituye al
demonio de notificaciones ni se mete en su camino. mako sigue haciendo su
trabajo; si este grabador se cae, dejas de grabar pero **no te quedas sin
avisos**. Nunca puede romper lo que ya funciona.

LO QUE COSTÓ AVERIGUAR (no lo redescubras)
------------------------------------------
- El id de la notificación **no está en la llamada `Notify`**: viene en la
  RESPUESTA. Se emparejan por `reply_serial`, que es igual al `serial` de la
  llamada. Sin eso no se puede saber a qué aviso se refiere un `NotificationClosed`.
- La regla de espiado para las respuestas tiene que ser
  `type='method_return',sender='org.freedesktop.Notifications'`. Con un
  `type='method_return'` a secas te llega **todo el tráfico del bus** (gsettings,
  systemd, portales...) y el proceso se pasa el día despertándose para nada.
  Medido: con la regla estrecha, 16 mensajes en 9 s; sin ella, cientos.
- Una conexión que llama a `BecomeMonitor` **ya no puede hablar**, solo escuchar.
  Por eso se abre una conexión privada y no la compartida de `Gio.bus_get_sync`.
- Las hints pueden traer la imagen del icono en crudo (`image-data`, un array de
  píxeles). Guardar eso en el JSONL serían megabytes por aviso: solo se guardan
  las hints escalares.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

APP = "avisos"

# Un aviso es un titular. Si alguien manda una novela, se corta: el historial es
# para reconocer qué llegó, no para archivar cuerpos arbitrariamente grandes.
MAXIMO_CUERPO = 4000
# Seguro contra una app en bucle. El tmpfs de la sesión no es infinito y quedarse
# sin `$XDG_RUNTIME_DIR` rompe cosas que no tienen nada que ver con esto (el fifo
# de las barras, sin ir más lejos).
MAXIMO_FICHERO = 20 * 1024 * 1024
# Una llamada sin respuesta a los 5 s es una notificación que nadie recogió
# (demonio caído). Se apunta igual, sin id: mejor un registro cojo que un hueco.
ESPERA_RESPUESTA = 5.0

URGENCIAS = {0: "baja", 1: "normal", 2: "critica"}
# Los motivos de NotificationClosed son los de la especificación de freedesktop.
CIERRES = {1: "expiro", 2: "la descartaste", 3: "la cerro el programa"}


# ─────────────────────────────────────────────────────────────────────────────
# Dónde se guarda
# ─────────────────────────────────────────────────────────────────────────────

def carpeta_sesion() -> Path:
    """Carpeta volátil. Se va sola al cerrar sesión, que es lo que se quiere."""
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    ruta = Path(base) / APP
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def carpeta_guardados() -> Path:
    """Carpeta permanente. Solo baja aquí lo que apartas a mano."""
    base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    ruta = Path(base) / APP
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def fichero_sesion() -> Path:
    return carpeta_sesion() / "sesion.jsonl"


def fichero_guardados() -> Path:
    return carpeta_guardados() / "guardados.jsonl"


# ─────────────────────────────────────────────────────────────────────────────
# Leer y escribir el registro
#
# Es JSONL y se escribe SOLO añadiendo al final: así una caída a media escritura
# se lleva como mucho la última línea, y nunca el historial entero. Lo que en
# otro diseño sería «actualizar un registro» aquí es apuntar una línea de tipo
# `cierre` o `accion`; quien lee las va plegando encima. Sale más barato que
# reescribir el fichero cada vez que descartas algo.
# ─────────────────────────────────────────────────────────────────────────────

def _apuntar(ruta: Path, registro: dict) -> None:
    try:
        if ruta.exists() and ruta.stat().st_size > MAXIMO_FICHERO:
            return
        with ruta.open("a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except OSError:
        pass  # grabar nunca puede tumbar nada


def _lineas(ruta: Path) -> list[dict]:
    if not ruta.is_file():
        return []
    salida = []
    try:
        with ruta.open(encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    salida.append(json.loads(linea))
                except json.JSONDecodeError:
                    continue  # línea a medias de una caída: se ignora y ya
    except OSError:
        return []
    return salida


def hints_escalares(hints: dict) -> dict:
    """Las hints que se pueden guardar: fuera las imágenes en crudo.

    Una notificación puede traer su icono como `image-data`: un array con los
    píxeles dentro. Volcarlo al JSONL serían cientos de KB por aviso, y el
    registro vive en un tmpfs que comparte sitio con el fifo de las barras.
    Solo interesan los escalares (urgency, category, sender-pid, el hilo...).

    `bool` va antes que `int` en la comprobación porque en Python un bool ES un
    int; el orden no cambia el resultado aquí, pero sí la cabeza de quien lea.
    """
    return {clave: valor for clave, valor in (hints or {}).items()
            if isinstance(valor, (str, bool, int, float))}


def avisos(ruta: Path | None = None) -> list[dict]:
    """El historial ya plegado: cada aviso con su cierre y su acción puestos."""
    por_n: dict[int, dict] = {}
    for registro in _lineas(ruta or fichero_sesion()):
        n = registro.get("n")
        if n is None:
            continue
        if registro.get("tipo") == "aviso":
            por_n[n] = registro
        elif n in por_n:
            # Un `cierre` o una `accion` no traen el aviso entero, solo el campo
            # que cambia.
            por_n[n].update({k: v for k, v in registro.items()
                             if k not in ("tipo", "n")})
    return [por_n[n] for n in sorted(por_n)]


# ─────────────────────────────────────────────────────────────────────────────
# El grabador
# ─────────────────────────────────────────────────────────────────────────────

def demonio() -> int:
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib

    reglas = [
        "type='method_call',interface='org.freedesktop.Notifications',"
        "member='Notify'",
        "type='signal',interface='org.freedesktop.Notifications'",
        # Estrecha a propósito: ver la cabecera.
        "type='method_return',sender='org.freedesktop.Notifications'",
    ]

    ruta = fichero_sesion()
    # El contador arranca de donde lo dejó el fichero: si el grabador se reinicia
    # a media sesión, los números no se pisan y lo que ya listaste sigue valiendo.
    previos = avisos(ruta)
    estado = {"n": (previos[-1]["n"] if previos else 0)}
    esperando: dict[int, tuple[float, dict]] = {}   # serial de la llamada -> aviso
    por_id: dict[int, int] = {}                     # id de mako -> n nuestro

    def registrar(aviso: dict) -> None:
        _apuntar(ruta, aviso)
        if aviso.get("id_demonio") is not None:
            por_id[aviso["id_demonio"]] = aviso["n"]

    def vaciar_pendientes(ahora: float) -> None:
        """Avisos cuya respuesta no llegó: se apuntan igual, sin id."""
        for serial in [s for s, (t, _) in esperando.items()
                       if ahora - t > ESPERA_RESPUESTA]:
            _, aviso = esperando.pop(serial)
            registrar(aviso)

    def filtro(conexion, mensaje, entrante, datos=None):
        ahora = time.time()
        vaciar_pendientes(ahora)
        tipo = mensaje.get_message_type()
        cuerpo = mensaje.get_body()

        if tipo == Gio.DBusMessageType.METHOD_CALL and \
                mensaje.get_member() == "Notify" and cuerpo is not None:
            try:
                (app, reemplaza, icono, resumen, texto,
                 acciones, hints, caducidad) = tuple(cuerpo)[:8]
            except (ValueError, TypeError):
                return None
            hints = hints_escalares(dict(hints) if hints else {})
            estado["n"] += 1
            # Las acciones vienen en lista plana [id, etiqueta, id, etiqueta...].
            pares = list(acciones or [])
            aviso = {
                "tipo": "aviso",
                "n": estado["n"],
                "epoch": round(ahora, 3),
                "hora": datetime.fromtimestamp(ahora).isoformat(timespec="seconds"),
                "app": str(app or ""),
                "resumen": str(resumen or ""),
                "cuerpo": str(texto or "")[:MAXIMO_CUERPO],
                "urgencia": URGENCIAS.get(hints.get("urgency", 1), "normal"),
                "icono": str(icono or ""),
                "categoria": hints.get("category", ""),
                "escritorio": hints.get("desktop-entry", ""),
                "hilo": hints.get("x-canonical-private-synchronous", ""),
                "pid": hints.get("sender-pid"),
                "acciones": dict(zip(pares[::2], pares[1::2])),
                "reemplaza": int(reemplaza or 0),
                "caducidad": int(caducidad),
                "id_demonio": None,
            }
            esperando[mensaje.get_serial()] = (ahora, aviso)
            return None

        if tipo == Gio.DBusMessageType.METHOD_RETURN:
            pendiente = esperando.pop(mensaje.get_reply_serial(), None)
            if pendiente and cuerpo is not None:
                _, aviso = pendiente
                try:
                    aviso["id_demonio"] = int(tuple(cuerpo)[0])
                except (ValueError, TypeError, IndexError):
                    pass
                registrar(aviso)
            return None

        if tipo == Gio.DBusMessageType.SIGNAL and cuerpo is not None:
            miembro = mensaje.get_member()
            try:
                valores = tuple(cuerpo)
            except TypeError:
                return None
            if miembro == "NotificationClosed" and len(valores) >= 2:
                n = por_id.get(int(valores[0]))
                if n is not None:
                    _apuntar(ruta, {"tipo": "cierre", "n": n,
                                    "cierre": CIERRES.get(int(valores[1]), "")})
            elif miembro == "ActionInvoked" and len(valores) >= 2:
                n = por_id.get(int(valores[0]))
                if n is not None:
                    _apuntar(ruta, {"tipo": "accion", "n": n,
                                    "pulsada": str(valores[1])})
            return None

        return None

    direccion = Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None)
    conexion = Gio.DBusConnection.new_for_address_sync(
        direccion,
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
        | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
        None, None)
    conexion.call_sync(
        "org.freedesktop.DBus", "/org/freedesktop/DBus",
        "org.freedesktop.DBus.Monitoring", "BecomeMonitor",
        GLib.Variant("(asu)", (reglas, 0)),
        None, Gio.DBusCallFlags.NONE, -1, None)
    conexion.add_filter(filtro)

    bucle = GLib.MainLoop()
    # Si el bus se va, la sesión se acabó: no tiene sentido seguir vivo. Es la
    # misma lección del demonio del fondo, que sobrevivió a su Hyprland y estorbó.
    conexion.connect("closed", lambda *_: bucle.quit())
    try:
        bucle.run()
    except KeyboardInterrupt:
        pass
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# Guardar y olvidar
# ─────────────────────────────────────────────────────────────────────────────

def guardar(n: int, nota: str = "") -> int:
    coincide = [a for a in avisos() if a["n"] == n]
    if not coincide:
        print(f"no hay ningún aviso con el número {n} en esta sesión",
              file=sys.stderr)
        return 1
    aviso = dict(coincide[0])
    if any(g.get("epoch") == aviso.get("epoch") and g.get("resumen") == aviso.get("resumen")
           for g in _lineas(fichero_guardados())):
        print(f"#{n} ya estaba guardado")
        return 0
    aviso["tipo"] = "aviso"
    aviso["guardado_el"] = datetime.now().isoformat(timespec="seconds")
    if nota:
        aviso["nota"] = nota
    _apuntar(fichero_guardados(), aviso)
    print(f"guardado: {aviso['resumen'] or aviso['app']}")
    return 0


def olvidar(indice: int) -> int:
    guardados = _lineas(fichero_guardados())
    if not 1 <= indice <= len(guardados):
        print(f"no hay ningún guardado con el número {indice}", file=sys.stderr)
        return 1
    fuera = guardados.pop(indice - 1)
    ruta = fichero_guardados()
    # Reescritura entera: es el único sitio donde se borra, pasa una vez cada
    # mucho, y hacerlo por temporal + rename deja el fichero siempre completo.
    temporal = ruta.with_suffix(".nuevo.jsonl")
    with temporal.open("w", encoding="utf-8") as f:
        for g in guardados:
            f.write(json.dumps(g, ensure_ascii=False) + "\n")
    temporal.replace(ruta)
    print(f"olvidado: {fuera.get('resumen') or fuera.get('app')}")
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# Mirarlo
# ─────────────────────────────────────────────────────────────────────────────

def _hora(aviso: dict) -> str:
    return (aviso.get("hora") or "")[11:16] or "--:--"


def _una_linea(aviso: dict, ancho_app: int = 14) -> str:
    marca = {"critica": "!", "baja": "·"}.get(aviso.get("urgencia"), " ")
    app = (aviso.get("app") or "?")[:ancho_app].ljust(ancho_app)
    resumen = aviso.get("resumen") or (aviso.get("cuerpo") or "")[:60]
    return f"{marca} {_hora(aviso)}  {app}  {resumen}"


def listar(cuantos: int, como_json: bool, desde_guardados: bool) -> int:
    lista = _lineas(fichero_guardados()) if desde_guardados else avisos()
    if como_json:
        # La salida para quien lea esto desde fuera. Se numera aquí para que el
        # número que ve otro programa sea el mismo que escribes tú.
        for i, aviso in enumerate(lista, 1):
            aviso.setdefault("indice", i)
        json.dump(lista[-cuantos:] if cuantos else lista,
                  sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0
    if not lista:
        print("no hay nada guardado todavía" if desde_guardados
              else "no ha llegado ninguna notificación en esta sesión")
        return 0
    recorte = lista[-cuantos:] if cuantos else lista
    for i, aviso in enumerate(recorte, len(lista) - len(recorte) + 1):
        numero = i if desde_guardados else aviso["n"]
        print(f"{numero:>4}  {_una_linea(aviso)}")
    return 0


def ver(n: int, desde_guardados: bool) -> int:
    lista = _lineas(fichero_guardados()) if desde_guardados else avisos()
    if desde_guardados:
        aviso = lista[n - 1] if 1 <= n <= len(lista) else None
    else:
        aviso = next((a for a in lista if a["n"] == n), None)
    if aviso is None:
        print(f"no hay ningún aviso con el número {n}", file=sys.stderr)
        return 1
    print(texto_entero(aviso))
    return 0


def texto_entero(aviso: dict) -> str:
    lineas = [
        aviso.get("resumen") or "(sin título)",
        "─" * max(20, min(78, len(aviso.get("resumen") or "") + 4)),
        "",
        aviso.get("cuerpo") or "(sin cuerpo)",
        "",
        f"de       {aviso.get('app') or '?'}",
        f"cuándo   {aviso.get('hora') or '?'}",
        f"urgencia {aviso.get('urgencia') or '?'}",
    ]
    if aviso.get("cierre"):
        lineas.append(f"final    {aviso['cierre']}")
    if aviso.get("pulsada"):
        lineas.append(f"pulsaste «{aviso['pulsada']}»")
    if aviso.get("nota"):
        lineas.append(f"nota     {aviso['nota']}")
    if aviso.get("guardado_el"):
        lineas.append(f"guardado {aviso['guardado_el']}")
    return "\n".join(lineas)


# ─────────────────────────────────────────────────────────────────────────────
# El visor: fuzzel, que ya está montado y con tu paleta
#
# No hay panel GTK propio a propósito: fuzzel ya está montado, con la paleta
# puesta y sabiendo buscar. Un panel más es una superficie más que mantener, y
# esto se abre, se mira y se cierra.
# ─────────────────────────────────────────────────────────────────────────────

def _elegir(opciones: list[str], titulo: str) -> int | None:
    """Saca fuzzel en modo dmenu y devuelve el índice elegido, o None."""
    if not shutil.which("fuzzel"):
        print("fuzzel no está instalado: usa `avisos listar`",
              file=sys.stderr)
        return None
    try:
        proceso = subprocess.run(
            ["fuzzel", "--dmenu", "--index", "--prompt", titulo,
             "--lines", "16", "--width", "78"],
            input="\n".join(opciones), capture_output=True, text=True,
            timeout=300, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    elegido = (proceso.stdout or "").strip()
    return int(elegido) if elegido.isdigit() else None


def menu() -> int:
    lista = list(reversed(avisos()))   # lo último arriba, que es lo que buscas
    if not lista:
        subprocess.run(["notify-send", "-a", "Historial",
                        "Sin notificaciones", "Nada ha llegado en esta sesión"],
                       check=False)
        return 0
    guardados = _lineas(fichero_guardados())
    ya = {(g.get("epoch"), g.get("resumen")) for g in guardados}

    filas = []
    for aviso in lista:
        estrella = "★ " if (aviso.get("epoch"), aviso.get("resumen")) in ya else "  "
        filas.append(estrella + _una_linea(aviso))

    elegido = _elegir(filas, "avisos ❯ ")
    if elegido is None:
        return 0
    aviso = lista[elegido]
    esta_guardado = (aviso.get("epoch"), aviso.get("resumen")) in ya

    acciones = [
        "Ver entero",
        "Dejar de guardarlo" if esta_guardado else "Guardar para hablarlo después",
    ]
    if shutil.which("wl-copy"):
        acciones.append("Copiar el texto")
    acciones.append("Volver")

    cual = _elegir(acciones, "qué hago ❯ ")
    if cual is None or acciones[cual] == "Volver":
        return menu() if cual is not None else 0

    accion = acciones[cual]
    if accion == "Ver entero":
        destino = carpeta_sesion() / "detalle.txt"
        destino.write_text(texto_entero(aviso), encoding="utf-8")
        guion = Path(__file__).resolve().parent / "terminal.sh"
        subprocess.Popen([str(guion), "aviso-detalle", "less", "-R", str(destino)],
                         start_new_session=True)
    elif accion == "Copiar el texto":
        subprocess.run(["wl-copy"], input=texto_entero(aviso), text=True,
                       check=False)
    elif esta_guardado:
        indice = next((i for i, g in enumerate(guardados, 1)
                       if (g.get("epoch"), g.get("resumen"))
                       == (aviso.get("epoch"), aviso.get("resumen"))), None)
        if indice:
            olvidar(indice)
    else:
        guardar(aviso["n"])
    return 0


# ─────────────────────────────────────────────────────────────────────────────

AYUDA = __doc__.split("DÓNDE VIVE")[0].strip()


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "ayuda"):
        print(AYUDA)
        return 0
    orden, resto = argv[0], argv[1:]

    if orden == "--demonio":
        return demonio()
    if orden == "menu":
        return menu()

    guardados = "--guardados" in resto or orden == "guardados"
    resto = [a for a in resto if a != "--guardados"]
    como_json = "--json" in resto
    resto = [a for a in resto if a != "--json"]

    if orden in ("listar", "guardados"):
        cuantos = 0
        if "-n" in resto:
            i = resto.index("-n")
            if i + 1 < len(resto) and resto[i + 1].isdigit():
                cuantos = int(resto[i + 1])
        elif not guardados:
            cuantos = 30      # lo de hoy suele ser mucho; lo apartado, poco
        return listar(cuantos, como_json, guardados)

    if orden in ("ver", "guardar", "olvidar"):
        if not resto or not resto[0].lstrip("#").isdigit():
            print(f"uso: avisos {orden} <número>", file=sys.stderr)
            return 2
        n = int(resto[0].lstrip("#"))
        if orden == "ver":
            return ver(n, guardados)
        if orden == "guardar":
            return guardar(n, " ".join(resto[1:]))
        return olvidar(n)

    print(f"no conozco la orden «{orden}»\n\n{AYUDA}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
