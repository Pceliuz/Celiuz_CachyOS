#!/usr/bin/env python3
"""
tests/lib/telefono_falso.py — un celular de mentira para Celiuz Remoto.

Hace lo que hara la app de verdad (remoto/PROTOCOLO.md): genera su par Ed25519,
se empareja por el canal USB, entra con reto + firma + contraseña, mira el
estado por el WebSocket y renueva el pase. Sin Android, sin adb y sin red: le
habla a un servidor en 127.0.0.1.

Como libreria (Telefono) y como CLI para las pruebas de bash:

    telefono_falso.py emparejar <puerto_usb> <codigo> <carpeta> [nombre]
    telefono_falso.py entrar <puerto_red> <carpeta> <contrasena>
    telefono_falso.py pedir <metodo> <url> [token]
    telefono_falso.py vivo <puerto_red> <token> <n>
    telefono_falso.py renovar <puerto_usb> <codigo> <carpeta> <contrasena>
    telefono_falso.py invitacion <puerto_red> <codigo> <carpeta> [nombre]

Todas imprimen {"http": codigo, "cuerpo": {...}} en una linea.
"""

import asyncio
import base64
import json
import os
import sys
import urllib.error
import urllib.request

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

PREFIJO = "celiuz-remoto/v0/"


def b64(x):
    return base64.b64encode(x).decode()


def pedir(metodo, url, cuerpo=None, token=None, timeout=10):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    r = urllib.request.Request(url, data=datos, method=metodo)
    if datos is not None:
        r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        texto = e.read()
        try:
            return e.code, json.loads(texto)
        except ValueError:
            return e.code, {"crudo": texto.decode(errors="replace")}


class Telefono:
    def __init__(self, carpeta):
        self.carpeta = carpeta
        os.makedirs(carpeta, exist_ok=True)
        ruta = os.path.join(carpeta, "clave")
        if os.path.exists(ruta):
            with open(ruta, "rb") as fh:
                self.privada = Ed25519PrivateKey.from_private_bytes(fh.read())
        else:
            self.privada = Ed25519PrivateKey.generate()
            with open(ruta, "wb") as fh:
                fh.write(self.privada.private_bytes(serialization.Encoding.Raw,
                                                    serialization.PrivateFormat.Raw,
                                                    serialization.NoEncryption()))
        self.publica = b64(self.privada.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw))

    @property
    def dispositivo(self):
        try:
            with open(os.path.join(self.carpeta, "dispositivo")) as fh:
                return fh.read().strip()
        except OSError:
            return None

    def firmar(self, para, dato):
        return b64(self.privada.sign((PREFIJO + para + ":" + dato).encode()))

    def emparejar(self, puerto_usb, codigo, nombre="Teléfono de pruebas"):
        http, c = pedir("POST", f"http://127.0.0.1:{puerto_usb}/usb/emparejar", {
            "codigo": codigo, "nombre": nombre, "publica": self.publica,
            "firma": self.firmar("emparejar", codigo)})
        if http == 200:
            with open(os.path.join(self.carpeta, "dispositivo"), "w") as fh:
                fh.write(c["dispositivo"])
        return http, c

    def aceptar_invitacion(self, puerto_red, codigo, nombre="Amigo"):
        """Fase 8, sin cable. Se firma el codigo NORMALIZADO (solo letras y
        numeros, en mayusculas): asi da igual como lo copie la persona."""
        limpio = "".join(c for c in codigo.upper() if c.isalnum())
        http, c = pedir("POST", f"http://127.0.0.1:{puerto_red}/v0/invitacion", {
            "codigo": codigo, "nombre": nombre, "publica": self.publica,
            "firma": self.firmar("invitacion", limpio)})
        if http == 200:
            with open(os.path.join(self.carpeta, "dispositivo"), "w") as fh:
                fh.write(c["dispositivo"])
        return http, c

    def entrar(self, puerto, contrasena, ident=None):
        ident = ident or self.dispositivo
        base = f"http://127.0.0.1:{puerto}"
        _, r = pedir("GET", f"{base}/v0/reto?dispositivo={ident}")
        return pedir("POST", f"{base}/v0/sesion", {
            "dispositivo": ident, "reto": r["reto"],
            "firma": self.firmar("sesion", r["reto"]), "contrasena": contrasena})

    def renovar(self, puerto_usb, codigo, contrasena):
        return pedir("POST", f"http://127.0.0.1:{puerto_usb}/usb/renovar", {
            "codigo": codigo, "dispositivo": self.dispositivo,
            "firma": self.firmar("renovar", codigo), "contrasena": contrasena})


async def vivo(puerto, token, n, espera=10):
    """Los n primeros mensajes de /v0/vivo, y como se cerro si se cerro."""
    import aiohttp
    mensajes, cierre = [], None
    async with aiohttp.ClientSession() as s:
        try:
            async with s.ws_connect(f"http://127.0.0.1:{puerto}/v0/vivo",
                                    headers={"Authorization": "Bearer " + token}) as ws:
                while len(mensajes) < n:
                    m = await asyncio.wait_for(ws.receive(), espera)
                    if m.type == aiohttp.WSMsgType.TEXT:
                        mensajes.append(json.loads(m.data))
                    else:
                        cierre = ws.close_code
                        break
        except aiohttp.WSServerHandshakeError as e:
            return {"http": e.status, "mensajes": [], "cierre": None}
    return {"http": 101, "mensajes": mensajes, "cierre": cierre}


def main(a):
    orden = a[0]
    if orden == "emparejar":
        http, c = Telefono(a[3]).emparejar(int(a[1]), a[2], *(a[4:5] or []))
    elif orden == "entrar":
        http, c = Telefono(a[2]).entrar(int(a[1]), a[3])
    elif orden == "invitacion":
        http, c = Telefono(a[3]).aceptar_invitacion(int(a[1]), a[2], *(a[4:5] or []))
    elif orden == "renovar":
        http, c = Telefono(a[3]).renovar(int(a[1]), a[2], a[4])
    elif orden == "pedir":
        http, c = pedir(a[1], a[2], token=(a[3] if len(a) > 3 else None))
    elif orden == "vivo":
        print(json.dumps(asyncio.run(vivo(int(a[1]), a[2], int(a[3])))))
        return 0
    else:
        print(__doc__, file=sys.stderr)
        return 2
    print(json.dumps({"http": http, "cuerpo": c}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
