#!/usr/bin/env python3
"""
hypr/scripts/menu-rapido.py — el menú rápido del modo gaming.

Se abre encima de lo que haya (también de un juego a pantalla completa) con
SUPER + la tecla de al lado del 1, con Select + Start en el mando (lo vigila
modo-gaming.py) o con X desde la biblioteca. Volver a pulsarlo lo cierra.

    arriba: lo que está pasando y los controles
        el juego en curso · la música (MPRIS: ⏮ ⏯ ⏭) · volumen de juego,
        música y chat · silenciar el micro · captura de pantalla
    y debajo, con scroll, lo que se abre
        tus escritorios del modo · tus apps y los lanzadores (en un escritorio
        nuevo) · otro juego · salir del modo

Teclado, mando y ratón: flechas / cruceta para moverse, Enter / A para usar;
sobre una barra de volumen, izquierda y derecha la mueven; Esc / B cierra.

Mientras está abierto el mando es SOLO suyo (lib/mando.py, exclusivo): si no,
cada A del menú sería también una A en la partida de detrás.
"""

import importlib.util
import json
import math
import os
import shlex
import signal
import subprocess
import sys
import threading
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gdk, GLib, Gtk, GtkLayerShell, Pango  # noqa: E402

AQUI = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(AQUI, "lib"))
import canales  # noqa: E402
import catalogo  # noqa: E402
import dibujo  # noqa: E402
import mando  # noqa: E402
import sonido  # noqa: E402
from dibujo import AZUL, C, ROSA, VERDE, suave  # noqa: E402

_spec = importlib.util.spec_from_file_location("modo_gaming", os.path.join(AQUI, "modo-gaming.py"))
modo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(modo)

LANZAR = os.path.join(AQUI, "lanzar.sh")
CAPTURA = os.path.join(AQUI, "screenshot.sh")
MODO = os.path.join(AQUI, "modo-gaming.py")
ENTRADA, SALIDA = 0.22, 0.16
PASO_VOLUMEN = 0.05


def ruta_pid():
    return os.path.join(canales.RUNTIME, "menu-rapido.%s.pid" % (canales.firma() or "sin-sesion"))


def otro_abierto():
    """El PID de un menú ya abierto en esta sesión, o None."""
    try:
        with open(ruta_pid()) as fh:
            pid = int(fh.read().strip())
        with open("/proc/%d/cmdline" % pid, "rb") as fh:
            if b"menu-rapido.py" in fh.read():
                return pid
    except (OSError, ValueError):
        pass
    return None


def minutos_de(pid):
    """Cuánto lleva vivo un proceso, en minutos (para «esta sesión»)."""
    try:
        with open("/proc/%d/stat" % pid) as fh:
            inicio = int(fh.read().rsplit(")", 1)[1].split()[19])
        with open("/proc/uptime") as fh:
            arriba = float(fh.read().split()[0])
        return max(0, int((arriba - inicio / os.sysconf("SC_CLK_TCK")) / 60))
    except (OSError, ValueError, IndexError):
        return None


