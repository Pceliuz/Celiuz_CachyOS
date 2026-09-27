#!/usr/bin/env python3
"""
hypr/scripts/modo-gaming.py — entrar y salir del modo gaming.

Uso:
    modo-gaming.py toggle             entra o sale, preguntando antes (el atajo)
    modo-gaming.py on  [--sin-preguntar]
    modo-gaming.py off [--sin-preguntar] [--forzar]   (con un juego abierto no sale
                                      salvo con --forzar)
    modo-gaming.py estado [--json]    sale con 0 si esta puesto y 1 si no
    modo-gaming.py ir N               ir al escritorio N del modo (si tiene algo)
    modo-gaming.py anadir-app         elegir con fuzzel una app permitida

QUE HACE AL ENTRAR
------------------
Quitar de en medio todo lo que no sea jugar, para que la GPU y la CPU sean del
juego:
  - cierra las ventanas que no son juegos, lanzadores ni apps permitidas
    (catalogo.py). Se PIDE, como la X de la ventana: si una app tiene trabajo
    sin guardar, lo pregunta ella (kitty con un proceso dentro no se deja
    cerrar, medido en anidado). Las terminales se quedan salvo que
    `cerrar_terminales` diga lo contrario: cuestan casi nada y pueden llevar
    una sesion SSH o una compilacion (el mismo criterio que el bloqueo);
  - apaga el fondo en video (wallpaper-pause.py mata mpvpaper, que es VRAM)
    y quita las barras (waybar-autohide.py las mata);
  - apaga blur, sombras y animaciones, y apunta como estaban para devolverlo;
  - pone los avisos en «no molestar» (si ya lo estaban, al salir se quedan);
  - corre los ganchos de ~/.config/celiuz/modo-gaming.d/ y arranca Steam (en la
    bandeja, con el overlay de MangoHud);
  - lo que se quedo abierto se guarda en un escritorio oculto, y en el 1 queda
    solo la biblioteca (el reparto entero, junto a WS_BIBLIOTECA);
  - si el usuario tiene `video_entrada` en su modo-gaming.json, todo esto pasa
    DETRAS de ese video, que termina en la biblioteca.
Los servicios del sistema (audio, red, Bluetooth, portales) no se tocan nunca.

Y al salir, lo contrario (con `video_salida` delante, si lo hay): cada ventana
guardada vuelve a su escritorio, y lo abierto durante el modo va a donde
estabas al entrar. Steam y los juegos NO se cierran al salir: el modo decide
que se ve, no lo que el usuario tenga corriendo.

LOS GANCHOS (~/.config/celiuz/modo-gaming.d/)
---------------------------------------------
Cada ejecutable de esa carpeta se corre con `on` al entrar y `off` al salir,
en segundo plano y sin esperarle. Es la puerta para lo que es de CADA equipo y
no pinta nada en un repo publico: pausar un asistente, bajar un servicio
propio... Vacia para quien clona.

EL ESTADO
---------
En $XDG_RUNTIME_DIR/modo-gaming.<firma>.json, con la firma de la sesion igual
que los FIFO (lib/canales.py): dos sesiones vivas del mismo usuario no pueden
creerse las dos en modo gaming por compartir carpeta. Guarda lo necesario para
deshacer (los efectos como estaban, si el «no molestar» lo puso el modo).

LO QUE NO AGUANTA (a proposito, por ahora)
------------------------------------------
Una recarga de la config de Hyprland devuelve blur y animaciones, y relanzar el
demonio de las barras las levanta: los dos leen su estado de cero. Salir y
volver a entrar lo arregla.
"""

import glob
import json
import os
import stat
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(AQUI, "lib"))

import canales  # noqa: E402
import catalogo  # noqa: E402
import hypr  # noqa: E402
import juegos  # noqa: E402
import mando  # noqa: E402

LANZAR = os.path.join(AQUI, "lanzar.sh")
BIBLIOTECA = os.path.join(AQUI, "biblioteca.py")
TARJETA = os.path.join(AQUI, "modo-gaming-tarjeta.py")
MENU = os.path.join(AQUI, "menu-rapido.py")
# Select + Start a la vez abre el menu rapido desde el mando, jugando. Una
# combinacion que ningun juego usa sola, y no el boton central, que es de Steam.
ACORDE_MENU = {0x13A, 0x13B}

# Lo que cambia al entrar, y a que valor. Se lee antes con getoption y al salir
# se devuelve tal cual estaba.
#   blur, sombras, animaciones: GPU que es del juego.
#   on_focus_under_fullscreen = 0: una ventana nueva NO le quita la pantalla
#     completa a quien la tenga. Con el valor de fabrica (2) la biblioteca —o el
#     juego— se partia la pantalla con cualquier ventana que se abriera encima
#     (medido en anidado). Lo que tenga que verse, el vigilante lo pone
#     flotando por encima (ver vigilar()).
EFECTOS = {
    "decoration:blur:enabled": "false",
    "decoration:shadow:enabled": "false",
    "animations:enabled": "false",
    "misc:on_focus_under_fullscreen": "0",
    # Sin el fondo de fabrica de Hyprland (su logo o su imagen): con el video de
    # fondo apagado es lo que se veia detras de las ventanas pequeñas de los
    # lanzadores de Warframe o Soulframe. Negro, como pidio el usuario.
    "misc:disable_hyprland_logo": "true",
    "misc:force_default_wallpaper": "0",
}

# Ventanas que no se cierran nunca, por clase (en minusculas, subcadena).
SIEMPRE = ("steam",)

# LOS ESCRITORIOS DEL MODO (lo pidio asi el usuario, 2026-09-26):
#   1        la biblioteca, sola; el juego que lances desde ella se abre AHI y
#            la biblioteca se cierra. Si el juego se cierra, vuelve la biblioteca.
#   2, 3...  cada app o juego que abras mientras (desde el menu rapido, o una
#            terminal con SUPER+Enter) va al SIGUIENTE, y te lleva. No hay
#            escritorios vacios: si uno se queda sin nada, los de detras corren
#            un puesto, y no se puede ir a uno que no tenga nada.
#   oculto   lo que ya estaba abierto al entrar (terminales, navegador...): a un
#            escritorio especial que no se ve ni se compone, y al salir vuelve
#            cada ventana al numero en que estaba.
# Cada cosa en su escritorio es tambien lo que menos gasta: Hyprland no compone
# ni pide fotogramas a lo que no se ve, y un juego solo y a pantalla completa
# puede ir directo a la pantalla.
WS_BIBLIOTECA = 1
GUARDADAS = "special:modo-gaming"
CLASE_BIBLIOTECA = "celiuz-biblioteca"
CLASE_VIDEO = "celiuz-video"   # el video de entrada o de salida (mpv)
# Las ventanas de Steam que son su ventana principal (van a apps). Las demas
# —«Launching…», el procesado de shaders, avisos— se quedan donde salen: son
# justo lo que tienes que ver al lanzar un juego.
STEAM_PRINCIPALES = ("steam", "friends list", "lista de amigos")


