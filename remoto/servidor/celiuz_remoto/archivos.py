"""
remoto/servidor/celiuz_remoto/archivos.py — el explorador: listar, buscar, descargar, miniaturas.

Fase 6 (remoto/DISEÑO.md, «Archivos: un explorador propio, no Dolphin»). Todo
pide permiso `archivos` y el PASE (lo comprueba servidor.py), y todo es de
SOLO LECTURA.

LA FRONTERA es la carpeta personal, y se mira DESPUES de resolver la ruta con
realpath, no antes: `Documentos/../../etc` o un enlace `Documentos/x -> /etc`
parecen de dentro hasta que se resuelven. Una ruta que salga, da Fuera (403).

Y dentro de casa hay sitios que NUNCA se enseñan aunque estes en tu derecho
(NUNCA, abajo): las claves de ssh y gpg, los llaveros, los perfiles de los
navegadores (cookies y contraseñas guardadas) y lo propio de Celiuz Remoto
(los telefonos emparejados, la clave de firma del APK). Es lo que pide el caso
del celular robado: con la contraseña de la app y un pase vigente se puede
sacar un documento, pero no lo que abre las demas puertas. Un enlace que lleve
ahi tambien se resuelve y se rechaza.

Los ocultos (los que empiezan por punto) no salen en la lista salvo que se
pidan, igual que en Dolphin; los de NUNCA no salen ni pidiendolos.
"""

import datetime as dt
import hashlib
import os
import shutil
import stat
import subprocess
import time

from . import pase, rutas

# Relativas a la carpeta personal. Se comparan por componentes enteros:
# «.ssh» bloquea «.ssh/id_ed25519» pero no «.sshrc».
NUNCA = (
    ".ssh", ".gnupg", ".password-store", ".pki",
    ".local/share/keyrings", ".local/share/kwalletd",
    ".mozilla", ".thunderbird", ".config/BraveSoftware", ".config/google-chrome",
    ".config/chromium", ".config/vivaldi", ".config/microsoft-edge",
    ".config/celiuz/remoto", ".local/state/celiuz/remoto",
)
MAX_ENTRADAS = 2000          # una carpeta con mas se corta (y se dice)
MAX_RESULTADOS = 200
PLAZO_BUSCAR = 3.0           # segundos: buscar no puede colgar el servicio
LADO_MIN, LADO_MAX = 64, 1024

IMAGENES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif", ".tif", ".tiff", ".heic"}
VIDEOS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"}


class Fuera(Exception):
    """La ruta sale de casa o va a un sitio de NUNCA (403)."""


class NoExiste(Exception):
    """404."""


def casa():
    return os.path.realpath(os.path.expanduser("~"))


def _prohibida(relativa):
    partes = [p for p in relativa.split(os.sep) if p]
    for n in NUNCA:
        trozos = n.split("/")
        if partes[:len(trozos)] == trozos:
            return True
    return False


def resolver(ruta):
    """(absoluta resuelta, relativa a casa) de una ruta que manda el celular.
    "" o "." es la carpeta personal. Fuera si sale o es de NUNCA; NoExiste si
    no esta."""
    if not isinstance(ruta, str) or "\0" in ruta:
        raise Fuera("ruta rara")
    if os.path.isabs(ruta):
        raise Fuera("las rutas son relativas a la carpeta personal")
    base = casa()
    absoluta = os.path.realpath(os.path.join(base, ruta))
    if absoluta != base and not absoluta.startswith(base + os.sep):
        raise Fuera("sale de la carpeta personal")
    relativa = os.path.relpath(absoluta, base)
    relativa = "" if relativa == "." else relativa
    # La escrita tambien: «.ssh/..» resuelve a casa y es inofensiva, pero
    # «.ssh/id_ed25519» tiene que caer aunque fuera un enlace a otro sitio.
    escrita = os.path.normpath(ruta)
    if _prohibida(relativa) or (escrita != "." and _prohibida(escrita)):
        raise Fuera("esa carpeta no se enseña desde el celular")
    if not os.path.lexists(absoluta):
        raise NoExiste(ruta)
    return absoluta, relativa


def _iso(marca):
    return pase.iso(dt.datetime.fromtimestamp(marca).astimezone())


def _entrada(base_abs, base_rel, nombre, ocultos):
    """Lo que se enseña de una entrada, o None si no se enseña."""
    if nombre.startswith(".") and not ocultos:
        return None
    rel = os.path.join(base_rel, nombre) if base_rel else nombre
    try:
        absoluta, rel_resuelta = resolver(rel)
        st = os.stat(absoluta)
    except (Fuera, NoExiste, OSError):
        return None      # fuera de casa, prohibida, o un enlace roto
    if stat.S_ISDIR(st.st_mode):
        try:
            n = sum(1 for e in os.scandir(absoluta) if ocultos or not e.name.startswith("."))
        except OSError:
            n = None
        return {"nombre": nombre, "tipo": "carpeta", "elementos": n,
                "modificado": _iso(st.st_mtime)}
    if not stat.S_ISREG(st.st_mode):
        return None      # sockets, fifos, dispositivos: nada que bajar
    return {"nombre": nombre, "tipo": "archivo", "tamano": st.st_size,
            "modificado": _iso(st.st_mtime)}


