#!/usr/bin/env python3
"""
hypr/scripts/lib/imagen_saludo.py — deja una imagen lista para el saludo de la
terminal (hypr/scripts/saludo.sh). El original no se toca: se escribe una copia.

    imagen_saludo.py ORIGEN DESTINO.png [ORIGEN DESTINO.png ...]

Varios pares en una llamada valen para `celiuz-saludo --preparar`: arrancar
python con GTK cuesta ~0,4 s, mas que adaptar la imagen.

Lo que hace, en este orden:
  1. La reduce para que quepa en LADO x LADO. Una de 5000 px tarda en
     convertirse en cada terminal y no se ve mejor en 22 celdas.
  2. Si tiene transparencia, RECORTA el margen vacio. Los stickers traen mucho
     aire alrededor del personaje, y ese aire cuenta para el tamaño: sin
     recortar, el dibujo sale pequeño dentro de su caja.
  3. Si no la tiene (una foto, un cartel), le REDONDEA las esquinas, para que se
     vea como una tarjeta y no como un rectangulo pegado.

Lee lo que lea GdkPixbuf (PNG, JPG, WebP, GIF: del GIF, el primer fotograma), da
igual la extension que tenga el fichero. Sale con 1 si no puede, y saludo.sh usa
entonces el original.
"""

import math
import os
import sys

import gi

gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gdk", "3.0")
import cairo  # noqa: E402
from gi.repository import Gdk, GdkPixbuf  # noqa: E402

LADO = 400          # px: el lado mayor de la copia (en 22 celdas sobra)
MINI = 128          # px: la miniatura donde se busca el recorte (rapido)
UMBRAL_ALFA = 16    # menos que esto cuenta como transparente al recortar
OPACA = 0.995       # fraccion de pixeles opacos para tratarla como «sin fondo transparente»
MARGEN = 4          # px que se dejan al recortar, para no cortar el borde del trazo
RADIO = 0.07        # radio de las esquinas, en fraccion del lado menor


def cargar(ruta):
    pb = GdkPixbuf.Pixbuf.new_from_file(ruta)
    w, h = pb.get_width(), pb.get_height()
    f = min(1.0, LADO / max(w, h))
    if f < 1.0:
        pb = pb.scale_simple(max(1, round(w * f)), max(1, round(h * f)),
                             GdkPixbuf.InterpType.HYPER)
    if not pb.get_has_alpha():
        pb = pb.add_alpha(False, 0, 0, 0)
    return pb


def caja_visible(pb):
    """(x0, y0, x1, y1) de lo que no es transparente, y la fraccion opaca."""
    w, h, paso = pb.get_width(), pb.get_height(), pb.get_rowstride()
    datos = pb.get_pixels()
    x0, y0, x1, y1 = w, h, -1, -1
    opacos = 0
    for y in range(h):
        fila = datos[y * paso + 3: y * paso + 4 * w: 4]   # solo los alfa
        xs = [x for x, a in enumerate(fila) if a > UMBRAL_ALFA]
        if xs:
            y0 = min(y0, y)
            y1 = y
            x0 = min(x0, xs[0])
            x1 = max(x1, xs[-1])
        opacos += sum(1 for a in fila if a >= 250)
    return (x0, y0, x1, y1), opacos / float(w * h)


def adaptar(origen, destino):
    pb = cargar(origen)
    w, h = pb.get_width(), pb.get_height()
    # El recorte se busca en una miniatura: recorrer pixel a pixel en python la
    # imagen entera tarda ~0,4 s, y es lo que espera una terminal nueva. Se
    # pasa a la grande con un pixel de miniatura de holgura por lado.
    k = min(1.0, MINI / max(w, h))
    mini = pb if k == 1.0 else pb.scale_simple(max(1, round(w * k)), max(1, round(h * k)),
                                               GdkPixbuf.InterpType.BILINEAR)
    (x0, y0, x1, y1), opaca = caja_visible(mini)
    if x1 >= 0 and k < 1.0:
        x0, y0 = int((x0 - 1) / k), int((y0 - 1) / k)
        x1, y1 = int(math.ceil((x1 + 2) / k)), int(math.ceil((y1 + 2) / k))
    if x1 < 0:          # entera transparente: se deja como esta
        pb.savev(destino, "png", [], [])
        return
    if opaca >= OPACA:
        redondear = True
    else:
        redondear = False
        x0, y0 = max(0, x0 - MARGEN), max(0, y0 - MARGEN)
        x1, y1 = min(w - 1, x1 + MARGEN), min(h - 1, y1 + MARGEN)
        pb = pb.new_subpixbuf(x0, y0, x1 - x0 + 1, y1 - y0 + 1)
        w, h = pb.get_width(), pb.get_height()

    sup = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(sup)
    if redondear:
        r = RADIO * min(w, h)
        cr.new_sub_path()
        cr.arc(w - r, r, r, -math.pi / 2, 0)
        cr.arc(w - r, h - r, r, 0, math.pi / 2)
        cr.arc(r, h - r, r, math.pi / 2, math.pi)
        cr.arc(r, r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()
        cr.clip()
    Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0)
    cr.paint()
    sup.write_to_png(destino)


def main(argv):
    if not argv or len(argv) % 2:
        print(__doc__.strip().split("\n\n")[1], file=sys.stderr)
        return 2
    codigo = 0
    for origen, destino in zip(argv[0::2], argv[1::2]):
        # Se escribe al lado y se mueve: una terminal que abra a la vez nunca
        # ve una copia a medias.
        tmp = "%s.%d.tmp" % (destino, os.getpid())
        try:
            adaptar(origen, tmp)
            os.replace(tmp, destino)
        except Exception as e:   # imagen rota o formato que GdkPixbuf no lee
            print("imagen_saludo: %s: %s" % (origen, e), file=sys.stderr)
            try:
                os.remove(tmp)
            except OSError:
                pass
            codigo = 1
    return codigo


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
