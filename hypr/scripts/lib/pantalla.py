#!/usr/bin/env python3
"""
~/dotfiles/hypr/scripts/lib/pantalla.py

Que pantalla hay delante, y que medidas le tocan.

POR QUE EXISTE
--------------
Este repo se usa en dos equipos con pantallas distintas (1920x1080 y 1366x768) y
hasta ahora las medidas iban escritas a mano en pixeles, pensadas para la del
autor. Eso reventó de verdad: el velo de la pantalla de bloqueo tenia
`size = 1920, 1080` y en la laptop hyprlock NO lo recorto —lo reescalo— dejando
un rectangulo oscuro de 1089x612 pegado a la esquina de arriba a la izquierda,
con un escalon a la vista. Se arreglo poniendolo en porcentaje, pero el resto de
numeros (el tamano de la tarjeta, las fuentes del reloj, las tarjetas del
selector de fondos) seguian cableados al monitor del autor.

Aqui se pregunta UNA vez que pantalla hay y se derivan las medidas de ella. Nadie
mas vuelve a escribir un 1920.

TODO SE MIDE EN CALIENTE, NO SE GENERA AL INSTALAR. Es a proposito: un fichero
generado en la instalacion se queda viejo en cuanto cambias de monitor, conectas
un proyector o mueves el disco a otro equipo. Preguntandolo al arrancar, clonar
el repo y usarlo es lo mismo.

DE DONDE SALEN LOS DATOS, en este orden:
  1. Hyprland por su socket de control. Es la verdad: sabe el modo, la escala y
     la rotacion de verdad, y funciona igual dentro de una instancia anidada.
  2. /sys/class/drm, leyendo el modo preferido de cada salida conectada. Sirve
     cuando no hay compositor: instalar.sh se puede ejecutar desde un TTY.
  3. 1920x1080. El ultimo recurso, para que nada se quede sin numero.

USO DESDE LA TERMINAL
    pantalla.py                 resumen de lo que hay
    pantalla.py --json          todo, para otro script
    pantalla.py ancho|alto|escala|factor|nombre|refresco
    pantalla.py --hyprlock      fragmento hyprlang con las medidas del bloqueo
    pantalla.py --monitor       la linea `monitor =` que corresponde a esta salida

USO DESDE PYTHON
    import pantalla
    p = pantalla.principal()        # {'nombre', 'ancho', 'alto', 'escala', ...}
    m = pantalla.medidas()          # medidas ya derivadas para esta pantalla
"""

import json
import os
import socket
import sys

# La pantalla para la que se penso todo el escritorio. No es "la buena": es
# solamente el punto de comparacion del que salen las proporciones.
BASE_ANCHO = 1920
BASE_ALTO = 1080

# Limites del factor de escala. Sin ellos, una pantalla muy pequena dejaria el
# reloj del bloqueo ilegible y una 4K lo pondria del tamano de un cartel.
FACTOR_MIN = 0.62
FACTOR_MAX = 2.20

RUNTIME = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"

# Rotaciones que intercambian ancho y alto (90 y 270 grados, con y sin espejo).
# Hyprland numera las transformadas de 0 a 7 igual que wl_output.
TRANSFORMADAS_GIRADAS = (1, 3, 5, 7)

_cache = None


# --- De donde salen los datos -------------------------------------------------

def _hypr(comando):
    """Pregunta al socket de control de Hyprland. Cadena vacia si no se puede."""
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not sig:
        return ""
    ruta = os.path.join(RUNTIME, "hypr", sig, ".socket.sock")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(ruta)
            s.sendall(comando.encode())
            trozos = []
            while True:
                trozo = s.recv(8192)
                if not trozo:
                    break
                trozos.append(trozo)
        return b"".join(trozos).decode(errors="replace")
    except OSError:
        return ""


def _de_hyprland():
    """Los monitores tal y como los ve el compositor, o [] si no hay sesion."""
    try:
        crudos = json.loads(_hypr("j/monitors"))
    except ValueError:
        return []
    salida = []
    for m in crudos:
        try:
            ancho, alto = int(m["width"]), int(m["height"])
        except (KeyError, TypeError, ValueError):
            continue
        # Una pantalla girada mide al reves de lo que dice su modo.
        if m.get("transform", 0) in TRANSFORMADAS_GIRADAS:
            ancho, alto = alto, ancho
        salida.append({
            "nombre": m.get("name") or "?",
            "descripcion": m.get("description") or "",
            "ancho": ancho,
            "alto": alto,
            "refresco": round(float(m.get("refreshRate") or 0), 3),
            "escala": round(float(m.get("scale") or 1) or 1, 6),
            "x": int(m.get("x") or 0),
            "y": int(m.get("y") or 0),
            "activo": bool(m.get("focused")),
            "origen": "hyprland",
        })
    return salida


