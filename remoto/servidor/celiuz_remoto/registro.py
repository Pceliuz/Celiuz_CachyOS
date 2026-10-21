"""
remoto/servidor/celiuz_remoto/registro.py — el diario de lo que hace cada telefono.

registro.jsonl (0600, fuera del repo): una linea por cosa, con cuando, que
telefono, que accion y su detalle. NUNCA contraseñas ni lo que se escriba en la
terminal: el diario es para saber que paso, no otra copia de los secretos.

Si no se puede escribir, se sigue: perder una linea del diario es mejor que
dejar al usuario sin poder apagar la PC.
"""

import json
import os
import sys

from . import pase, rutas

PROHIBIDOS = {"contrasena", "clave", "token", "firma"}


def apuntar(accion, dispositivo=None, **detalle):
    for k in PROHIBIDOS & detalle.keys():
        detalle[k] = "***"
    linea = {"cuando": pase.iso(pase.ahora()), "accion": accion}
    if dispositivo:
        linea["dispositivo"] = dispositivo
    linea.update(detalle)
    ruta = rutas.registro()
    try:
        os.makedirs(os.path.dirname(ruta), mode=0o700, exist_ok=True)
        fd = os.open(ruta, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(linea, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"celiuz-remoto: no pude escribir el registro: {e}", file=sys.stderr)


def ultimas(n=50):
    try:
        with open(rutas.registro(), encoding="utf-8") as fh:
            lineas = fh.readlines()[-n:]
    except OSError:
        return []
    salida = []
    for linea in lineas:
        try:
            salida.append(json.loads(linea))
        except ValueError:
            continue
    return salida
