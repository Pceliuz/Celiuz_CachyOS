#!/usr/bin/env python3
"""
hypr/scripts/grabar-elegir.py — la tarjeta de SUPER+R: ¿que grabamos?

    grabar-elegir.py            la tarjeta; imprime la eleccion y sale con 0
    grabar-elegir.py --png RUTA dibuja la tarjeta a un PNG sin enseñar nada
                                (con --ventanas, la segunda pagina)

Contesta con los argumentos de grabar.sh, en una linea:

    --full | --zona | --ventana 0xDIRECCION      y detras, si toca, --sin-audio

Esc (o «Cancelar») sale con 1 sin imprimir nada. La tarjeta NO graba: solo
pregunta. Quien graba es grabar.sh, y asi el mismo script sirve igual desde el
atajo directo (SUPER+ALT+R) que desde aqui.

Es una capa OVERLAY con el teclado en exclusiva, como la del modo gaming (de la
que toma el aspecto): 1, 2 y 3 eligen sin raton, S cambia el sonido.

El interruptor del sonido se recuerda entre grabaciones
($XDG_STATE_HOME/celiuz/grabar.json): quien graba clases con sonido lo quiere
asi la proxima vez, sin tener que acordarse.
"""

import importlib.util
import json
import os
import sys

AQUI = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(AQUI, "lib"))
import grabacion  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "tarjeta_base", os.path.join(AQUI, "modo-gaming-tarjeta.py"))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
Gtk, Gdk, GLib, GtkLayerShell = base.Gtk, base.Gdk, base.GLib, base.GtkLayerShell
from gi.repository import Pango  # noqa: E402

ESTILO_EXTRA = """
    .opcion { padding: 14px 10px; }
    .opcion .glifo { font-size: 30px; color: @neon; }
    .opcion .nombre { font-size: 14px; font-weight: 700; color: @luz; }
    .opcion .tecla { margin-left: 0; }
    .opcion:hover { border-color: @neon; background: alpha(@violeta, 0.35); }
    .sonido-titulo { color: @luz; font-weight: 700; font-size: 14px; }
    .sonido-detalle { color: @tenue; font-size: 12px; }
    switch { background-image: none; background-color: @apagado; border: none;
             border-radius: 12px; min-width: 40px; min-height: 22px; box-shadow: none; }
    switch:checked { background-color: @violeta; box-shadow: 0 0 8px alpha(@neon, 0.55); }
    switch slider { background-image: none; background-color: @tenue; border: none;
                    border-radius: 50%; min-width: 16px; min-height: 16px; margin: 3px;
                    box-shadow: none; }
    switch:checked slider { background-color: @luz; }
    switch image { color: transparent; }
    .fila { border-radius: 10px; padding: 8px 10px; background: none; border: 1px solid transparent;
            box-shadow: none; }
    .fila:hover { background: alpha(@amatista, 0.14); border-color: alpha(@amatista, 0.4); }
    .fila .titulo-ventana { color: @luz; font-size: 13px; font-weight: 700; }
    .fila .detalle-ventana { color: @tenue; font-size: 11px; }
    .vacio { color: @tenue; font-size: 13px; padding: 12px 4px; }
    .enlace { background: none; border: none; box-shadow: none; color: @tenue;
              font-size: 12px; padding: 4px 6px; }
    .enlace:hover { color: @luz; }
    scrollbar { background: none; border: none; }
    scrollbar slider { background-color: @apagado; border: none; min-width: 4px; border-radius: 2px; }
"""

OPCIONES = (
    # (tecla, glifo Nerd Font, nombre, argumento). Los codigos salen del nombre
    # del glifo en la fuente (lib/nf_icons.py iconos()), no de memoria.
    ("1", "\U000F0379", "Pantalla completa", "--full"),   # md-monitor
    ("2", "\U000F0A6D", "Una zona", "--zona"),            # md-selection_drag
    ("3", "\U000F10AC", "Una ventana", "--ventana"),      # md-dock_window
)

DETALLE_SONIDO = {
    "--full": "Todo lo que suena en el equipo.",
    "--zona": "Todo lo que suena en el equipo.",
    "--ventana": "Solo el de esa app: tu música o una llamada no se cuelan.",
    None: "Con la pantalla o una zona, todo lo que suena; con una ventana, solo esa app.",
}


# --- El interruptor del sonido, recordado -----------------------------------

def ruta_preferencias():
    estado = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(estado, "celiuz", "grabar.json")


def leer_sonido():
    try:
        with open(ruta_preferencias()) as f:
            return bool(json.load(f).get("sonido", True))
    except (OSError, ValueError, AttributeError):
        return True   # lo de fabrica: con sonido, que es lo que se pidio


def guardar_sonido(valor):
    ruta = ruta_preferencias()
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w") as f:
            json.dump({"sonido": bool(valor)}, f)
    except OSError:
        pass   # no recordarlo no puede impedir grabar


