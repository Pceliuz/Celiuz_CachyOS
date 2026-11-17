#!/usr/bin/env python3
"""
hypr/scripts/grabar-indicador.py — la pastilla «● 00:12» de la grabacion, para
los modos en que la barra no se ve (gaming, programador, estudio).

    grabar-indicador.py              la lanza grabar.sh con cada grabacion
    grabar-indicador.py --png RUTA   la dibuja a un fichero (con --pausa, en pausa)

Hace lo mismo que el punto rojo de la barra: clic izquierdo termina la
grabacion, clic derecho la pausa o la reanuda. Y lo mismo con el teclado en
cualquier sitio: SUPER+R termina, SUPER+CTRL+R pausa.

COMO VIVE
---------
grabar.sh la lanza SIEMPRE al empezar, y ella decide cada segundo si se enseña:
solo con un modo puesto (lib/grabacion.py modo_sin_barra). Fuera de un modo se
queda escondida —la barra ya lo dice— y si entras al modo gaming con la
grabacion en marcha, aparece. Cuando la grabacion termina, se va sola. Una
sola a la vez: un cerrojo con la firma de la sesion.

DONDE SE PONE
-------------
En un monitor que NO salga en el video si lo hay (grabando la pantalla
completa, en la otra); si no, arriba a la derecha y pequeña. Grabando una
ventana da igual: la ventana se graba sola y lo que flota encima no entra.

El estado se lo pregunta a grabar.sh --estado, el unico dueño: aqui no se lee
el fichero de estado por libre.
"""

import fcntl
import json
import os
import subprocess
import sys

AQUI = os.path.dirname(os.path.realpath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, os.path.join(AQUI, "lib"))
import canales  # noqa: E402
import grabacion  # noqa: E402

GRABAR = os.path.join(AQUI, "grabar.sh")
COLORES = os.path.join(RAIZ, "waybar", "colores.css")
MARGEN = 14

ESTILO = """
window { background: transparent; }
.pastilla {
    background: alpha(@abismo, 0.92);
    border: 1px solid alpha(@rojo_neon, 0.8);
    border-radius: 999px;
    padding: 6px 14px 6px 12px;
    box-shadow: 0 0 10px alpha(@rojo_neon, 0.45);
}
.pastilla.pausado {
    border-color: alpha(@atencion, 0.8);
    box-shadow: 0 0 10px alpha(@atencion, 0.35);
}
.punto { color: @rojo_neon; font-size: 15px;
         font-family: "MesloLGS Nerd Font Propo", monospace; }
.pausado .punto { color: @atencion; }
.reloj { color: @luz; font-size: 14px; font-weight: 800;
         font-family: "MesloLGS Nerd Font Propo", monospace; }
.pista { color: @tenue; font-size: 11px; }
"""

# Los dos glifos de la MISMA fuente (md-record, md-pause; codigos sacados de
# lib/nf_icons.py iconos()): con el «⏸» de emoji la pastilla crecia 8 px al
# pausar y daba un salto.
G_GRABANDO = "\U000F044A"
G_PAUSA = "\U000F03E4"

COLORES_FABRICA = ("@define-color abismo #0d0418; @define-color luz #e4c7ff;"
                   "@define-color tenue #8a7aa8; @define-color atencion #f6c177;"
                   "@define-color rojo_neon #ff1f4b;")


def estado():
    """Lo que dice grabar.sh --estado; {} si no contesta."""
    try:
        r = subprocess.run([GRABAR, "--estado"], capture_output=True, text=True, timeout=3)
        return json.loads(r.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}


