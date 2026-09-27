#!/usr/bin/env python3
"""
hypr/scripts/lib/catalogo.py

Que JUEGOS, LANZADORES y APPS hay instalados en esta maquina. Es lo que ensena
la biblioteca del modo gaming, y lo que usa el dock para no ensenar juegos.

No confundir con `juegos.py`: aquel mira PROCESOS vivos («¿esto que corre es un
juego?», para no congelarlo al bloquear); este mira lo INSTALADO («¿que juegos
tengo?»). Preguntas distintas con fuentes distintas.

LAS TRES CLASES
---------------
- **juego**: lo que se juega. Sale en la biblioteca y NO en el dock.
- **lanzador**: Steam, Heroic, Lutris... Tiendas y gestores de descargas. Salen
  en el dock (el usuario deja Steam descargando horas) Y en la biblioteca.
- **app**: lo que el modo gaming deja abrir mientras juegas: el navegador
  predeterminado (para el chat de voz) y las que anada cada usuario en
  `~/.config/celiuz/modo-gaming.json`. Nada cableado: en el equipo del autor
  sale Brave, en otro saldra Firefox u Opera.

DE DONDE SALE CADA JUEGO
------------------------
1. STEAM. Sus manifiestos (`appmanifest_N.acf`, en cada biblioteca de
   `libraryfolders.vdf`) dicen que esta instalado, pero NO que es un juego:
   Proton, los Steam Linux Runtime y los redistribuibles tambien tienen
   manifiesto. Lo que si lo dice es el TIPO en `appcache/appinfo.vdf` (binario):
   medido el 2026-09-25 en la PC del autor, los juegos salen `game`/`Game`,
   Proton y los runtimes `Tool` y Wallpaper Engine `Application` — justo el que
   Steam mete en la biblioteca como si fuera un juego. Si ese fichero no se
   puede leer (formato nuevo de Steam), se cae a descartar por nombre.
2. `.desktop` con `Categories=Game` (flatpak incluidos) que no sean lanzadores
   ni herramientas: Soulframe por Proton, Hytale, el lanzador de Minecraft.
   Los accesos directos que crea Steam (`steam steam://rungameid/N`) se saltan:
   ese juego ya sale por Steam, con sus imagenes.

LAS IMAGENES
------------
Steam guarda en local las de cada juego de la biblioteca
(`appcache/librarycache/<appid>/`): la caratula vertical, el «hero» (la imagen
ancha de fondo) y el logo. A veces sueltas y a veces dentro de una subcarpeta
con nombre de hash, asi que se buscan por nombre y no por ruta.

Uso:
    catalogo.py                  resumen legible
    catalogo.py --json           todo, para la biblioteca
    catalogo.py clase CMD [ICONO]  juego | lanzador | app (lo pregunta el dock)
"""

import functools
import glob
import json
import os
import re
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import apps  # noqa: E402

JUEGO, LANZADOR, APP = "juego", "lanzador", "app"

# Tiendas y gestores de juegos. Id de .desktop en minusculas (el de flatpak es
# el id de la app). Una lista corta que se amplia cuando aparezca otro: el coste
# de no estar es que el lanzador saldria como juego, visible y sin romper nada.
LANZADORES = {
    "steam", "com.valvesoftware.steam",
    "heroic", "com.heroicgameslauncher.hgl",
    "lutris", "net.lutris.lutris",
    "com.usebottles.bottles",
    "itch", "io.itch.itch",
    "minigalaxy", "io.github.sharkwouter.minigalaxy",
    "io.github.faugus.faugus-launcher",
    "page.kramo.cartridges",
}

# Herramientas que se declaran `Game` sin serlo: gestores de Proton, de
# overlays, de mandos. Ni juego ni lanzador: no salen.
HERRAMIENTAS = {
    "com.vysp3r.protonplus", "protonplus",
    "net.davidotek.pupgui2", "protonup-qt",
    "io.github.benjamimgois.goverlay", "goverlay",
    "io.github.radiolamp.mangojuice", "mangojuice",
    "com.github.mtkennerly.ludusavi",
    "steam-rom-manager",
    "io.github.antimicrox.antimicrox", "antimicrox",
}

