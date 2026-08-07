#!/usr/bin/env python3
"""
~/dotfiles/hypr/scripts/calendar-panel.py

El panel de calendario que cuelga de la barra al hacer click en el reloj.

No es una ventana normal: es una capa de Wayland (gtk-layer-shell), la misma
tecnica con la que waybar se pega al borde de la pantalla. Eso significa que
queda anclada al borde superior por debajo de la barra, encima de las apps, y
que Hyprland no la cuenta como ventana — no rompe el mosaico ni roba sitio.

Muestra tres cosas a la vez sobre cada dia:
  - los feriados y celebraciones del Peru (lib/pe_fechas.py, sin red),
  - tus eventos de Google Calendar (lib/gcal.py, desde el cache local),
  - y el detalle de lo que caiga en el dia que selecciones.

Se comporta como un boton: correrlo otra vez mientras esta abierto lo cierra.
Es lo que hace el click en el reloj de waybar.
"""

import datetime as dt
import os
import signal
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import canales  # noqa: E402

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, Gdk, GLib, GtkLayerShell  # noqa: E402

import pe_fechas  # noqa: E402
import gcal  # noqa: E402

# Alto de la barra (config.jsonc). El panel arranca justo debajo.
ALTO_BARRA = 38
ANCHO_PANEL = 340
# Margen minimo al filo de la pantalla cuando el panel se coloca bajo el reloj.
MARGEN_BORDE = 8
# Si el cache de Google es mas viejo que esto, se refresca al abrir el panel.
CACHE_VIEJO = 300  # 5 minutos
# Segundos con el puntero lejos del panel antes de que se cierre solo.
CIERRE_DELAY = 2.5

RUNTIME = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
PID_PATH = os.path.join(RUNTIME, "calendar-panel.pid")
# El FIFO del demonio de la barra: mientras el panel este abierto le pedimos
# que no se esconda, o el panel quedaria colgando de una barra invisible.
# Con la firma de la sesion; ver lib/canales.py.
FIFO_BARRA = canales.canal_barras()

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "setiembre", "octubre", "noviembre", "diciembre"]
DIAS_CORTOS = ["L", "M", "M", "J", "V", "S", "D"]

CSS = b"""
window {
    background-color: rgba(20, 8, 38, 0.97);
    border: 1px solid #b16cff;
    /* Sin esquinas arriba: asi se lee como una prolongacion de la barra y no
     * como una ventana suelta que casualmente esta cerca. */
    border-top: none;
    border-radius: 0 0 10px 10px;
    color: #e0def4;
    font-family: "MesloLGS Nerd Font";
    font-size: 13px;
}
#cabecera { font-size: 15px; font-weight: bold; color: #e0def4; padding: 4px 2px; }
#nav {
    background: transparent; border: none; color: #b16cff;
    font-size: 17px; padding: 0 10px; margin: 0;
}
#nav:hover { background-color: rgba(177, 108, 255, 0.18); border-radius: 6px; }
#dsem { color: #b16cff; font-weight: bold; font-size: 11px; padding-bottom: 3px; }

/* Los dias son botones para poder seleccionarlos con el puntero. */
#dia {
    background: transparent; border: 1px solid transparent;
    border-radius: 7px; padding: 0; margin: 1px;
    min-width: 36px; min-height: 30px;
    color: #e0def4;
    transition: background-color 150ms ease-in-out, border-color 150ms ease-in-out;
}
#dia:hover { background-color: rgba(177, 108, 255, 0.20); }
#dia.otromes { color: #4a4458; }
#dia.hoy { border-color: #b16cff; color: #b16cff; font-weight: bold; }
#dia.sel { background-color: rgba(177, 108, 255, 0.32); border-color: #b16cff; }
#dia.feriado { color: #eb6f92; font-weight: bold; }
#dia.domingo { color: #c98aa6; }
#dia.otromes.feriado, #dia.otromes.domingo { color: #4a4458; }

#separador { background-color: rgba(177, 108, 255, 0.28); min-height: 1px; }
#detalle-fecha { color: #b16cff; font-weight: bold; padding: 6px 2px 2px 2px; }
#detalle { padding: 0 2px 6px 2px; }
#pie { color: #6e6a86; font-size: 10px; padding-top: 4px; }
"""


