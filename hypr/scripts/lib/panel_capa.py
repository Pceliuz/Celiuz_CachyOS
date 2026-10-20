#!/usr/bin/env python3
"""
hypr/scripts/lib/panel_capa.py — lo comun de los paneles que cuelgan de la
barra al pinchar un icono (bluetooth-panel.py, wifi-panel.py).

Es una capa de Wayland (gtk-layer-shell), como el panel de calendario: queda
bajo la barra, encima de las apps, y Hyprland no la cuenta como ventana. Lo que
da esta base, y por que cada cosa:

  - Cuelga del icono: se centra bajo el PUNTERO, en la pantalla donde este (con
    el televisor enchufado la barra existe en las dos). A GTK no se le puede
    preguntar el puntero en Wayland; se le pregunta a Hyprland.
  - Cabecera (glifo, titulo, linea de estado, interruptor), un cuerpo que se
    rehace entero en cada repintado, y un pie.
  - El alto del cuerpo se fija a mano: una capa toma el alto MINIMO de lo que
    lleva, y el de un ScrolledWindow es casi cero (la lista salia aplastada).
  - Se cierra con Escape, con otro clic en el icono (`lanzar` hace de
    interruptor) o con el puntero un rato lejos. No por foco: Hyprland tiene
    focus_follows_mouse y el foco se pierde con solo rozar otra ventana. Y no
    mientras `ocupado()`: cerrar a medio emparejar o conectar lo cortaria.
  - Mientras esta abierto, la barra no se esconde (`hold`/`release` por su
    FIFO): si no, el panel colgaria de nada.

Importarlo pide GTK 3 y gtk-layer-shell: quien lo use lo importa DENTRO de una
funcion y con un try, para poder decir que falta en vez de no hacer nada.
"""

import os
import signal
import socket
import time

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GLib, Gtk, GtkLayerShell, Pango  # noqa: E402

import canales  # noqa: E402
import dibujo  # noqa: E402
from panel_estilo import (ALTO_BARRA, ANCHO, CIERRE_DELAY, MARGEN_BORDE,  # noqa: E402
                          SOMBRA, css_base)

G_GIRO = "\U000F0450"
solo_wayland = dibujo.solo_wayland


def cursor_pos():
    """(x, y) del puntero en coordenadas globales, segun Hyprland; None si no
    se sabe."""
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not sig:
        return None
    runtime = os.environ.get("XDG_RUNTIME_DIR") or "/run/user/%d" % os.getuid()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect(os.path.join(runtime, "hypr", sig, ".socket.sock"))
            s.sendall(b"cursorpos")
            x, y = s.recv(256).decode(errors="replace").strip().split(",")
        return int(x), int(y)
    except (OSError, ValueError):
        return None


def avisar_barra(orden):
    try:
        fd = os.open(canales.canal_barras(), os.O_WRONLY | os.O_NONBLOCK)
        try:
            os.write(fd, (orden + "\n").encode())
        finally:
            os.close(fd)
    except OSError:
        pass   # sin demonio de barras (lanzada a mano) el panel va igual


def etiqueta(texto="", clases=(), nombre=None, xalign=0.0):
    e = Gtk.Label(label=texto, xalign=xalign)
    if nombre:
        e.set_name(nombre)
    for c in clases:
        e.get_style_context().add_class(c)
    return e


def boton(texto, al_pulsar, clases=()):
    b = Gtk.Button(label=texto)
    b.set_valign(Gtk.Align.CENTER)
    b.set_relief(Gtk.ReliefStyle.NONE)
    b.set_can_focus(False)
    for c in clases:
        b.get_style_context().add_class(c)
    b.connect("clicked", lambda *_: al_pulsar())
    return b


def caja(vertical=False, espacio=0):
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical
                   else Gtk.Orientation.HORIZONTAL, spacing=espacio)


