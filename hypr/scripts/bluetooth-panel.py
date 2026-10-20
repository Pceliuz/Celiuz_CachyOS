#!/usr/bin/env python3
"""
hypr/scripts/bluetooth-panel.py

El menu de Bluetooth que cuelga de la barra al hacer clic en su icono.

Es una capa de Wayland (gtk-layer-shell), como el panel de calendario: queda
bajo la barra, encima de las apps, y Hyprland no la cuenta como ventana. Correrlo
otra vez con el panel abierto lo cierra, que es lo que hace el clic.

LO QUE ENSEÑA
-------------
  - Arriba, el aparato EN USO, con su bateria y un boton para soltarlo.
  - MIS AURICULARES (y lo demas emparejado): cuando se uso cada uno y en que
    estado lo tiene el demonio —esperando, en espera por el cerrojo, soltado a
    mano, bloqueado por ti—, con un boton para conectarlo o cambiar a el.
  - CERCA, SIN EMPAREJAR: mientras el panel esta abierto se busca, y lo que
    aparece con nombre se empareja con un boton, sin terminal.
  - Los dos ajustes del demonio (conectar solo, uno a la vez), que se guardan en
    bluetooth.conf como si los hubieras escrito a mano.
  - El boton «⋯» de cada emparejado deja cambiarle el nombre u olvidarlo. Sirve
    sobre todo cuando varios TWS se llaman igual: hasta que les pongas nombre,
    el panel los distingue por el final de su direccion.

LO QUE NO HACE
--------------
No decide nada sobre a quien conectar: eso es de bluetooth.py --demonio, y de
ahi se importa la logica (el orden por ultimo uso, el cerrojo, los ajustes). Este
fichero solo ENSENA lo que el demonio piensa y le da botones.

Para lo que el panel no cubre (un teclado que pide escribir un PIN, perfiles,
varios adaptadores) esta «Ajustes avanzados», que abre bluetui.

POR QUE EMPAREJAR PARA LA BUSQUEDA
----------------------------------
Medido el 2026-10-19 con unos TWS: `Pair` con la busqueda en marcha fallo con
`ConnectionAttemptFailed`, y el mismo aparato se conecto en cuanto se paro. La
radio de esta tarjeta hace a la vez el wifi y el Bluetooth, y buscar y emparejar
se pisan. Por eso el panel para de buscar, empareja, conecta y vuelve a buscar.

USO
---
    bluetooth-panel.py           abre el panel (o lo cierra si ya esta abierto)
    bluetooth-panel.py --ver     lo que enseñaria, en texto, sin abrir nada
"""

import importlib.util
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field

RAIZ = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(RAIZ, "lib"))


def _cargar_bt():
    # Por ruta y con otro nombre: `import bluetooth` podria encontrar PyBluez,
    # que se instala justo con ese nombre.
    spec = importlib.util.spec_from_file_location(
        "celiuz_bluetooth", os.path.join(RAIZ, "bluetooth.py"))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


bt = _cargar_bt()

BATERIA = "org.bluez.Battery1"
AGENTES = "org.bluez.AgentManager1"
AGENTE = "org.bluez.Agent1"
RUTA_AGENTE = "/org/celiuz/bluetooth/panel"

MAX_CERCA = 6
PLAZO_EMPAREJAR_MS = 60_000

MESES = ["ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sep", "oct", "nov", "dic"]

# Nerd Font (Material Design). Van por codigo porque en el fichero no se ven.
G_BT = "\U000F00AF"
G_BT_OFF = "\U000F00B2"
G_AURIS = "\U000F02CB"
G_ALTAVOZ = "\U000F04C3"
G_MOVIL = "\U000F011C"
G_PORTATIL = "\U000F0322"
G_TECLADO = "\U000F030C"
G_RATON = "\U000F037D"
G_MANDO = "\U000F0297"
G_IMPRESORA = "\U000F042A"
G_SOLTAR = "\U000F0338"
G_BUSCAR = "\U000F0349"
G_AJUSTES = "\U000F0493"
G_GIRO = "\U000F0450"
G_MAS = "\U000F01D8"
G_AVISO = "\U000F0026"
G_PILAS = ["\U000F008E", "\U000F007A", "\U000F007B", "\U000F007C", "\U000F007D",
           "\U000F007E", "\U000F007F", "\U000F0080", "\U000F0081", "\U000F0082",
           "\U000F0079"]

