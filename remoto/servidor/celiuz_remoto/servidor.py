"""
remoto/servidor/celiuz_remoto/servidor.py — el servicio: tres canales, un estado.

    red      IP de Tailscale :47110   /v0/...    lo que usa la app
    USB      127.0.0.1:47111          /usb/...   emparejar y renovar; SOLO abierto
                                                 mientras la app de la PC lo pide
    control  socket Unix (0600)       /control/  la CLI y la app de la PC

El contrato de cada ruta esta en remoto/PROTOCOLO.md; el porque, en DISEÑO.md.

Todo lo que pueda tardar (scrypt, ~50 ms) va a un hilo: el bucle de aiohttp
tambien sirve los /v0/vivo de cada segundo, y no puede pararse a hacer cuentas.
"""

import asyncio
import contextlib
import hmac
import json
import os
import secrets
import shutil
import subprocess
import sys

from aiohttp import WSCloseCode, web

from . import VERSION_PROTOCOLO, ajustes, dispositivos as dsp, pase, red, registro, rutas
from .sesion import FIRMA_MALA, Rechazo, Sesiones, firma_buena, texto_firmado

VENTANA_DURA = 120          # segundos que se queda abierto el canal USB
VIVO_CADA = 1.0
CIERRE_SIN_SESION = 4401    # codigo de cierre del WebSocket al caducar la sesion


def avisar_en_la_pc(titulo, cuerpo):
    """Una notificacion en el escritorio. De mejor esfuerzo: sin notify-send o
    sin sesion grafica, se queda en el registro y en el diario del servicio."""
    print(f"celiuz-remoto: {titulo}: {cuerpo}", file=sys.stderr)
    if shutil.which("notify-send"):
        with contextlib.suppress(OSError):
            subprocess.Popen(["notify-send", "-a", "Celiuz Remoto", "-u", "critical",
                              titulo, cuerpo],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)


def _rechazo(http, error, mensaje, **extra):
    return Rechazo(http, error, mensaje, **extra)


async def _cuerpo(peticion, *campos):
    try:
        datos = await peticion.json()
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        raise _rechazo(400, "peticion", "El cuerpo no es JSON.") from None
    if not isinstance(datos, dict):
        raise _rechazo(400, "peticion", "El cuerpo tiene que ser un objeto JSON.")
    for c in campos:
        if not isinstance(datos.get(c), str) or not datos[c]:
            raise _rechazo(400, "peticion", f"Falta «{c}».")
    return datos


@web.middleware
async def _errores(request, handler):
    # Los nombres no son libres: aiohttp 3.14 llama al middleware por nombre
    # (handler=...), y con otro nombre cada peticion era un 500.
    try:
        return await handler(request)
    except Rechazo as r:
        return web.json_response(r.cuerpo(), status=r.http)
    except web.HTTPNotFound:
        return web.json_response({"error": "no_existe", "mensaje": "No existe."}, status=404)
    except web.HTTPMethodNotAllowed:
        return web.json_response({"error": "no_existe", "mensaje": "Método no admitido."},
                                 status=405)


class Ventana:
    """El canal USB abierto: para que, con que codigo, y como acabo."""

    def __init__(self, modo, contrasena=None, permisos=(), nombre=None, serie=None):
        self.modo = modo
        self.serie = serie                    # la del cable (adb), si la dice la PC
        self.codigo = secrets.token_urlsafe(24)
        self.contrasena = contrasena          # ya en hash
        self.permisos = list(permisos)
        self.nombre = nombre
        self.estado = "abierta"
        self.dispositivo = None
        self.fin = asyncio.Event()

    def codigo_bueno(self, codigo):
        return isinstance(codigo, str) and hmac.compare_digest(codigo, self.codigo)