class PanelCapa(Gtk.Window):
    """La base. La subclase llena `self.pie` en su __init__ (tras llamar a
    este) y el cuerpo en cada repintado, con vaciar_cuerpo() + seccion() /
    vacio() / self.cuerpo.pack_start(...) + terminar_cuerpo()."""

    def __init__(self, namespace, glifo, titulo, extra_css="", ancho=ANCHO, esqueleto=True):
        """Con `esqueleto=False` no hay cabecera, lista ni pie: solo
        `self.marco`, para un panel con su propia forma (el del reloj)."""
        super().__init__()
        self.ancho = ancho
        self._fuera_desde = None
        self._estado_id = None
        self._ignorar = False

        pantalla = self.get_screen()
        visual = pantalla.get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)
        self.set_app_paintable(True)
        prov = Gtk.CssProvider()
        prov.load_from_data((css_base(dibujo.C, dibujo.FUENTE) + extra_css).encode())
        Gtk.StyleContext.add_provider_for_screen(
            pantalla, prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self._montar_capa(namespace)
        if esqueleto:
            self._esqueleto(glifo, titulo)
        else:
            self.marco = caja(vertical=True)
            self.marco.set_name("marco")
            self.marco.set_size_request(ancho, -1)
            self.add(self.marco)
        self.connect("key-press-event", self._tecla)
        GLib.timeout_add(200, self._vigilar_puntero)

    # --- Donde va -----------------------------------------------------------

    def _montar_capa(self, namespace):
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, namespace)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        # ON_DEMAND: coge el teclado al pinchar (Escape, escribir) pero no se
        # lo quita a la app que estabas usando solo por aparecer.
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)
        pos = cursor_pos()
        display = Gdk.Display.get_default()
        monitor = (display.get_monitor_at_point(*pos) if pos else None) \
            or display.get_primary_monitor() or display.get_monitor(0)
        geo = monitor.get_geometry()
        GtkLayerShell.set_monitor(self, monitor)
        self.mon = geo
        ancho = self.ancho + 2 * SOMBRA
        x = (pos[0] - geo.x) if pos else geo.width // 2
        self.izq = max(MARGEN_BORDE - SOMBRA,
                       min(x - ancho // 2, geo.width - ancho - MARGEN_BORDE + SOMBRA))
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.LEFT, self.izq)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, ALTO_BARRA - 4)
        self.set_size_request(ancho, -1)

    # --- El esqueleto ---------------------------------------------------------

    def _esqueleto(self, glifo, titulo):
        marco = caja(vertical=True)
        marco.set_name("marco")
        marco.set_size_request(self.ancho, -1)
        self.add(marco)

        self.marco = marco
        cab = self._cab = caja(espacio=10)
        self.glifo_cab = etiqueta(glifo, nombre="glifo-cab")
        textos = caja(vertical=True)
        textos.pack_start(etiqueta(titulo, nombre="titulo"), False, False, 0)
        self.sub = etiqueta(nombre="sub")
        textos.pack_start(self.sub, False, False, 0)
        self.interruptor = Gtk.Switch()
        self.interruptor.set_valign(Gtk.Align.CENTER)
        self.interruptor.set_can_focus(False)
        self.interruptor.connect("notify::active", self._al_interruptor)
        cab.pack_start(self.glifo_cab, False, False, 0)
        cab.pack_start(textos, True, True, 0)
        cab.pack_end(self.interruptor, False, False, 0)
        marco.pack_start(cab, False, False, 0)
        marco.pack_start(self.raya(), False, False, 10)

        self.cuerpo = caja(vertical=True)
        self.rollo = Gtk.ScrolledWindow()
        self.rollo.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.rollo.add(self.cuerpo)
        marco.pack_start(self.rollo, True, True, 0)

        marco.pack_start(self.raya(), False, False, 10)
        self.pie = caja(vertical=True, espacio=8)
        marco.pack_start(self.pie, False, False, 0)
        self.estado = etiqueta(nombre="estado")
        self.estado.set_line_wrap(True)
        self.estado.set_no_show_all(True)
        self.estado.set_margin_top(8)
        marco.pack_start(self.estado, False, False, 0)

    def raya(self):
        r = Gtk.Box()
        r.set_name("raya")
        return r

    def opcion(self, texto, ayuda, al_cambiar):
        """Un interruptor del pie. `al_cambiar(activo)` solo cuando lo mueve
        quien usa el panel, no cuando lo pone el repintado."""
        fila = caja(espacio=10)
        textos = caja(vertical=True)
        textos.pack_start(etiqueta(texto, nombre="opcion"), False, False, 0)
        textos.pack_start(etiqueta(ayuda, ("tenue",)), False, False, 0)
        sw = Gtk.Switch()
        sw.set_valign(Gtk.Align.CENTER)
        sw.set_can_focus(False)
        sw.connect("notify::active",
                   lambda s, _p: None if self._ignorar else al_cambiar(s.get_active()))
        fila.pack_start(textos, True, True, 0)
        fila.pack_end(sw, False, False, 0)
        self.pie.pack_start(fila, False, False, 0)
        return sw

    def poner(self, interruptor, activo, sensible=True):
        """Mueve un interruptor sin que cuente como si lo hubieras movido tu."""
        self._ignorar = True
        interruptor.set_active(activo)
        interruptor.set_sensitive(sensible)
        self._ignorar = False

    def cabecera(self, glifo, sub, apagado=False):
        self.glifo_cab.set_text(glifo)
        ctx = self.glifo_cab.get_style_context()
        (ctx.add_class if apagado else ctx.remove_class)("apagado")
        self.sub.set_text(sub)

    # --- El cuerpo --------------------------------------------------------------

    def vaciar_cuerpo(self):
        for hijo in self.cuerpo.get_children():
            self.cuerpo.remove(hijo)

    def seccion(self, texto, buscando=False):
        c = caja()
        c.pack_start(etiqueta(texto.upper(), ("seccion",)), True, True, 0)
        if buscando:
            c.pack_end(etiqueta(G_GIRO + " BUSCANDO…", ("buscando",)), False, False, 0)
        c.set_margin_top(12 if self.cuerpo.get_children() else 0)
        c.set_margin_bottom(6)
        self.cuerpo.pack_start(c, False, False, 0)

    def vacio(self, texto):
        e = etiqueta(texto, nombre="vacio")
        e.set_line_wrap(True)
        self.cuerpo.pack_start(e, False, False, 0)

    def _alto_libre(self):
        """Lo que le queda a la lista: la pantalla menos la barra, la cabecera,
        el pie y los margenes. Medido, no una cifra fija: el pie de cada panel
        mide distinto (con una cifra fija la lista del Wi-Fi salia cortada)."""
        resto = sum(w.get_preferred_height_for_width(self.ancho - 28)[1]
                    for w in (self._cab, self.pie))
        if self.estado.get_visible():
            resto += self.estado.get_preferred_height_for_width(self.ancho - 28)[1] + 8
        resto += 2 * 14 + 2 * 21 + 2 * SOMBRA + 2   # relleno, rayas, halo, borde
        return max(160, self.mon.height - (ALTO_BARRA - 4) - resto - MARGEN_BORDE)

    def terminar_cuerpo(self, ver=None):
        """Fija el alto de la lista. Con `ver`, la desplaza para que ese
        widget quede a la vista (el que estas usando: tras repintar, la lista
        volveria arriba y lo dejaria fuera)."""
        self.cuerpo.show_all()
        _minimo, natural = self.cuerpo.get_preferred_height_for_width(self.ancho - 28)
        alto = min(natural, self._alto_libre())
        # En este orden: GTK no admite un minimo mayor que el maximo vigente.
        self.rollo.set_max_content_height(-1)
        self.rollo.set_min_content_height(alto)
        self.rollo.set_max_content_height(alto)
        # Que la capa encoja si ahora hay menos: pide el minimo y GTK la deja
        # en lo que ocupe de verdad.
        self.resize(self.ancho + 2 * SOMBRA, 1)
        if ver is not None and natural > alto:
            def mostrar():
                coords = ver.translate_coordinates(self.cuerpo, 0, 0)
                if coords:
                    ajuste = self.rollo.get_vadjustment()
                    abajo = coords[1] + ver.get_allocated_height()
                    if abajo > ajuste.get_value() + alto:
                        ajuste.set_value(min(abajo - alto + 8, ajuste.get_upper()))
                return False
            GLib.idle_add(mostrar)

    # --- La linea de estado de abajo ------------------------------------------

    def avisar(self, texto, error=False, fijo=False):
        ctx = self.estado.get_style_context()
        (ctx.add_class if error else ctx.remove_class)("error")
        self.estado.set_text(texto)
        self.estado.show()
        if self._estado_id:
            GLib.source_remove(self._estado_id)
            self._estado_id = None
        if not fijo:
            def borrar():
                self._estado_id = None
                self.estado.hide()
                return False
            self._estado_id = GLib.timeout_add_seconds(8, borrar)

    # --- Lo que la subclase puede cambiar -------------------------------------

    def al_interruptor(self, activo):
        """El interruptor de la cabecera."""

    def ocupado(self):
        """True mientras haya algo a medias: entonces no se cierra solo."""
        return False

    def al_escape(self):
        self.close()

    def al_cerrar(self):
        """Lo que haya que soltar al salir (una busqueda, un agente...)."""

    # --- Cerrarse ---------------------------------------------------------------

    def _al_interruptor(self, sw, _p):
        if not self._ignorar:
            self.al_interruptor(sw.get_active())

    def _vigilar_puntero(self):
        pos = cursor_pos()
        if pos is None or self.ocupado():
            self._fuera_desde = None
            return True
        x, y = pos[0] - self.mon.x, pos[1] - self.mon.y
        ancho = self.ancho + 2 * SOMBRA
        dentro = (self.izq <= x <= self.izq + ancho and
                  0 <= y <= ALTO_BARRA + self.get_allocated_height())
        if dentro or (0 <= x <= self.mon.width and y < ALTO_BARRA):
            self._fuera_desde = None
        else:
            ahora = time.monotonic()
            if self._fuera_desde is None:
                self._fuera_desde = ahora
            elif ahora - self._fuera_desde >= CIERRE_DELAY:
                self.close()
                return False
        return True

    def _tecla(self, _w, ev):
        if Gdk.keyval_name(ev.keyval) == "Escape":
            self.al_escape()
            return True
        return False


