"""
~/dotfiles/hypr/scripts/lib/wallpapers.py

Todo lo que hay que saber sobre los fondos de pantalla, en un solo sitio:
donde estan, cual esta puesto, como se cambia y como se le habla a mpvpaper.

Lo usan CeliuzPaper (la app) y set-wallpaper.sh (la version de terminal), y es
por donde entraria un asistente: aqui no hay interfaz, solo datos y acciones.

Los fondos vienen del Workshop de Wallpaper Engine. De sus cuatro tipos solo los
de tipo "video" son un archivo reproducible por mpvpaper; los de "scene" y "web"
necesitan el motor de Wallpaper Engine, y los de "application" son ejecutables de
Windows (el vector de la campana de malware del Workshop de 2025: aqui no se
ejecutan, pero se reconocen y se descartan).
"""

import json
import os
import re
import socket
import subprocess

CASA = os.path.expanduser("~")
WALLDIR = os.path.join(CASA, "dotfiles/hypr/wallpapers")
CURRENT = os.path.join(WALLDIR, "current")
LANZADOR = os.path.join(CASA, "dotfiles/hypr/scripts/wallpaper.sh")

RUNTIME = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
MPV_SOCKET = os.path.join(RUNTIME, "mpvpaper.sock")
# FIFO del demonio de ahorro: mientras se esta eligiendo fondo hay que pedirle
# que no toque la pausa, o pausaria el video de la vista previa.
FIFO_PAUSA = os.path.join(RUNTIME, "wallpaper-pause.fifo")

CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.join(CASA, ".cache")),
                     "celiuzpaper")
CACHE_MINIATURAS = os.path.join(CACHE, "thumbs")
CACHE_DATOS = os.path.join(CACHE, "info.json")

# 431960 = el appid de Wallpaper Engine en Steam.
WE_APPID = 431960
# Carpetas propias, para videos que no vengan del Workshop. No hace falta que
# existan; si las creas, sus videos salen en la lista automaticamente.
CARPETAS_PROPIAS = [
    os.path.join(CASA, "Vídeos/wallpapers"),
    os.path.join(CASA, "Videos/wallpapers"),
    os.path.join(WALLDIR, "propios"),
]
EXTENSIONES = (".mp4", ".mkv", ".webm", ".mov", ".avi")

# Ancho al que se guardan las miniaturas. 440 da nitidez de sobra para tarjetas
# de 220 px y sigue pesando ~15 KB por fondo.
ANCHO_MINIATURA = 440


# --- Donde estan los fondos ---------------------------------------------------

def _bibliotecas_steam():
    """Carpetas del Workshop de Wallpaper Engine en todas las bibliotecas.

    Steam puede tener varias (la del usuario esta en un disco aparte), y las
    declara en libraryfolders.vdf.
    """
    bases = [os.path.join(CASA, ".local/share/Steam"), os.path.join(CASA, ".steam/steam")]
    for vdf in (os.path.join(CASA, ".local/share/Steam/steamapps/libraryfolders.vdf"),
                os.path.join(CASA, ".steam/steam/steamapps/libraryfolders.vdf")):
        try:
            with open(vdf, encoding="utf-8", errors="replace") as fh:
                bases += re.findall(r'"path"\s+"([^"]+)"', fh.read())
        except OSError:
            continue
    vistas = []
    for base in bases:
        ruta = os.path.join(base, "steamapps/workshop/content", str(WE_APPID))
        if os.path.isdir(ruta) and ruta not in vistas:
            vistas.append(ruta)
    return vistas


def _leer_item(carpeta):
    """Un fondo del Workshop, o None si su project.json no se puede leer."""
    try:
        with open(os.path.join(carpeta, "project.json"), encoding="utf-8",
                  errors="replace") as fh:
            proyecto = json.load(fh)
    except (OSError, ValueError):
        return None

    tipo = (proyecto.get("type") or "?").lower()
    archivo = proyecto.get("file") or ""
    video = os.path.join(carpeta, archivo) if archivo else ""
    vista = proyecto.get("preview") or ""
    return {
        "id": os.path.basename(carpeta.rstrip("/")),
        "titulo": proyecto.get("title") or os.path.basename(carpeta),
        "tipo": tipo,
        "video": video,
        "vista": os.path.join(carpeta, vista) if vista else "",
        "etiquetas": proyecto.get("tags") or [],
        # Solo sirve si es video Y el archivo existe: algunos "video" apuntan a un
        # .pkg empaquetado que no es reproducible.
        "usable": tipo == "video" and bool(video) and os.path.isfile(video),
    }


def _leer_propio(ruta):
    return {
        "id": "propio:" + os.path.basename(ruta),
        "titulo": os.path.splitext(os.path.basename(ruta))[0],
        "tipo": "video",
        "video": ruta,
        "vista": "",
        "etiquetas": ["propio"],
        "usable": True,
    }


