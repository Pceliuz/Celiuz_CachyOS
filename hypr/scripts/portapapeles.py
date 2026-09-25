#!/usr/bin/env python3
"""
~/dotfiles/hypr/scripts/portapapeles.py

El historial del portapapeles, con cosas FIJADAS y cosas GUARDADAS.

    portapapeles.py demonio     lo arranca autostart.conf: vigila lo que copias
    portapapeles.py menu        SUPER+SHIFT+V
    portapapeles.py vaciar      borra el historial (no toca fijados ni guardados)
    portapapeles.py --ver       donde vive cada cosa, cuantas hay y los ajustes

LAS TRES LISTAS
---------------
- HISTORIAL: todo lo que copias, texto o imagen, se apunta solo. Se olvida a las
  `horas` (24) y nunca guarda mas de `maximo` (50): lo mas viejo sale primero.
  Vive en memoria ($XDG_RUNTIME_DIR) y muere al cerrar sesion.
- FIJADOS (󰐃): lo que usas a cada rato. Salen arriba del todo y no caducan,
  pero duran lo que dura la SESION: al cerrarla o apagar, se van.
- GUARDADOS (󰆓): lo que quieres tener cualquier dia. Van al disco
  ($XDG_DATA_HOME/celiuz/portapapeles) y sobreviven a reinicios.

En el menu: Enter copia · Ctrl+F fija/desfija · Ctrl+G guarda/quita de guardados
· Ctrl+D lo borra (de su lista y del historial). La ayuda sale escrita en la caja
de busqueda mientras esta vacia. Tras fijar, guardar o borrar, el menu se vuelve
a abrir en el mismo sitio, para que veas el cambio y sigas.

POR QUE EL HISTORIAL NO VA AL DISCO. Por el portapapeles pasa de todo: codigos,
direcciones, trozos de conversaciones. Guardarlo en disco sin que lo pidas lo
dejaria ahi despues de apagar. Lo que quieras conservar, lo guardas (Ctrl+G), y
eso es una decision tuya. Y lo que un gestor de contraseñas marca como secreto
(KeePassXC, por ejemplo) no se apunta NUNCA: wl-paste lo avisa con
CLIPBOARD_STATE=sensitive y el tipo `x-kde-passwordManagerHint`.

POR QUE NO CLIPHIST. cliphist no sabe de caducidad por tiempo (solo cuenta
entradas) ni de fijar o guardar, y todo eso habria que montarlo encima de su
base de datos. Con un fichero por entrada las tres listas son tres carpetas, la
edad es la fecha del fichero, y fijar o guardar es copiarlo: sin dependencias nuevas
(wl-clipboard y fuzzel ya los pide instalar.sh).

COMO SE GUARDA. Un fichero por entrada, `<huella>.<ext>`, con la huella sacada
del contenido: copiar dos veces lo mismo no lo duplica, lo sube arriba. La
fecha del fichero es la ultima vez que se copio, y ordena la lista.

LA SESION. Los fijados y el historial viven en
`$XDG_RUNTIME_DIR/celiuz-portapapeles.<firma>/`. La firma va en el nombre por la
regla de lib/canales.py: $XDG_RUNTIME_DIR es del USUARIO, no de la sesion, y
sobrevive a cerrar sesion si hay otra abierta; sin firma, «hasta cerrar sesion»
seria mentira. Al arrancar, el demonio borra las carpetas de sesiones cuyo
Hyprland ya no contesta — nunca las de otra sesion viva, y sin firma no reclama
nada (la misma regla que `pids_de_esta_sesion`).

LOS AJUSTES, en `$XDG_CONFIG_HOME/celiuz/portapapeles.conf` (no se versiona,
como bluetooth.conf), y se leen en cada copia, asi que no hay que reiniciar:

    maximo = 50     cuantas cosas guarda el historial
    horas = 24      a las cuantas horas se olvida una
    max_mb = 16     lo que pese mas que esto no se apunta (una imagen enorme)
"""

import fcntl
import hashlib
import os
import shutil
import socket
import subprocess
import sys
import time

SCRIPT = os.path.realpath(__file__)
REPO = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT)))

AJUSTES_FABRICA = {"maximo": 50, "horas": 24, "max_mb": 16}

# El tipo de cada imagen, en el orden en que se prefiere pedirla.
IMAGENES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp",
            "image/gif": "gif", "image/bmp": "bmp"}
TEXTOS = ("text/plain;charset=utf-8", "text/plain", "UTF8_STRING", "STRING",
          "TEXT")
