#!/usr/bin/env python3
"""
hypr/scripts/programador-menu.py — el menú rápido del modo programador.

Con SUPER + la tecla de al lado del 1 (la misma que el del modo gaming:
menu-rapido.py le pasa el testigo cuando el modo puesto es este). Volver a
pulsarla lo cierra.

    abierto    lo que tienes abierto, cada app con SU volumen (por su árbol de
               procesos, como en el modo gaming), ir y cerrar
    música     cada reproductor (MPRIS) con ⏮ ⏯ ⏭ y el volumen de su app
    controles  micro, captura, «no molestar»
    fijadas    tus apps de siempre: abrir, quitar (X / Supr) y «+ fijar» otra
    y abajo: el inicio entero, y salir del modo

Hereda de menu-rapido.py lo que no es aspecto (moverse con teclado, mando y
ratón, el scroll, el volumen, cerrar lo abierto). El dibujo es otro entero:
un panel de terminal con el tema del modo, nada del violeta del gaming.

Con `--png RUTA [ANCHO ALTO]` se dibuja en un fichero y sale, sin ventana.
"""

import importlib.util
import os
import signal
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.realpath(__file__))
_spec = importlib.util.spec_from_file_location("menu_rapido", os.path.join(AQUI, "menu-rapido.py"))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

import canales  # noqa: E402  (menu-rapido.py ya puso lib/ en el path)
import dibujo  # noqa: E402
import programador  # noqa: E402
import sonido  # noqa: E402
from dibujo import suave  # noqa: E402

dibujo.FUENTE = "MesloLGS Nerd Font Mono"
MODO = os.path.join(AQUI, "modo-programador.py")
NEGRITA = Pango.Weight.BOLD
modo = base.modo                         # el modulo de modo-gaming.py (ventanas, escritorios)


def ruta_pid():
    return os.path.join(canales.RUNTIME, "programador-menu.%s.pid" % (canales.firma() or "sin-sesion"))


def otro_abierto():
    try:
        with open(ruta_pid()) as fh:
            pid = int(fh.read().strip())
        with open("/proc/%d/cmdline" % pid, "rb") as fh:
            if b"programador-menu.py" in fh.read():
                return pid
    except (OSError, ValueError):
        pass
    return None


def modo_puesto():
    try:
        return subprocess.run([sys.executable, MODO, "estado"], capture_output=True, timeout=5).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


