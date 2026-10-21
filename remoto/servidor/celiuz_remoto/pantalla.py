"""
remoto/servidor/celiuz_remoto/pantalla.py — el escritorio remoto: ver y manejar la pantalla.

Fase 8 (remoto/DISEÑO.md, «Extras»). Es tan poderoso como la terminal (con la
pantalla se hace cualquier cosa), asi que pide lo mismo: permiso propio
(`pantalla`, apagado de fabrica), el pase y la contraseña OTRA VEZ. Y solo hay
uno a la vez.

COMO: wayvnc (el servidor VNC de Wayland, `sudo pacman -S wayvnc`) se arranca
SOLO mientras se mira, dentro de la sesion de Hyprland viva, y escucha en un
SOCKET UNIX de $XDG_RUNTIME_DIR (0700), no en un puerto: nadie mas del equipo
llega a el. El servicio hace de puente entre ese socket y un WebSocket
autenticado (servidor.py, /v0/pantalla/<billete>), y en el celular lo pinta
noVNC dentro de un WebView. Al cerrar, wayvnc se para.

El WebSocket lo abre la pagina del WebView, que no puede poner la cabecera
Authorization: por eso la llave es el BILLETE (un solo uso, 30 s, de ese
telefono), que se dio con sesion + pase + contraseña. Mientras dura, se vuelve
a mirar cada pocos segundos que el telefono sigue teniendo todo.

Con la pantalla bloqueada se ve el bloqueo, y lo que se teclee va al bloqueo:
no se salta nada (hace falta la contraseña de Linux, como delante de la PC).
"""

import asyncio
import contextlib
import json
import os
import shutil
import subprocess
import time

from . import escritorio


def wayvnc():
    """La ruta de wayvnc, o None. CELIUZ_REMOTO_WAYVNC solo para las pruebas."""
    ruta = os.environ.get("CELIUZ_REMOTO_WAYVNC") or shutil.which("wayvnc")
    return ruta if ruta and os.access(ruta, os.X_OK) else None


def _runtime():
    return os.environ.get("XDG_RUNTIME_DIR") or "/run/user/%d" % os.getuid()


def sesion():
    """(firma, socket de wayland, salida enfocada) del Hyprland vivo, o None."""
    firma = escritorio.instancia()
    if not firma:
        return None
    try:
        instancias = json.loads(escritorio._hyprctl(firma, "instances", "-j") or "[]")
    except ValueError:
        instancias = []
    wl = next((i.get("wl_socket") for i in instancias if i.get("instance") == firma), None)
    if not wl:
        return None
    try:
        monitores = json.loads(escritorio._hyprctl(firma, "monitors", "-j") or "[]")
    except ValueError:
        monitores = []
    salida = next((m.get("name") for m in monitores if m.get("focused")), None)
    return firma, wl, salida


class Vnc:
    """Un wayvnc en un socket unix, mientras dure la mirada."""

    def __init__(self, firma, wl, salida=None):
        carpeta = os.path.join(_runtime(), "celiuz-remoto")
        os.makedirs(carpeta, mode=0o700, exist_ok=True)
        self.socket = os.path.join(carpeta, "vnc.sock")
        control = self.control = os.path.join(carpeta, "vnc-control.sock")
        for s in (self.socket, control):
            with contextlib.suppress(FileNotFoundError):
                os.unlink(s)
        orden = [wayvnc(), "--unix-socket", "--render-cursor", f"--socket={control}"]
        if salida:
            orden.append(f"--output={salida}")
        orden.append(self.socket)
        entorno = dict(os.environ, WAYLAND_DISPLAY=wl, HYPRLAND_INSTANCE_SIGNATURE=firma,
                       XDG_RUNTIME_DIR=_runtime())
        self.proceso = subprocess.Popen(orden, env=entorno, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                        start_new_session=True)
        self.desde = time.time()

    async def listo(self, plazo=8.0):
        """True cuando el socket existe; False si wayvnc murio o no llego."""
        limite = time.monotonic() + plazo
        while time.monotonic() < limite:
            if self.proceso.poll() is not None:
                return False
            if os.path.exists(self.socket):
                return True
            await asyncio.sleep(0.1)
        return False

    def error(self):
        if self.proceso.poll() is None:
            return ""
        with contextlib.suppress(Exception):
            return (self.proceso.stderr.read() or b"").decode("utf-8", "replace").strip()[-300:]
        return ""

    async def cerrar(self):
        if self.proceso.poll() is None:
            self.proceso.terminate()
            for _ in range(30):
                if self.proceso.poll() is not None:
                    break
                await asyncio.sleep(0.1)
            if self.proceso.poll() is None:
                self.proceso.kill()
        with contextlib.suppress(Exception):
            self.proceso.wait(timeout=2)
        for s in (self.socket, self.control):
            with contextlib.suppress(FileNotFoundError):
                os.unlink(s)
