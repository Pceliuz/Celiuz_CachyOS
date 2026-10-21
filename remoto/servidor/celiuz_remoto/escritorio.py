"""
remoto/servidor/celiuz_remoto/escritorio.py — la sesion grafica, vista desde el servicio.

El servicio es de systemd --user y NO vive dentro de la sesion de Hyprland: su
entorno se fija al arrancar, y la HYPRLAND_INSTANCE_SIGNATURE que trae se queda
vieja en cuanto cierras sesion y vuelves a entrar con el servicio corriendo.
Por eso aqui la instancia se busca EN CALIENTE: la que conteste por su socket
(y si hubiera dos vivas, la mas nueva).

Tres cosas:
  - instancia()   que Hyprland esta vivo ahora mismo, o None
  - ventanas()    lo que hay abierto; cerrar() lo cierra PIDIENDOLO (como
                  SUPER+Q), nunca matando: si hay algo sin guardar, pregunta
  - presencia()   ¿hay una persona delante? (ver abajo)

LA PRESENCIA la mide hypridle, que es quien ya sabe si se toca el teclado o el
raton (ext-idle-notify) y respeta los inhibidores: un video reproduciendose NO
cuenta como ausencia (viendo anime no se toca el raton en 20 minutos, y eso es
una persona). hypr/hypridle.conf tiene un listener a los PRESENCIA_S segundos
que llama a `celiuz-remoto presencia ausente` y, al volver, `... presente`.
Tres respuestas, como `hyprctl locked` en lock.sh: «presente», «nadie» y
«no_lo_se». «No lo sé» NO es «nadie»: con hypridle caido, la vigilancia no
apaga una PC que quiza alguien este usando.
"""

import json
import os
import socket
import subprocess
import time

from . import rutas

import hypr  # noqa: E402  (hypr/scripts/lib)

PRESENCIA_S = 300   # el mismo numero que el listener de hypr/hypridle.conf


def _runtime():
    return os.environ.get("XDG_RUNTIME_DIR") or "/run/user/%d" % os.getuid()


def _viva(firma):
    ruta = os.path.join(_runtime(), "hypr", firma, ".socket.sock")
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect(ruta)
        return True
    except OSError:
        return False
    finally:
        s.close()


def instancia():
    """La firma del Hyprland vivo (la mas nueva si hay varias), o None.
    «Existe la carpeta» no basta: Hyprland no siempre la limpia al irse
    (CLAUDE.md, «Un demonio que sobrevive a SU Hyprland»)."""
    carpeta = os.path.join(_runtime(), "hypr")
    try:
        firmas = os.listdir(carpeta)
    except OSError:
        return None
    vivas = [f for f in firmas if _viva(f)]
    if not vivas:
        return None
    # La firma lleva la hora de arranque en su segundo campo.
    def hora(f):
        partes = f.split("_")
        return int(partes[1]) if len(partes) > 1 and partes[1].isdigit() else 0
    return max(vivas, key=hora)


def _hyprctl(firma, *args):
    entorno = dict(os.environ, HYPRLAND_INSTANCE_SIGNATURE=firma)
    try:
        r = subprocess.run(["hyprctl", *args], capture_output=True, text=True,
                           timeout=5, check=False, env=entorno)
        return r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def ventanas():
    """[{id, app, titulo, escritorio, clase, pid}] de la sesion viva; [] sin sesion.
    Se dejan fuera las que no se pueden cerrar con sentido (sin mapear o en el
    escritorio del bloqueo)."""
    firma = instancia()
    if not firma:
        return []
    try:
        clientes = json.loads(_hyprctl(firma, "clients", "-j") or "[]")
    except ValueError:
        return []
    salida = []
    for c in clientes:
        if not c.get("mapped", True) or not c.get("address"):
            continue
        esc = c.get("workspace") or {}
        if esc.get("id", 0) < 0 and not str(esc.get("name", "")).startswith("special"):
            continue
        clase = c.get("class") or c.get("initialClass") or ""
        salida.append({
            "id": c["address"],
            "app": _nombre_app(clase, c.get("initialTitle") or c.get("title") or ""),
            "titulo": c.get("title") or "",
            "escritorio": esc.get("name") or esc.get("id"),
            "clase": clase,
            "pid": c.get("pid"),
        })
    salida.sort(key=lambda v: (str(v["escritorio"]), v["app"].lower()))
    return salida


def _nombre_app(clase, titulo):
    """«brave-browser» -> «Brave», «org.kde.dolphin» -> «Dolphin». Sin
    adivinar de mas: si no se reconoce, la clase tal cual."""
    if not clase:
        return titulo or "?"
    nombre = clase.split(".")[-1].replace("-browser", "").replace("_", " ").replace("-", " ")
    return nombre[:1].upper() + nombre[1:] if nombre.islower() else nombre


def cerrar(direccion):
    """Pide cerrar UNA ventana (como SUPER+Q). False si no existe o no hay sesion."""
    firma = instancia()
    if not firma or not any(v["id"] == direccion for v in ventanas()):
        return False
    modo = hypr.modo_por_respuesta(_hyprctl(firma, "eval", "return 1"))
    if modo == hypr.LUA:
        _hyprctl(firma, "dispatch", 'hl.dsp.window.close({ window = "address:%s" })' % direccion)
    elif modo == hypr.CONF:
        _hyprctl(firma, "dispatch", "closewindow", "address:%s" % direccion)
    else:
        return False
    return True


# --- presencia ------------------------------------------------------------------

def marcar_presencia(estado, ahora=None):
    """Lo llama hypridle (via `celiuz-remoto presencia ausente|presente`)."""
    ruta = rutas.presencia()
    os.makedirs(os.path.dirname(ruta), mode=0o700, exist_ok=True)
    datos = {"estado": estado, "desde": ahora or time.time(),
             "firma": os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or instancia()}
    tmp = ruta + ".nuevo"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(datos, fh)
    os.replace(tmp, ruta)


def _hypridle_vivo():
    try:
        r = subprocess.run(["systemctl", "--user", "is-active", "--quiet", "hypridle.service"],
                           timeout=5, check=False)
        if r.returncode == 0:
            return True
        r = subprocess.run(["pgrep", "-u", str(os.getuid()), "-x", "hypridle"],
                           capture_output=True, timeout=5, check=False)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def presencia():
    """«presente», «nadie» o «no_lo_se», con el porque: (estado, motivo)."""
    firma = instancia()
    if not firma:
        return "nadie", "no hay ninguna sesión gráfica abierta"
    if not _hypridle_vivo():
        return "no_lo_se", "hypridle no está corriendo: no hay quien mida la actividad"
    try:
        with open(rutas.presencia(), encoding="utf-8") as fh:
            datos = json.load(fh)
    except (OSError, ValueError):
        datos = {}
    if datos.get("firma") != firma:
        # Nada apuntado en ESTA sesion: hypridle aun no ha visto 5 minutos
        # quietos desde que se entro. Eso es alguien delante.
        return "presente", "actividad desde que se abrió la sesión"
    if datos.get("estado") == "ausente":
        return "nadie", "sin teclado ni ratón desde hace más de %d min, y sin vídeo" % (PRESENCIA_S // 60)
    return "presente", "teclado, ratón o un vídeo en los últimos %d min" % (PRESENCIA_S // 60)