def escanear():
    """Todos los fondos encontrados, usables o no, ordenados por titulo."""
    fondos = []
    for dir_workshop in _bibliotecas_steam():
        for nombre in sorted(os.listdir(dir_workshop)):
            carpeta = os.path.join(dir_workshop, nombre)
            if os.path.isdir(carpeta):
                item = _leer_item(carpeta)
                if item:
                    fondos.append(item)
    for carpeta in CARPETAS_PROPIAS:
        if not os.path.isdir(carpeta):
            continue
        for nombre in sorted(os.listdir(carpeta)):
            if nombre.lower().endswith(EXTENSIONES):
                fondos.append(_leer_propio(os.path.join(carpeta, nombre)))
    fondos.sort(key=lambda f: f["titulo"].lower())
    return fondos


def usables(fondos=None):
    """Los que mpvpaper puede reproducir, sin repetidos.

    Se quitan los que apuntan al MISMO archivo: en el Workshop es normal acabar
    suscrito dos veces al mismo video (subido por dos cuentas, o resubido), y en
    un selector visual dos tarjetas identicas solo hacen dudar.
    """
    fuera = []
    vistos = set()
    for fondo in (fondos if fondos is not None else escanear()):
        if not fondo["usable"]:
            continue
        # La clave es nombre + tamano, no la ruta: los duplicados del Workshop
        # son COPIAS del mismo video en carpetas distintas, asi que por ruta no se
        # detectarian.
        try:
            clave = (os.path.basename(fondo["video"]), os.path.getsize(fondo["video"]))
        except OSError:
            clave = (fondo["video"], 0)
        if clave in vistos:
            continue
        vistos.add(clave)
        fuera.append(fondo)
    return fuera


# --- Cual esta puesto, y como cambiarlo ---------------------------------------

def actual():
    """Ruta del video que esta puesto de fondo, o None si no hay ninguno."""
    try:
        return os.path.realpath(CURRENT) if os.path.exists(CURRENT) else None
    except OSError:
        return None


