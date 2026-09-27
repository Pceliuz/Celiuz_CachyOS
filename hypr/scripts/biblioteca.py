#!/usr/bin/env python3
"""
hypr/scripts/biblioteca.py — la biblioteca de juegos del modo gaming.

La abre modo-gaming.py al entrar, en su escritorio (`gaming`), a pantalla
completa. Enseña lo que dice lib/catalogo.py en tres pestañas —juegos,
lanzadores y apps—, con el fondo y el logo del juego seleccionado sacados de la
caché local de Steam, y se maneja con teclado, mando (lib/mando.py) o ratón.

    teclado          mando          ratón
    ← →              cruceta/palanca  rueda        elegir
    Tab / ⇧Tab       LB / RB          clic pestaña sección
    Enter            A                clic / JUGAR lanzar
    Esc              B                            salir del modo (pregunta)

Al lanzar un JUEGO se queda enseñando «Lanzando…» hasta que el juego abre su
ventana AQUI, en el escritorio 1: entonces el vigilante de modo-gaming.py la
cierra, para no gastar nada mientras juegas, y al cerrar el juego la vuelve a
abrir. Una app o un lanzador se abren en el escritorio siguiente. Si en ese rato Steam saca una ventana (la
de «Processing Vulkan shaders»), el vigilante la pone flotando por encima para
que se vea. Una APP o un LANZADOR se abren en un escritorio nuevo y la
biblioteca sigue aquí.

Todo se dibuja a mano con Cairo sobre una sola superficie: así el aspecto es el
de la maqueta aprobada y no el de unos widgets de GTK con tema, y no se
redibuja nada mientras no cambia algo.
"""

import json
import math
import os
import shlex
import shutil
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
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango, PangoCairo  # noqa: E402

AQUI = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(AQUI, "lib"))
import catalogo  # noqa: E402
import dibujo  # noqa: E402
import mando  # noqa: E402
from dibujo import AZUL, C, ROSA, VERDE, suave  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(AQUI))
LANZAR = os.path.join(AQUI, "lanzar.sh")
MODO = os.path.join(AQUI, "modo-gaming.py")
MENU = os.path.join(AQUI, "menu-rapido.py")
CLASE = "celiuz-biblioteca"

ENTRADA, SALIDA, CRUCE = 0.55, 0.32, 0.25     # segundos de cada animacion
ESPERA_LANZAR = 180                            # hasta dar un lanzamiento por perdido

def hyprctl_json(*args):
    try:
        return json.loads(subprocess.run(["hyprctl", "-j"] + list(args), capture_output=True,
                                         text=True, timeout=3).stdout or "null")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def cuando(ultima):
    if not ultima:
        return "Nunca"
    dias = (time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
            - time.mktime(time.localtime(ultima)[:3] + (0, 0, 0, 0, 0, -1))) / 86400
    dias = round(dias)
    if dias <= 0:
        return "Hoy"
    if dias == 1:
        return "Ayer"
    if dias < 30:
        return "Hace %d días" % dias
    return time.strftime("%d/%m/%Y", time.localtime(ultima))


def horas(minutos):
    if not minutos:
        return "—"
    return "%d h" % round(minutos / 60) if minutos >= 60 else "%d min" % minutos


ORIGEN = {"steam": "Steam", "flatpak": "Flatpak", "desktop": "Local"}


