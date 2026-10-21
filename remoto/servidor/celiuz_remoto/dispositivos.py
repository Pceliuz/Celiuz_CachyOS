"""
remoto/servidor/celiuz_remoto/dispositivos.py — los telefonos emparejados.

dispositivos.json (0600, fuera del repo), un objeto por telefono:

    id            16 hex, lo da la PC al emparejar
    nombre        el que dice el celular («Redmi Note 13»)
    publica       su clave publica Ed25519, base64 (la privada no sale de el)
    contrasena    {"sal", "hash", "n", "r", "p"}: scrypt de la contraseña de la app
    permisos      ["estado", "energia", ...]
    pase_hasta    ISO 8601 con zona, o null
    fallos        contraseñas mal seguidas; al llegar a MAX_FALLOS, bloqueado
    bloqueado     true: no entra hasta que se desbloquee desde la PC
    creado, ultima_sesion
    serie         la del cable (adb) con que se emparejo, o null

Revocar quita el telefono entero; «quitar el pase» solo vacia pase_hasta.

POR QUE SE RELEE EN CADA OPERACION y no se guarda en memoria: lo tocan a la vez
el servicio y la CLI (o la app de la PC) al revocar. Con un cerrojo (flock) y
el fichero entero en cada vuelta no hay dos copias que puedan separarse; son
unos pocos KB.
"""

import base64
import binascii
import contextlib
import fcntl
import hashlib
import hmac
import json
import os
import secrets
import tempfile

from . import rutas

PERMISOS = ("estado", "energia", "ventanas", "archivos", "terminal")
# Lo que se da al emparejar si no se dice otra cosa (DISEÑO.md, «Qué pide cada
# cosa»): ver y apagar. Lo demas se activa a mano por telefono.
PERMISOS_DE_FABRICA = ("estado", "energia")
MAX_FALLOS = 5

# scrypt: ~50 ms y 32 MB por intento en esta PC. Bastante para que probar
# contraseñas a lo bruto sea caro, poco para que entrar se note.
SCRYPT = {"n": 2 ** 15, "r": 8, "p": 1}


class ErrorDispositivo(Exception):
    pass


def _scrypt(contrasena, sal, n, r, p):
    return hashlib.scrypt(contrasena.encode("utf-8"), salt=sal, n=n, r=r, p=p,
                          maxmem=128 * 1024 * 1024, dklen=32)


def hash_contrasena(contrasena):
    if not isinstance(contrasena, str) or len(contrasena) < 4:
        raise ErrorDispositivo("la contraseña tiene que tener al menos 4 caracteres")
    sal = secrets.token_bytes(16)
    h = _scrypt(contrasena, sal, **SCRYPT)
    return dict(SCRYPT, sal=base64.b64encode(sal).decode(), hash=base64.b64encode(h).decode())


def contrasena_buena(guardada, contrasena):
    if not guardada or not isinstance(contrasena, str):
        return False
    try:
        sal = base64.b64decode(guardada["sal"])
        esperado = base64.b64decode(guardada["hash"])
        h = _scrypt(contrasena, sal, guardada["n"], guardada["r"], guardada["p"])
    except (KeyError, ValueError, binascii.Error):
        return False
    return hmac.compare_digest(h, esperado)


def publica_valida(texto):
    """32 bytes en base64: lo que mide una clave publica Ed25519."""
    try:
        return len(base64.b64decode(texto, validate=True)) == 32
    except (binascii.Error, TypeError, ValueError):
        return False


