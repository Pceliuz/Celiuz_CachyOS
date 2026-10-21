"""
remoto/servidor/celiuz_remoto/invitacion.py — ayudar a un amigo: dejar entrar a un celular SIN cable, por un rato.

Fase 8 (remoto/DISEÑO.md, «Extras»: modo «ayudar a un amigo»). El caso: un
amigo con esta misma config tiene un problema en SU PC y tu le ayudas desde tu
celular, cada uno en su casa. Emparejar pide el cable, y aqui no hay cable.

Asi que lo que se abre es mas pequeño que un emparejamiento, y se cierra solo:
  - Lo abre la persona DELANTE de la PC (la ventana o `celiuz-remoto invitar`):
    es la que da permiso, igual que con el cable. Nunca se abre desde fuera.
  - Una INVITACION de un solo uso: un codigo (16 letras) y una contraseña que
    la PC inventa y enseña para que se manden por WhatsApp o se digan. Vale 15
    minutos y se gasta al usarla.
  - El celular invitado nace con FECHA DE CADUCIDAD (`expira`, unas horas):
    a esa hora deja de existir para todo (entrar, cada peticion, una terminal o
    una pantalla abiertas) y se borra solo. Su pase dura lo mismo y no se
    renueva: para seguir, otra invitacion.
  - Con los permisos que elija la PC (de fabrica: ver el estado, las apps y la
    pantalla; nada de apagar, archivos ni terminal).
  - Cinco codigos mal y la invitacion se QUEMA (y la PC avisa): no se puede
    probar a lo bruto, aunque el codigo ya es largo.

Por la red solo llega a la PC quien este en su tailnet: el amigo tiene que
compartirle la PC por Tailscale (consola de Tailscale -> Share). Eso lo explica
la ventana; este modulo no toca Tailscale.
"""

import hmac
import secrets
import time

VALE = 15 * 60                 # segundos para usar la invitacion
MAX_FALLOS = 5
HORAS = (1, 2, 4, 8)           # lo que se puede elegir de acceso
PERMISOS_DE_FABRICA = ("estado", "ventanas", "pantalla")
_LETRAS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"    # sin 0/O, 1/I/L: se dictan por telefono


def normalizar(codigo):
    """«abcd efgh-jkmn pqrs» -> «ABCDEFGHJKMNPQRS»."""
    return "".join(c for c in str(codigo or "").upper() if c.isalnum())


def bonito(codigo):
    return "-".join(codigo[i:i + 4] for i in range(0, len(codigo), 4))


class Invitacion:
    def __init__(self, permisos, horas, hash_contrasena, contrasena):
        self.codigo = "".join(secrets.choice(_LETRAS) for _ in range(16))
        self.contrasena = contrasena          # en claro solo para ENSEÑARLA en la PC
        self.hash = hash_contrasena
        self.permisos = list(permisos)
        self.horas = horas
        self.hasta = time.monotonic() + VALE
        self.fallos = 0
        self.estado = "abierta"               # abierta | usada | caducada | cancelada | quemada
        self.dispositivo = None

    def abierta(self):
        if self.estado == "abierta" and time.monotonic() > self.hasta:
            self.estado = "caducada"
            self.contrasena = None
        return self.estado == "abierta"

    def codigo_bueno(self, codigo):
        return hmac.compare_digest(normalizar(codigo), self.codigo)

    def fallo(self):
        """True si con este fallo se quema."""
        self.fallos += 1
        if self.fallos >= MAX_FALLOS:
            self.estado = "quemada"
            self.contrasena = None
            return True
        return False

    def resumen(self):
        quedan = max(0, round(self.hasta - time.monotonic())) if self.abierta() else 0
        return {"estado": self.estado, "quedan": quedan, "permisos": self.permisos,
                "horas": self.horas, "dispositivo": self.dispositivo,
                "codigo": bonito(self.codigo) if self.estado == "abierta" else None,
                "contrasena": self.contrasena if self.estado == "abierta" else None}


def contrasena_nueva():
    """Tres trozos de cuatro letras: facil de dictar, ~60 bits."""
    return "-".join("".join(secrets.choice(_LETRAS.lower()) for _ in range(4)) for _ in range(3))
