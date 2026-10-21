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

LA TERMINAL NO MUERE CON EL WEBSOCKET (el usuario, 2026-10-21: quería
minimizarla, abrir otra para hacer commits y mirar el estado de la PC sin
perder lo que corría). Antes, cerrar la pantalla de Terminal, cambiar de
pestaña o perder la red un momento cerraba el WebSocket y con él la shell.
Ahora cada terminal es una `Sesion` de la PC, con número, que sigue viva
SUELTA (sin nadie mirando) hasta SUELTA_DURA, y el mismo teléfono la RETOMA
(`/v0/terminales/<id>`) sin la contraseña: ya la dio al abrirla, y retomar
pide igual sesión, permiso y pase. Lo que sale mientras está suelta se guarda
(lo último, MEMORIA bytes) y se repinta al retomarla. Se cierra de verdad al
pedirlo (DELETE), al salir la shell, al pasar SUELTA_DURA sin nadie, o en
cuanto el teléfono pierde el pase, el permiso o lo revocan (eso se mira
también con ella suelta: el vigía es de la PC, no del WebSocket).
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
MAX_ABIERTAS = 5           # entre todos los telefonos
SUELTA_DURA = 3600         # una terminal sin nadie mirando, hasta que se cierra sola
MEMORIA = 512 * 1024       # lo ultimo que salio, para repintarlo al retomarla
TROZO = 64 * 1024          # al repintar se manda en trozos de este tamaño
CIERRE_SALIO = 4000        # la shell termino (exit)
CIERRE_OTRO = 4001         # la retomo otra pantalla (solo se mira desde un sitio)
CIERRE_CERRADA = 4002      # la cerraron (DELETE, o se cerro sola por llevar suelta SUELTA_DURA)
CIERRE_SIN_SESION = 4401   # caduco la sesion de la app: la terminal sigue viva, suelta
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


class Sesion:
    """Una terminal de la PC: su shell, lo ultimo que salio y quien la mira
    (un WebSocket o nadie). La `bomba` lee la shell siempre, se mire o no."""

    def __init__(self, pty, dispositivo, numero, al_salir):
        self.id = secrets.token_urlsafe(12)
        self.pty = pty
        self.dispositivo = dispositivo
        self.numero = numero
        self.memoria = bytearray()
        self.ws = None
        self.suelta_desde = time.monotonic()
        self._envio = asyncio.Lock()     # el repintado y lo nuevo, en orden
        self._al_salir = al_salir
        self.bomba = asyncio.ensure_future(self._bombear())

    async def _bombear(self):
        async for datos in self.pty.leer():
            self.memoria += datos
            if len(self.memoria) > MEMORIA:
                del self.memoria[:len(self.memoria) - MEMORIA]
            ws = self.ws
            if ws is not None:
                # Esperar al envio frena la lectura si el celular no da abasto
                # (y la shell se frena sola al llenarse el PTY). Suelta, no
                # espera a nadie: se guarda lo ultimo y ya.
                async with self._envio:
                    with contextlib.suppress(ConnectionResetError, RuntimeError):
                        if not ws.closed:
                            await ws.send_bytes(datos)
        await self._al_salir(self)

    async def mirar(self, ws, filas, columnas, retomada):
        """Engancha `ws`: le repinta lo guardado y desde ahi le manda lo nuevo.
        Si otra pantalla la estaba mirando, a esa se le cierra (CIERRE_OTRO)."""
        anterior = self.ws
        async with self._envio:
            # La foto y el enganche sin un await entre medias: lo que la bomba
            # lea despues espera al candado y sale DETRAS del repintado.
            foto = bytes(self.memoria)
            self.ws = ws
            self.suelta_desde = None
            for i in range(0, len(foto), TROZO):
                await ws.send_bytes(foto[i:i + TROZO])
        if anterior is not None and anterior is not ws and not anterior.closed:
            with contextlib.suppress(ConnectionResetError, RuntimeError):
                await anterior.close(code=CIERRE_OTRO, message=b"otro")
        if retomada:
            # Un programa a pantalla completa (vim, htop, claude) solo se
            # repinta entero si cambia el tamaño: el kernel no manda SIGWINCH
            # si es el mismo. Se mueve una columna y se devuelve.
            self.pty.tamano(filas, max(10, columnas - 1))
            await asyncio.sleep(0.05)
        self.pty.tamano(filas, columnas)

    def soltar(self, ws):
        """El WebSocket `ws` se fue (minimizar, red, cerrar la app). Si era el
        que miraba, la terminal queda suelta; si ya la miraba otro, nada."""
        if self.ws is ws:
            self.ws = None
            self.suelta_desde = time.monotonic()

    def titulo(self):
        """Lo que corre delante en la terminal (fish, claude, vim...)."""
        try:
            grupo = os.tcgetpgrp(self.pty.maestro)
            with open(f"/proc/{grupo}/comm", encoding="utf-8") as fh:
                return fh.read().strip()
        except (OSError, ValueError):
            return ""

    def ficha(self):
        return {"id": self.id, "numero": self.numero, "desde": round(self.pty.desde),
                "titulo": self.titulo(), "mirando": self.ws is not None}


class Terminales:
    def __init__(self):
        self.billetes = {}
        self.abiertas = {}     # id de la sesion -> Sesion

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

    def nueva(self, pty, dispositivo, al_salir):
        """La Sesion de una shell recien abierta, con el numero libre mas bajo
        de ese telefono (cerrar la 1 y abrir otra da otra vez la 1)."""
        usados = {x.numero for x in self.abiertas.values() if x.dispositivo == dispositivo}
        numero = next(n for n in range(1, MAX_ABIERTAS + 2) if n not in usados)
        sesion = Sesion(pty, dispositivo, numero, al_salir)
        self.abiertas[sesion.id] = sesion
        return sesion

    def de(self, dispositivo):
        return sorted((x for x in self.abiertas.values() if x.dispositivo == dispositivo),
                      key=lambda x: x.numero)

    def una(self, ident, dispositivo):
        x = self.abiertas.get(ident)
        return x if x is not None and x.dispositivo == dispositivo else None

    def sueltas_de_mas(self, ahora=None):
        ahora = time.monotonic() if ahora is None else ahora
        return [x for x in self.abiertas.values()
                if x.ws is None and x.suelta_desde is not None and ahora - x.suelta_desde > SUELTA_DURA]

    async def cerrar(self, sesion, codigo=CIERRE_CERRADA, motivo="cerrada"):
        """Cierra de verdad: la shell (SIGHUP a su grupo) y quien la mire."""
        if self.abiertas.pop(sesion.id, None) is None:
            return False
        ws = sesion.ws
        sesion.ws = None
        if ws is not None and not ws.closed:
            with contextlib.suppress(ConnectionResetError, RuntimeError):
                await ws.close(code=codigo, message=motivo.encode()[:120])
        await sesion.pty.cerrar()
        if sesion.bomba is not asyncio.current_task():   # al salir la shell, es ella quien llama
            sesion.bomba.cancel()
        return True

    async def cerrar_todas(self):
        for sesion in list(self.abiertas.values()):
            await self.cerrar(sesion, motivo="servicio_parado")