# Si no se puede leer el tipo de appinfo.vdf, esto no es un juego.
NO_JUEGO_STEAM = re.compile(
    r"^(proton\b|steam linux runtime|steamworks|steamvr|.*redistributable)", re.I)

STEAM_URL = re.compile(r"steam://rungameid/(\d+)")


# --- Rutas -------------------------------------------------------------------
def _casa():
    return os.path.expanduser("~")


def config_usuario():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(_casa(), ".config")
    return os.path.join(base, "celiuz", "modo-gaming.json")


def estado_usuario():
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(_casa(), ".local", "state")
    return os.path.join(base, "celiuz", "modo-gaming.json")


def raiz_steam():
    """La carpeta de Steam de este usuario, o None. Nativa primero, flatpak
    despues."""
    for r in (os.path.join(_casa(), ".local/share/Steam"),
              os.path.join(_casa(), ".steam/steam"),
              os.path.join(_casa(), ".var/app/com.valvesoftware.Steam/data/Steam")):
        if os.path.isdir(os.path.join(r, "steamapps")):
            return os.path.realpath(r)
    return None


# --- VDF de texto (los .acf y los .vdf que no son binarios) -------------------
_TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])|//[^\n]*|\[[^\]]*\]|(\S+)')


def vdf(texto):
    """El formato KeyValues de Valve, a diccionarios. Las claves en minusculas:
    Steam no es constante con las mayusculas («game» y «Game», «LastPlayed» y
    «lastplayed» segun el fichero)."""
    pila = [{}]
    clave = None
    for m in _TOKEN.finditer(texto):
        cadena, llave, suelto = m.groups()
        if llave == "{":
            nuevo = {}
            if clave is not None:
                pila[-1][clave.lower()] = nuevo
            pila.append(nuevo)
            clave = None
        elif llave == "}":
            if len(pila) > 1:
                pila.pop()
            clave = None
        elif cadena is not None or suelto is not None:
            valor = cadena if cadena is not None else suelto
            if cadena is not None:
                valor = valor.replace('\\"', '"').replace("\\\\", "\\")
            if clave is None:
                clave = valor
            else:
                pila[-1][clave.lower()] = valor
                clave = None
    return pila[0]


def _leer_vdf(ruta):
    try:
        with open(ruta, encoding="utf-8", errors="replace") as fh:
            return vdf(fh.read())
    except OSError:
        return {}


# --- appinfo.vdf (binario): solo el tipo de cada app --------------------------
def _kv_binario(datos, pos, tabla):
    """Un bloque KeyValues binario. Devuelve (dict, posicion siguiente)."""
    salida = {}
    while True:
        tipo = datos[pos]
        pos += 1
        if tipo in (8, 11):
            return salida, pos
        if tabla is not None:
            clave = tabla[struct.unpack_from("<I", datos, pos)[0]]
            pos += 4
        else:
            fin = datos.index(b"\0", pos)
            clave = datos[pos:fin].decode("utf-8", "replace")
            pos = fin + 1
        if tipo == 0:
            valor, pos = _kv_binario(datos, pos, tabla)
        elif tipo == 1:
            fin = datos.index(b"\0", pos)
            valor = datos[pos:fin].decode("utf-8", "replace")
            pos = fin + 1
        elif tipo in (2, 3, 4, 6):
            valor = struct.unpack_from("<i", datos, pos)[0]
            pos += 4
        elif tipo in (7, 10):
            valor = struct.unpack_from("<Q", datos, pos)[0]
            pos += 8
        else:
            raise ValueError("tipo KeyValues desconocido: %d" % tipo)
        salida[clave.lower()] = valor


