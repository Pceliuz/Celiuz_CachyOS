"""
~/dotfiles/hypr/scripts/lib/wallpapers.py

Todo lo que hay que saber sobre los fondos de pantalla, en un solo sitio:
donde estan, cual esta puesto, como se cambia y como se le habla a mpvpaper.

Lo usan CeliuzPaper (la app) y set-wallpaper.sh (la version de terminal), y es
por donde entraria un asistente: aqui no hay interfaz, solo datos y acciones.

Los fondos salen de varias FUENTES, y cada una es un modulo en el selector:

  Wallpaper Engine   los del Workshop de Steam. De sus cuatro tipos solo los de
                     tipo "video" son un archivo reproducible por mpvpaper; los
                     de "scene" y "web" necesitan el motor de Wallpaper Engine, y
                     los de "application" son ejecutables de Windows (el vector
                     de la campana de malware del Workshop de 2025: aqui no se
                     ejecutan, pero se reconocen y se descartan).
  Tu carpeta de      la que el sistema diga, en el idioma que sea. NO se busca
  videos             "Videos" a pelo: se pregunta al estandar XDG, que aqui
                     responde ~/Vídeos y en otro equipo respondera ~/Videos,
                     ~/Vidéos o lo que toque.
  Carpetas anadidas  las que anadas tu desde la app, guardadas FUERA del repo.

Nada de esto se configura al instalar: si no hay Steam, el modulo de Wallpaper
Engine no aparece; si no hay carpeta de videos, tampoco. Clonar el repo en otra
maquina y abrir la app es todo lo que hay que hacer.

UN FONDO PUEDE SER UN VIDEO O UNA IMAGEN FIJA. Los dos los pinta el mismo
mpvpaper. Por historia, la ruta del fichero se guarda en la clave "video" aunque
sea un jpg; lo que distingue a los dos es la clave "imagen".
"""

import json
import os
import re
import socket
import subprocess

CASA = os.path.expanduser("~")
# La raiz del repo, resolviendo el enlace simbolico: a este script se le puede
# llamar por ~/.config/hypr/... o por ~/.local/bin/..., y realpath() lleva
# hasta el fichero de verdad dentro del repo, se haya clonado donde se haya
# clonado. Antes ponia "~/dotfiles/...", que obligaba a clonar justo ahi.
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
WALLDIR = os.path.join(RAIZ, "hypr/wallpapers")
CURRENT = os.path.join(WALLDIR, "current")
LANZADOR = os.path.join(RAIZ, "hypr/scripts/wallpaper.sh")

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
# Carpeta del repo para dejar videos propios. Es la unica ruta fija que queda, y
# esta dentro del propio repo, asi que vale igual en cualquier equipo.
CARPETA_REPO = os.path.join(WALLDIR, "propios")

# Un fondo puede ser un video o una imagen fija. Las dos las pinta el mismo
# mpvpaper: mpv es un reproductor, pero muestra imagenes igual de bien, y con
# `--image-display-duration=inf` se queda quieta en pantalla para siempre
# (comprobado; ver wallpaper.sh).
#
# Importa poder usar imagenes porque casi todas las colecciones de fondos que
# circulan —wallhaven.cc y los repos de wallpapers de GitHub— son imagenes. Sin
# esto, la mitad de lo que existe quedaba fuera.
EXTENSIONES_VIDEO = (".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v")
EXTENSIONES_IMAGEN = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".avif", ".jxl")
EXTENSIONES = EXTENSIONES_VIDEO + EXTENSIONES_IMAGEN


def es_imagen(ruta):
    """True si este fondo es una imagen fija y no un video."""
    return str(ruta).lower().endswith(EXTENSIONES_IMAGEN)

# Las carpetas que anade el usuario se guardan AQUI y no en el repo: son de esta
# maquina y solo de esta (la regla de oro del CLAUDE.md). Un clon en otro equipo
# empieza sin ninguna, que es lo correcto.
CONFIG = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.join(CASA, ".config")),
                      "celiuzpaper")
CARPETAS_JSON = os.path.join(CONFIG, "carpetas.json")

# Hasta donde se baja al recorrer una carpeta. Con 3 entra lo que la gente tiene
# de verdad (Vídeos/fondos/anime/x.mp4) sin que un ~/Vídeos enorme cueste
# segundos ni se cuele un arbol entero de otra cosa.
PROFUNDIDAD = 3

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
        "imagen": False,
    }


