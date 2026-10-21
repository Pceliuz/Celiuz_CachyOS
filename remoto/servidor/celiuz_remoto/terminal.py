"""
remoto/servidor/celiuz_remoto/terminal.py — la terminal remota: tu shell en un PTY, por WebSocket.

Fase 7 (remoto/DISEÑO.md, «Terminal con sudo»). Es lo mas poderoso del remoto,
asi que es lo que mas pide, y servidor.py lo comprueba todo antes de llegar aqui:

  - el permiso `terminal` de ESE telefono (viene apagado: se da en la PC);
  - el pase de 24 h;
  - la contraseña de la app OTRA VEZ, aunque ya haya sesion (cuenta como fallo,
    igual que al entrar: al 5.o el telefono se bloquea).

Con eso se da un BILLETE de un solo uso que vale 30 s, y con el billete se abre
el WebSocket. Se separa en dos porque el WebSocket no lleva cuerpo, y porque
asi la contraseña viaja en un POST normal y no en una URL.

Mientras la terminal esta abierta se vuelve a mirar cada pocos segundos que el
telefono SIGUE teniendo todo (revocado, pase caducado, permiso quitado desde la
PC): si no, se cierra en el acto. Y la PC lo cuenta: un aviso al abrirla y una
linea en el registro al abrir y al cerrar (cuanto duro). Lo que se teclea NO se
apunta en ningun sitio: ahi pasa la contraseña de sudo.

La shell es la del usuario (/etc/passwd), como shell de entrada (`-l`), en su
carpeta personal, con TERM=xterm-256color (lo que pinta xterm.js en la app).
Al cerrar se le manda SIGHUP a todo su grupo, como cuando cierras una terminal
de verdad.
"""

import asyncio
import contextlib
import fcntl
import os
import pwd
import secrets
import signal
import struct
import termios
import time

BILLETE_DURA = 30          # segundos para abrir el WebSocket tras dar la contraseña
MAX_ABIERTAS = 3           # entre todos los telefonos
CIERRE_SALIO = 4000        # la shell termino (exit)
CIERRE_SIN_PERMISO = 4403  # revocado, pase vencido o permiso quitado mientras estaba abierta


def shell_del_usuario():
    """$SHELL (systemd se la pone al servicio desde /etc/passwd) y, si no, la de
    /etc/passwd. Por el entorno primero para que una prueba pueda dar otra y no
    arranque la shell de verdad, con la config de verdad, de quien la corre."""
    s = os.environ.get("SHELL", "")
    if not (s and os.access(s, os.X_OK)):
        try:
            s = pwd.getpwuid(os.getuid()).pw_shell
        except KeyError:
            s = ""
    return s if s and os.access(s, os.X_OK) else "/bin/sh"


def casa():
    return os.path.expanduser("~")


def entorno():
    """El del servicio (el del systemd del usuario), con lo que espera una
    terminal. Nada de la sesion grafica: la terminal no depende de que haya una."""
    cuenta = pwd.getpwuid(os.getuid())
    e = {k: v for k, v in os.environ.items()
         if k in ("PATH", "LANG", "LC_ALL", "LC_MESSAGES", "LANGUAGE", "XDG_RUNTIME_DIR",
                  "DBUS_SESSION_BUS_ADDRESS", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
                  "XDG_STATE_HOME", "XDG_CACHE_HOME", "TZ")}
    e.update({"HOME": casa(), "USER": cuenta.pw_name, "LOGNAME": cuenta.pw_name,
              "SHELL": shell_del_usuario(), "TERM": "xterm-256color", "COLORTERM": "truecolor",
              "PWD": casa(), "CELIUZ_REMOTO": "1"})
    e.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
    e.setdefault("LANG", "C.UTF-8")
    return e


def poner_tamano(fd, filas, columnas):
    filas = max(2, min(500, int(filas)))
    columnas = max(10, min(500, int(columnas)))
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", filas, columnas, 0, 0))


class Billete:
    def __init__(self, disp):
        self.id = secrets.token_urlsafe(18)
        self.dispositivo = disp["id"]
        self.hasta = time.monotonic() + BILLETE_DURA


