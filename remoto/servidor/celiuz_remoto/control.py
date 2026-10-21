"""
remoto/servidor/celiuz_remoto/control.py — hablarle al servicio por su socket.

Lo usan la CLI (celiuz-remoto.py emparejar / renovar / estado) y la app de la
PC. Sin dependencias: http.client sobre un socket Unix, para que la app GTK no
tenga que cargar aiohttp.
"""

import http.client
import json
import socket

from . import rutas


class SinServicio(Exception):
    pass


class _Conexion(http.client.HTTPConnection):
    def __init__(self, ruta, timeout):
        super().__init__("localhost", timeout=timeout)
        self.ruta = ruta

    def connect(self):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect(self.ruta)
        self.sock = s


def pedir(metodo, ruta, cuerpo=None, timeout=10.0):
    """(codigo_http, json). SinServicio si el servicio no esta escuchando."""
    sock = rutas.control()
    c = _Conexion(sock, timeout)
    try:
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        cabeceras = {"Content-Type": "application/json"} if datos is not None else {}
        c.request(metodo, ruta, body=datos, headers=cabeceras)
        r = c.getresponse()
        texto = r.read()
    except (FileNotFoundError, ConnectionRefusedError):
        raise SinServicio(
            "el servicio de Celiuz Remoto no está corriendo "
            "(systemctl --user start celiuz-remoto, o celiuz-remoto.py servir)") from None
    finally:
        c.close()
    try:
        return r.status, json.loads(texto or b"{}")
    except ValueError:
        return r.status, {"error": "respuesta", "mensaje": texto.decode(errors="replace")}
