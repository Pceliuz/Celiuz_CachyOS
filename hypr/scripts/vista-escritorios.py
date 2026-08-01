#!/usr/bin/env python3
"""vista-escritorios.py — el cambiador de escritorios de SUPER+TAB.

QUE ES. El gesto de Windows, pero de ESCRITORIOS y no de ventanas:

    manten SUPER y pulsa TAB   -> aparecen flotando en el centro los
                                  escritorios QUE TIENEN APPS ABIERTAS
    sin soltar SUPER, mas TAB  -> vas saltando de uno a otro, y el escritorio
                                  CAMBIA DE VERDAD a cada salto: no es una
                                  miniatura, es lo que hay
    suelta SUPER               -> te quedas donde estabas mirando

Las tarjetas flotan sobre la pantalla y no hay ni barra ni velo detras: lo que
se esta eligiendo es el escritorio de verdad, asi que taparlo seria quitarle el
sentido al gesto.

Los escritorios vacios no salen: para abrir algo nuevo en el 5 estan los
SUPER+numero de siempre, que no cambian. Son dos gestos distintos:
    SUPER+1..7  — "quiero ABRIR X ahi". Saltas a ciegas, y esta bien asi.
    SUPER+TAB   — "quiero VOLVER a lo que tengo abierto", pero no te acuerdas de
                  en cual lo dejaste. Lo ves y lo eliges.

LA PREVISUALIZACION ES EL CAMBIO DE VERDAD, igual que en CeliuzPaper al elegir
fondo: alli el fondo cambia a pantalla completa mientras te mueves por la tira, y
Escape deja el que tenias. Aqui igual.

    SUPER+TAB otra vez       siguiente
    SUPER+SHIFT+TAB          anterior
    soltar SUPER             quedarte donde estas mirando
    Enter o clic             lo mismo, por si sueltas SUPER sin querer
    Escape                   VOLVER al escritorio desde el que abriste
    1..9                     ir a ese escritorio y listo

OJO CON QUIEN MUEVE LA SELECCION: no es el teclado de esta ventana. Hyprland
atiende sus binds antes de entregar la tecla al cliente, asi que mientras SUPER
siga pulsado la capa NUNCA ve el TAB (comprobado en la sesion real con
VISTA_DEBUG: solo aparecen procesos nuevos, ni una pulsacion). Por eso cada
SUPER+TAB nuevo le manda una senal a la ventana que ya esta abierta en vez de
abrir otra — ver despertar().

Como toda capa que coge el teclado en exclusiva, lleva salida de emergencia:
Escape y un cierre automatico a los SEGUNDOS_MAXIMOS sin tocar nada, que se
rearma con cada tecla. Una capa asi colgada te deja sin teclado en todo el
escritorio, y eso no puede depender de que el codigo no falle nunca.

Depuracion:  VISTA_DEBUG=1 vista-escritorios.py
             escribe cada tecla, cada senal y cada salto en
             $XDG_RUNTIME_DIR/vista-escritorios.log
"""

import os
import signal
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PALETA_CONF = os.path.join(RAIZ, "conf", "colores.conf")
EJECUCION = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
PIDFILE = os.path.join(EJECUCION, "vista-escritorios.pid")
DIARIO = os.path.join(EJECUCION, "vista-escritorios.log")

TAM_ICONO = 72
MAX_ICONOS = 5
ANCHO_TARJETA = 380
SEGUNDOS_MAXIMOS = 20   # cierre de seguridad, se rearma con cada tecla

# Cada cuanto se mira la bandera de "soltaron SUPER". 30 ms no se nota al soltar
# y no gasta nada; ver _mirar_si_soltaron para por que es una bandera y no una
# senal enganchada a GLib.
MS_MIRAR_SOLTAR = 30

DEPURAR = os.environ.get("VISTA_DEBUG") == "1"


def apuntar(texto):
    if not DEPURAR:
        return
    with open(DIARIO, "a") as fh:
        fh.write(f"{time.strftime('%H:%M:%S')} {texto}\n")


