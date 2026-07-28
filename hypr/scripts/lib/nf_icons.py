"""
~/dotfiles/hypr/scripts/lib/nf_icons.py

Buscador de iconos de la Nerd Font, leyendo el .ttf directamente.

Para que el gestor del dock pueda ofrecer "busca un icono para esta app" hacen
falta los NOMBRES de los glifos, no solo sus codigos. Las fuentes parcheadas de
Nerd Fonts los traen dentro (md-firefox, oct-terminal, dev-python...), asi que
se sacan de ahi: se leen las tablas `cmap` (codigo -> glifo) y `post` (glifo ->
nombre) del fichero y se cruzan.

Por que no usar fontTools: obligaria a instalar python-fonttools solo para esto.
El formato de estas dos tablas es fijo y llevan decadas sin cambiar, asi que sale
mas barato leerlas aqui (unas 80 lineas) que anadir una dependencia.

Solo se miran los codigos de las zonas de uso privado, que es donde Nerd Fonts
mete sus iconos: el resto de la fuente son letras normales.

El resultado se guarda en cache (~/.cache/dock-manager/icons-<mtime>.json)
porque recorrer el .ttf tarda ~0.4 s y el gestor tiene que abrirse al instante.
"""

import json
import os
import struct

FUENTE = "/usr/share/fonts/TTF/MesloLGSNerdFont-Regular.ttf"
CACHE_DIR = os.path.expanduser("~/.cache/dock-manager")

# Zonas de uso privado donde Nerd Fonts coloca sus iconos. El primer bloque es
# el area de uso privado del plano basico; el segundo, el plano 15 (suplementario
# de uso privado), que es donde viven los miles de iconos Material Design.
RANGOS = ((0xE000, 0xF8FF), (0xF0000, 0xFFFFD))


def _tablas(data):
    _, num = struct.unpack(">IH", data[:6])
    tablas = {}
    for i in range(num):
        off = 12 + i * 16
        tag, _, offset, length = struct.unpack(">4sIII", data[off:off + 16])
        tablas[tag.decode("latin1")] = (offset, length)
    return tablas


def _en_rango(cp):
    return any(a <= cp <= b for a, b in RANGOS)


def _cmap(data, tablas):
    """codigo -> numero de glifo, solo de las zonas de uso privado."""
    base, _ = tablas["cmap"]
    _, n = struct.unpack(">HH", data[base:base + 4])
    fuera = {}
    for i in range(n):
        _, _, off = struct.unpack(">HHI", data[base + 4 + i * 8:base + 12 + i * 8])
        sub = base + off
        fmt = struct.unpack(">H", data[sub:sub + 2])[0]

        if fmt == 4:
            # Formato 4: segmentos del plano basico. idRangeOffset != 0 obliga a
            # saltar a un array de glifos que empieza en la propia posicion del
            # offset, de ahi la aritmetica con `ro_base`.
            seg2 = struct.unpack(">H", data[sub + 6:sub + 8])[0]
            seg = seg2 // 2
            ends = struct.unpack(f">{seg}H", data[sub + 14:sub + 14 + seg2])
            p = sub + 16 + seg2
            starts = struct.unpack(f">{seg}H", data[p:p + seg2])
            p += seg2
            deltas = struct.unpack(f">{seg}h", data[p:p + seg2])
            p += seg2
            ro_base = p
            rangos = struct.unpack(f">{seg}H", data[p:p + seg2])
            for i2 in range(seg):
                for cp in range(starts[i2], min(ends[i2], 0xFFFF) + 1):
                    if not _en_rango(cp):
                        continue
                    if rangos[i2] == 0:
                        gid = (cp + deltas[i2]) & 0xFFFF
                    else:
                        gp = ro_base + i2 * 2 + rangos[i2] + (cp - starts[i2]) * 2
                        if gp + 2 > len(data):
                            continue
                        gid = struct.unpack(">H", data[gp:gp + 2])[0]
                        if gid:
                            gid = (gid + deltas[i2]) & 0xFFFF
                    if gid:
                        fuera.setdefault(cp, gid)

        elif fmt == 12:
            # Formato 12: grupos contiguos, y es el unico que cubre los planos
            # altos (los iconos md- viven en U+F0000+).
            ngrupos = struct.unpack(">I", data[sub + 12:sub + 16])[0]
            for i2 in range(ngrupos):
                ini, fin, gini = struct.unpack(">III", data[sub + 16 + i2 * 12:sub + 28 + i2 * 12])
                for cp in range(ini, min(fin, 0x10FFFF) + 1):
                    if _en_rango(cp):
                        fuera.setdefault(cp, gini + (cp - ini))
    return fuera