def tipos_steam(raiz, appids):
    """{appid: tipo en minusculas} para los appids pedidos. {} si no se puede.

    Formatos conocidos: 0x07564427 (v27), 0x07564428 (v28, añade un sha1) y
    0x07564429 (v29, las claves van a una tabla de cadenas al final). Se salta
    de app en app por su tamaño, asi que solo se descodifican las pedidas.
    """
    ruta = os.path.join(raiz, "appcache", "appinfo.vdf")
    try:
        with open(ruta, "rb") as fh:
            datos = fh.read()
        magia = struct.unpack_from("<I", datos, 0)[0]
        if magia not in (0x07564427, 0x07564428, 0x07564429):
            return {}
        pos, tabla = 8, None
        if magia == 0x07564429:
            inicio = struct.unpack_from("<q", datos, 8)[0]
            cuantas = struct.unpack_from("<I", datos, inicio)[0]
            tabla = [c.decode("utf-8", "replace")
                     for c in datos[inicio + 4:].split(b"\0")[:cuantas]]
            pos = 16
        cabecera = 4 + 4 + 8 + 20 + 4 + (20 if magia >= 0x07564428 else 0)
        buscados = {int(a) for a in appids}
        tipos = {}
        while pos + 8 <= len(datos) and buscados - tipos.keys():
            appid, tam = struct.unpack_from("<II", datos, pos)
            if appid == 0:
                break
            if appid in buscados:
                kv, _ = _kv_binario(datos, pos + 8 + cabecera, tabla)
                comun = kv.get("appinfo", {}).get("common", {})
                tipos[appid] = str(comun.get("type", "")).lower()
            pos += 8 + tam
        return tipos
    except (OSError, ValueError, IndexError, struct.error):
        return {}


# --- Steam -------------------------------------------------------------------
def _bibliotecas(raiz):
    rutas = [raiz]
    for bloque in _leer_vdf(os.path.join(raiz, "steamapps", "libraryfolders.vdf")) \
            .get("libraryfolders", {}).values():
        if isinstance(bloque, dict) and bloque.get("path"):
            rutas.append(bloque["path"])
    vistas, salida = set(), []
    for r in rutas:
        real = os.path.realpath(r)
        if real not in vistas and os.path.isdir(os.path.join(real, "steamapps")):
            vistas.add(real)
            salida.append(real)
    return salida


def _imagenes_steam(raiz, appid):
    """Caratula, fondo y logo de la cache local de Steam (None si falta)."""
    base = os.path.join(raiz, "appcache", "librarycache", str(appid))

    def buscar(*nombres):
        for nombre in nombres:
            for patron in (nombre, os.path.join("*", nombre)):
                hallados = sorted(glob.glob(os.path.join(base, patron)))
                if hallados:
                    return hallados[0]
        return None

    return {
        "caratula": buscar("library_600x900.jpg", "library_capsule.jpg"),
        "fondo": buscar("library_hero.jpg"),
        "logo": buscar("logo.png"),
    }


def _tiempos_steam(raiz):
    """{appid: {"minutos", "ultima"}} de la cuenta con la que se entro la
    ultima vez. Steam lo guarda por cuenta, en userdata/<id de 32 bits>."""
    usuarios = _leer_vdf(os.path.join(raiz, "config", "loginusers.vdf")).get("users", {})
    candidatos = []
    for steamid, datos in usuarios.items():
        if not (isinstance(datos, dict) and steamid.isdigit()):
            continue
        reciente = datos.get("mostrecent") == "1"
        candidatos.append((reciente, int(datos.get("timestamp", "0") or 0),
                           int(steamid) - 76561197960265728))
    if not candidatos:
        return {}
    cuenta = max(candidatos)[2]
    local = _leer_vdf(os.path.join(raiz, "userdata", str(cuenta), "config",
                                   "localconfig.vdf"))
    apps_ = (local.get("userlocalconfigstore", {}).get("software", {})
             .get("valve", {}).get("steam", {}).get("apps", {}))
    tiempos = {}
    for appid, datos in apps_.items():
        if isinstance(datos, dict) and appid.isdigit():
            tiempos[appid] = {
                "minutos": int(datos["playtime"]) if datos.get("playtime", "").isdigit() else None,
                "ultima": int(datos["lastplayed"]) if datos.get("lastplayed", "").isdigit() else None,
            }
    return tiempos


