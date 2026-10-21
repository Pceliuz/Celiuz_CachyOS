"""
remoto/servidor/celiuz_remoto/conversion.py — un vídeo que el celular no puede
reproducir, convertido en la PC antes de bajarlo.

POR QUE EXISTE (el usuario, 2026-10-21, en su HONOR): los vídeos bajados se
guardaban bien y salían en la galería, pero los fondos de moewalls no se
reproducían. Medido con ffprobe: 1080p 30 se veía; 1440p 24 a 12 Mb/s, a
medias (el reproductor que abrió la app dijo que no, la galería sí); 4K 60
H.264 a 40 Mb/s y 4K 30 HEVC, en negro. No era la descarga (el md5 en el
celular era el de la PC): es lo que el decodificador del celular aguanta. En
el Redmi de pruebas, `media_codecs.xml` dice `performance-point-3840x2160 = 30`
para H.264: 4K 60 no lo decodifica nadie ahí.

EL REPARTO: quien sabe lo que aguanta el celular es EL CELULAR (le pregunta a
su MediaCodecList, módulo celiuz-nativo), y quien sabe cómo es el vídeo es la
PC (ffprobe, `info()`). Así que la app pide la ficha, decide, y si hace falta
pide aquí una conversión al tamaño y la velocidad que su decodificador sí
aguanta (`lado` corto y `fps`). La PC no adivina nada del celular.

CÓMO SE CONVIERTE: H.264 High en MP4 con AAC estéreo, que lo reproduce
cualquier Android. Con libx264 y no con la gráfica, MEDIDO en la PC: un 4K 60
de 21 s tarda 7,7 s con libx264 veryfast y 6,8 s con NVENC — lo lento es
DECODIFICAR el 4K, no codificar el 1080p —, y libx264 está en cualquier ffmpeg
(la laptop no tiene NVIDIA). CRF 20 para no perder calidad a la vista (lo
pidió el usuario: «no bajando tanto la calidad»), con un techo de bitrate por
tamaño para que el decodificador no se ahogue con un pico.

Una a la vez (ffmpeg a 4K se come la CPU entera), con `nice`, y en
~/.cache/celiuz/remoto/convertidos con la misma clave que las miniaturas
(ruta + tamaño + fecha + lado + fps): pedir dos veces lo mismo no convierte
dos veces. Si el celular deja de preguntar por una conversión (cerró la app,
perdió la red), a los ABANDONO segundos se para: no tiene sentido tener la
CPU al 100 % para nadie. Lo convertido se borra a los CADUCA segundos.
"""

import asyncio
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import time

from . import rutas

ABANDONO = 90                  # s sin que el celular pregunte: se para
CADUCA = 2 * 24 * 3600         # lo convertido se borra a los dos días
LADOS = (480, 720, 1080, 1440, 2160)
TECHO_MBPS = {480: 3, 720: 8, 1080: 16, 1440: 28, 2160: 50}

# Lo que ffprobe llama de una forma y Android (MediaFormat) de otra.
MIME_VIDEO = {
    "h264": "video/avc", "hevc": "video/hevc", "vp8": "video/x-vnd.on2.vp8",
    "vp9": "video/x-vnd.on2.vp9", "av1": "video/av01", "mpeg4": "video/mp4v-es",
    "h263": "video/3gpp", "mpeg2video": "video/mpeg2",
}
MIME_AUDIO = {
    "aac": "audio/mp4a-latm", "mp3": "audio/mpeg", "opus": "audio/opus",
    "vorbis": "audio/vorbis", "flac": "audio/flac", "ac3": "audio/ac3",
    "eac3": "audio/eac3", "dts": "audio/vnd.dts", "truehd": "audio/true-hd",
    "amr_nb": "audio/3gpp", "amr_wb": "audio/amr-wb",
}


class NoEsVideo(Exception):
    """No hay ffprobe, o el fichero no tiene pista de vídeo (404)."""


def _fps(texto):
    try:
        a, b = str(texto).split("/")
        return round(int(a) / int(b), 3) if int(b) else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