class Biblioteca(Gtk.Window):
    def __init__(self):
        super().__init__(title="Biblioteca — modo gaming")
        self.cat = catalogo.catalogo()
        self.secciones = [("JUEGOS", "juegos"), ("LANZADORES", "lanzadores"), ("APPS", "apps")]
        self.sec = 0 if self.cat["juegos"] else (1 if self.cat["lanzadores"] else 2)
        self.sel = {0: 0, 1: 0, 2: 0}
        self.scroll = {0: 0.0, 1: 0.0, 2: 0.0}
        self.imgs = dibujo.Imagenes()
        self.inicio = time.monotonic()
        self.saliendo = None
        self.cambio = (None, 0.0)        # (fondo anterior, cuando se cambio)
        self.lanzando = None
        self.aviso = None                # (texto, hasta)
        self.gpu = ""
        self.steam = False
        self.zonas = []                  # (x, y, w, h, accion) para el raton

        self.area = Gtk.DrawingArea()
        self.area.set_can_focus(True)
        self.area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.SCROLL_MASK
                             | Gdk.EventMask.SMOOTH_SCROLL_MASK)
        self.area.connect("draw", self.dibujar)
        self.area.connect("button-press-event", self.clic)
        self.area.connect("scroll-event", self.rueda)
        self.add(self.area)
        self.connect("key-press-event", self.tecla)
        self.connect("delete-event", self.cerrar)
        self.connect("focus-in-event", self.al_verse)
        self.vista = False
        self.mando = mando.Mando(self.boton).empezar()

        GLib.timeout_add(16, self.animar)
        GLib.timeout_add_seconds(5, self.refrescar_chips)
        self.refrescar_chips()
        # Con el video de entrada delante NO se pide la pantalla completa: se la
        # quitaria (medido en anidado: la biblioteca tapaba el video, y mpv, sin
        # poder dibujarse, se quedaba congelado). Se pide al verse (al_verse).
        if not hay_video():
            self.fullscreen()

    # --- Datos ----------------------------------------------------------------
    def items(self, sec=None):
        return self.cat[self.secciones[self.sec if sec is None else sec][1]]

    def actual(self):
        lista = self.items()
        return lista[self.sel[self.sec]] if lista else None

    def pixbuf(self, ruta, ancho, alto, cubrir=False):
        return self.imgs.cargar(ruta, ancho, alto, cubrir)

    def icono(self, item, tam):
        return self.imgs.icono(item.get("icono") or "", tam)

    texto = staticmethod(dibujo.texto)
    _medir = staticmethod(dibujo.medir)
    redondo = staticmethod(dibujo.redondo)

    def refrescar_chips(self):
        def trabajo():
            steam = "steam" in _comms()
            gpu = ""
            if shutil.which("nvidia-smi"):
                try:
                    r = subprocess.run(["nvidia-smi", "--query-gpu=name,temperature.gpu",
                                        "--format=csv,noheader"], capture_output=True,
                                       text=True, timeout=2).stdout.strip().splitlines()
                    if r:
                        nombre, temp = [x.strip() for x in r[0].split(",")[:2]]
                        nombre = nombre.replace("NVIDIA ", "").replace("GeForce ", "")
                        gpu = "%s · %s °C" % (nombre, temp)
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    pass
            GLib.idle_add(self._chips_listos, steam, gpu)
        threading.Thread(target=trabajo, daemon=True).start()
        return True

    def _chips_listos(self, steam, gpu):
        if (steam, gpu) != (self.steam, self.gpu):
            self.steam, self.gpu = steam, gpu
            self.area.queue_draw()
        return False

    # --- Acciones -------------------------------------------------------------
    def mover(self, paso):
        lista = self.items()
        if not lista:
            return
        nuevo = max(0, min(len(lista) - 1, self.sel[self.sec] + paso))
        if nuevo != self.sel[self.sec]:
            self.cambio = (self.fondo_de(self.actual()), time.monotonic())
            self.sel[self.sec] = nuevo
            self.area.queue_draw()

    def seccion(self, paso):
        nueva = (self.sec + paso) % len(self.secciones)
        if nueva != self.sec:
            self.cambio = (self.fondo_de(self.actual()), time.monotonic())
            self.sec = nueva
            self.area.queue_draw()

    def avisar(self, texto, segundos=4):
        self.aviso = (texto, time.monotonic() + segundos)
        self.area.queue_draw()

    def lanzar(self):
        item = self.actual()
        if not item or self.lanzando:
            return
        try:
            orden = shlex.split(item["cmd"])
        except ValueError:
            orden = item["cmd"].split()
        try:
            # Con el overlay (MangoHud) si es un juego: si este lanzamiento es el
            # que arranca Steam, sus juegos lo heredan.
            entorno = dict(os.environ, **(catalogo.entorno_de_juego()
                                          if item["tipo"] == catalogo.JUEGO else {}))
            subprocess.Popen([LANZAR] + orden, env=entorno, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        except OSError as e:
            self.avisar("No se pudo abrir: %s" % e)
            return
        if item["tipo"] == catalogo.JUEGO:
            catalogo.apuntar_lanzado(item["id"])
            self.lanzando = {"item": item, "desde": time.monotonic()}
            GLib.timeout_add(700, self.vigilar_lanzamiento)
        else:
            self.avisar("Abriendo %s en un escritorio nuevo…" % item["nombre"])
        self.area.queue_draw()

    def vigilar_lanzamiento(self):
        """Cuando el juego abre su ventana en el escritorio 1, el vigilante de
        modo-gaming.py cierra la biblioteca (se va con su animacion, ver
        cerrar()). Aqui solo se pone un tope a la espera."""
        if not self.lanzando or self.saliendo is not None:
            return False
        if time.monotonic() - self.lanzando["desde"] > ESPERA_LANZAR:
            self.lanzando = None
            self.avisar("No llegó a abrirse. Si Steam estaba preparando shaders, "
                        "puede tardar más: vuelve a intentarlo.", 8)
            return False
        return True

    def salir_del_modo(self):
        if self.lanzando:
            self.lanzando = None
            self.avisar("Espera cancelada (el juego puede abrirse igual).")
            return
        subprocess.Popen([MODO, "toggle"], start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def menu(self):
        if os.path.exists(MENU):
            subprocess.Popen([MENU], start_new_session=True, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def cerrar(self, *_):
        """Al pedirle que se cierre (lo hace modo-gaming.py al salir), se va
        con su animacion en vez de desaparecer de golpe."""
        if self.saliendo is None:
            self.saliendo = time.monotonic()
        return True

    def al_verse(self, *_):
        """La primera vez que recibe el foco es cuando de verdad se ve: al
        entrar al modo se abre DETRAS del video de entrada, que tiene la
        pantalla completa y no deja que Hyprland se la de a ella. Entonces la
        pide otra vez y hace ahi su animacion de entrada."""
        if self.vista:
            return False
        self.vista = True
        self.fullscreen()
        self.inicio = time.monotonic()
        self.area.queue_draw()
        return False

    # --- Entrada --------------------------------------------------------------
    def tecla(self, _w, e):
        k = e.keyval
        mayus = e.state & Gdk.ModifierType.SHIFT_MASK
        if k in (Gdk.KEY_Left, Gdk.KEY_a, Gdk.KEY_A):
            self.mover(-1)
        elif k in (Gdk.KEY_Right, Gdk.KEY_d, Gdk.KEY_D):
            self.mover(1)
        elif k == Gdk.KEY_Home:
            self.mover(-10 ** 6)
        elif k == Gdk.KEY_End:
            self.mover(10 ** 6)
        elif k in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
            self.seccion(-1 if (mayus or k == Gdk.KEY_ISO_Left_Tab) else 1)
        elif k in (Gdk.KEY_Up, Gdk.KEY_w, Gdk.KEY_W):
            self.seccion(-1)
        elif k in (Gdk.KEY_Down, Gdk.KEY_s, Gdk.KEY_S):
            self.seccion(1)
        elif k in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            self.lanzar()
        elif k == Gdk.KEY_Escape:
            self.salir_del_modo()
        return True

    def boton(self, accion):
        # El mando se lee del kernel para todo el sistema: solo cuenta si la
        # biblioteca es la ventana con el foco (jugando, o en el navegador,
        # pulsar A no puede lanzar otro juego).
        if not self.is_active() or self.saliendo:
            return
        {"izquierda": lambda: self.mover(-1), "derecha": lambda: self.mover(1),
         "arriba": lambda: self.seccion(-1), "abajo": lambda: self.seccion(1),
         "anterior": lambda: self.seccion(-1), "siguiente": lambda: self.seccion(1),
         "aceptar": self.lanzar, "start": self.lanzar, "atras": self.salir_del_modo,
         "x": self.menu, "select": self.menu}.get(accion, lambda: None)()

    def clic(self, _w, e):
        for x, y, w, h, accion in reversed(self.zonas):
            if x <= e.x <= x + w and y <= e.y <= y + h:
                accion(e)
                return True
        return True

    def rueda(self, _w, e):
        if e.direction in (Gdk.ScrollDirection.UP, Gdk.ScrollDirection.LEFT):
            self.mover(-1)
        elif e.direction in (Gdk.ScrollDirection.DOWN, Gdk.ScrollDirection.RIGHT):
            self.mover(1)
        elif e.direction == Gdk.ScrollDirection.SMOOTH:
            _, dx, dy = e.get_scroll_deltas()
            d = dx if abs(dx) > abs(dy) else dy
            if abs(d) > 0.3:
                self.mover(1 if d > 0 else -1)
        return True

    # --- Animacion ------------------------------------------------------------
    def animar(self):
        ahora = time.monotonic()
        activo = ahora - self.inicio < ENTRADA or ahora - self.cambio[1] < CRUCE \
            or self.lanzando is not None
        if self.saliendo is not None:
            if ahora - self.saliendo >= SALIDA:
                Gtk.main_quit()
                return False
            activo = True
        if self.aviso and ahora > self.aviso[1]:
            self.aviso = None
            activo = True
        # El carrusel se desliza hasta su sitio en vez de saltar.
        for s in self.scroll:
            objetivo = self._scroll_objetivo(s)
            if abs(self.scroll[s] - objetivo) > 0.5:
                self.scroll[s] += (objetivo - self.scroll[s]) * 0.25
                activo = True
            else:
                self.scroll[s] = objetivo
        if activo:
            self.area.queue_draw()
        return True

    # --- Dibujo ---------------------------------------------------------------
    def fondo_de(self, item):
        return (item or {}).get("arte", {}).get("fondo") if item else None

    def _escala(self):
        a = self.area.get_allocation()
        return a.width, a.height, max(0.5, min(a.width / 1920, a.height / 1080))

    def _scroll_objetivo(self, s):
        w, _, f = self._escala()
        lista = self.items(s)
        if not lista:
            return 0.0
        paso = (170 + 26) * f
        sel = self.sel[s]
        visible = max(1, int((w - 144 * f - 218 * f) / paso))
        primero = max(0, min(sel - visible // 2, len(lista) - 1 - visible))
        return max(0, primero) * paso

    def dibujar_fondo(self, cr, w, h, ruta, alfa, zoom):
        pix = self.pixbuf(ruta, w, h, cubrir=True) if ruta else None
        if pix is None:
            return
        cr.save()
        cr.translate(w / 2, h / 2)
        cr.scale(zoom, zoom)
        Gdk.cairo_set_source_pixbuf(cr, pix, -pix.get_width() / 2, -pix.get_height() / 2)
        cr.paint_with_alpha(alfa)
        cr.restore()

    def dibujar(self, _w, cr):
        import cairo
        w, h, f = self._escala()
        ahora = time.monotonic()
        entrada = suave((ahora - self.inicio) / ENTRADA)
        global_alfa = entrada
        if self.saliendo is not None:
            global_alfa = 1 - suave((ahora - self.saliendo) / SALIDA)
        self.zonas = []

        cr.push_group()
        cr.set_source_rgb(*C["abismo"])
        cr.paint()

        item = self.actual()
        # Fondo: el «hero» del juego, con fundido cruzado al cambiar de juego y
        # un zoom que se asienta al entrar.
        zoom = 1.06 - 0.06 * entrada
        k = suave((ahora - self.cambio[1]) / CRUCE)
        if k < 1 and self.cambio[0]:
            self.dibujar_fondo(cr, w, h, self.cambio[0], 1 - k, zoom)
        self.dibujar_fondo(cr, w, h, self.fondo_de(item), k if self.cambio[0] or k < 1 else 1, zoom)

        # Los velos de la maqueta: oscuro a la izquierda y abajo, halo violeta.
        g = cairo.LinearGradient(0, 0, w, 0)
        for pos, a in ((0, .97), (.34, .78), (.62, .15), (1, .35)):
            g.add_color_stop_rgba(pos, *C["abismo"], a)
        cr.set_source(g)
        cr.paint()
        g = cairo.LinearGradient(0, h, 0, 0)
        for pos, a in ((0, 1), (.30, .92), (.58, 0)):
            g.add_color_stop_rgba(pos, *C["abismo"], a)
        cr.set_source(g)
        cr.paint()
        g = cairo.RadialGradient(w * .18, h * .40, 0, w * .18, h * .40, w * .55)
        g.add_color_stop_rgba(0, *C["violeta"], .28)
        g.add_color_stop_rgba(1, *C["violeta"], 0)
        cr.set_source(g)
        cr.paint()

        self.dibujar_barra(cr, w, h, f)
        if item:
            self.dibujar_ficha(cr, w, h, f, item, entrada)
        else:
            self.texto(cr, "No hay nada aquí todavía", 72 * f, 300 * f, 40 * f, C["luz"], Pango.Weight.BOLD)
            self.texto(cr, "Los juegos salen solos de Steam y de las apps instaladas con "
                           "categoría Game.", 72 * f, 360 * f, 16 * f, C["tenue"], ancho=800 * f)
        self.dibujar_pestanas(cr, w, h, f)
        self.dibujar_carrusel(cr, w, h, f, entrada)
        self.dibujar_ayuda(cr, w, h, f)
        self.dibujar_shaders(cr, w, h, f)
        if self.lanzando:
            self.dibujar_lanzando(cr, w, h, f, ahora)
        if self.aviso:
            self.dibujar_aviso(cr, w, h, f)

        cr.pop_group_to_source()
        cr.paint_with_alpha(global_alfa)

    def chip(self, cr, x_derecha, y, f, texto, punto=None):
        pad = 14 * f
        capa_w, capa_h = self._medir(cr, texto, 15 * f)
        ancho = capa_w + pad * 2 + (17 * f if punto else 0)
        x = x_derecha - ancho
        self.redondo(cr, x, y, ancho, 36 * f, 18 * f)
        cr.set_source_rgba(*C["superficie"], .55)
        cr.fill_preserve()
        cr.set_source_rgba(*C["amatista"], .25)
        cr.set_line_width(1)
        cr.stroke()
        tx = x + pad
        if punto:
            cr.arc(tx + 4 * f, y + 18 * f, 4 * f, 0, 2 * math.pi)
            cr.set_source_rgb(*punto)
            cr.fill()
            tx += 17 * f
        self.texto(cr, texto, tx, y + (36 * f - capa_h) / 2, 15 * f, C["tenue"])
        return x - 16 * f

    def dibujar_barra(self, cr, w, h, f):
        y = 36 * f
        cr.save()
        cr.translate(79 * f, y + 18 * f)
        cr.rotate(math.pi / 4)
        cr.rectangle(-7 * f, -7 * f, 14 * f, 14 * f)
        cr.set_source_rgb(*C["neon"])
        cr.fill()
        cr.restore()
        tw, th = self.texto(cr, "MODO GAMING", 102 * f, y + 8 * f, 15 * f, C["neon"],
                            Pango.Weight.BOLD, espaciado=6 * f)
        mw, _ = self.texto(cr, "·  CELIUZ", 102 * f + tw + 14 * f, y + 8 * f, 15 * f, C["tenue"], espaciado=4 * f)
        tope = 102 * f + tw + 14 * f + mw + 30 * f      # los chips no pisan el titulo
        hora = time.strftime("%H:%M")
        hw, _ = self.texto(cr, hora, w - 72 * f, y + 2 * f, 30 * f, C["luz"], Pango.Weight.BOLD, derecha=True)
        x = w - 72 * f - hw - 26 * f
        chips = []
        if self.gpu:
            chips.append((self.gpu, None))
        if self.mando.conectado:
            chips.append(("󰊴  Mando conectado", None))
        if self.steam:
            chips.append(("Steam en segundo plano", VERDE))
        for texto, punto in chips:
            ancho = self._medir(cr, texto, 15 * f)[0] + 28 * f + (17 * f if punto else 0)
            if x - ancho < tope:
                break
            x = self.chip(cr, x, y, f, texto, punto)

    def dibujar_ficha(self, cr, w, h, f, item, entrada):
        x0 = 72 * f
        y = 118 * f + (1 - entrada) * 30 * f
        juegos_ = self.cat["juegos"]
        if item["tipo"] == catalogo.JUEGO:
            etiqueta = "ÚLTIMO JUGADO" if (juegos_ and item is juegos_[0] and item["jugado"]["ultima"]) else "JUEGO"
        else:
            etiqueta = "LANZADOR" if item["tipo"] == catalogo.LANZADOR else "APP PERMITIDA"
        self.texto(cr, etiqueta, x0, y, 14 * f, C["amatista"], espaciado=5 * f)
        y += 36 * f
        logo = self.pixbuf(item.get("arte", {}).get("logo"), 560 * f, 190 * f)
        if logo:
            Gdk.cairo_set_source_pixbuf(cr, logo, x0, y + (190 * f - logo.get_height()) / 2)
            cr.paint()
            y += 190 * f
        else:
            ic = self.icono(item, 120 * f)
            dx = 0
            if ic:
                Gdk.cairo_set_source_pixbuf(cr, ic, x0, y + 35 * f)
                cr.paint()
                dx = ic.get_width() + 28 * f
            self.texto(cr, item["nombre"], x0 + dx, y + 55 * f, 56 * f, C["luz"], Pango.Weight.HEAVY,
                       ancho=900 * f)
            y += 190 * f

        y += 22 * f
        if item["tipo"] == catalogo.JUEGO:
            datos = [(horas(item["jugado"]["minutos"]), "JUGADAS"),
                     (cuando(item["jugado"]["ultima"]), "ÚLTIMA VEZ"),
                     (ORIGEN.get(item.get("origen"), "—"), "ORIGEN")]
        elif item["tipo"] == catalogo.LANZADOR:
            datos = [(ORIGEN.get(item.get("origen"), "—"), "ORIGEN"), ("Tienda y descargas", "PARA")]
        else:
            datos = [("Navegador" if item.get("navegador") else "Tuya", "APP"), ("Un escritorio nuevo", "SE ABRE EN")]
        x = x0
        for grande, peque in datos:
            gw, _ = self.texto(cr, grande, x, y, 34 * f, C["luz"], Pango.Weight.BOLD)
            pw, _ = self.texto(cr, peque, x, y + 48 * f, 13 * f, C["tenue"], espaciado=3 * f)
            x += max(gw, pw) + 40 * f
        y += 96 * f

        verbo = "JUGAR" if item["tipo"] == catalogo.JUEGO else "ABRIR"
        bw, bh = 234 * f, 62 * f
        self.redondo(cr, x0, y, bw, bh, 14 * f)
        import cairo
        g = cairo.LinearGradient(x0, y, x0 + bw, y + bh)
        g.add_color_stop_rgb(0, 0.545, 0.172, 1.0)
        g.add_color_stop_rgb(1, *C["violeta"])
        cr.set_source(g)
        cr.fill_preserve()
        cr.set_source_rgba(*C["neon"], .6)
        cr.set_line_width(2 * f)
        cr.stroke()
        cr.move_to(x0 + 46 * f, y + 21 * f)
        cr.line_to(x0 + 62 * f, y + 31 * f)
        cr.line_to(x0 + 46 * f, y + 41 * f)
        cr.close_path()
        cr.set_source_rgb(1, 1, 1)
        cr.fill()
        self.texto(cr, verbo, x0 + 76 * f, y + 17 * f, 22 * f, (1, 1, 1), Pango.Weight.BOLD, espaciado=4 * f)
        self.zonas.append((x0, y, bw, bh, lambda e: self.lanzar()))

    def dibujar_pestanas(self, cr, w, h, f):
        y = h - 468 * f
        x = 72 * f
        x += self._tecla_lb(cr, x, y, f, "LB") + 30 * f
        for i, (titulo, clave) in enumerate(self.secciones):
            on = i == self.sec
            tw, th = self.texto(cr, titulo, x, y, 17 * f, C["luz"] if on else C["tenue"],
                                Pango.Weight.BOLD if on else Pango.Weight.NORMAL, espaciado=5 * f)
            nw, _ = self.texto(cr, str(len(self.cat[clave])), x + tw + 6 * f, y + 3 * f, 13 * f, C["amatista"])
            if on:
                self.redondo(cr, x, y + th + 8 * f, tw - 5 * f, 3 * f, 1.5 * f)
                cr.set_source_rgb(*C["neon"])
                cr.fill()
            self.zonas.append((x, y - 6 * f, tw + nw + 10 * f, th + 16 * f,
                               lambda e, i=i: self.seccion(i - self.sec)))
            x += tw + nw + 34 * f
        self._tecla_lb(cr, x, y, f, "RB")

    def _tecla_lb(self, cr, x, y, f, texto):
        tw, th = self._medir(cr, texto, 12 * f)
        ancho = tw + 16 * f
        self.redondo(cr, x, y + 1 * f, ancho, 22 * f, 6 * f)
        cr.set_source_rgba(*C["apagado"], 1)
        cr.set_line_width(1)
        cr.stroke()
        self.texto(cr, texto, x + 8 * f, y + 1 * f + (22 * f - th) / 2, 12 * f, C["tenue"])
        return ancho

    def dibujar_carrusel(self, cr, w, h, f, entrada):
        lista = self.items()
        base = h - 93 * f                              # borde inferior de las tarjetas
        x = 72 * f - self.scroll[self.sec] + (1 - entrada) * 80 * f
        for i, item in enumerate(lista):
            sel = i == self.sel[self.sec]
            cw, ch = (218 * f, 327 * f) if sel else (170 * f, 255 * f)
            if x + cw < 0:
                x += cw + 26 * f
                continue
            if x > w:
                break
            y = base - ch
            if sel:
                for r, a in ((26, .10), (16, .16), (8, .22)):
                    self.redondo(cr, x - r * f / 2, y - r * f / 2, cw + r * f, ch + r * f, 18 * f)
                    cr.set_source_rgba(*C["amatista"], a)
                    cr.fill()
            cr.save()
            self.redondo(cr, x, y, cw, ch, 14 * f)
            cr.clip()
            caratula = self.pixbuf((item.get("arte") or {}).get("caratula"), cw, ch, cubrir=True)
            if caratula:
                Gdk.cairo_set_source_pixbuf(cr, caratula, x + (cw - caratula.get_width()) / 2,
                                            y + (ch - caratula.get_height()) / 2)
                cr.paint_with_alpha(1 if sel else .55)
            else:
                import cairo
                g = cairo.LinearGradient(x, y, x + cw, y + ch)
                g.add_color_stop_rgb(0, *C["apagado"])
                g.add_color_stop_rgb(1, *C["abismo"])
                cr.set_source(g)
                cr.paint_with_alpha(1 if sel else .7)
                ic = self.icono(item, 96 * f)
                if ic:
                    Gdk.cairo_set_source_pixbuf(cr, ic, x + (cw - ic.get_width()) / 2, y + ch * .30)
                    cr.paint_with_alpha(1 if sel else .6)
                self.texto(cr, item["nombre"].upper(), x + 12 * f, y + ch * .68, 14 * f,
                           C["luz"], Pango.Weight.BOLD, espaciado=2 * f, alfa=1 if sel else .6,
                           ancho=cw - 24 * f)
            if sel:
                import cairo
                g = cairo.LinearGradient(x, y, x + cw * .4, y + ch * .4)
                g.add_color_stop_rgba(0, 1, 1, 1, .22)
                g.add_color_stop_rgba(1, 1, 1, 1, 0)
                cr.set_source(g)
                cr.paint()
            cr.restore()
            self.redondo(cr, x, y, cw, ch, 14 * f)
            cr.set_source_rgba(*C["neon"], 1) if sel else cr.set_source_rgba(*C["amatista"], .12)
            cr.set_line_width(2 * f if sel else 1)
            cr.stroke()
            if item.get("shaders_pendientes"):
                dibujo.circulo(cr, x + 22 * f, y + 22 * f, 12 * f)
                cr.set_source_rgb(*C["atencion"])
                cr.fill()
                self.texto(cr, "!", x + 22 * f, y + 12 * f, 15 * f, C["abismo"], Pango.Weight.BOLD, centro=True)
            etiqueta = {"steam": "STEAM", "flatpak": "FLATPAK", "desktop": "LOCAL"}.get(item.get("origen"), "")
            if etiqueta:
                ew, eh = self._medir(cr, etiqueta, 11 * f)
                self.redondo(cr, x + cw - ew - 26 * f, y + 10 * f, ew + 16 * f, eh + 8 * f, 6 * f)
                cr.set_source_rgba(*C["abismo"], .85)
                cr.fill()
                self.texto(cr, etiqueta, x + cw - ew - 18 * f, y + 14 * f, 11 * f,
                           AZUL if etiqueta == "STEAM" else C["tenue"])
            self.zonas.append((x, y, cw, ch, lambda e, i=i: self._clic_tarjeta(i)))
            x += cw + 26 * f

    def _clic_tarjeta(self, i):
        if i == self.sel[self.sec]:
            self.lanzar()
        else:
            self.mover(i - self.sel[self.sec])

    def dibujar_ayuda(self, cr, w, h, f):
        y = h - 64 * f
        cr.rectangle(0, y, w, 64 * f)
        cr.set_source_rgba(*C["abismo"], .85)
        cr.fill()
        cr.move_to(0, y)
        cr.line_to(w, y)
        cr.set_source_rgba(*C["amatista"], .14)
        cr.set_line_width(1)
        cr.stroke()
        x = 72 * f
        cy = y + 32 * f
        verbo = "Jugar" if self.sec == 0 else "Abrir"
        botones = [("A", VERDE, verbo), ("B", ROSA, "Salir del modo")]
        if os.path.exists(MENU):
            botones.append(("X", AZUL, "Menú rápido"))
        for letra, color, texto in botones:
            cr.arc(x + 14 * f, cy, 14 * f, 0, 2 * math.pi)
            cr.set_source_rgb(*color)
            cr.fill()
            lw, lh = self._medir(cr, letra, 13 * f, Pango.Weight.BOLD)
            self.texto(cr, letra, x + 14 * f - lw / 2, cy - lh / 2, 13 * f, C["abismo"], Pango.Weight.BOLD)
            tw, th = self.texto(cr, texto, x + 38 * f, cy - 9 * f, 14 * f, C["tenue"])
            x += 38 * f + tw + 30 * f
        x = w - 72 * f
        for tecla, texto in reversed([("← →", "Elegir"), ("Tab", "Sección"), ("Enter", verbo), ("Esc", "Salir")]):
            tw, _ = self._medir(cr, texto, 14 * f)
            x -= tw
            self.texto(cr, texto, x, cy - 9 * f, 14 * f, C["tenue"])
            kw, kh = self._medir(cr, tecla, 12 * f)
            x -= kw + 16 * f + 8 * f
            self.redondo(cr, x, cy - 13 * f, kw + 16 * f, 26 * f, 6 * f)
            cr.set_source_rgba(*C["superficie"], 1)
            cr.fill_preserve()
            cr.set_source_rgba(*C["apagado"], 1)
            cr.stroke()
            self.texto(cr, tecla, x + 8 * f, cy - kh / 2, 12 * f, C["luz"])
            x -= 30 * f

    def dibujar_shaders(self, cr, w, h, f):
        """Lo que Steam tiene pendiente de procesar (la ventana de «Processing
        Vulkan shaders»), para no encontrarselo al darle a jugar. El progreso
        no se sabe desde fuera: solo que esta en cola, y el orden."""
        pendientes = [j for j in self.cat["juegos"] if j.get("shaders_pendientes")]
        if not pendientes:
            return
        ancho = 430 * f
        x, y = w - 72 * f - ancho, 120 * f
        alto = (96 + 30 * min(4, len(pendientes))) * f
        self.redondo(cr, x, y, ancho, alto, 14 * f)
        cr.set_source_rgba(*C["superficie"], .72)
        cr.fill_preserve()
        cr.set_source_rgba(*C["atencion"], .35)
        cr.set_line_width(1)
        cr.stroke()
        self.texto(cr, "SHADERS PENDIENTES EN STEAM", x + 22 * f, y + 18 * f, 13 * f, C["atencion"], espaciado=3 * f)
        yy = y + 48 * f
        for j in pendientes[:4]:
            pct = j.get("shaders_porcentaje")
            self.texto(cr, j["nombre"], x + 22 * f, yy, 15 * f, C["luz"], ancho=ancho - 120 * f, una_linea=True)
            self.texto(cr, "procesando %d %%" % pct if pct is not None else "en cola", x + ancho - 22 * f, yy,
                       13 * f, C["atencion"] if pct is not None else C["tenue"], derecha=True)
            yy += 30 * f
        self.texto(cr, "Steam los prepara mientras no juegas. Si lanzas uno ya, verás su ventana.",
                   x + 22 * f, yy + 2 * f, 11 * f, C["tenue"], ancho=ancho - 44 * f)

    def dibujar_lanzando(self, cr, w, h, f, ahora):
        cr.set_source_rgba(*C["abismo"], .72)
        cr.paint()
        nombre = self.lanzando["item"]["nombre"]
        pulso = (math.sin((ahora - self.lanzando["desde"]) * 4) + 1) / 2
        cx, cy = w / 2, h / 2 - 40 * f
        for i in range(3):
            fase = (ahora * 1.4 + i / 3) % 1
            cr.arc(cx, cy, (30 + 60 * fase) * f, 0, 2 * math.pi)
            cr.set_source_rgba(*C["neon"], (1 - fase) * .5)
            cr.set_line_width(3 * f)
            cr.stroke()
        cr.arc(cx, cy, 18 * f, 0, 2 * math.pi)
        cr.set_source_rgba(*C["neon"], .6 + .4 * pulso)
        cr.fill()
        titulo = "Lanzando %s" % nombre
        tw, _ = self._medir(cr, titulo, 30 * f, Pango.Weight.BOLD)
        self.texto(cr, titulo, cx - tw / 2, cy + 110 * f, 30 * f, C["luz"], Pango.Weight.BOLD)
        sub = "Si Steam está preparando shaders, verás su ventana encima."
        sw, _ = self._medir(cr, sub, 15 * f)
        self.texto(cr, sub, cx - sw / 2, cy + 160 * f, 15 * f, C["tenue"])
        pie = "Esc / B para dejar de esperar"
        pw, _ = self._medir(cr, pie, 13 * f)
        self.texto(cr, pie, cx - pw / 2, cy + 196 * f, 13 * f, C["tenue"], alfa=.8)

    def dibujar_aviso(self, cr, w, h, f):
        texto = self.aviso[0]
        tw, th = self._medir(cr, texto, 15 * f)
        tw = min(tw, 900 * f)
        x, y = w - 72 * f - tw - 40 * f, h - 140 * f
        self.redondo(cr, x, y, tw + 40 * f, th + 28 * f, 12 * f)
        cr.set_source_rgba(*C["superficie"], .92)
        cr.fill_preserve()
        cr.set_source_rgba(*C["atencion"], .5)
        cr.set_line_width(1)
        cr.stroke()
        self.texto(cr, texto, x + 20 * f, y + 14 * f, 15 * f, C["luz"], ancho=900 * f)


def _comms():
    """Los nombres de todos los procesos (un proceso puede irse a mitad)."""
    nombres = set()
    for pid in os.listdir("/proc"):
        if pid.isdigit():
            try:
                with open("/proc/%s/comm" % pid) as fh:
                    nombres.add(fh.read().strip())
            except OSError:
                continue
    return nombres


def hay_video():
    return any((c.get("class") or "") == "celiuz-video" for c in hyprctl_json("clients") or [])


def ya_abierta():
    for c in hyprctl_json("clients") or []:
        if (c.get("class") or "") == CLASE:
            return True
    return False


def main():
    if not dibujo.solo_wayland():
        print("biblioteca: no hay sesion Wayland donde dibujar", file=sys.stderr)
        return 1
    # Una sola por sesion, con un cerrojo y no preguntando «¿hay ya una
    # ventana?»: eso llega tarde. Paso en anidado al terminar el video de
    # entrada: la abrian a la vez modo-gaming.py y su vigilante (que veia el
    # escritorio 1 vacio), las dos preguntaban antes de que la otra tuviera
    # ventana, y salian dos bibliotecas.
    import fcntl
    sys.path.insert(0, os.path.join(AQUI, "lib"))
    import canales
    cerrojo = open(os.path.join(canales.RUNTIME, "biblioteca.%s.lock" % (canales.firma() or "sin-sesion")), "w")
    try:
        fcntl.flock(cerrojo, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0
    if ya_abierta():
        return 0
    GLib.set_prgname(CLASE)
    if not Gtk.init_check(sys.argv)[0]:
        print("biblioteca: no hay pantalla donde dibujar", file=sys.stderr)
        return 1
    ventana = Biblioteca()
    ventana.connect("destroy", Gtk.main_quit)
    ventana.show_all()
    ventana.area.grab_focus()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
