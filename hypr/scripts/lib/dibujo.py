#!/usr/bin/env python3
"""
hypr/scripts/lib/dibujo.py — lo comun para dibujar a mano con Cairo las
pantallas del modo gaming (biblioteca.py y menu-rapido.py).

Las dos se dibujan enteras con Cairo y no con widgets de GTK, para que se vean
como las maquetas aprobadas y no como un tema de GTK. Esto es lo que comparten:
la paleta del repo, el texto con la fuente del repo, los rectangulos
redondeados y una cache de imagenes escaladas.

Quien lo use tiene que haber fijado ya las versiones de gi (Gtk 3, Gdk 3,
Pango, PangoCairo, GdkPixbuf) antes de importarlo.
"""

import math
import os

from gi.repository import GdkPixbuf, GLib, Pango, PangoCairo

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
FUENTE = "MesloLGS Nerd Font Propo"

PALETA_FABRICA = {
    "abismo": "#0d0418", "superficie": "#1a0830", "apagado": "#2d1b4e",
    "violeta": "#6a00f4", "amatista": "#b16cff", "neon": "#c77dff",
    "luz": "#e4c7ff", "tenue": "#8a7aa8", "atencion": "#f6c177", "alerta": "#eb6f92",
}
VERDE = (0.49, 1.0, 0.69)
AZUL = (0.62, 0.78, 1.0)
ROSA = (0.92, 0.44, 0.57)


def paleta():
    """Los colores de waybar/colores.css (generado de colores.conf), para que
    estas pantallas lleven el tono de quien clona el repo y no el del autor.
    Con los de fabrica como respaldo, para un equipo a medio instalar."""
    colores = dict(PALETA_FABRICA)
    try:
        with open(os.path.join(RAIZ, "waybar", "colores.css"), encoding="utf-8") as fh:
            for linea in fh:
                partes = linea.split()
                if len(partes) >= 3 and partes[0] == "@define-color" and partes[2].startswith("#"):
                    colores[partes[1]] = partes[2].rstrip(";")
    except OSError:
        pass
    return {k: tuple(int(v[i:i + 2], 16) / 255 for i in (1, 3, 5)) for k, v in colores.items()
            if isinstance(v, str) and len(v) >= 7}


C = paleta()


def solo_wayland():
    """Solo en una sesion Wayland, y sin caer nunca a X11: sin WAYLAND_DISPLAY
    GTK probaria DISPLAY y se dibujaria por XWayland donde no toca (asi abrio
    la prueba del modo gaming tres bibliotecas en la sesion real)."""
    if not os.environ.get("WAYLAND_DISPLAY"):
        return False
    os.environ["GDK_BACKEND"] = "wayland"
    return True


def suave(t):
    """0..1 -> 0..1 con salida suave (ease-out cubica)."""
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 3


def _capa(cr, texto, tam, peso, espaciado, ancho):
    capa = PangoCairo.create_layout(cr)
    fuente = Pango.FontDescription.from_string(FUENTE)
    fuente.set_absolute_size(tam * Pango.SCALE)
    fuente.set_weight(peso)
    capa.set_font_description(fuente)
    if espaciado:
        attrs = Pango.AttrList()
        attrs.insert(Pango.attr_letter_spacing_new(int(espaciado * Pango.SCALE)))
        capa.set_attributes(attrs)
    if ancho:
        capa.set_width(int(ancho * Pango.SCALE))
        capa.set_wrap(Pango.WrapMode.WORD_CHAR)
    capa.set_text(texto, -1)
    return capa


def medir(cr, texto, tam, peso=Pango.Weight.NORMAL, espaciado=0.0, ancho=None):
    return _capa(cr, texto, tam, peso, espaciado, ancho).get_pixel_size()


def texto(cr, texto_, x, y, tam, color, peso=Pango.Weight.NORMAL, espaciado=0.0,
          alfa=1.0, ancho=None, derecha=False, centro=False, una_linea=False):
    """Escribe y devuelve (ancho, alto). `una_linea` corta con «…» en `ancho`."""
    capa = _capa(cr, texto_, tam, peso, espaciado, None if una_linea else ancho)
    if una_linea and ancho:
        capa.set_width(int(ancho * Pango.SCALE))
        capa.set_ellipsize(Pango.EllipsizeMode.END)
    tw, th = capa.get_pixel_size()
    cr.set_source_rgba(*color, alfa)
    cr.move_to(x - tw if derecha else (x - tw / 2 if centro else x), y)
    PangoCairo.show_layout(cr, capa)
    # show_layout deja un «punto actual»: sin limpiarlo, el siguiente arco
    # arranca con una linea desde el texto hasta el (se veia una diagonal suelta
    # en la pantalla de «Lanzando»).
    cr.new_path()
    return tw, th


def redondo(cr, x, y, w, h, r):
    r = max(0, min(r, w / 2, h / 2))
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def circulo(cr, cx, cy, r):
    cr.new_sub_path()
    cr.arc(cx, cy, r, 0, 2 * math.pi)


class Imagenes:
    """Imagenes escaladas (a caber, o a cubrir recortando), con cache LRU."""

    def __init__(self, tope=60):
        self.cache, self.orden, self.tope = {}, [], tope
        self._tema = None

    def cargar(self, ruta, ancho, alto, cubrir=False):
        if not ruta:
            return None
        clave = (ruta, int(ancho), int(alto), cubrir)
        if clave in self.cache:
            return self.cache[clave]
        try:
            original = GdkPixbuf.Pixbuf.new_from_file(ruta)
        except GLib.Error:
            self.cache[clave] = None
            return None
        pw, ph = original.get_width(), original.get_height()
        escala = (max if cubrir else min)(ancho / pw, alto / ph)
        pix = original.scale_simple(max(1, int(pw * escala)), max(1, int(ph * escala)),
                                    GdkPixbuf.InterpType.BILINEAR)
        self.cache[clave] = pix
        self.orden.append(clave)
        if len(self.orden) > self.tope:
            self.cache.pop(self.orden.pop(0), None)
        return pix

    def icono(self, nombre, tam):
        """Un icono del tema por nombre (o una ruta absoluta), a `tam` px."""
        if not nombre:
            return None
        if os.path.isabs(nombre):
            return self.cargar(nombre, tam, tam)
        if self._tema is None:
            from gi.repository import Gtk
            self._tema = Gtk.IconTheme.get_default() or Gtk.IconTheme.new()
        info = self._tema.lookup_icon(nombre, int(tam), 0)
        return self.cargar(info.get_filename(), tam, tam) if info else None