class Servicio:
    def __init__(self, ip, almacen=None, muestreador=None, valores=None, avisar=avisar_en_la_pc):
        self.ip = ip
        self.valores = valores or ajustes.leer()
        self.almacen = almacen or dsp.Almacen()
        self.avisar = avisar
        self.sesiones = Sesiones(self.almacen, avisar=avisar, caducidad=self.valores["sesion"])
        self.muestreador = muestreador
        self._muestra = (0.0, None)
        self.ventana = None
        self._usb = None            # el runner del canal USB mientras esta abierto
        self._temporizador = None
        self._runners = []
        self._tareas = set()

    # --- utilidades ---

    def equipo(self):
        return red.nombre_equipo()

    def _telefono(self, peticion, permiso=None, tocar=True):
        cabecera = peticion.headers.get("Authorization", "")
        token = cabecera[7:] if cabecera.startswith("Bearer ") else None
        disp = self.sesiones.quien(token, tocar=tocar) if token else None
        if disp is None:
            raise _rechazo(401, "sin_sesion", "La sesión caducó: vuelve a entrar.")
        if permiso and permiso not in disp.get("permisos", []):
            raise _rechazo(403, "sin_permiso",
                           "Este celular no tiene permiso para esto. Actívalo desde la PC.")
        return token, disp

    def _muestrear(self):
        t = asyncio.get_running_loop().time()
        hora, muestra = self._muestra
        # Con dos celulares mirando a la vez se mide una vez por segundo, no dos.
        if muestra is None or t - hora >= VIVO_CADA * 0.9:
            muestra = self.muestreador.tomar()
            self._muestra = (t, muestra)
        return muestra

    # --- red: /v0 ---

    async def v0_reto(self, peticion):
        ident = peticion.query.get("dispositivo", "")
        return web.json_response({"reto": self.sesiones.reto(ident), "caduca": 30})

    async def v0_entrar(self, peticion):
        d = await _cuerpo(peticion, "dispositivo", "reto", "firma")
        contrasena = d.get("contrasena")
        loop = asyncio.get_running_loop()
        try:
            token, disp = await loop.run_in_executor(
                None, self.sesiones.entrar, d["dispositivo"], d["reto"], d["firma"], contrasena)
        except Rechazo as r:
            if r.error in ("contrasena", "bloqueado"):
                registro.apuntar("entrar_mal", d["dispositivo"], motivo=r.error)
            raise
        self.almacen.cambiar(disp["id"], ultima_sesion=pase.iso(pase.ahora()))
        registro.apuntar("entrar", disp["id"])
        return web.json_response({
            "token": token, "caduca_en": self.valores["sesion"],
            "pase_hasta": disp["pase_hasta"] if pase.vigente(disp) else None,
            "permisos": disp["permisos"], "equipo": self.equipo(),
        })

    async def v0_salir(self, peticion):
        token, disp = self._telefono(peticion, tocar=False)
        self.sesiones.salir(token)
        registro.apuntar("salir", disp["id"])
        return web.json_response({"ok": True})

    async def v0_equipo(self, peticion):
        self._telefono(peticion, "estado")
        return web.json_response(dict(self.muestreador.equipo(), protocolo=VERSION_PROTOCOLO))

    async def v0_vivo(self, peticion):
        token, disp = self._telefono(peticion, "estado")
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(peticion)
        lector = asyncio.ensure_future(ws.receive())   # para enterarse de que cierra
        try:
            while not ws.closed:
                disp = self.sesiones.quien(token)
                if disp is None or "estado" not in disp.get("permisos", []):
                    await ws.close(code=CIERRE_SIN_SESION, message=b"sin_sesion")
                    break
                muestra = dict(self._muestrear(),
                               pase_hasta=disp["pase_hasta"] if pase.vigente(disp) else None,
                               vigilancia="desarmada")
                await ws.send_json(muestra)
                hecho, _ = await asyncio.wait({lector}, timeout=VIVO_CADA)
                if hecho:
                    break          # el celular cerro (o mando algo: no se espera nada)
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            lector.cancel()
            if not ws.closed:
                await ws.close(code=WSCloseCode.GOING_AWAY)
        return ws

    # --- USB: /usb ---

    def _ventana_abierta(self):
        if self.ventana is None or self.ventana.estado != "abierta":
            raise web.HTTPNotFound()
        return self.ventana

    async def usb_hola(self, peticion):
        v = self._ventana_abierta()
        return web.json_response({"modo": v.modo, "equipo": self.equipo()})

    async def usb_emparejar(self, peticion):
        v = self._ventana_abierta()
        if v.modo != "emparejar":
            raise web.HTTPNotFound()
        d = await _cuerpo(peticion, "codigo", "publica", "firma")
        if not v.codigo_bueno(d["codigo"]) or not dsp.publica_valida(d["publica"]) or \
                not firma_buena(d["publica"], texto_firmado("emparejar", d["codigo"]), d["firma"]):
            raise Rechazo(*FIRMA_MALA)
        disp = self.almacen.crear(v.nombre or d.get("nombre"), d["publica"], v.contrasena,
                                  v.permisos, pase.iso(pase.ahora()), serie=v.serie)
        # Emparejar DA el pase: se cumple lo que pide (cable, y la contraseña
        # recien creada delante de la PC). Es el «Emparejar y dar pase de 24 h»
        # de la maqueta.
        hasta = pase.renovado()
        disp = self.almacen.cambiar(disp["id"], pase_hasta=hasta)
        registro.apuntar("emparejado", disp["id"], nombre=disp["nombre"],
                         permisos=disp["permisos"], pase_hasta=hasta)
        self._cerrar_ventana("hecho", disp["id"])
        return web.json_response({
            "dispositivo": disp["id"], "equipo": self.equipo(),
            "direccion": f"{self.ip}:{self.valores['puerto_red']}",
            "permisos": disp["permisos"], "pase_hasta": hasta,
        })

    async def usb_renovar(self, peticion):
        v = self._ventana_abierta()
        if v.modo != "renovar":
            raise web.HTTPNotFound()
        d = await _cuerpo(peticion, "codigo", "dispositivo", "firma")
        disp = self.almacen.uno(d["dispositivo"])
        if not v.codigo_bueno(d["codigo"]) or disp is None or \
                not firma_buena(disp["publica"], texto_firmado("renovar", d["codigo"]), d["firma"]):
            raise Rechazo(*FIRMA_MALA)
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, self.sesiones.comprobar_contrasena,
                                       disp, d.get("contrasena"))
        except Rechazo as r:
            registro.apuntar("renovar_mal", disp["id"], motivo=r.error)
            raise
        hasta = pase.renovado()
        self.almacen.cambiar(disp["id"], pase_hasta=hasta)
        registro.apuntar("pase_renovado", disp["id"], hasta=hasta)
        self._cerrar_ventana("hecho", disp["id"])
        return web.json_response({"pase_hasta": hasta})

    # --- la ventana USB ---

    def _app_usb(self):
        app = web.Application(middlewares=[_errores], client_max_size=64 * 1024)
        app.add_routes([web.get("/usb/hola", self.usb_hola),
                        web.post("/usb/emparejar", self.usb_emparejar),
                        web.post("/usb/renovar", self.usb_renovar)])
        return app

    async def abrir_ventana(self, modo, contrasena=None, permisos=(), nombre=None, serie=None):
        if self.ventana is not None and self.ventana.estado == "abierta":
            raise _rechazo(409, "ocupado", "Ya hay una ventana USB abierta.")
        hash_c = None
        if modo == "emparejar":
            malos = [p for p in permisos if p not in dsp.PERMISOS]
            if malos:
                raise _rechazo(400, "peticion", f"Permisos desconocidos: {', '.join(malos)}")
            loop = asyncio.get_running_loop()
            try:
                hash_c = await loop.run_in_executor(None, dsp.hash_contrasena, contrasena)
            except dsp.ErrorDispositivo as e:
                raise _rechazo(400, "peticion", str(e)) from None
        elif modo != "renovar":
            raise _rechazo(400, "peticion", "El modo es «emparejar» o «renovar».")
        runner = web.AppRunner(self._app_usb(), access_log=None)
        await runner.setup()
        try:
            await web.TCPSite(runner, "127.0.0.1", self.valores["puerto_usb"]).start()
        except OSError as e:
            await runner.cleanup()
            raise _rechazo(409, "ocupado",
                           f"No puedo abrir el puerto USB {self.valores['puerto_usb']}: {e}") from None
        self._usb = runner
        self.ventana = Ventana(modo, hash_c, permisos or dsp.PERMISOS_DE_FABRICA, nombre, serie)
        self._temporizador = asyncio.get_running_loop().call_later(
            VENTANA_DURA, self._cerrar_ventana, "caducada")
        registro.apuntar("ventana_usb", modo=modo)
        return self.ventana

    def _cerrar_ventana(self, estado, dispositivo=None):
        v = self.ventana
        if v is None or v.estado != "abierta":
            return
        v.estado, v.dispositivo = estado, dispositivo
        if self._temporizador:
            self._temporizador.cancel()
            self._temporizador = None
        runner, self._usb = self._usb, None
        v.fin.set()
        if estado != "hecho":
            registro.apuntar("ventana_usb_cerrada", estado=estado)
        if runner is not None:
            # Despues de contestar: cerrar el canal dentro de su propia peticion
            # cortaria la respuesta a medias.
            asyncio.get_running_loop().call_later(0.2, self._soltar_usb, runner)

    def _soltar_usb(self, runner):
        # La tarea se guarda: asyncio solo apunta las tareas con una referencia
        # DEBIL, y una sin dueño puede desaparecer antes de acabar. Si no se
        # guardaba, el puerto USB se quedaba escuchando (contestando 404).
        tarea = asyncio.ensure_future(runner.cleanup())
        self._tareas.add(tarea)
        tarea.add_done_callback(self._tareas.discard)

    # --- control: /control ---

    async def control_abrir(self, peticion):
        d = await _cuerpo(peticion, "modo")
        permisos = d.get("permisos") or []
        if not isinstance(permisos, list):
            raise _rechazo(400, "peticion", "«permisos» es una lista.")
        serie = d.get("serie") if isinstance(d.get("serie"), str) else None
        v = await self.abrir_ventana(d["modo"], d.get("contrasena"), permisos, d.get("nombre"), serie)
        return web.json_response({"codigo": v.codigo, "caduca": VENTANA_DURA,
                                  "puerto": self.valores["puerto_usb"]})

    async def control_esperar(self, peticion):
        v = self.ventana
        if v is None:
            raise web.HTTPNotFound()
        try:
            espera = min(float(peticion.query.get("espera", "0")), VENTANA_DURA + 5)
        except ValueError:
            espera = 0
        if espera > 0 and v.estado == "abierta":
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(v.fin.wait(), espera)
        return web.json_response({"estado": v.estado, "modo": v.modo,
                                  "dispositivo": v.dispositivo})

    async def control_cerrar(self, peticion):
        self._cerrar_ventana("cancelada")
        return web.json_response({"ok": True})

    async def control_estado(self, peticion):
        v = self.ventana
        return web.json_response({
            "red": f"{self.ip}:{self.valores['puerto_red']}",
            "sesiones": self.sesiones.cuantas(),
            "ventana": v.modo if v is not None and v.estado == "abierta" else None,
            "equipo": self.equipo(),
        })

    # --- arrancar ---

    def app_red(self):
        app = web.Application(middlewares=[_errores], client_max_size=64 * 1024)
        app.add_routes([
            web.get("/v0/reto", self.v0_reto),
            web.post("/v0/sesion", self.v0_entrar),
            web.delete("/v0/sesion", self.v0_salir),
            web.get("/v0/equipo", self.v0_equipo),
            web.get("/v0/vivo", self.v0_vivo),
        ])
        return app

    def app_control(self):
        app = web.Application(middlewares=[_errores], client_max_size=64 * 1024)
        app.add_routes([
            web.post("/control/ventana", self.control_abrir),
            web.get("/control/ventana", self.control_esperar),
            web.delete("/control/ventana", self.control_cerrar),
            web.get("/control/estado", self.control_estado),
        ])
        return app

    async def arrancar(self):
        if not red.direccion_segura(self.ip):
            raise red.SinRed(f"no escucho en {self.ip}: no es de Tailscale ni local")
        r = web.AppRunner(self.app_red(), access_log=None)
        await r.setup()
        await web.TCPSite(r, self.ip, self.valores["puerto_red"]).start()
        self._runners.append(r)

        sock = rutas.control()
        os.makedirs(os.path.dirname(sock), mode=0o700, exist_ok=True)
        with contextlib.suppress(FileNotFoundError):
            os.unlink(sock)
        c = web.AppRunner(self.app_control(), access_log=None)
        await c.setup()
        # umask antes de crear el socket: un chmod despues dejaria un hueco en
        # el que otro usuario podria conectarse.
        viejo = os.umask(0o177)
        try:
            await web.UnixSite(c, sock).start()
        finally:
            os.umask(viejo)
        self._runners.append(c)

    async def parar(self):
        self._cerrar_ventana("cancelada")
        if self._usb is not None:
            await self._usb.cleanup()
        for r in reversed(self._runners):
            await r.cleanup()
        self._runners.clear()
        with contextlib.suppress(FileNotFoundError):
            os.unlink(rutas.control())
        if self.muestreador is not None:
            self.muestreador.cerrar()


async def servir(ip, muestreador):
    """Hasta SIGTERM/SIGINT. Devuelve el codigo de salida."""
    import signal
    s = Servicio(ip, muestreador=muestreador)
    await s.arrancar()
    print(f"celiuz-remoto: escuchando en {ip}:{s.valores['puerto_red']} "
          f"(control en {rutas.control()})", file=sys.stderr, flush=True)
    registro.apuntar("servicio_arranca", direccion=f"{ip}:{s.valores['puerto_red']}")
    parar = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, parar.set)
    await parar.wait()
    await s.parar()
    registro.apuntar("servicio_para")
    return 0
