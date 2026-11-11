#!/usr/bin/env python3
"""
hypr/scripts/modo-estudio.py — entrar y salir del modo estudio.

Uso:
    modo-estudio.py toggle            entra o sale, preguntando antes
    modo-estudio.py on  [--sin-preguntar]
    modo-estudio.py off [--sin-preguntar]
    modo-estudio.py estado [--json]   sale con 0 si esta puesto y 1 si no

LA IDEA
-------
El primo del modo programador (lo pidio el usuario: «voy a estudiar, no a jugar
ni hacer otras cosas»): lo mismo que el programador, y ademas se aparta al
escritorio oculto el OCIO —reproductores de video y musica, chats, redes— en
todas las pantallas, no solo en la de trabajo. Lo que se abre de eso mientras
dura se aparta con un aviso que anima.

Se queda lo de trabajar: el editor, la terminal, el navegador (documentacion),
la pizarra de Celiuz y la propia Celiuz.

Los tres modos no se juntan: con el gaming o el programador puestos, el estudio
no entra (lo dice).

El estado vive en ~/.config/celiuz/modo-estudio.json y es SUYO: no comparte el
del programador (seria mentira a plazos).

LOS GANCHOS (~/.config/celiuz/modo-estudio.d/)
----------------------------------------------
Como los del modo programador: cada ejecutable se corre con `on` al entrar y
`off` al salir. Vacia para quien clona: aqui se enchufa el gancho que abre la
pizarra y arranca la profesora (eso vive en el repo de Celiuz).
"""

import datetime
import glob
import importlib.util
import json
import os
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(AQUI, "lib"))

import canales  # noqa: E402
import hypr  # noqa: E402
import ocio  # noqa: E402
import programador  # noqa: E402

# El primo se carga por ruta: el archivo lleva guion y no se puede importar por
# nombre. Asi se reusa lo que ya hace bien, sin copiarlo.
_spec = importlib.util.spec_from_file_location(
    "modo_programador", os.path.join(AQUI, "modo-programador.py"))
mp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mp)

# Las funciones de escritorio (clientes, mover, num_ws) viven en modo-gaming.py,
# no en el programador. Se cargan por ruta, igual que el primo.
_spec = importlib.util.spec_from_file_location(
    "modo_gaming", os.path.join(AQUI, "modo-gaming.py"))
mg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mg)

GUARDADAS = "special:modo-estudio"

# El tema del estudio: papel y ambar, nada que ver con el violeta del gaming ni
# con el verde de editor del programador. Vive solo aqui.
TEMA_FABRICA = {
    "fondo": "#1a1712",      # papel viejo, calido
    "panel": "#221e17",
    "linea": "#2b261d",
    "borde": "#3a3327",
    "texto": "#e6ddc8",
    "tenue": "#8a8171",
    "comentario": "#6f6858",
    "ambar": "#e0b060",      # el acento: el foco, el borde activo
    "ocre": "#c98f3c",
    "verde": "#a3be8c",
    "rojo": "#cf7a6b",
    "azul": "#8aa9c9",
    "morado": "#b9a0d0",
}


# --- Rutas ----------------------------------------------------------------------
def _config():
    return os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")


def config_usuario():
    return os.path.join(_config(), "celiuz", "modo-estudio.json")


def carpeta_ganchos():
    return os.path.join(_config(), "celiuz", "modo-estudio.d")


# --- Estado ---------------------------------------------------------------------
def leer():
    try:
        with open(config_usuario(), encoding="utf-8") as fh:
            datos = json.load(fh)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def encendido():
    return bool(leer().get("encendido"))


def guardar(datos):
    ruta = config_usuario()
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta + ".nuevo", "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=2)
    os.replace(ruta + ".nuevo", ruta)