class Almacen:
    def __init__(self, ruta=None):
        self.ruta = ruta or rutas.dispositivos()

    @contextlib.contextmanager
    def _abierto(self, escribir):
        """Cerrojo sobre un fichero aparte (el .json se reemplaza entero al
        guardar, y un flock sobre el viejo no protegeria al nuevo)."""
        carpeta = os.path.dirname(self.ruta)
        if not escribir and not os.path.exists(self.ruta):
            # Leer no crea nada: «dispositivos» en un equipo sin emparejar no
            # tiene por que dejar carpetas.
            yield {"version": 1, "dispositivos": {}}
            return
        os.makedirs(carpeta, mode=0o700, exist_ok=True)
        fd = os.open(self.ruta + ".cerrojo", os.O_RDWR | os.O_CREAT, 0o600)
        with os.fdopen(fd, "r+") as cerrojo:
            fcntl.flock(cerrojo, fcntl.LOCK_EX if escribir else fcntl.LOCK_SH)
            datos = self._leer()
            yield datos
            if escribir:
                self._escribir(datos)

    def _leer(self):
        try:
            with open(self.ruta, encoding="utf-8") as fh:
                datos = json.load(fh)
        except FileNotFoundError:
            return {"version": 1, "dispositivos": {}}
        except (OSError, ValueError) as e:
            # Un fichero roto NO se trata como vacio: guardar encima borraria
            # todos los telefonos. Mejor plantarse y que se vea.
            raise ErrorDispositivo(f"no puedo leer {self.ruta}: {e}") from e
        datos.setdefault("dispositivos", {})
        return datos

    def _escribir(self, datos):
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.ruta), prefix=".dispositivos-")
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(datos, fh, ensure_ascii=False, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.ruta)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise

    # --- lectura ---

    def todos(self):
        with self._abierto(False) as d:
            return list(d["dispositivos"].values())

    def uno(self, ident):
        with self._abierto(False) as d:
            return d["dispositivos"].get(ident)

    # --- escritura ---

    def crear(self, nombre, publica, hash_contra, permisos, ahora, serie=None):
        if not publica_valida(publica):
            raise ErrorDispositivo("la clave publica no es Ed25519 (32 bytes en base64)")
        malos = [x for x in permisos if x not in PERMISOS]
        if malos:
            raise ErrorDispositivo(f"permisos desconocidos: {', '.join(malos)}")
        nombre = (str(nombre or "").strip() or "Celular")[:60]
        with self._abierto(True) as d:
            # La misma clave publica dos veces seria el mismo telefono
            # emparejado otra vez: se sustituye el viejo, no se duplica.
            for viejo in [k for k, v in d["dispositivos"].items() if v["publica"] == publica]:
                del d["dispositivos"][viejo]
            ident = secrets.token_hex(8)
            d["dispositivos"][ident] = {
                "id": ident, "nombre": nombre, "publica": publica,
                "contrasena": hash_contra, "permisos": sorted(set(permisos), key=PERMISOS.index),
                "pase_hasta": None, "fallos": 0, "bloqueado": False,
                "creado": ahora, "ultima_sesion": None,
                # La serie USB (adb) con que se emparejo: para que la app de
                # la PC sepa si el celular enchufado ya es uno de estos. No es
                # un secreto ni sirve para entrar.
                "serie": serie,
            }
            return dict(d["dispositivos"][ident])

    def cambiar(self, ident, **campos):
        """Cambia campos de un telefono. Devuelve el telefono, o None si no hay."""
        with self._abierto(True) as d:
            disp = d["dispositivos"].get(ident)
            if disp is None:
                return None
            disp.update(campos)
            return dict(disp)

    def fallo(self, ident):
        """Una contraseña mal. Devuelve (fallos, recien_bloqueado)."""
        with self._abierto(True) as d:
            disp = d["dispositivos"].get(ident)
            if disp is None:
                return 0, False
            disp["fallos"] = disp.get("fallos", 0) + 1
            nuevo = disp["fallos"] >= MAX_FALLOS and not disp.get("bloqueado")
            if disp["fallos"] >= MAX_FALLOS:
                disp["bloqueado"] = True
            return disp["fallos"], nuevo

    def revocar(self, ident):
        with self._abierto(True) as d:
            return d["dispositivos"].pop(ident, None) is not None

    def por_serie(self, serie):
        return next((x for x in self.todos() if serie and x.get("serie") == serie), None)

    def buscar(self, texto):
        """Por id entero, por principio de id o por nombre exacto. Ambiguo = None."""
        todos = self.todos()
        exactos = [x for x in todos if x["id"] == texto]
        if exactos:
            return exactos[0]
        candidatos = [x for x in todos if x["id"].startswith(texto) or x["nombre"] == texto]
        return candidatos[0] if len(candidatos) == 1 else None