DEBUG = bool(os.environ.get("CALPANEL_DEBUG"))


def _dbg(msg):
    """Trazas solo con CALPANEL_DEBUG=1. Utiles para depurar el ciclo de vida
    de la capa, que depende del compositor y no se puede razonar a ciegas."""
    if DEBUG:
        print(f"[{dt.datetime.now():%H:%M:%S.%f}] {msg}", file=sys.stderr, flush=True)


def avisar_barra(mensaje):
    """Escribe una orden en el FIFO del demonio de la barra, si esta vivo."""
    try:
        fd = os.open(FIFO_BARRA, os.O_WRONLY | os.O_NONBLOCK)
        try:
            os.write(fd, (mensaje + "\n").encode())
        finally:
            os.close(fd)
    except OSError:
        # Sin demonio (barra lanzada a mano) el panel funciona igual.
        pass


def cursor_pos():
    """(x, y) del puntero segun Hyprland. None si no se puede saber.

    Se pregunta al socket de control de Hyprland y no a GTK porque en Wayland
    una app no puede consultar el puntero cuando no esta encima de ella, que es
    justo el caso que hay que detectar aqui."""
    import socket as sk
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not sig:
        return None
    ruta = os.path.join(RUNTIME, "hypr", sig, ".socket.sock")
    try:
        with sk.socket(sk.AF_UNIX, sk.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect(ruta)
            s.sendall(b"cursorpos")
            datos = s.recv(256).decode(errors="replace").strip()
        x, y = datos.split(",")
        return int(x), int(y)
    except (OSError, ValueError, IndexError):
        return None


class Panel(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.hoy = dt.date.today()
        self.seleccion = self.hoy
        self.mes = self.hoy.replace(day=1)
        self.eventos = gcal.cargar_cache()

        self._montar_capa()
        self._construir()
        self._pintar_mes()

        self.connect("destroy", Gtk.main_quit)
        self.connect("key-press-event", self._tecla)

        # El cierre NO va por foco. Hyprland trae focus_follows_mouse activado,
        # asi que basta con que el puntero roce cualquier ventana para que la
        # capa pierda el foco: el panel se cerraba solo al mover el raton, antes
        # incluso de que te diera tiempo a llegar a el. Se vigila el puntero.
        self._fuera_desde = None
        GLib.timeout_add(200, self._vigilar_puntero)

        self.connect("map-event", lambda *_: _dbg("map"))
        self.connect("unmap-event", lambda *_: _dbg("unmap"))
        self.connect("delete-event", lambda *_: _dbg("delete"))
        self.show_all()
        _dbg("show_all hecho")
        self._refrescar_si_toca()

    # --- Colocacion en pantalla ---

    def _montar_capa(self):
        GtkLayerShell.init_for_window(self)
        # OVERLAY para que quede por encima de las ventanas, igual que la barra
        # cuando baja.
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, ALTO_BARRA)
        # ON_DEMAND: recibe el teclado al clickarlo (para Escape) pero no se lo
        # roba a la app que estabas usando solo por aparecer.
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)

        self.set_size_request(ANCHO_PANEL, -1)

        # Se centra bajo el puntero, que al abrirse esta justo sobre el reloj.
        # Asi el panel cuelga del reloj sin tener que adivinar su posicion en la
        # barra, que cambia con el ancho del texto y de los workspaces.
        pos = cursor_pos()
        monitor = Gdk.Display.get_default().get_monitor(0)
        ancho_pantalla = monitor.get_geometry().width if monitor else 1920
        x = pos[0] if pos else ancho_pantalla // 2
        self.izq = max(MARGEN_BORDE,
                       min(x - ANCHO_PANEL // 2,
                           ancho_pantalla - ANCHO_PANEL - MARGEN_BORDE))
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.LEFT, self.izq)

    # --- Construccion de la interfaz ---

    def _construir(self):
        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), prov,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        caja.set_border_width(10)
        self.add(caja)

        cab = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        b_ant = Gtk.Button(label="‹")
        b_ant.set_name("nav")
        b_ant.connect("clicked", lambda *_: self._mover_mes(-1))
        b_sig = Gtk.Button(label="›")
        b_sig.set_name("nav")
        b_sig.connect("clicked", lambda *_: self._mover_mes(1))

        self.titulo = Gtk.Label()
        self.titulo.set_name("cabecera")
        self.titulo.set_hexpand(True)

        cab.pack_start(b_ant, False, False, 0)
        cab.pack_start(self.titulo, True, True, 0)
        cab.pack_start(b_sig, False, False, 0)
        caja.pack_start(cab, False, False, 0)

        self.rejilla = Gtk.Grid()
        self.rejilla.set_column_homogeneous(True)
        caja.pack_start(self.rejilla, False, False, 0)

        sep = Gtk.Box()
        sep.set_name("separador")
        caja.pack_start(sep, False, False, 6)

        self.det_fecha = Gtk.Label(xalign=0)
        self.det_fecha.set_name("detalle-fecha")
        caja.pack_start(self.det_fecha, False, False, 0)

        self.detalle = Gtk.Label(xalign=0)
        self.detalle.set_name("detalle")
        self.detalle.set_line_wrap(True)
        self.detalle.set_max_width_chars(38)
        caja.pack_start(self.detalle, False, False, 0)

        self.pie = Gtk.Label(xalign=0)
        self.pie.set_name("pie")
        caja.pack_start(self.pie, False, False, 0)

        # Rueda del raton sobre el panel = cambiar de mes.
        self.add_events(Gdk.EventMask.SCROLL_MASK)
        self.connect("scroll-event", self._rueda)

    # --- Dibujo del mes ---

    def _pintar_mes(self):
        for hijo in self.rejilla.get_children():
            self.rejilla.remove(hijo)

        self.titulo.set_text(f"{MESES[self.mes.month - 1]} {self.mes.year}")

        for col, nombre in enumerate(DIAS_CORTOS):
            lbl = Gtk.Label(label=nombre)
            lbl.set_name("dsem")
            self.rejilla.attach(lbl, col, 0, 1, 1)

        # La rejilla empieza en el lunes de la semana del dia 1.
        primero = self.mes
        inicio = primero - dt.timedelta(days=primero.weekday())

        for i in range(42):  # 6 semanas cubren cualquier mes
            fecha = inicio + dt.timedelta(days=i)
            fila, col = divmod(i, 7)
            self.rejilla.attach(self._boton_dia(fecha), col, fila + 1, 1, 1)

        self.rejilla.show_all()
        self._mostrar_detalle()

    def _eventos_de(self, fecha):
        """Eventos de Google de ese dia, sin los festivos que ya sabemos.

        Si Google dice "Dia de la Independencia" el 28 de julio y pe_fechas ya
        pinta "Fiestas Patrias" ese mismo dia, mostrar los dos solo ensucia. Pero
        los festivos de Google que caen en dias que NO tenemos marcados si pasan:
        son los dias no laborables que el gobierno saca por decreto cada ano."""
        marcas = pe_fechas.del_dia(fecha)
        return [e for e in self.eventos.get(fecha.isoformat(), [])
                if not (e.get("festivo") and marcas)]

    def _boton_dia(self, fecha):
        marcas = pe_fechas.del_dia(fecha)
        eventos = self._eventos_de(fecha)
        es_feriado = any(t == pe_fechas.FERIADO for t, _ in marcas)
        es_celebra = any(t == pe_fechas.CELEBRACION for t, _ in marcas)

        # Numero arriba y una fila de puntitos debajo: rojo si es feriado, rosa
        # si es una celebracion, cyan si tienes algo tuyo ese dia.
        puntos = ""
        if es_feriado:
            puntos += "<span color='#eb6f92'>•</span>"
        elif es_celebra:
            puntos += "<span color='#ebbcba'>•</span>"
        if eventos:
            puntos += "<span color='#9ccfd8'>•</span>"

        etq = Gtk.Label()
        etq.set_markup(
            f"<span size='11500'>{fecha.day}</span>\n"
            f"<span size='6500'>{puntos or ' '}</span>")
        etq.set_justify(Gtk.Justification.CENTER)

        btn = Gtk.Button()
        btn.set_name("dia")
        btn.add(etq)
        btn.set_relief(Gtk.ReliefStyle.NONE)

        ctx = btn.get_style_context()
        if fecha.month != self.mes.month:
            ctx.add_class("otromes")
        if es_feriado:
            ctx.add_class("feriado")
        elif fecha.weekday() == 6:
            ctx.add_class("domingo")
        if fecha == self.hoy:
            ctx.add_class("hoy")
        if fecha == self.seleccion:
            ctx.add_class("sel")

        btn.connect("clicked", self._click_dia, fecha)
        return btn

    def _click_dia(self, _btn, fecha):
        self.seleccion = fecha
        # Clickar un dia de otro mes salta a ese mes, como en cualquier agenda.
        if fecha.month != self.mes.month or fecha.year != self.mes.year:
            self.mes = fecha.replace(day=1)
        self._pintar_mes()

    def _mover_mes(self, delta):
        mes = self.mes.month + delta
        ano = self.mes.year + (mes - 1) // 12
        self.mes = dt.date(ano, (mes - 1) % 12 + 1, 1)
        self._pintar_mes()

    def _rueda(self, _w, ev):
        if ev.direction == Gdk.ScrollDirection.UP:
            self._mover_mes(-1)
        elif ev.direction == Gdk.ScrollDirection.DOWN:
            self._mover_mes(1)
        return True

    # --- Detalle del dia seleccionado ---

    def _mostrar_detalle(self):
        f = self.seleccion
        etiqueta = "hoy" if f == self.hoy else ""
        dia_sem = ["lunes", "martes", "miercoles", "jueves", "viernes",
                   "sabado", "domingo"][f.weekday()]
        cab = f"{dia_sem} {f.day} de {MESES[f.month - 1]}"
        if etiqueta:
            cab += f"  <span color='#6e6a86'>· {etiqueta}</span>"
        self.det_fecha.set_markup(cab)

        lineas = []
        for tipo, nombre in pe_fechas.del_dia(f):
            if tipo == pe_fechas.FERIADO:
                lineas.append(f"<span color='#eb6f92'>󰃭 {GLib.markup_escape_text(nombre)}</span>"
                              f"  <span color='#6e6a86' size='9000'>feriado</span>")
            else:
                lineas.append(f"<span color='#ebbcba'>󰸗 {GLib.markup_escape_text(nombre)}</span>")

        for ev in self._eventos_de(f):
            hora = ev["hora"] or "todo el dia"
            titulo = GLib.markup_escape_text(ev["titulo"])
            lineas.append(
                f"<span color='#9ccfd8'>{hora}</span>  {titulo}"
                f"\n   <span color='#6e6a86' size='9000'>{GLib.markup_escape_text(ev['calendario'])}</span>")

        if not lineas:
            lineas.append("<span color='#6e6a86'>Nada anotado este dia</span>")

        self.detalle.set_markup("\n".join(lineas))
        self._pintar_pie()

    def _pintar_pie(self):
        if not gcal.hay_sesion():
            self.pie.set_markup(
                "<span color='#f6c177'>Google Calendar sin conectar</span>")
            return
        edad = gcal.edad_cache()
        if edad is None:
            self.pie.set_text("Google: sin datos todavia")
        elif edad < 120:
            self.pie.set_text("Google: al dia")
        elif edad < 3600:
            self.pie.set_text(f"Google: hace {int(edad // 60)} min")
        else:
            self.pie.set_text(f"Google: hace {int(edad // 3600)} h")

    # --- Refresco en segundo plano ---

    def _refrescar_si_toca(self):
        """Lanza una sincronizacion si el cache esta viejo, sin bloquear nada."""
        if not gcal.hay_sesion():
            return
        edad = gcal.edad_cache()
        if edad is not None and edad < CACHE_VIEJO:
            return
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib", "gcal.py")
        try:
            proc = subprocess.Popen(
                [sys.executable, script, "sync"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            return
        # Se vuelve a mirar el cache cuando el sync haya tenido tiempo de acabar.
        GLib.timeout_add_seconds(3, self._recargar_cache, proc)

    def _recargar_cache(self, proc):
        if proc.poll() is None:
            return True  # sigue bajando, se reintenta
        self.eventos = gcal.cargar_cache()
        self._pintar_mes()
        return False

    def _vigilar_puntero(self):
        """Cierra el panel cuando el puntero lleva un rato lejos.

        Cuenta como "dentro" tambien la franja de la barra: subir del panel al
        reloj para cerrarlo no debe disparar el cierre por el camino."""
        pos = cursor_pos()
        if pos is None:
            return True  # sin datos, no se cierra nada por las bravas
        x, y = pos
        alto = self.get_allocated_height()
        dentro_panel = (self.izq <= x <= self.izq + ANCHO_PANEL
                        and ALTO_BARRA <= y <= ALTO_BARRA + alto)
        dentro_barra = y < ALTO_BARRA

        if dentro_panel or dentro_barra:
            self._fuera_desde = None
        else:
            ahora = GLib.get_monotonic_time() / 1_000_000
            if self._fuera_desde is None:
                self._fuera_desde = ahora
            elif ahora - self._fuera_desde >= CIERRE_DELAY:
                _dbg("puntero fuera: cierro")
                self.close()
                return False
        return True

    def _tecla(self, _w, ev):
        nombre = Gdk.keyval_name(ev.keyval)
        if nombre == "Escape":
            self.close()
        elif nombre in ("Left", "Page_Up"):
            self._mover_mes(-1)
        elif nombre in ("Right", "Page_Down"):
            self._mover_mes(1)
        elif nombre in ("Home", "t"):
            self.mes = self.hoy.replace(day=1)
            self.seleccion = self.hoy
            self._pintar_mes()
        return True


def ya_abierto_lo_cierro():
    """Si hay otra instancia viva la mata y devuelve True (efecto interruptor)."""
    try:
        with open(PID_PATH) as f:
            pid = int(f.read().strip())
    except (OSError, ValueError):
        return False
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except ProcessLookupError:
        return False  # pidfile huerfano de una sesion anterior
    except PermissionError:
        return False


def main():
    if ya_abierto_lo_cierro():
        return

    with open(PID_PATH, "w") as f:
        f.write(str(os.getpid()))

    # Mientras el panel este abierto la barra no se esconde: si se escondiera,
    # el panel quedaria flotando sin nada de lo que colgar y no habria reloj
    # que clickar para cerrarlo.
    avisar_barra("hold")

    def salir(*_):
        avisar_barra("release")
        try:
            os.remove(PID_PATH)
        except OSError:
            pass
        Gtk.main_quit()

    signal.signal(signal.SIGTERM, lambda *_: salir())
    signal.signal(signal.SIGINT, lambda *_: salir())
    # GLib necesita despertar de vez en cuando para atender las senales de Unix.
    GLib.timeout_add(200, lambda: True)

    panel = Panel()
    panel.connect("destroy", lambda *_: salir())
    Gtk.main()

    avisar_barra("release")
    try:
        os.remove(PID_PATH)
    except OSError:
        pass


if __name__ == "__main__":
    main()
