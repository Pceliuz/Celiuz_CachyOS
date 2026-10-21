"""
remoto/servidor/celiuz_remoto/ajustes.py — ~/.config/celiuz/remoto.conf.

Lineas `clave = valor`, con `#` para comentarios, como clima.conf. Todo es
opcional: sin fichero, los valores de fabrica. Una clave desconocida o un valor
que no se entiende se ignoran con un aviso por stderr, nunca tumban el servicio.

    puerto_red = 47110        donde escucha por Tailscale
    puerto_usb = 47111        el canal USB (adb reverse), solo mientras se empareja
    sesion     = 300          segundos sin uso hasta que caduca una sesion
"""

import sys

from . import PUERTO_RED, PUERTO_USB, rutas

DE_FABRICA = {"puerto_red": PUERTO_RED, "puerto_usb": PUERTO_USB, "sesion": 300}
LIMITES = {"puerto_red": (1024, 65535), "puerto_usb": (1024, 65535), "sesion": (30, 86400)}


def leer(ruta=None):
    ruta = ruta or rutas.ajustes()
    valores = dict(DE_FABRICA)
    try:
        with open(ruta, encoding="utf-8") as fh:
            lineas = fh.read().splitlines()
    except OSError:
        return valores
    for n, linea in enumerate(lineas, 1):
        linea = linea.split("#", 1)[0].strip()
        if not linea:
            continue
        clave, _, valor = (x.strip() for x in linea.partition("="))
        if clave not in DE_FABRICA:
            print(f"{ruta}:{n}: no conozco «{clave}», la ignoro", file=sys.stderr)
            continue
        try:
            numero = int(valor)
        except ValueError:
            numero = None
        bajo, alto = LIMITES[clave]
        if numero is None or not bajo <= numero <= alto:
            print(f"{ruta}:{n}: «{clave}» tiene que ser un numero entre {bajo} y {alto}",
                  file=sys.stderr)
            continue
        valores[clave] = numero
    return valores