def despertar(senal):
    """Si ya hay una ventana abierta, le manda la senal y devuelve True.

    ESTA ES LA PIEZA CLAVE DE TODO EL ATAJO, y no es un adorno.

    La ventana NUNCA llega a ver el TAB. Comprobado en la sesion real con
    VISTA_DEBUG: al mantener SUPER y pulsar TAB otra vez, en el diario no
    aparece ni una pulsacion de tecla — lo que aparece es un proceso NUEVO.
    Hyprland atiende sus binds ANTES de entregar la tecla al cliente, asi que
    mientras SUPER siga pulsado cada TAB vuelve a disparar el bind y la ventana
    no se entera de nada.

    Con lo que hacia la primera version (matar a la anterior y abrir otra), el
    efecto era el que se notaba al usarlo: cambiaba a un escritorio, y al
    segundo TAB "se regresaba y se cerraba" — porque al morir por SIGTERM la
    anterior volvia a su escritorio de partida.

    El pidfile va aqui dentro y no con un `pkill -f` en el bind por lo de
    siempre: pkill -f se encuentra a si mismo en la linea de comandos del propio
    bind y se mata antes de empezar.
    """
    try:
        with open(PIDFILE) as fh:
            pid = int(fh.read().strip())
        os.kill(pid, 0)                # existe?
    except (OSError, ValueError):
        return False
    try:
        os.kill(pid, senal)
    except OSError:
        return False
    return True


# --- Fase temprana, ANTES de cargar GTK --------------------------------------
# Importar GTK cuesta 100 ms medidos, y hasta que no acaba este proceso no
# existe para nadie. Eso abria una carrera de verdad: si sueltas SUPER en ese
# rato, el aviso de "lo solte" (bindr de keybinds.conf, que manda SIGWINCH) no
# encontraba a quien avisar y la ventana se quedaba abierta para siempre — el
# fallo de "la toco rapido y se queda puesta".
#
# Por eso lo primero de todo, antes de importar nada caro, es: mirar si ya hay
# otra ventana abierta (y entonces solo despertarla), dejar el pidfile puesto, y
# apuntar el aviso de soltar si llega antes de tiempo. Asi la ventana ciega baja
# de ~130 ms a ~30 ms.
ATRAS = "--atras" in sys.argv
SOLTARON_SUPER = False


def _apunta_que_soltaron(*_):
    """Manejador de SIGWINCH. Vive desde el primer milisegundo y NO se cambia.

    Este manejador se queda puesto TODA la vida del proceso, y la ventana lo
    consulta cada pocos milisegundos. Es a proposito: antes se ponia este al
    principio y luego, al abrir la ventana, se le encimaba el de GLib
    (`unix_signal_add`) — y el aviso de soltar SUPER se perdia entre los dos.
    En el diario de la sesion real se veia clavado: el ciclo funcionaba, pero al
    soltar no pasaba nada y habia que rematar con Enter.

    Un manejador de senal de Python no puede tocar GTK: solo levanta la bandera.
    """
    global SOLTARON_SUPER
    SOLTARON_SUPER = True
    apuntar("senal: soltaron SUPER")


if __name__ == "__main__":
    if despertar(signal.SIGUSR2 if ATRAS else signal.SIGUSR1):
        sys.exit(0)
    signal.signal(signal.SIGWINCH, _apunta_que_soltaron)
    with open(PIDFILE, "w") as fh:
        fh.write(str(os.getpid()))

import re                                                        # noqa: E402
import subprocess                                                # noqa: E402

import gi                                                        # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, GtkLayerShell, Pango  # noqa: E402,E501


# --- La paleta ---------------------------------------------------------------

def paleta():
    """Lee conf/colores.conf y devuelve {nombre: (r, g, b, a)}.

    Se lee en caliente en vez de copiar los violetas aqui porque la paleta es
    fuente unica (ver el README): si algun dia cambia el amatista, esta pantalla
    cambia sola. GTK no sabe leer hyprlang, asi que la conversion es este parseo.

    OJO CON EL ORDEN DEL ALFA: en los ARCHIVOS de config el formato es
    rgba(RRGGBBAA) — el alfa va AL FINAL. `hyprctl getoption` los devuelve al
    reves (AARRGGBB), y confundirlos da colores casi iguales con la
    transparencia cambiada, que cuesta mucho de ver.
    """
    colores = {}
    patron = re.compile(r"^\$(\w+)\s*=\s*rgba\(([0-9a-fA-F]{8})\)")
    try:
        with open(PALETA_CONF, encoding="utf-8") as fh:
            for linea in fh:
                m = patron.match(linea.strip())
                if m:
                    v = m.group(2)
                    colores[m.group(1)] = (
                        int(v[0:2], 16), int(v[2:4], 16),
                        int(v[4:6], 16), int(v[6:8], 16) / 255)
    except OSError:
        pass
    return colores