def juegos_steam():
    raiz = raiz_steam()
    if not raiz:
        return []
    manifiestos = {}
    for biblioteca in _bibliotecas(raiz):
        for ruta in glob.glob(os.path.join(biblioteca, "steamapps", "appmanifest_*.acf")):
            estado = _leer_vdf(ruta).get("appstate", {})
            appid = estado.get("appid", "")
            if not appid.isdigit():
                continue
            # Bit 4 = totalmente instalado. Un juego a medio descargar sale en
            # Steam, pero lanzarlo desde aqui solo abriria la descarga.
            if not int(estado.get("stateflags", "0") or 0) & 4:
                continue
            manifiestos[appid] = estado

    tipos = tipos_steam(raiz, manifiestos.keys())
    tiempos = _tiempos_steam(raiz)
    juegos = []
    for appid, estado in manifiestos.items():
        nombre = estado.get("name") or appid
        tipo = tipos.get(int(appid))
        if tipo is not None:
            if tipo != "game":
                continue
        elif NO_JUEGO_STEAM.match(nombre):
            continue
        t = tiempos.get(appid, {})
        ultima = t.get("ultima")
        if not ultima and estado.get("lastplayed", "").isdigit():
            ultima = int(estado["lastplayed"]) or None
        juegos.append({
            "id": "steam:" + appid,
            "nombre": nombre,
            "tipo": JUEGO,
            "origen": "steam",
            "cmd": "steam steam://rungameid/" + appid,
            "icono": "steam_icon_" + appid,
            "arte": _imagenes_steam(raiz, appid),
            "jugado": {"minutos": t.get("minutos"), "ultima": ultima},
        })
    return juegos


# --- .desktop ----------------------------------------------------------------
def _carpetas_desktop():
    datos_casa = os.environ.get("XDG_DATA_HOME") or os.path.join(_casa(), ".local/share")
    resto = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    vistas, salida = set(), []
    for d in [datos_casa] + resto.split(":"):
        if not d:
            continue
        carpeta = os.path.join(d, "applications")
        if carpeta not in vistas:
            vistas.add(carpeta)
            salida.append(carpeta)
    return salida


@functools.lru_cache(maxsize=1)
def _entradas_desktop():
    """{id: (ruta, campos)} de todos los .desktop visibles, el primero gana
    (el orden XDG: lo del usuario pisa lo del sistema)."""
    entradas = {}
    for carpeta in _carpetas_desktop():
        for ruta in sorted(glob.glob(os.path.join(carpeta, "*.desktop"))):
            ident = os.path.basename(ruta)[:-len(".desktop")]
            if ident in entradas:
                continue
            campos = {}
            try:
                with open(ruta, encoding="utf-8", errors="replace") as fh:
                    dentro = False
                    for linea in fh:
                        linea = linea.strip()
                        if linea.startswith("["):
                            if dentro:
                                break
                            dentro = linea == "[Desktop Entry]"
                        elif dentro and "=" in linea and not linea.startswith("#"):
                            k, v = linea.split("=", 1)
                            campos.setdefault(k, v.strip())
            except OSError:
                continue
            entradas[ident] = (ruta, campos)
    return entradas