def aplicar(video, relanzar=None):
    """Deja este video como fondo, de forma permanente.

    Cambiar de fondo es repuntar el enlace `current`: nada mas. Si mpvpaper ya
    esta reproduciendo ese archivo (porque venia de la vista previa en vivo) no
    hace falta reiniciarlo, y de ahi que `relanzar` sea automatico por defecto.
    """
    video = os.path.realpath(video)
    if not os.path.isfile(video):
        raise FileNotFoundError(video)
    os.makedirs(WALLDIR, exist_ok=True)
    tmp = CURRENT + ".nuevo"
    # Se crea aparte y se mueve encima: asi el enlace nunca queda a medias, y
    # os.symlink no falla por "ya existe".
    if os.path.lexists(tmp):
        os.remove(tmp)
    os.symlink(video, tmp)
    os.replace(tmp, CURRENT)

    if relanzar is None:
        relanzar = reproduciendo() != video
    if relanzar:
        subprocess.Popen([LANZADOR, "--only-mpv"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return video


# --- Hablar con mpvpaper ------------------------------------------------------

def mpv(*orden):
    """Manda una orden al socket IPC de mpv y devuelve su respuesta (o None).

    Que no haya socket es normal, no un error: puede que mpvpaper no este
    corriendo (arranque en frio, o lo mato el demonio por la stoplist).
    """
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(MPV_SOCKET)
            s.sendall((json.dumps({"command": list(orden)}) + "\n").encode())
            return json.loads(s.recv(8192).decode(errors="replace").splitlines()[0])
    except (OSError, ValueError, IndexError):
        return None


def mpv_vivo():
    return mpv("get_property", "path") is not None


def reproduciendo():
    """Ruta real del video que mpvpaper tiene cargado ahora mismo."""
    r = mpv("get_property", "path")
    if not r or r.get("error") != "success":
        return None
    ruta = r.get("data") or ""
    return os.path.realpath(ruta) if ruta else None


def previsualizar(video):
    """Carga un video en el fondo YA, sin tocar nada permanente.

    Es lo que hace que elegir fondo sea mirar el escritorio en vez de mirar
    miniaturas: `loadfile` cambia el video en marcha, sin reiniciar mpvpaper y
    sin que parpadee. Se quita la pausa porque el demonio de ahorro la pone
    cuando hay ventanas abiertas, y un fondo congelado no se puede juzgar.
    """
    if mpv("loadfile", video) is None:
        return False
    mpv("set_property", "pause", False)
    return True


def _hypr(comando):
    """Pregunta al socket de control de Hyprland. Cadena vacia si no se puede."""
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not sig:
        return ""
    ruta = os.path.join(RUNTIME, "hypr", sig, ".socket.sock")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(ruta)
            s.sendall(comando.encode())
            trozos = []
            while True:
                trozo = s.recv(8192)
                if not trozo:
                    break
                trozos.append(trozo)
        return b"".join(trozos).decode(errors="replace")
    except OSError:
        return ""


def despejar_escritorio():
    """Lleva a un workspace vacio para poder VER el fondo. Devuelve a donde volver.

    Hace falta porque el fondo esta detras de las ventanas: con los gaps a 0, una
    sola ventana lo tapa entero, asi que un selector transparente ensenaria las
    ventanas y no el fondo. Se busca el primer workspace sin ventanas (Hyprland
    los crea al vuelo, asi que siempre hay uno) y se vuelve al salir.

    Devuelve el id del workspace de origen, o None si no hizo falta moverse
    (porque ya estabas en uno vacio) o si no se pudo.
    """
    try:
        activo = json.loads(_hypr("j/activeworkspace"))
        espacios = json.loads(_hypr("j/workspaces"))
    except ValueError:
        return None
    if activo.get("windows", 0) == 0:
        return None
    ocupados = {w["id"] for w in espacios if w.get("windows", 0) > 0}
    destino = next((i for i in range(1, 100) if i not in ocupados), None)
    if destino is None:
        return None
    _hypr(f"dispatch workspace {destino}")
    return activo.get("id")


def volver_al_escritorio(origen):
    if origen is not None:
        _hypr(f"dispatch workspace {origen}")


def avisar_pausa(mensaje):
    """`hold` = que el demonio de ahorro no toque la pausa; `release` = que vuelva
    a mandar el (y que recalcule ya)."""
    try:
        fd = os.open(FIFO_PAUSA, os.O_WRONLY | os.O_NONBLOCK)
        try:
            os.write(fd, (mensaje + "\n").encode())
        finally:
            os.close(fd)
        return True
    except OSError:
        return False   # sin demonio, la app funciona igual


# --- Miniaturas y datos de cada video ----------------------------------------

def _ffprobe(video):
    try:
        salida = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height,duration", "-of", "csv=p=0", video],
            capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return {}
    partes = salida.split(",")
    datos = {}
    try:
        datos["ancho"] = int(partes[0])
        datos["alto"] = int(partes[1])
    except (IndexError, ValueError):
        pass
    try:
        datos["duracion"] = float(partes[2])
    except (IndexError, ValueError):
        pass
    return datos


def _cargar_cache():
    try:
        with open(CACHE_DATOS) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _guardar_cache(cache):
    try:
        os.makedirs(CACHE, exist_ok=True)
        with open(CACHE_DATOS, "w") as fh:
            json.dump(cache, fh)
    except OSError:
        pass


def miniatura(fondo, generar=True):
    """Ruta de la miniatura 16:9 del fondo, sacada del propio video.

    Las vistas previas que trae Wallpaper Engine son cuadradas (192x192), asi que
    recortadas a 16:9 se pierde medio fondo. Se saca un fotograma de verdad con
    ffmpeg (a 3 s, o al 10% si el video es mas corto) y se guarda en cache: cuesta
    ~0.27 s la primera vez y cero las siguientes.

    Con generar=False no crea nada: devuelve la miniatura si ya existe y, si no,
    la vista previa de Wallpaper Engine, que sirve de relleno instantaneo mientras
    la de verdad se genera en segundo plano.
    """
    if not fondo.get("video"):
        return fondo.get("vista") or None
    destino = os.path.join(CACHE_MINIATURAS, f"{fondo['id']}.jpg")
    if os.path.exists(destino):
        try:
            if os.path.getmtime(destino) >= os.path.getmtime(fondo["video"]):
                return destino
        except OSError:
            return destino
    if not generar:
        return fondo.get("vista") or None

    info = datos(fondo)
    duracion = info.get("duracion") or 0
    momento = 3.0 if duracion > 6 else max(0.0, duracion * 0.1)
    try:
        os.makedirs(CACHE_MINIATURAS, exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{momento:.2f}",
             "-i", fondo["video"], "-frames:v", "1",
             "-vf", f"scale={ANCHO_MINIATURA}:-2", "-y", destino],
            capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return fondo.get("vista") or None
    return destino if os.path.exists(destino) else (fondo.get("vista") or None)


def datos(fondo):
    """Ancho, alto, duracion y tamano del video. En cache tras la primera vez."""
    cache = _cargar_cache()
    clave = fondo["id"]
    guardado = cache.get(clave)
    try:
        peso = os.path.getsize(fondo["video"])
    except OSError:
        peso = 0
    if guardado and guardado.get("peso") == peso:
        return guardado

    info = _ffprobe(fondo["video"])
    info["peso"] = peso
    cache[clave] = info
    _guardar_cache(cache)
    return info


def describir(fondo, info=None):
    """Linea de datos legible: «1920x1080 · 14 s · 10.1 MB»."""
    info = info if info is not None else datos(fondo)
    trozos = []
    if info.get("ancho"):
        trozos.append(f"{info['ancho']}x{info['alto']}")
    if info.get("duracion"):
        trozos.append(f"{info['duracion']:.0f} s")
    if info.get("peso"):
        trozos.append(f"{info['peso'] / 1_048_576:.1f} MB")
    return "  ·  ".join(trozos)


def buscar(texto, fondos=None):
    """Fondos usables cuyo titulo o nombre de archivo contiene el texto."""
    lista = usables(fondos)
    t = texto.strip().lower()
    if not t:
        return []
    exactos = [f for f in lista if f["titulo"].lower() == t]
    if exactos:
        return exactos
    return [f for f in lista
            if t in f["titulo"].lower() or t in os.path.basename(f["video"]).lower()]