SECRETO = "x-kde-passwordManagerHint"

FIJADO, GUARDADO = "󰐃", "󰆓"
AYUDA = "Enter copia · Ctrl+F fija · Ctrl+G guarda · Ctrl+D borra"

# Lo que devuelve fuzzel con cada tecla (custom-1, -2, -3: ver _config_fuzzel).
TECLA_FIJAR, TECLA_GUARDAR, TECLA_BORRAR = 10, 11, 12


# ─────────────────────────────────────────────────────────────────────────────
# Donde vive cada cosa
# ─────────────────────────────────────────────────────────────────────────────

def _runtime():
    return os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"


def firma():
    return os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or ""


PREFIJO = "celiuz-portapapeles."


def dir_sesion():
    """La carpeta de ESTA sesion. Sin firma (a mano, desde un TTY) vale la unica
    que haya; si hay varias no se adivina, igual que lib/canales.py."""
    sig = firma()
    if sig:
        return os.path.join(_runtime(), PREFIJO + sig)
    try:
        sueltas = sorted(n for n in os.listdir(_runtime()) if n.startswith(PREFIJO))
    except OSError:
        sueltas = []
    if len(sueltas) == 1:
        return os.path.join(_runtime(), sueltas[0])
    return os.path.join(_runtime(), PREFIJO + "sin-sesion")


def dir_historial():
    return os.path.join(dir_sesion(), "historial")


def dir_fijados():
    return os.path.join(dir_sesion(), "fijados")


def dir_guardados():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "celiuz", "portapapeles")


def fichero_ajustes():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "celiuz", "portapapeles.conf")


def ajustes():
    a = dict(AJUSTES_FABRICA)
    try:
        with open(fichero_ajustes(), encoding="utf-8") as f:
            texto = f.read()
    except OSError:
        return a
    for linea in texto.splitlines():
        linea = linea.split("#", 1)[0].strip()
        clave, _, valor = linea.partition("=")
        clave = clave.strip().lower()
        if clave in a:
            try:
                n = float(valor.strip().replace(",", "."))
            except ValueError:
                continue
            if n > 0:
                a[clave] = n
    a["maximo"] = max(1, int(a["maximo"]))
    return a


def _crear(ruta, modo=0o700):
    os.makedirs(ruta, mode=modo, exist_ok=True)
    return ruta


# ─────────────────────────────────────────────────────────────────────────────
# Las entradas
# ─────────────────────────────────────────────────────────────────────────────

def _entradas(carpeta):
    """[(nombre, fecha)] de una carpeta, lo mas reciente primero."""
    try:
        nombres = os.listdir(carpeta)
    except OSError:
        return []
    salida = []
    for n in nombres:
        if n.startswith("."):
            continue   # temporales a medio escribir
        try:
            salida.append((n, os.stat(os.path.join(carpeta, n)).st_mtime))
        except OSError:
            continue   # se la llevo la poda entre el listdir y el stat
    return sorted(salida, key=lambda e: (-e[1], e[0]))


def _escribir(carpeta, nombre, datos):
    """Escritura atomica: nadie ve nunca un fichero a medias."""
    _crear(carpeta)
    temporal = os.path.join(carpeta, f".{nombre}.{os.getpid()}")
    with open(temporal, "wb") as f:
        f.write(datos)
    os.chmod(temporal, 0o600)
    os.replace(temporal, os.path.join(carpeta, nombre))


def _borrar(ruta):
    try:
        os.unlink(ruta)
        return True
    except OSError:
        return False


def podar(a=None):
    """Olvida del historial lo caducado y lo que sobre por encima del maximo."""
    a = a or ajustes()
    carpeta = dir_historial()
    limite = time.time() - a["horas"] * 3600
    for i, (nombre, fecha) in enumerate(_entradas(carpeta)):
        if i >= a["maximo"] or fecha < limite:
            _borrar(os.path.join(carpeta, nombre))