def info(absoluta):
    """La ficha del vídeo para que el celular decida:
    {contenedor, duracion, video: {codec, mime, perfil, ancho, alto, fps, rotacion},
     audio: {codec, mime} | None}. Ancho y alto son los del fotograma tal cual
    va codificado (lo que ve el decodificador), y `rotacion` lo que el
    reproductor lo gira al enseñarlo."""
    if not shutil.which("ffprobe"):
        raise NoEsVideo("sin ffprobe")
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-of", "json", "-show_entries",
             "format=format_name,duration:stream=codec_type,codec_name,profile,width,height,"
             "avg_frame_rate,r_frame_rate:stream_side_data=rotation", absoluta],
            capture_output=True, timeout=15, check=False, stdin=subprocess.DEVNULL)
        datos = json.loads(r.stdout or b"{}")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        raise NoEsVideo("ffprobe no pudo") from None
    flujos = datos.get("streams") or []
    v = next((s for s in flujos if s.get("codec_type") == "video"
              and s.get("width") and s.get("codec_name") not in ("mjpeg", "png")), None)
    if v is None:
        raise NoEsVideo("sin pista de vídeo")
    a = next((s for s in flujos if s.get("codec_type") == "audio"), None)
    rotacion = 0
    for lado in v.get("side_data_list") or []:
        if "rotation" in lado:
            with contextlib.suppress(TypeError, ValueError):
                rotacion = int(lado["rotation"]) % 360
    fps = _fps(v.get("avg_frame_rate")) or _fps(v.get("r_frame_rate"))
    try:
        duracion = float((datos.get("format") or {}).get("duration") or 0)
    except ValueError:
        duracion = 0.0
    return {
        "contenedor": (datos.get("format") or {}).get("format_name", ""),
        "duracion": round(duracion, 3),
        "video": {"codec": v.get("codec_name", ""), "mime": MIME_VIDEO.get(v.get("codec_name"), ""),
                  "perfil": v.get("profile", ""), "ancho": int(v["width"]), "alto": int(v["height"]),
                  "fps": fps, "rotacion": rotacion},
        "audio": None if a is None else {"codec": a.get("codec_name", ""),
                                         "mime": MIME_AUDIO.get(a.get("codec_name"), "")},
    }


def orden_ffmpeg(origen, destino, lado, fps, fps_original):
    """La orden entera. El lado CORTO baja a `lado` (nunca sube) y se respeta
    la proporción; ffmpeg ya gira lo que venga girado, así que lo que sale va
    derecho y sin rotación (el celular lo comprobó contra eso)."""
    filtros = [f"scale='if(gte(iw,ih),-2,min({lado},iw))':'if(gte(iw,ih),min({lado},ih),-2)'"
               ":flags=lanczos"]
    if fps and (not fps_original or fps < fps_original - 0.5):
        filtros.append(f"fps={fps:g}")
    techo = TECHO_MBPS[lado]
    return ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", origen,
            "-map", "0:v:0", "-map", "0:a:0?", "-sn", "-dn",
            "-vf", ",".join(filtros),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-profile:v", "high",
            "-pix_fmt", "yuv420p", "-maxrate", f"{techo}M", "-bufsize", f"{techo * 2}M",
            "-c:a", "aac", "-b:a", "192k", "-ac", "2",
            "-movflags", "+faststart", "-progress", "pipe:1", "-nostats", destino]


def carpeta():
    return os.path.join(os.path.dirname(rutas.miniaturas()), "convertidos")


def nombre_convertido(nombre, lado, fps):
    """«fondo.mkv» -> «fondo (1080p 60).mp4»: que en la galería se sepa que no
    es el original."""
    base = os.path.splitext(nombre)[0]
    return f"{base} ({lado}p {fps:g}).mp4"


class Trabajo:
    def __init__(self, ident, relativa, lado, fps, destino, duracion):
        self.id = ident
        self.relativa = relativa
        self.lado, self.fps = lado, fps
        self.destino = destino
        self.duracion = duracion
        self.estado = "listo" if os.path.exists(destino) else "en_cola"
        self.progreso = 1.0 if self.estado == "listo" else 0.0
        self.mensaje = ""
        self.visto = time.monotonic()
        self.proceso = None
        self.tarea = None

    def ficha(self):
        d = {"id": self.id, "estado": self.estado, "progreso": round(self.progreso, 3),
             "nombre": nombre_convertido(os.path.basename(self.relativa), self.lado, self.fps)}
        if self.estado == "listo":
            with contextlib.suppress(OSError):
                d["tamano"] = os.path.getsize(self.destino)
        if self.mensaje:
            d["mensaje"] = self.mensaje
        return d