def clase_de_desktop(ident, campos):
    """juego | lanzador | None (ni lo uno ni lo otro, o una herramienta)."""
    bajo = ident.lower()
    if bajo in LANZADORES:
        return LANZADOR
    if bajo in HERRAMIENTAS:
        return None
    categorias = {c.strip().lower() for c in campos.get("Categories", "").split(";") if c.strip()}
    if "game" not in categorias:
        return None
    # Una utilidad que se apunta a Game (gestores de mandos, de Proton...).
    if categorias & {"utility", "settings"}:
        return None
    return JUEGO


def _visible(campos):
    if campos.get("NoDisplay", "").lower() == "true" or campos.get("Hidden", "").lower() == "true":
        return False
    if campos.get("Type", "Application") != "Application":
        return False
    return bool(apps.limpiar_exec(campos.get("Exec", "")))


def juegos_y_lanzadores_desktop():
    """(juegos, lanzadores) que vienen de .desktop."""
    juegos, lanzadores = [], []
    for ident, (ruta, campos) in _entradas_desktop().items():
        if not _visible(campos):
            continue
        clase = clase_de_desktop(ident, campos)
        if clase is None:
            continue
        cmd = apps.limpiar_exec(campos["Exec"])
        # El acceso directo que crea Steam: ese juego ya sale por Steam.
        if clase == JUEGO and STEAM_URL.search(cmd):
            continue
        entrada = {
            "id": ("flatpak:" if "flatpak/exports" in ruta else "desktop:") + ident,
            "nombre": campos.get("Name") or ident,
            "tipo": clase,
            "origen": "flatpak" if "flatpak/exports" in ruta else "desktop",
            "cmd": cmd,
            "icono": campos.get("Icon", ""),
            "arte": {"caratula": None, "fondo": None, "logo": None},
            "jugado": {"minutos": None, "ultima": None},
        }
        (juegos if clase == JUEGO else lanzadores).append(entrada)
    return juegos, lanzadores


# --- Lo del usuario ------------------------------------------------------------
def _leer_json(ruta):
    try:
        with open(ruta, encoding="utf-8") as fh:
            datos = json.load(fh)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def ajustes():
    """`~/.config/celiuz/modo-gaming.json`, con valores por defecto:

        apps               [{label, cmd, icon_name}] que se pueden abrir jugando
        ocultar            ids del catalogo que no deben salir ("steam:431960")
        cerrar_terminales  si el modo cierra tambien las terminales (false)
    """
    datos = _leer_json(config_usuario())
    apps_ = [a for a in datos.get("apps", []) if isinstance(a, dict) and a.get("cmd")]
    ocultar = {str(x) for x in datos.get("ocultar", [])}
    return {"apps": apps_, "ocultar": ocultar,
            "cerrar_terminales": datos.get("cerrar_terminales") is True}


def apps_permitidas(ajustes_=None):
    """El navegador predeterminado y las que anadio el usuario, sin repetir."""
    ajustes_ = ajustes_ or ajustes()
    salida, vistas = [], set()
    nav = apps.navegador()
    candidatas = ([dict(nav, navegador=True)] if nav else []) + ajustes_["apps"]
    for a in candidatas:
        if a["cmd"] in vistas:
            continue
        vistas.add(a["cmd"])
        salida.append({
            "id": "app:" + a["cmd"],
            "nombre": a.get("label") or a["cmd"],
            "tipo": APP,
            "cmd": a["cmd"],
            "icono": a.get("icon_name", ""),
            "navegador": bool(a.get("navegador")),
        })
    return salida


def apuntar_lanzado(ident):
    """Anota que se acaba de lanzar un juego que no es de Steam (Steam lleva su
    propia cuenta), para que la biblioteca lo ponga delante la proxima vez."""
    if ident.startswith("steam:"):
        return
    ruta = estado_usuario()
    datos = _leer_json(ruta)
    jugado = datos.setdefault("jugado", {})
    entrada = jugado.setdefault(ident, {})
    entrada["ultima"] = int(time.time())
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta + ".nuevo", "w", encoding="utf-8") as fh:
            json.dump(datos, fh, ensure_ascii=False, indent=2)
        os.replace(ruta + ".nuevo", ruta)
    except OSError:
        pass


