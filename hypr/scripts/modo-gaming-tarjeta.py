#!/usr/bin/env python3
"""
hypr/scripts/modo-gaming-tarjeta.py — la pregunta antes de entrar o salir del
modo gaming.

    modo-gaming-tarjeta.py entrar|salir|bloqueado ["aviso en ambar"]

Sale con 0 SOLO si se acepto (Enter, A en el mando o clic en el boton). Esc, clic en cancelar
o dejar pasar CUENTA segundos sale con 1. Es a proposito asimetrico: el modo
cierra ventanas, y un atajo rozado jugando o trabajando no puede hacer nada sin
que lo digas.

Es una capa OVERLAY: se dibuja por encima de todo, tambien de un juego a
pantalla completa, y coge el teclado en exclusiva mientras esta.
"""

import os
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gdk, GLib, Gtk, GtkLayerShell  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib"))
import mando  # noqa: E402
COLORES = os.path.join(RAIZ, "waybar", "colores.css")

CUENTA = 5.0   # segundos hasta rendirse sola, sin hacer nada

TEXTOS = {
    "entrar": ("¿Entrar al modo gaming?",
               "Se cierran las apps abiertas y se apagan el fondo, las barras "
               "y los efectos.",
               "Entrar"),
    "salir": ("¿Salir del modo gaming?",
              "Vuelven el fondo, las barras y los efectos.",
              "Salir"),
    # Con un juego abierto no se sale: solo se avisa (y sale siempre con 1).
    "bloqueado": ("Tienes un juego abierto",
                  "Guarda la partida y cierra el juego antes de salir del modo gaming.",
                  None),
}

ESTILO = """
* { font-family: "MesloLGS Nerd Font Propo", sans-serif; }
window { background: transparent; }
.tarjeta {
    background: alpha(@superficie, 0.96);
    border: 1px solid alpha(@neon, 0.45);
    border-radius: 18px;
    padding: 30px 38px 22px 38px;
    box-shadow: 0 0 40px alpha(@violeta, 0.45);
}
.marca { color: @neon; font-weight: 800; letter-spacing: 6px; font-size: 12px; }
.titulo { color: @luz; font-weight: 800; font-size: 24px; }
.texto { color: @tenue; font-size: 14px; }
.aviso { color: @atencion; font-size: 14px; font-weight: 700; }
.boton {
    border-radius: 12px; padding: 10px 26px; font-weight: 700; font-size: 15px;
    border: 1px solid alpha(@amatista, 0.30); background: alpha(@apagado, 0.7);
    color: @luz; box-shadow: none; text-shadow: none;
}
.boton.si {
    background: linear-gradient(135deg, #8b2cff, @violeta);
    border-color: alpha(@neon, 0.7); color: white;
    box-shadow: 0 0 22px alpha(@violeta, 0.7);
}
.tecla {
    font-size: 11px; color: @tenue; border: 1px solid @apagado; border-radius: 5px;
    padding: 1px 6px; margin-left: 8px; background: alpha(@abismo, 0.6);
}
.boton.si .tecla { color: @luz; border-color: alpha(@luz, 0.4); background: alpha(@abismo, 0.25); }
progressbar trough { min-height: 3px; background: alpha(@apagado, 0.6); border-radius: 2px; border: none; }
progressbar progress { min-height: 3px; background: @neon; border-radius: 2px; border: none; }
"""


def boton(texto, tecla, principal):
    b = Gtk.Button()
    caja = Gtk.Box(spacing=0)
    caja.pack_start(Gtk.Label(label=texto), False, False, 0)
    t = Gtk.Label(label=tecla)
    t.get_style_context().add_class("tecla")
    caja.pack_start(t, False, False, 0)
    b.add(caja)
    b.get_style_context().add_class("boton")
    if principal:
        b.get_style_context().add_class("si")
    return b