def carpeta_xdg(clave, respaldos=()):
    """Una carpeta del usuario (VIDEOS, PICTURES...), en el idioma que sea.

    Aqui la de videos es ~/Vídeos con tilde y la de imagenes ~/Imágenes; en un
    sistema en ingles son ~/Videos y ~/Pictures, y en aleman ~/Bilder. Adivinar
    el nombre seria empezar mal, asi que se pregunta al estandar XDG, que es
    justamente quien sabe la respuesta:

      1. $XDG_<CLAVE>_DIR, si el entorno ya la trae puesta.
      2. ~/.config/user-dirs.dirs, que es el fichero donde vive de verdad. Se lee
         a mano en vez de llamar a `xdg-user-dir` para no depender de que
         xdg-user-dirs este instalado.
      3. El binario `xdg-user-dir`, por si el fichero no estuviera.
      4. Unos cuantos nombres conocidos, como ultimo recurso.

    Devuelve None si no existe ninguna: la app se apana sin ella.
    """
    ruta = os.environ.get(f"XDG_{clave}_DIR")
    if not ruta:
        try:
            with open(os.path.join(CASA, ".config/user-dirs.dirs"),
                      encoding="utf-8", errors="replace") as fh:
                encontrado = re.search(rf'^\s*XDG_{clave}_DIR\s*=\s*"?([^"\n]+)"?',
                                       fh.read(), re.M)
            if encontrado:
                # El fichero guarda las rutas como "$HOME/Vídeos".
                ruta = encontrado.group(1).replace("$HOME", CASA).replace("${HOME}", CASA)
        except OSError:
            ruta = None
    if not ruta:
        try:
            ruta = subprocess.run(["xdg-user-dir", clave], capture_output=True,
                                  text=True, timeout=5).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            ruta = None
    if not ruta or os.path.realpath(ruta) == os.path.realpath(CASA):
        # Sin configurar, xdg-user-dir contesta el propio $HOME. Recorrer la casa
        # entera buscando fondos no es lo que nadie espera.
        for nombre in respaldos:
            candidata = os.path.join(CASA, nombre)
            if os.path.isdir(candidata):
                return candidata
        return None
    return ruta if os.path.isdir(ruta) else None


def carpeta_videos():
    """Tu carpeta de videos, la llame el sistema como la llame."""
    return carpeta_xdg("VIDEOS", ("Vídeos", "Videos", "Vidéos", "Filme"))


def carpeta_imagenes():
    """Tu carpeta de imagenes, la llame el sistema como la llame.

    Es un modulo aparte del de videos y no una mezcla: ahi es donde la gente
    guarda de verdad los fondos que se descarga, que casi siempre son imagenes.
    """
    return carpeta_xdg("PICTURES", ("Imágenes", "Pictures", "Images", "Bilder",
                                    "Imagens", "Immagini"))


# --- Carpetas que anade el usuario --------------------------------------------

def carpetas_extra():
    """Las carpetas anadidas a mano, en orden y sin las que ya no existan."""
    try:
        with open(CARPETAS_JSON, encoding="utf-8") as fh:
            guardadas = json.load(fh).get("carpetas") or []
    except (OSError, ValueError, AttributeError):
        return []
    salida = []
    for ruta in guardadas:
        if isinstance(ruta, str) and os.path.isdir(ruta) and ruta not in salida:
            salida.append(ruta)
    return salida


def _guardar_carpetas(lista):
    os.makedirs(CONFIG, exist_ok=True)
    tmp = CARPETAS_JSON + ".nuevo"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"carpetas": lista}, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, CARPETAS_JSON)


def anadir_carpeta(ruta):
    """Anade una carpeta a las fuentes. Devuelve False si no aporta nada nuevo.

    Se rechaza la que ya estaria cubierta por otra fuente (la de videos, el
    Workshop, o una anadida antes): tenerla dos veces solo duplicaria tarjetas.
    """
    ruta = os.path.realpath(os.path.expanduser(ruta))
    if not os.path.isdir(ruta):
        raise NotADirectoryError(ruta)
    ya = [os.path.realpath(f["ruta"]) for f in fuentes() if f.get("ruta")]
    if ruta in ya:
        return False
    lista = carpetas_extra()
    lista.append(ruta)
    _guardar_carpetas(lista)
    return True


def quitar_carpeta(ruta):
    """Quita una carpeta anadida. No borra ni un archivo: solo deja de mirarla."""
    ruta = os.path.realpath(os.path.expanduser(ruta))
    lista = [c for c in carpetas_extra() if os.path.realpath(c) != ruta]
    _guardar_carpetas(lista)
    return True


# --- Las fuentes, que son los modulos del selector ----------------------------