class MenuProgramador(base.Menu):
    ESPACIO = "programador-menu"
    MANDO_EXCLUSIVO = False             # detras no hay una partida que proteger

    def cargar_catalogo(self):
        aj = programador.ajustes()
        self.T = programador.tema_rgb(aj["tema"])
        lista = programador.apps_de_trabajo(aj)
        return {"apps": lista, "lanzadores": [], "juegos": [], "fijadas": programador.favoritas(lista)}

    # --- Datos ------------------------------------------------------------------
    def _leer(self):
        """Lo abierto en los escritorios numerados, agrupado por app y con su
        sonido (el mismo reparto que el menu del modo gaming, sin juegos ni
        biblioteca), y los reproductores con la app de cada uno."""
        ventanas = modo.clientes()
        activo = modo.escritorio_activo().get("id")
        flujos = sonido.flujos(sonido._pw_dump())
        abiertos, vistos = [], {}
        for v in ventanas:
            n = modo.num_ws(v)
            if not n or not v.get("address") or modo._clase(v).startswith("programador-"):
                continue
            huella = modo.huella_app(v.get("pid")) or ("ventana", v["address"])
            if huella in vistos:
                vistos[huella]["ventanas"].append(v)
                continue
            item = {"clave": "%s:%s" % huella, "ventanas": [v], "ws": n, "guardada": False,
                    "juego": False, "pid": v.get("pid") or 0, "nombre": self.nombre_de(v),
                    "icono": self.icono_de(v), "activo": n == activo,
                    "titulo": (v.get("title") or "")[:80]}
            vistos[huella] = item
            abiertos.append(item)
        for item in abiertos:
            arbol = sonido.descendientes([x.get("pid") for x in item["ventanas"] if x.get("pid")])
            item["flujos"] = [f for f in flujos if f["pid"] in arbol]
        musica = []
        for r in sonido.reproductores() or []:
            dueño = next((a for a in abiertos
                          if r["pid"] in sonido.descendientes([x.get("pid") for x in a["ventanas"]])), None)
            if dueño is not None:
                dueño["reproductor"] = r
                r["app"], r["flujos"] = dueño, dueño["flujos"]
            else:
                arbol = sonido.descendientes([r["pid"]]) if r["pid"] else set()
                r["app"], r["flujos"] = None, [f for f in flujos if f["pid"] in arbol]
            musica.append(r)
        abiertos = [a for a in abiertos if "reproductor" not in a]
        abiertos.sort(key=lambda x: x["ws"] or 99)
        modos = modo.makoctl("mode") or ""
        datos = {"abiertos": abiertos, "musica": musica, "micro": sonido.micro(),
                 "no_molestar": "no-molestar" in modos.split()}
        GLib.idle_add(self._listos, datos)

    def icono_de(self, v):
        clase = (v.get("class") or "").lower()
        limpia = programador._sin_signos(clase)
        for a in self.cat["apps"]:
            for p in [a.get("icono") or ""] + a.get("pistas", []):
                pl = programador._sin_signos(p)
                if pl and len(pl) >= 4 and (pl == limpia or pl in limpia or limpia in pl):
                    return a.get("icono") or clase
        if clase in programador.TERMINALES or clase == "prog-term":
            return "utilities-terminal"
        return super().icono_de(v)

    # --- Acciones ----------------------------------------------------------------
    def orden(self, *args):
        self.cerrar(lambda: subprocess.Popen([sys.executable, MODO] + list(args), start_new_session=True,
                                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL))

    def abrir_app(self, app):
        self.orden("lanzar", app["id"])

    def quitar_app(self, ident):
        """La X de una fijada: fuera del menu (sigue en el inicio)."""
        if not programador.desfijar(ident):
            return
        antes = self.cat["fijadas"]
        pos = next((i for i, a in enumerate(antes) if a["id"] == ident), 0)
        self.cat["fijadas"] = [a for a in antes if a["id"] != ident]
        quedan = self.cat["fijadas"]
        self.foco_id = "abrir:" + quedan[min(pos, len(quedan) - 1)]["id"] if quedan else "anadir"
        self.area.queue_draw()

    def no_molestar(self):
        modo.makoctl("mode", "-t", "no-molestar")
        self.datos["no_molestar"] = not self.datos.get("no_molestar")
        self.area.queue_draw()

    # --- Dibujo (todo propio: el tema del modo) ------------------------------------
    def t(self, cr, texto, x, y, tam, color, peso=Pango.Weight.NORMAL, **k):
        return dibujo.texto(cr, texto, x, y, tam, self.T[color] if isinstance(color, str) else color, peso, **k)

    def trozos(self, cr, x, y, tam, partes):
        for texto, color, *peso in partes:
            w, _ = self.t(cr, texto, x, y, tam, color, peso[0] if peso else Pango.Weight.NORMAL)
            x += w
        return x

    def caja(self, cr, x, y, w, h, color, alfa=1.0, r=4):
        dibujo.redondo(cr, x, y, w, h, r * self.f)
        cr.set_source_rgba(*self.T[color], alfa)
        cr.fill()

    def marco_foco(self, cr, x, y, w, h, r, f, activo):
        if not activo:
            return
        dibujo.redondo(cr, x, y, w, h, 4 * f)
        cr.set_source_rgba(*self.T["verde"], 1)
        cr.set_line_width(1.5 * f)
        cr.stroke()

    def boton_txt(self, cr, ident, x, y, texto, f, accion, color="texto", tam=13):
        """Un boton de texto entre corchetes, como en una TUI: [ ir ]."""
        tw, th = dibujo.medir(cr, texto, tam * f, NEGRITA)
        rect = (x, y, tw + 24 * f, 30 * f)
        activo = self.elemento(ident, rect, accion)
        self.caja(cr, *rect, "linea" if activo else "panel", 1)
        dibujo.redondo(cr, *rect, 4 * f)
        cr.set_source_rgba(*self.T["verde" if activo else "borde"], 1)
        cr.set_line_width(1.5 * f if activo else 1)
        cr.stroke()
        self.t(cr, texto, x + 12 * f, y + (30 * f - th) / 2, tam * f,
               color if accion else "borde", NEGRITA)
        return rect[0] + rect[2]

    def barra_volumen(self, cr, clave, x, y, ancho, f, flujos):
        """[■■■■■■······] 60% — elegible; izquierda/derecha la mueven."""
        valor = max(((fl["volumen"] or 0) for fl in flujos), default=None)
        if valor is None:
            return
        rect = (x - 8 * f, y - 4 * f, ancho + 16 * f, 26 * f)
        celda = dibujo.medir(cr, "■", 13 * f)[0]
        inicio = x + 34 * f
        celdas = max(6, int((ancho - 34 * f - 70 * f) / celda))
        activo = self.elemento("vol:" + clave, rect, None, "barra", barra=(inicio, celdas * celda))
        if activo:
            self.caja(cr, *rect, "linea", 1)
        self.marco_foco(cr, *rect, 4 * f, f, activo)
        llenos = int(round(valor * celdas))
        self.t(cr, "vol", x, y, 13 * f, "cian")
        self.trozos(cr, inicio, y, 13 * f, [("■" * llenos, "verde"), ("■" * (celdas - llenos), "borde")])
        self.t(cr, "%3d%%" % round(valor * 100), x + ancho, y, 13 * f, "texto", derecha=True)

    def tam(self):
        a = self.area.get_allocation()
        return a.width, a.height

    def dibujar(self, _w, cr):
        self.pintar(cr, *self.tam())

    def pintar(self, cr, w, h):
        import cairo
        f = self.f = max(0.55, min(w / 1920, h / 1080))
        ahora = time.monotonic()
        k = suave((ahora - self.inicio) / base.ENTRADA)
        if self.saliendo is not None:
            k = 1 - suave((ahora - self.saliendo) / base.SALIDA)
        foco_previo = self.foco_id
        self.elementos = []
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.set_source_rgba(0, 0, 0, .35 * k)
        cr.paint()

        pw = min(w, 640 * f)
        px = self.panel_x = w - pw + (1 - k) * 60 * f
        cr.push_group()
        cr.rectangle(px, 0, pw, h)
        cr.set_source_rgba(*self.T["fondo"], .98)
        cr.fill()
        cr.rectangle(px, 0, 1.5 * f, h)
        cr.set_source_rgba(*self.T["verde"], .8)
        cr.fill()

        # La barra de titulo de una terminal
        self.caja(cr, px, 0, pw, 46 * f, "panel", 1, 0)
        for i, c in enumerate(("rojo", "amarillo", "verde")):
            dibujo.circulo(cr, px + 26 * f + i * 22 * f, 23 * f, 6.5 * f)
            cr.set_source_rgba(*self.T[c], .9)
            cr.fill()
        self.t(cr, "~/menu-rapido — modo programador", px + pw / 2 + 20 * f, 14 * f, 13 * f, "tenue", centro=True)
        self.t(cr, time.strftime("%H:%M"), px + pw - 22 * f, 12 * f, 16 * f, "texto", NEGRITA, derecha=True)

        m = 34 * f
        self.trozos(cr, px + m, 66 * f, 15 * f, [("❯ ", "verde", NEGRITA), ("menu ", "azul", NEGRITA),
                                                 ("--rapido", "naranja")])
        self.arriba = 104 * f
        self.alto_visible = h - self.arriba - 52 * f
        cr.save()
        cr.rectangle(px, self.arriba, pw, self.alto_visible)
        cr.clip()
        cr.translate(0, self.arriba - self.scroll)
        fin = self.dibujar_contenido(cr, px + m, 0, pw - 2 * m, f)
        cr.restore()
        self.scroll_max = max(0.0, fin + 20 * f - self.alto_visible)
        self.scroll_objetivo = min(self.scroll_objetivo, self.scroll_max)
        if self.scroll_max > 0:
            total = self.alto_visible
            largo = max(40 * f, total * self.alto_visible / (fin + 20 * f))
            y = self.arriba + (total - largo) * (self.scroll / self.scroll_max)
            self.caja(cr, px + pw - 10 * f, y, 4 * f, largo, "borde", 1, 2)

        # Linea de estado
        ye = h - 40 * f
        self.caja(cr, px, ye, pw, 40 * f, "panel", 1, 0)
        tw, _ = dibujo.medir(cr, " MENÚ ", 13 * f, NEGRITA)
        cr.rectangle(px, ye, tw + 20 * f, 40 * f)
        cr.set_source_rgba(*self.T["verde"], 1)
        cr.fill()
        self.t(cr, " MENÚ ", px + 10 * f, ye + 11 * f, 13 * f, "fondo", NEGRITA)
        self.t(cr, "↑↓ mover · ←→ volumen · Enter usar · Supr quitar · Esc", px + pw - 18 * f, ye + 11 * f,
               12 * f, "tenue", derecha=True)

        cr.pop_group_to_source()
        cr.paint_with_alpha(k)

        ids = [e["id"] for e in self.elementos]
        if foco_previo is None:
            primero = next((i for i, x in enumerate(ids) if x.startswith("abrir:")), 0)
            if ids:
                self.foco, self.foco_id = primero, ids[primero]
                self.area.queue_draw()
        elif foco_previo in ids:
            self.foco = ids.index(foco_previo)
        elif self.elementos:
            self.foco = min(self.foco, len(self.elementos) - 1)
            self.foco_id = self.elementos[self.foco]["id"]
            self.area.queue_draw()

    def seccion(self, cr, x, y, texto, f, extra=""):
        self.trozos(cr, x, y, 14 * f, [("## ", "comentario"), (texto, "morado", NEGRITA),
                                       ("  " + extra if extra else "", "comentario")])
        return y + 32 * f

    def dibujar_contenido(self, cr, x, y, ancho, f):
        abiertos = self.datos.get("abiertos") or []
        y = self.seccion(cr, x, y, "abierto", f, "# %d" % len(abiertos))
        if not abiertos:
            self.t(cr, "# nada abierto todavía", x, y, 13 * f, "comentario")
            y += 34 * f
        for item in abiertos:
            y = self.dibujar_abierto(cr, x, y, ancho, f, item) + 10 * f
        y += 10 * f

        reproductores = self.datos.get("musica") or []
        y = self.seccion(cr, x, y, "música", f)
        if not reproductores:
            self.t(cr, "# no suena nada. Pon algo en tu app de música", x, y, 13 * f, "comentario")
            y += 34 * f
        for r in reproductores:
            y = self.dibujar_musica(cr, x, y, ancho, f, r) + 10 * f
        y += 10 * f

        y = self.seccion(cr, x, y, "controles", f)
        mic = self.datos.get("micro")
        callado = bool(mic and mic[1])
        xb = self.boton_txt(cr, "micro", x, y, ("󰍭 micro: off" if callado else "󰍬 micro: on") if mic else "sin micro",
                            f, self.micro if mic else None, "rojo" if callado else "texto") + 10 * f
        xb = self.boton_txt(cr, "captura", xb, y, "󰄀 captura", f, self.captura) + 10 * f
        dnd = self.datos.get("no_molestar")
        self.boton_txt(cr, "dnd", xb, y, "󰂛 avisos: off" if dnd else "󰂚 avisos: on", f, self.no_molestar,
                       "amarillo" if dnd else "texto")
        y += 50 * f

        fijadas = self.cat["fijadas"]
        y = self.seccion(cr, x, y, "fijadas", f, "# Supr quita · + fija otra")
        cols = 4
        hueco = 10 * f
        lado = (ancho - (cols - 1) * hueco) / cols
        alto = lado * .82
        for i in range(len(fijadas) + 1):
            cx = x + (i % cols) * (lado + hueco)
            cy = y + (i // cols) * (alto + hueco)
            rect = (cx, cy, lado, alto)
            if i < len(fijadas):
                app = fijadas[i]
                rx = 22 * f
                x_rect = (cx + lado - rx - 6 * f, cy + 6 * f, rx, rx)
                self.elemento("quitar:" + app["id"], x_rect, lambda a=app["id"]: self.quitar_app(a), tipo="quitar")
                activo = self.elemento("abrir:" + app["id"], rect, lambda a=app: self.abrir_app(a),
                                       quitar=app["id"])
                self.caja(cr, *rect, "linea" if activo else "panel", 1)
                dibujo.redondo(cr, *rect, 4 * f)
                cr.set_source_rgba(*self.T["verde" if activo else "borde"], 1)
                cr.set_line_width(1.5 * f if activo else 1)
                cr.stroke()
                pix = self.imgs.icono(app.get("icono"), 40 * f) or self.imgs.icono("application-x-executable", 40 * f)
                if pix:
                    Gdk.cairo_set_source_pixbuf(cr, pix, cx + (lado - pix.get_width()) / 2, cy + alto * .16)
                    cr.paint()
                self.t(cr, app["nombre"], cx + lado / 2, cy + alto * .68, 12 * f, "texto", centro=True,
                       ancho=lado - 10 * f, una_linea=True)
                self.t(cr, "×", x_rect[0] + rx / 2, x_rect[1] - 2 * f, 16 * f, "rojo" if activo else "borde",
                       NEGRITA, centro=True)
            else:
                activo = self.elemento("anadir", rect, lambda: self.orden("anadir-app"))
                dibujo.redondo(cr, *rect, 4 * f)
                cr.set_dash([5 * f, 4 * f])
                cr.set_source_rgba(*self.T["verde" if activo else "borde"], 1)
                cr.set_line_width(1.2 * f)
                cr.stroke()
                cr.set_dash([])
                self.t(cr, "+", cx + lado / 2, cy + alto * .12, 34 * f, "verde" if activo else "tenue", centro=True)
                self.t(cr, "fijar", cx + lado / 2, cy + alto * .68, 12 * f, "tenue", centro=True)
        y += ((len(fijadas) + cols) // cols) * (alto + hueco) + 16 * f

        xb = self.boton_txt(cr, "inicio", x, y, " todas las apps (inicio)", f, lambda: self.orden("inicio"),
                            "azul") + 10 * f
        self.boton_txt(cr, "salir", xb, y, " salir del modo", f, lambda: self.orden("toggle"), "rojo")
        return y + 40 * f

    def dibujar_abierto(self, cr, x, y, ancho, f, item):
        clave = item["clave"]
        con_sonido = bool(item.get("flujos"))
        alto = (92 if con_sonido else 62) * f
        self.caja(cr, x, y, ancho, alto, "linea" if item.get("activo") else "panel", 1)
        if item.get("activo"):
            self.caja(cr, x, y + 8 * f, 3 * f, alto - 16 * f, "verde", 1, 1)
        pix = self.imgs.icono(item.get("icono"), 32 * f) or self.imgs.icono("application-x-executable", 32 * f)
        if pix:
            Gdk.cairo_set_source_pixbuf(cr, pix, x + 14 * f, y + 14 * f)
            cr.paint()
        tx = x + 58 * f
        derecha = x + ancho - 12 * f
        botones_x = derecha - 110 * f
        self.trozos(cr, tx, y + 10 * f, 15 * f, [(item["nombre"], "texto", NEGRITA)])
        self.t(cr, "ws %d" % item["ws"], botones_x - 12 * f, y + 12 * f, 12 * f,
               "verde" if item.get("activo") else "tenue", derecha=True)
        self.t(cr, item.get("titulo") or "", tx, y + 34 * f, 12 * f, "tenue",
               ancho=botones_x - tx - 60 * f, una_linea=True)
        usable = not item.get("activo")
        bx = self.boton_txt(cr, "ir:" + clave, botones_x, y + 14 * f, "ir", f,
                            (lambda n=item["ws"]: self.orden("ir", str(n))) if usable else None, "azul") + 8 * f
        self.boton_txt(cr, "cerrar:" + clave, bx, y + 14 * f, "×", f, lambda c=clave: self.cerrar_abierto(c), "rojo")
        if con_sonido:
            self.barra_volumen(cr, clave, tx, y + alto - 30 * f, derecha - tx, f, item["flujos"])
        return y + alto

    def dibujar_musica(self, cr, x, y, ancho, f, r):
        app = r.get("app")
        clave = app["clave"] if app else "musica:" + r["bus"]
        alto = 118 * f
        self.caja(cr, x, y, ancho, alto, "panel", 1)
        portada = self.imgs.cargar(r.get("portada"), 64 * f, 64 * f, cubrir=True)
        if portada:
            cr.save()
            dibujo.redondo(cr, x + 12 * f, y + 12 * f, 64 * f, 64 * f, 4 * f)
            cr.clip()
            Gdk.cairo_set_source_pixbuf(cr, portada, x + 12 * f + (64 * f - portada.get_width()) / 2,
                                        y + 12 * f + (64 * f - portada.get_height()) / 2)
            cr.paint()
            cr.restore()
        else:
            self.t(cr, "󰎈", x + 44 * f, y + 26 * f, 30 * f, "morado", centro=True)
        tx = x + 90 * f
        bx0 = x + ancho - 3 * 42 * f - 6 * f
        sonando = r["estado"] == "Playing"
        self.t(cr, r["titulo"] or "sin título", tx, y + 12 * f, 15 * f, "texto", NEGRITA,
               ancho=bx0 - tx - 8 * f, una_linea=True)
        self.t(cr, r["artista"] or (app or {}).get("nombre", ""), tx, y + 36 * f, 12 * f, "tenue",
               ancho=bx0 - tx - 8 * f, una_linea=True)
        estado = ("▶ sonando" if sonando else "⏸ en pausa") + (" · %s · ws %d" % (app["nombre"], app["ws"])
                                                               if app else "")
        self.t(cr, estado, tx, y + 58 * f, 11 * f, "verde" if sonando else "tenue", ancho=bx0 - tx, una_linea=True)
        for i, (glifo, metodo) in enumerate((("󰒮", "Previous"), ("󰏤" if sonando else "󰐊", "PlayPause"),
                                             ("󰒭", "Next"))):
            self.boton_txt(cr, "musica:%s:%s" % (r["bus"], metodo), bx0 + i * 42 * f, y + 14 * f, glifo, f,
                           lambda b=r["bus"], m=metodo: self.musica(b, m), "verde" if metodo == "PlayPause" else "texto")
        if r.get("flujos"):
            self.barra_volumen(cr, clave, x + 14 * f, y + alto - 30 * f, ancho - 28 * f, f, r["flujos"])
        return y + alto

    def dibujar_confirmacion(self, cr, px, pw, h, f):
        pass                            # aqui no hay juegos que confirmar


def a_png(ruta, ancho, alto):
    """El menu en un PNG, sin ventana (para mirarlo y para las pruebas)."""
    import cairo

    class Area:
        def queue_draw(self):
            pass

    menu = MenuProgramador.__new__(MenuProgramador)
    menu.imgs = dibujo.Imagenes()
    menu.inicio = time.monotonic() - 10
    menu.saliendo = None
    menu.foco, menu.elementos, menu.foco_id = 0, [], None
    menu.scroll = menu.scroll_objetivo = menu.scroll_max = 0.0
    menu.f, menu.arriba, menu.alto_visible, menu.panel_x = 1.0, 104.0, 800.0, 0.0
    menu.confirmar = None
    menu.area = Area()
    menu.cat = menu.cargar_catalogo()
    menu.datos = {"abiertos": [], "musica": [], "micro": None}
    GLib.idle_add = lambda fn, datos: setattr(menu, "datos", datos)
    menu._leer()
    sup = cairo.ImageSurface(cairo.FORMAT_ARGB32, ancho, alto)
    cr = cairo.Context(sup)
    menu.pintar(cr, ancho, alto)
    menu.pintar(cr, ancho, alto)        # el segundo, con el foco ya puesto
    sup.write_to_png(ruta)
    return 0


def main(argv):
    if argv[:1] == ["--png"] and len(argv) >= 2:
        ancho, alto = (int(argv[2]), int(argv[3])) if len(argv) >= 4 else (1920, 1080)
        return a_png(argv[1], ancho, alto)
    if not dibujo.solo_wayland():
        return 1
    otro = otro_abierto()
    if otro:
        os.kill(otro, signal.SIGTERM)   # la misma tecla lo cierra
        return 0
    if not modo_puesto():
        return 0                        # fuera del modo no hay menu
    if not Gtk.init_check(sys.argv)[0]:
        return 1
    with open(ruta_pid(), "w") as fh:
        fh.write(str(os.getpid()))
    menu = MenuProgramador()
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
    sys.exit(main(sys.argv[1:]))