def _de_drm():
    """Modo preferido de cada salida conectada, leido del kernel.

    Es el respaldo para cuando no hay compositor al que preguntar (instalar.sh
    ejecutado desde un TTY, por ejemplo). El kernel no sabe nada de escalas ni de
    como estan colocadas las pantallas, asi que eso se da por defecto.
    """
    salida = []
    base = "/sys/class/drm"
    try:
        conectores = sorted(os.listdir(base))
    except OSError:
        return []
    for conector in conectores:
        carpeta = os.path.join(base, conector)
        try:
            with open(os.path.join(carpeta, "status")) as fh:
                if fh.read().strip() != "connected":
                    continue
            with open(os.path.join(carpeta, "modes")) as fh:
                modo = fh.readline().strip()
        except OSError:
            continue
        try:
            ancho, alto = (int(n) for n in modo.split("x", 1))
        except ValueError:
            continue
        # "card1-HDMI-A-1" -> "HDMI-A-1", que es como lo nombra Hyprland.
        nombre = conector.split("-", 1)[1] if "-" in conector else conector
        salida.append({
            "nombre": nombre,
            "descripcion": "",
            "ancho": ancho,
            "alto": alto,
            "refresco": 0.0,
            "escala": 1.0,
            "x": 0,
            "y": 0,
            "activo": not salida,      # el primero conectado hace de principal
            "origen": "drm",
        })
    return salida


def _por_defecto():
    return [{
        "nombre": "?",
        "descripcion": "",
        "ancho": BASE_ANCHO,
        "alto": BASE_ALTO,
        "refresco": 0.0,
        "escala": 1.0,
        "x": 0,
        "y": 0,
        "activo": True,
        "origen": "defecto",
    }]


def monitores(recargar=False):
    """Todas las pantallas encontradas. La lista nunca sale vacia."""
    global _cache
    if _cache is None or recargar:
        _cache = _de_hyprland() or _de_drm() or _por_defecto()
    return _cache


def principal(recargar=False):
    """La pantalla que manda: la que tiene el foco, o la primera que haya.

    Con varios monitores hay que elegir uno, porque las medidas de un fragmento
    de hyprlock o de una ventana son un solo numero. Se elige donde esta mirando
    el usuario, que es donde va a salir el bloqueo o el selector.
    """
    lista = monitores(recargar)
    return next((m for m in lista if m.get("activo")), lista[0])


# --- Medidas derivadas --------------------------------------------------------

def logico(mon=None):
    """Tamano en pixeles LOGICOS, que es en los que piensan hyprlock y GTK.

    Con escala 1 es el tamano de verdad. Con escala 1.5 en una 4K, el escritorio
    se comporta como uno de 2560x1440: es ese el numero contra el que hay que
    medir una fuente, no los 3840 fisicos.
    """
    mon = mon or principal()
    escala = mon.get("escala") or 1.0
    return (int(round(mon["ancho"] / escala)), int(round(mon["alto"] / escala)))


def factor(mon=None):
    """Cuanto hay que encoger o agrandar lo pensado para 1920x1080.

    Se toma el MENOR de los dos lados a proposito. Si se tomara el ancho, una
    pantalla apaisada de portatil (1366x768) dejaria la tarjeta del bloqueo mas
    alta que el hueco disponible; con el menor, lo que cabia sigue cabiendo.
    """
    ancho, alto = logico(mon)
    crudo = min(ancho / BASE_ANCHO, alto / BASE_ALTO)
    return round(max(FACTOR_MIN, min(FACTOR_MAX, crudo)), 4)


def px(valor, mon=None):
    """Un numero pensado para 1080p, ya traido a esta pantalla."""
    return int(round(valor * factor(mon)))


def medidas(mon=None):
    """Todo lo que depende del tamano de la pantalla, en un solo diccionario.

    Quien necesite una medida la pide aqui y no la calcula por su cuenta: asi hay
    un unico sitio donde mirar por que algo se ve de un tamano.
    """
    mon = mon or principal()
    ancho, alto = logico(mon)
    f = factor(mon)
    return {
        "nombre": mon["nombre"],
        "ancho": ancho,
        "alto": alto,
        "escala": mon.get("escala") or 1.0,
        "refresco": mon.get("refresco") or 0.0,
        "origen": mon.get("origen", "?"),
        "factor": f,

        # --- Pantalla de bloqueo (hyprlock) ---
        # El velo NO esta aqui: va en porcentaje dentro de hyprlock.conf, que es
        # lo unico que garantiza que cubra la pantalla entera.
        "lock_tarjeta_w": px(330, mon),
        "lock_tarjeta_h": px(210, mon),
        "lock_tarjeta_y": px(60, mon),
        "lock_rounding": max(8, px(18, mon)),
        "lock_titulo": px(26, mon),
        "lock_titulo_y": px(132, mon),
        "lock_usuario": px(13, mon),
        "lock_usuario_y": px(104, mon),
        "lock_reloj": px(54, mon),
        "lock_reloj_y": px(62, mon),
        "lock_fecha": px(12, mon),
        "lock_fecha_y": px(26, mon),
        "lock_campo_w": px(330, mon),
        "lock_campo_h": px(46, mon),
        "lock_campo_y": px(-75, mon),

        # --- Selector de fondos (CeliuzPaper) ---
        # La tarjeta es 16:9 porque esa es la forma de un fondo de pantalla; solo
        # cambia lo grande que se dibuja.
        "paper_tarjeta_w": max(150, px(220, mon)),
        "paper_tarjeta_h": max(84, px(124, mon)),
        "paper_separacion": max(8, px(14, mon)),
        "paper_margen": max(22, px(46, mon)),
        # El velo de abajo se mide contra el ALTO de la pantalla y no con el
        # factor: es la franja que tapa el fondo, y tiene que ocupar la misma
        # proporcion de pantalla en cualquiera de las dos.
        "paper_velo": int(round(alto * 0.352)),
        "paper_radio": max(8, px(14, mon)),
    }