def fuentes():
    """Los sitios de donde salen fondos, en el orden en que se ensenan.

    Solo aparece la fuente que EXISTE en esta maquina: sin Steam no hay modulo de
    Wallpaper Engine, y sin carpeta de videos tampoco el suyo. Asi el selector se
    adapta solo al equipo en el que se abra, sin configurar nada.
    """
    lista = []
    workshop = _bibliotecas_steam()
    if workshop:
        lista.append({"id": "workshop", "nombre": "Wallpaper Engine",
                      "tipo": "workshop", "ruta": None, "rutas": workshop,
                      "quitable": False})
    # Las dos carpetas del sistema, cada una su modulo. Se ensena el nombre que
    # tengan de verdad ("Vídeos", "Imágenes", "Pictures"...), asi que el usuario
    # ve el suyo y no una traduccion nuestra.
    #
    # Si un equipo tuviera las dos apuntando al mismo sitio, se queda una sola:
    # dos pestanas identicas solo hacen dudar.
    vistas = set()
    for clave, carpeta in (("videos", carpeta_videos()),
                           ("imagenes", carpeta_imagenes())):
        if not carpeta:
            continue
        real = os.path.realpath(carpeta)
        if real in vistas:
            continue
        vistas.add(real)
        lista.append({"id": clave, "nombre": os.path.basename(carpeta.rstrip("/")),
                      "tipo": "carpeta", "ruta": carpeta, "rutas": [carpeta],
                      "quitable": False})
    if os.path.isdir(CARPETA_REPO):
        lista.append({"id": "repo", "nombre": "Del repo", "tipo": "carpeta",
                      "ruta": CARPETA_REPO, "rutas": [CARPETA_REPO],
                      "quitable": False})
    for ruta in carpetas_extra():
        lista.append({"id": "extra:" + ruta,
                      "nombre": os.path.basename(ruta.rstrip("/")) or ruta,
                      "tipo": "carpeta", "ruta": ruta, "rutas": [ruta],
                      "quitable": True})
    return lista


def _videos_de(carpeta):
    """Los videos de una carpeta y sus subcarpetas, hasta PROFUNDIDAD niveles."""
    encontrados = []
    base = carpeta.rstrip("/")
    for raiz, subs, ficheros in os.walk(base):
        nivel = raiz[len(base):].count(os.sep)
        # Las ocultas fuera: ahi viven caches y basura de otras apps, no fondos.
        subs[:] = [] if nivel >= PROFUNDIDAD - 1 else [s for s in subs
                                                      if not s.startswith(".")]
        for nombre in sorted(ficheros):
            if nombre.lower().endswith(EXTENSIONES) and not nombre.startswith("."):
                encontrados.append(os.path.join(raiz, nombre))
    return encontrados


def _leer_propio(ruta, fuente="repo"):
    return {
        # El id lleva la ruta entera para que dos videos con el mismo nombre en
        # carpetas distintas no compartan miniatura en cache.
        "id": "propio:" + ruta.replace("/", "_"),
        "titulo": os.path.splitext(os.path.basename(ruta))[0],
        "tipo": "video",
        "video": ruta,
        "vista": "",
        "etiquetas": ["propio"],
        "usable": True,
        "fuente": fuente,
        # Un fondo fijo se trata distinto en tres sitios: la miniatura (no hay
        # fotograma que buscar), la ficha (no tiene duracion) y las banderas con
        # las que se lanza mpvpaper.
        "imagen": es_imagen(ruta),
    }


def escanear():
    """Todos los fondos encontrados, usables o no, ordenados por titulo.

    Cada fondo sale etiquetado con la fuente de la que viene (`fuente`), que es
    lo que despues reparte las tarjetas por modulos en el selector.
    """
    fondos = []
    for fuente in fuentes():
        if fuente["tipo"] == "workshop":
            for dir_workshop in fuente["rutas"]:
                try:
                    nombres = sorted(os.listdir(dir_workshop))
                except OSError:
                    continue
                for nombre in nombres:
                    carpeta = os.path.join(dir_workshop, nombre)
                    if os.path.isdir(carpeta):
                        item = _leer_item(carpeta)
                        if item:
                            item["fuente"] = fuente["id"]
                            fondos.append(item)
        else:
            for ruta in _videos_de(fuente["ruta"]):
                fondos.append(_leer_propio(ruta, fuente["id"]))
    fondos.sort(key=lambda f: f["titulo"].lower())
    return fondos


def por_fuente(fondos=None):
    """Los fondos USABLES repartidos por fuente: {id_fuente: [fondos]}.

    Se reparte despues de quitar duplicados, no antes, para que la cuenta que
    ensena cada modulo sea la de las tarjetas que se van a ver de verdad.
    """
    reparto = {}
    for fondo in usables(fondos):
        reparto.setdefault(fondo.get("fuente", "?"), []).append(fondo)
    return reparto


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

    # En un video se busca un fotograma con contenido (a los 3 s, o al 10% si
    # dura menos); una imagen NO tiene donde buscar, y pedirle un `-ss 3` a
    # ffmpeg sobre un jpg lo deja sin nada que escribir y la miniatura sale vacia.
    orden = ["ffmpeg", "-nostdin", "-v", "error"]
    if not fondo.get("imagen"):
        info = datos(fondo)
        duracion = info.get("duracion") or 0
        momento = 3.0 if duracion > 6 else max(0.0, duracion * 0.1)
        orden += ["-ss", f"{momento:.2f}"]
    orden += ["-i", fondo["video"], "-frames:v", "1",
              "-vf", f"scale={ANCHO_MINIATURA}:-2", "-y", destino]
    try:
        os.makedirs(CACHE_MINIATURAS, exist_ok=True)
        subprocess.run(orden, capture_output=True, timeout=30)
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
    if fondo.get("imagen"):
        # ffprobe le da 0,04 s a un jpg, que no significa nada. En su sitio se
        # dice lo unico util: que es fija.
        trozos.append("imagen fija")
    elif info.get("duracion"):
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