def eleccion(argumento, sonido, direccion=None):
    """La linea que se le devuelve a grabar.sh."""
    partes = [argumento] + ([direccion] if direccion else [])
    if not sonido:
        partes.append("--sin-audio")
    return " ".join(partes)


# --- La tarjeta ---------------------------------------------------------------

def etiqueta(texto, clase, **kw):
    e = Gtk.Label(label=texto, xalign=kw.pop("xalign", 0), **kw)
    e.get_style_context().add_class(clase)
    return e


def icono_de(clase):
    """El icono de la app por su clase; si el tema no lo tiene, uno generico."""
    tema = Gtk.IconTheme.get_default()
    for nombre in (clase, clase.lower(), clase.lower().split(".")[-1], "application-x-executable"):
        if nombre and tema and tema.has_icon(nombre):
            img = Gtk.Image.new_from_icon_name(nombre, Gtk.IconSize.DND)
            img.set_pixel_size(32)
            return img
    return Gtk.Image()


class Tarjeta:
    def __init__(self, ventana, lista_ventanas):
        self.ventana = ventana
        self.lista = lista_ventanas
        self.respuesta = None
        self.sonido = leer_sonido()

        self.pila = Gtk.Stack()
        self.pila.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.pila.set_transition_duration(120)
        self.pila.set_vhomogeneous(False)
        self.pila.set_interpolate_size(True)
        self.pila.add_named(self.pagina_inicio(), "inicio")
        self.pila.add_named(self.pagina_ventanas(), "ventanas")

        marco = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        marco.get_style_context().add_class("tarjeta")
        marco.set_size_request(520, -1)
        marco.pack_start(self.pila, True, True, 0)
        ventana.add(marco)

    # -- Pagina 1: que grabar y si con sonido --
    def pagina_inicio(self):
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        caja.pack_start(etiqueta("●  GRABAR", "marca"), False, False, 0)
        caja.pack_start(etiqueta("¿Qué grabamos?", "titulo"), False, False, 0)

        botones = Gtk.Box(spacing=12, homogeneous=True)
        botones.set_margin_top(10)
        for tecla, glifo, nombre, arg in OPCIONES:
            b = Gtk.Button()
            dentro = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            dentro.pack_start(etiqueta(glifo, "glifo", xalign=0.5), False, False, 0)
            dentro.pack_start(etiqueta(nombre, "nombre", xalign=0.5), False, False, 0)
            t = etiqueta(tecla, "tecla", xalign=0.5)
            t.set_halign(Gtk.Align.CENTER)
            dentro.pack_start(t, False, False, 0)
            b.add(dentro)
            for c in ("boton", "opcion"):
                b.get_style_context().add_class(c)
            b.connect("clicked", lambda _b, a=arg: self.elegir(a))
            b.connect("enter-notify-event", lambda *_a, a=arg: self.pintar_sonido(a))
            b.connect("leave-notify-event", lambda *_a: self.pintar_sonido(None))
            botones.pack_start(b, True, True, 0)
        caja.pack_start(botones, False, False, 0)

        fila = Gtk.Box(spacing=12)
        fila.set_margin_top(10)
        textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        textos.pack_start(etiqueta("Con sonido", "sonido-titulo"), False, False, 0)
        self.detalle_sonido = etiqueta("", "sonido-detalle")
        self.detalle_sonido.set_line_wrap(True)
        self.detalle_sonido.set_max_width_chars(52)
        textos.pack_start(self.detalle_sonido, False, False, 0)
        fila.pack_start(textos, True, True, 0)
        self.interruptor = Gtk.Switch(active=self.sonido)
        self.interruptor.set_valign(Gtk.Align.CENTER)
        self.interruptor.connect("notify::active", self.cambio_sonido)
        fila.pack_end(self.interruptor, False, False, 0)
        caja.pack_start(fila, False, False, 0)
        self.pintar_sonido(None)

        pie = Gtk.Box(spacing=6)
        pie.set_margin_top(6)
        cancelar = base.boton("Cancelar", "Esc", False)
        cancelar.connect("clicked", lambda *_: self.terminar(None))
        pie.pack_end(cancelar, False, False, 0)
        pie.pack_start(etiqueta("SUPER+R otra vez la termina", "sonido-detalle"), False, False, 0)
        caja.pack_start(pie, False, False, 0)
        return caja

    def pintar_sonido(self, arg):
        if not self.sonido:
            self.detalle_sonido.set_text("Sin sonido: solo la imagen.")
        else:
            self.detalle_sonido.set_text(DETALLE_SONIDO[arg])
        return False

    def cambio_sonido(self, interruptor, _p):
        self.sonido = interruptor.get_active()
        guardar_sonido(self.sonido)
        self.pintar_sonido(None)

    # -- Pagina 2: que ventana --
    def pagina_ventanas(self):
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        caja.pack_start(etiqueta("●  GRABAR UNA VENTANA", "marca"), False, False, 0)
        caja.pack_start(etiqueta("¿Cuál?", "titulo"), False, False, 0)
        nota = etiqueta("Se graba ella aunque te vayas a otra ventana o escritorio.", "texto")
        nota.set_line_wrap(True)
        caja.pack_start(nota, False, False, 0)

        filas = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        if not self.lista:
            filas.pack_start(etiqueta("No hay ninguna ventana abierta.", "vacio"), False, False, 0)
        for v in self.lista:
            b = Gtk.Button()
            b.get_style_context().add_class("fila")
            fila = Gtk.Box(spacing=12)
            fila.pack_start(icono_de(v["clase"]), False, False, 0)
            textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            t = etiqueta(v["titulo"] or v["clase"], "titulo-ventana")
            t.set_ellipsize(Pango.EllipsizeMode.END)
            t.set_max_width_chars(48)
            textos.pack_start(t, False, False, 0)
            textos.pack_start(etiqueta("%s · escritorio %s" % (v["clase"], v["escritorio"]),
                                       "detalle-ventana"), False, False, 0)
            fila.pack_start(textos, True, True, 0)
            b.add(fila)
            b.connect("clicked", lambda _b, d=v["direccion"]: self.terminar(
                eleccion("--ventana", self.sonido, d)))
            filas.pack_start(b, False, False, 0)

        rodillo = Gtk.ScrolledWindow()
        rodillo.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        # Una capa toma el alto MINIMO de lo que lleva, y el de un
        # ScrolledWindow es casi cero: se le da a mano (lib/panel_capa.py).
        rodillo.set_min_content_height(min(360, max(60, 54 * len(self.lista))))
        rodillo.add(filas)
        caja.pack_start(rodillo, True, True, 0)

        pie = Gtk.Box(spacing=6)
        pie.set_margin_top(4)
        atras = base.boton("Atrás", "Esc", False)
        atras.connect("clicked", lambda *_: self.pila.set_visible_child_name("inicio"))
        pie.pack_end(atras, False, False, 0)
        caja.pack_start(pie, False, False, 0)
        return caja

    # -- Acciones --
    def elegir(self, arg):
        if arg == "--ventana":
            self.pila.set_visible_child_name("ventanas")
        else:
            self.terminar(eleccion(arg, self.sonido))

    def tecla(self, _w, evento):
        k = evento.keyval
        en_inicio = self.pila.get_visible_child_name() == "inicio"
        if k == Gdk.KEY_Escape:
            if en_inicio:
                self.terminar(None)
            else:
                self.pila.set_visible_child_name("inicio")
            return True
        if en_inicio:
            for tecla, _g, _n, arg in OPCIONES:
                if k in (Gdk.keyval_from_name(tecla), Gdk.keyval_from_name("KP_" + tecla)):
                    self.elegir(arg)
                    return True
            if k in (Gdk.KEY_s, Gdk.KEY_S):
                self.interruptor.set_active(not self.interruptor.get_active())
                return True
        return False

    def terminar(self, respuesta):
        self.respuesta = respuesta
        self.ventana.destroy()


