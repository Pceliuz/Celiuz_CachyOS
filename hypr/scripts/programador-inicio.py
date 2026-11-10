#!/usr/bin/env python3
"""
hypr/scripts/programador-inicio.py — el inicio del modo programador.

Sale al entrar al modo (modo-programador.py) y, dentro de el, con SUPER+B:
un lanzador a pantalla completa con las apps de trabajo por secciones
(lib/programador.py). Volver a pulsarlo lo cierra.

Por dentro se ve como un editor, y a proposito nada como la biblioteca del modo
gaming (lo pidio el usuario): pestañas arriba, numeros de linea, un explorador
con una carpeta por seccion, un buscador que es un prompt, y una linea de
estado como la de vim. A la derecha, lo del momento: CPU, memoria, disco, que
pantalla es la de trabajo y que esta sonando.

    escribir        filtra (todas las secciones; como una paleta de ordenes)
    flechas         moverse por las apps
    Tab / ⇧Tab      seccion siguiente / anterior
    Enter           abrir
    ⇧Enter          abrirla en la OTRA pantalla (el anime, la musica)
    Esc             borra lo escrito; sin nada escrito, cierra

Con `--png RUTA [ANCHO ALTO]` se dibuja en un fichero y sale, sin crear
ninguna ventana: es como se comprueba el aspecto sin tocar la sesion.
"""

import json
import os
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
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

AQUI = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(AQUI, "lib"))
import canales  # noqa: E402
import dibujo  # noqa: E402
import programador  # noqa: E402
import sonido  # noqa: E402
from dibujo import suave  # noqa: E402

dibujo.FUENTE = "MesloLGS Nerd Font Mono"   # todo en monoespaciada: es una terminal
MODO = os.path.join(AQUI, "modo-programador.py")
ENTRADA, SALIDA = 0.28, 0.14
NEGRITA = Pango.Weight.BOLD
ICONO_SECCION = {"codigo": "\uf121", "sistemas": "\uf233", "seguridad": "\U000f0483", "documentos": "\U000f0219",
                 "web": "\U000f075a", "terminal": "\uf120", "mias": "\uf005"}


def ruta_pid():
    return os.path.join(canales.RUNTIME, "programador-inicio.%s.pid" % (canales.firma() or "sin-sesion"))


def otro_abierto():
    try:
        with open(ruta_pid()) as fh:
            pid = int(fh.read().strip())
        with open("/proc/%d/cmdline" % pid, "rb") as fh:
            if b"programador-inicio.py" in fh.read():
                return pid
    except (OSError, ValueError):
        pass
    return None


# --- Lo de la derecha (lo del momento) ---------------------------------------------
def _cpu():
    with open("/proc/stat") as fh:
        campos = [int(x) for x in fh.readline().split()[1:]]
    return sum(campos), campos[3] + (campos[4] if len(campos) > 4 else 0)


def memoria():
    datos = {}
    try:
        with open("/proc/meminfo") as fh:
            for linea in fh:
                k, v = linea.split(":", 1)
                datos[k] = int(v.split()[0])
        total = datos["MemTotal"]
        return (total - datos.get("MemAvailable", 0)) / total, total / 1048576
    except (OSError, KeyError, ValueError, ZeroDivisionError):
        return None, None


def disco():
    try:
        s = os.statvfs(os.path.expanduser("~"))
        return 1 - s.f_bavail / s.f_blocks, s.f_blocks * s.f_frsize / 1e9
    except (OSError, ZeroDivisionError):
        return None, None


def pantallas(trabajo):
    """[(nombre, es la de trabajo)] de las pantallas encendidas."""
    try:
        r = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True, timeout=3)
        lista = json.loads(r.stdout or "[]")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []
    if not any(m.get("name") == trabajo for m in lista):
        trabajo = next((m.get("name") for m in lista if m.get("focused")), None)
    return [(m.get("name", "?"), m.get("name") == trabajo) for m in lista]


