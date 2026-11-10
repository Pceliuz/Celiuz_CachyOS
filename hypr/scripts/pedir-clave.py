#!/usr/bin/env python3
"""
hypr/scripts/pedir-clave.py — la contraseña para sudo, en una tarjeta.

    SUDO_ASKPASS=pedir-clave.py sudo -A ...   (asi lo usa instalar.sh)
    pedir-clave.py --png RUTA                  la tarjeta a un fichero, sin ventana

Es un «askpass» de sudo: sudo lo ejecuta, y lo que este imprima es la
contraseña. Si se cancela (Esc, «Ahora no») sale con 1 sin imprimir nada, y
sudo no ejecuta la orden.

POR QUE EXISTE (2026-11-05). La pantalla de inicio (SDDM) va en /usr/share y
pide root. Cuando `./instalar.sh` se lanzaba desde algo que no es una terminal
—Claude Code, que es como se instala este repo en un equipo nuevo— sudo no
tenia donde preguntar, el paso del SDDM se quedaba fuera y habia que acordarse
de pedirlo aparte. Ahora instalar.sh, sin terminal pero con sesion grafica,
pregunta aqui.

Lo que dice la tarjeta lo pone quien llama en CELIUZ_CLAVE_MOTIVO. La
contraseña no se guarda en ningun sitio: va de la casilla a la salida estandar,
que es una tuberia que solo lee sudo.

Si la contraseña esta mal, sudo vuelve a llamar a este programa (hasta tres
veces) sin decirle nada. Se nota porque el que llama, sudo, es el MISMO
proceso: se apunta su pid en $XDG_RUNTIME_DIR y la segunda vez la tarjeta dice
que no era esa.
"""

import importlib.util
import os
import sys

AQUI = os.path.dirname(os.path.realpath(__file__))
MOTIVO_FABRICA = "Hace falta tu contraseña para instalar algo del sistema."


def cargar_base():
    """La tarjeta del modo gaming: misma cara que las demas preguntas."""
    spec = importlib.util.spec_from_file_location(
        "tarjeta_base", os.path.join(AQUI, "modo-gaming-tarjeta.py"))
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    return base


def marca_reintento():
    """True si este mismo sudo ya nos llamo (la contraseña de antes fallo)."""
    runtime = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    # Las de sudos que ya terminaron no le sirven a nadie.
    try:
        for nombre in os.listdir(runtime):
            if nombre.startswith("celiuz-clave.") and not os.path.exists(
                    "/proc/" + nombre.split(".", 1)[1]):
                os.unlink(os.path.join(runtime, nombre))
    except OSError:
        pass
    ruta = os.path.join(runtime, "celiuz-clave.%d" % os.getppid())
    repetida = os.path.exists(ruta)
    try:
        with open(ruta, "w", encoding="utf-8"):
            pass
    except OSError:
        pass
    return repetida


def construir(base, motivo, reintento, terminar):
    Gtk = base.Gtk
    base.cargar_estilo("""
        entry { font-size: 16px; padding: 10px 14px; border-radius: 12px;
                border: 1px solid alpha(@amatista, 0.45); background: alpha(@abismo, 0.8);
                color: @luz; caret-color: @neon; box-shadow: none; }
        entry:focus { border-color: @neon; }
        .error { color: @atencion; font-size: 13px; font-weight: 700; }
    """)
    caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    caja.get_style_context().add_class("tarjeta")
    caja.set_size_request(480, -1)
    for texto, clase in (("◆  CONTRASEÑA", "marca"),
                         ("Hace falta tu contraseña", "titulo"),
                         (motivo, "texto")):
        etiqueta = Gtk.Label(label=texto, xalign=0)
        etiqueta.set_line_wrap(True)
        etiqueta.set_max_width_chars(46)
        etiqueta.get_style_context().add_class(clase)
        caja.pack_start(etiqueta, False, False, 0)

    casilla = Gtk.Entry()
    casilla.set_visibility(False)
    casilla.set_placeholder_text("la de tu usuario (la de sudo)")
    casilla.set_margin_top(10)
    caja.pack_start(casilla, False, False, 0)
    if reintento:
        error = Gtk.Label(label="No era esa. Prueba otra vez.", xalign=0)
        error.get_style_context().add_class("error")
        caja.pack_start(error, False, False, 0)

    botones = Gtk.Box(spacing=12)
    botones.set_margin_top(14)
    no = base.boton("Ahora no", "Esc", False)
    si = base.boton("Seguir", "Intro", True)
    no.connect("clicked", lambda _b: terminar(None))
    si.connect("clicked", lambda _b: terminar(casilla.get_text()))
    casilla.connect("activate", lambda _e: terminar(casilla.get_text()))
    botones.pack_end(si, False, False, 0)
    botones.pack_end(no, False, False, 0)
    caja.pack_start(botones, False, False, 0)
    return caja, casilla


def png(ruta):
    """La tarjeta dibujada a un fichero (para la guia), sin abrir ventana."""
    base = cargar_base()
    Gtk = base.Gtk
    if not Gtk.init_check(sys.argv)[0]:
        return 1
    motivo = os.environ.get("CELIUZ_CLAVE_MOTIVO") or MOTIVO_FABRICA
    caja, casilla = construir(base, motivo, False, lambda _v: None)
    casilla.set_text("contraseña")
    ventana = Gtk.OffscreenWindow()
    marco = Gtk.EventBox()
    marco.get_style_context().add_class("fondo-png")
    caja.set_margin_start(30)
    caja.set_margin_end(30)
    caja.set_margin_top(30)
    caja.set_margin_bottom(30)
    marco.add(caja)
    ventana.add(marco)
    ventana.show_all()
    casilla.select_region(0, 0)
    while Gtk.events_pending():
        Gtk.main_iteration()
    ventana.get_pixbuf().savev(ruta, "png", [], [])
    return 0


def main(argv):
    if argv[:1] == ["--png"] and len(argv) == 2:
        return png(argv[1])
    base = cargar_base()
    Gtk, Gdk, GtkLayerShell = base.Gtk, base.Gdk, base.GtkLayerShell
    if not base.solo_wayland() or not Gtk.init_check(sys.argv)[0]:
        return 1
    respuesta = {"valor": None}
    ventana = Gtk.Window()

    def terminar(valor):
        respuesta["valor"] = valor
        ventana.destroy()

    caja, casilla = construir(base, os.environ.get("CELIUZ_CLAVE_MOTIVO") or MOTIVO_FABRICA,
                              marca_reintento(), terminar)
    GtkLayerShell.init_for_window(ventana)
    GtkLayerShell.set_namespace(ventana, "pedir-clave")
    GtkLayerShell.set_layer(ventana, GtkLayerShell.Layer.OVERLAY)
    # En exclusiva: lo que teclees va a la casilla y a nada mas.
    GtkLayerShell.set_keyboard_mode(ventana, GtkLayerShell.KeyboardMode.EXCLUSIVE)
    ventana.set_app_paintable(True)
    if ventana.get_screen().get_rgba_visual():
        ventana.set_visual(ventana.get_screen().get_rgba_visual())
    ventana.add(caja)
    ventana.connect("key-press-event",
                    lambda _w, e: terminar(None) if e.keyval == Gdk.KEY_Escape else False)
    ventana.connect("destroy", Gtk.main_quit)
    ventana.show_all()
    casilla.grab_focus()
    Gtk.main()
    if respuesta["valor"] is None:
        return 1
    sys.stdout.write(respuesta["valor"] + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