# El icono que BlueZ deduce de la clase del aparato -> (glifo, que es).
TIPOS = {
    "audio-headset": (G_AURIS, "Auriculares"),
    "audio-headphones": (G_AURIS, "Auriculares"),
    "audio-card": (G_ALTAVOZ, "Altavoz"),
    "phone": (G_MOVIL, "Teléfono"),
    "computer": (G_PORTATIL, "Ordenador"),
    "input-keyboard": (G_TECLADO, "Teclado"),
    "input-mouse": (G_RATON, "Ratón"),
    "input-tablet": (G_RATON, "Tableta"),
    "input-gaming": (G_MANDO, "Mando"),
    "printer": (G_IMPRESORA, "Impresora"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Lo que se ve (sin D-Bus ni GTK: es lo que prueba tests/unidad/bluetooth-panel.sh)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Fila:
    mac: str
    nombre: str
    glifo: str
    detalle: str = ""
    etiqueta: str = ""      # el final de la MAC, si hay otro con el mismo nombre
    marca: str = ""         # «listo para emparejar»
    accion: str = None      # soltar | conectar | cambiar | emparejar | None
    bateria: int = None
    audio: bool = False
    editable: bool = False  # se le puede cambiar el nombre u olvidar


@dataclass
class Modelo:
    hay_adaptador: bool = False
    encendido: bool = False
    equipo: str = ""
    buscando: bool = False
    rfkill_blando: bool = False
    rfkill_duro: bool = False
    en_uso: list = field(default_factory=list)
    guardados: list = field(default_factory=list)
    cerca: list = field(default_factory=list)
    cerrojo: bool = True
    auto: bool = True


def tipo_de(props):
    return TIPOS.get(str(props.get("Icon") or ""), (G_BT, "Aparato"))


def glifo_bateria(pct):
    if pct is None:
        return ""
    return G_PILAS[max(0, min(10, int(round(pct / 10))))]


def cuando(epoch, ahora):
    """«Usado hoy, 14:16», «Usado ayer», «Usado el 30 sep»."""
    if not epoch:
        return "Nunca usado"
    import datetime as dt
    dia = dt.date.fromtimestamp(epoch)
    hoy = dt.date.fromtimestamp(ahora)
    if dia == hoy:
        return "Usado hoy, %s" % time.strftime("%H:%M", time.localtime(epoch))
    if (hoy - dia).days == 1:
        return "Usado ayer"
    texto = "Usado el %d %s" % (dia.day, MESES[dia.month - 1])
    if dia.year != hoy.year:
        texto += " %d" % dia.year
    return texto


def senal(rssi):
    if rssi is None:
        return 3, ""
    if rssi >= -60:
        return 0, "muy cerca"
    if rssi >= -75:
        return 1, "cerca"
    return 2, "lejos"


def construir(objetos, recuerdo, ajustes, rfkill=(False, False), ahora=None):
    """La foto de BlueZ (adaptadores, aparatos y baterias) -> lo que enseña el
    panel. No toca nada."""
    ahora = time.time() if ahora is None else ahora
    m = Modelo(rfkill_blando=rfkill[0], rfkill_duro=rfkill[1],
               cerrojo=ajustes.cerrojo, auto=ajustes.auto)
    adaptadores = [i[bt.ADAPTADOR] for i in objetos.values() if bt.ADAPTADOR in i]
    if not adaptadores:
        return m
    m.hay_adaptador = True
    m.encendido = any(a.get("Powered") for a in adaptadores)
    m.equipo = str(adaptadores[0].get("Alias") or adaptadores[0].get("Name") or "")
    m.buscando = m.encendido and any(a.get("Discovering") for a in adaptadores)

    aparatos = bt.leer_aparatos(objetos)
    plan = bt.decidir(aparatos, recuerdo, ajustes)

    def props(a):
        return objetos[a.ruta][bt.DISPOSITIVO]

    def bateria(a):
        pct = objetos[a.ruta].get(BATERIA, {}).get("Percentage")
        return int(pct) if pct is not None else None

    # --- En uso: el activo primero ---
    conectados = sorted((a for a in aparatos if a.conectado),
                        key=lambda a: (a.mac != plan.activo, a.nombre.lower()))
    for a in conectados:
        glifo, tipo = tipo_de(props(a))
        if a.audio and a.mac != plan.activo and ajustes.cerrojo:
            detalle = "De sobra: el cerrojo lo va a soltar"
        elif a.audio:
            detalle = "Conectado · suena por aquí"
        else:
            detalle = "Conectado · %s" % tipo.lower()
        m.en_uso.append(Fila(a.mac, a.nombre, glifo, detalle, accion="soltar",
                             bateria=bateria(a), audio=a.audio,
                             editable=a.emparejado))

    # --- Emparejados que no estan conectados ---
    guardados = [a for a in aparatos if a.emparejado and not a.conectado]
    audio = bt.por_preferencia([a for a in guardados if a.audio], recuerdo)
    otros = sorted((a for a in guardados if not a.audio), key=lambda a: a.nombre.lower())
    hay_activo_audio = plan.activo is not None
    for a in audio + otros:
        glifo, tipo = tipo_de(props(a))
        if a.audio:
            partes = [cuando(recuerdo.ultimo_uso.get(a.mac), ahora)]
            if bt.bloqueado_por_ti(a, recuerdo):
                partes.append("bloqueado por ti")
            elif a.bloqueado:
                partes.append("en espera (uno a la vez)")
            elif a.mac in recuerdo.soltados:
                partes.append("lo soltaste")
            elif ajustes.auto and m.encendido and not hay_activo_audio:
                partes.append("entra solo al encenderlo")
            detalle = " · ".join(partes)
        else:
            detalle = "%s emparejado" % tipo
        if not m.encendido or bt.bloqueado_por_ti(a, recuerdo):
            accion = None
        elif a.audio and hay_activo_audio and ajustes.cerrojo:
            accion = "cambiar"
        else:
            accion = "conectar"
        m.guardados.append(Fila(a.mac, a.nombre, glifo, detalle, accion=accion,
                                bateria=bateria(a), audio=a.audio, editable=True))

    # --- Cerca, sin emparejar: solo los que dicen su nombre ---
    if m.encendido:
        nuevos = []
        for a in aparatos:
            p = props(a)
            if a.emparejado or not str(p.get("Name") or "").strip():
                continue
            rssi = p.get("RSSI")
            rssi = int(rssi) if rssi is not None else None
            orden, texto = senal(rssi)
            nuevos.append((not a.audio, orden, a.nombre.lower(), a, texto))
        nuevos.sort(key=lambda t: t[:3])
        for _, _, _, a, texto in nuevos[:MAX_CERCA]:
            glifo, tipo = tipo_de(props(a))
            detalle = " · ".join(x for x in (tipo, texto) if x)
            m.cerca.append(Fila(a.mac, a.nombre, glifo, detalle,
                                marca="listo para emparejar" if a.audio else "",
                                accion="emparejar", audio=a.audio))

    # Dos con el mismo nombre se distinguen por el final de la direccion.
    filas = m.en_uso + m.guardados + m.cerca
    veces = {}
    for f in filas:
        veces[f.nombre.lower()] = veces.get(f.nombre.lower(), 0) + 1
    for f in filas:
        if veces[f.nombre.lower()] > 1:
            f.etiqueta = "…" + f.mac[-5:]
    return m


def explicar(mensaje):
    """El error de BlueZ, en algo que se entienda."""
    m = (mensaje or "").lower()
    if "page-timeout" in m or "page timeout" in m or "host is down" in m:
        return "No contesta. ¿Está encendido y fuera del estuche?"
    if "authenticationtimeout" in m or "authentication timeout" in m:
        return "No aceptó a tiempo. Ponlo en modo emparejar y prueba otra vez."
    if "connectionattemptfailed" in m:
        return "No se pudo hablar con él. Acércalo y prueba otra vez."
    if "authenticationfailed" in m or "authentication failed" in m or "rejected" in m:
        return "Rechazó el emparejado. Bórralo del otro aparato y prueba otra vez."
    if "inprogress" in m or "in progress" in m:
        return "Ya se está intentando; espera un momento."
    if "notready" in m or "not ready" in m:
        return "El Bluetooth está apagado."
    if "busy" in m:
        return "La radio está ocupada; prueba en unos segundos."
    return (mensaje or "error").rsplit(":", 1)[-1].strip() or "error"


def ver():
    """Lo que enseñaria el panel, en texto. Para mirar sin abrir nada."""
    bus, _, error = bt._abrir()
    if error:
        print(error)
        return 1
    control = Control(bus)
    m = construir(control.foto(), bt.Recuerdo.cargar(), bt.Ajustes.cargar(),
                  bt._rfkill_bloqueado())
    if not m.hay_adaptador:
        print("Sin adaptador Bluetooth.")
        return 0
    print("Bluetooth %s: %s%s" % (m.equipo, "encendido" if m.encendido else "apagado",
                                  ", buscando" if m.buscando else ""))
    for titulo, filas in (("En uso", m.en_uso), ("Emparejados", m.guardados),
                          ("Cerca, sin emparejar", m.cerca)):
        if not filas:
            continue
        print("\n" + titulo)
        for f in filas:
            extra = " %s" % f.etiqueta if f.etiqueta else ""
            pila = "  %d%%" % f.bateria if f.bateria is not None else ""
            print("  %-22s %s%s  [%s]" % (f.nombre + extra, f.detalle, pila,
                                         f.accion or "-"))
    print("\nConectar solo: %s · Uno a la vez: %s" % (
        "si" if m.auto else "no", "si" if m.cerrojo else "no"))
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# Las acciones, por D-Bus (sin GTK: las prueba tests/e2e/bluetooth-panel.sh)
# ─────────────────────────────────────────────────────────────────────────────

AGENTE_XML = """
<node>
  <interface name="org.bluez.Agent1">
    <method name="Release"/>
    <method name="RequestPinCode">
      <arg type="o" direction="in"/><arg type="s" direction="out"/>
    </method>
    <method name="DisplayPinCode">
      <arg type="o" direction="in"/><arg type="s" direction="in"/>
    </method>
    <method name="RequestPasskey">
      <arg type="o" direction="in"/><arg type="u" direction="out"/>
    </method>
    <method name="DisplayPasskey">
      <arg type="o" direction="in"/><arg type="u" direction="in"/>
      <arg type="q" direction="in"/>
    </method>
    <method name="RequestConfirmation">
      <arg type="o" direction="in"/><arg type="u" direction="in"/>
    </method>
    <method name="RequestAuthorization">
      <arg type="o" direction="in"/>
    </method>
    <method name="AuthorizeService">
      <arg type="o" direction="in"/><arg type="s" direction="in"/>
    </method>
    <method name="Cancel"/>
  </interface>
</node>
"""


class Control:
    """Lo que hacen los botones. Cada accion es asincrona y termina llamando a
    `listo(error)`, con error None si fue bien o un texto ya explicado."""

    def __init__(self, bus, al_cambiar=None):
        self.Gio, self.GLib = bt._gio()
        self.bus = bus
        self.al_cambiar = al_cambiar
        self.objetos = {}
        self.emparejando = None      # la ruta a la que el agente le dice que si
        self.quiere_buscar = False
        self._pendiente = None
        self._agente = None
        self._subs = []

    # --- La foto, y avisar cuando cambia --------------------------------------

    def foto(self):
        GLib = self.GLib
        r = self.bus.call_sync(bt.BLUEZ, "/", bt.OBJETOS, "GetManagedObjects", None,
                               GLib.VariantType("(a{oa{sa{sv}}})"), 0,
                               bt.PLAZO_LLAMADA_MS, None)
        objetos = {}
        for ruta, ifaces in r.unpack()[0].items():
            util = {i: dict(p) for i, p in ifaces.items()
                    if i in (bt.ADAPTADOR, bt.DISPOSITIVO, BATERIA)}
            if util:
                objetos[ruta] = util
        self.objetos = objetos
        return objetos

    def escuchar(self):
        nada = self.Gio.DBusSignalFlags.NONE
        for interfaz, senal_ in ((bt.OBJETOS, "InterfacesAdded"),
                                 (bt.OBJETOS, "InterfacesRemoved"),
                                 (bt.PROPIEDADES, "PropertiesChanged")):
            self._subs.append(self.bus.signal_subscribe(
                bt.BLUEZ, interfaz, senal_, None, None, nada, self._algo_cambio))
        self._subs.append(self.bus.signal_subscribe(
            "org.freedesktop.DBus", "org.freedesktop.DBus", "NameOwnerChanged",
            "/org/freedesktop/DBus", bt.BLUEZ, nada, self._algo_cambio))

    def _algo_cambio(self, *_):
        # Llegan en rafagas (y durante la busqueda, un RSSI tras otro): se juntan.
        if self._pendiente is None:
            self._pendiente = self.GLib.timeout_add(200, self._avisar)

    def _avisar(self):
        self._pendiente = None
        if self.al_cambiar:
            self.al_cambiar()
        return False

    # --- Utilidades -----------------------------------------------------------

    def ruta(self, mac):
        for ruta, ifaces in self.objetos.items():
            p = ifaces.get(bt.DISPOSITIVO)
            if p is not None and str(p.get("Address", "")).upper() == mac:
                return ruta
        return None

    def _adaptador_de(self, ruta):
        return str(self.objetos.get(ruta, {}).get(bt.DISPOSITIVO, {}).get(
            "Adapter") or "/org/bluez/hci0")

    def _es_audio(self, ruta):
        try:
            self.foto()   # recien emparejado: los UUID acaban de llegar
        except self.GLib.Error:
            pass
        return any(a.audio for a in bt.leer_aparatos(self.objetos) if a.ruta == ruta)

    def _adaptadores(self):
        return [r for r, i in self.objetos.items()
                if i.get(bt.ADAPTADOR, {}).get("Powered")]

    def _llamar(self, ruta, interfaz, metodo, params, plazo, listo):
        """Una llamada asincrona; `listo(error_crudo_o_None)`."""
        def hecho(bus, resultado, _d=None):
            try:
                bus.call_finish(resultado)
            except self.GLib.Error as e:
                listo(e.message)
                return
            listo(None)
        self.bus.call(bt.BLUEZ, ruta, interfaz, metodo, params, None,
                      self.Gio.DBusCallFlags.NONE, plazo, None, hecho, None)

    def _poner(self, ruta, interfaz, nombre, variante, listo):
        self._llamar(ruta, bt.PROPIEDADES, "Set",
                     self.GLib.Variant("(ssv)", (interfaz, nombre, variante)),
                     bt.PLAZO_LLAMADA_MS, listo)

    # --- Buscar ---------------------------------------------------------------

    def buscar(self, si):
        """Empieza o para la busqueda en los adaptadores encendidos. BlueZ la
        para solo si este proceso se muere, asi que no puede quedarse puesta."""
        self.quiere_buscar = si
        for ruta in self._adaptadores():
            buscando = self.objetos[ruta][bt.ADAPTADOR].get("Discovering")
            if si and not buscando:
                self._llamar(ruta, bt.ADAPTADOR, "StartDiscovery", None,
                             bt.PLAZO_LLAMADA_MS, lambda _e: None)
            elif not si and buscando:
                self._llamar(ruta, bt.ADAPTADOR, "StopDiscovery", None,
                             bt.PLAZO_LLAMADA_MS, lambda _e: None)

    # --- El agente: dice que si al aparato que se esta emparejando, y a nadie mas

    def registrar_agente(self):
        info = self.Gio.DBusNodeInfo.new_for_xml(AGENTE_XML).lookup_interface(AGENTE)
        registrar = getattr(self.bus, "register_object_with_closures2",
                            self.bus.register_object)
        try:
            self._agente = registrar(RUTA_AGENTE, info, self._agente_llamada, None, None)
        except self.GLib.Error:
            self._agente = None
            return
        # NoInputNoOutput: lo que piden unos auriculares. Lo que necesite un PIN
        # escrito se empareja desde bluetui («Ajustes avanzados»).
        self._llamar("/org/bluez", AGENTES, "RegisterAgent",
                     self.GLib.Variant("(os)", (RUTA_AGENTE, "NoInputNoOutput")),
                     bt.PLAZO_LLAMADA_MS, lambda _e: None)

    def soltar_agente(self):
        if self._agente is None:
            return
        try:
            self.bus.call_sync(bt.BLUEZ, "/org/bluez", AGENTES, "UnregisterAgent",
                               self.GLib.Variant("(o)", (RUTA_AGENTE,)), None, 0,
                               2000, None)
        except self.GLib.Error:
            pass
        self.bus.unregister_object(self._agente)
        self._agente = None

    def _agente_llamada(self, _c, _emisor, _ruta, _i, metodo, params, invocacion):
        GLib = self.GLib
        if metodo in ("Release", "Cancel"):
            invocacion.return_value(None)
            return
        aparato = params.unpack()[0] if params is not None and len(params.unpack()) else None
        if aparato is None or aparato != self.emparejando:
            invocacion.return_dbus_error("org.bluez.Error.Rejected",
                                         "no lo esta emparejando el panel")
            return
        if metodo == "RequestPinCode":
            # Los auriculares viejos con PIN fijo usan casi todos el 0000.
            invocacion.return_value(GLib.Variant("(s)", ("0000",)))
        elif metodo == "RequestPasskey":
            invocacion.return_value(GLib.Variant("(u)", (0,)))
        else:
            invocacion.return_value(None)

    # --- Las acciones ---------------------------------------------------------

    def conectar(self, mac, listo):
        ruta = self.ruta(mac)
        if ruta is None:
            listo("Ya no está.")
            return

        def hecho(e):
            if not e or "alreadyconnected" in e.lower():
                listo(None)
            elif "inprogress" in e.lower() or "in progress" in e.lower():
                # Lo esta llamando otro a la vez (el demonio, tras soltar el que
                # habia): no es un fallo, se espera a ver en que acaba.
                self._esperar_conexion(ruta, listo, time.monotonic() + 20)
            else:
                listo(explicar(e))
        self._llamar(ruta, bt.DISPOSITIVO, "Connect", None, bt.PLAZO_CONECTAR_MS, hecho)

    def _esperar_conexion(self, ruta, listo, hasta):
        def mirar():
            try:
                self.foto()
            except self.GLib.Error:
                pass
            if self.objetos.get(ruta, {}).get(bt.DISPOSITIVO, {}).get("Connected"):
                listo(None)
                return False
            if time.monotonic() > hasta:
                listo(explicar("page-timeout"))
                return False
            return True
        self.GLib.timeout_add(500, mirar)

    def soltar(self, mac, listo):
        ruta = self.ruta(mac)
        if ruta is None:
            listo(None)
            return
        self._llamar(ruta, bt.DISPOSITIVO, "Disconnect", None, bt.PLAZO_LLAMADA_MS,
                     lambda e: listo(explicar(e) if e else None))

    def cambiar(self, mac, listo):
        """Soltar los auriculares en uso y conectar estos. Soltar primero hace
        falta con el cerrojo puesto: si no, el demonio echaria al nuevo."""
        en_uso = [a.mac for a in bt.leer_aparatos(self.objetos)
                  if a.conectado and a.audio and a.mac != mac]
        if not en_uso:
            self.conectar(mac, listo)
            return
        pendientes = {"n": len(en_uso)}

        def suelto(_e):
            pendientes["n"] -= 1
            if pendientes["n"] == 0:
                # Un respiro para que el demonio vea la salida y quite su bloqueo.
                self.GLib.timeout_add(800, lambda: self.conectar(mac, listo) or False)
        for otro in en_uso:
            self.soltar(otro, suelto)

    def emparejar(self, mac, listo):
        ruta = self.ruta(mac)
        if ruta is None:
            listo("Ya no está: vuelve a buscar.")
            return
        volver_a_buscar = self.quiere_buscar
        self.emparejando = ruta

        def fin(error):
            self.emparejando = None
            if volver_a_buscar:
                self.buscar(True)
            listo(error)

        def conectado(e):
            fin(explicar(e) if e else None)

        def confiado(_e):
            # Con otros auriculares puestos y el cerrojo encendido, conectar a
            # secas no sirve: el demonio bloquea al recien emparejado en cuanto
            # se entera, y si entra lo echa. Visto en el anidado. Se hace como
            # «Usar este»: se suelta el que estaba y entra el nuevo.
            if bt.Ajustes.cargar().cerrojo and self._es_audio(ruta):
                self.cambiar(mac, lambda e: fin(e))
            else:
                self._llamar(ruta, bt.DISPOSITIVO, "Connect", None,
                             bt.PLAZO_CONECTAR_MS, conectado)

        def emparejado(e):
            if e and "alreadyexists" not in e.lower():
                fin(explicar(e))
                return
            # Trusted: que pueda volver a entrar solo la proxima vez.
            self._poner(ruta, bt.DISPOSITIVO, "Trusted", self.GLib.Variant("b", True),
                        confiado)

        def pedir():
            self._llamar(ruta, bt.DISPOSITIVO, "Pair", None, PLAZO_EMPAREJAR_MS,
                         emparejado)
            return False

        # Ver la cabecera: con la busqueda en marcha, emparejar falla.
        self.buscar(False)
        self.quiere_buscar = volver_a_buscar
        self.GLib.timeout_add(600, pedir)

    def renombrar(self, mac, nombre, listo):
        ruta = self.ruta(mac)
        if ruta is None:
            listo("Ya no está.")
            return
        # Un nombre vacio le devuelve el suyo de fabrica (lo hace BlueZ).
        self._poner(ruta, bt.DISPOSITIVO, "Alias", self.GLib.Variant("s", nombre.strip()),
                    lambda e: listo(explicar(e) if e else None))

    def olvidar(self, mac, listo):
        ruta = self.ruta(mac)
        if ruta is None:
            listo(None)
            return
        self._llamar(self._adaptador_de(ruta), bt.ADAPTADOR, "RemoveDevice",
                     self.GLib.Variant("(o)", (ruta,)), bt.PLAZO_LLAMADA_MS,
                     lambda e: listo(explicar(e) if e else None))

    def cerrar(self):
        if self.quiere_buscar:
            for ruta in self._adaptadores():
                if self.objetos[ruta][bt.ADAPTADOR].get("Discovering"):
                    try:
                        self.bus.call_sync(bt.BLUEZ, ruta, bt.ADAPTADOR, "StopDiscovery",
                                           None, None, 0, 2000, None)
                    except self.GLib.Error:
                        pass
        self.soltar_agente()
        for s in self._subs:
            self.bus.signal_unsubscribe(s)
        self._subs = []


# ─────────────────────────────────────────────────────────────────────────────
# La ventana
# ─────────────────────────────────────────────────────────────────────────────

# El aspecto y la capa son los de todos los paneles de la barra: lib/panel_estilo.py
# (sin GTK, lo comprueban las pruebas) y lib/panel_capa.py.
from panel_estilo import _hex, css_base as css  # noqa: E402,F401  (las pruebas los usan)


def abrir_panel():
    try:
        import panel_capa as pc
    except (ImportError, ValueError):
        # Sin gtk-layer-shell no hay panel, pero el clic no puede quedarse en
        # nada (waybar se traga el error): se dice, y se abre bluetui.
        bt.avisar("Falta gtk-layer-shell",
                  "Sin el, el panel de Bluetooth no puede abrirse; va bluetui.\n"
                  "sudo pacman -S gtk-layer-shell")
        return bt.gestionar()
    if not pc.solo_wayland():
        print("bluetooth-panel: hace falta una sesion Wayland", file=sys.stderr)
        return 1
    GLib, Gtk, Pango = pc.GLib, pc.Gtk, pc.Pango
    etiqueta, boton, caja = pc.etiqueta, pc.boton, pc.caja

    class Panel(pc.PanelCapa):
        def __init__(self, bus):
            super().__init__("bluetooth-panel", G_BT, "Bluetooth")
            self.control = Control(bus, self.repintar)
            self.ocupados = {}      # mac -> texto mientras se hace algo con el
            self.editando = None    # mac del que tiene abierto el «⋯»
            self.confirmar = None   # mac que se va a olvidar, a falta del «si»
            self.modelo = None
            self.demonio = bt._demonio_vivo()

            self.sw_auto = self.opcion("Conectar solo al encenderlos",
                                       "Primero el último que usaste",
                                       lambda si: self._al_ajuste("auto", si))
            self.sw_cerrojo = self.opcion("Uno a la vez", "Con uno puesto, los demás esperan",
                                          lambda si: self._al_ajuste("cerrojo", si))
            botones = caja(espacio=8)
            self.b_buscar = boton(G_BUSCAR + "  Buscar aparatos",
                                  lambda: self.control.buscar(True), ("suave",))
            botones.pack_start(self.b_buscar, False, False, 0)
            botones.pack_end(boton(G_AJUSTES + "  Ajustes avanzados", self._avanzado,
                                   ("suave",)), False, False, 0)
            self.pie.pack_start(botones, False, False, 2)

            self.control.escuchar()
            self.control.registrar_agente()
            self.repintar(primera=True)
            if self.modelo.encendido:
                self.control.buscar(True)

        # --- Pintar lo que dice el modelo -------------------------------------

        def repintar(self, primera=False, forzar=False):
            try:
                objetos = self.control.foto()
            except GLib.Error as e:
                self.avisar("No pude leer el Bluetooth: %s" % explicar(e.message), True)
                return
            modelo = construir(objetos, bt.Recuerdo.cargar(), bt.Ajustes.cargar(),
                               bt._rfkill_bloqueado())
            if self.control.quiere_buscar and modelo.encendido and not modelo.buscando \
                    and self.control.emparejando is None:
                self.control.buscar(True)   # se encendio con el panel abierto
            # Con el «⋯» abierto no se rehace nada: se perderia lo que escribes.
            if not (primera or forzar) and (modelo == self.modelo or self.editando):
                return
            self.modelo = m = modelo

            self.poner(self.interruptor, m.encendido,
                       not m.rfkill_duro and (m.hay_adaptador or m.rfkill_blando))
            self.poner(self.sw_auto, m.auto)
            self.poner(self.sw_cerrojo, m.cerrojo)
            if not m.hay_adaptador:
                sub = "apagado por el modo avión" if m.rfkill_blando else "no hay adaptador"
            else:
                sub = "%s · %s" % (m.equipo, "encendido" if m.encendido else "apagado")
            self.cabecera(G_BT if m.encendido else G_BT_OFF, sub, apagado=not m.encendido)
            self.b_buscar.set_sensitive(m.encendido and not m.buscando)
            self.b_buscar.set_label(G_BUSCAR + ("  Buscando…" if m.buscando else "  Buscar aparatos"))

            self.vaciar_cuerpo()
            if not m.encendido:
                self.vacio(G_AVISO + "  " + (
                    "El interruptor o la tecla de modo avión lo tienen apagado."
                    if m.rfkill_duro else "El Bluetooth está apagado. Enciéndelo arriba."))
            else:
                self.seccion("En uso")
                if m.en_uso:
                    for f in m.en_uso:
                        self.cuerpo.pack_start(self._fila(f, "uso"), False, False, 0)
                else:
                    self.vacio("Nada conectado.")
                if m.guardados:
                    self.seccion("Mis aparatos")
                    for f in m.guardados:
                        self.cuerpo.pack_start(self._fila(f, "guardado"), False, False, 0)
                self.seccion("Cerca, sin emparejar", buscando=m.buscando)
                if m.cerca:
                    for f in m.cerca:
                        self.cuerpo.pack_start(self._fila(f, "cerca"), False, False, 0)
                else:
                    self.vacio("Pon el aparato en modo emparejar y saldrá aquí."
                               if m.buscando else "Pulsa «Buscar aparatos».")
            if m.auto and not self.demonio and m.hay_adaptador:
                self.avisar("El demonio no está en marcha: no se conectan solos hasta "
                            "volver a entrar en la sesión.", fijo=True)
            self.terminar_cuerpo()

        def _fila(self, f, tipo):
            externa = caja(vertical=True, espacio=8)
            externa.get_style_context().add_class("uso" if tipo == "uso" else "fila")
            if tipo == "cerca":
                externa.get_style_context().add_class("cerca")
            fila = caja(espacio=12)
            ico = etiqueta(f.glifo, ("ico",), xalign=0.5)
            ico.set_valign(Gtk.Align.CENTER)
            fila.pack_start(ico, False, False, 0)

            textos = caja(vertical=True, espacio=1)
            linea = caja(espacio=6)
            nombre = etiqueta(f.nombre, ("nombre",))
            nombre.set_ellipsize(Pango.EllipsizeMode.END)
            linea.pack_start(nombre, False, False, 0)
            if f.etiqueta:
                linea.pack_start(etiqueta(f.etiqueta, ("etiqueta",)), False, False, 0)
            textos.pack_start(linea, False, False, 0)
            if f.marca:
                # En su propia linea: al lado del nombre se lo comia entero.
                marca = caja()
                marca.pack_start(etiqueta(f.marca, ("marca",)), False, False, 0)
                textos.pack_start(marca, False, False, 1)
            detalle = etiqueta(self.ocupados.get(f.mac) or f.detalle, ("detalle",))
            detalle.set_line_wrap(True)
            detalle.set_max_width_chars(28)
            textos.pack_start(detalle, False, False, 0)
            fila.pack_start(textos, True, True, 0)

            if f.editable:
                fila.pack_end(boton(G_MAS, lambda: self._editar(f.mac), ("mas",)),
                              False, False, 0)
            accion = self._boton_accion(f)
            if accion is not None:
                fila.pack_end(accion, False, False, 0)
            externa.pack_start(fila, False, False, 0)

            if tipo == "uso" and f.bateria is not None:
                pila = caja(espacio=8)
                pila.pack_start(etiqueta(glifo_bateria(f.bateria), ("pila",)), False, False, 0)
                barra = Gtk.LevelBar()
                barra.set_min_value(0)
                barra.set_max_value(100)
                barra.set_value(f.bateria)
                barra.set_valign(Gtk.Align.CENTER)
                barra.remove_offset_value(Gtk.LEVEL_BAR_OFFSET_LOW)
                barra.remove_offset_value(Gtk.LEVEL_BAR_OFFSET_HIGH)
                barra.remove_offset_value(Gtk.LEVEL_BAR_OFFSET_FULL)
                pila.pack_start(barra, True, True, 0)
                pila.pack_start(etiqueta("%d%%" % f.bateria, ("pila",)), False, False, 0)
                externa.pack_start(pila, False, False, 0)

            if self.editando == f.mac:
                externa.pack_start(self._editor(f), False, False, 0)
            return externa

        def _boton_accion(self, f):
            if f.mac in self.ocupados or f.accion is None:
                return None
            if f.accion == "soltar":
                texto, clases = (G_SOLTAR + " Soltar", ())
            elif f.accion == "emparejar":
                texto, clases = ("Emparejar", ("lleno",))
            elif f.accion == "cambiar":
                texto, clases = ("Usar este", ("suave",))
            else:
                texto, clases = ("Conectar", ("suave",))
            return boton(texto, lambda: self._hacer(f), clases)

        def _editor(self, f):
            c = caja(espacio=6)
            if self.confirmar == f.mac:
                pregunta = etiqueta("¿Olvidar %s? Habrá que emparejarlo otra vez." % f.nombre,
                                    ("detalle",))
                pregunta.set_line_wrap(True)
                c.pack_start(pregunta, True, True, 0)
                c.pack_end(boton("No", self._cerrar_editor, ("suave",)), False, False, 0)
                c.pack_end(boton("Sí, olvidar", lambda: self._olvidar(f), ("peligro",)),
                           False, False, 0)
                return c
            entrada = Gtk.Entry()
            entrada.set_text(f.nombre)
            entrada.set_placeholder_text("Nombre")
            entrada.connect("activate", lambda *_: self._renombrar(f, entrada.get_text()))
            c.pack_start(entrada, True, True, 0)
            c.pack_start(boton("Guardar", lambda: self._renombrar(f, entrada.get_text()),
                               ("lleno",)), False, False, 0)
            c.pack_start(boton("Olvidar", lambda: self._pedir_olvidar(f.mac), ("peligro",)),
                         False, False, 0)
            GLib.idle_add(lambda: entrada.grab_focus() or False)
            return c

        # --- Lo que hacen los botones -----------------------------------------

        def _hacer(self, f):
            textos = {"soltar": "Soltando…", "conectar": "Conectando…",
                      "cambiar": "Cambiando…", "emparejar": "Emparejando… acércalo"}
            self.ocupados[f.mac] = textos[f.accion]
            self._forzar()

            def listo(error):
                self.ocupados.pop(f.mac, None)
                if error:
                    self.avisar("%s: %s" % (f.nombre, error), True)
                elif f.accion == "emparejar":
                    self.avisar("%s emparejado y conectado." % f.nombre)
                self._forzar()

            getattr(self.control, f.accion)(f.mac, listo)

        def _editar(self, mac):
            self.confirmar = None
            self.editando = None if self.editando == mac else mac
            self._forzar()

        def _cerrar_editor(self):
            self.editando = self.confirmar = None
            self._forzar()

        def _pedir_olvidar(self, mac):
            self.confirmar = mac
            self._forzar()

        def _renombrar(self, f, nombre):
            self.editando = None

            def listo(error):
                if error:
                    self.avisar("No pude renombrarlo: %s" % error, True)
                self._forzar()
            self.control.renombrar(f.mac, nombre, listo)

        def _olvidar(self, f):
            self.editando = self.confirmar = None

            def listo(error):
                if error:
                    self.avisar("No pude olvidarlo: %s" % error, True)
                else:
                    self.avisar("%s olvidado." % f.nombre)
                self._forzar()
            self.control.olvidar(f.mac, listo)

        def _forzar(self):
            """Repinta aunque BlueZ no haya cambiado nada: cambio lo de
            alrededor (un «Conectando…», el editor, un ajuste)."""
            self.repintar(forzar=True)

        def al_interruptor(self, _activo):
            # alternar() ya sabe de rfkill (el modo avion) y avisa si no puede.
            subprocess.Popen([os.path.join(RAIZ, "bluetooth.py"), "alternar"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        def _al_ajuste(self, clave, activo):
            ajustes = bt.Ajustes.cargar()
            setattr(ajustes, clave, activo)
            try:
                ajustes.guardar()
            except OSError as e:
                self.avisar("No pude guardar el ajuste: %s" % e, True)
            self._forzar()

        def _avanzado(self):
            subprocess.Popen([os.path.join(RAIZ, "bluetooth.py"), "gestionar"],
                             start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.close()

        # --- Lo de la base ----------------------------------------------------

        def ocupado(self):
            # Cerrar a medio emparejar lo cortaria; y escribiendo un nombre,
            # alejar el raton no es «ya no lo quiero».
            return bool(self.ocupados or self.editando)

        def al_escape(self):
            if self.editando:
                self._cerrar_editor()
            else:
                self.close()

        def al_cerrar(self):
            self.control.cerrar()

    def crear():
        bus, _, error = bt._abrir()
        if error:
            bt.avisar("Bluetooth", error)
            return None
        return Panel(bus)

    return pc.lanzar("bluetooth-panel", crear)


def main(argv):
    if argv == ["--ver"]:
        return ver()
    if argv:
        print(__doc__.split("USO\n---\n", 1)[-1].rstrip(), file=sys.stderr)
        return 2
    return abrir_panel()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
