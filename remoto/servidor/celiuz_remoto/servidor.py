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
import time
import urllib.parse

from aiohttp import WSCloseCode, web

from . import VERSION_PROTOCOLO, ajustes, archivos, dispositivos as dsp, escritorio, historial, inicio, pase, red, registro, rutas
from .energia import ACCIONES, Energia
from .vigilancia import CADA as VIGILANCIA_CADA, Vigilancia
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
        self.energia = Energia(self.valores["cuenta_atras"], avisar)
        self.vigilancia = Vigilancia(self.almacen, self._apagar_desde_hilo, avisar)
        self._bucle = None
        self.muestreador = muestreador
        self._muestra = (0.0, None)
        self.ventana = None
        self._usb = None            # el runner del canal USB mientras esta abierto
        self._temporizador = None
        self._runners = []
        self._tareas = set()
        self._pendiente = None     # (runner, plazo) del canal USB que se esta soltando
        self._miniaturas = asyncio.Semaphore(2)   # ffmpeg de dos en dos, no de cien en cien

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
        self._apuntar_ip(peticion, disp)
        return token, disp

    def _apuntar_ip(self, peticion, disp):
        """La IP de Tailscale del telefono: es como la vigilancia sabe cual de
        los aparatos de `tailscale status` es (vigilancia.py)."""
        ip = peticion.remote
        if ip and ip != disp.get("ip_tailscale"):
            self.almacen.cambiar(disp["id"], ip_tailscale=ip)
            disp["ip_tailscale"] = ip

    def _pase(self, disp):
        if not pase.vigente(disp):
            raise _rechazo(423, "pase_vencido", pase.mensaje_vencido(disp))

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
        self._apuntar_ip(peticion, disp)
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
        return web.json_response(dict(self.muestreador.equipo(), protocolo=VERSION_PROTOCOLO,
                                      cuenta_atras=self.valores["cuenta_atras"]))

    async def v0_vivo(self, peticion):
        token, disp = self._telefono(peticion, "estado")
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(peticion)
        lector = asyncio.ensure_future(ws.receive())   # para enterarse de que cierra
        loop = asyncio.get_running_loop()
        try:
            while not ws.closed:
                disp = self.sesiones.quien(token)
                if disp is None or "estado" not in disp.get("permisos", []):
                    await ws.close(code=CIERRE_SIN_SESION, message=b"sin_sesion")
                    break
                muestra = dict(self._muestrear(),
                               pase_hasta=disp["pase_hasta"] if pase.vigente(disp) else None,
                               vigilancia=self.vigilancia.estado,
                               energia=self.energia.estado(),
                               escritorio=await loop.run_in_executor(None, inicio.estado))
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

    # --- energia, ventanas y latido ---

    async def v0_energia(self, peticion):
        _, disp = self._telefono(peticion, "energia")
        if peticion.method == "GET":
            return web.json_response({"energia": self.energia.estado()})
        if peticion.method == "DELETE":
            return web.json_response({"cancelada": self.energia.cancelar(disp)})
        d = await _cuerpo(peticion, "accion")
        if d["accion"] not in ACCIONES:
            raise _rechazo(400, "peticion", "La acción es apagar, reiniciar o suspender.")
        if d.get("confirmado") is not True:
            raise _rechazo(409, "confirmar", "Falta confirmarlo.")
        estado = self.energia.programar(d["accion"], disp)
        return web.json_response({"cuenta_atras": estado["quedan"], "energia": estado})

    async def v0_ventanas(self, peticion):
        self._telefono(peticion, "ventanas")
        lista = await asyncio.get_running_loop().run_in_executor(None, escritorio.ventanas)
        return web.json_response({"ventanas": [{k: v[k] for k in ("id", "app", "titulo", "escritorio")}
                                               for v in lista],
                                  "sesion": lista != [] or escritorio.instancia() is not None})

    async def v0_cerrar_ventana(self, peticion):
        _, disp = self._telefono(peticion, "ventanas")
        self._pase(disp)
        d = await _cuerpo(peticion)
        if d.get("confirmado") is not True:
            raise _rechazo(409, "confirmar", "Falta confirmarlo.")
        ident = peticion.match_info["id"]
        ok = await asyncio.get_running_loop().run_in_executor(None, escritorio.cerrar, ident)
        if not ok:
            raise _rechazo(404, "no_existe", "Esa ventana ya no está abierta.")
        registro.apuntar("ventana_cerrada", disp["id"], ventana=ident)
        return web.json_response({"pedido": True})

    # --- tras un reinicio: la pantalla de inicio (fase 5) ---

    async def v0_escritorio(self, peticion):
        self._telefono(peticion, "estado")
        return web.json_response(await asyncio.get_running_loop().run_in_executor(
            None, inicio.estado))

    async def v0_entrar_escritorio(self, peticion):
        """Con la PC en SDDM: autologin de un solo uso y la sesion arranca
        bloqueada. Permiso de energia (es encender la sesion, como encender la
        PC) y con PASE: es lo que mas se parece a sentarse delante."""
        _, disp = self._telefono(peticion, "energia")
        self._pase(disp)
        d = await _cuerpo(peticion)
        if d.get("confirmado") is not True:
            raise _rechazo(409, "confirmar", "Falta confirmarlo.")
        ok, mensaje = await asyncio.get_running_loop().run_in_executor(None, inicio.entrar)
        if not ok:
            registro.apuntar("entrar_escritorio_mal", disp["id"], motivo=mensaje)
            raise _rechazo(409, "estado", f"No puedo entrar: {mensaje}.")
        registro.apuntar("entrar_escritorio", disp["id"])
        return web.json_response({"pedido": True, "mensaje": mensaje})

    # --- archivos (fase 6): permiso `archivos` y pase en todo, solo lectura ---

    def _de_archivos(self, peticion):
        _, disp = self._telefono(peticion, "archivos")
        self._pase(disp)
        return disp

    @staticmethod
    async def _en_hilo(funcion, *args):
        """Lo de disco va a un hilo, y sus dos fallos se convierten en respuesta."""
        try:
            return await asyncio.get_running_loop().run_in_executor(None, funcion, *args)
        except archivos.Fuera as e:
            raise _rechazo(403, "fuera", f"Eso no se enseña desde el celular: {e}.") from None
        except archivos.NoExiste:
            raise _rechazo(404, "no_existe", "No está en la PC.") from None

    async def v0_archivos(self, peticion):
        self._de_archivos(peticion)
        ocultos = peticion.query.get("ocultos") == "1"
        d = await self._en_hilo(archivos.listar, peticion.query.get("ruta", ""), ocultos)
        fijados = await self._en_hilo(historial.rutas_favoritas)
        for e in d["entradas"]:
            e["favorito"] = (os.path.join(d["ruta"], e["nombre"]) if d["ruta"] else e["nombre"]) in fijados
        return web.json_response(d)

    async def v0_buscar(self, peticion):
        self._de_archivos(peticion)
        q = peticion.query.get("q", "")
        if len(q.strip()) < 2:
            raise _rechazo(400, "peticion", "Escribe al menos dos letras.")
        return web.json_response(await self._en_hilo(
            archivos.buscar, peticion.query.get("ruta", ""), q, peticion.query.get("ocultos") == "1"))

    async def v0_descargar(self, peticion):
        disp = self._de_archivos(peticion)
        absoluta, relativa, st = await self._en_hilo(archivos.archivo, peticion.query.get("ruta", ""))
        # Solo cuenta como «bajado» la peticion que empieza por el principio: un
        # Range que reanuda a medias es la misma descarga, no otra.
        try:
            desde = peticion.http_range.start
        except ValueError:
            desde = None
        if not desde:
            await self._en_hilo(historial.apuntar_descarga, relativa, st, disp["id"])
            registro.apuntar("descarga", disp["id"], ruta=relativa, tamano=st.st_size)
        nombre = urllib.parse.quote(os.path.basename(relativa))
        return web.FileResponse(absoluta, chunk_size=256 * 1024, headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{nombre}",
            "Cache-Control": "no-store"})

    async def v0_miniatura(self, peticion):
        self._de_archivos(peticion)
        try:
            lado = int(peticion.query.get("lado", "256"))
        except ValueError:
            raise _rechazo(400, "peticion", "«lado» es un número.") from None
        async with self._miniaturas:
            destino = await self._en_hilo(archivos.miniatura, peticion.query.get("ruta", ""), lado)
        return web.FileResponse(destino, headers={"Cache-Control": "private, max-age=86400"})

    async def v0_recientes(self, peticion):
        self._de_archivos(peticion)
        if peticion.method == "DELETE":
            ruta = peticion.query.get("ruta")
            return web.json_response({"olvidados": await self._en_hilo(historial.olvidar, ruta)})
        return web.json_response({"recientes": await self._en_hilo(historial.recientes)})

    async def v0_favoritos(self, peticion):
        disp = self._de_archivos(peticion)
        if peticion.method == "PUT":
            d = await _cuerpo(peticion)
            if not isinstance(d.get("ruta"), str):
                raise _rechazo(400, "peticion", "Falta «ruta».")
            relativa = await self._en_hilo(historial.fijar, d["ruta"])
            registro.apuntar("favorito", disp["id"], ruta=relativa)
        elif peticion.method == "DELETE":
            await self._en_hilo(historial.soltar, peticion.query.get("ruta", ""))
        return web.json_response({"favoritos": await self._en_hilo(historial.favoritos)})

    async def v0_latido(self, peticion):
        """«Me estan apagando» (y de paso, una señal). Sin sesion: lo manda un
        servicio de fondo de la app. La firma es sobre el minuto, que la PC
        acepta si es el suyo o el anterior (PROTOCOLO.md, «Latido»)."""
        d = await _cuerpo(peticion, "dispositivo", "minuto", "firma")
        disp = self.almacen.uno(d["dispositivo"])
        apagando = bool(d.get("apagando"))
        minuto_pc = int(time.time() // 60)
        try:
            minuto = int(d["minuto"])
        except ValueError:
            minuto = -1
        texto = f"{d['dispositivo']}:{minuto}:{1 if apagando else 0}"
        if disp is None or minuto not in (minuto_pc, minuto_pc - 1) or \
                not firma_buena(disp["publica"], texto_firmado("latido", texto), d["firma"]):
            raise Rechazo(*FIRMA_MALA)
        cambios = {"ultima_senal": time.time()}
        if apagando:
            cambios["apagando_en"] = time.time()
            registro.apuntar("latido_apagando", disp["id"])
        self.almacen.cambiar(disp["id"], **cambios)
        self._apuntar_ip(peticion, disp)
        return web.json_response({"siguiente_en": 300})

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
        disp = disp_creado = self.almacen.crear(v.nombre or d.get("nombre"), d["publica"], v.contrasena,
                                                v.permisos, pase.iso(pase.ahora()), serie=v.serie)
        # Emparejar DA el pase: se cumple lo que pide (cable, y la contraseña
        # recien creada delante de la PC). Es el «Emparejar y dar pase de 24 h»
        # de la maqueta.
        hasta = pase.renovado()
        disp = self.almacen.cambiar(disp["id"], pase_hasta=hasta)
        registro.apuntar("emparejado", disp["id"], nombre=disp["nombre"],
                         permisos=disp["permisos"], pase_hasta=hasta)
        for viejo in disp_creado.get("sustituye", []):
            self.sesiones.echar(viejo)
            registro.apuntar("sustituido", viejo, por=disp["id"])
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
        if self._pendiente is not None:
            # La ventana anterior acaba de cerrarse y su puerto aun no se ha
            # soltado: emparejar otra vez enseguida daba «address already in
            # use» (lo destapo la prueba de emparejar dos veces el mismo celular).
            viejo, plazo = self._pendiente
            plazo.cancel()
            self._pendiente = None
            await viejo.cleanup()
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
            # cortaria la respuesta a medias. Se apunta, por si se abre otra
            # ventana antes de esos 0,2 s (abrir_ventana lo suelta ya).
            self._pendiente = (runner, asyncio.get_running_loop().call_later(
                0.2, self._soltar_usb, runner))

    def _soltar_usb(self, runner):
        self._pendiente = None
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

    async def control_energia(self, peticion):
        """Cancelar desde la PC (la ventana, la CLI)."""
        return web.json_response({"cancelada": self.energia.cancelar(desde_pc=True),
                                  "energia": self.energia.estado()})

    async def control_vigilancia(self, peticion):
        loop = asyncio.get_running_loop()
        if peticion.method == "POST":
            d = await _cuerpo(peticion)
            await loop.run_in_executor(None, self.vigilancia.armar, bool(d.get("armada")))
        return web.json_response(await loop.run_in_executor(None, self.vigilancia.resumen))

    async def control_estado(self, peticion):
        v = self.ventana
        return web.json_response({
            "red": f"{self.ip}:{self.valores['puerto_red']}",
            "sesiones": self.sesiones.cuantas(),
            "ventana": v.modo if v is not None and v.estado == "abierta" else None,
            "equipo": self.equipo(),
            "energia": self.energia.estado(),
            "vigilancia": self.vigilancia.estado,
            "escritorio": inicio.estado(),
            "linger": inicio.linger(),
            "sistema": inicio.sistema_instalado(),
        })

    def _apagar_desde_hilo(self):
        self._bucle.call_soon_threadsafe(self.energia.programar, "apagar", None)

    async def _vigilar(self):
        loop = self._bucle = asyncio.get_running_loop()
        while True:
            try:
                await loop.run_in_executor(None, self.vigilancia.vuelta)
            except Exception as e:  # noqa: BLE001  una vuelta rota no para la vigilancia
                print(f"celiuz-remoto: la vigilancia falló una vuelta: {e!r}", file=sys.stderr)
            await asyncio.sleep(VIGILANCIA_CADA)

    # --- arrancar ---

    def app_red(self):
        app = web.Application(middlewares=[_errores], client_max_size=64 * 1024)
        app.add_routes([
            web.get("/v0/reto", self.v0_reto),
            web.post("/v0/sesion", self.v0_entrar),
            web.delete("/v0/sesion", self.v0_salir),
            web.get("/v0/equipo", self.v0_equipo),
            web.get("/v0/vivo", self.v0_vivo),
            web.get("/v0/energia", self.v0_energia),
            web.post("/v0/energia", self.v0_energia),
            web.delete("/v0/energia", self.v0_energia),
            web.get("/v0/ventanas", self.v0_ventanas),
            web.post("/v0/ventanas/{id}/cerrar", self.v0_cerrar_ventana),
            web.post("/v0/latido", self.v0_latido),
            web.get("/v0/escritorio", self.v0_escritorio),
            web.post("/v0/escritorio/entrar", self.v0_entrar_escritorio),
            web.get("/v0/archivos", self.v0_archivos),
            web.get("/v0/archivos/buscar", self.v0_buscar),
            web.get("/v0/archivos/descargar", self.v0_descargar),
            web.get("/v0/archivos/miniatura", self.v0_miniatura),
            web.get("/v0/recientes", self.v0_recientes),
            web.delete("/v0/recientes", self.v0_recientes),
            web.get("/v0/favoritos", self.v0_favoritos),
            web.put("/v0/favoritos", self.v0_favoritos),
            web.delete("/v0/favoritos", self.v0_favoritos),
        ])
        return app

    def app_control(self):
        app = web.Application(middlewares=[_errores], client_max_size=64 * 1024)
        app.add_routes([
            web.post("/control/ventana", self.control_abrir),
            web.get("/control/ventana", self.control_esperar),
            web.delete("/control/ventana", self.control_cerrar),
            web.get("/control/estado", self.control_estado),
            web.delete("/control/energia", self.control_energia),
            web.get("/control/vigilancia", self.control_vigilancia),
            web.post("/control/vigilancia", self.control_vigilancia),
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
        self._tareas.add(asyncio.ensure_future(self._vigilar()))

    async def parar(self):
        for tarea in list(self._tareas):
            tarea.cancel()
        self.energia.cancelar(silencio=True)
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