def fragmento_hyprlock(mon=None):
    """Las medidas del bloqueo, en hyprlang, listas para `source`.

    Se escribe en cache y hyprlock.conf lo carga DESPUES de sus propios valores
    por defecto. El orden importa y es la parte segura del diseno: hyprlang deja
    redefinir una variable y gana la ultima (medido en un Hyprland anidado), asi
    que este fichero PISA a los numeros de 1080p. Y si algun dia no existiera,
    hyprlock se queja de un `source` que falta pero sigue dibujando con los
    valores de fabrica, en vez de quedarse sin pantalla de bloqueo.
    """
    m = medidas(mon)
    lineas = [
        "# GENERADO por hypr/scripts/lib/pantalla.py — NO EDITAR A MANO.",
        "#",
        f"# Medidas para {m['nombre']} ({m['ancho']}x{m['alto']} logicos, "
        f"escala {m['escala']:g}, factor {m['factor']:g}).",
        "# Se reescribe en cada bloqueo, asi que cambiar de monitor no deja nada viejo.",
        "",
    ]
    for clave, valor in sorted(m.items()):
        if clave.startswith("lock_"):
            lineas.append(f"${clave} = {valor}")
    return "\n".join(lineas) + "\n"


def linea_monitor(mon=None):
    """La linea `monitor =` que describe esta salida, por si se quiere fijar."""
    mon = mon or principal()
    refresco = f"@{mon['refresco']:g}" if mon.get("refresco") else ""
    return (f"monitor = {mon['nombre']}, {mon['ancho']}x{mon['alto']}{refresco}, "
            f"{mon['x']}x{mon['y']}, {mon.get('escala') or 1:g}")


# --- Terminal -----------------------------------------------------------------

def _resumen():
    lista = monitores()
    m = medidas()
    fuente = {"hyprland": "preguntado a Hyprland",
              "drm": "leido del kernel (sin compositor)",
              "defecto": "NO detectada: valores de reserva"}.get(m["origen"], m["origen"])
    print(f"\n  PANTALLA  ·  {fuente}\n")
    for mon in lista:
        marca = "●" if mon is principal() else " "
        refresco = f"@{mon['refresco']:g}Hz" if mon.get("refresco") else ""
        print(f"  {marca} {mon['nombre']:<12} {mon['ancho']}x{mon['alto']}{refresco}"
              f"  escala {mon['escala']:g}"
              + (f"   {mon['descripcion']}" if mon["descripcion"] else ""))
    print(f"\n  Logicos: {m['ancho']}x{m['alto']}   ·   factor {m['factor']:g} "
          f"(1 = la pantalla para la que se escribio todo, {BASE_ANCHO}x{BASE_ALTO})\n")
    print("  De ahi salen, entre otras:")
    print(f"    bloqueo   tarjeta {m['lock_tarjeta_w']}x{m['lock_tarjeta_h']}"
          f"   reloj {m['lock_reloj']}px   campo {m['lock_campo_w']}x{m['lock_campo_h']}")
    print(f"    fondos    tarjeta {m['paper_tarjeta_w']}x{m['paper_tarjeta_h']}"
          f"   velo {m['paper_velo']}px   margen {m['paper_margen']}px")
    if m["origen"] == "defecto":
        print("\n  ! No se pudo detectar ninguna pantalla. Se usan los valores de")
        print("    reserva; nada se rompe, pero las medidas no seran las de tu monitor.")
    print()


def main():
    args = sys.argv[1:]
    orden = args[0] if args else ""

    if orden in ("-h", "--help"):
        return print(__doc__.strip())
    if orden == "--json":
        return print(json.dumps({"monitores": monitores(), "medidas": medidas()},
                                indent=2, ensure_ascii=False))
    if orden == "--hyprlock":
        return sys.stdout.write(fragmento_hyprlock())
    if orden == "--monitor":
        return print(linea_monitor())
    if orden in ("ancho", "alto", "escala", "factor", "nombre", "refresco"):
        mon = principal()
        ancho, alto = logico(mon)
        valores = {"ancho": ancho, "alto": alto, "escala": f"{mon['escala']:g}",
                   "factor": f"{factor(mon):g}", "nombre": mon["nombre"],
                   "refresco": f"{mon['refresco']:g}"}
        return print(valores[orden])
    if orden:
        sys.exit(f"pantalla: no entiendo «{orden}». Prueba --help")
    _resumen()


if __name__ == "__main__":
    main()