# --- Rutas -------------------------------------------------------------------
def ruta_estado():
    """La del estado de ESTA sesion. Sin firma (a mano desde un TTY) se usa la
    unica que haya; con varias no se adivina (misma regla que lib/canales.py)."""
    sig = canales.firma()
    if sig:
        return os.path.join(canales.RUNTIME, "modo-gaming.%s.json" % sig)
    sueltos = glob.glob(os.path.join(canales.RUNTIME, "modo-gaming.*.json"))
    if len(sueltos) == 1:
        return sueltos[0]
    return os.path.join(canales.RUNTIME, "modo-gaming.sin-sesion.json")


def carpeta_ganchos():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "celiuz", "modo-gaming.d")


def shutil_which(programa):
    import shutil
    return shutil.which(programa)


def leer_estado():
    try:
        with open(ruta_estado(), encoding="utf-8") as fh:
            datos = json.load(fh)
        return datos if isinstance(datos, dict) and datos.get("activo") else None
    except (OSError, ValueError):
        return None


def guardar_estado(datos):
    ruta = ruta_estado()
    temporal = ruta + ".nuevo"
    with open(temporal, "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=2)
    os.replace(temporal, ruta)


# --- Hablar con los demas ----------------------------------------------------
def _hyprctl(*args):
    try:
        r = subprocess.run(["hyprctl"] + list(args), capture_output=True, text=True,
                           timeout=5, check=False)
        return r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def mandar_fifo(ruta, texto):
    """Escribe una orden en el FIFO de un demonio. False si no hay FIFO.

    Se comprueba que ES un FIFO antes de abrir: un `open` sobre una ruta que no
    existe crearia un fichero normal y la orden se perderia callada (la trampa
    del CLAUDE.md con `echo x > ruta-sin-fifo`). Sin bloquear: si el demonio no
    esta leyendo, se sigue."""
    try:
        if not stat.S_ISFIFO(os.stat(ruta).st_mode):
            return False
        fd = os.open(ruta, os.O_WRONLY | os.O_NONBLOCK)
    except OSError:
        return False
    try:
        os.write(fd, (texto + "\n").encode())
        return True
    except OSError:
        return False
    finally:
        os.close(fd)


def leer_opcion(clave):
    """El valor de una opcion como texto «true»/«false»/numero, o None.

    En Lua getoption devuelve `"bool": true` y en hyprlang `"int": 1` (CLAUDE.md,
    «La config es Lua»): se miran los dos."""
    try:
        datos = json.loads(_hyprctl("getoption", clave, "-j") or "{}")
    except ValueError:
        return None
    if "bool" in datos:
        return "true" if datos["bool"] else "false"
    if "int" in datos:
        return str(datos["int"])
    if "float" in datos:
        return str(datos["float"])
    return None


def poner_opcion(modo, clave, valor):
    verbo, resto = hypr.peticion_keyword(modo, clave, valor)
    if verbo == "keyword":
        clave_, _, valor_ = resto.partition(" ")
        return _hyprctl("keyword", clave_, valor_)
    return _hyprctl(verbo, resto)


def makoctl(*args):
    try:
        r = subprocess.run(["makoctl"] + list(args), capture_output=True, text=True,
                           timeout=3, check=False)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def correr_ganchos(fase):
    carpeta = carpeta_ganchos()
    try:
        nombres = sorted(os.listdir(carpeta))
    except OSError:
        return []
    corridos = []
    for nombre in nombres:
        ruta = os.path.join(carpeta, nombre)
        if nombre.startswith(".") or not os.path.isfile(ruta) or not os.access(ruta, os.X_OK):
            continue
        try:
            subprocess.Popen([ruta, fase], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
            corridos.append(nombre)
        except OSError:
            pass
    return corridos


# --- Que ventanas se quedan ----------------------------------------------------
def _proceso(pid):
    """(nombres, ruta del ejecutable, linea de ordenes) de un pid."""
    nombres, ruta, orden = set(), "", ""
    try:
        with open("/proc/%d/comm" % pid) as fh:
            nombres.add(fh.read().strip().lower())
    except OSError:
        pass
    try:
        ruta = os.readlink("/proc/%d/exe" % pid)
        nombres.add(os.path.basename(ruta).lower())
    except OSError:
        pass
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as fh:
            orden = fh.read().replace(b"\0", b" ").decode("utf-8", "replace").lower()
    except OSError:
        pass
    return nombres, ruta.lower(), orden


def _nombre_de_orden(cmd):
    partes = (cmd or "").split()
    return os.path.basename(partes[0]).lower() if partes else ""


def es_juego(ventana):
    """Si el proceso de una ventana es un juego, por las capas de juegos.py
    (Steam/Proton por la ruta del ejecutable, ananicy, flatpak de juego)."""
    pid = ventana.get("pid") or 0
    if pid <= 0:
        return None
    nombres, ruta, orden = _proceso(pid)
    if juegos.HUELLA_STEAM.search(ruta):
        return "juego de Steam"
    if nombres & juegos.nombres_de_juego():
        return "juego"
    if any(f in orden for f in juegos.flatpaks_de_juego()):
        return "juego (flatpak)"
    return None


def _clase(ventana):
    return (ventana.get("class") or ventana.get("initialClass") or "").lower()


def _sin_signos(texto):
    return "".join(c for c in (texto or "").lower() if c.isalnum())


def motivo_para_quedarse(ventana, permitidas, cerrar_terminales):
    """Por que una ventana NO se cierra, o None si se cierra."""
    clase = (ventana.get("class") or ventana.get("initialClass") or "").lower()
    if clase in (CLASE_VIDEO, CLASE_BIBLIOTECA):
        return "del propio modo"
    if any(s in clase for s in SIEMPRE):
        return "lanzador"
    if ventana.get("fullscreen"):
        return "a pantalla completa"
    if not cerrar_terminales and clase in juegos.TERMINALES:
        return "terminal"
    # Se compara sin guiones ni puntos: Brave se lanza como «brave» y su clase es
    # «brave-browser»; Glassy Music se lanza como «glassy-music» y su clase es
    # «nankill.xyz.glassymusic.mod» (con la comparacion literal no casaba, y el
    # modo cerraba la musica del usuario al entrar).
    limpia = _sin_signos(clase)
    for app in permitidas:
        nombre = _sin_signos(_nombre_de_orden(app["cmd"]))
        icono = _sin_signos(app.get("icono") or "")
        if nombre and limpia and (nombre in limpia or limpia in nombre):
            return "app permitida"
        if icono and limpia and (icono == limpia or limpia in icono or icono in limpia):
            return "app permitida"
    return es_juego(ventana)


def cerrar_ventanas(modo, permitidas, cerrar_terminales):
    try:
        ventanas = json.loads(_hyprctl("clients", "-j") or "[]")
    except ValueError:
        return [], []
    cerradas, quedan = [], []
    for v in ventanas:
        if not v.get("mapped", True) or not v.get("address"):
            continue
        motivo = motivo_para_quedarse(v, permitidas, cerrar_terminales)
        nombre = v.get("class") or v.get("title") or v["address"]
        if motivo:
            quedan.append("%s (%s)" % (nombre, motivo))
            continue
        if modo == hypr.LUA:
            _hyprctl("dispatch", 'hl.dsp.window.close({ window = "address:%s" })' % v["address"])
        else:
            _hyprctl("dispatch", "closewindow", "address:%s" % v["address"])
        cerradas.append(nombre)
    return cerradas, quedan


# Ventanas de lanzadores que se cierran cuando empieza un juego (y al salir del
# modo): cerrar la ventana de Steam lo manda a la bandeja, sin matar nada.
CLASES_LANZADOR = ("steam", "heroic", "lutris", "bottles", "itch", "minigalaxy")


def es_ventana_de_lanzador(ventana):
    clase = _clase(ventana)
    if clase.startswith("steam_app_") or es_dialogo_steam(ventana):
        return False
    return any(c in clase for c in CLASES_LANZADOR)


# --- Escritorios ----------------------------------------------------------------
def clientes():
    try:
        return json.loads(_hyprctl("clients", "-j") or "[]")
    except ValueError:
        return []


def escritorio_activo():
    try:
        return json.loads(_hyprctl("activeworkspace", "-j") or "{}")
    except ValueError:
        return {}


def _donde(nombre):
    """El selector de escritorio: un numero, o un nombre (con `name:` delante,
    salvo los especiales, que ya lo llevan)."""
    n = str(nombre)
    if n.lstrip("-").isdigit() or n.startswith("special:"):
        return n
    return "name:%s" % n


def ir(modo, nombre):
    _hyprctl("dispatch", hypr.peticion_dispatch(modo, "workspace", _donde(nombre)))


def mover(modo, direccion, nombre, seguir=False):
    donde = _donde(nombre)
    if modo == hypr.LUA:
        _hyprctl("dispatch", 'hl.dsp.window.move({ workspace = %s, window = "address:%s", follow = %s })'
                 % (donde if donde.lstrip("-").isdigit() else hypr.cadena_lua(donde),
                    direccion, "true" if seguir else "false"))
    else:
        _hyprctl("dispatch", "movetoworkspace" if seguir else "movetoworkspacesilent",
                 "%s,address:%s" % (donde, direccion))


def cerrar_ventana(modo, direccion):
    if modo == hypr.LUA:
        _hyprctl("dispatch", 'hl.dsp.window.close({ window = "address:%s" })' % direccion)
    else:
        _hyprctl("dispatch", "closewindow", "address:%s" % direccion)


def _en(ventana):
    return (ventana.get("workspace") or {}).get("name", "")


def num_ws(ventana):
    """El numero de escritorio de una ventana, o None si esta en uno especial
    (los especiales tienen id negativo) o no se sabe."""
    i = (ventana.get("workspace") or {}).get("id")
    return i if isinstance(i, int) and i >= 1 else None


def es_dialogo_steam(ventana):
    """Una ventana de Steam que no es su ventana principal: «Launching…», el
    procesado de shaders, avisos. Se deja donde sale: es lo que hay que ver."""
    if "steam" not in _clase(ventana) or _clase(ventana).startswith("steam_app_"):
        return False
    return (ventana.get("title") or "").strip().lower() not in STEAM_PRINCIPALES


def es_de_juego(ventana):
    """Ventana de un juego (Steam/Proton, ananicy, flatpak de juego). Sin mirar
    la pantalla completa: el video del modo tambien lo esta."""
    return _clase(ventana) not in (CLASE_BIBLIOTECA, CLASE_VIDEO) \
        and "steam" != _clase(ventana) and bool(es_juego(ventana))


def huella_app(pid):
    """Lo que dice que dos ventanas son de la MISMA app, para que un segundo
    ventanal suyo (una llamada de WhatsApp en Brave, el juego que sale tras su
    lanzador) vaya con el primero y no a un escritorio nuevo:
      - un juego de Steam: su SteamAppId (todos los juegos de Steam comparten el
        grupo de procesos de Steam, asi que el grupo no los distingue);
      - lo demas: su grupo de procesos (cada app lanzada lleva su scope de
        systemd, ver lanzar.sh)."""
    if not pid:
        return None
    try:
        with open("/proc/%d/environ" % pid, "rb") as fh:
            for par in fh.read().split(b"\0"):
                if par.startswith(b"SteamAppId="):
                    valor = par.split(b"=", 1)[1].decode()
                    if valor and valor != "0":
                        return ("steam", valor)
    except OSError:
        pass
    try:
        with open("/proc/%d/cgroup" % pid) as fh:
            grupo = fh.read().strip().split("::")[-1]
    except OSError:
        return None
    if not grupo or "steam" in grupo.lower() or not grupo.endswith(".scope"):
        return None
    return ("grupo", grupo)


def en_uso(ventanas):
    """Los escritorios numerados con alguna ventana (sin contar el video)."""
    return sorted({num_ws(v) for v in ventanas if num_ws(v) and _clase(v) != CLASE_VIDEO})


def flotar_encima(modo, direccion):
    """Una ventana de Steam salida en la biblioteca («Launching…», shaders):
    flotando, centrada y con el foco, para que se vea encima de la biblioteca
    a pantalla completa (medido en anidado: sin flotar queda detras)."""
    if modo != hypr.LUA:
        for orden in ("setfloating", "centerwindow", "focuswindow"):
            _hyprctl("dispatch", orden, "address:%s" % direccion)
        return
    for dsp in ('hl.dsp.window.float({ action = "enable", window = "address:%s" })',
                'hl.dsp.window.center({ window = "address:%s" })',
                'hl.dsp.focus({ window = "address:%s" })'):
        _hyprctl("dispatch", dsp % direccion)


def biblioteca_abierta(ventanas=None):
    return any(_clase(v) == CLASE_BIBLIOTECA for v in (ventanas if ventanas is not None else clientes()))


def abrir_biblioteca():
    # Sin sesion Wayland no hay donde enseñarla (ver solo_wayland() en ella).
    if not os.path.exists(BIBLIOTECA) or not os.environ.get("WAYLAND_DISPLAY"):
        return
    try:
        subprocess.Popen([sys.executable, BIBLIOTECA], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except OSError:
        pass


ULTIMO_JUEGO = [-1000.0]           # cuando llego la ultima ventana de juego


def colocar_nueva(modo, v, ventanas):
    """Donde va una ventana que se acaba de abrir con el modo puesto."""
    clase = _clase(v)
    ws = num_ws(v)
    if clase == CLASE_VIDEO or ws is None:
        return
    if clase == CLASE_BIBLIOTECA:
        if ws != WS_BIBLIOTECA:
            mover(modo, v["address"], WS_BIBLIOTECA, False)   # sin llevarte
        return
    if es_dialogo_steam(v):
        if ws == WS_BIBLIOTECA and biblioteca_abierta(ventanas):
            flotar_encima(modo, v["address"])
        return
    otras = [x for x in ventanas if x.get("address") != v.get("address") and num_ws(x)
             and _clase(x) not in (CLASE_BIBLIOTECA, CLASE_VIDEO) and not es_dialogo_steam(x)]
    # 1. Otra ventana de la misma app: con ella.
    huella = huella_app(v.get("pid"))
    if huella:
        for x in otras:
            if huella_app(x.get("pid")) == huella:
                if num_ws(x) != ws:
                    mover(modo, v["address"], num_ws(x), True)
                return
    # 2. Un juego, y en el 1 no hay otro: al 1, y la biblioteca se va. Las
    #    ventanas de los lanzadores (Steam...) se cierran: a la bandeja.
    if es_de_juego(v):
        ULTIMO_JUEGO[0] = time.monotonic()
    if es_de_juego(v) and not any(num_ws(x) == WS_BIBLIOTECA and es_de_juego(x) for x in otras):
        if ws != WS_BIBLIOTECA:
            mover(modo, v["address"], WS_BIBLIOTECA, True)
        for x in ventanas:
            if _clase(x) == CLASE_BIBLIOTECA or es_ventana_de_lanzador(x):
                cerrar_ventana(modo, x["address"])
        return
    # 2b. Steam abre su ventana justo DESPUES de arrancar un juego (pasa): se
    #     cierra tambien, si el juego empezo hace nada.
    if es_ventana_de_lanzador(v) and time.monotonic() - ULTIMO_JUEGO[0] < 45:
        cerrar_ventana(modo, v["address"])
        return
    # 3. Lo demas (una app, otro juego mas): al escritorio siguiente, y te lleva.
    siguiente = max([num_ws(x) for x in otras if num_ws(x)] + [WS_BIBLIOTECA]) + 1
    mover(modo, v["address"], siguiente, True)


def recolocar(modo):
    """Tras cerrarse una ventana: el 1 nunca queda vacio (vuelve la biblioteca),
    los demas sin huecos, y si te quedaste en uno vacio, al anterior."""
    ventanas = clientes()
    activo = escritorio_activo().get("id")
    usados = en_uso(ventanas)
    if WS_BIBLIOTECA not in usados:
        if not biblioteca_abierta(ventanas):
            abrir_biblioteca()
        if activo not in usados:
            ir(modo, WS_BIBLIOTECA)
            activo = WS_BIBLIOTECA
    for i, n in enumerate([n for n in usados if n > WS_BIBLIOTECA]):
        objetivo = WS_BIBLIOTECA + 1 + i
        if n == objetivo:
            continue
        for v in ventanas:
            if num_ws(v) == n:
                mover(modo, v["address"], objetivo, False)
        if activo == n:
            ir(modo, objetivo)
            activo = objetivo
    ventanas = clientes()
    usados = en_uso(ventanas)
    if activo not in usados and activo and activo > WS_BIBLIOTECA:
        ir(modo, max([n for n in usados if n < activo] + [WS_BIBLIOTECA]))


def vigilar():
    """El vigilante: mientras dure el modo, cada ventana nueva a su escritorio
    (ver la tabla de arriba, junto a WS_BIBLIOTECA), sin huecos, y sin dejarte
    ir a un escritorio que no tenga nada. Tambien escucha el mando para abrir
    el menu rapido con Select + Start."""
    import select
    import socket
    modo = hypr.modo()
    ruta = os.path.join(canales.RUNTIME, "hypr", canales.firma(), ".socket2.sock")
    try:
        eventos = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        eventos.connect(ruta)
    except OSError:
        return 1
    buffer = b""
    mandos = {}                         # fd -> botones pulsados ahora
    buscado = 0.0
    bueno = WS_BIBLIOTECA               # el ultimo escritorio valido en que estuviste
    while True:
        # Los mandos, para Select + Start. Solo se buscan si no hay ninguno, y
        # como mucho cada 5 s (abrir cada /dev/input cuesta, ver lib/mando.py).
        if not mandos and time.monotonic() - buscado > 5:
            buscado = time.monotonic()
            for _, fd, _ in mando.buscar():
                mandos[fd] = set()
        listos, _, _ = select.select([eventos] + list(mandos), [], [], 2.0)
        if not leer_estado():
            return 0                    # el modo se quito: me voy
        for fd in [x for x in listos if x in mandos]:
            if leer_mando(fd, mandos):
                abrir_menu()
        if eventos not in listos:
            continue
        trozo = eventos.recv(8192)
        if not trozo:
            return 0                    # Hyprland se fue
        buffer += trozo
        *lineas, buffer = buffer.split(b"\n")
        for linea in lineas:
            evento, _, datos = linea.decode("utf-8", "replace").partition(">>")
            if evento == "openwindow":
                direccion = "0x" + datos.split(",")[0]
                ventanas = clientes()
                v = next((x for x in ventanas if x.get("address") == direccion), None)
                if v:
                    colocar_nueva(modo, v, ventanas)
            elif evento == "closewindow":
                time.sleep(0.25)
                recolocar(modo)
            elif evento == "workspace":
                if not datos.isdigit():
                    continue
                n = int(datos)
                if n == WS_BIBLIOTECA or n in en_uso(clientes()):
                    bueno = n
                else:
                    ir(modo, bueno)     # a uno vacio no se va


def leer_mando(fd, mandos):
    """Lee lo pendiente de un mando. True si acaba de completarse el acorde."""
    try:
        datos = os.read(fd, mando.EVENTO.size * 64)
    except BlockingIOError:
        return False
    except OSError:
        mandos.pop(fd, None)            # desenchufado
        try:
            os.close(fd)
        except OSError:
            pass
        return False
    pulsados = mandos[fd]
    completo = False
    for i in range(0, len(datos) - mando.EVENTO.size + 1, mando.EVENTO.size):
        _, _, tipo, codigo, valor = mando.EVENTO.unpack_from(datos, i)
        if tipo != mando.EV_KEY or codigo not in ACORDE_MENU:
            continue
        if valor:
            pulsados.add(codigo)
            if pulsados >= ACORDE_MENU:
                completo = True
                pulsados.clear()        # uno por pulsacion, no en bucle
        else:
            pulsados.discard(codigo)
    return completo


def abrir_menu():
    if os.path.exists(MENU) and os.environ.get("WAYLAND_DISPLAY"):
        try:
            subprocess.Popen([sys.executable, MENU], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        except OSError:
            pass


def ir_cli(sitio):
    """`modo-gaming.py ir N` (lo usa el menu rapido): solo a un escritorio con
    algo, o al 1."""
    if not leer_estado():
        print("modo gaming: no esta puesto", file=sys.stderr)
        return 1
    if not sitio.isdigit():
        print("uso: modo-gaming.py ir <numero de escritorio>", file=sys.stderr)
        return 2
    n = int(sitio)
    if n != WS_BIBLIOTECA and n not in en_uso(clientes()):
        print("modo gaming: el escritorio %d no tiene nada" % n, file=sys.stderr)
        return 1
    ir(hypr.modo(), n)
    return 0


def anadir_app():
    """Elegir con fuzzel una app instalada y guardarla entre las permitidas
    (~/.config/celiuz/modo-gaming.json), sin tocar lo demas del fichero."""
    import shutil
    if not shutil.which("fuzzel"):
        print("modo gaming: hace falta fuzzel para elegir la app", file=sys.stderr)
        return 1
    ya = {a["cmd"] for a in catalogo.apps_permitidas()}
    candidatas = []
    for ident, (_, campos) in sorted(catalogo._entradas_desktop().items(),
                                     key=lambda x: (x[1][1].get("Name") or x[0]).lower()):
        if not catalogo._visible(campos) or catalogo.clase_de_desktop(ident, campos):
            continue                    # ni ocultas, ni juegos, ni lanzadores
        cmd = catalogo.apps.limpiar_exec(campos.get("Exec", ""))
        if cmd and cmd not in ya:
            candidatas.append({"label": campos.get("Name") or ident, "cmd": cmd,
                               "icon_name": campos.get("Icon", "")})
    if not candidatas:
        return 1
    try:
        r = subprocess.run(["fuzzel", "--dmenu", "--index", "--prompt", "Añadir al modo gaming: "],
                           input="\n".join(c["label"] for c in candidatas), capture_output=True,
                           text=True, timeout=300)
        indice = int(r.stdout.strip())
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return 1                        # cancelado
    if not 0 <= indice < len(candidatas):
        return 1
    ruta = catalogo.config_usuario()
    datos = catalogo._leer_json(ruta)
    datos.setdefault("apps", []).append(candidatas[indice])
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta + ".nuevo", "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=4)
        fh.write("\n")
    os.replace(ruta + ".nuevo", ruta)
    print("modo gaming: añadida «%s»" % candidatas[indice]["label"])
    return 0


ATAJOS_ESCRITORIO = range(1, 8)       # los SUPER+1..7 de lua/keybinds.lua


def cambiar_atajos_escritorio(modo, en_modo):
    """Mientras dure el modo, SUPER+N pasa por `modo-gaming.py ir N`, que no
    va a un escritorio vacio. Con el atajo de siempre Hyprland CAMBIABA y el
    vigilante te devolvia, y en ese instante se veia el fondo vacio mezclado
    con la ventana de al lado (lo vio el usuario el 2026-09-26). Al salir se
    ponen los de siempre, igual que los escribe lua/keybinds.lua."""
    for i in ATAJOS_ESCRITORIO:
        if modo == hypr.LUA:
            accion = ('hl.dsp.exec_cmd(%s)' % hypr.cadena_lua("%s ir %d" % (os.path.realpath(__file__), i))
                      if en_modo else "hl.dsp.focus({ workspace = %d })" % i)
            desc = ("modo gaming: ir al escritorio %d" if en_modo else "ir al escritorio %d") % i
            _hyprctl("eval", 'hl.unbind("SUPER + %d"); hl.bind("SUPER + %d", %s, { description = "%s" })'
                     % (i, i, accion, desc))
        else:
            _hyprctl("keyword", "unbind", "SUPER,%d" % i)
            if en_modo:
                _hyprctl("keyword", "bind", "SUPER,%d,exec,%s ir %d" % (i, os.path.realpath(__file__), i))
            else:
                _hyprctl("keyword", "bind", "SUPER,%d,workspace,%d" % (i, i))


def arrancar_vigilante():
    try:
        return subprocess.Popen([sys.executable, os.path.realpath(__file__), "vigilar"],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True).pid
    except OSError:
        return None


def parar_vigilante(pid):
    """Por PID, y solo si ese PID sigue siendo NUESTRO vigilante: un PID viejo
    puede haberse reciclado para otro proceso."""
    if not pid:
        return
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as fh:
            orden = fh.read().decode("utf-8", "replace")
    except OSError:
        return
    if "modo-gaming.py" in orden and "vigilar" in orden:
        try:
            os.kill(pid, 15)
        except OSError:
            pass


# --- El overlay (MangoHud) y Steam ------------------------------------------------
PALETA_FABRICA = {"abismo": "0d0418", "apagado": "2d1b4e", "violeta": "6a00f4",
                  "amatista": "b16cff", "neon": "c77dff", "luz": "e4c7ff",
                  "tenue": "8a7aa8", "atencion": "f6c177", "alerta": "eb6f92"}


def paleta_hex():
    """La paleta del repo en hex pelado (lo que quiere MangoHud), leida en
    caliente de waybar/colores.css: el overlay lleva el tono de quien clona el
    repo, no el del autor."""
    colores = dict(PALETA_FABRICA)
    raiz = os.path.dirname(os.path.dirname(AQUI))
    try:
        with open(os.path.join(raiz, "waybar", "colores.css"), encoding="utf-8") as fh:
            for linea in fh:
                partes = linea.split()
                if len(partes) >= 3 and partes[0] == "@define-color" and partes[2].startswith("#"):
                    colores[partes[1]] = partes[2].strip(";#")[:6]
    except OSError:
        pass
    return colores


def fuente_del_repo():
    try:
        r = subprocess.run(["fc-match", "-f", "%{file}", "MesloLGS Nerd Font Propo"],
                           capture_output=True, text=True, timeout=3)
        return r.stdout.strip() if "Meslo" in r.stdout else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def escribir_mangohud():
    """La config del overlay: una barra horizontal arriba a la izquierda con la
    paleta del repo, ESCONDIDA hasta pulsar Supr (`toggle_hud=Delete`, la misma
    tecla que ya usaba la config de Soulframe del autor). La tecla la lee el
    propio MangoHud y no un atajo de Hyprland a proposito: un juego con su
    propia config de MangoHud con esa tecla (Soulframe) alternaria dos veces
    por pulsacion, o sea nada. `control=mangohud` deja ademas esconderlo y
    enseñarlo desde fuera (`mangohudctl`, el boton del menu rapido)."""
    c = paleta_hex()
    fuente = fuente_del_repo()
    lineas = [
        "# GENERADO por hypr/scripts/modo-gaming.py al entrar al modo gaming.",
        "# NO EDITAR: se reescribe cada vez. Los colores salen de colores.conf.",
        "legacy_layout=0",
        "horizontal",
        # Centrada y del ancho de lo que enseña (sin horizontal_stretch se
        # estira a lo ancho de la pantalla, larga y vacia: lo dijo el usuario).
        "position=top-center",
        "horizontal_stretch=0",
        "offset_y=12",
        "round_corners=10",
        "background_alpha=0.62",
        "background_color=%s" % c["abismo"],
        "font_size=18",
    ] + (["font_file=%s" % fuente] if fuente else []) + [
        "text_color=%s" % c["luz"],
        "fps",
        "fps_color_change",
        "fps_value=30,60",
        "fps_color=%s,%s,7dffb0" % (c["alerta"], c["atencion"]),
        "frametime",
        "frame_timing=1",
        "frametime_color=%s" % c["neon"],
        "gpu_stats",
        "gpu_temp",
        "gpu_color=%s" % c["neon"],
        "vram",
        "vram_color=%s" % c["amatista"],
        "cpu_stats",
        "cpu_temp",
        "cpu_color=%s" % c["amatista"],
        "ram",
        "ram_color=%s" % c["tenue"],
        "engine_color=%s" % c["neon"],
        "horizontal_separator_color=%s" % c["apagado"],
        "toggle_hud=Delete",
        "no_display",
        "control=mangohud",
    ]
    ruta = catalogo.ruta_mangohud()
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta + ".nuevo", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lineas) + "\n")
    os.replace(ruta + ".nuevo", ruta)
    return ruta


def pids_de(nombre):
    """Los procesos `nombre` que corren con ESTA casa ($HOME).

    Por nombre a secas seria el `pkill -x` que el repo ya no usa: una prueba,
    con su casa de mentira, veria el Steam de verdad del usuario y le mandaria
    `steam -shutdown`. Steam es de la casa que lo lanzo, asi que la casa es
    el discriminante bueno (mismo principio que lib/canales.py: sin lo nuestro
    no se reclama nada)."""
    casa = ("HOME=" + os.path.expanduser("~")).encode()
    salida = []
    for comm in glob.glob("/proc/[0-9]*/comm"):
        try:
            with open(comm) as fh:
                if fh.read().strip() != nombre:
                    continue
            with open(comm[:-4] + "environ", "rb") as fh:
                if casa in fh.read().split(b"\0"):
                    salida.append(int(comm.split("/")[2]))
        except (OSError, ValueError):
            continue
    return salida


def steam_con_overlay():
    """True/False si el Steam que corre lleva MANGOHUD=1; None si no corre."""
    pids = pids_de("steam")
    if not pids:
        return None
    for pid in pids:
        try:
            with open("/proc/%d/environ" % pid, "rb") as fh:
                if b"MANGOHUD=1\0" in fh.read() + b"\0":
                    return True
        except OSError:
            continue
    return False


def hilos_para_shaders(raiz):
    """Mas hilos para procesar shaders (`steam_dev.cfg`). Steam usa pocos por
    defecto y en la PC del autor tardaba HORAS (CPU de 12 hilos). Se dejan dos
    libres, y si el usuario ya puso su valor, manda el suyo."""
    ruta = os.path.join(raiz, "steam_dev.cfg")
    try:
        with open(ruta, encoding="utf-8", errors="replace") as fh:
            texto = fh.read()
    except OSError:
        texto = ""
    if "unshaderbackgroundprocessingthreads" in texto.lower():
        return
    hilos = max(2, (os.cpu_count() or 4) - 2)
    with open(ruta, "a", encoding="utf-8") as fh:
        if texto and not texto.endswith("\n"):
            fh.write("\n")
        fh.write("unShaderBackgroundProcessingThreads %d\n" % hilos)


def ultimo_jugado_primero(raiz):
    """Reordena la cola de shaders de Steam para que vaya primero el ultimo
    juego jugado. SOLO con Steam cerrado (lo reescribe al salir). Que Steam
    respete el orden de `ProcessingQueue` no esta comprobado todavia."""
    cola = catalogo.cola_de_shaders()
    juegos_ = [j for j in catalogo.juegos_steam() if j["jugado"]["ultima"]]
    if not cola or not juegos_:
        return
    primero = max(juegos_, key=lambda j: j["jugado"]["ultima"])["id"][6:]
    if primero not in cola or cola[0] == primero:
        return
    nueva = [primero] + [x for x in cola if x != primero]
    ruta = os.path.join(raiz, "config", "config.vdf")
    with open(ruta, encoding="utf-8", errors="replace") as fh:
        texto = fh.read()
    import re
    texto2 = re.sub(r'("ProcessingQueue"\s+")[^"]*(")', lambda m: m.group(1) + ";".join(nueva) + ";" + m.group(2),
                    texto, count=1)
    if texto2 != texto:
        with open(ruta + ".celiuz-nuevo", "w", encoding="utf-8") as fh:
            fh.write(texto2)
        os.replace(ruta + ".celiuz-nuevo", ruta)


def procesado_de_fondo(raiz, poner=False):
    """El «Permitir el procesamiento en segundo plano de shaders de Vulkan» de
    Steam (`EnableShaderBackgroundProcessing` en config/config.vdf). Viene
    APAGADO en PC, y con el apagado Steam no procesa nada hasta que le das a
    jugar: medido el 2026-09-26 en el shader_log de la PC del autor, bajo shaders
    nuevos de Aniimo a la 01:34 y no los toco hasta las 08:10, al lanzarlo, con
    el usuario esperando. True si esta puesto (o si se acaba de poner).

    Solo se escribe con Steam CERRADO (lo reescribe al salir). Si el usuario lo
    puso a 0 a mano, se respeta."""
    import re
    ruta = os.path.join(raiz, "config", "config.vdf")
    try:
        with open(ruta, encoding="utf-8", errors="replace") as fh:
            texto = fh.read()
    except OSError:
        return False
    m = re.search(r'"EnableShaderBackgroundProcessing"\s+"(\d)"', texto)
    if m:
        return m.group(1) == "1"
    if not poner:
        return False
    bloque = re.search(r'(\n(\t*)"ShaderCacheManager"\s*\n\t*\{\n)', texto)
    if not bloque:
        return False
    sangria = bloque.group(2) + "\t"
    nuevo = texto[:bloque.end()] + '%s"EnableShaderBackgroundProcessing"\t\t"1"\n' % sangria + texto[bloque.end():]
    with open(ruta + ".celiuz-nuevo", "w", encoding="utf-8") as fh:
        fh.write(nuevo)
    os.replace(ruta + ".celiuz-nuevo", ruta)
    return True


def preparar_steam():
    """En segundo plano al entrar: Steam en la bandeja CON el overlay, y con los
    shaders mejor atendidos. Si ya corre con el overlay, nada. Si corre sin el
    y NO hay ningun juego abierto, se cierra ordenadamente (`steam -shutdown`:
    las descargas siguen solas al volver) y se relanza. Con un juego abierto no
    se toca: ese juego se queda sin overlay, pero la partida sigue."""
    estado = steam_con_overlay()
    raiz = catalogo.raiz_steam()
    falta_fondo = bool(raiz) and not procesado_de_fondo(raiz)
    if estado is True and not falta_fondo:
        return 0
    if estado is not None:
        if juegos_abiertos():
            return 0
        subprocess.run(["steam", "-shutdown"], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False)
        for _ in range(60):
            if not pids_de("steam"):
                break
            time.sleep(0.5)
        else:
            return 1                    # no se cerro: mejor sin overlay que dos Steam
    if raiz:
        try:
            hilos_para_shaders(raiz)
            procesado_de_fondo(raiz, poner=True)
            ultimo_jugado_primero(raiz)
        except OSError:
            pass
    if os.access(LANZAR, os.X_OK):
        subprocess.Popen([LANZAR, "steam", "-silent"], env=dict(os.environ, **catalogo.entorno_de_juego()),
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    return 0


def steam_corriendo():
    return bool(pids_de("steam"))


def juegos_abiertos():
    """Las VENTANAS de juego abiertas. Antes se preguntaba a juegos.py por
    scopes, y eso contaba al propio cliente de Steam como juego («capa 1:
    Steam»): con Steam abierto siempre habia «un juego», y preparar-steam no
    relanzaba nunca Steam con el overlay (paso el 2026-09-26: Supr no enseñaba
    nada en Aniimo porque su Steam era el de antes, sin MANGOHUD)."""
    return [v.get("class") or v.get("title") for v in clientes() if es_de_juego(v)]


# --- Preguntar -----------------------------------------------------------------
def preguntar(accion, aviso=""):
    """La tarjeta de confirmacion: True solo si se acepto. Sin tarjeta (no hay
    pantalla, falta GTK) NO se hace nada: un atajo pulsado sin querer no puede
    cerrarte las ventanas porque la pregunta no se pudo dibujar."""
    if not os.path.exists(TARJETA):
        return False
    orden = [sys.executable, TARJETA, accion] + ([aviso] if aviso else [])
    try:
        return subprocess.run(orden, check=False, timeout=60).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


# --- Entrar y salir --------------------------------------------------------------
# --- Los videos de entrada y salida ------------------------------------------------
CARPETA_VIDEOS = os.path.join(os.path.dirname(os.path.dirname(AQUI)), "hypr", "modo-gaming")


def ruta_video(clave):
    """El video de entrada (`inicio.*`) o de salida (`final.*`) de
    hypr/modo-gaming/, o el que diga `video_entrada` / `video_salida` en
    ~/.config/celiuz/modo-gaming.json (manda este). Esa carpeta NO se versiona
    (ver su .gitignore): cada uno pone los suyos, que casi nunca son
    redistribuibles. Sin ninguno, el modo entra y sale sin video."""
    ruta = catalogo._leer_json(catalogo.config_usuario()).get(clave) or ""
    ruta = os.path.expanduser(str(ruta))
    if ruta and os.path.isfile(ruta):
        return ruta
    nombre = "inicio" if clave == "video_entrada" else "final"
    for ext in ("mp4", "webm", "mkv", "mov"):
        candidato = os.path.join(CARPETA_VIDEOS, "%s.%s" % (nombre, ext))
        if os.path.isfile(candidato):
            return candidato
    return None


def duracion(ruta):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", ruta], capture_output=True, text=True, timeout=5)
        return float(r.stdout.strip())
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def arrancar_video(ruta):
    """El video a pantalla completa con mpv, con fundido a negro al empezar y
    al acabar (imagen y sonido). Se salta con Enter, Esc, espacio, un clic o
    A / Start en el mando. Devuelve el proceso, o None si no se puede."""
    if not ruta or not shutil_which("mpv") or not os.environ.get("WAYLAND_DISPLAY"):
        return None
    dur = duracion(ruta)
    teclas = os.path.join(canales.RUNTIME, "modo-gaming-video.%s.conf" % (canales.firma() or "sin-sesion"))
    with open(teclas, "w") as fh:
        fh.write("ESC quit\nENTER quit\nKP_ENTER quit\nSPACE quit\nq quit\nMBTN_LEFT quit\n"
                 "GAMEPAD_ACTION_DOWN quit\nGAMEPAD_START quit\n")
    # --vo=wlshm (por software) y no la GPU: medido el 2026-09-26 en la PC del
    # autor (NVIDIA), mpv tarda 3-8 s en abrir su ventana con la salida por
    # GPU —inicializarla es lo lento— y 0,14 s con wlshm. Con 8 s el modo se
    # cansaba de esperar y el video de salida no salia a pantalla completa (lo
    # vio el usuario). Un video corto escalado por CPU no cuesta nada.
    # Y SIN --no-border: con wlshm rompe mpv 0.41 («Input image format unknown»,
    # «Size was <= 0») y no sale nada. En Hyprland no hace falta de todas formas.
    orden = ["mpv", "--fs", "--vo=wlshm", "--wayland-app-id=" + CLASE_VIDEO,
             "--title=Modo gaming",
             "--no-osc", "--osd-level=0", "--no-input-default-bindings", "--input-conf=" + teclas,
             "--input-gamepad=yes", "--keep-open=no", "--really-quiet", "--no-terminal",
             "--force-window=immediate", "--background-color=#000000"]
    if dur and dur > 2:
        fin = max(0.0, dur - 0.8)
        orden += ["--vf=lavfi=[fade=t=in:st=0:d=0.6,fade=t=out:st=%.2f:d=0.8]" % fin,
                  "--af=lavfi=[afade=t=in:st=0:d=0.6,afade=t=out:st=%.2f:d=0.8]" % fin]
    try:
        return subprocess.Popen(orden + [ruta], stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return None


def esperar_ventana(clase, tope=4.0, pid=None):
    """La ventana de `clase` (y de ESE proceso, si se da): con dos videos a la
    vez, «la primera ventana de video» puede ser la de otro (paso: la salida
    cogio la del video de entrada, que se habia quedado colgado)."""
    fin = time.monotonic() + tope
    while time.monotonic() < fin:
        for v in clientes():
            if _clase(v) == clase and (pid is None or v.get("pid") == pid):
                return v
        time.sleep(0.1)
    return None


def a_pantalla_completa(modo, ventana):
    """El video a pantalla completa DE VERDAD: mpv lo pide con --fs, pero si al
    abrirse otra ventana ya la tenia en ese escritorio (la biblioteca), Hyprland
    no se la da y queda en mosaico. Paso al salir del modo en la PC del usuario:
    el video salio compartiendo escritorio con sus terminales."""
    for v in clientes():
        if v.get("address") == ventana.get("address"):
            if v.get("fullscreen"):
                return
            if modo == hypr.LUA:
                _hyprctl("dispatch", 'hl.dsp.focus({ window = "address:%s" })' % v["address"])
                _hyprctl("dispatch", 'hl.dsp.window.fullscreen({ mode = "fullscreen" })')
            else:
                _hyprctl("dispatch", "focuswindow", "address:%s" % v["address"])
                _hyprctl("dispatch", "fullscreen", "0")
            return


def esperar_video(proceso, ruta):
    """Hasta que el video acabe (o lo salten). Si no acaba a su hora, fuera:
    un mpv que no puede dibujarse (algo le tapa la pantalla completa) se queda
    congelado sin avanzar, y quedaria una ventana de video zombi."""
    if proceso is None:
        return
    try:
        proceso.wait(timeout=(duracion(ruta) or 60) + 8)
    except subprocess.TimeoutExpired:
        proceso.terminate()
        try:
            proceso.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proceso.kill()


# --- Entrar y salir --------------------------------------------------------------
def entrar(sin_preguntar=False):
    """Todo lo pesado ocurre DETRAS del video de entrada (si lo hay), y la
    biblioteca se abre tambien detras: cuando el video acaba, ya esta ahi.
    Steam se prepara lo PRIMERO, para que su reinicio y el procesado de shaders
    corran mientras tanto."""
    if leer_estado():
        print("modo gaming: ya estaba puesto")
        return 0
    modo = hypr.modo()
    if not modo:
        print("modo gaming: no hay una sesion de Hyprland con la que hablar", file=sys.stderr)
        return 1
    if not sin_preguntar and not preguntar("entrar"):
        print("modo gaming: cancelado")
        return 1

    estado = {"activo": True, "desde": int(time.time()), "firma": canales.firma(),
              "efectos": {}, "no_molestar_puesto": False, "guardadas": {},
              "origen": escritorio_activo().get("id") or 1, "vigilante": None}
    # El estado se escribe PRIMERO: si algo de lo de abajo falla a medias, salir
    # sigue sabiendo que deshacer.
    guardar_estado(estado)

    escribir_mangohud()
    if shutil_which("steam"):
        try:
            subprocess.Popen([sys.executable, os.path.realpath(__file__), "preparar-steam"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            pass

    ruta = ruta_video("video_entrada")
    video = arrancar_video(ruta)
    ventana_video = esperar_ventana(CLASE_VIDEO, tope=8, pid=video.pid) if video else None

    for clave, en_modo in EFECTOS.items():
        valor = leer_opcion(clave)
        if valor is not None:
            estado["efectos"][clave] = valor
            poner_opcion(modo, clave, en_modo)
    modos = makoctl("mode")
    if modos is not None and "no-molestar" not in modos.split():
        if makoctl("mode", "-a", "no-molestar") is not None:
            estado["no_molestar_puesto"] = True
    guardar_estado(estado)
    mandar_fifo(canales.canal_barras(), "gaming-on dock:gaming-on")
    mandar_fifo(canales.canal_fondo(), "gaming-on")

    aj = catalogo.ajustes()
    permitidas = catalogo.apps_permitidas(aj)
    cerradas, quedan = cerrar_ventanas(modo, permitidas, aj["cerrar_terminales"])
    time.sleep(0.3)

    # Lo que se quedo: los juegos que ya estuvieran abiertos, al 1 (el primero)
    # y a los siguientes; todo lo demas, al escritorio oculto, apuntando donde
    # estaba para devolverlo al salir.
    siguiente = WS_BIBLIOTECA
    hay_juego = False
    for v in clientes():
        if not v.get("address") or _clase(v) in (CLASE_VIDEO, CLASE_BIBLIOTECA):
            continue
        if es_de_juego(v):
            mover(modo, v["address"], siguiente, False)
            siguiente += 1
            hay_juego = True
            continue
        if num_ws(v):
            estado["guardadas"][v["address"]] = num_ws(v)
            mover(modo, v["address"], GUARDADAS, False)
    guardar_estado(estado)

    if ventana_video:
        mover(modo, ventana_video["address"], WS_BIBLIOTECA, True)
        a_pantalla_completa(modo, ventana_video)
    else:
        ir(modo, WS_BIBLIOTECA)
    estado["vigilante"] = arrancar_vigilante()
    guardar_estado(estado)
    cambiar_atajos_escritorio(modo, True)
    ganchos = correr_ganchos("on")
    if not hay_juego:
        abrir_biblioteca()              # detras del video: al acabar, ya esta

    esperar_video(video, ruta)
    ir(modo, WS_BIBLIOTECA)

    print("modo gaming: puesto")
    if cerradas:
        print("  cerradas: " + ", ".join(cerradas))
    if quedan:
        print("  guardadas hasta salir: " + ", ".join(quedan))
    if ganchos:
        print("  ganchos: " + ", ".join(ganchos))
    return 0


def salir(sin_preguntar=False, forzar=False):
    """Con un juego abierto NO se sale: primero se guarda la partida y se
    cierra el juego (lo pidio el usuario; `--forzar` se lo salta). Si no, el
    video de salida va PRIMERO y a pantalla completa, y detras se cierran la
    biblioteca y los lanzadores, y cada ventana vuelve a su sitio. Los efectos
    (animaciones incluidas) vuelven cuando el video termina."""
    estado = leer_estado()
    if not estado:
        print("modo gaming: no estaba puesto")
        return 0
    if not forzar and juegos_abiertos():
        print("modo gaming: hay un juego abierto; guarda la partida y cierralo antes de salir",
              file=sys.stderr)
        if not sin_preguntar:
            preguntar("bloqueado")
        return 1
    if not sin_preguntar and not preguntar("salir"):
        print("modo gaming: cancelado")
        return 1

    parar_vigilante(estado.get("vigilante"))
    modo = hypr.modo()
    origen = estado.get("origen") or 1
    guardadas = estado.get("guardadas") or {}
    ruta = ruta_video("video_salida")
    video = None
    if modo:
        video = arrancar_video(ruta)
        ventana_video = esperar_ventana(CLASE_VIDEO, tope=8, pid=video.pid) if video else None
        if ventana_video:
            mover(modo, ventana_video["address"], origen, True)
            a_pantalla_completa(modo, ventana_video)
        # Detras del video: la biblioteca y los lanzadores se cierran (Steam, a
        # la bandeja); lo guardado vuelve a su numero, y lo abierto durante el
        # modo, a donde estabas al entrar.
        cerrar_de_salida(modo)
        # Lo que se guardo al entrar vuelve a su numero; lo que se abrio
        # DURANTE el modo (el navegador, la musica, una terminal) se cierra,
        # pidiendolo: al salir no se queda nada del modo sonando (lo pidio el
        # usuario, con Brave y Glassy Music aun sonando despues de salir).
        pedidas = []
        for v in clientes():
            if not v.get("address") or _clase(v) in (CLASE_VIDEO, CLASE_BIBLIOTECA) \
                    or es_ventana_de_lanzador(v):
                continue
            if v["address"] in guardadas:
                mover(modo, v["address"], guardadas[v["address"]], False)
            elif num_ws(v):
                cerrar_ventana(modo, v["address"])
                pedidas.append(v["address"])
            elif _en(v) == GUARDADAS:
                mover(modo, v["address"], origen, False)
        # La que no se ha ido (kitty con algo corriendo pregunta antes de
        # cerrarse), a donde vas a estar: si no, su pregunta se quedaria en un
        # escritorio que no ves.
        if pedidas:
            time.sleep(1.5)
            for v in clientes():
                if v.get("address") in pedidas:
                    mover(modo, v["address"], origen, False)
        cambiar_atajos_escritorio(modo, False)
        if not ventana_video:
            ir(modo, origen)
    correr_ganchos("off")
    esperar_video(video, ruta)
    # Barras, fondo y avisos, DESPUES del video: las barras son capas de arriba y
    # al relanzarse se veian un momento encima del video (lo vio el usuario).
    if estado.get("no_molestar_puesto"):
        makoctl("mode", "-r", "no-molestar")
    mandar_fifo(canales.canal_barras(), "gaming-off dock:gaming-off")
    mandar_fifo(canales.canal_fondo(), "gaming-off")
    if modo:
        for clave, valor in estado.get("efectos", {}).items():
            poner_opcion(modo, clave, valor)
        ir(modo, origen)
    try:
        os.remove(ruta_estado())
    except OSError:
        pass
    print("modo gaming: quitado")
    return 0


def cerrar_de_salida(modo):
    """La biblioteca y las ventanas de los lanzadores. La biblioteca se va con
    su animacion; si en un momento no se ha ido, se la termina por su PID."""
    bibliotecas = []
    for v in clientes():
        if _clase(v) == CLASE_BIBLIOTECA:
            bibliotecas.append(v.get("pid"))
            cerrar_ventana(modo, v["address"])
        elif es_ventana_de_lanzador(v):
            cerrar_ventana(modo, v["address"])
    if bibliotecas:
        time.sleep(0.8)
        vivas = {v.get("pid") for v in clientes() if _clase(v) == CLASE_BIBLIOTECA}
        for pid in vivas:
            if pid and pid > 0:
                try:
                    os.kill(pid, 15)
                except OSError:
                    pass


def estado_cli(como_json):
    estado = leer_estado()
    if como_json:
        print(json.dumps({"activo": bool(estado), "desde": (estado or {}).get("desde")}))
    else:
        print("puesto desde %s" % time.strftime("%H:%M", time.localtime(estado["desde"]))
              if estado else "quitado")
    return 0 if estado else 1


def main(argv):
    orden = argv[0] if argv else ""
    sin = "--sin-preguntar" in argv
    if orden == "on":
        return entrar(sin)
    if orden == "off":
        return salir(sin, "--forzar" in argv)
    if orden == "toggle":
        return salir(sin, "--forzar" in argv) if leer_estado() else entrar(sin)
    if orden == "estado":
        return estado_cli("--json" in argv)
    if orden == "vigilar":
        return vigilar()
    if orden == "ir":
        return ir_cli(argv[1] if len(argv) > 1 else "")
    if orden == "anadir-app":
        return anadir_app()
    if orden == "preparar-steam":
        return preparar_steam()
    print(__doc__.split("QUE HACE")[0].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
