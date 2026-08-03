#!/usr/bin/env python3
"""
~/dotfiles/hypr/scripts/waybar-autohide.py

Controla el auto-ocultado de las barras y lanza las CUATRO instancias de waybar:

  arriba  ->  config.jsonc      (barra de estado)  +  trigger.jsonc
  abajo   ->  dock.jsonc        (acceso rapido)    +  dock-trigger.jsonc

Las dos barras se comportan exactamente igual, cada una en su borde:
  - Workspace sin ventanas -> la barra se queda puesta, fija. No hay nada que
    estorbar, asi que no tiene sentido esconderla.
  - Se abre una app        -> la barra se retira y en su lugar aparece su
    linea-tirador centrada en el borde. Las cuatro capas van con
    "exclusive": false, asi que nunca reservan espacio: la ventana no se achica
    ni se recoloca, la barra simplemente se superpone.
  - Click en la linea      -> la barra vuelve, ENCIMA de la app.
  - Puntero fuera 1.5 s    -> se oculta otra vez. Mientras el puntero siga
    dentro, se queda todo el tiempo que haga falta.

La zona que cuenta como "el puntero esta en la barra" es distinta para cada una:
la de arriba ocupa todo el ancho de la pantalla, pero el dock es una tira estrecha
centrada, asi que ahi tambien se mira la X. Sin eso, dejar el raton en la esquina
inferior izquierda mantendria el dock abierto para siempre. El tamano del dock no
esta escrito aqui: se le pregunta a Hyprland por su capa, porque cambia cada vez
que se anade o se quita una app.

Sobre la animacion: waybar NO desmapea su superficie al ocultarse, solo le pone
la clase CSS .hidden y la baja a la capa inferior. Por eso la transicion es un
fundido en CSS (ver style.css) y no un deslizado, y por eso solo se aprecia al
aparecer: al ocultarse, el cambio de capa deja la barra tapada por la ventana
de la app al instante.

El estado se consulta por el socket de control de Hyprland en vez de lanzar
`hyprctl` cada vez: son ~0.03 ms por consulta, asi que sondear a 10 Hz es
practicamente gratis (nada de procesos nuevos ni de hilos).

Ordenes por el FIFO ($XDG_RUNTIME_DIR/waybar-autohide.fifo):
    show | hide | toggle | hold | release | reload | lock | unlock
                                                    -> barra de arriba
    dock:show | dock:hide | dock:lock | ...         -> dock
`reload` relanza esa barra para que relea su config: lo usa gen-dock.py cuando
cambian las apps del dock.
Las ordenes sin prefijo van a la barra de arriba a proposito: es lo que ya
manda el panel de calendario (hold/release) y el bind SUPER+B.

CUIDADO CON `hide` Y `hold`, que no significan lo que parece:
    `hide`  no esconde nada por la fuerza: solo suelta el "sacada a mano", y
            despues el demonio decide como siempre. Si el escritorio esta
            VACIO la deja visible (ver update(): sin ventanas la barra se
            queda puesta, que es lo que quieres a diario).
    `hold`  hace lo CONTRARIO de esconder: la retiene VISIBLE. Es para el panel
            de calendario, que cuelga de la barra.
Para quitarla de en medio de verdad esta `lock`, que las MATA (y `unlock`, que
las levanta otra vez). La usa scripts/lock.sh antes de bloquear la pantalla, y
matarlas no es exagerado: con el bloqueo puesto y `session_lock_xray` encendido,
una barra "escondida" —que sigue existiendo, solo que en la capa de abajo— se
lee entera por encima del bloqueo, y como el bloqueo salta a un escritorio vacio
no hay ninguna ventana que la tape. Comprobado en anidado el 2026-07-28: se leia
la IP, la CPU, la RAM y la hora sobre la pantalla de bloqueo.
"""

import json
import os
import re
import select
import signal
import socket
import subprocess
import sys
import time

WAYBAR_DIR = os.path.expanduser("~/dotfiles/waybar")

# Franja desde el borde superior que cuenta como "el puntero esta en la barra".
# Algo mas que los 38 px de alto, para que rozar el borde no la cierre.
HOVER_ZONE = 42
# Cortesia alrededor del dock: cuantos px mas alla de su capa sigue contando como
# "el puntero esta encima", para que rozar un borde no lo cierre.
DOCK_MARGIN = 40
# Cada cuanto se le vuelve a preguntar a Hyprland por el tamano de la capa del
# dock. No es fijo: cambia al anadir o quitar apps.
GEO_REFRESH = 2.0