class Tarjeta(Gtk.Window):
    def __init__(self, accion, aviso):
        super().__init__()
        self.respuesta = 1
        titulo, texto, si = TEXTOS[accion]

        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, "modo-gaming-tarjeta")
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        self.set_app_paintable(True)
        pantalla = self.get_screen()
        if pantalla.get_rgba_visual():
            self.set_visual(pantalla.get_rgba_visual())

        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        caja.get_style_context().add_class("tarjeta")
        caja.set_size_request(460, -1)

        for texto_, clase in (("◆  MODO GAMING", "marca"), (titulo, "titulo"), (texto, "texto")):
            etiqueta = Gtk.Label(label=texto_, xalign=0)
            etiqueta.set_line_wrap(True)
            etiqueta.set_max_width_chars(44)
            etiqueta.get_style_context().add_class(clase)
            caja.pack_start(etiqueta, False, False, 0)
        if aviso:
            etiqueta = Gtk.Label(label=aviso, xalign=0)
            etiqueta.set_line_wrap(True)
            etiqueta.get_style_context().add_class("aviso")
            caja.pack_start(etiqueta, False, False, 0)

        botones = Gtk.Box(spacing=12)
        botones.set_margin_top(14)
        self.solo_aviso = si is None
        if self.solo_aviso:
            ok = boton("Entendido", "Enter", True)
            ok.connect("clicked", lambda *_: self.terminar(1))
            botones.pack_end(ok, False, False, 0)
        else:
            no = boton("Cancelar", "Esc", False)
            no.connect("clicked", lambda *_: self.terminar(1))
            ok = boton(si, "Enter", True)
            ok.connect("clicked", lambda *_: self.terminar(0))
            botones.pack_end(ok, False, False, 0)
            botones.pack_end(no, False, False, 0)
        caja.pack_start(botones, False, False, 0)

        self.barra = Gtk.ProgressBar()
        self.barra.set_fraction(1.0)
        self.barra.set_margin_top(12)
        caja.pack_start(self.barra, False, False, 0)

        self.add(caja)
        self.connect("key-press-event", self.tecla)
        # Con mando tambien: A acepta, B cancela. La tarjeta coge el teclado en
        # exclusiva mientras vive, asi que cualquier pulsacion es para ella.
        self.mando = mando.Mando(self.boton).empezar()
        self.connect("destroy", Gtk.main_quit)
        self.inicio = GLib.get_monotonic_time()
        GLib.timeout_add(40, self.contar)

    def tecla(self, _w, evento):
        if evento.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.terminar(1 if self.solo_aviso else 0)
        elif evento.keyval == Gdk.KEY_Escape:
            self.terminar(1)
        return True

    def boton(self, accion):
        if accion in ("aceptar", "start"):
            self.terminar(1 if self.solo_aviso else 0)
        elif accion in ("atras", "select"):
            self.terminar(1)

    def contar(self):
        pasado = (GLib.get_monotonic_time() - self.inicio) / 1e6
        self.barra.set_fraction(max(0.0, 1.0 - pasado / CUENTA))
        if pasado >= CUENTA:
            self.terminar(1)
            return False
        return True

    def terminar(self, respuesta):
        self.respuesta = respuesta
        self.destroy()


def solo_wayland():
    """Solo en una sesion Wayland, y sin caer nunca a X11: sin WAYLAND_DISPLAY
    GTK probaria DISPLAY y se dibujaria por XWayland donde no toca (asi abrio
    la prueba del modo gaming tres bibliotecas en la sesion real)."""
    if not os.environ.get("WAYLAND_DISPLAY"):
        return False
    os.environ["GDK_BACKEND"] = "wayland"
    return True


def main(argv):
    if not argv or argv[0] not in TEXTOS:
        print("uso: modo-gaming-tarjeta.py entrar|salir|bloqueado [aviso]", file=sys.stderr)
        return 2
    if not solo_wayland() or not Gtk.init_check(sys.argv)[0]:
        return 1
    css = Gtk.CssProvider()
    try:
        with open(COLORES, encoding="utf-8") as fh:
            colores = fh.read()
    except OSError:
        # Sin la paleta generada (un equipo a medio instalar) la tarjeta se
        # sigue dibujando: la pregunta importa mas que el color.
        colores = ("@define-color abismo #0d0418; @define-color superficie #1a0830;"
                   "@define-color apagado #2d1b4e; @define-color violeta #6a00f4;"
                   "@define-color amatista #b16cff; @define-color neon #c77dff;"
                   "@define-color luz #e4c7ff; @define-color tenue #8a7aa8;"
                   "@define-color atencion #f6c177;")
    css.load_from_data((colores + ESTILO).encode())
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css,
                                             Gtk.STYLE_PROVIDER_PRIORITY_USER)
    tarjeta = Tarjeta(argv[0], argv[1] if len(argv) > 1 else "")
    tarjeta.show_all()
    Gtk.main()
    return tarjeta.respuesta


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