def a_png(ruta, pagina):
    """La tarjeta dibujada a un fichero, sin mapear ninguna superficie: asi se
    mira su aspecto con la sesion ocupada."""
    if not Gtk.init_check(sys.argv)[0]:
        return 1
    base.cargar_estilo(ESTILO_EXTRA)
    ventana = Gtk.OffscreenWindow()
    t = Tarjeta(ventana, grabacion.ventanas())
    ventana.show_all()
    t.pila.set_visible_child_name(pagina)
    while Gtk.events_pending():
        Gtk.main_iteration()
    GLib.timeout_add(400, Gtk.main_quit)
    Gtk.main()
    ventana.get_pixbuf().savev(ruta, "png", [], [])
    return 0


def main(argv):
    if argv[:1] == ["--png"] and len(argv) >= 2:
        if not base.solo_wayland():
            return 1
        return a_png(argv[1], "ventanas" if "--ventanas" in argv else "inicio")
    if not base.solo_wayland() or not Gtk.init_check(sys.argv)[0]:
        return 1
    base.cargar_estilo(ESTILO_EXTRA)

    ventana = Gtk.Window()
    GtkLayerShell.init_for_window(ventana)
    GtkLayerShell.set_namespace(ventana, "grabar-tarjeta")
    GtkLayerShell.set_layer(ventana, GtkLayerShell.Layer.OVERLAY)
    GtkLayerShell.set_keyboard_mode(ventana, GtkLayerShell.KeyboardMode.EXCLUSIVE)
    ventana.set_app_paintable(True)
    if ventana.get_screen().get_rgba_visual():
        ventana.set_visual(ventana.get_screen().get_rgba_visual())

    t = Tarjeta(ventana, grabacion.ventanas())
    ventana.connect("key-press-event", t.tecla)
    ventana.connect("destroy", Gtk.main_quit)
    ventana.show_all()
    Gtk.main()

    if not t.respuesta:
        return 1
    # La tarjeta ya no esta, pero el compositor tiene que enterarse antes de que
    # empiece a grabar la pantalla completa: si no, sale en el primer fotograma.
    while Gtk.events_pending():
        Gtk.main_iteration()
    print(t.respuesta, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