def _pedir(tipo):
    """El contenido del portapapeles en ese tipo, o None."""
    try:
        r = subprocess.run(["wl-paste", "--no-newline", "--type", tipo],
                           capture_output=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def _tipos():
    try:
        r = subprocess.run(["wl-paste", "--list-types"], capture_output=True,
                           text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return r.stdout.split() if r.returncode == 0 else []


def recibir():
    """Lo llama `wl-paste --watch` cada vez que cambia el portapapeles."""
    try:
        sys.stdin.buffer.read()   # lo que manda wl-paste: se pide abajo en el tipo bueno
    except (OSError, ValueError):
        pass
    if os.environ.get("CLIPBOARD_STATE", "data") != "data":
        return 0   # vacio (nil) o secreto (sensitive): no se apunta
    tipos = _tipos()
    if not tipos or SECRETO in tipos:
        return 0

    # Texto antes que imagen: si algo se ofrece como las dos cosas (una celda de
    # una hoja de calculo), lo que querias era el texto.
    datos, ext = None, None
    texto = next((t for t in TEXTOS if t in tipos), None)
    if texto:
        datos, ext = _pedir(texto), "txt"
        if datos is not None and not datos.strip():
            return 0   # solo espacios: nada que recordar
    else:
        imagen = next((t for t in IMAGENES if t in tipos), None)
        if imagen:
            datos, ext = _pedir(imagen), IMAGENES[imagen]
    if not datos:
        return 0

    a = ajustes()
    if len(datos) > a["max_mb"] * 1024 * 1024:
        return 0
    nombre = hashlib.sha1(datos).hexdigest()[:20] + "." + ext
    ruta = os.path.join(dir_historial(), nombre)
    if os.path.exists(ruta):
        os.utime(ruta)           # ya estaba: sube arriba
    else:
        _escribir(dir_historial(), nombre, datos)
    podar(a)
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# El menu
# ─────────────────────────────────────────────────────────────────────────────

def _es_imagen(nombre):
    return not nombre.endswith(".txt")


def _medidas_png(ruta):
    try:
        with open(ruta, "rb") as f:
            cabecera = f.read(24)
    except OSError:
        return None
    if cabecera[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return int.from_bytes(cabecera[16:20], "big"), int.from_bytes(cabecera[20:24], "big")


def _resumen(ruta, nombre, ancho=72):
    if _es_imagen(nombre):
        m = _medidas_png(ruta)
        tam = f" {m[0]}×{m[1]}" if m else ""
        return f"Imagen{tam} ({nombre.rsplit('.', 1)[1].upper()})"
    try:
        with open(ruta, "rb") as f:
            texto = f.read(4096).decode("utf-8", "replace")
    except OSError:
        return "?"
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    una = " ⏎ ".join(lineas)
    una = " ".join(una.split())
    if len(una) > ancho:
        una = una[:ancho - 1] + "…"
    return una


def listado():
    """Lo que enseña el menu, en orden: fijados, guardados, historial.

    Algo fijado Y guardado sale una sola vez, en los fijados, con las dos
    marcas; y lo que ya esta fijado o guardado no se repite en el historial.
    """
    fijados = _entradas(dir_fijados())
    guardados = _entradas(dir_guardados())
    n_fij = {n for n, _ in fijados}
    n_gua = {n for n, _ in guardados}

    filas = []
    for n, _ in fijados:
        filas.append({"nombre": n, "ruta": os.path.join(dir_fijados(), n),
                      "fijado": True, "guardado": n in n_gua})
    for n, _ in guardados:
        if n not in n_fij:
            filas.append({"nombre": n, "ruta": os.path.join(dir_guardados(), n),
                          "fijado": False, "guardado": True})
    for n, _ in _entradas(dir_historial()):
        if n not in n_fij and n not in n_gua:
            filas.append({"nombre": n, "ruta": os.path.join(dir_historial(), n),
                          "fijado": False, "guardado": False})
    return filas


def _linea(fila):
    marcas = (FIJADO if fila["fijado"] else " ") + (GUARDADO if fila["guardado"] else " ")
    texto = f"{marcas}  {_resumen(fila['ruta'], fila['nombre'])}"
    if _es_imagen(fila["nombre"]):
        # Protocolo de dmenu extendido de rofi, que fuzzel entiende: la
        # miniatura de la propia imagen como icono de la fila.
        texto += "\0icon\x1f" + fila["ruta"]
    return texto


def _config_fuzzel():
    """Una config de fuzzel para este menu: la tuya, mas tres teclas.

    Se escribe en cada apertura porque tiene que apuntar a TU fuzzel.ini con
    ruta absoluta —fuzzel no expande `~` ni `$HOME`, y si el `include` no existe
    sale sin abrir—, y la ruta depende de donde este tu casa.

    Ctrl+F y Ctrl+D ya eran de fuzzel (mover el cursor a la derecha y borrar el
    caracter siguiente); aqui se les quitan para darselas al menu, y esas dos
    cosas siguen con Derecha y Supr. Ctrl+G era «cancelar» de fabrica, pero
    fuzzel.ini ya lo tiene en Escape y Ctrl+C.
    """
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    tuyo = os.path.join(base, "fuzzel", "fuzzel.ini")
    if not os.path.exists(tuyo):
        tuyo = os.path.join(REPO, "fuzzel", "fuzzel.ini")
    lineas = []
    if os.path.exists(tuyo):
        lineas.append(f"include={tuyo}")
    lineas += ["[key-bindings]",
               "cursor-right=Right",
               "delete-next=Delete KP_Delete",
               "cancel=Escape Control+c",
               "custom-1=Control+f",
               "custom-2=Control+g",
               "custom-3=Control+d"]
    ruta = os.path.join(_crear(dir_sesion()), "fuzzel.ini")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")
    return ruta


def _fuzzel(filas, seleccion):
    """(codigo, indice) de fuzzel; indice None si se cancelo."""
    entrada = "\n".join(_linea(f) for f in filas) + "\n"
    orden = ["fuzzel", "--config", _config_fuzzel(), "--dmenu", "--index",
             "--prompt", "󰅍  ", "--placeholder", AYUDA,
             "--lines", str(min(len(filas), 12)), "--width", "70",
             "--select-index", str(seleccion)]
    try:
        r = subprocess.run(orden, input=entrada.encode(), capture_output=True,
                           timeout=600, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return 1, None
    salida = r.stdout.decode(errors="replace").strip()
    indice = int(salida) if salida.isdigit() else None
    if indice is not None and not 0 <= indice < len(filas):
        indice = None
    return r.returncode, indice


def _avisar(titulo, cuerpo=""):
    subprocess.run(["notify-send", "-a", "Portapapeles", titulo, cuerpo],
                   check=False, stderr=subprocess.DEVNULL)


def copiar(fila):
    ext = fila["nombre"].rsplit(".", 1)[1]
    orden = ["wl-copy"]
    if ext != "txt":
        tipo = next(t for t, e in IMAGENES.items() if e == ext)
        orden += ["--type", tipo]
    # wl-copy se queda en segundo plano sirviendo el contenido: si se le
    # capturase la salida, esa tuberia no se cerraria nunca y esto no volveria.
    with open(fila["ruta"], "rb") as f:
        subprocess.run(orden, stdin=f, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=False)


def _copiar_fichero(origen, carpeta, nombre):
    """Copia a otra lista, con la fecha de AHORA: la de la lista es cuando lo
    pusiste ahi.

    Copia de verdad y no enlace duro, aunque dentro de la sesion se podria: un
    enlace comparte la FECHA con el original, asi que fijar algo lo subia
    tambien arriba del historial, y al desfijarlo aparecia primero de la lista
    sin haberlo copiado. Lo fijado es poco; la copia no se nota.
    """
    _crear(carpeta)
    destino = os.path.join(carpeta, nombre)
    if not os.path.exists(destino):
        temporal = os.path.join(carpeta, f".{nombre}.{os.getpid()}")
        shutil.copyfile(origen, temporal)
        os.chmod(temporal, 0o600)
        os.replace(temporal, destino)
    os.utime(destino)


def fijar(fila):
    if fila["fijado"]:
        _borrar(os.path.join(dir_fijados(), fila["nombre"]))
    else:
        _copiar_fichero(fila["ruta"], dir_fijados(), fila["nombre"])


def guardar(fila):
    if fila["guardado"]:
        _borrar(os.path.join(dir_guardados(), fila["nombre"]))
        _avisar("Quitado de guardados", _resumen(fila["ruta"], fila["nombre"], 60))
    else:
        _copiar_fichero(fila["ruta"], dir_guardados(), fila["nombre"])


def borrar(fila):
    """Fuera de TODAS las listas: si solo se quitara de la suya, volveria a
    salir mas abajo, en el historial, y parece que no ha hecho nada."""
    resumen = _resumen(fila["ruta"], fila["nombre"], 60)
    for carpeta in (dir_fijados(), dir_guardados(), dir_historial()):
        _borrar(os.path.join(carpeta, fila["nombre"]))
    if fila["guardado"]:
        # Lo guardado es lo unico que no vuelve solo: que quede dicho.
        _avisar("Borrado de guardados", resumen)


def menu():
    if not shutil.which("fuzzel"):
        _avisar("Falta fuzzel", "El historial del portapapeles lo necesita")
        return 1
    seleccion = 0
    while True:
        podar()
        filas = listado()
        if not filas:
            _avisar("El portapapeles está vacío",
                    "Lo que copies aparecerá aquí (SUPER+SHIFT+V)")
            return 0
        codigo, i = _fuzzel(filas, min(seleccion, len(filas) - 1))
        if i is None:
            return 0
        fila = filas[i]
        if codigo == 0:
            copiar(fila)
            return 0
        if codigo == TECLA_FIJAR:
            fijar(fila)
        elif codigo == TECLA_GUARDAR:
            guardar(fila)
        elif codigo == TECLA_BORRAR:
            borrar(fila)
        else:
            return 0
        # Se vuelve a abrir sobre la misma entrada, que puede haber cambiado de
        # sitio (al fijarla sube arriba del todo).
        nuevas = [f["nombre"] for f in listado()]
        seleccion = nuevas.index(fila["nombre"]) if fila["nombre"] in nuevas else i


# ─────────────────────────────────────────────────────────────────────────────
# El demonio
# ─────────────────────────────────────────────────────────────────────────────

def _hyprland_vive(sig):
    """¿Contesta el Hyprland de esa firma? Lo que vale es el connect: «existe la
    carpeta de la instancia» no sirve, Hyprland no siempre la limpia."""
    ruta = os.path.join(_runtime(), "hypr", sig, ".socket.sock")
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect(ruta)
        return True
    except OSError:
        return False
    finally:
        s.close()


def limpiar_sesiones_muertas():
    """Borra el historial y los fijados de las sesiones que ya no estan.

    Sin firma no se reclama nada: sin saber cual es la nuestra, «las demas» son
    todas, y alguna puede ser de una sesion viva."""
    sig = firma()
    if not sig:
        return []
    borradas = []
    try:
        nombres = os.listdir(_runtime())
    except OSError:
        return []
    for n in nombres:
        if not n.startswith(PREFIJO):
            continue
        otra = n[len(PREFIJO):]
        if otra == sig or (otra != "sin-sesion" and _hyprland_vive(otra)):
            continue
        shutil.rmtree(os.path.join(_runtime(), n), ignore_errors=True)
        borradas.append(n)
    return borradas


def demonio():
    if not shutil.which("wl-paste"):
        _avisar("Falta wl-clipboard", "El historial del portapapeles lo necesita")
        return 1
    limpiar_sesiones_muertas()
    carpeta = _crear(dir_sesion())
    # Uno por sesion. El cerrojo lo hereda wl-paste (el exec conserva el
    # descriptor) y se suelta solo cuando muere: sin ficheros de PID que se
    # queden viejos.
    cerrojo = os.open(os.path.join(carpeta, "demonio.lock"),
                      os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(cerrojo, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("portapapeles: ya hay uno vigilando en esta sesion", file=sys.stderr)
        return 0
    os.set_inheritable(cerrojo, True)
    os.execvp("wl-paste", ["wl-paste", "--watch", sys.executable, SCRIPT, "recibir"])
    return 1   # no se llega: execvp no vuelve


def _vigilando():
    ruta = os.path.join(dir_sesion(), "demonio.lock")
    try:
        fd = os.open(ruta, os.O_RDONLY)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return False   # nadie lo tenia
    except OSError:
        return True
    finally:
        os.close(fd)


def ver():
    a = ajustes()
    h, fj, g = (len(_entradas(d)) for d in (dir_historial(), dir_fijados(), dir_guardados()))
    print(f"vigilando:  {'si' if _vigilando() else 'NO (portapapeles.py demonio)'}")
    print(f"historial:  {h} de {a['maximo']} como mucho, se olvidan a las {a['horas']:g} h")
    print(f"            {dir_historial()}")
    print(f"fijados:    {fj} (hasta cerrar sesion)  {dir_fijados()}")
    print(f"guardados:  {g} (para siempre)  {dir_guardados()}")
    print(f"ajustes:    {fichero_ajustes()}"
          f"{'' if os.path.exists(fichero_ajustes()) else ' (no existe: valen los de fabrica)'}")
    return 0


def vaciar():
    for n, _ in _entradas(dir_historial()):
        _borrar(os.path.join(dir_historial(), n))
    return 0


def main(args):
    verbos = {"demonio": demonio, "recibir": recibir, "menu": menu,
              "vaciar": vaciar, "--ver": ver, "ver": ver}
    if len(args) != 1 or args[0] not in verbos:
        print(__doc__.split("LAS TRES")[0].strip(), file=sys.stderr)
        return 2
    return verbos[args[0]]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