class Pty:
    """Una shell en un PTY. `leer()` es un async generator de bytes."""

    def __init__(self, filas=24, columnas=80, orden=None):
        import subprocess
        self.maestro, esclavo = os.openpty()
        poner_tamano(esclavo, filas, columnas)
        os.set_blocking(self.maestro, False)
        orden = orden or [shell_del_usuario(), "-l"]

        def controlar():
            # start_new_session hace setsid antes de esto: el PTY pasa a ser la
            # terminal de control y la shell tiene control de trabajos (Ctrl+C,
            # Ctrl+Z) como en una terminal de verdad.
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        self.proceso = subprocess.Popen(
            orden, stdin=esclavo, stdout=esclavo, stderr=esclavo, cwd=casa(),
            env=entorno(), start_new_session=True, preexec_fn=controlar, close_fds=True)
        os.close(esclavo)
        self.desde = time.time()
        self._cola = asyncio.Queue(maxsize=64)
        self._fin = False
        asyncio.get_running_loop().add_reader(self.maestro, self._hay_datos)

    def _hay_datos(self):
        try:
            datos = os.read(self.maestro, 65536)
        except BlockingIOError:
            return
        except OSError:
            datos = b""    # EIO: la shell cerro el PTY (salio)
        if not datos:
            self._dejar_de_leer()
            self._cola.put_nowait(None)
            return
        try:
            self._cola.put_nowait(datos)
        except asyncio.QueueFull:
            # El celular no da abasto (un `cat` de un fichero enorme): se deja de
            # leer hasta que se vacie, y la shell se frena sola al llenarse el PTY.
            self._dejar_de_leer()
            asyncio.ensure_future(self._reanudar(datos))

    async def _reanudar(self, datos):
        await self._cola.put(datos)
        if not self._fin:
            with contextlib.suppress(ValueError, OSError):
                asyncio.get_running_loop().add_reader(self.maestro, self._hay_datos)

    def _dejar_de_leer(self):
        with contextlib.suppress(ValueError, OSError):
            asyncio.get_running_loop().remove_reader(self.maestro)

    async def leer(self):
        while True:
            datos = await self._cola.get()
            if datos is None:
                return
            yield datos

    def escribir(self, datos):
        vista = memoryview(datos)
        limite = time.monotonic() + 5
        while vista and time.monotonic() < limite:
            try:
                n = os.write(self.maestro, vista)
                vista = vista[n:]
            except BlockingIOError:
                time.sleep(0.01)
            except OSError:
                return

    def tamano(self, filas, columnas):
        with contextlib.suppress(OSError, ValueError, TypeError):
            poner_tamano(self.maestro, filas, columnas)
            # La shell se entera por SIGWINCH, que manda el kernel solo.

    def viva(self):
        return self.proceso.poll() is None

    async def cerrar(self):
        """SIGHUP a todo el grupo, como al cerrar una terminal; SIGKILL si en 2 s
        sigue ahi (un programa que ignora HUP no deja la shell colgada)."""
        self._fin = True
        self._dejar_de_leer()
        if self.viva():
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(self.proceso.pid, signal.SIGHUP)
            for _ in range(20):
                if not self.viva():
                    break
                await asyncio.sleep(0.1)
            if self.viva():
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.killpg(self.proceso.pid, signal.SIGKILL)
        with contextlib.suppress(OSError):
            os.close(self.maestro)
        with contextlib.suppress(Exception):
            self.proceso.wait(timeout=2)


class Terminales:
    def __init__(self):
        self.billetes = {}
        self.abiertas = {}     # id del billete -> (Pty, dispositivo)

    def dar_billete(self, disp):
        ahora = time.monotonic()
        self.billetes = {k: b for k, b in self.billetes.items() if b.hasta > ahora}
        if len(self.abiertas) >= MAX_ABIERTAS:
            return None
        b = Billete(disp)
        self.billetes[b.id] = b
        return b

    def gastar_billete(self, ident, disp):
        """True si el billete existe, no caduco y es de ESTE telefono. Se gasta."""
        b = self.billetes.pop(ident, None)
        return b is not None and b.hasta > time.monotonic() and b.dispositivo == disp["id"]

    def cuantas(self):
        return len(self.abiertas)

    async def cerrar_todas(self):
        for pty, _ in list(self.abiertas.values()):
            await pty.cerrar()
        self.abiertas.clear()