def _ruta_pid(nombre):
    return canales.canal(nombre, "pid")


# Los paneles de la barra se excluyen: abrir uno cierra los demas.
PANELES = ("bluetooth-panel", "wifi-panel", "calendar-panel")


def _pid_de(nombre):
    """El pid del panel `nombre` si esta abierto, o None. Se mira que el pid
    sea de verdad ese script: un .pid viejo puede apuntar a otro proceso que
    heredo el numero, y a ese no hay que mandarle nada."""
    try:
        with open(_ruta_pid(nombre)) as f:
            pid = int(f.read().strip())
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            if (nombre + ".py").encode() in f.read():
                return pid
    except (OSError, ValueError):
        pass
    return None


def _ya_abierto_lo_cierro(nombre):
    pid = _pid_de(nombre)
    if pid is None:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return False
    return True


def _cerrar_los_otros(nombre, espera=1.5):
    """Cierra los demas paneles y espera a que salgan. Esperar importa: al
    salir mandan `release` a la barra, y si llegara despues del `hold` de este
    la barra se esconderia con el panel abierto."""
    pids = []
    for otro in PANELES:
        if otro != nombre:
            pid = _pid_de(otro)
            if pid is not None:
                try:
                    os.kill(pid, signal.SIGTERM)
                    pids.append(pid)
                except OSError:
                    pass
    limite = time.monotonic() + espera
    while pids and time.monotonic() < limite:
        pids = [p for p in pids if os.path.exists("/proc/%d" % p)]
        if pids:
            time.sleep(0.03)