class Menu(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.imgs = dibujo.Imagenes()
        self.inicio = time.monotonic()
        self.saliendo = None
        self.foco = 0
        self.elementos = []           # [{rect, accion, tipo, id}] del último dibujo
        self.foco_id = None
        self.scroll = self.scroll_objetivo = self.scroll_max = 0.0
        self.f, self.arriba, self.alto_visible, self.panel_x = 1.0, 140.0, 800.0, 0.0
        self.datos = {"abiertos": [], "musica": None, "micro": None}
        self.confirmar = None           # el juego que se va a cerrar (pregunta)
        self.cat = catalogo.catalogo()

        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, "menu-rapido")
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        for borde in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM,
                      GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
            GtkLayerShell.set_anchor(self, borde, True)
        GtkLayerShell.set_exclusive_zone(self, -1)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        self.set_app_paintable(True)
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)

        self.area = Gtk.DrawingArea()
        self.area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.SCROLL_MASK
                             | Gdk.EventMask.SMOOTH_SCROLL_MASK)
        self.area.connect("draw", self.dibujar)
        self.area.connect("button-press-event", self.clic)
        self.area.connect("scroll-event", self.rueda)
        self.add(self.area)
        self.connect("key-press-event", self.tecla)
        self.mando = mando.Mando(self.boton, exclusivo=True).empezar()
        signal.signal(signal.SIGTERM, lambda *_: GLib.idle_add(self.cerrar))

        self.refrescar()
        GLib.timeout_add(1500, self.refrescar)
        GLib.timeout_add(16, self.animar)

    # --- Datos (en un hilo: pw-dump y D-Bus no pueden congelar el dibujo) --------
    def refrescar(self):
        threading.Thread(target=self._leer, daemon=True).start()
        return self.saliendo is None

    def _leer(self):
        """Todo lo abierto (en cualquier escritorio del modo, y lo guardado al
        entrar), agrupado por app, con SU sonido: los flujos de PipeWire de su
        arbol de procesos. Medido: el audio de Brave y el de Glassy Music los
        abre un proceso hijo del de su ventana, asi que el arbol los encuentra
        sin adivinar nombres (por nombre no se reconocia a Glassy: su audio sale
        como «Chromium»)."""
        ventanas = modo.clientes()
        activo = modo.escritorio_activo().get("id")
        dump = sonido._pw_dump()
        flujos = sonido.flujos(dump)
        abiertos, vistos = [], {}
        hay_biblioteca = False
        for v in ventanas:
            clase = modo._clase(v)
            if clase == modo.CLASE_BIBLIOTECA:
                hay_biblioteca = True
                continue
            if clase == modo.CLASE_VIDEO or modo.es_dialogo_steam(v) or not v.get("address"):
                continue
            n = modo.num_ws(v)
            guardada = False
            if not n:
                continue                # lo guardado al entrar no es del modo
            huella = modo.huella_app(v.get("pid")) or ("ventana", v["address"])
            if huella in vistos:
                vistos[huella]["ventanas"].append(v)
                continue
            juego = modo.es_de_juego(v)
            j = self.juego_del_catalogo(v) if juego else None
            item = {"clave": "%s:%s" % huella, "ventanas": [v], "ws": n, "guardada": guardada,
                    "juego": bool(juego), "pid": v.get("pid") or 0,
                    "nombre": (j or {}).get("nombre") or self.nombre_de(v),
                    "caratula": (j or {}).get("arte", {}).get("caratula"),
                    "icono": (j or {}).get("icono") or self.icono_de(v), "activo": n == activo}
            vistos[huella] = item
            abiertos.append(item)
        for item in abiertos:
            arbol = sonido.descendientes([x.get("pid") for x in item["ventanas"] if x.get("pid")])
            item["flujos"] = [f for f in flujos if f["pid"] in arbol]
            if not item["flujos"] and item["juego"]:
                # Proton a veces saca el sonido por un proceso de Wine que no
                # cuelga de la ventana: los de Wine sin dueño, al juego.
                item["flujos"] = [f for f in flujos if sonido.clasificar(f, set(), set(), set()) == "juego"]
        # Cada reproductor (MPRIS) con su app: el pid dueño de su nombre en el bus
        # es el de la ventana de la app, o uno de su arbol. Esas apps salen como
        # tarjeta de musica (con su volumen), no repetidas en «abierto».
        musica = []
        for r in sonido.reproductores():
            dueño = next((a for a in abiertos
                          if r["pid"] in sonido.descendientes([x.get("pid") for x in a["ventanas"]])), None)
            if dueño is not None:
                dueño["reproductor"] = r
                r["app"] = dueño
                r["flujos"] = dueño["flujos"]
            else:
                arbol = sonido.descendientes([r["pid"]]) if r["pid"] else set()
                r["app"], r["flujos"] = None, [f for f in flujos if f["pid"] in arbol]
            musica.append(r)
        abiertos = [a for a in abiertos if "reproductor" not in a]
        abiertos.sort(key=lambda x: x["ws"] or 99)
        if hay_biblioteca:
            abiertos.insert(0, {"clave": "biblioteca", "biblioteca": True, "ws": modo.WS_BIBLIOTECA,
                                "nombre": "Biblioteca", "activo": activo == modo.WS_BIBLIOTECA,
                                "flujos": [], "ventanas": [], "juego": False, "guardada": False})
        datos = {"abiertos": abiertos, "musica": musica, "micro": sonido.micro()}
        GLib.idle_add(self._listos, datos)

    @staticmethod
    def nombre_de(v):
        clase = (v.get("class") or "").lower()
        conocidos = {"brave-browser": "Brave", "kitty": "Terminal", "org.kde.dolphin": "Archivos",
                     "nankill.xyz.glassymusic.mod": "Glassy Music", "steam": "Steam"}
        if clase in conocidos:
            return conocidos[clase]
        return (v.get("initialTitle") or v.get("title") or v.get("class") or "?")[:40]

    def icono_de(self, v):
        clase = v.get("class") or ""
        for item in self.cat["apps"] + self.cat["lanzadores"]:
            icono = item.get("icono") or ""
            if icono and (icono.lower() in clase.lower() or clase.lower() in icono.lower()):
                return icono
        return {"brave-browser": "brave-desktop", "nankill.xyz.glassymusic.mod": "glassy-music-nankill-mod"}.get(
            clase.lower(), clase)

    def _listos(self, datos):
        self.datos = datos
        self.area.queue_draw()
        return False

    def juego_del_catalogo(self, ventana):
        clase = (ventana.get("class") or "").lower()
        if clase.startswith("steam_app_"):
            ident = "steam:" + clase[len("steam_app_"):]
            for j in self.cat["juegos"]:
                if j["id"] == ident:
                    return j
        return None

    # --- Acciones ------------------------------------------------------------------
    def cerrar(self, despues=None):
        if self.saliendo is None:
            self.saliendo = time.monotonic()
            self.despues = despues
        return False

    def _despues_de_cerrar(self):
        if getattr(self, "despues", None):
            # Tras irse la capa: una captura no puede salir con el menú dentro.
            time.sleep(0.15)
            self.despues()

    def lanzar(self, cmd, juego=False):
        try:
            orden = shlex.split(cmd)
        except ValueError:
            orden = cmd.split()
        entorno = dict(os.environ, **(catalogo.entorno_de_juego() if juego else {}))
        self.cerrar(lambda: subprocess.Popen([LANZAR] + orden, env=entorno, start_new_session=True,
                                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL))

    def overlay(self):
        """Enseñar / esconder el overlay de MangoHud desde fuera del juego (por
        si un juego no lee Supr). Sin juego con MangoHud, mangohudctl no tiene
        a quien hablar y no pasa nada."""
        try:
            subprocess.run(["mangohudctl", "toggle", "no_display"], capture_output=True, timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            pass
        self.cerrar()

    def orden(self, *args):
        self.cerrar(lambda: subprocess.Popen([MODO] + list(args), start_new_session=True,
                                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL))

    def musica(self, bus, metodo):
        sonido.controlar(bus, metodo)
        GLib.timeout_add(250, self.refrescar)

    def abierto(self, clave):
        """Lo abierto con esa clave: una fila de «abierto» o la app de una
        tarjeta de musica."""
        for a in self.datos.get("abiertos", []):
            if a["clave"] == clave:
                return a
        for r in self.datos.get("musica") or []:
            if r.get("app") and r["app"]["clave"] == clave:
                return r["app"]
            if not r.get("app") and "musica:" + r["bus"] == clave:
                return {"clave": clave, "flujos": r["flujos"], "ventanas": [], "juego": False}
        return None

    def cerrar_abierto(self, clave, confirmado=False):
        """Una app se cierra ya (pidiendolo, como la X). Un juego pregunta
        antes: hay juegos que guardan solos y otros que no."""
        item = self.abierto(clave)
        if not item:
            return
        if item["juego"] and not confirmado:
            self.confirmar = item
            self.foco_id = "confirmar:ir"
            self.area.queue_draw()
            return
        for v in item["ventanas"]:
            modo.cerrar_ventana(modo.hypr.modo() or "lua", v["address"])
        self.confirmar = None
        self.foco_id = None
        GLib.timeout_add(600, self.refrescar)

    def volumen(self, grupo, paso):
        item = self.abierto(grupo)
        flujos = item["flujos"] if item else []
        if not flujos:
            return
        actual = max((f["volumen"] or 0) for f in flujos)
        nuevo = max(0.0, min(1.0, round((actual + paso) / PASO_VOLUMEN) * PASO_VOLUMEN))
        sonido.poner_volumen(flujos, nuevo)
        for f in flujos:
            f["volumen"] = nuevo
        self.area.queue_draw()

    def micro(self):
        sonido.alternar_micro()
        self.datos["micro"] = sonido.micro()
        self.area.queue_draw()

    def captura(self):
        self.cerrar(lambda: subprocess.Popen([CAPTURA, "--full"], start_new_session=True,
                                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL))

    # --- Entrada ---------------------------------------------------------------------
    def actual(self):
        return self.elementos[self.foco] if 0 <= self.foco < len(self.elementos) else None

    def mover(self, dx, dy):
        """Navegacion espacial (en coordenadas del contenido, con scroll): el
        elemento mas cercano en esa direccion. Sobre una barra de volumen,
        izquierda y derecha la mueven en vez de navegar."""
        e = self.actual()
        if e is None:
            return
        if e["tipo"] == "barra" and dx:
            self.volumen(e["id"].split(":", 1)[1], dx * PASO_VOLUMEN)
            return
        x0, y0, w0, h0 = e["rect"]
        cx, cy = x0 + w0 / 2, y0 + h0 / 2
        mejor, puntos = None, None
        for i, o in enumerate(self.elementos):
            if i == self.foco:
                continue
            x, y, w, h = o["rect"]
            ax, ay = x + w / 2 - cx, y + h / 2 - cy
            if (dx and ax * dx <= 4) or (dy and ay * dy <= 4):
                continue
            principal, lateral = (abs(ax), abs(ay)) if dx else (abs(ay), abs(ax))
            p = principal + lateral * 2.5
            if puntos is None or p < puntos:
                mejor, puntos = i, p
        if mejor is not None:
            self.foco = mejor
            self.foco_id = self.elementos[mejor]["id"]
            self.seguir_foco()
            self.area.queue_draw()

    def seguir_foco(self):
        """Que el elemento con el foco se vea: el scroll va hasta el."""
        e = self.actual()
        if not e or self.confirmar:
            return
        _, y, _, h = e["rect"]
        alto = self.alto_visible
        margen = 30 * self.f
        if y - margen < self.scroll_objetivo:
            self.scroll_objetivo = max(0.0, y - margen)
        elif y + h + margen > self.scroll_objetivo + alto:
            self.scroll_objetivo = min(self.scroll_max, y + h + margen - alto)

    def usar(self):
        e = self.actual()
        if e and e.get("accion"):
            e["accion"]()

    def tecla(self, _w, ev):
        k = ev.keyval
        if k == Gdk.KEY_Escape and self.confirmar:
            self.confirmar, self.foco_id = None, None
            self.area.queue_draw()
        elif k == Gdk.KEY_Escape:
            self.cerrar()
        elif k in (Gdk.KEY_Left, Gdk.KEY_a):
            self.mover(-1, 0)
        elif k in (Gdk.KEY_Right, Gdk.KEY_d):
            self.mover(1, 0)
        elif k in (Gdk.KEY_Up, Gdk.KEY_w):
            self.mover(0, -1)
        elif k in (Gdk.KEY_Down, Gdk.KEY_s, Gdk.KEY_Tab):
            self.mover(0, 1)
        elif k in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            self.usar()
        elif k == Gdk.KEY_grave or ev.hardware_keycode == 49:
            self.cerrar()             # la misma tecla que lo abrio lo cierra
        return True

    def boton(self, accion):
        if self.saliendo is not None:
            return
        if accion == "atras" and self.confirmar:
            self.confirmar, self.foco_id = None, None
            self.area.queue_draw()
            return
        {"izquierda": lambda: self.mover(-1, 0), "derecha": lambda: self.mover(1, 0),
         "arriba": lambda: self.mover(0, -1), "abajo": lambda: self.mover(0, 1),
         "aceptar": self.usar, "atras": self.cerrar, "start": self.cerrar,
         "select": self.cerrar}.get(accion, lambda: None)()

    def clic(self, _w, ev):
        if ev.x < self.panel_x:
            self.cerrar()              # clic fuera del panel: volver al juego
            return True
        if not (self.arriba <= ev.y <= self.arriba + self.alto_visible):
            return True
        cy = ev.y - self.arriba + self.scroll
        for i, e in enumerate(self.elementos):
            x, y, w, h = e["rect"]
            if x <= ev.x <= x + w and y <= cy <= y + h:
                self.foco, self.foco_id = i, e["id"]
                if e["tipo"] == "barra":
                    fraccion = (ev.x - e["barra"][0]) / max(1, e["barra"][1])
                    grupo = e["id"].split(":", 1)[1]
                    item = self.abierto(grupo)
                    flujos = item["flujos"] if item else []
                    if flujos:
                        actual = max((f["volumen"] or 0) for f in flujos)
                        self.volumen(grupo, max(0.0, min(1.0, fraccion)) - actual)
                elif e.get("accion"):
                    e["accion"]()
                self.area.queue_draw()
                return True
        return True

    def rueda(self, _w, ev):
        paso = 0
        if ev.direction == Gdk.ScrollDirection.UP:
            paso = -1
        elif ev.direction == Gdk.ScrollDirection.DOWN:
            paso = 1
        elif ev.direction == Gdk.ScrollDirection.SMOOTH:
            paso = ev.get_scroll_deltas()[2]
        self.scroll_objetivo = max(0.0, min(self.scroll_max, self.scroll_objetivo + paso * 90 * self.f))
        self.area.queue_draw()
        return True

    # --- Animacion -----------------------------------------------------------------
    def animar(self):
        ahora = time.monotonic()
        if self.saliendo is not None:
            if ahora - self.saliendo >= SALIDA:
                self.hide()
                threading.Thread(target=self._despues_de_cerrar, daemon=True).start()
                GLib.timeout_add(400, Gtk.main_quit)
                return False
            self.area.queue_draw()
        elif ahora - self.inicio < ENTRADA:
            self.area.queue_draw()
        if abs(self.scroll - self.scroll_objetivo) > 0.5:
            self.scroll += (self.scroll_objetivo - self.scroll) * 0.3
            self.area.queue_draw()
        else:
            self.scroll = self.scroll_objetivo
        return True

    # --- Dibujo --------------------------------------------------------------------
    def elemento(self, ident, rect, accion=None, tipo="boton", **extra):
        """Registra algo que se puede elegir. `rect` en coordenadas del
        CONTENIDO (sin scroll): asi la navegacion llega tambien a lo que aun no
        se ve, y el scroll lo trae."""
        e = {"id": ident, "rect": rect, "accion": accion, "tipo": tipo}
        e.update(extra)
        self.elementos.append(e)
        return self.foco_id == ident

    def marco_foco(self, cr, x, y, w, h, r, f, activo):
        if not activo:
            return
        for grosor, alfa in ((10, .12), (5, .22)):
            dibujo.redondo(cr, x - grosor * f / 2, y - grosor * f / 2, w + grosor * f, h + grosor * f, r + 4 * f)
            cr.set_source_rgba(*C["amatista"], alfa)
            cr.fill()
        dibujo.redondo(cr, x, y, w, h, r)
        cr.set_source_rgba(*C["neon"], 1)
        cr.set_line_width(2 * f)
        cr.stroke()

    def tarjeta(self, cr, x, y, w, h, f, fondo=.55):
        dibujo.redondo(cr, x, y, w, h, 14 * f)
        cr.set_source_rgba(*C["apagado"], fondo)
        cr.fill_preserve()
        cr.set_source_rgba(*C["amatista"], .18)
        cr.set_line_width(1)
        cr.stroke()

    def boton_texto(self, cr, ident, rect, texto, f, accion, color=None, fondo=.55, usable=True):
        activo = self.elemento(ident, rect, accion if usable else None)
        self.tarjeta(cr, *rect, f, fondo if usable else .2)
        self.marco_foco(cr, *rect, 14 * f, f, activo)
        x, y, w, h = rect
        tw, th = dibujo.medir(cr, texto, 15 * f, Pango.Weight.BOLD)
        dibujo.texto(cr, texto, x + w / 2, y + (h - th) / 2, 15 * f,
                     color or (C["luz"] if usable else C["tenue"]), Pango.Weight.BOLD, centro=True,
                     ancho=w - 16 * f, una_linea=True)

    def dibujar(self, _w, cr):
        import cairo
        a = self.area.get_allocation()
        w, h = a.width, a.height
        f = self.f = max(0.5, min(w / 1920, h / 1080))
        ahora = time.monotonic()
        k = suave((ahora - self.inicio) / ENTRADA)
        if self.saliendo is not None:
            k = 1 - suave((ahora - self.saliendo) / SALIDA)
        foco_previo = self.foco_id
        self.elementos = []

        cr.set_operator(cairo.OPERATOR_CLEAR)   # la capa es transparente
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.set_source_rgba(*C["abismo"], .55 * k)
        cr.paint()

        pw = min(w, 660 * f)
        px = self.panel_x = w - pw + (1 - k) * 80 * f
        cr.push_group()
        g = cairo.LinearGradient(0, 0, 0, h)
        g.add_color_stop_rgba(0, *C["superficie"], .95)
        g.add_color_stop_rgba(1, *C["abismo"], .97)
        cr.rectangle(px, 0, pw, h)
        cr.set_source(g)
        cr.fill()
        cr.move_to(px, 0)
        cr.line_to(px, h)
        cr.set_source_rgba(*C["neon"], .35)
        cr.set_line_width(1)
        cr.stroke()

        m = 52 * f
        dibujo.texto(cr, "MENÚ RÁPIDO", px + m, 48 * f, 30 * f, C["luz"], Pango.Weight.BOLD, espaciado=5 * f)
        dibujo.texto(cr, "el juego sigue corriendo detrás", px + m, 92 * f, 13 * f, C["tenue"], espaciado=2 * f)
        dibujo.texto(cr, time.strftime("%H:%M"), px + pw - m, 48 * f, 28 * f, C["luz"], Pango.Weight.BOLD, derecha=True)

        # El contenido, con scroll, entre la cabecera y el pie.
        self.arriba = 140 * f
        self.alto_visible = h - self.arriba - 76 * f
        cr.save()
        cr.rectangle(px, self.arriba, pw, self.alto_visible)
        cr.clip()
        cr.translate(0, self.arriba - self.scroll)
        fin = self.dibujar_contenido(cr, px + m, 0, pw - 2 * m, f)
        cr.restore()
        self.scroll_max = max(0.0, fin + 20 * f - self.alto_visible)
        self.scroll_objetivo = min(self.scroll_objetivo, self.scroll_max)
        if self.scroll_max > 0:
            # La guia del scroll, a la derecha.
            total = self.alto_visible
            largo = max(40 * f, total * self.alto_visible / (fin + 20 * f))
            y = self.arriba + (total - largo) * (self.scroll / self.scroll_max if self.scroll_max else 0)
            dibujo.redondo(cr, px + pw - 18 * f, y, 5 * f, largo, 2.5 * f)
            cr.set_source_rgba(*C["amatista"], .45)
            cr.fill()
            if self.scroll < self.scroll_max - 2:
                g = cairo.LinearGradient(0, self.arriba + self.alto_visible - 50 * f, 0, self.arriba + self.alto_visible)
                g.add_color_stop_rgba(0, *C["abismo"], 0)
                g.add_color_stop_rgba(1, *C["abismo"], .9)
                cr.rectangle(px, self.arriba + self.alto_visible - 50 * f, pw - 24 * f, 50 * f)
                cr.set_source(g)
                cr.fill()
        self.dibujar_pie(cr, px, h, pw, f)
        if self.confirmar:
            self.elementos = []
            self.dibujar_confirmacion(cr, px, pw, h, f)
        cr.pop_group_to_source()
        cr.paint_with_alpha(k)

        ids = [e["id"] for e in self.elementos]
        if foco_previo is None:
            # Al abrir, en tu primera app (el navegador para el chat, tu
            # musica): es a lo que se viene al menu casi siempre.
            primero = next((i for i, x in enumerate(ids) if x.startswith("abrir:")), 0)
            if ids:
                # Sin mover el scroll: al abrir se ve desde arriba (lo de
                # ahora); el scroll ya seguira al foco cuando te muevas.
                self.foco, self.foco_id = primero, ids[primero]
                self.area.queue_draw()
        elif foco_previo in ids:
            self.foco = ids.index(foco_previo)
        elif self.elementos:
            self.foco = min(self.foco, len(self.elementos) - 1)
            self.foco_id = self.elementos[self.foco]["id"]
            self.area.queue_draw()

    def seccion(self, cr, x, y, texto, f):
        dibujo.texto(cr, texto, x, y, 13 * f, C["amatista"], Pango.Weight.BOLD, espaciado=5 * f)
        return y + 30 * f

    def dibujar_contenido(self, cr, x, y, ancho, f):
        """Todo lo que se desplaza. Arriba lo de ahora (juego, musica, volumen,
        micro, overlay, captura) y debajo lo que se abre. Devuelve el alto."""
        abiertos = self.datos.get("abiertos") or []
        if abiertos:
            y = self.seccion(cr, x, y, "ABIERTO", f)
            for item in abiertos:
                y = self.dibujar_abierto(cr, x, y, ancho, f, item) + 12 * f
            y += 8 * f
        reproductores = self.datos.get("musica") or []
        y = self.seccion(cr, x, y, "MÚSICA", f)
        if not reproductores:
            self.tarjeta(cr, x, y, ancho, 90 * f, f, .25)
            dibujo.texto(cr, "No suena nada", x + 20 * f, y + 22 * f, 17 * f, C["tenue"])
            dibujo.texto(cr, "Pon música en tu app y aparecerá aquí", x + 20 * f, y + 52 * f,
                         13 * f, C["tenue"], alfa=.7)
            y += 106 * f
        for r in reproductores:
            y = self.dibujar_musica(cr, x, y, ancho, f, r) + 12 * f
        y += 4 * f

        # Micro, overlay y captura
        mic = self.datos.get("micro")
        tercio = (ancho - 2 * 12 * f) / 3
        callado = bool(mic and mic[1])
        texto_mic = ("󰍭  Silenciado" if callado else "󰍬  Micro") if mic else "Sin micro"
        self.boton_texto(cr, "micro", (x, y, tercio, 60 * f), texto_mic, f, self.micro,
                         color=ROSA if callado else None)
        self.boton_texto(cr, "overlay", (x + tercio + 12 * f, y, tercio, 60 * f), "󰄨  Overlay", f, self.overlay)
        self.boton_texto(cr, "captura", (x + 2 * (tercio + 12 * f), y, tercio, 60 * f), "󰄀  Captura", f,
                         self.captura)
        y += 84 * f

        # Abrir: tus apps y los lanzadores (en un escritorio nuevo)
        y = self.seccion(cr, x, y, "ABRIR EN UN ESCRITORIO NUEVO", f)
        cosas = self.cat["apps"] + self.cat["lanzadores"]
        lado = (ancho - 3 * 14 * f) / 4
        for i in range(len(cosas) + 1):
            cx = x + (i % 4) * (lado + 14 * f)
            cy = y + (i // 4) * (lado + 14 * f)
            rect = (cx, cy, lado, lado)
            if i < len(cosas):
                item = cosas[i]
                activo = self.elemento("abrir:" + item["id"], rect, lambda c=item["cmd"]: self.lanzar(c))
                self.tarjeta(cr, *rect, f, .55)
                self.marco_foco(cr, *rect, 18 * f, f, activo)
                pix = self.imgs.icono(item.get("icono"), 52 * f)
                if pix:
                    Gdk.cairo_set_source_pixbuf(cr, pix, cx + (lado - pix.get_width()) / 2, cy + lado * .16)
                    cr.paint()
                dibujo.texto(cr, item["nombre"], cx + lado / 2, cy + lado * .70, 12 * f, C["luz"],
                             centro=True, ancho=lado - 12 * f, una_linea=True)
            else:
                activo = self.elemento("anadir", rect, lambda: self.orden("anadir-app"))
                dibujo.redondo(cr, *rect, 18 * f)
                cr.set_dash([6 * f, 5 * f])
                cr.set_source_rgba(*C["amatista"], .45)
                cr.set_line_width(1.5 * f)
                cr.stroke()
                cr.set_dash([])
                self.marco_foco(cr, *rect, 18 * f, f, activo)
                dibujo.texto(cr, "+", cx + lado / 2, cy + lado * .14, 38 * f, C["tenue"], centro=True)
                dibujo.texto(cr, "Añadir", cx + lado / 2, cy + lado * .70, 12 * f, C["tenue"], centro=True)
        y += ((len(cosas) + 1 + 3) // 4) * (lado + 14 * f) + 16 * f

        # Otro juego (tambien a un escritorio nuevo, si ya hay uno en el 1)
        y = self.seccion(cr, x, y, "OTRO JUEGO", f)
        abiertos_ = {a["nombre"] for a in self.datos.get("abiertos", []) if a.get("juego")}
        juegos_ = [j for j in self.cat["juegos"] if j["nombre"] not in abiertos_]
        mw = (ancho - 4 * 14 * f) / 5
        mh = mw * 1.5
        for i, j in enumerate(juegos_):
            cx = x + (i % 5) * (mw + 14 * f)
            cy = y + (i // 5) * (mh + 14 * f)
            rect = (cx, cy, mw, mh)
            activo = self.elemento("juego:" + j["id"], rect, lambda jj=j: self._otro_juego(jj))
            cr.save()
            dibujo.redondo(cr, *rect, 10 * f)
            cr.clip()
            pix = self.imgs.cargar(j["arte"].get("caratula"), mw, mh, cubrir=True)
            if pix:
                Gdk.cairo_set_source_pixbuf(cr, pix, cx + (mw - pix.get_width()) / 2, cy + (mh - pix.get_height()) / 2)
                cr.paint()
            else:
                cr.set_source_rgba(*C["apagado"], .8)
                cr.paint()
                ic = self.imgs.icono(j.get("icono"), 44 * f)
                if ic:
                    Gdk.cairo_set_source_pixbuf(cr, ic, cx + (mw - ic.get_width()) / 2, cy + mh * .25)
                    cr.paint()
                dibujo.texto(cr, j["nombre"], cx + mw / 2, cy + mh * .68, 11 * f, C["luz"], centro=True,
                             ancho=mw - 8 * f, una_linea=True)
            cr.restore()
            self.marco_foco(cr, *rect, 10 * f, f, activo)
        if not juegos_:
            dibujo.texto(cr, "No hay más juegos", x, y + 10 * f, 14 * f, C["tenue"])
            y += 40 * f
        else:
            y += ((len(juegos_) + 4) // 5) * (mh + 14 * f) + 16 * f

        rect = (x, y, ancho, 58 * f)
        activo = self.elemento("salir", rect, lambda: self.orden("toggle"))
        dibujo.redondo(cr, *rect, 14 * f)
        cr.set_source_rgba(*ROSA, .14)
        cr.fill_preserve()
        cr.set_source_rgba(*ROSA, .5)
        cr.set_line_width(1)
        cr.stroke()
        self.marco_foco(cr, *rect, 14 * f, f, activo)
        dibujo.texto(cr, "Salir del modo gaming", x + ancho / 2, y + 18 * f, 15 * f, ROSA,
                     Pango.Weight.BOLD, centro=True)
        return y + 58 * f

    def boton_redondo(self, cr, ident, cx, cy, r, glifo, f, accion, color=None, fondo=None):
        rect = (cx - r, cy - r, 2 * r, 2 * r)
        activo = self.elemento(ident, rect, accion)
        dibujo.circulo(cr, cx, cy, r)
        cr.set_source_rgba(*(fondo or C["apagado"]), .9 if accion else .35)
        cr.fill()
        self.marco_foco(cr, *rect, r, f, activo)
        tw, th = dibujo.medir(cr, glifo, r * .9)
        dibujo.texto(cr, glifo, cx, cy - th / 2, r * .9, color or (C["luz"] if accion else C["tenue"]), centro=True)

    def barra_volumen(self, cr, clave, x, y, ancho, f, flujos):
        """Una barra fina de volumen, elegible (izquierda/derecha la mueven)."""
        valor = max(((fl["volumen"] or 0) for fl in flujos), default=None)
        if valor is None:
            return
        rect = (x - 8 * f, y - 12 * f, ancho + 16 * f, 26 * f)
        activo = self.elemento("vol:" + clave, rect, None, "barra", barra=(x + 22 * f, ancho - 70 * f))
        self.marco_foco(cr, *rect, 10 * f, f, activo)
        dibujo.texto(cr, "󰕾", x, y - 8 * f, 13 * f, C["tenue"])
        bx, bw = x + 22 * f, ancho - 70 * f
        dibujo.redondo(cr, bx, y - 2 * f, bw, 4 * f, 2 * f)
        cr.set_source_rgba(*C["apagado"], 1)
        cr.fill()
        dibujo.redondo(cr, bx, y - 2 * f, max(4 * f, bw * valor), 4 * f, 2 * f)
        cr.set_source_rgb(*C["neon"])
        cr.fill()
        dibujo.circulo(cr, bx + bw * valor, y, 6 * f)
        cr.set_source_rgb(*C["luz"])
        cr.fill()
        dibujo.texto(cr, "%d%%" % round(valor * 100), x + ancho, y - 8 * f, 12 * f, C["tenue"], derecha=True)

    def dibujar_abierto(self, cr, x, y, ancho, f, item):
        """Una tarjeta de lo abierto, al estilo de la maqueta: caratula (o
        icono), nombre, que hace y donde; a la derecha ir y cerrar; y debajo su
        volumen, fino, si suena. Devuelve donde acaba."""
        clave = item["clave"]
        con_sonido = bool(item.get("flujos"))
        if item.get("biblioteca"):
            alto = 72 * f
        elif con_sonido:
            alto = 120 * f
        else:
            alto = (104 if item.get("activo") or item.get("caratula") else 84) * f
        self.tarjeta(cr, x, y, ancho, alto, f, .5 if item.get("activo") else .38)
        tx = x + 16 * f
        if item.get("caratula"):
            pix = self.imgs.cargar(item["caratula"], 54 * f, 81 * f, cubrir=True)
            if pix:
                cr.save()
                dibujo.redondo(cr, tx, y + 12 * f, 54 * f, 81 * f, 8 * f)
                cr.clip()
                Gdk.cairo_set_source_pixbuf(cr, pix, tx + (54 * f - pix.get_width()) / 2, y + 12 * f)
                cr.paint()
                cr.restore()
            tx += 72 * f
        else:
            pix = self.imgs.icono(item.get("icono") or ("applications-games" if item.get("biblioteca") else ""),
                                  44 * f)
            if pix:
                Gdk.cairo_set_source_pixbuf(cr, pix, tx, y + (min(alto, 104 * f) - 44 * f) / 2 - 6 * f)
                cr.paint()
            tx += 62 * f
        derecha = x + ancho - 16 * f
        botones = 2 if not item.get("biblioteca") else 1
        dibujo.texto(cr, item["nombre"], tx, y + 18 * f, 18 * f, C["luz"], Pango.Weight.BOLD,
                     ancho=derecha - tx - botones * 50 * f, una_linea=True)
        if item.get("biblioteca"):
            sub = "escritorio 1"
        elif item["juego"]:
            mins = minutos_de(item.get("pid") or 0)
            sub = ("jugando · %s · " % catalogo._horas(mins) if mins else "jugando · ") + "escritorio %d" % item["ws"]
        else:
            sub = "escritorio %d" % item["ws"]
        dibujo.texto(cr, sub, tx, y + 46 * f, 13 * f, C["tenue"], espaciado=1 * f)
        if item.get("activo"):
            dibujo.circulo(cr, tx + 4 * f, y + 76 * f, 4 * f)
            cr.set_source_rgb(*VERDE)
            cr.fill()
            dibujo.texto(cr, "AQUÍ" if not item["juego"] else "EN CURSO", tx + 14 * f, y + 68 * f, 11 * f,
                         VERDE, espaciado=3 * f)
        # Ir y cerrar, redondos, arriba a la derecha
        cy = y + 34 * f
        bx = derecha - 20 * f
        if not item.get("biblioteca"):
            self.boton_redondo(cr, "cerrar:" + clave, bx, cy, 20 * f, "󰅖", f,
                               lambda c=clave: self.cerrar_abierto(c), color=ROSA)
            bx -= 50 * f
        usable = bool(item["ws"]) and not item.get("activo")
        self.boton_redondo(cr, "ir:" + clave, bx, cy, 20 * f, "󰁔", f,
                           (lambda n=item["ws"]: self.orden("ir", str(n))) if usable else None)
        if con_sonido:
            self.barra_volumen(cr, clave, tx, y + alto - 20 * f, derecha - tx, f, item["flujos"])
        return y + alto

    def dibujar_musica(self, cr, x, y, ancho, f, r):
        """Una tarjeta por reproductor (Brave, Glassy...): portada, que suena,
        ⏮ ⏯ ⏭, y debajo el volumen de ESA app, con ir y cerrar si es del modo."""
        app = r.get("app")
        clave = app["clave"] if app else "musica:" + r["bus"]
        alto = 150 * f
        self.tarjeta(cr, x, y, ancho, alto, f, .45)
        portada = self.imgs.cargar(r.get("portada"), 82 * f, 82 * f, cubrir=True)
        tx = x + 14 * f
        if portada:
            cr.save()
            dibujo.redondo(cr, tx, y + 14 * f, 82 * f, 82 * f, 10 * f)
            cr.clip()
            Gdk.cairo_set_source_pixbuf(cr, portada, tx + (82 * f - portada.get_width()) / 2,
                                        y + 14 * f + (82 * f - portada.get_height()) / 2)
            cr.paint()
            cr.restore()
        else:
            pix = self.imgs.icono((app or {}).get("icono"), 52 * f)
            if pix:
                Gdk.cairo_set_source_pixbuf(cr, pix, tx + 15 * f, y + 29 * f)
                cr.paint()
        tx += 98 * f
        bx0 = x + ancho - 3 * 50 * f - 10 * f
        dibujo.texto(cr, r["titulo"] or "Sin título", tx, y + 16 * f, 16 * f, C["luz"],
                     Pango.Weight.BOLD, ancho=bx0 - tx - 10 * f, una_linea=True)
        dibujo.texto(cr, r["artista"] or (app or {}).get("nombre", ""), tx, y + 42 * f, 13 * f, C["tenue"],
                     ancho=bx0 - tx - 10 * f, una_linea=True)
        estado = "SONANDO" if r["estado"] == "Playing" else "EN PAUSA"
        if app:
            estado += "  ·  %s · escritorio %d" % (app["nombre"].upper(), app["ws"])
        dibujo.texto(cr, estado, tx, y + 68 * f, 11 * f, VERDE if r["estado"] == "Playing" else C["tenue"],
                     espaciado=2 * f, ancho=x + ancho - tx - 14 * f, una_linea=True)
        for i, (glifo, metodo) in enumerate((("󰒮", "Previous"),
                                             ("󰏤" if r["estado"] == "Playing" else "󰐊", "PlayPause"),
                                             ("󰒭", "Next"))):
            self.boton_redondo(cr, "musica:%s:%s" % (r["bus"], metodo), bx0 + 22 * f + i * 50 * f, y + 38 * f,
                               22 * f, glifo, f, lambda b=r["bus"], m=metodo: self.musica(b, m),
                               fondo=C["violeta"] if metodo == "PlayPause" else None)
        # Abajo: el volumen de la app, e ir / cerrar
        derecha = x + ancho - 16 * f
        fin_barra = derecha - (110 * f if app else 0)
        if r.get("flujos"):
            self.barra_volumen(cr, clave, x + 16 * f, y + alto - 26 * f, fin_barra - x - 16 * f, f, r["flujos"])
        if app:
            self.boton_redondo(cr, "cerrar:" + clave, derecha - 18 * f, y + alto - 26 * f, 18 * f, "󰅖", f,
                               lambda c=clave: self.cerrar_abierto(c), color=ROSA)
            usable = not app.get("activo")
            self.boton_redondo(cr, "ir:" + clave, derecha - 64 * f, y + alto - 26 * f, 18 * f, "󰁔", f,
                               (lambda n=app["ws"]: self.orden("ir", str(n))) if usable else None)
        return y + alto

    def dibujar_confirmacion(self, cr, px, pw, h, f):
        """«¿Cerrar este juego?»: ir a guardar, cerrarlo ya, o nada."""
        item = self.confirmar
        cr.set_source_rgba(*C["abismo"], .78)
        cr.rectangle(px, 0, pw, h)
        cr.fill()
        ancho, alto = pw - 104 * f, 250 * f
        x, y = px + 52 * f, (h - alto) / 2
        dibujo.redondo(cr, x, y, ancho, alto, 18 * f)
        cr.set_source_rgba(*C["superficie"], .98)
        cr.fill_preserve()
        cr.set_source_rgba(*ROSA, .5)
        cr.set_line_width(1)
        cr.stroke()
        dibujo.texto(cr, "¿Cerrar %s?" % item["nombre"], x + 28 * f, y + 28 * f, 22 * f, C["luz"], Pango.Weight.BOLD,
                     ancho=ancho - 56 * f, una_linea=True)
        dibujo.texto(cr, "Si el juego no guarda solo, entra y guarda la partida antes.", x + 28 * f, y + 70 * f,
                     14 * f, C["tenue"], ancho=ancho - 56 * f)
        tercio = (ancho - 56 * f - 2 * 12 * f) / 3
        by = y + alto - 84 * f
        # En coordenadas del contenido: la confirmacion va fija, sin scroll.
        base = self.scroll - self.arriba
        for i, (ident, texto, accion, color) in enumerate((
                ("confirmar:ir", "Ir a guardar", lambda: self.orden("ir", str(item["ws"])), None),
                ("confirmar:cerrar", "Cerrar ya", lambda: self.cerrar_abierto(item["clave"], True), ROSA),
                ("confirmar:cancelar", "Cancelar", self._cancelar_confirmacion, None))):
            rect = (x + 28 * f + i * (tercio + 12 * f), by, tercio, 56 * f)
            activo = self.elemento(ident, (rect[0], rect[1] + base, rect[2], rect[3]), accion)
            dibujo.redondo(cr, *rect, 14 * f)
            cr.set_source_rgba(*(ROSA if color else C["apagado"]), .25 if color else .7)
            cr.fill()
            self.marco_foco(cr, *rect, 14 * f, f, activo)
            tw, th = dibujo.medir(cr, texto, 15 * f, Pango.Weight.BOLD)
            dibujo.texto(cr, texto, rect[0] + tercio / 2, by + (56 * f - th) / 2, 15 * f, color or C["luz"],
                         Pango.Weight.BOLD, centro=True)

    def _cancelar_confirmacion(self):
        self.confirmar, self.foco_id = None, None
        self.area.queue_draw()

    def _otro_juego(self, juego):
        catalogo.apuntar_lanzado(juego["id"])
        self.lanzar(juego["cmd"], juego=True)

    def dibujar_pie(self, cr, px, h, pw, f):
        y = h - 58 * f
        cr.move_to(px, y - 14 * f)
        cr.line_to(px + pw, y - 14 * f)
        cr.set_source_rgba(*C["amatista"], .12)
        cr.set_line_width(1)
        cr.stroke()
        x = px + 52 * f
        cy = y + 20 * f
        for letra, color, texto in (("A", VERDE, "Usar"), ("B", ROSA, "Volver")):
            dibujo.circulo(cr, x + 13 * f, cy, 13 * f)
            cr.set_source_rgb(*color)
            cr.fill()
            dibujo.texto(cr, letra, x + 13 * f, cy - 8 * f, 12 * f, C["abismo"], Pango.Weight.BOLD, centro=True)
            tw, _ = dibujo.texto(cr, texto, x + 34 * f, cy - 9 * f, 13 * f, C["tenue"])
            x += 34 * f + tw + 24 * f
        dibujo.texto(cr, "↑↓ recorrer · ←→ volumen · Esc", px + pw - 52 * f, cy - 9 * f,
                     13 * f, C["tenue"], derecha=True)


def main():
    if not dibujo.solo_wayland():
        return 1
    otro = otro_abierto()
    if otro:
        os.kill(otro, signal.SIGTERM)  # la misma tecla lo cierra
        return 0
    if not modo.leer_estado():
        return 0                       # fuera del modo gaming no hay menú
    if not Gtk.init_check(sys.argv)[0]:
        return 1
    with open(ruta_pid(), "w") as fh:
        fh.write(str(os.getpid()))
    menu = Menu()
    menu.show_all()
    try:
        Gtk.main()
    finally:
        try:
            if otro_abierto() == os.getpid():
                os.remove(ruta_pid())
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