def estado_modo():
    try:
        r = subprocess.run([sys.executable, MODO, "estado", "--json"], capture_output=True, text=True, timeout=5)
        return json.loads(r.stdout or "{}")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {}


class Inicio:
    """El inicio, sin GTK: los datos, la navegacion y el dibujo. La ventana
    (abajo, `Ventana`) solo le pasa teclas y le pide que se pinte."""

    def __init__(self, repintar=lambda: None, cerrar=lambda: None):
        self.repintar, self.al_cerrar = repintar, cerrar
        aj = programador.ajustes()
        self.T = programador.tema_rgb(aj["tema"])
        self.todas = programador.apps_de_trabajo(aj)
        self.secciones = programador.por_seccion(self.todas)
        self.seccion = next((i for i, s in enumerate(self.secciones) if s[4]), 0)
        self.busqueda = ""
        self.foco = 0
        self.scroll = 0
        self.columnas = 1
        self.rects = []                # [(rect, accion)] del ultimo dibujo
        self.imgs = dibujo.Imagenes()
        self.inicio = time.monotonic()
        self.saliendo = None
        est = estado_modo()
        self.desde = est.get("desde") or int(time.time())
        self.trabajo = est.get("pantalla")
        self.datos = {"cpu": None, "ram": (None, None), "disco": (None, None),
                      "pantallas": [], "musica": []}
        self._cpu_antes = None
        self.usuario = "%s@%s" % (os.environ.get("USER") or "yo", os.uname().nodename.lower())

    # --- Datos ------------------------------------------------------------------
    def leer(self):
        try:
            total, libre = _cpu()
            if self._cpu_antes:
                dt, dl = total - self._cpu_antes[0], libre - self._cpu_antes[1]
                cpu = max(0.0, min(1.0, 1 - dl / dt)) if dt > 0 else None
            else:
                cpu = None
            self._cpu_antes = (total, libre)
        except (OSError, ValueError, IndexError):
            cpu = None
        try:
            musica = sonido.reproductores() or []
        except Exception:
            musica = []
        self.datos = {"cpu": cpu, "ram": memoria(), "disco": disco(),
                      "pantallas": pantallas(self.trabajo), "musica": musica}

    def visibles(self):
        if self.busqueda:
            return programador.buscar(self.todas, self.busqueda)
        return self.secciones[self.seccion][4]

    def otra_pantalla(self):
        for nombre, es_trabajo in self.datos["pantallas"]:
            if not es_trabajo:
                return nombre
        return None

    # --- Acciones ----------------------------------------------------------------
    def abrir(self, app, otra=False):
        orden = [sys.executable, MODO, "lanzar", app["id"]]
        pantalla = self.otra_pantalla() if otra else None
        if pantalla:
            orden += ["--pantalla", pantalla]
        self.cerrar(lambda: subprocess.Popen(orden, start_new_session=True, stdin=subprocess.DEVNULL,
                                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

    def cerrar(self, despues=None):
        if self.saliendo is None:
            self.saliendo = time.monotonic()
            self.despues = despues
            self.repintar()

    def mover(self, dx, dy):
        n = len(self.visibles())
        if not n:
            return
        f = self.foco + dx + dy * self.columnas
        if dx and (f // self.columnas != self.foco // self.columnas):
            f = self.foco               # izquierda/derecha no saltan de fila
        self.foco = max(0, min(n - 1, f))
        self.repintar()

    def cambiar_seccion(self, paso):
        self.busqueda = ""
        self.seccion = (self.seccion + paso) % len(self.secciones)
        self.foco = self.scroll = 0
        self.repintar()

    def tecla(self, nombre, texto="", shift=False, ctrl=False):
        """Una tecla por su nombre de Gdk (Return, Escape, Up...) y lo que
        escribe. Devuelve True si la uso."""
        if nombre in ("Escape",):
            if self.busqueda:
                self.busqueda, self.foco = "", 0
                self.repintar()
            else:
                self.cerrar()
        elif nombre in ("Return", "KP_Enter"):
            lista = self.visibles()
            if lista:
                self.abrir(lista[min(self.foco, len(lista) - 1)], otra=shift)
        elif nombre == "BackSpace":
            if ctrl:
                self.busqueda = ""
            self.busqueda = self.busqueda[:-1]
            self.foco = 0
            self.repintar()
        elif nombre in ("Tab", "ISO_Left_Tab"):
            self.cambiar_seccion(-1 if shift or nombre == "ISO_Left_Tab" else 1)
        elif nombre == "Left":
            self.mover(-1, 0)
        elif nombre == "Right":
            self.mover(1, 0)
        elif nombre == "Up":
            self.mover(0, -1)
        elif nombre == "Down":
            self.mover(0, 1)
        elif texto and texto.isprintable() and not ctrl:
            self.busqueda += texto
            self.foco = 0
            self.repintar()
        else:
            return False
        return True

    def clic(self, x, y):
        for (rx, ry, rw, rh), accion in self.rects:
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                accion()
                return

    def rueda(self, paso):
        self.mover(0, paso)

    # --- Dibujo ------------------------------------------------------------------
    def t(self, cr, texto, x, y, tam, color, peso=Pango.Weight.NORMAL, alfa=1.0, **k):
        return dibujo.texto(cr, texto, x, y, tam, self.T[color] if isinstance(color, str) else color,
                            peso, alfa=alfa, **k)

    def trozos(self, cr, x, y, tam, partes):
        """Texto con colores por trozos, seguidos (resaltado de sintaxis)."""
        for texto, color, *peso in partes:
            w, _ = self.t(cr, texto, x, y, tam, color, peso[0] if peso else Pango.Weight.NORMAL)
            x += w
        return x

    def caja(self, cr, x, y, w, h, color, alfa=1.0, r=0):
        if r:
            dibujo.redondo(cr, x, y, w, h, r)
        else:
            cr.rectangle(x, y, w, h)
        cr.set_source_rgba(*self.T[color], alfa)
        cr.fill()

    def barra_ascii(self, cr, x, y, tam, valor, ancho_c, color):
        """[|||||·····] 42% — como htop."""
        llenos = int(round((valor or 0) * ancho_c))
        x = self.trozos(cr, x, y, tam, [("[", "tenue"), ("|" * llenos, color, NEGRITA),
                                         ("·" * (ancho_c - llenos), "borde"), ("]", "tenue")])
        self.t(cr, " %3d%%" % round((valor or 0) * 100) if valor is not None else "   …", x, y, tam, "texto")

    def pintar(self, cr, w, h):
        import cairo
        f = max(0.55, min(w / 1920, h / 1080))
        ahora = time.monotonic()
        k = suave((ahora - self.inicio) / ENTRADA)
        if self.saliendo is not None:
            k = 1 - suave((ahora - self.saliendo) / SALIDA)
        self.rects = []
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.push_group()
        cr.set_source_rgba(*self.T["fondo"], .97)
        cr.paint()

        # Pestañas
        alto_tabs = 44 * f
        self.caja(cr, 0, 0, w, alto_tabs, "panel")
        x = 0
        for i, (glifo, nombre, color) in enumerate((("\uf121 ", "inicio.py", "verde"), ("\uf48a ", "LEEME.md", "tenue"))):
            tw, _ = dibujo.medir(cr, glifo + nombre + "  ●", 14 * f)
            ancho = tw + 44 * f
            if i == 0:
                self.caja(cr, x, 0, ancho, alto_tabs, "fondo")
                self.caja(cr, x, 0, ancho, 2 * f, "verde")
            self.trozos(cr, x + 20 * f, 13 * f, 14 * f, [(glifo, color), (nombre, "texto" if i == 0 else "tenue"),
                                                        ("  ●" if i == 0 else "", "naranja")])
            x += ancho
            cr.rectangle(x, 0, 1, alto_tabs)
            cr.set_source_rgba(*self.T["borde"], 1)
            cr.fill()
        reloj = time.strftime("%H:%M")
        tw, _ = self.t(cr, reloj, w - 24 * f, 11 * f, 17 * f, "texto", NEGRITA, derecha=True)
        self.t(cr, self.usuario, w - 40 * f - tw, 14 * f, 13 * f, "tenue", derecha=True)
        cr.rectangle(0, alto_tabs, w, 1)
        cr.set_source_rgba(*self.T["borde"], 1)
        cr.fill()

        # Linea de estado (abajo, como vim)
        alto_estado = 34 * f
        ye = h - alto_estado
        self.caja(cr, 0, ye, w, alto_estado, "panel")
        etiqueta = " BUSCAR " if self.busqueda else " INICIO "
        tw, _ = dibujo.medir(cr, etiqueta, 13 * f, NEGRITA)
        self.caja(cr, 0, ye, tw + 20 * f, alto_estado, "amarillo" if self.busqueda else "verde")
        self.t(cr, etiqueta, 10 * f, ye + 8 * f, 13 * f, "fondo", NEGRITA)
        lista = self.visibles()
        carpeta = "resultados" if self.busqueda else self.secciones[self.seccion][1]
        self.trozos(cr, tw + 36 * f, ye + 8 * f, 13 * f, [("\ue0a0 modo-programador", "morado"), ("  │  ", "borde"),
                                                         ("~/trabajo/" + carpeta, "texto"), ("  │  ", "borde"),
                                                         ("%d app%s" % (len(lista), "" if len(lista) == 1 else "s"), "tenue")])
        ayuda = "Enter abrir · ⇧Enter otra pantalla · Tab sección · Esc %s" % ("borrar" if self.busqueda else "cerrar")
        self.t(cr, ayuda + "   utf-8  " + reloj, w - 20 * f, ye + 8 * f, 13 * f, "tenue", derecha=True)

        # Medidas de las columnas
        gutter = 64 * f
        lateral = 300 * f
        derecho = min(400 * f, w * .24)
        cx0 = gutter + lateral
        cx1 = w - derecho
        arriba = alto_tabs + 26 * f
        paso = 30 * f

        # Numeros de linea (el de la linea con el foco, encendido)
        lineas = int((ye - arriba) / paso)
        foco_linea = 4 + (min(self.foco, max(0, len(lista) - 1)) // max(1, self.columnas) - self.scroll) * 4
        for i in range(lineas):
            self.t(cr, str(i + 1), gutter - 16 * f, arriba + i * paso, 13 * f,
                   "verde" if i + 1 == foco_linea else "borde", derecha=True)
        cr.rectangle(gutter, alto_tabs, 1, ye - alto_tabs)
        cr.set_source_rgba(*self.T["borde"], 1)
        cr.fill()

        self.pintar_explorador(cr, gutter, arriba, lateral, ye, f, paso)
        self.pintar_centro(cr, cx0, arriba, cx1 - cx0, ye, f, paso, ahora, lista)
        self.pintar_derecha(cr, cx1, arriba, derecho, ye, f, paso)

        cr.pop_group_to_source()
        cr.paint_with_alpha(k)

    def pintar_explorador(self, cr, x, y, ancho, fin, f, paso):
        self.caja(cr, x + 1, y - 26 * f, ancho - 1, fin - y + 26 * f, "panel", .55)
        self.t(cr, "EXPLORADOR", x + 22 * f, y, 12 * f, "tenue", NEGRITA, espaciado=2 * f)
        y += paso * 1.3
        self.trozos(cr, x + 22 * f, y, 14 * f, [("▾ ", "tenue"), ("\uf07c ", "amarillo"), ("~/trabajo", "texto", NEGRITA)])
        y += paso * 1.2
        for i, (clave, carpeta, titulo, color, apps_) in enumerate(self.secciones):
            activa = i == self.seccion and not self.busqueda
            if activa:
                self.caja(cr, x + 1, y - 6 * f, ancho - 1, paso + 2 * f, "linea")
                self.caja(cr, x + 1, y - 6 * f, 3 * f, paso + 2 * f, "verde")
            self.trozos(cr, x + 40 * f, y, 14 * f, [(ICONO_SECCION.get(clave, "") + " ", color),
                                                    (carpeta, "texto" if activa else "tenue",
                                                     NEGRITA if activa else Pango.Weight.NORMAL)])
            self.t(cr, str(len(apps_)), x + ancho - 22 * f, y, 12 * f, color if apps_ else "borde", derecha=True)
            self.rects.append(((x, y - 6 * f, ancho, paso), lambda n=i: self._elegir_seccion(n)))
            y += paso + 4 * f
        y += paso * .6
        titulo = self.secciones[self.seccion][2]
        self.t(cr, "# " + titulo.lower(), x + 22 * f, y, 13 * f, "comentario")
        self.t(cr, "# Tab cambia de carpeta", x + 22 * f, y + paso * .8, 13 * f, "comentario")

    def _elegir_seccion(self, n):
        self.busqueda, self.seccion, self.foco, self.scroll = "", n, 0, 0
        self.repintar()

    def pintar_centro(self, cr, x, y, ancho, fin, f, paso, ahora, lista):
        m = 40 * f
        x += m
        ancho -= 2 * m
        sesion = int(time.time() - self.desde)
        self.trozos(cr, x, y, 14 * f, [("# modo programador · %d apps · sesión %02d:%02d:%02d"
                                        % (len(self.todas), sesion // 3600, sesion // 60 % 60, sesion % 60),
                                        "comentario")])
        y += paso
        clave, carpeta, titulo, color, _ = self.secciones[self.seccion]
        if self.busqueda:
            self.trozos(cr, x, y, 18 * f, [("buscar", "azul", NEGRITA), ("(", "texto"),
                                           ('"%s"' % self.busqueda, "verde"), (")", "texto"),
                                           ("  # %d resultado%s" % (len(lista), "" if len(lista) == 1 else "s"), "comentario")])
        else:
            self.trozos(cr, x, y, 18 * f, [("def ", "morado", NEGRITA), (clave, "azul", NEGRITA), ("():", "texto"),
                                           ("  # " + titulo, "comentario")])
        y += paso * 1.5
        # El prompt de busqueda, con su cursor de bloque parpadeando
        alto_p = 46 * f
        self.caja(cr, x, y, ancho, alto_p, "panel", 1, 4 * f)
        dibujo.redondo(cr, x, y, ancho, alto_p, 4 * f)
        cr.set_source_rgba(*self.T["verde" if self.busqueda else "borde"], 1)
        cr.set_line_width(1)
        cr.stroke()
        px = self.trozos(cr, x + 18 * f, y + 12 * f, 17 * f, [("❯ ", "verde", NEGRITA)])
        if self.busqueda:
            px = self.trozos(cr, px, y + 12 * f, 17 * f, [(self.busqueda, "texto")])
        else:
            self.t(cr, "escribe para buscar en todo…", px + 14 * f, y + 12 * f, 17 * f, "tenue", alfa=.7)
        if int(ahora * 1.9) % 2 == 0 or self.busqueda:
            self.caja(cr, px + 1, y + 11 * f, 10 * f, 22 * f, "verde", .9)
        y += alto_p + 28 * f

        if not lista:
            if self.busqueda:
                self.t(cr, "# nada coincide con «%s»" % self.busqueda, x, y, 15 * f, "comentario")
            elif clave == programador.SEGURIDAD:
                self.t(cr, "# nada instalado todavía. Aparecerán aquí al instalarlas:", x, y, 15 * f, "comentario")
                self.t(cr, "#   " + programador.SUGERENCIAS_SEGURIDAD, x, y + paso, 15 * f, "comentario")
            elif clave == programador.MIAS:
                self.t(cr, "# vacío: añade apps desde el menú rápido (SUPER + la tecla de al lado del 1)",
                       x, y, 15 * f, "comentario")
            else:
                self.t(cr, "pass  # nada instalado en esta sección", x, y, 15 * f, "comentario")
            return

        # La cuadricula
        hueco = 16 * f
        cw = 270 * f
        self.columnas = max(1, int((ancho + hueco) / (cw + hueco)))
        cw = (ancho - (self.columnas - 1) * hueco) / self.columnas
        ch = 104 * f
        filas_vistas = max(1, int((fin - y - 10 * f + hueco) / (ch + hueco)))
        fila_foco = min(self.foco, len(lista) - 1) // self.columnas
        if fila_foco < self.scroll:
            self.scroll = fila_foco
        elif fila_foco >= self.scroll + filas_vistas:
            self.scroll = fila_foco - filas_vistas + 1
        for i, app in enumerate(lista):
            fila, col = divmod(i, self.columnas)
            if not self.scroll <= fila < self.scroll + filas_vistas:
                continue
            ax = x + col * (cw + hueco)
            ay = y + (fila - self.scroll) * (ch + hueco)
            activo = i == self.foco
            self.caja(cr, ax, ay, cw, ch, "linea" if activo else "panel", 1, 6 * f)
            dibujo.redondo(cr, ax, ay, cw, ch, 6 * f)
            cr.set_source_rgba(*self.T["verde" if activo else "borde"], 1)
            cr.set_line_width(1.5 * f if activo else 1)
            cr.stroke()
            if activo:
                self.caja(cr, ax, ay + 10 * f, 3 * f, ch - 20 * f, "verde")
            pix = self.imgs.icono(app.get("icono"), 44 * f) or self.imgs.icono(
                "utilities-terminal" if app["terminal"] else "application-x-executable", 44 * f)
            if pix:
                Gdk.cairo_set_source_pixbuf(cr, pix, ax + 18 * f, ay + (ch - pix.get_height()) / 2)
                cr.paint()
            tx = ax + 76 * f
            seccion_color = next((s[3] for s in self.secciones if s[0] == app["seccion"]), "texto")
            self.t(cr, app["nombre"], tx, ay + 20 * f, 16 * f, "texto", NEGRITA,
                   ancho=cw - 90 * f, una_linea=True)
            orden = os.path.basename((app["cmd"] or "").split()[0]) if app["cmd"] else ""
            self.trozos(cr, tx, ay + 48 * f, 13 * f, [("$ ", seccion_color), (orden[:24], "tenue")])
            etiquetas = []
            if app["terminal"]:
                etiquetas.append(("TTY", "cian"))
            if app.get("navegador"):
                etiquetas.append(("WEB", "morado"))
            if app.get("mia"):
                etiquetas.append(("TUYA", "naranja"))
            if self.busqueda:
                etiquetas.append((app["seccion"], seccion_color))
            ex = tx
            for texto, c in etiquetas:
                tw, _ = dibujo.medir(cr, texto, 10 * f, NEGRITA)
                self.caja(cr, ex, ay + 74 * f, tw + 12 * f, 17 * f, c, .16, 3 * f)
                self.t(cr, texto, ex + 6 * f, ay + 75 * f, 10 * f, c, NEGRITA)
                ex += tw + 18 * f
            self.rects.append(((ax, ay, cw, ch), lambda a=app: self.abrir(a)))
        quedan = (len(lista) - 1) // self.columnas + 1 - (self.scroll + filas_vistas)
        if quedan > 0:
            self.t(cr, "# … %d fila%s más (↓)" % (quedan, "s" if quedan > 1 else ""), x,
                   fin - 30 * f, 13 * f, "comentario")

    def pintar_derecha(self, cr, x, y, ancho, fin, f, paso):
        cr.rectangle(x, y - 26 * f, 1, fin - y + 26 * f)
        cr.set_source_rgba(*self.T["borde"], 1)
        cr.fill()
        x += 28 * f
        ancho -= 56 * f
        tam = 14 * f
        celdas = max(8, int((ancho - 160 * f) / dibujo.medir(cr, "|", tam)[0]))

        def titulo(texto, yy):
            self.t(cr, texto, x, yy, 12 * f, "tenue", NEGRITA, espaciado=2 * f)
            return yy + paso

        y = titulo("SISTEMA", y)
        d = self.datos
        for etiqueta, valor, color, extra in (
                ("cpu ", d["cpu"], "verde", ""),
                ("mem ", d["ram"][0], "azul", " de %.0f G" % d["ram"][1] if d["ram"][1] else ""),
                ("disk", d["disco"][0], "amarillo", " de %.0f G" % d["disco"][1] if d["disco"][1] else "")):
            self.t(cr, etiqueta, x, y, tam, "cian")
            self.barra_ascii(cr, x + 56 * f, y, tam, valor, celdas, color)
            y += paso
            if extra:
                self.t(cr, "     " + extra.strip(), x, y - 8 * f, 11 * f, "comentario")
                y += paso * .45
        y += paso * .5

        y = titulo("PANTALLAS", y)
        if not d["pantallas"]:
            self.t(cr, "…", x, y, tam, "tenue")
            y += paso
        for nombre, es_trabajo in d["pantallas"]:
            self.trozos(cr, x, y, tam, [("● " if es_trabajo else "○ ", "verde" if es_trabajo else "morado"),
                                        (nombre + "  ", "texto"),
                                        ("trabajo" if es_trabajo else "libre · ⇧Enter abre aquí",
                                         "tenue")])
            y += paso
        y += paso * .5

        y = titulo("SONANDO", y)
        musica = [r for r in d["musica"] if r.get("titulo")]
        if not musica:
            self.t(cr, "# nada. ¿un lofi?", x, y, tam, "comentario")
            y += paso
        for r in musica[:2]:
            sonando = r.get("estado") == "Playing"
            self.trozos(cr, x, y, tam, [("󰎈 " if sonando else "󰏤 ", "verde" if sonando else "tenue")])
            self.t(cr, r["titulo"], x + 26 * f, y, tam, "texto", NEGRITA, ancho=ancho - 26 * f, una_linea=True)
            y += paso * .8
            self.t(cr, r.get("artista") or "", x + 26 * f, y, 12 * f, "tenue", ancho=ancho - 26 * f, una_linea=True)
            y += paso
        y += paso * .5

        y = titulo("ATAJOS", y)
        for combo, que in (("SUPER+B", "este inicio"), ("SUPER+`", "menú rápido"),
                           ("SUPER+Enter", "terminal"), ("SUPER+P", "salir del modo")):
            self.trozos(cr, x, y, 13 * f, [(combo.ljust(13), "amarillo"), (que, "tenue")])
            y += paso * .85


# --- La ventana ----------------------------------------------------------------------
class Ventana(Gtk.Window):
    def __init__(self):
        super().__init__()
        from gi.repository import GtkLayerShell
        self.inicio = Inicio(self.repintar, self.cerrar)
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, "programador-inicio")
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
        self.area.connect("draw", lambda _w, cr: self.inicio.pintar(cr, self.area.get_allocated_width(),
                                                                     self.area.get_allocated_height()))
        self.area.connect("button-press-event", lambda _w, e: self.inicio.clic(e.x, e.y))
        self.area.connect("scroll-event", self.rueda)
        self.add(self.area)
        self.connect("key-press-event", self.tecla)
        signal.signal(signal.SIGTERM, lambda *_: GLib.idle_add(self.inicio.cerrar))
        self.refrescar()
        GLib.timeout_add(1000, self.refrescar)
        GLib.timeout_add(16, self.animar)
        GLib.timeout_add(260, self.parpadeo)

    def repintar(self):
        self.area.queue_draw()

    def cerrar(self):
        self.inicio.cerrar()

    def refrescar(self):
        def leer():
            self.inicio.leer()
            GLib.idle_add(self.repintar)
        threading.Thread(target=leer, daemon=True).start()
        return self.inicio.saliendo is None

    def parpadeo(self):
        self.repintar()
        return self.inicio.saliendo is None

    def animar(self):
        i = self.inicio
        ahora = time.monotonic()
        if i.saliendo is not None:
            if ahora - i.saliendo >= SALIDA:
                self.hide()
                despues = getattr(i, "despues", None)
                if despues:
                    despues()
                GLib.timeout_add(150, Gtk.main_quit)
                return False
            self.repintar()
        elif ahora - i.inicio < ENTRADA:
            self.repintar()
        return True

    def tecla(self, _w, ev):
        nombre = Gdk.keyval_name(ev.keyval) or ""
        texto = chr(Gdk.keyval_to_unicode(ev.keyval)) if Gdk.keyval_to_unicode(ev.keyval) else ""
        estado = ev.state
        if nombre == "grave" or ev.hardware_keycode == 49:
            # La tecla del menu rapido: se cierra esto y se abre aquel.
            self.inicio.cerrar(lambda: subprocess.Popen([sys.executable, MODO, "menu"], start_new_session=True))
            return True
        self.inicio.tecla(nombre, texto, bool(estado & Gdk.ModifierType.SHIFT_MASK),
                          bool(estado & Gdk.ModifierType.CONTROL_MASK))
        return True

    def rueda(self, _w, ev):
        paso = 0
        if ev.direction == Gdk.ScrollDirection.UP:
            paso = -1
        elif ev.direction == Gdk.ScrollDirection.DOWN:
            paso = 1
        elif ev.direction == Gdk.ScrollDirection.SMOOTH:
            dy = ev.get_scroll_deltas()[2]
            paso = (dy > 0) - (dy < 0)
        if paso:
            self.inicio.rueda(paso)
        return True


def a_png(ruta, ancho, alto, busqueda="", seccion=None):
    """Dibuja el inicio en un PNG, sin ventana (para mirarlo y para las pruebas)."""
    import cairo
    inicio = Inicio()
    inicio.leer()
    time.sleep(0.25)
    inicio.leer()
    inicio.inicio -= 10                 # sin animacion de entrada
    if seccion is not None:
        inicio.seccion = seccion
    inicio.busqueda = busqueda
    sup = cairo.ImageSurface(cairo.FORMAT_ARGB32, ancho, alto)
    cr = cairo.Context(sup)
    inicio.pintar(cr, ancho, alto)
    sup.write_to_png(ruta)
    return 0


def main(argv):
    if argv[:1] == ["--png"] and len(argv) >= 2:
        ancho, alto = (int(argv[2]), int(argv[3])) if len(argv) >= 4 else (1920, 1080)
        busqueda = argv[argv.index("--buscar") + 1] if "--buscar" in argv[:-1] else ""
        seccion = int(argv[argv.index("--seccion") + 1]) if "--seccion" in argv[:-1] else None
        return a_png(argv[1], ancho, alto, busqueda, seccion)
    if not dibujo.solo_wayland():
        return 1
    otro = otro_abierto()
    if otro:
        os.kill(otro, signal.SIGTERM)   # la misma tecla lo cierra
        return 0
    if not Gtk.init_check(sys.argv)[0]:
        return 1
    with open(ruta_pid(), "w") as fh:
        fh.write(str(os.getpid()))
    ventana = Ventana()
    ventana.show_all()
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