def reloj(segundos):
    s = max(0, int(segundos or 0))
    return "%02d:%02d" % (s // 60, s % 60)


def cerrojo():
    """Uno por sesion: si ya hay una pastilla viva, esta sobra."""
    try:
        fd = os.open(canales.canal("grabar-indicador", "lock"), os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except OSError:
        return None


def cargar_gtk():
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import Gdk, GLib, Gtk, GtkLayerShell
    return Gdk, GLib, Gtk, GtkLayerShell


class Pastilla:
    def __init__(self, Gtk, ventana):
        self.Gtk = Gtk
        self.ventana = ventana
        self.caja = Gtk.Box(spacing=8)
        self.caja.get_style_context().add_class("pastilla")
        self.punto = Gtk.Label(label=G_GRABANDO)
        self.punto.get_style_context().add_class("punto")
        self.reloj = Gtk.Label(label="00:00")
        self.reloj.get_style_context().add_class("reloj")
        self.pista = Gtk.Label(label="clic: terminar · derecho: pausa")
        self.pista.get_style_context().add_class("pista")
        for w in (self.punto, self.reloj, self.pista):
            self.caja.pack_start(w, False, False, 0)
        # Un EventBox para que el clic llegue: una Box sola no tiene ventana
        # propia y no recibe pulsaciones.
        self.eventos = Gtk.EventBox()
        self.eventos.add(self.caja)
        ventana.add(self.eventos)

    def pintar(self, datos):
        pausado = bool(datos.get("pausado"))
        self.punto.set_text(G_PAUSA if pausado else G_GRABANDO)
        self.reloj.set_text(reloj(datos.get("transcurrido")))
        self.pista.set_text("clic: terminar · derecho: seguir" if pausado
                            else "clic: terminar · derecho: pausa")
        ctx = self.caja.get_style_context()
        (ctx.add_class if pausado else ctx.remove_class)("pausado")


def cargar_estilo(Gtk, Gdk):
    try:
        with open(COLORES, encoding="utf-8") as fh:
            colores = fh.read()
    except OSError:
        colores = COLORES_FABRICA
    css = Gtk.CssProvider()
    css.load_from_data((colores + ESTILO).encode())
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css,
                                             Gtk.STYLE_PROVIDER_PRIORITY_USER)


def a_png(ruta, pausado):
    Gdk, GLib, Gtk, _ = cargar_gtk()
    if not Gtk.init_check(sys.argv)[0]:
        return 1
    cargar_estilo(Gtk, Gdk)
    ventana = Gtk.OffscreenWindow()
    p = Pastilla(Gtk, ventana)
    p.pintar({"pausado": pausado, "transcurrido": 754})
    ventana.show_all()
    GLib.timeout_add(300, Gtk.main_quit)
    Gtk.main()
    ventana.get_pixbuf().savev(ruta, "png", [], [])
    return 0


def main(argv):
    if not os.environ.get("WAYLAND_DISPLAY"):
        return 1
    # Sin caer nunca a X11: se dibujaria por XWayland donde no toca.
    os.environ["GDK_BACKEND"] = "wayland"
    if argv[:1] == ["--png"] and len(argv) >= 2:
        return a_png(argv[1], "--pausa" in argv)

    fd = cerrojo()
    if fd is None:
        return 0

    Gdk, GLib, Gtk, GtkLayerShell = cargar_gtk()
    if not Gtk.init_check(sys.argv)[0]:
        return 1
    cargar_estilo(Gtk, Gdk)

    ventana = Gtk.Window()
    GtkLayerShell.init_for_window(ventana)
    GtkLayerShell.set_namespace(ventana, "grabar-indicador")
    # OVERLAY: por encima tambien de un juego a pantalla completa.
    GtkLayerShell.set_layer(ventana, GtkLayerShell.Layer.OVERLAY)
    GtkLayerShell.set_anchor(ventana, GtkLayerShell.Edge.TOP, True)
    GtkLayerShell.set_anchor(ventana, GtkLayerShell.Edge.RIGHT, True)
    GtkLayerShell.set_margin(ventana, GtkLayerShell.Edge.TOP, MARGEN)
    GtkLayerShell.set_margin(ventana, GtkLayerShell.Edge.RIGHT, MARGEN)
    # Nunca coge el teclado: jugando, un aviso que robe el foco es lo peor.
    GtkLayerShell.set_keyboard_mode(ventana, GtkLayerShell.KeyboardMode.NONE)
    ventana.set_app_paintable(True)
    if ventana.get_screen().get_rgba_visual():
        ventana.set_visual(ventana.get_screen().get_rgba_visual())

    p = Pastilla(Gtk, ventana)
    p.caja.show_all()
    p.eventos.show()

    def clic(_w, evento):
        if evento.button == 1:
            subprocess.Popen([GRABAR, "--parar"], start_new_session=True)
        elif evento.button == 3:
            subprocess.Popen([GRABAR, "--pausar"], start_new_session=True)
        return True
    p.eventos.connect("button-press-event", clic)

    visible = {"si": False, "donde": None}

    def colocar(datos):
        mon = grabacion.monitor_para_indicador(datos.get("modo"), datos.get("donde"),
                                               grabacion.monitores())
        nombre = mon.get("name") if mon else None
        if nombre == visible["donde"]:
            return
        visible["donde"] = nombre
        if mon:
            gdk_mon = Gdk.Display.get_default().get_monitor_at_point(mon["x"] + 1, mon["y"] + 1)
            if gdk_mon:
                GtkLayerShell.set_monitor(ventana, gdk_mon)

    def latido():
        datos = estado()
        if not datos.get("grabando"):
            if Gtk.main_level() > 0:
                Gtk.main_quit()
            return False
        p.pintar(datos)
        if grabacion.modo_sin_barra():
            if not visible["si"]:
                # El monitor se fija con la capa sin mapear: cambiarlo con ella
                # a la vista no la mueve en todos los compositores.
                colocar(datos)
                ventana.show()
                visible["si"] = True
        elif visible["si"]:
            ventana.hide()
            visible["si"] = False
            visible["donde"] = None
        return True

    if latido():
        GLib.timeout_add(1000, latido)
        Gtk.main()
    os.close(fd)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