def ruta_mangohud():
    """La config del overlay que genera modo-gaming.py al entrar. En la casa y
    no en $XDG_RUNTIME_DIR: los juegos de Steam corren dentro de su contenedor
    (pressure-vessel), que ve la casa pero no tiene por que ver /run/user."""
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(_casa(), ".cache")
    return os.path.join(base, "celiuz", "mangohud.conf")


def entorno_de_juego():
    """Las variables con que se lanza un juego para que lleve el overlay (vacio
    si todavia no se genero su config: sin ella no se pide overlay)."""
    ruta = ruta_mangohud()
    if not os.path.exists(ruta):
        return {}
    return {"MANGOHUD": "1", "MANGOHUD_CONFIGFILE": ruta}


_EVENTO_SHADER = re.compile(
    r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\] (?:"
    r"Starting processing job for app (?P<empieza>\d+)"
    r"|Still replaying (?P<va>\d+) \((?P<pct>\d+)%"
    r"|\[ App ID (?P<acaba>\d+) \] fossilize_replay completed"
    r"|Processing downloaded cache for AppID (?P<baja>\d+))")


def estado_shaders():
    """{"pendientes": [appid...], "procesando": (appid, porcentaje) | None}.

    `ProcessingQueue` de config.vdf NO basta: Steam solo guarda ese fichero AL
    CERRARSE, asi que con Steam abierto es un dato viejo (paso: la biblioteca
    decia que God of War no tenia nada pendiente y lo compilo al lanzarlo). Se
    corrige con lo que Steam va apuntando en logs/shader_log.txt despues de la
    ultima vez que guardo: que empezo, por que porcentaje va, que acabo, y que
    bajo shaders nuevos de otros jugadores (eso los deja pendientes)."""
    raiz = raiz_steam()
    if not raiz:
        return {"pendientes": [], "procesando": None}
    config = os.path.join(raiz, "config", "config.vdf")
    cola = cola_de_shaders()
    try:
        desde = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(config)))
    except OSError:
        desde = ""
    procesando = None
    try:
        with open(os.path.join(raiz, "logs", "shader_log.txt"), "rb") as fh:
            fh.seek(0, 2)
            fh.seek(max(0, fh.tell() - 400000))
            lineas = fh.read().decode("utf-8", "replace").splitlines()
    except OSError:
        lineas = []
    for linea in lineas:
        m = _EVENTO_SHADER.match(linea)
        if not m or m.group(1) < desde:
            continue
        if m.group("empieza"):
            procesando = (m.group("empieza"), 0)
        elif m.group("va"):
            procesando = (m.group("va"), int(m.group("pct")))
        elif m.group("acaba"):
            cola = [x for x in cola if x != m.group("acaba")]
            if procesando and procesando[0] == m.group("acaba"):
                procesando = None
        elif m.group("baja") and m.group("baja") not in cola:
            cola.append(m.group("baja"))
    if procesando and procesando[0] not in cola:
        cola.insert(0, procesando[0])
    return {"pendientes": cola, "procesando": procesando}


def cola_de_shaders():
    """Los appids que Steam tiene pendientes de procesar shaders, en orden
    (`ProcessingQueue` de config/config.vdf)."""
    raiz = raiz_steam()
    if not raiz:
        return []
    try:
        with open(os.path.join(raiz, "config", "config.vdf"), encoding="utf-8", errors="replace") as fh:
            m = re.search(r'"ProcessingQueue"\s+"([^"]*)"', fh.read())
    except OSError:
        return []
    return [x for x in (m.group(1).split(";") if m else []) if x.isdigit()]


# --- Todo junto ----------------------------------------------------------------
def _orden_juegos(juego):
    """El ultimo jugado primero; los nunca jugados, por nombre, al final."""
    ultima = juego["jugado"]["ultima"] or 0
    return (-ultima, juego["nombre"].lower())


