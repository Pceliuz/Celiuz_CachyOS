"""
remoto/servidor/celiuz_remoto/sesion.py — entrar: reto, firma, contraseña y token que caduca.

- El telefono firma un reto con su clave privada Ed25519; la PC lo comprueba
  con la publica. La privada no viaja nunca.
- Primero la firma y DESPUES la contraseña: una firma mala no es el telefono,
  y no debe poder gastarle intentos (si no, cualquiera en la tailnet podria
  bloquearlo adrede).
- La contraseña se compara contra su hash scrypt (dispositivos.py).
- Al 5.o fallo seguido el telefono queda bloqueado y se avisa en la PC.
- El token caduca tras CADUCIDAD segundos sin uso. Vive solo en memoria: un
  reinicio del servicio echa a todo el mundo, que es lo seguro.
"""

import base64
import binascii
import secrets
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from . import dispositivos as dsp, pase


def caducado(disp):
    """Un invitado sin cable cuya hora ya paso (invitacion.py)."""
    hasta = pase.leer((disp or {}).get("expira"))
    return hasta is not None and pase.ahora() >= hasta

PREFIJO = "celiuz-remoto/v0/"
RETO_VALE = 30          # segundos
CADUCIDAD = 300         # segundos sin uso
MAX_RETOS = 256         # para que pedir retos a lo loco no llene la memoria


def texto_firmado(para, dato):
    return (PREFIJO + para + ":" + dato).encode("utf-8")


def firma_buena(publica_b64, mensaje, firma_b64):
    try:
        clave = Ed25519PublicKey.from_public_bytes(base64.b64decode(publica_b64))
        clave.verify(base64.b64decode(firma_b64, validate=True), mensaje)
        return True
    except (InvalidSignature, ValueError, binascii.Error, TypeError):
        return False


class Rechazo(Exception):
    """Un no, con lo que va en la respuesta (PROTOCOLO.md, «Respuestas de error»)."""

    def __init__(self, http, error, mensaje, **extra):
        super().__init__(mensaje)
        self.http, self.error, self.mensaje, self.extra = http, error, mensaje, extra

    def cuerpo(self):
        return dict({"error": self.error, "mensaje": self.mensaje}, **self.extra)


FIRMA_MALA = (401, "firma", "Este celular no está emparejado con esta PC, o el reto caducó.")


class Sesiones:
    def __init__(self, almacen, avisar=None, reloj=time.monotonic, caducidad=CADUCIDAD):
        self.almacen = almacen
        self.caducidad = caducidad
        self.avisar = avisar or (lambda titulo, cuerpo: None)
        self.reloj = reloj
        self.retos = {}      # reto -> (dispositivo, caduca)
        self.tokens = {}     # token -> {"dispositivo", "ultimo"}

    # --- retos ---

    def _barrer(self):
        t = self.reloj()
        self.retos = {k: v for k, v in self.retos.items() if v[1] > t}
        self.tokens = {k: v for k, v in self.tokens.items() if t - v["ultimo"] < self.caducidad}

    def reto(self, ident):
        self._barrer()
        if len(self.retos) >= MAX_RETOS:
            # Se tira el mas viejo: un atacante llenando la tabla solo consigue
            # que sus propios retos caduquen antes.
            del self.retos[min(self.retos, key=lambda k: self.retos[k][1])]
        r = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
        self.retos[r] = (str(ident), self.reloj() + RETO_VALE)
        return r

    def _gastar_reto(self, ident, reto):
        self._barrer()
        dato = self.retos.pop(reto, None) if isinstance(reto, str) else None
        return dato is not None and dato[0] == ident

    # --- entrar ---

    def comprobar_contrasena(self, disp, contrasena):
        """Cuenta el fallo y bloquea al 5.o. Lanza Rechazo si no vale."""
        if disp.get("bloqueado"):
            raise Rechazo(403, "bloqueado",
                          "Este celular está bloqueado por demasiados intentos. "
                          "Desbloquéalo desde la PC.")
        if dsp.contrasena_buena(disp.get("contrasena"), contrasena):
            if disp.get("fallos"):
                self.almacen.cambiar(disp["id"], fallos=0)
            return
        fallos, recien = self.almacen.fallo(disp["id"])
        if recien:
            self.avisar("Celiuz Remoto: celular bloqueado",
                        f"«{disp['nombre']}» falló la contraseña {fallos} veces seguidas "
                        "y ya no puede entrar. Si no eras tú, revócalo.")
            raise Rechazo(403, "bloqueado",
                          "Demasiados intentos: este celular queda bloqueado. "
                          "Desbloquéalo desde la PC.")
        raise Rechazo(401, "contrasena", "Contraseña incorrecta.",
                      intentos_restantes=max(0, dsp.MAX_FALLOS - fallos))

    def entrar(self, ident, reto, firma, contrasena):
        """Devuelve (token, telefono) o lanza Rechazo."""
        ident = str(ident or "")
        reto_ok = self._gastar_reto(ident, reto)
        disp = self.almacen.uno(ident)
        if disp is not None and caducado(disp):
            disp = None
        if not disp or not reto_ok or not firma_buena(
                disp["publica"], texto_firmado("sesion", reto), firma):
            raise Rechazo(*FIRMA_MALA)
        self.comprobar_contrasena(disp, contrasena)
        token = secrets.token_urlsafe(32)
        self.tokens[token] = {"dispositivo": ident, "ultimo": self.reloj()}
        return token, disp

    # --- usar ---

    def quien(self, token, tocar=True):
        """El telefono de ese token (releido: un revocado se va al instante),
        o None si no vale."""
        self._barrer()
        s = self.tokens.get(token) if isinstance(token, str) else None
        if s is None:
            return None
        disp = self.almacen.uno(s["dispositivo"])
        if disp is None or disp.get("bloqueado") or caducado(disp):
            self.tokens.pop(token, None)
            return None
        if tocar:
            s["ultimo"] = self.reloj()
        return disp

    def salir(self, token):
        return self.tokens.pop(token, None) is not None

    def echar(self, ident):
        """Cierra todas las sesiones de un telefono (al revocarlo)."""
        for k in [k for k, v in self.tokens.items() if v["dispositivo"] == ident]:
            del self.tokens[k]

    def cuantas(self):
        self._barrer()
        return len(self.tokens)