# --- Avisos ---------------------------------------------------------------------
def avisar(titulo, texto=""):
    """Un aviso de escritorio. Si no hay con que, no pasa nada."""
    if not shutil.which("notify-send"):
        return
    try:
        subprocess.run(["notify-send", "-a", "Celiuz", titulo, texto],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


# --- Ganchos --------------------------------------------------------------------
def correr_ganchos(fase):
    """Cada ejecutable de modo-estudio.d/ se corre con `on` o `off`.
    Se espera a que terminen (con un tope): el gancho de la pizarra tiene que
    haber arrancado antes de que el comando devuelva el control."""
    carpeta = carpeta_ganchos()
    if not os.path.isdir(carpeta):
        return
    for ruta in sorted(glob.glob(os.path.join(carpeta, "*"))):
        if not os.path.isfile(ruta) or not os.access(ruta, os.X_OK):
            continue
        try:
            pro = subprocess.Popen([ruta, fase], stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL,
                                   start_new_session=True)
        except OSError:
            continue
        try:
            pro.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass


# --- Los otros modos ------------------------------------------------------------
def _otro_modo_puesto():
    """El gaming o el programador, si alguno esta puesto. Los tres no se juntan."""
    if os.path.exists(os.path.join(carpeta_ganchos(), "..", "modo-estudio.json")):
        pass
    try:
        if mp.leer_estado():
            return "programador"
    except Exception:
        pass
    try:
        if _gaming_puesto():
            return "gaming"
    except Exception:
        pass
    return None


def _gaming_puesto():
    sig = canales.firma()
    patrones = ["modo-gaming.*.json"]
    for nombre in patrones:
        for ruta in glob.glob(os.path.join(canales.RUNTIME, nombre)):
            if sig and sig not in ruta:
                continue
            try:
                with open(ruta, encoding="utf-8") as fh:
                    if json.load(fh).get("activo"):
                        return True
            except (OSError, ValueError, AttributeError):
                continue
    return False


# --- El ocio --------------------------------------------------------------------
def es_ocio(ventana):
    """Si la ventana es de ocio: un juego, una tienda, un reproductor, un chat
    o una red. Se le pregunta a ocio por la clase de la ventana."""
    try:
        if mg.es_de_juego(ventana) or mg.es_ventana_de_lanzador(ventana):
            return True
    except Exception:
        pass
    try:
        clase = (ventana.get("class") or ventana.get("initialClass") or "").lower()
        if clase and ocio.es_ocio_id(clase):
            return True
    except Exception:
        pass
    return False


def apartar_ocio():
    """Manda al escritorio oculto TODO lo de ocio que haya abierto, en todas las
    pantallas. Lo de trabajo no se toca. Sin compositor no se hace nada."""
    try:
        ventanas = mg.clientes()
    except Exception:
        return 0
    modo = hypr.modo()
    movidas = 0
    for ventana in ventanas or []:
        if not ventana.get("address") or not es_ocio(ventana):
            continue
        try:
            if mg._en(ventana) == GUARDADAS:
                continue
            mg.mover(modo, ventana["address"], GUARDADAS, False)
            movidas += 1
        except Exception:
            continue
    return movidas


# --- El tema --------------------------------------------------------------------
def tema():
    datos = leer().get("tema") or {}
    colores = dict(TEMA_FABRICA)
    for k, v in datos.items():
        if k in colores and isinstance(v, str) and len(v) == 7 and v.startswith("#"):
            colores[k] = v
    return colores


def poner_tema(colores):
    """El borde activo con el ambar del estudio. Si no hay compositor, nada."""
    try:
        crudo = "%s %s 45deg" % ("ff" + colores["ambar"][1:], "ff" + colores["ocre"][1:])
        mp.poner_gradiente(hypr.modo(), "general:col.active_border", crudo)
        inactivo = "ff" + colores["borde"][1:]
        mp.poner_gradiente(hypr.modo(), "general:col.inactive_border", inactivo + " 0deg")
    except Exception:
        pass


# --- Entrar y salir -------------------------------------------------------------
def entrar(sin_preguntar=False):
    if encendido():
        avisar("El modo estudio ya esta puesto", "A estudiar.")
        return 0
    otro = _otro_modo_puesto()
    if otro:
        avisar("No se juntan", "El modo %s esta puesto. Sal de el primero." % otro)
        print("no entra: el modo %s esta puesto" % otro, file=sys.stderr)
        return 1
    if not sin_preguntar:
        try:
            if not mp.preguntar("Entrar en el modo estudio"):
                return 1
        except Exception:
            return 1
    estado = leer()
    estado.update({
        "encendido": True,
        "activo": True,
        "desde": datetime.datetime.now().isoformat(timespec="seconds"),
        "guardadas": GUARDADAS,
    })
    guardar(estado)
    correr_ganchos("on")
    poner_tema(tema())
    apartar_ocio()
    avisar("Modo estudio", "Fuera el ocio. Animo, a por el ejercicio.")
    return 0


def salir(sin_preguntar=False):
    if not encendido():
        avisar("El modo estudio no esta puesto", "")
        return 0
    if not sin_preguntar:
        try:
            if not mp.preguntar("Salir del modo estudio"):
                return 1
        except Exception:
            return 1
            
    estado = leer()
    estado.update({
        "encendido": False,
        "activo": False,
        "hasta": datetime.datetime.now().isoformat(timespec="seconds"),
    })
    guardar(estado)
    correr_ganchos("off")
    avisar("Modo estudio fuera", "Buen trabajo. Ya puedes con lo demas.")
    return 0


# --- CLI ------------------------------------------------------------------------
def estado_cli(como_json=False):
    puesto = encendido()
    if como_json:
        print(json.dumps({"encendido": puesto, "modo": "estudio" if puesto else None},
                         ensure_ascii=False))
    else:
        print("encendido" if puesto else "apagado")
    return 0 if puesto else 1


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    sin_preguntar = "--sin-preguntar" in argv[1:]
    como_json = "--json" in argv[1:]
    orden = args[0] if args else "estado"
    if orden == "on":
        return entrar(sin_preguntar)
    if orden == "off":
        return salir(sin_preguntar)
    if orden == "toggle":
        return salir(sin_preguntar) if encendido() else entrar(sin_preguntar)
    if orden == "estado":
        return estado_cli(como_json)
    print("uso: modo-estudio.py on|off|toggle|estado [--sin-preguntar] [--json]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
