#!/usr/bin/env python3
"""tests/lib/mpv_falso.py — un mpv de mentira por su socket de IPC, para que
lock.sh crea que el fondo en video esta corriendo.

    mpv_falso.py <socket>

Contesta `get_property path` (un video que no existe: ffmpeg falla y lock.sh
sigue, que es lo que se quiere) y `time-pos`; a todo lo demas, «success».
ATIENDE cada conexion en bucle: un `listen()` sin `accept()` llena la cola y
acaba fingiendo el fallo que no se queria probar (ver CLAUDE.md).
"""
import json
import os
import socket
import sys

ruta = sys.argv[1]
if os.path.exists(ruta):
    os.unlink(ruta)
srv = socket.socket(socket.AF_UNIX)
srv.bind(ruta)
srv.listen(16)
DATOS = {"path": "/no/existe/fondo.mp4", "time-pos": 1.5, "pause": False}
while True:
    con, _ = srv.accept()
    with con, con.makefile("rw") as f:
        for linea in f:
            try:
                orden = json.loads(linea).get("command", [])
            except ValueError:
                break
            if orden[:1] == ["get_property"]:
                r = {"data": DATOS.get(orden[1]), "error": "success", "request_id": 0}
            else:
                r = {"error": "success", "request_id": 0}
            f.write(json.dumps(r) + "\n")
            f.flush()