# Segundos que espera tras salir el puntero antes de volver a ocultarse.
HIDE_DELAY = 1.5
# Periodo del bucle. 0.1 s da una reaccion inmediata a ojo y no cuesta nada.
TICK = 0.1

RUNTIME = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
FIFO_PATH = os.path.join(RUNTIME, "waybar-autohide.fifo")

CURSOR_RE = re.compile(r"^(\d+),\s*(\d+)$")


def hypr_socket():
    """Ruta del socket de control de la instancia de Hyprland en curso."""
    base = os.path.join(RUNTIME, "hypr")
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not sig:
        # Sin la variable (p.ej. lanzado a mano desde otra terminal), cae en la
        # unica instancia viva.
        candidates = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
        if not candidates:
            sys.exit("waybar-autohide: no encuentro ninguna instancia de Hyprland")
        sig = candidates[0]
    return os.path.join(base, sig, ".socket.sock")


SOCKET = hypr_socket()


def query(cmd):
    """Manda un comando al socket de Hyprland y devuelve la respuesta cruda."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(SOCKET)
            s.sendall(cmd.encode())
            chunks = []
            while True:
                chunk = s.recv(8192)
                if not chunk:
                    break
                chunks.append(chunk)
            return b"".join(chunks).decode(errors="replace")
    except OSError:
        return ""


def screen_size():
    """Tamano LOGICO del monitor enfocado, que es en lo que viene el cursor."""
    try:
        monitors = json.loads(query("j/monitors"))
        mon = next((m for m in monitors if m.get("focused")), monitors[0])
        scale = mon.get("scale") or 1.0
        return round(mon["width"] / scale), round(mon["height"] / scale)
    except (ValueError, KeyError, IndexError):
        return 1920, 1080


SCREEN_W, SCREEN_H = screen_size()


def read_state():
    """(ventanas en el workspace activo, x, y del cursor). Una sola ida y vuelta."""
    out = query("[[BATCH]]activeworkspace;cursorpos")
    windows = 0
    # Si falla la lectura se asume "fuera de las dos barras": el centro exacto.
    cursor_x, cursor_y = SCREEN_W // 2, SCREEN_H // 2
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("windows:"):
            try:
                windows = int(line.split(":", 1)[1])
            except ValueError:
                pass
            continue
        # cursorpos llega como "1762, 0" al final del lote. Se comprueba con
        # regex porque el titulo de la ventana tambien puede llevar comas.
        m = CURSOR_RE.match(line)
        if m:
            cursor_x, cursor_y = int(m.group(1)), int(m.group(2))
    return windows, cursor_x, cursor_y


# Niveles de capa de Hyprland: 0 background, 1 bottom, 2 top, 3 overlay. Las
# cuatro instancias de waybar nacen en `top`; al ocultarse bajan a `bottom`.
LAYER_TOP = 2


def layer_levels():
    """{namespace: nivel} de las capas vivas. Una ida y vuelta de 0,05 ms.

    Es la UNICA fuente fiable de si una barra esta puesta o no. Waybar solo
    ofrece un toggle (SIGUSR1), y una senal que se pierde no deja ningun rastro
    del lado del demonio: sin mirar aqui, el estado recordado se queda mintiendo
    para siempre.
    """
    try:
        data = json.loads(query("j/layers"))
    except ValueError:
        return {}
    niveles = {}
    for monitor in data.values():
        for nivel, superficies in monitor.get("levels", {}).items():
            for capa in superficies:
                ns = capa.get("namespace")
                if ns:
                    niveles[ns] = int(nivel)
    return niveles


def in_top_zone(x, y):
    """La barra de arriba ocupa todo el ancho: solo importa la altura."""
    return y < HOVER_ZONE


# Geometria de la capa del dock, preguntada a Hyprland y recordada un rato.
# Antes su ancho estaba escrito a mano aqui y tenia que coincidir con el campo
# "width" de dock.jsonc; ahora que las apps se anaden y quitan en caliente ese
# ancho cambia solo, asi que se lee del compositor y no hay nada que sincronizar.
_dock_geo = {"x": 0, "y": 0, "w": 0, "h": 0, "t": -GEO_REFRESH}


def dock_geometry():
    now = time.monotonic()
    if now - _dock_geo["t"] < GEO_REFRESH:
        return _dock_geo
    _dock_geo["t"] = now
    try:
        data = json.loads(query("j/layers"))
    except ValueError:
        return _dock_geo
    for monitor in data.values():
        for layers in monitor.get("levels", {}).values():
            for layer in layers:
                if layer.get("namespace") == "waybar-dock":
                    _dock_geo.update(x=layer["x"], y=layer["y"],
                                     w=layer["w"], h=layer["h"])
                    return _dock_geo
    return _dock_geo


def in_dock_zone(x, y):
    """El dock es estrecho y centrado: hay que mirar tambien la X."""
    geo = dock_geometry()
    if not geo["w"]:
        # Sin datos de la capa (aun arrancando) se cae a la franja de abajo a lo
        # ancho: mas vale que no se esconda de mas que que no se pueda sacar.
        return y >= SCREEN_H - 90
    return (geo["x"] - DOCK_MARGIN <= x <= geo["x"] + geo["w"] + DOCK_MARGIN
            and y >= geo["y"] - DOCK_MARGIN)


def launch(config):
    return subprocess.Popen(
        ["waybar", "-c", os.path.join(WAYBAR_DIR, config),
         "-s", os.path.join(WAYBAR_DIR, "style.css")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class Bar:
    """Una barra y su linea-tirador: siempre visibles la una o la otra."""

    def __init__(self, config, trigger_config, in_zone, namespace, trigger_namespace):
        self.in_zone = in_zone
        self.config = config
        self.trigger_config = trigger_config
        # Como se llaman las dos capas en Hyprland (el "name" de cada jsonc). Es
        # por donde update() consulta el estado REAL en vez de recordarlo.
        self.namespace = namespace
        self.trigger_namespace = trigger_namespace
        self.proc = launch(config)
        self.trigger = launch(trigger_config)
        self.manual = False   # el usuario la saco con click en la linea
        self.held = False     # algo la esta reteniendo (el panel de calendario)
        self.locked = False   # la pantalla esta bloqueada: oculta pase lo que pase
        self.left_at = 0.0    # momento en que el puntero salio de la barra

    def toggle(self):
        """SIGUSR1 = toggle (el valor por defecto de waybar).

        Se usa el alternar y no un "hide" explicito porque la accion hide de
        waybar no desmapea la superficie, solo la manda a la capa inferior, y
        sin desmapeo Hyprland no tiene evento que animar. Como la barra y su
        tirador siempre cambian a la vez y en sentidos opuestos, alternar los
        dos es exacto.
        """
        self.proc.send_signal(signal.SIGUSR1)
        self.trigger.send_signal(signal.SIGUSR1)

    def command(self, cmd):
        if cmd == "show":
            self.manual = True
            self.left_at = time.monotonic()
        elif cmd == "hide":
            self.manual = False
        elif cmd == "toggle":
            self.manual = not self.manual
            self.left_at = time.monotonic()
        elif cmd == "hold":
            # El panel de calendario cuelga de la barra: mientras este abierto
            # la barra se queda, aunque el puntero se vaya.
            self.held = True
        elif cmd == "release":
            self.held = False
            # No se esconde de golpe al cerrar el panel: se le da el mismo
            # margen de cortesia que al sacar el puntero.
            self.manual = True
            self.left_at = time.monotonic()
        elif cmd == "lock":
            # Pantalla bloqueada: la barra se MATA, no se esconde.
            #
            # Esconderla no vale, y esta comprobado (2026-07-28, en anidado):
            # "esconder" en waybar es bajarla a la capa inferior, la superficie
            # sigue existiendo, y con el bloqueo puesto y `session_lock_xray`
            # encendido se lee entera por encima del bloqueo. En la captura de
            # la prueba se leian la IP, la CPU, la RAM y la hora. Como ademas el
            # bloqueo salta a un escritorio vacio, no hay ninguna ventana que la
            # tape. La unica forma de que no se vea es que no exista.
            if not self.locked:
                self.locked = True
                self.kill()
        elif cmd == "unlock":
            if self.locked:
                self.locked = False
                self.relanzar()
        elif cmd == "reload":
            self.reload()

    def reload(self):
        """Relanza las dos instancias para que relean su config.

        Waybar no sabe recargar su configuracion por senal (SIGUSR2 esta cogido
        por el toggle), asi que cuando el dock cambia de apps hay que reiniciarlo.
        Se hace desde aqui y no desde fuera porque el demonio vigila que sus
        procesos sigan vivos: si los mata otro, se apaga entero.
        """
        self.kill()
        self.relanzar()

    def relanzar(self):
        """Levanta de nuevo las dos instancias, dandolas ya por muertas.

        Sale de `reload` para que el desbloqueo pueda reusarla: `lock` mata las
        barras y `unlock` las vuelve a levantar con esto mismo.
        """
        for proc in (self.proc, self.trigger):
            try:
                proc.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                pass
        self.proc = launch(self.config)
        self.trigger = launch(self.trigger_config)
        # Margen de cortesia para que se vea el cambio antes de que se esconda
        # sola. No hace falta anotar "queda visible": update() lo lee de la capa
        # real, y mientras la superficie no exista no le manda ninguna senal.
        self.manual = True
        self.left_at = time.monotonic()
        # `held` se conserva a proposito: quien recarga el dock es el gestor de
        # apps al anadir o quitar una, y sigue abierto y apoyado en el. Si se
        # limpiara aqui, el dock se escondaria debajo del gestor a mitad de faena
        # (era justo lo que pasaba).
        # La capa nueva puede tener otro tamano (mas o menos apps): se olvida la
        # geometria recordada para no calcular la zona con la vieja.
        _dock_geo["t"] = -GEO_REFRESH

    def visible_real(self, capas):
        """True/False segun la capa REAL de la barra. None si aun no existe.

        Waybar no desmapea al ocultarse: baja su superficie de la capa `top` a la
        `bottom`, asi que el nivel dice exactamente en que estado esta. Se exigen
        las DOS superficies porque el toggle las mueve juntas: si una todavia no
        nacio, la senal la recibiria solo la otra y quedarian descuadradas.
        """
        nivel = capas.get(self.namespace)
        nivel_tirador = capas.get(self.trigger_namespace)
        if nivel is None or nivel_tirador is None:
            return None
        return nivel >= LAYER_TOP

    def update(self, windows, x, y, capas):
        if self.locked:
            # Durante el bloqueo las barras estan MUERTAS (ver command("lock")),
            # asi que aqui no hay nada que alternar: mandarles una senal seria
            # escribirle a un proceso que ya no esta.
            return
        if windows == 0:
            # Sin apps la barra se queda puesta, y se olvida el estado manual.
            want_visible = True
            self.manual = False
        elif self.held:
            want_visible = True
        elif self.manual:
            if self.in_zone(x, y):
                self.left_at = time.monotonic()   # dentro: el reloj se reinicia
            elif time.monotonic() - self.left_at >= HIDE_DELAY:
                self.manual = False
            want_visible = self.manual
        else:
            want_visible = False

        # Se compara contra la capa REAL, nunca contra lo que creamos haber
        # dejado. Waybar solo ofrece un toggle, asi que un estado recordado que
        # se desvie UNA sola vez deja las barras invertidas para siempre: puestas
        # con apps abiertas y escondidas con el escritorio vacio.
        #
        # Y se desviaba de verdad al desbloquear la pantalla (2026-08-01,
        # reproducido 3 de 3 en la laptop): `unlock` relanza waybar y lock.sh
        # vuelve al escritorio con ventanas en ese mismo instante, asi que el
        # toggle de ocultar salia cuando waybar aun no tenia superficie y se
        # perdia. En el sobremesa waybar arrancaba a tiempo y por eso alli no se
        # veia. Mirando la capa, una senal perdida se corrige sola al ciclo
        # siguiente en vez de invertirlo todo.
        visible = self.visible_real(capas)
        if visible is None:
            return                      # sin superficie: la senal se perderia
        if want_visible != visible:
            self.toggle()

    def alive(self):
        # Con la pantalla bloqueada las matamos nosotros a proposito, asi que
        # verlas muertas es lo normal y no es motivo para apagar el demonio.
        if self.locked:
            return True
        return self.proc.poll() is None and self.trigger.poll() is None

    def kill(self):
        for proc in (self.proc, self.trigger):
            try:
                proc.terminate()
            except OSError:
                pass


def abrir_fifo():
    """Crea el FIFO de ordenes de cero y lo deja abierto. Devuelve el descriptor.

    O_RDWR y no O_RDONLY: manteniendo nosotros mismos un extremo de escritura
    abierto, el FIFO nunca da EOF y select() no se dispara en bucle.
    """
    try:
        os.remove(FIFO_PATH)   # un huerfano de otra sesion, o un fichero suelto
    except FileNotFoundError:
        pass
    os.mkfifo(FIFO_PATH, 0o600)
    return os.open(FIFO_PATH, os.O_RDWR | os.O_NONBLOCK)


def es_nuestro(fifo):
    """Si la ruta del FIFO sigue siendo el mismo fichero que tenemos abierto.

    Deja de serlo cuando alguien lo borra: otra instancia del demonio que
    arranca, o una que se apaga y se lleva por delante el FIFO de la que se
    queda. Entonces nuestro descriptor apunta a un inodo sin nombre —lo delata
    `ls -l /proc/<pid>/fd`, que lo marca "(deleted)"— y NADIE puede volver a
    hablarnos: el demonio sigue escondiendo y sacando barras por posicion del
    puntero, pero se queda sordo para siempre.

    Y sordo sin decirlo: `echo show > ...fifo` sobre una ruta sin FIFO CREA un
    fichero normal, escribe dentro y sale con 0. Los clicks en las lineas-tirador
    y el SUPER+C parecen funcionar y no hacen nada. Paso de verdad el 2026-08-01.
    """
    try:
        en_disco = os.stat(FIFO_PATH)
    except OSError:
        return False
    abierto = os.fstat(fifo)
    return (en_disco.st_ino, en_disco.st_dev) == (abierto.st_ino, abierto.st_dev)


def matar_otros():
    """SIGTERM a las otras instancias del demonio, y esperar a que se vayan.

    Por PID y no con `pkill -f waybar-autohide.py`, que es lo que hacia el atajo
    de reinicio y tenia dos fallos: el patron encaja tambien con el shell que
    lanza el reinicio —su linea de comandos contiene esa misma ruta—, asi que se
    mataba a si mismo antes de relanzar nada; y no esperaba, de modo que el
    `cleanup` de la instancia vieja llegaba tarde y borraba el FIFO que la nueva
    acababa de crear.
    """
    yo = os.getpid()
    otros = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit() or int(pid) == yo:
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as fh:
                partes = fh.read().decode(errors="replace").split("\0")
        except OSError:
            continue
        if len(partes) >= 2 and "python" in partes[0] and \
                partes[1].endswith("waybar-autohide.py"):
            otros.append(int(pid))

    for pid in otros:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    # Esperar a que suelten sus barras y su FIFO antes de crear los nuestros.
    limite = time.monotonic() + 5.0
    while otros and time.monotonic() < limite:
        otros = [p for p in otros if os.path.exists(f"/proc/{p}")]
        if otros:
            time.sleep(0.1)


def main():
    if "--reiniciar" in sys.argv:
        matar_otros()

    fifo = abrir_fifo()

    bars = {
        "main": Bar("config.jsonc", "trigger.jsonc", in_top_zone,
                    "waybar-main", "waybar-trigger"),
        "dock": Bar("dock.jsonc", "dock-trigger.jsonc", in_dock_zone,
                    "waybar-dock", "waybar-dock-trigger"),
    }

    def cleanup(*_):
        for bar in bars.values():
            bar.kill()
        # Solo se borra el FIFO si sigue siendo EL NUESTRO. Sin esta condicion,
        # una instancia que se apaga tarde se lleva por delante el FIFO de la que
        # acaba de arrancar y deja el sistema entero sin canal de ordenes.
        if es_nuestro(fifo):
            try:
                os.remove(FIFO_PATH)
            except OSError:
                pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    # Deja que las cuatro barras creen sus superficies antes de senalarlas.
    time.sleep(1.0)

    proxima_revision = 0.0

    while True:
        # El timeout de select() hace de reloj del bucle: no hace falta sleep.
        ready, _, _ = select.select([fifo], [], [], TICK)

        # Una vez por segundo se comprueba que el FIFO de la ruta sigue siendo el
        # que tenemos abierto, y si no, se rehace. Es lo que impide que el
        # demonio se quede sordo sin remedio: seis piezas le hablan por aqui —las
        # dos lineas-tirador, SUPER+C, el panel de calendario, el gestor del dock
        # y la pantalla de bloqueo— y todas fallan calladas si el FIFO no esta.
        ahora = time.monotonic()
        if ahora >= proxima_revision:
            proxima_revision = ahora + 1.0
            if not es_nuestro(fifo):
                os.close(fifo)
                fifo = abrir_fifo()
        if ready:
            try:
                data = os.read(fifo, 1024).decode(errors="replace")
            except BlockingIOError:
                data = ""
            for token in data.split():
                # "dock:show" -> dock; "show" a secas -> barra de arriba.
                target, _, cmd = token.rpartition(":")
                bar = bars.get(target or "main")
                if bar:
                    bar.command(cmd)

        windows, cursor_x, cursor_y = read_state()
        capas = layer_levels()
        for bar in bars.values():
            bar.update(windows, cursor_x, cursor_y, capas)

        # Si alguna barra muere (crash, kill manual), no seguimos a ciegas.
        if not all(bar.alive() for bar in bars.values()):
            cleanup()


if __name__ == "__main__":
    main()
