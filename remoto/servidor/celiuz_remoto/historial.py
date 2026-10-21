"""
remoto/servidor/celiuz_remoto/historial.py — recientes y favoritos del explorador.

Fase 6. Vive en LA PC (~/.local/state/celiuz/remoto/historial.json, 0600), no
en el celular: si cambias de celular lo conservas, y si te lo roban no se
llevan la lista (remoto/DISEÑO.md, «Archivos»). Uno por usuario, no por
telefono: cada reciente apunta cual lo bajo.

Un reciente recuerda el tamaño y la fecha que tenia el archivo AL BAJARLO, y
con eso se dice su estado contra la PC: «igual», «nueva_version» (cambio el
tamaño o la fecha) o «no_esta». Los favoritos son archivos o carpetas fijados,
con si siguen existiendo.

Las rutas son relativas a la carpeta personal, las mismas que /v0/archivos.
"""

import datetime as dt
import json
import os
import threading
import time

from . import archivos, pase, rutas

MAX_RECIENTES = 200
_cerrojo = threading.Lock()


def _leer():
    try:
        with open(rutas.historial(), encoding="utf-8") as fh:
            datos = json.load(fh)
    except (OSError, ValueError):
        datos = {}
    if not isinstance(datos, dict):
        datos = {}
    datos.setdefault("recientes", [])
    datos.setdefault("favoritos", [])
    return datos


def _escribir(datos):
    ruta = rutas.historial()
    os.makedirs(os.path.dirname(ruta), mode=0o700, exist_ok=True)
    tmp = ruta + ".nuevo"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, ruta)


def _iso(marca):
    return pase.iso(dt.datetime.fromtimestamp(marca).astimezone())


def apuntar_descarga(relativa, st, dispositivo, ahora=None):
    """Un archivo bajado entero. Si ya estaba, sube arriba con los datos nuevos."""
    with _cerrojo:
        datos = _leer()
        recientes = [r for r in datos["recientes"] if r.get("ruta") != relativa]
        recientes.insert(0, {"ruta": relativa, "bajado": _iso(ahora or time.time()),
                             "tamano": st.st_size, "mtime_ns": st.st_mtime_ns,
                             "dispositivo": dispositivo})
        datos["recientes"] = recientes[:MAX_RECIENTES]
        _escribir(datos)


def _estado(r):
    try:
        absoluta, _ = archivos.resolver(r["ruta"])
        st = os.stat(absoluta)
    except (archivos.Fuera, archivos.NoExiste, OSError):
        return "no_esta"
    if st.st_size == r.get("tamano") and st.st_mtime_ns == r.get("mtime_ns"):
        return "igual"
    return "nueva_version"


def recientes():
    with _cerrojo:
        lista = _leer()["recientes"]
    salida = []
    for r in lista:
        salida.append({"ruta": r["ruta"], "nombre": os.path.basename(r["ruta"]),
                       "carpeta": os.path.dirname(r["ruta"]), "bajado": r.get("bajado"),
                       "tamano": r.get("tamano"), "dispositivo": r.get("dispositivo"),
                       "estado": _estado(r)})
    return salida


def olvidar(relativa=None):
    """Quita un reciente (o todos, sin ruta). Solo la lista: el archivo no se toca."""
    with _cerrojo:
        datos = _leer()
        antes = len(datos["recientes"])
        datos["recientes"] = [] if relativa is None else \
            [r for r in datos["recientes"] if r.get("ruta") != relativa]
        _escribir(datos)
        return antes - len(datos["recientes"])


def favoritos():
    with _cerrojo:
        lista = _leer()["favoritos"]
    salida = []
    for f in lista:
        try:
            absoluta, _ = archivos.resolver(f["ruta"])
            tipo = "carpeta" if os.path.isdir(absoluta) else "archivo"
            existe = True
        except (archivos.Fuera, archivos.NoExiste, OSError):
            tipo, existe = f.get("tipo", "archivo"), False
        salida.append({"ruta": f["ruta"], "nombre": os.path.basename(f["ruta"]) or "Carpeta personal",
                       "tipo": tipo, "existe": existe, "desde": f.get("desde")})
    return salida


def fijar(ruta, ahora=None):
    """Añade un favorito (la ruta tiene que valer: resolver() lanza si no).
    Devuelve la relativa ya normalizada."""
    absoluta, relativa = archivos.resolver(ruta)
    tipo = "carpeta" if os.path.isdir(absoluta) else "archivo"
    with _cerrojo:
        datos = _leer()
        if not any(f.get("ruta") == relativa for f in datos["favoritos"]):
            datos["favoritos"].append({"ruta": relativa, "tipo": tipo,
                                       "desde": _iso(ahora or time.time())})
            _escribir(datos)
    return relativa


def soltar(ruta):
    """Quita un favorito. Por la ruta tal cual: uno que ya no existe tambien se
    tiene que poder quitar."""
    relativa = os.path.normpath(ruta) if ruta not in ("", ".") else ""
    with _cerrojo:
        datos = _leer()
        antes = len(datos["favoritos"])
        datos["favoritos"] = [f for f in datos["favoritos"] if f.get("ruta") != relativa]
        _escribir(datos)
        return antes != len(datos["favoritos"])


def rutas_favoritas():
    with _cerrojo:
        return {f["ruta"] for f in _leer()["favoritos"]}
