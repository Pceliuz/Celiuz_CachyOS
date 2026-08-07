#!/usr/bin/env python3
"""
~/dotfiles/hypr/scripts/wallpaper-pause.py

Se encarga de que el fondo de pantalla en video no gaste recursos cuando no se
ve. Hace dos cosas distintas:

  1. PAUSA el video cuando hay una ventana tapandolo, y lo reanuda al volver a
     un workspace vacio. Corta el gasto de CPU y del decodificador de la GPU;
     la RAM se queda reservada, que es lo que permite reanudar al instante.

  2. MATA mpvpaper entero mientras corra alguno de los programas de
     ~/.config/mpvpaper/stoplist (tus juegos), y lo vuelve a levantar al
     cerrarlos. Ahi si se libera todo: los ~430 MB de RAM y la VRAM.

  3. LO RESUCITA si se muere por su cuenta, hasta MAX_REVIVIR veces seguidas.
     Sin esto, un mpvpaper que se cae deja el escritorio sin fondo hasta que
     reinicies la sesion, y sin decir nada.

POR QUE HAY QUE HACERLO A MANO
------------------------------
mpvpaper trae -p (auto-pause) y -s (auto-stop) justo para el punto 1, pero
**bajo Hyprland no funcionan** — su propio manual avisa de que "the auto
options might not work as intended". Se apoyan en el "surface frame callback"
de Wayland, o sea en que el compositor deje de pedir fotogramas cuando la capa
esta tapada, y Hyprland se los sigue pidiendo aunque haya una ventana encima a
pantalla completa. Comprobado de dos maneras: con -p, la propiedad `pause` de
mpv se queda en False con el fondo totalmente tapado; con -s, ni el PID ni la
RSS se mueven. Su lista stoplist si funciona (va por nombre de proceso), pero
solo con -s activo, y -s se pelea con la pausa de aqui. Asi que se replica.

COMO
----
Se suscribe al socket de eventos de Hyprland (.socket2.sock) en vez de sondear:
reacciona al instante y no cuesta nada. Cada 5 s como mucho, ademas, revisa la
stoplist leyendo /proc (sin lanzar pidof, para no crear procesos a cada rato) y
reconcilia la pausa contra lo que mpv tiene de verdad, porque mpvpaper se
reinicia por fuera de aqui (CeliuzPaper, set-wallpaper.sh) y vuelve sin pausa.

Ordenes por el FIFO ($XDG_RUNTIME_DIR/wallpaper-pause.<firma>.fifo, uno por
sesion; ver lib/canales.py): `hold` para que deje
de tocar la pausa y `release` para que vuelva a mandar. Las usa CeliuzPaper: al
elegir fondo hace falta ver el video en marcha, y este demonio lo pausaria por
tener ventanas abiertas.

La regla de la pausa es "ventanas > 0 -> pausa" porque tienes los gaps a 0: en
cuanto hay una ventana en mosaico, tapa el fondo entero. Si algun dia pones
gaps o usas mucho ventanas flotantes pequenas, es aqui donde hay que afinarlo.
"""

import json
import os
import select
import signal
import socket
import subprocess
import sys
import time

RUNTIME = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "lib"))
import canales  # noqa: E402

# Lo abre mpvpaper con --input-ipc-server (ver wallpaper.sh).
MPV_SOCKET = os.path.join(RUNTIME, "mpvpaper.sock")
STOPLIST = os.path.expanduser("~/.config/mpvpaper/stoplist")
# La raiz del repo, resolviendo el enlace simbolico: a este script se le puede
# llamar por ~/.config/hypr/... o por ~/.local/bin/..., y realpath() lleva
# hasta el fichero de verdad dentro del repo, se haya clonado donde se haya
# clonado. Antes ponia "~/dotfiles/...", que obligaba a clonar justo ahi.
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
LANZADOR = os.path.join(RAIZ, "hypr/scripts/wallpaper.sh")
# El enlace al video que esta puesto. Si no existe es que aun no se ha elegido
# ninguno, y entonces no hay nada que revivir.
CURRENT = os.path.join(RAIZ, "hypr/wallpapers/current")
# Cuantas veces seguidas se intenta resucitar mpvpaper antes de rendirse y
# decirlo. Ver el bloque 1b del bucle.
MAX_REVIVIR = 3

