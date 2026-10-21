"""
remoto/servidor/celiuz_remoto/energia.py — apagar, reiniciar y suspender, con cuenta atras.

- Nada pasa al instante: primero un aviso en la PC con cuenta atras
  (`cuenta_atras` de remoto.conf, 60 s de fabrica) y un boton «Cancelar». Si
  hay alguien delante, lo cancela (remoto/DISEÑO.md, «Qué pide cada cosa»).
- Se cancela desde la PC (el boton del aviso, la ventana, la CLI) o desde el
  celular (DELETE /v0/energia).
- Al acabar la cuenta, se piden cerrar las ventanas (como SUPER+Q: lo que tenga
  algo sin guardar puede preguntar), se espera un poco, y systemctl.

Apagar va SIN pase a proposito: estando de viaje es justo cuando mas falta
hace, y apagar no le hace daño a nadie (DISEÑO.md).

El aviso de la PC es un `notify-send --wait` con una accion: el proceso vuelve
cuando se pulsa o se cierra, y dice cual. Sin notify-send (o sin sesion
grafica) no hay boton en la PC, y la cuenta sigue igual: cancelar desde el
celular o la CLI sigue valiendo.
"""

import asyncio
import contextlib
import datetime as dt
import shutil
import subprocess
import time

from . import escritorio, pase, registro

ACCIONES = {
    "apagar": ("poweroff", "apagará", "Apagar"),
    "reiniciar": ("reboot", "reiniciará", "Reiniciar"),
    "suspender": ("suspend", "suspenderá", "Suspender"),
}
ESPERA_VENTANAS = 5   # segundos entre pedir cerrar las ventanas y systemctl


class Energia:
    def __init__(self, cuenta_atras=60, avisar=None):
        self.cuenta_atras = cuenta_atras
        self.avisar = avisar or (lambda *a: None)
        self.accion = None
        self.origen = None
        self.hasta = None          # time.monotonic() en que se ejecuta
        self.hasta_iso = None
        self._tarea = None
        self._aviso = None         # el notify-send --wait
        self.ultima = None         # lo ultimo que paso, para enseñarlo

    def estado(self):
        if self.accion is None:
            return None
        return {"accion": self.accion, "quedan": max(0, round(self.hasta - time.monotonic())),
                "hasta": self.hasta_iso, "origen": self.origen}

    def programar(self, accion, disp=None):
        """Empieza la cuenta. `disp`: el telefono que lo pide (None = la PC).
        Si ya habia una, la sustituye (la ultima orden manda)."""
        if accion not in ACCIONES:
            raise ValueError(accion)
        self.cancelar(silencio=True)
        origen = disp["nombre"] if disp else "pc"
        self.accion, self.origen = accion, origen
        self.hasta = time.monotonic() + self.cuenta_atras
        self.hasta_iso = pase.iso(pase.ahora() + dt.timedelta(seconds=self.cuenta_atras))
        self._tarea = asyncio.ensure_future(self._cuenta(accion))
        registro.apuntar("energia_pedida", disp["id"] if disp else None,
                         que=accion, segundos=self.cuenta_atras)
        self._mostrar_aviso(accion, origen)
        return self.estado()

    def cancelar(self, disp=None, silencio=False, desde_pc=False):
        """`disp`: el telefono que cancela; desde_pc: el aviso, la ventana o la CLI."""
        if self.accion is None:
            return False
        accion = self.accion
        if self._tarea is not None:
            self._tarea.cancel()
        self._cerrar_aviso()
        self.accion = self.origen = self.hasta = self.hasta_iso = self._tarea = None
        if not silencio:
            registro.apuntar("energia_cancelada", disp["id"] if disp else None,
                             que=accion, por="pc" if desde_pc or not disp else "celular")
            self.ultima = {"accion": accion, "cancelada": True}
        return True

    async def _cuenta(self, accion):
        try:
            await asyncio.sleep(max(0, self.hasta - time.monotonic()))
        except asyncio.CancelledError:
            return
        self._cerrar_aviso()
        registro.apuntar("energia_ejecutada", que=accion)
        if accion != "suspender":
            # Pedir, no matar: lo que tenga algo sin guardar puede preguntar en
            # la PC. systemctl no espera a nadie de todas formas.
            for v in await asyncio.get_running_loop().run_in_executor(None, escritorio.ventanas):
                await asyncio.get_running_loop().run_in_executor(None, escritorio.cerrar, v["id"])
            await asyncio.sleep(ESPERA_VENTANAS)
        self.accion = self.origen = self.hasta = self.hasta_iso = self._tarea = None
        self.ultima = {"accion": accion, "cancelada": False}
        ejecutar(accion)

    # --- el aviso en la PC ---

    def _mostrar_aviso(self, accion, origen):
        if not shutil.which("notify-send"):
            return
        verbo = ACCIONES[accion][1]
        quien = f" (lo pidió «{origen}»)" if origen and origen != "pc" else ""
        try:
            self._aviso = subprocess.Popen(
                ["notify-send", "--wait", "-p", "-a", "Celiuz Remoto", "-u", "critical",
                 "-t", str(self.cuenta_atras * 1000), "--action=cancelar=Cancelar",
                 f"La PC se {verbo} en {self.cuenta_atras} s",
                 f"A las {self.hasta_iso[11:19]}{quien}. Si estás delante y no quieres, pulsa Cancelar."],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True)
        except OSError:
            self._aviso = None
            return
        asyncio.ensure_future(self._esperar_aviso(self._aviso))

    async def _esperar_aviso(self, proc):
        # Con -p, notify-send dice primero el ID de la notificacion y, al
        # pulsar, la accion. El ID hace falta para CERRARLA: matar el proceso
        # no la quita de la pantalla (medido el 2026-10-20: tras cancelar
        # desde el celular, en la PC seguia «La PC se suspenderá en 300 s»).
        loop = asyncio.get_running_loop()
        primera = await loop.run_in_executor(None, proc.stdout.readline)
        if primera.strip().isdigit():
            proc.id_aviso = int(primera)
        resto = await loop.run_in_executor(None, proc.stdout.read)
        # Solo cuenta si sigue siendo ESTE aviso (uno viejo cerrado no cancela
        # una cuenta nueva).
        if proc is self._aviso and "cancelar" in resto.split():
            self.cancelar(desde_pc=True)
            self.avisar("Celiuz Remoto", "Cancelado desde la PC.")

    def _cerrar_aviso(self):
        proc, self._aviso = self._aviso, None
        if proc is None:
            return
        ident = getattr(proc, "id_aviso", None)
        if ident is not None:
            cerrar_notificacion(ident)
        if proc.poll() is None:
            with contextlib.suppress(OSError):
                proc.terminate()


def cerrar_notificacion(ident):
    """CloseNotification por D-Bus: el estandar, vale con mako y con cualquiera."""
    with contextlib.suppress(OSError, subprocess.TimeoutExpired):
        subprocess.run(["gdbus", "call", "--session", "--dest", "org.freedesktop.Notifications",
                        "--object-path", "/org/freedesktop/Notifications",
                        "--method", "org.freedesktop.Notifications.CloseNotification", str(int(ident))],
                       timeout=5, check=False, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def ejecutar(accion):
    orden = ["systemctl", ACCIONES[accion][0]]
    try:
        subprocess.run(orden, timeout=30, check=False,
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as e:
        registro.apuntar("energia_fallo", que=accion, motivo=str(e))