class Conversiones:
    def __init__(self, abandono=ABANDONO):
        self.abandono = abandono
        self.trabajos = {}
        self._una = asyncio.Semaphore(1)

    @staticmethod
    def clave(relativa, st, lado, fps):
        return hashlib.sha256(
            f"{relativa}\0{st.st_size}\0{st.st_mtime_ns}\0{lado}\0{fps:g}".encode()).hexdigest()[:32]

    def pedir(self, absoluta, relativa, st, lado, fps, ficha):
        """El trabajo de esa conversión: el que ya hay, uno listo de la caché o
        uno nuevo en marcha."""
        ident = self.clave(relativa, st, lado, fps)
        t = self.trabajos.get(ident)
        if t is not None and t.estado not in ("error", "cancelado"):
            t.visto = time.monotonic()
            return t
        os.makedirs(carpeta(), mode=0o700, exist_ok=True)
        _purgar()
        t = Trabajo(ident, relativa, lado, fps, os.path.join(carpeta(), ident + ".mp4"),
                    ficha.get("duracion") or 0)
        self.trabajos[ident] = t
        if t.estado == "listo":
            with contextlib.suppress(OSError):
                os.utime(t.destino)      # CADUCA cuenta desde que se usó
        else:
            t.tarea = asyncio.ensure_future(self._convertir(t, absoluta, ficha["video"]["fps"]))
        return t

    def ver(self, ident):
        t = self.trabajos.get(ident)
        if t is not None:
            t.visto = time.monotonic()
        return t

    def cancelar(self, ident):
        t = self.trabajos.get(ident)
        if t is None:
            return False
        if t.estado in ("en_cola", "convirtiendo"):
            t.estado, t.mensaje = "cancelado", "Cancelada."
            if t.proceso is not None and t.proceso.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    t.proceso.kill()
            elif t.tarea is not None:
                t.tarea.cancel()
        return True

    async def parar(self):
        for ident in list(self.trabajos):
            self.cancelar(ident)
        for t in list(self.trabajos.values()):
            if t.tarea is not None:
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await t.tarea

    async def _convertir(self, t, origen, fps_original):
        async with self._una:
            if t.estado == "cancelado":
                return
            if time.monotonic() - t.visto > self.abandono:
                t.estado, t.mensaje = "cancelado", "Nadie la esperaba."
                return
            t.estado = "convirtiendo"
            # La extension real AL FINAL: ffmpeg elige el formato por ella.
            tmp = f"{t.destino[:-4]}.{os.getpid()}.nuevo.mp4"
            stderr = b""
            try:
                t.proceso = await asyncio.create_subprocess_exec(
                    *orden_ffmpeg(origen, tmp, t.lado, t.fps, fps_original),
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    preexec_fn=lambda: os.nice(10))
                errores = asyncio.ensure_future(t.proceso.stderr.read())
                while True:
                    try:
                        linea = await asyncio.wait_for(t.proceso.stdout.readline(), 5)
                    except asyncio.TimeoutError:
                        linea = None
                    if linea == b"":
                        break
                    if linea and linea.startswith(b"out_time_us=") and t.duracion:
                        with contextlib.suppress(ValueError):
                            t.progreso = max(0.0, min(0.99, int(linea[12:]) / 1e6 / t.duracion))
                    if time.monotonic() - t.visto > self.abandono:
                        t.estado, t.mensaje = "cancelado", "Nadie la esperaba."
                        t.proceso.kill()
                        break
                codigo = await t.proceso.wait()
                stderr = await errores
            except OSError as e:
                codigo, stderr = -1, str(e).encode()
            if t.estado == "cancelado":
                _borrar(tmp)
                return
            if codigo == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 0:
                os.replace(tmp, t.destino)
                t.estado, t.progreso = "listo", 1.0
                return
            _borrar(tmp)
            ultima = stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or [f"código {codigo}"]
            t.estado, t.mensaje = "error", f"ffmpeg no pudo convertirlo: {ultima[0][:200]}"


def _borrar(ruta):
    with contextlib.suppress(FileNotFoundError):
        os.unlink(ruta)


def _purgar(ahora=None):
    """Lo convertido hace más de CADUCA, y los temporales que dejó un servicio
    que murió a medias."""
    ahora = ahora or time.time()
    with contextlib.suppress(FileNotFoundError):
        for e in os.scandir(carpeta()):
            with contextlib.suppress(OSError):
                viejo = ahora - e.stat().st_mtime > CADUCA
                if viejo or (".nuevo." in e.name and ahora - e.stat().st_mtime > 3600):
                    os.unlink(e.path)