# Ordenes de fuera, por FIFO:
#   hold     -> deja de tocar la pausa (lo pide CeliuzPaper mientras eliges
#               fondo: con la pausa puesta veri­as un fotograma congelado y no
#               se puede elegir asi).
#   release  -> vuelve a mandar, y recalcula ya mismo.
# Con la firma de la sesion; ver lib/canales.py.
FIFO_PATH = canales.canal_fondo()

# Cada cuanto se revisa la stoplist, como maximo. Tambien es el timeout del
# select, o sea el latido del bucle cuando no pasa nada en Hyprland.
PERIODO = 5.0

# Cuanto se insiste en hablar con Hyprland antes de rendirse y salir. El porque
# esta en el bucle de reconexion de main(). Se puede forzar desde el entorno
# para probarlo sin esperar un minuto (lo usa tests/unidad/fondo-huerfano.sh).
ABANDONO = float(os.environ.get("WALLPAPER_PAUSE_ABANDONO", "60"))

# Eventos de Hyprland tras los que merece la pena recontar ventanas. El resto
# (cambios de foco, de titulo, de submap...) no altera lo que tapa el fondo.
EVENTOS = (
    "workspace>>", "focusedmon>>",
    "openwindow>>", "closewindow>>",
    "movewindowv2>>", "movewindow>>",
    "fullscreen>>", "changefloatingmode>>",
)


def hypr_dir():
    base = os.path.join(RUNTIME, "hypr")
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not sig:
        candidatos = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
        if not candidatos:
            sys.exit("wallpaper-pause: no encuentro ninguna instancia de Hyprland")
        sig = candidatos[0]
    return os.path.join(base, sig)


HYPR_DIR = hypr_dir()