COLORES = paleta()


def col(nombre, alfa=None, respaldo="rgba(177,108,255,1)"):
    """Un color de la paleta como rgba() de CSS, opcionalmente con otro alfa."""
    if nombre not in COLORES:
        return respaldo
    r, g, b, a = COLORES[nombre]
    return f"rgba({r},{g},{b},{a if alfa is None else alfa:.3f})"


def css():
    return f"""
    /* La capa no se pinta: NADA de barra ni de velo. Lo unico que se ve son las
     * tarjetas flotando en el centro, porque todo lo demas de la pantalla es la
     * previsualizacion — el escritorio de verdad, que hay que poder mirar
     * entero. Cualquier fondo aqui taparia justo lo que se esta eligiendo. */
    window {{
        background-color: transparent;
        font-family: "MesloLGS Nerd Font";
        color: {col('luz')};
    }}
    /* La tarjeta en reposo casi no existe: solo la elegida esta encendida. Si
     * todas brillaran, no se sabria de un vistazo cual estas mirando. */
    /* Las tarjetas van casi opacas a proposito. No es capricho: flotan sobre
     * CUALQUIER cosa (un navegador blanco, un juego, una terminal), y con poca
     * opacidad se colaba lo de detras — medido, un 5% bastaba para que los
     * numeros de una calculadora se leyeran como fantasmas dentro. */
    #tarjeta {{
        background-color: {col('superficie', 0.94)};
        border: 2px solid {col('apagado')};
        border-radius: 14px;
        padding: 18px 20px;
        margin: 9px;
        transition: background-color 120ms ease-in-out,
                    border-color 120ms ease-in-out;
    }}
    #tarjeta:hover {{ border-color: {col('amatista', 0.55)}; }}
    #tarjeta.elegida {{
        border-color: {col('neon')};
        background-color: {col('violeta', 0.30)};
    }}
    #numero {{ font-size: 44px; font-weight: bold; color: {col('tenue')}; }}
    #tarjeta.elegida #numero {{ color: {col('luz')}; }}
    /* De donde saliste. Sirve para saber que te devuelve Escape. */
    #origen {{ font-size: 11px; color: {col('amatista')}; padding-left: 12px; }}
    #apps {{ font-size: 15px; color: {col('tenue')}; padding-top: 10px; }}
    #tarjeta.elegida #apps {{ color: {col('luz', 0.85)}; }}
    #mas {{ font-size: 16px; color: {col('tenue')}; padding-left: 8px; }}
    """


# --- Lo que hay abierto ------------------------------------------------------

def _hyprctl(*args, json_=False):
    import json
    orden = ["hyprctl"] + (["-j"] if json_ else []) + list(args)
    salida = subprocess.run(orden, capture_output=True, text=True).stdout
    return json.loads(salida) if json_ else salida.strip()


def escritorio_actual():
    return _hyprctl("activeworkspace", json_=True).get("id")


def escritorios_con_apps():
    """Los escritorios que tienen ventanas, con sus apps, ordenados por numero.

    Se construye desde `clients` y no desde `workspaces` porque el recuento de
    workspaces incluye ventanas que no estan mapeadas y aqui hace falta lo que
    se ve de verdad. Los escritorios especiales (id negativo) quedan fuera: son
    el scratchpad, no sitios a los que "ir".
    """
    ventanas = {}
    for c in _hyprctl("clients", json_=True):
        wid = c.get("workspace", {}).get("id", 0)
        if wid <= 0 or not c.get("mapped", True) or c.get("hidden"):
            continue
        ventanas.setdefault(wid, []).append(c)

    salida = []
    for wid in sorted(ventanas):
        # Por orden de uso reciente: el foco mas fresco primero, que es el que
        # mejor te recuerda "esto es lo que dejaste ahi".
        apps = sorted(ventanas[wid], key=lambda c: c.get("focusHistoryID", 99))
        salida.append({
            "id": wid,
            "apps": [(c.get("class", ""), c.get("title", "")) for c in apps],
        })
    return salida


