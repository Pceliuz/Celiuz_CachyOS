"""
remoto/servidor/celiuz_remoto/rutas.py — donde vive cada cosa de Celiuz Remoto
FUERA del repo.

Nada de esto entra en git: son las claves, los telefonos y el historial de ESTE
equipo (la regla de oro del CLAUDE.md). Se pregunta a las XDG_* en cada llamada,
no al importar, para que una prueba con un $HOME de mentira no escriba en la
casa de verdad.
"""

import os


def _xdg(variable, por_defecto):
    valor = os.environ.get(variable)
    if valor and os.path.isabs(valor):
        return valor
    return os.path.join(os.path.expanduser("~"), por_defecto)


def config():
    """~/.config/celiuz/remoto: ajustes y la clave de firma del APK."""
    return os.path.join(_xdg("XDG_CONFIG_HOME", ".config"), "celiuz", "remoto")


def ajustes():
    """~/.config/celiuz/remoto.conf: puerto, carpetas permitidas, margenes."""
    return os.path.join(_xdg("XDG_CONFIG_HOME", ".config"), "celiuz", "remoto.conf")


def estado():
    """~/.local/state/celiuz/remoto: telefonos, historial y registro."""
    return os.path.join(_xdg("XDG_STATE_HOME", ".local/state"), "celiuz", "remoto")


def dispositivos():
    return os.path.join(estado(), "dispositivos.json")


def historial():
    return os.path.join(estado(), "historial.json")


def registro():
    return os.path.join(estado(), "registro.jsonl")


def firma_apk():
    return os.path.join(config(), "firma.keystore")


def apk():
    """El APK de la app del celular, ya compilado (lo deja ahi la compilacion
    de la fase 3). Fuera del repo: pesa y es de este equipo."""
    return os.path.join(_xdg("XDG_DATA_HOME", ".local/share"), "celiuz", "remoto",
                        "celiuz-remoto.apk")


def control():
    """El socket de control (la CLI y la app de la PC le hablan al servicio).

    En $XDG_RUNTIME_DIR, que es del usuario y no de la sesion: el servicio es
    uno por usuario, no uno por Hyprland, asi que aqui no lleva firma."""
    runtime = os.environ.get("XDG_RUNTIME_DIR") or "/run/user/%d" % os.getuid()
    return os.path.join(runtime, "celiuz-remoto.sock")


def todas():
    return {
        "ajustes": ajustes(),
        "dispositivos": dispositivos(),
        "historial": historial(),
        "registro": registro(),
        "firma_apk": firma_apk(),
        "apk": apk(),
        "control": control(),
    }