def ventanas_activas():
    """Cuantas ventanas hay en el workspace que se esta viendo. None si falla."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(os.path.join(HYPR_DIR, ".socket.sock"))
            s.sendall(b"activeworkspace")
            datos = b""
            while True:
                trozo = s.recv(8192)
                if not trozo:
                    break
                datos += trozo
    except OSError:
        return None
    for linea in datos.decode(errors="replace").splitlines():
        if linea.strip().startswith("windows:"):
            try:
                return int(linea.split(":", 1)[1])
            except ValueError:
                return None
    return None


def mpv(orden):
    """Manda una orden al socket IPC de mpv. Devuelve None si no esta.

    Que no este es normal, no un error: puede que mpvpaper aun no haya
    arrancado, o que lo hayamos matado nosotros por la stoplist.
    """
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(MPV_SOCKET)
            s.sendall((json.dumps(orden) + "\n").encode())
            return s.recv(4096)
    except (OSError, ValueError):
        return None


def pausa_real():
    """Lo que mpv tiene puesto DE VERDAD, o None si no se le pudo preguntar."""
    respuesta = mpv({"command": ["get_property", "pause"]})
    if not respuesta:
        return None
    try:
        datos = json.loads(respuesta.decode(errors="replace").splitlines()[0])
    except (ValueError, IndexError):
        return None
    if datos.get("error") != "success":
        return None
    return bool(datos.get("data"))


def procesos_en_marcha():
    """Nombres de todos los procesos vivos, leyendo /proc directamente."""
    nombres = set()
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/comm") as fh:
                nombres.add(fh.read().strip())
        except OSError:
            continue   # el proceso murio mientras lo leiamos
    return nombres


def leer_stoplist():
    """Nombres de la stoplist. Se relee cada vez: asi anadir un juego a la lista
    tiene efecto sin reiniciar nada."""
    try:
        with open(STOPLIST) as fh:
            return {n for n in fh.read().split() if n}
    except OSError:
        return set()


def mpvpaper_vivo():
    return subprocess.run(["pgrep", "-x", "mpvpaper"],
                          stdout=subprocess.DEVNULL).returncode == 0


def matar_mpvpaper():
    subprocess.run(["pkill", "-x", "mpvpaper"], stdout=subprocess.DEVNULL)
    time.sleep(0.5)
    subprocess.run(["pkill", "-9", "-x", "mpvpaper"], stdout=subprocess.DEVNULL)


def avisar(titulo, cuerpo):
    """Una notificacion. Es la unica salida visible que tiene este demonio: corre
    suelto con setsid y su stdout va a /dev/null."""
    subprocess.run(["notify-send", "-a", "Fondo de pantalla", "-u", "normal",
                    "-i", "dialog-warning", titulo, cuerpo],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def levantar_mpvpaper():
    # --only-mpv para que el lanzador no nos mate a nosotros de rebote.
    subprocess.run([LANZADOR, "--only-mpv"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def abrir_fifo():
    """FIFO nuevo en cada arranque, por si quedo uno huerfano.

    Se abre en O_RDWR y no en O_RDONLY: manteniendo nosotros mismos un extremo de
    escritura abierto, el FIFO nunca da EOF y select() no se dispara en bucle.
    """
    try:
        os.remove(FIFO_PATH)
    except FileNotFoundError:
        pass
    try:
        os.mkfifo(FIFO_PATH, 0o600)
        return os.open(FIFO_PATH, os.O_RDWR | os.O_NONBLOCK)
    except OSError:
        return None


def main():
    # Un solo demonio a la vez: si quedo otro de una recarga anterior, que se
    # vaya el viejo. (wallpaper.sh ya lo hace, pero por si se lanza a mano.)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    fifo = abrir_fifo()

    pausado = None       # lo ultimo que le dijimos a mpv
    parado_por_juego = False
    retenido = False     # alguien pidio `hold`: no se toca la pausa
    revividos = 0        # intentos seguidos de resucitar mpvpaper (ver 1b)
    sin_hyprland = None  # desde cuando no se consigue hablar con el compositor

    while True:
        try:
            eventos = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            eventos.connect(os.path.join(HYPR_DIR, ".socket2.sock"))
        except OSError:
            # No hay compositor al otro lado. Son dos situaciones distintas y
            # hay que separarlas:
            #
            #   - Arranque en frio: Hyprland aun no ha abierto el socket. Se
            #     espera y se vuelve a intentar, que es lo de siempre.
            #   - Nuestro Hyprland ya NO ESTA. Aqui quedarse esperando es peor
            #     que morirse, y no es una hipotesis: paso el 2026-08-04. Este
            #     demonio se lanza con `setsid`, asi que NO muere con el
            #     compositor que lo arranco; y HYPR_DIR se fija al empezar, o
            #     sea que un Hyprland nuevo tampoco lo recupera — se queda
            #     reintentando contra una instancia muerta, para siempre.
            #
            #     Y estorba, porque wallpaper.sh decide si hace falta lanzar un
            #     demonio con un `pgrep` POR NOMBRE: el zombi contesta que si,
            #     y la sesion viva se queda sin nadie que pause el fondo. El
            #     sintoma es justo el contrario de lo que parece un fallo del
            #     demonio — el video corriendo con ventanas encima, y ademas
            #     ningun `hold` ni `release` llega, porque el FIFO tambien es
            #     suyo. Asi que tras ABANDONO segundos sin conseguir hablar con
            #     nadie, este proceso se aparta y deja el sitio libre.
            if sin_hyprland is None:
                sin_hyprland = time.monotonic()
            elif time.monotonic() - sin_hyprland >= ABANDONO:
                print("wallpaper-pause: mi Hyprland ya no esta; dejo el sitio",
                      file=sys.stderr)
                sys.exit(0)
            time.sleep(2)
            continue

        sin_hyprland = None
        pausado = None
        buffer = b""
        try:
            while True:
                vigilar = [eventos] + ([fifo] if fifo is not None else [])
                listos, _, _ = select.select(vigilar, [], [], PERIODO)
                listo = eventos in listos

                # --- 0. Ordenes de fuera (CeliuzPaper) ---
                if fifo is not None and fifo in listos:
                    try:
                        ordenes = os.read(fifo, 1024).decode(errors="replace").split()
                    except BlockingIOError:
                        ordenes = []
                    for orden in ordenes:
                        if orden == "hold":
                            retenido = True
                        elif orden == "release":
                            retenido = False
                            pausado = None   # obliga a recalcular abajo

                # --- 1. La stoplist: juegos ---
                vivos = procesos_en_marcha()
                hay_juego = bool(leer_stoplist() & vivos)
                # Se saca de la lista que ya tenemos en la mano en vez de lanzar
                # un pgrep: este bucle da una vuelta cada 5 s y el fichero evita
                # crear procesos a proposito (ver la cabecera).
                hay_fondo = "mpvpaper" in vivos
                if hay_juego and not parado_por_juego:
                    matar_mpvpaper()
                    parado_por_juego = True
                    pausado = None
                elif not hay_juego and parado_por_juego:
                    levantar_mpvpaper()
                    parado_por_juego = False
                    pausado = None
                    revividos = 0
                    time.sleep(1.5)   # deja que mpv abra su socket

                # --- 1b. Se murio solo ---
                # Hasta ahora mpvpaper solo se relanzaba tras matarlo la
                # stoplist: si se caia por cualquier otro motivo, el escritorio
                # se quedaba sin fondo hasta el siguiente reinicio de sesion, sin
                # avisar. Pasa de verdad — se cayo durante las pruebas del
                # 2026-08-01 sin dejar rastro en el journal.
                #
                # Se reintenta un numero limitado de veces: si el video esta
                # corrompido o el archivo ya no existe, mpvpaper muere nada mas
                # nacer y sin tope esto seria un bucle de arranques cada 5 s.
                elif (not hay_fondo and os.path.exists(CURRENT)
                      and revividos < MAX_REVIVIR):
                    revividos += 1
                    levantar_mpvpaper()
                    pausado = None
                    time.sleep(1.5)
                    if not mpvpaper_vivo() and revividos >= MAX_REVIVIR:
                        avisar("El fondo de pantalla no arranca",
                               "mpvpaper se cierra solo al abrirlo. Prueba a "
                               "elegir otro video con CeliuzPaper.")
                elif hay_fondo:
                    revividos = 0     # volvio a estar bien: cuenta a cero

                # --- 2. Los eventos de Hyprland: pausa por ventanas encima ---
                recontar = False
                if listo:
                    trozo = eventos.recv(8192)
                    if not trozo:
                        break          # Hyprland cerro el socket
                    buffer += trozo
                    *lineas, buffer = buffer.split(b"\n")
                    for linea in lineas:
                        if linea.decode(errors="replace").startswith(EVENTOS):
                            recontar = True

                if parado_por_juego:
                    continue
                if retenido:
                    # Alguien esta eligiendo fondo: el video se queda como lo
                    # ponga el, y al soltar (`release`) se recalcula.
                    pausado = None
                    continue

                # Sin evento de Hyprland, el latido (cada PERIODO) sirve para
                # RECONCILIAR: se mira lo que mpv tiene de verdad en vez de
                # fiarse de `pausado`. Hace falta porque mpvpaper se reinicia
                # por fuera de aqui —CeliuzPaper al aplicar un fondo,
                # set-wallpaper.sh— y vuelve siempre sin pausa; con la copia
                # local diciendo que ya estaba pausado, el video se quedaba
                # corriendo hasta el siguiente evento de ventanas, o para
                # siempre si no lo habia. Cuesta una consulta al socket.
                if not recontar:
                    pausado = pausa_real()

                n = ventanas_activas()
                if n is None:
                    continue
                quiere_pausa = n > 0
                if quiere_pausa != pausado:
                    # Solo se apunta si la orden LLEGO. Si mpvpaper todavia no
                    # ha abierto su socket, apuntarla dejaria a `pausado`
                    # mintiendo y el fondo no se pausaria nunca.
                    if mpv({"command": ["set_property", "pause", quiere_pausa]}) is not None:
                        pausado = quiere_pausa
        except OSError:
            pass
        finally:
            eventos.close()

        time.sleep(2)   # se cayo el socket de eventos: reconectar


if __name__ == "__main__":
    main()