def _nombres(data, tablas):
    """numero de glifo -> nombre. Solo la version 2.0 de `post` los trae."""
    if "post" not in tablas:
        return {}
    base, length = tablas["post"]
    if struct.unpack(">I", data[base:base + 4])[0] != 0x00020000:
        return {}
    nglifos = struct.unpack(">H", data[base + 32:base + 34])[0]
    indices = struct.unpack(f">{nglifos}H", data[base + 34:base + 34 + nglifos * 2])
    p = base + 34 + nglifos * 2
    fin = base + length
    pila = []
    while p < fin:
        ln = data[p]
        pila.append(data[p + 1:p + 1 + ln].decode("latin1"))
        p += 1 + ln
    # Los indices por debajo de 258 son los nombres estandar de Macintosh
    # (letras y signos); los iconos siempre caen por encima.
    salida = {}
    for gid, idx in enumerate(indices):
        if idx >= 258 and idx - 258 < len(pila):
            salida[gid] = pila[idx - 258]
    return salida


def _leer_fuente(ruta):
    with open(ruta, "rb") as fh:
        data = fh.read()
    tablas = _tablas(data)
    nombres = _nombres(data, tablas)
    return {nombres[gid]: cp for cp, gid in _cmap(data, tablas).items() if gid in nombres}


def iconos(ruta=FUENTE):
    """{nombre del glifo: codigo}. Con cache en disco por mtime de la fuente."""
    try:
        mtime = int(os.path.getmtime(ruta))
    except OSError:
        return {}
    cache = os.path.join(CACHE_DIR, f"icons-{mtime}.json")
    try:
        with open(cache) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        pass

    tabla = _leer_fuente(ruta)
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        # Se limpian los caches de versiones anteriores de la fuente.
        for viejo in os.listdir(CACHE_DIR):
            if viejo.startswith("icons-") and viejo != os.path.basename(cache):
                os.remove(os.path.join(CACHE_DIR, viejo))
        with open(cache, "w") as fh:
            json.dump(tabla, fh)
    except OSError:
        pass
    return tabla


# Colecciones preferidas, en orden. Los iconos del dock actual son casi todos
# de Material Design (md-), que es la coleccion mas completa y de trazo mas
# uniforme; las demas se dejan pero puntuan peor al sugerir.
PREFERIDAS = ("md-", "fa-", "cod-", "oct-", "dev-", "linux-", "seti-")


def _rango(nombre, termino):
    """Como de buena es la coincidencia. Menos es mejor; None = no vale.

    La distincion importante es entre "palabra suelta" y "trozo de otra
    palabra": sin ella, buscar "mission" devuelve md-transmission_tower.
    """
    bajo = nombre.lower()
    cuerpo = bajo.split("-", 1)[1] if "-" in bajo else bajo
    palabras = cuerpo.replace("-", "_").split("_")
    if cuerpo == termino:
        return 0
    if palabras and palabras[0] == termino:
        return 1
    if termino in palabras:
        return 2
    if cuerpo.startswith(termino):
        return 3
    if termino in cuerpo:
        return 4
    return None


def _coleccion(nombre):
    for i, pref in enumerate(PREFERIDAS):
        if nombre.startswith(pref):
            return i
    return len(PREFERIDAS)


def buscar(termino, limite=64, tabla=None, max_rango=4):
    """Iconos cuyo nombre encaja con el termino, mejores primero.

    Orden: calidad de la coincidencia, coleccion preferida y luego lo corto que
    sea el nombre (los largos suelen ser variantes: md-firefox vs
    md-firefox_outline).
    """
    tabla = iconos() if tabla is None else tabla
    t = termino.strip().lower().replace(" ", "_")
    if not t:
        return []
    aciertos = []
    for nombre, cp in tabla.items():
        r = _rango(nombre, t)
        if r is None or r > max_rango:
            continue
        aciertos.append((r, _coleccion(nombre), len(nombre), nombre, cp))
    aciertos.sort()
    return [(n, cp) for _, _, _, n, cp in aciertos[:limite]]


def sugerir(*pistas, tabla=None):
    """Primer icono que encaje de verdad con alguna pista (nombre de app, binario).

    Se prueban en orden y con la frase entera antes que troceada. Solo acepta
    coincidencias de palabra completa (rango <= 2): mas suelto que eso acaba
    proponiendo iconos absurdos, y es mejor no sugerir nada que sugerir mal.
    """
    tabla = iconos() if tabla is None else tabla
    intentos = []
    for pista in pistas:
        if not pista:
            continue
        limpio = pista.strip().lower()
        if limpio not in intentos:
            intentos.append(limpio)
        for trozo in limpio.replace("-", " ").replace("_", " ").replace(".", " ").split():
            if len(trozo) > 2 and trozo not in intentos:
                intentos.append(trozo)
    for pista in intentos:
        res = buscar(pista, limite=1, tabla=tabla, max_rango=2)
        if res:
            return res[0]
    return None