# --- Iconos de las apps ------------------------------------------------------

def _dirs_apps():
    """Todos los sitios donde el sistema guarda .desktop, por prioridad XDG."""
    dirs = [os.path.join(os.path.expanduser(
        os.environ.get("XDG_DATA_HOME", "~/.local/share")), "applications")]
    for base in os.environ.get(
            "XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":"):
        if base:
            dirs.append(os.path.join(base, "applications"))
    # Flatpak y Snap no siempre estan en XDG_DATA_DIRS de la sesion. Es
    # exactamente lo que hacia que Minecraft no saliera en el gestor del dock.
    dirs += ["/var/lib/flatpak/exports/share/applications",
             os.path.expanduser(
                 "~/.local/share/flatpak/exports/share/applications"),
             "/var/lib/snapd/desktop/applications"]
    return dirs


def mapa_iconos():
    """{clase de ventana en minusculas: nombre de icono}.

    Hyprland da la CLASE de la ventana (`brave-browser`, `steam`), que no tiene
    por que llamarse igual que su icono. El puente es el .desktop: se indexa por
    su nombre de archivo y por `StartupWMClass`, que es justo el campo que
    existe para decir "la ventana que abro se llama asi".
    """
    mapa = {}
    for carpeta in _dirs_apps():
        if not os.path.isdir(carpeta):
            continue
        for nombre in os.listdir(carpeta):
            if not nombre.endswith(".desktop"):
                continue
            icono = clase_wm = None
            try:
                with open(os.path.join(carpeta, nombre),
                          encoding="utf-8", errors="replace") as fh:
                    for linea in fh:
                        if linea.startswith("Icon="):
                            icono = icono or linea[5:].strip()
                        elif linea.startswith("StartupWMClass="):
                            clase_wm = linea[15:].strip()
                        elif linea.startswith("[Desktop Action"):
                            break
            except OSError:
                continue
            if not icono:
                continue
            # setdefault: gana el primero, y las carpetas vienen en orden de
            # prioridad XDG (lo del usuario pisa a lo del sistema).
            mapa.setdefault(nombre[:-8].lower(), icono)
            if clase_wm:
                mapa.setdefault(clase_wm.lower(), icono)
    return mapa


class Iconos:
    def __init__(self):
        self.mapa = mapa_iconos()
        self.tema = Gtk.IconTheme.get_default()
        self.cache = {}

    def pixbuf(self, clase):
        if clase in self.cache:
            return self.cache[clase]
        pb = self._buscar(clase)
        self.cache[clase] = pb
        return pb

    def _buscar(self, clase):
        c = (clase or "").lower()
        candidatos = [self.mapa.get(c), c, c.split(".")[-1],
                      # org.kde.dolphin -> dolphin; Brave-browser -> brave
                      c.split("-")[0]]
        for nombre in candidatos:
            if not nombre:
                continue
            try:
                if os.path.isabs(nombre) and os.path.exists(nombre):
                    return GdkPixbuf.Pixbuf.new_from_file_at_size(
                        nombre, TAM_ICONO, TAM_ICONO)
                pb = self.tema.load_icon(
                    nombre, TAM_ICONO, Gtk.IconLookupFlags.FORCE_SIZE)
                if pb:
                    return pb
            except Exception:
                continue
        try:
            return self.tema.load_icon(
                "application-x-executable", TAM_ICONO,
                Gtk.IconLookupFlags.FORCE_SIZE)
        except Exception:
            return None


# --- La tira -----------------------------------------------------------------

class Vista(Gtk.Window):
    def __init__(self, datos, origen, paso_inicial=1):
        super().__init__()
        self.datos = datos
        self.origen = origen           # donde estabas al abrir; lo devuelve Escape
        self.destino = None            # a donde ir al cerrar; lo ejecuta main()
        self.tarjetas = []
        self.iconos = Iconos()
        self.reloj = None

        indice_origen = next(
            (i for i, d in enumerate(datos) if d["id"] == origen), 0)
        self.elegido = indice_origen

        self._montar_capa()
        # El visual RGBA. Sin canal alfa GTK compone el fondo contra negro y la
        # tira sale opaca del todo, perdiendo lo que se ve por detras.
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)

        prov = Gtk.CssProvider()
        prov.load_from_data(css().encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), prov,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.connect("destroy", Gtk.main_quit)
        self.connect("key-press-event", self._tecla)
        self.connect("key-release-event", self._soltar)

        self._construir()
        self.show_all()

        # Igual que el Alt+Tab de Windows: la combinacion ya te deja mirando el
        # SIGUIENTE, no donde estabas. Asi un toque rapido de SUPER+TAB te lleva
        # al otro escritorio sin tener que pulsar nada mas.
        self._mover(paso_inicial)

        # Avanzar y retroceder LLEGAN POR SENAL, no por teclado. Ver el
        # comentario de main(): Hyprland se queda la combinacion antes de que
        # llegue aqui, asi que cada SUPER+TAB nuevo despierta a esta ventana en
        # vez de abrir otra.
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1,
                             self._avanzar)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR2,
                             self._retroceder)
        self._rearmar_vigilante()

        # El aviso de "solte SUPER" se mira aqui, no se engancha como senal de
        # GLib: el manejador de la fase temprana ya tiene cogido SIGWINCH y
        # encimarle otro hacia que el aviso se perdiera. Esta vuelta tan
        # seguida ademas le da al interprete de Python ocasion de atender la
        # senal enseguida, que si no puede quedarse esperando dentro del poll.
        #
        # Sirve para las dos situaciones: si lo soltaste mientras esto
        # arrancaba, la bandera ya viene levantada de antes y se cierra en la
        # primera vuelta.
        GLib.timeout_add(MS_MIRAR_SOLTAR, self._mirar_si_soltaron)

    def _montar_capa(self):
        GtkLayerShell.init_for_window(self)
        # El namespace identifica la capa en los layerrule de Hyprland.
        GtkLayerShell.set_namespace(self, "vista-escritorios")
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        # La capa ocupa la pantalla entera pero es TRANSPARENTE: lo unico que se
        # pinta son las tarjetas, flotando en el centro. Antes era una tira
        # ancha apoyada abajo y tapaba parte de la app que estabas
        # previsualizando, que es justo lo que no puede pasar aqui.
        for borde in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM,
                      GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
            GtkLayerShell.set_anchor(self, borde, True)
        # EXCLUSIVE: hace falta para enterarse de que sueltas SUPER. Con
        # ON_DEMAND el teclado se queda en la ventana de debajo y no llega nada.
        GtkLayerShell.set_keyboard_mode(
            self, GtkLayerShell.KeyboardMode.EXCLUSIVE)

    def _repartir(self):
        """Como se colocan las tarjetas: un rectangulo, no una fila larga.

        Con uno o dos escritorios, una fila. De tres en adelante, DOS filas y
        arriba la mas llena, con la de abajo centrada bajo ella:

            3 -> 2 arriba, 1 abajo        5 -> 3 arriba, 2 abajo
            4 -> 2 y 2                    6 -> 3 y 3        7 -> 4 y 3

        Una sola fila de siete tarjetas grandes se comeria la pantalla de lado a
        lado, que es justo lo que hay que dejar ver.
        """
        pares = list(enumerate(self.datos))
        if len(pares) <= 2:
            return [pares]
        columnas = -(-len(pares) // 2)      # techo de la division
        return [pares[:columnas], pares[columnas:]]

    def _construir(self):
        centro = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        centro.set_halign(Gtk.Align.CENTER)
        centro.set_valign(Gtk.Align.CENTER)

        for tanda in self._repartir():
            fila = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            # Centrada por su cuenta: asi la fila de abajo queda centrada bajo
            # la de arriba cuando tiene una tarjeta menos.
            fila.set_halign(Gtk.Align.CENTER)
            for indice, d in tanda:
                fila.pack_start(self._tarjeta(indice, d), False, False, 0)
            centro.pack_start(fila, False, False, 0)

        self.add(centro)

    def _tarjeta(self, indice, d):
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        caja.set_name("tarjeta")
        caja.set_size_request(ANCHO_TARJETA, -1)

        cabecera = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        numero = Gtk.Label(label=str(d["id"]))
        numero.set_name("numero")
        cabecera.pack_start(numero, False, False, 0)
        if d["id"] == self.origen:
            marca = Gtk.Label(label="DESDE AQUI")
            marca.set_name("origen")
            marca.set_valign(Gtk.Align.CENTER)
            cabecera.pack_start(marca, False, False, 0)
        caja.pack_start(cabecera, False, False, 0)

        iconos = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for clase, _ in d["apps"][:MAX_ICONOS]:
            pb = self.iconos.pixbuf(clase)
            if pb:
                iconos.pack_start(
                    Gtk.Image.new_from_pixbuf(pb), False, False, 0)
        if len(d["apps"]) > MAX_ICONOS:
            mas = Gtk.Label(label=f"+{len(d['apps']) - MAX_ICONOS}")
            mas.set_name("mas")
            iconos.pack_start(mas, False, False, 0)
        caja.pack_start(iconos, False, False, 0)

        nombres = []
        for clase, titulo in d["apps"]:
            corto = (clase or titulo).split(".")[-1]
            if corto and corto not in nombres:
                nombres.append(corto)
        etiqueta = Gtk.Label(label=" · ".join(nombres))
        etiqueta.set_name("apps")
        etiqueta.set_xalign(0)
        etiqueta.set_ellipsize(Pango.EllipsizeMode.END)
        etiqueta.set_max_width_chars(24)
        caja.pack_start(etiqueta, False, False, 0)

        # Gtk.Box no recibe clics por si solo: hace falta un EventBox.
        marco = Gtk.EventBox()
        marco.add(caja)
        marco.connect("button-press-event", self._clic, indice)
        self.tarjetas.append(caja)
        return marco

    # --- Moverse y previsualizar ---

    def _marcar(self):
        for i, tarjeta in enumerate(self.tarjetas):
            ctx = tarjeta.get_style_context()
            if i == self.elegido:
                ctx.add_class("elegida")
            else:
                ctx.remove_class("elegida")

    def _mover(self, paso):
        self.elegido = (self.elegido + paso) % len(self.datos)
        self._marcar()
        self._previsualizar()

    def _avanzar(self, *_):
        apuntar("me despiertan: avanzar")
        self._rearmar_vigilante()
        self._mover(1)
        return True             # True = seguir escuchando la senal

    def _retroceder(self, *_):
        apuntar("me despiertan: retroceder")
        self._rearmar_vigilante()
        self._mover(-1)
        return True

    def _previsualizar(self):
        """El salto de verdad, con la tira todavia abierta.

        Se puede: comprobado que un `dispatch workspace` con esta capa abierta
        SI cambia el escritorio a la vista (la capa se queda encima, porque las
        capas son del monitor y no del escritorio). Esto es lo que hace que
        elegir sea mirar, como en CeliuzPaper con los fondos.
        """
        destino = self.datos[self.elegido]["id"]
        apuntar(f"previsualizo {destino}")
        _hyprctl("dispatch", "workspace", str(destino))

    def _clic(self, _widget, _ev, indice):
        self.elegido = indice
        self._marcar()
        self._previsualizar()
        return self._quedarse()

    # --- Teclado ---

    def _tecla(self, _w, ev):
        self._rearmar_vigilante()
        tecla = Gdk.keyval_name(ev.keyval)
        apuntar(f"tecla {tecla} estado={ev.state}")
        if ev.state & Gdk.ModifierType.MOD4_MASK:
            self.armado = True

        if tecla == "Escape":
            return self._volver()
        if tecla in ("Return", "KP_Enter"):
            return self._quedarse()
        if tecla in ("Tab", "Right", "Down"):
            self._mover(1)
        elif tecla in ("ISO_Left_Tab", "Left", "Up"):
            self._mover(-1)
        elif tecla and len(tecla) == 1 and tecla.isdigit():
            destino = next(
                (i for i, d in enumerate(self.datos)
                 if d["id"] == int(tecla)), None)
            if destino is not None:
                self.elegido = destino
                self._marcar()
                self._previsualizar()
                return self._quedarse()
        return True

    def _soltar(self, _w, ev):
        """Soltaste SUPER con la ventana ya puesta y con el foco: te quedas.

        Este es el camino normal y esta comprobado que llega (en el diario de la
        sesion real aparece "suelto Super_L"). El otro camino, para cuando la
        ventana aun no existia, es la senal del bindr — ver soltaron_super().
        """
        tecla = Gdk.keyval_name(ev.keyval)
        apuntar(f"suelto {tecla}")
        if tecla in ("Super_L", "Super_R"):
            return self._quedarse()
        return True

    def _mirar_si_soltaron(self):
        """Aviso de Hyprland de que SUPER se solto (bindr -> SIGWINCH).

        ESTE ES EL CAMINO BUENO, y no un respaldo del evento de teclado: desde
        que existe el `bindr` sobre SUPER_L, **Hyprland se queda esa tecla y ya
        no se la pasa a la ventana**. Comprobado en la sesion real: en el diario
        no aparece ni un solo "suelto", y si aparecen las pulsaciones normales
        (un Return). O sea que el evento de soltar de GTK esta muerto por
        diseno, y quien avisa es el compositor.

        Tampoco se puede adivinar preguntando: `Gdk.Keymap.get_modifier_state()`
        en esta sesion devuelve SIEMPRE 0x4000040 (con el bit de SUPER puesto)
        aunque no la toque nadie — no es el estado en vivo, es el mapa de que
        bit le corresponde. Medido.
        """
        if not SOLTARON_SUPER:
            return True
        apuntar("me quedo donde estoy: soltaron SUPER")
        self._quedarse()
        return False

    # --- Salidas ---

    def _quedarse(self):
        """Confirmar: te quedas en lo que estas mirando."""
        self.destino = self.datos[self.elegido]["id"]
        return self._cerrar()

    def _volver(self):
        """Cancelar: al escritorio desde el que abriste la tira."""
        self.destino = self.origen
        return self._cerrar()

    def _rearmar_vigilante(self):
        if self.reloj:
            GLib.source_remove(self.reloj)
        self.reloj = GLib.timeout_add_seconds(
            SEGUNDOS_MAXIMOS, lambda: self._volver() or False)

    def _cerrar(self):
        if self.reloj:
            # Si no se quita, saltaria sobre una ventana ya destruida y GTK
            # protestaria por consola.
            GLib.source_remove(self.reloj)
            self.reloj = None
        self.destroy()
        return True


# --- Arranque ----------------------------------------------------------------

def main():
    # Lo de "ya hay una abierta" y el pidfile se resolvio en la fase temprana,
    # arriba del todo, antes de cargar GTK.
    datos = escritorios_con_apps()
    if len(datos) < 2:
        # Con un solo escritorio ocupado no hay nada que elegir, y con ninguno
        # menos: abrir esto solo estorbaria.
        try:
            os.unlink(PIDFILE)
        except OSError:
            pass
        return 0

    origen = escritorio_actual()
    vista = Vista(datos, origen, -1 if ATRAS else 1)
    for sen in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        # Que un kill no te deje tirado en otro escritorio: se vuelve al de
        # partida, igual que con Escape.
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sen, vista._volver)
    try:
        Gtk.main()
    finally:
        try:
            os.unlink(PIDFILE)
        except OSError:
            pass

    # El salto final se REPITE aqui, ya sin capa por medio. Hace falta aunque la
    # previsualizacion ya te haya llevado: al destruirse una capa con el teclado
    # en exclusiva, Hyprland devuelve el foco a la ventana que lo tenia antes, y
    # esa ventana puede traerse consigo su escritorio, deshaciendo el salto sin
    # ningun aviso (hyprctl responde "ok" igual).
    if vista.destino is not None:
        _hyprctl("dispatch", "workspace", str(vista.destino))
    return 0


if __name__ == "__main__":
    sys.exit(main())