def _orden(e):
    return (e["tipo"] != "carpeta", e["nombre"].casefold())


def listar(ruta, ocultos=False):
    """{ruta, entradas, truncado}. Carpetas primero, por nombre."""
    absoluta, relativa = resolver(ruta)
    if not os.path.isdir(absoluta):
        raise NoExiste(ruta)
    try:
        nombres = os.listdir(absoluta)
    except PermissionError:
        raise Fuera("sin permiso para leer esa carpeta") from None
    entradas = []
    for nombre in nombres:
        e = _entrada(absoluta, relativa, nombre, ocultos)
        if e is not None:
            entradas.append(e)
    entradas.sort(key=_orden)
    return {"ruta": relativa, "entradas": entradas[:MAX_ENTRADAS],
            "truncado": len(entradas) > MAX_ENTRADAS}


def buscar(ruta, texto, ocultos=False, reloj=time.monotonic):
    """Por nombre, dentro de `ruta` y sus subcarpetas, sin distinguir mayusculas.
    Con tope de resultados y de tiempo: {ruta, q, resultados, truncado}."""
    absoluta, relativa = resolver(ruta)
    q = (texto or "").strip().casefold()
    if not q:
        return {"ruta": relativa, "q": texto, "resultados": [], "truncado": False}
    limite = reloj() + PLAZO_BUSCAR
    resultados, truncado = [], False
    for carpeta, subcarpetas, ficheros in os.walk(absoluta):
        rel_carpeta = os.path.relpath(carpeta, casa())
        rel_carpeta = "" if rel_carpeta == "." else rel_carpeta
        # No se baja a lo oculto ni a lo prohibido (ni se siguen enlaces:
        # os.walk no lo hace de fabrica, y asi no hay bucles).
        subcarpetas[:] = sorted(
            s for s in subcarpetas
            if (ocultos or not s.startswith("."))
            and not _prohibida(os.path.join(rel_carpeta, s)))
        for nombre in sorted(subcarpetas) + sorted(ficheros):
            if q not in nombre.casefold():
                continue
            e = _entrada(carpeta, rel_carpeta, nombre, ocultos)
            if e is None:
                continue
            e["ruta"] = os.path.join(rel_carpeta, nombre) if rel_carpeta else nombre
            resultados.append(e)
            if len(resultados) >= MAX_RESULTADOS:
                return {"ruta": relativa, "q": texto, "resultados": resultados, "truncado": True}
        if reloj() > limite:
            truncado = True
            break
    return {"ruta": relativa, "q": texto, "resultados": resultados, "truncado": truncado}


def archivo(ruta):
    """(absoluta, relativa, os.stat) de un fichero normal para descargarlo."""
    absoluta, relativa = resolver(ruta)
    st = os.stat(absoluta)
    if not stat.S_ISREG(st.st_mode):
        raise NoExiste(ruta)
    if not os.access(absoluta, os.R_OK):
        raise Fuera("sin permiso para leer ese archivo")
    return absoluta, relativa, st


# --- miniaturas -----------------------------------------------------------------

def tipo_miniatura(nombre):
    ext = os.path.splitext(nombre)[1].lower()
    return "imagen" if ext in IMAGENES else "video" if ext in VIDEOS else None


def miniatura(ruta, lado):
    """La ruta de un JPEG de como mucho `lado` px, hecho con ffmpeg y guardado
    en ~/.cache/celiuz/remoto/miniaturas (clave: ruta + tamaño + fecha + lado,
    asi un archivo que cambia saca otra). NoExiste si no es imagen ni video, o
    si no hay ffmpeg o no pudo."""
    absoluta, relativa, st = archivo(ruta)
    clase = tipo_miniatura(absoluta)
    if clase is None or not shutil.which("ffmpeg"):
        raise NoExiste(ruta)
    lado = max(LADO_MIN, min(LADO_MAX, int(lado)))
    clave = hashlib.sha256(f"{relativa}\0{st.st_size}\0{st.st_mtime_ns}\0{lado}".encode()).hexdigest()
    carpeta = rutas.miniaturas()
    destino = os.path.join(carpeta, clave + ".jpg")
    if os.path.exists(destino):
        return destino
    os.makedirs(carpeta, mode=0o700, exist_ok=True)
    # La extension real AL FINAL: ffmpeg elige el formato por ella (ya mordio
    # dos veces en este repo, CLAUDE.md).
    tmp = os.path.join(carpeta, f"{clave}.{os.getpid()}.nuevo.jpg")
    escala = (f"scale='min({lado},iw)':'min({lado},ih)':force_original_aspect_ratio=decrease")
    intentos = [["-ss", "3"], []] if clase == "video" else [[]]
    for antes in intentos:      # un video de menos de 3 s: desde el principio
        orden = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *antes, "-i", absoluta,
                 "-frames:v", "1", "-vf", escala, "-q:v", "4", tmp]
        try:
            r = subprocess.run(orden, capture_output=True, timeout=20, check=False,
                               stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            os.replace(tmp, destino)
            return destino
    try:
        os.unlink(tmp)
    except FileNotFoundError:
        pass
    raise NoExiste(ruta)