def catalogo():
    aj = ajustes()
    juegos_d, lanzadores = juegos_y_lanzadores_desktop()
    # Lo que la biblioteca apunta al lanzar un juego que no es de Steam (Steam
    # ya lleva su propia cuenta).
    jugado = _leer_json(estado_usuario()).get("jugado", {})
    for j in juegos_d:
        if j["id"] in jugado and isinstance(jugado[j["id"]], dict):
            j["jugado"].update({k: jugado[j["id"]].get(k) for k in ("minutos", "ultima")})
    juegos = [j for j in juegos_steam() + juegos_d if j["id"] not in aj["ocultar"]]
    shaders = estado_shaders()
    pendientes = set(shaders["pendientes"])
    for j in juegos:
        j["shaders_pendientes"] = j["id"].startswith("steam:") and j["id"][6:] in pendientes
        if shaders["procesando"] and j["id"] == "steam:" + shaders["procesando"][0]:
            j["shaders_porcentaje"] = shaders["procesando"][1]
    juegos.sort(key=_orden_juegos)
    lanzadores.sort(key=lambda x: x["nombre"].lower())
    return {
        "juegos": juegos,
        "lanzadores": [x for x in lanzadores if x["id"] not in aj["ocultar"]],
        "apps": apps_permitidas(aj),
    }


def _normal(cmd):
    """Un comando para comparar: el programa por su nombre, sin la ruta
    (`steam` y `/usr/bin/steam` son el mismo), y los espacios en orden."""
    partes = (cmd or "").split()
    if not partes:
        return ""
    return " ".join([os.path.basename(partes[0])] + partes[1:])


def clase_de_orden(cmd, icono=""):
    """Para el dock: si lo que lanza CMD es un juego, un lanzador o una app.

    Se reconoce por la URL de Steam, por el id del .desktop que coincida con el
    icono (el dock guarda el `Icon=` del .desktop), o por el `Exec=`."""
    if STEAM_URL.search(cmd or ""):
        return JUEGO
    limpio = _normal(cmd)
    for ident, (_, campos) in _entradas_desktop().items():
        clase = clase_de_desktop(ident, campos)
        if clase is None:
            continue
        if icono and icono in (ident, campos.get("Icon")):
            return clase
        if limpio and limpio == _normal(apps.limpiar_exec(campos.get("Exec", ""))):
            return clase
    return APP


def _horas(minutos):
    if not minutos:
        return ""
    return "%d h" % round(minutos / 60) if minutos >= 60 else "%d min" % minutos


def _cli(argv):
    if argv[:1] == ["clase"] and len(argv) in (2, 3):
        print(clase_de_orden(argv[1], argv[2] if len(argv) == 3 else ""))
        return 0
    if argv and argv != ["--json"]:
        print("uso: catalogo.py [--json] | clase CMD [ICONO]", file=sys.stderr)
        return 2
    cat = catalogo()
    if argv == ["--json"]:
        print(json.dumps(cat, ensure_ascii=False, indent=2))
        return 0
    for titulo, clave in (("JUEGOS", "juegos"), ("LANZADORES", "lanzadores"), ("APPS", "apps")):
        print("%s (%d)" % (titulo, len(cat[clave])))
        for x in cat[clave]:
            extra = ""
            if clave == "juegos":
                j = x["jugado"]
                cuando = time.strftime("%Y-%m-%d", time.localtime(j["ultima"])) if j["ultima"] else ""
                extra = "  ".join(p for p in (_horas(j["minutos"]), cuando) if p)
                sin = [k for k, v in x["arte"].items() if not v]
                if x["origen"] == "steam" and sin:
                    extra += "  (sin %s)" % ", ".join(sin)
            print("  %-34s %-8s %s" % (x["nombre"][:34], x.get("origen", ""), extra))
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