def lanzar(nombre, crear):
    """Abre el panel, o lo cierra si ya estaba abierto (el clic del icono).
    `crear()` devuelve la ventana, o None si no se puede (ya avisado)."""
    if _ya_abierto_lo_cierro(nombre):
        return 0
    _cerrar_los_otros(nombre)
    ventana = crear()
    if ventana is None:
        return 1
    with open(_ruta_pid(nombre), "w") as f:
        f.write(str(os.getpid()))
    avisar_barra("hold")

    def salir(*_):
        try:
            ventana.al_cerrar()
        finally:
            avisar_barra("release")
            try:
                os.remove(_ruta_pid(nombre))
            except OSError:
                pass
            Gtk.main_quit()
        return False

    ventana.connect("destroy", salir)
    # GLib.unix_signal_add esta obsoleto desde GLib 2.80 (avisa por stderr); el
    # sustituto vive en GLibUnix, que un GLib mas viejo no tiene.
    try:
        gi.require_version("GLibUnix", "2.0")
        from gi.repository import GLibUnix
        anadir_senal = GLibUnix.signal_add
    except (ImportError, ValueError):
        anadir_senal = GLib.unix_signal_add
    for sen in (signal.SIGTERM, signal.SIGINT):
        anadir_senal(GLib.PRIORITY_HIGH, sen, lambda *_: ventana.close() or False)
    ventana.show_all()
    Gtk.main()
    return 0


__all__ = ["Gdk", "GLib", "Gtk", "Pango", "PanelCapa", "boton", "caja", "etiqueta",
           "lanzar", "solo_wayland", "cursor_pos"]
