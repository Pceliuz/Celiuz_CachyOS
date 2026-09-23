#!/usr/bin/env python3
"""
~/dotfiles/hypr/scripts/bluetooth.py

Los auriculares Bluetooth se conectan solos, y de uno en uno.

LO QUE HACE
-----------
1. SE CONECTA SOLO. Con el Bluetooth encendido y ningun auricular conectado,
   prueba los emparejados uno detras de otro, EL ULTIMO QUE USASTE PRIMERO, y se
   queda con el primero que conteste — que es el que tienes encendido. Si tienes
   dos encendidos, gana el que usaste la ultima vez.

2. EL CERROJO. Mientras un auricular esta conectado, los demas no pueden
   entrar hasta que lo desconectes. Lleva dos capas, y hacen falta las dos:
     - Se BLOQUEAN (la propiedad `Blocked` de BlueZ). Un aparato bloqueado no
       puede conectarse por su cuenta: el kernel rechaza la llamada antes de que
       llegue a ningun sitio, sin que el audio salte ni un instante.
     - Pero `Blocked` NO frena una conexion que se pide DESDE ESTE LADO. Medido
       el 2026-09-21: con los TWS bloqueados, `bluetoothctl connect` se puso a
       buscarlos igual (acabo en `br-connection-page-timeout`, no en un
       rechazo). O sea que desde bluetui se podria colar uno. Si pasa, se le
       echa en el acto y sale un aviso diciendo por que.

3. SOLTAR A MANO NO ES UNA CAIDA. Si desconectas tu el auricular (bluetui, clic
   central en la barra, `bluetooth.py soltar`), no se vuelve a conectar solo: se
   prueba con los demas, y ese se queda quieto hasta que apagues y enciendas el
   Bluetooth o lo conectes tu. Si en cambio se apaga, se mete en el estuche o se
   sale de alcance, se le vuelve a buscar.

   Esto es lo que permite cambiar de auricular: soltar el que llevas y dejar que
   entre el otro. Sin esta regla el demonio recuperaria al primero a los pocos
   segundos, que era el defecto del `auris-reconectar` de antes (necesitaba un
   fichero de pausa aparte para poder desconectarlo).

   La diferencia la da BlueZ, no una suposicion: desde la 5.7x cada
   desconexion trae su motivo en la senal `Device1.Disconnected`
   (`org.bluez.Reason.Local`, `Remote`, `Timeout`, `Suspend`...). Solo `Local`
   cuenta como soltarlo, y solo si no fuimos nosotros quienes lo echamos.

POR QUE HACE FALTA UN DEMONIO
-----------------------------
BlueZ no persigue a nadie. `Trusted: yes` solo quiere decir que ACEPTA la
conexion si el aparato la pide, y muchos TWS no la piden: despues de una
desconexion desde este lado se quedan esperando a que alguien los llame. Medido
el 2026-08-18 con los del autor. Alguien tiene que iniciarla desde aqui.

LO QUE SE GUARDA, Y DONDE
-------------------------
    $XDG_STATE_HOME/celiuz/bluetooth.json      cuando usaste cada auricular por
                                               ultima vez, y cuales bloqueo ESTE
                                               demonio. Sobrevive a reinicios.
    $XDG_RUNTIME_DIR/celiuz-bluetooth.json     los que soltaste a mano. Se
                                               borra al reiniciar, a proposito.

La lista de bloqueados tiene que sobrevivir a un reinicio porque el `Blocked` de
BlueZ tambien sobrevive (se escribe en /var/lib/bluetooth). Si el equipo se
apaga con un auricular puesto, los otros amanecen bloqueados, y alguien tiene
que saber que fueron bloqueados por el cerrojo y no por ti. Por eso:

    ESTE DEMONIO SOLO DESBLOQUEA LO QUE BLOQUEO EL. Un aparato que bloqueaste tu
    a mano no aparece en su lista, no se toca nunca y tampoco se intenta
    conectar.

Y la red de seguridad: al arrancar, al apagar el Bluetooth y al salir, se
desbloquea todo lo suyo que no haga falta. Si aun asi te encuentras un auricular
bloqueado sin motivo, `bluetooth.py --ver` dice quien lo bloqueo, y
`bluetoothctl unblock <MAC>` lo arregla a mano.

QUE CUENTA COMO AURICULAR
-------------------------
Lo que anuncia recibir audio (A2DP «Audio Sink») o hacer de manos libres o de
auricular (HFP/HSP), o se presenta con un icono de audio. Un teclado, un raton o
el movil no se tocan nunca: ni se bloquean ni se prueban.

USO
---
    bluetooth.py --demonio   lo de arriba (lo lanza conf/autostart.conf)
    bluetooth.py --ver       el estado, sin tocar nada
    bluetooth.py conectar    conecta ya el primero que conteste
    bluetooth.py soltar      desconecta el que estes usando
    bluetooth.py alternar    enciende o apaga el Bluetooth (clic derecho en la
                             barra); si esta bloqueado por rfkill, lo desbloquea
"""

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field

BLUEZ = "org.bluez"
DISPOSITIVO = "org.bluez.Device1"
ADAPTADOR = "org.bluez.Adapter1"
PROPIEDADES = "org.freedesktop.DBus.Properties"
OBJETOS = "org.freedesktop.DBus.ObjectManager"

RAZON_LOCAL = "org.bluez.Reason.Local"

# Los perfiles que dicen «por aqui sale sonido hacia ti». Es el LADO que importa:
# un movil tambien habla A2DP y manos libres, pero anuncia los UUID del otro
# extremo (Audio Source 110a, Handsfree AG 111f) y aqui no casa.
UUIDS_AUDIO = frozenset({
    "0000110b-0000-1000-8000-00805f9b34fb",   # A2DP, el que escucha (Audio Sink)
    "0000111e-0000-1000-8000-00805f9b34fb",   # HFP, el lado del auricular
    "00001108-0000-1000-8000-00805f9b34fb",   # HSP, el lado del auricular
})
# Por si los UUID aun no se han leido (pasa con uno recien emparejado). El icono
# lo deduce BlueZ de la clase del aparato.
ICONOS_AUDIO = frozenset({"audio-headset", "audio-headphones", "audio-card"})

# El ritmo de los intentos cuando no contesta ninguno. El primero va casi en el
# acto; despues se afloja de 10 s a 60 s para no tener la radio buscando todo el
# rato: cada intento contra un auricular apagado son unos 5 s de busqueda, y en
# este portatil la radio del Bluetooth es la misma tarjeta que la del wifi.
# El tope es 60 y no los 120 de antes: ahora hay varios auriculares y quien
# enciende uno espera que entre pronto.
ESPERA_PRIMERA = 1
ESPERA_MIN = 10
ESPERA_MAX = 60
PLAZO_CONECTAR_MS = 30_000
PLAZO_LLAMADA_MS = 10_000

# Una desconexion que llega hasta estos segundos despues de echar a un aparato
# es la nuestra, no un «lo soltaste tu».
MARGEN_ECHADO = 10
# Y si a los 5 s sigue conectado, se le vuelve a echar.
REINTENTO_ECHAR = 5
# Y un auricular que se cae antes de llevar estos segundos puesto no se ha
# soltado a mano: es una conexion que BlueZ tiro por su cuenta (un perfil que
# fallo al negociar se despide tambien con motivo `Local`).
MINIMO_EN_USO = 3


def _dir_estado():
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return os.path.join(base, "celiuz")


def _dir_runtime():
    return os.environ.get("XDG_RUNTIME_DIR") or "/run/user/%d" % os.getuid()


def fichero_recuerdo():
    return os.path.join(_dir_estado(), "bluetooth.json")


def fichero_soltados():
    return os.path.join(_dir_runtime(), "celiuz-bluetooth.json")


def log(mensaje):
    # Va al diario de la unidad: journalctl --user -u celiuz-bluetooth
    print("bluetooth: " + mensaje, file=sys.stderr, flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# Lo que se decide (sin D-Bus: es lo que prueba tests/unidad/bluetooth.sh)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Aparato:
    ruta: str
    mac: str
    nombre: str
    audio: bool
    emparejado: bool
    conectado: bool
    bloqueado: bool
    encendido: bool      # su adaptador esta encendido


def leer_aparatos(objetos):
    """La foto de BlueZ (lo que da GetManagedObjects) como lista de Aparato."""
    encendidos = {ruta for ruta, ifaces in objetos.items()
                  if ifaces.get(ADAPTADOR, {}).get("Powered")}
    aparatos = []
    for ruta, ifaces in objetos.items():
        p = ifaces.get(DISPOSITIVO)
        if p is None:
            continue
        mac = str(p.get("Address", "")).upper()
        uuids = {str(u).lower() for u in p.get("UUIDs", [])}
        aparatos.append(Aparato(
            ruta=ruta,
            mac=mac,
            nombre=str(p.get("Alias") or p.get("Name") or mac),
            audio=bool(uuids & UUIDS_AUDIO) or p.get("Icon") in ICONOS_AUDIO,
            emparejado=bool(p.get("Paired")),
            conectado=bool(p.get("Connected")),
            bloqueado=bool(p.get("Blocked")),
            encendido=p.get("Adapter") in encendidos,
        ))
    return aparatos


def hay_adaptador_encendido(objetos):
    return any(ifaces.get(ADAPTADOR, {}).get("Powered")
               for ifaces in objetos.values())


@dataclass
class Recuerdo:
    ultimo_uso: dict = field(default_factory=dict)   # mac -> epoch
    bloqueados: set = field(default_factory=set)     # los que bloqueo el cerrojo
    soltados: set = field(default_factory=set)       # los que soltaste a mano
    activo: str = None                               # el que esta en uso

    @classmethod
    def cargar(cls):
        r = cls()
        datos = _leer_json(fichero_recuerdo())
        usos = datos.get("ultimo_uso")
        if isinstance(usos, dict):
            r.ultimo_uso = {str(m).upper(): float(t) for m, t in usos.items()
                            if isinstance(t, (int, float))}
        if isinstance(datos.get("bloqueados"), list):
            r.bloqueados = {str(m).upper() for m in datos["bloqueados"]}
        sueltos = _leer_json(fichero_soltados()).get("soltados")
        if isinstance(sueltos, list):
            r.soltados = {str(m).upper() for m in sueltos}
        return r

    def guardar(self):
        _escribir_json(fichero_recuerdo(), {
            "ultimo_uso": self.ultimo_uso,
            "bloqueados": sorted(self.bloqueados),
        })
        _escribir_json(fichero_soltados(), {"soltados": sorted(self.soltados)})


def _leer_json(ruta):
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def _escribir_json(ruta, datos):
    # Con un temporal y os.replace: un corte a medias no puede dejar la lista de
    # bloqueados vacia, que es la que dice que desbloquear.
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        temporal = ruta + ".tmp"
        with open(temporal, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(temporal, ruta)
    except OSError as e:
        log("no pude guardar %s: %s" % (ruta, e))


def por_preferencia(aparatos, recuerdo):
    """El ultimo que usaste primero. Los que nunca se usaron, al final y por
    nombre, para que el orden no cambie de una vez a otra."""
    return sorted(aparatos, key=lambda a: (-recuerdo.ultimo_uso.get(a.mac, 0.0),
                                           a.nombre.lower(), a.mac))


def bloqueado_por_ti(aparato, recuerdo):
    return aparato.bloqueado and aparato.mac not in recuerdo.bloqueados


@dataclass
class Plan:
    activo: str = None
    echar: list = field(default_factory=list)        # conectados de sobra
    bloquear: list = field(default_factory=list)
    desbloquear: list = field(default_factory=list)
    candidatos: list = field(default_factory=list)   # a quien llamar, en orden


def decidir(aparatos, recuerdo):
    """Lo que tiene que pasar ahora mismo. No hace nada: solo lo dice.

    Es de nivel y no de flanco —mira como estan las cosas, no que acaba de
    cambiar—, asi que da igual el orden en que lleguen las senales o si se
    pierde una: la siguiente foto corrige.
    """
    auriculares = [a for a in aparatos
                   if a.audio and a.emparejado and a.encendido]
    conectados = [a for a in auriculares if a.conectado]
    plan = Plan()

    # El que ya estaba en uso sigue siendolo mientras siga conectado. Si entran
    # dos a la vez sin que hubiera ninguno, gana el que usaste la ultima vez.
    if recuerdo.activo in {a.mac for a in conectados}:
        plan.activo = recuerdo.activo
    elif conectados:
        plan.activo = por_preferencia(conectados, recuerdo)[0].mac

    if plan.activo:
        for a in auriculares:
            if a.mac == plan.activo:
                # Conectado pero con nuestro bloqueo encima: pasa cuando se le
                # llamo antes de que llegara a aplicarse el desbloqueo.
                if a.bloqueado and a.mac in recuerdo.bloqueados:
                    plan.desbloquear.append(a.mac)
            elif a.conectado:
                plan.echar.append(a.mac)
            elif not a.bloqueado:
                plan.bloquear.append(a.mac)
        return plan

    # Nadie en uso: fuera todos los bloqueos del cerrojo, y a buscar.
    plan.desbloquear = sorted(recuerdo.bloqueados)
    libres = [a for a in auriculares
              if not bloqueado_por_ti(a, recuerdo) and a.mac not in recuerdo.soltados]
    plan.candidatos = [a.mac for a in por_preferencia(libres, recuerdo)]
    return plan


# ─────────────────────────────────────────────────────────────────────────────
# D-Bus
# ─────────────────────────────────────────────────────────────────────────────

def _gio():
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib
    return Gio, GLib


def bus_del_sistema():
    """El bus de BlueZ. Gio respeta DBUS_SYSTEM_BUS_ADDRESS, y las pruebas lo
    apuntan a un bus privado con un BlueZ falso: asi nunca tocan el de verdad."""
    Gio, _ = _gio()
    return Gio.bus_get_sync(Gio.BusType.SYSTEM, None)


def bluez_presente(bus):
    _, GLib = _gio()
    r = bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus",
                      "org.freedesktop.DBus", "NameHasOwner",
                      GLib.Variant("(s)", (BLUEZ,)), GLib.VariantType("(b)"),
                      0, PLAZO_LLAMADA_MS, None)
    return bool(r.unpack()[0])


def foto(bus):
    """Adaptadores y aparatos, como {ruta: {interfaz: {propiedad: valor}}}."""
    _, GLib = _gio()
    r = bus.call_sync(BLUEZ, "/", OBJETOS, "GetManagedObjects", None,
                      GLib.VariantType("(a{oa{sa{sv}}})"), 0,
                      PLAZO_LLAMADA_MS, None)
    objetos = {}
    for ruta, ifaces in r.unpack()[0].items():
        util = {i: dict(p) for i, p in ifaces.items()
                if i in (ADAPTADOR, DISPOSITIVO)}
        if util:
            objetos[ruta] = util
    return objetos


def _variante_blocked(valor):
    _, GLib = _gio()
    return GLib.Variant("(ssv)", (DISPOSITIVO, "Blocked", GLib.Variant("b", valor)))


def avisar(titulo, cuerpo):
    # Popen y no run: si mako no esta, notify-send se queda esperando, y este
    # demonio no puede quedarse parado por un aviso.
    try:
        subprocess.Popen(["notify-send", "-a", "Bluetooth", "-i", "bluetooth",
                          titulo, cuerpo],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except OSError:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# El demonio
# ─────────────────────────────────────────────────────────────────────────────

class Demonio:
    def __init__(self, bus):
        self.Gio, self.GLib = _gio()
        self.bus = bus
        self.recuerdo = Recuerdo.cargar()
        self.objetos = {}
        self.presente = False

        self._pendiente = False        # hay una reconciliacion en la cola
        self._encendido = None         # None: aun no lo sabemos
        self._activo_desde = 0.0
        self._ultimo_activo = None
        self._echados = {}             # mac -> cuando se le echo (monotonic)
        self._en_vuelo = set()         # (mac, valor) de un Blocked ya pedido

        self._espera = ESPERA_MIN
        self._temporizador = None
        self._cola = []                # la ronda de llamadas en curso
        self._conectando = None

    # --- Escuchar -------------------------------------------------------------

    def arrancar(self):
        Gio = self.Gio
        nada = Gio.DBusSignalFlags.NONE
        self.bus.signal_subscribe("org.freedesktop.DBus", "org.freedesktop.DBus",
                                  "NameOwnerChanged", "/org/freedesktop/DBus",
                                  BLUEZ, nada, self._al_cambiar_dueno)
        self.bus.signal_subscribe(BLUEZ, OBJETOS, "InterfacesAdded", None, None,
                                  nada, self._al_anadir)
        self.bus.signal_subscribe(BLUEZ, OBJETOS, "InterfacesRemoved", None, None,
                                  nada, self._al_quitar)
        self.bus.signal_subscribe(BLUEZ, PROPIEDADES, "PropertiesChanged", None,
                                  None, nada, self._al_cambiar)
        self.bus.signal_subscribe(BLUEZ, DISPOSITIVO, "Disconnected", None, None,
                                  nada, self._al_desconectar)
        if bluez_presente(self.bus):
            self._aparece_bluez()
        else:
            log("BlueZ no esta corriendo; espero a que aparezca")

    def _aparece_bluez(self):
        try:
            self.objetos = foto(self.bus)
        except self.GLib.Error as e:
            log("no pude leer BlueZ: %s" % e.message)
            return
        self.presente = True
        self._encendido = None
        log("BlueZ presente: %d aparatos de audio emparejados" % len(
            [a for a in leer_aparatos(self.objetos) if a.audio and a.emparejado]))
        self._despertar()
        self._reconciliar()

    def _al_cambiar_dueno(self, _c, _e, _r, _i, _s, params):
        _nombre, _antes, ahora = params.unpack()
        if ahora:
            self._aparece_bluez()
        else:
            log("BlueZ se ha ido")
            self.presente = False
            self.objetos = {}
            self._parar_ronda()

    def _al_anadir(self, _c, _e, _r, _i, _s, params):
        ruta, ifaces = params.unpack()
        util = {i: dict(p) for i, p in ifaces.items()
                if i in (ADAPTADOR, DISPOSITIVO)}
        if util:
            self.objetos.setdefault(ruta, {}).update(util)
            self._pedir_reconciliar()

    def _al_quitar(self, _c, _e, _r, _i, _s, params):
        ruta, ifaces = params.unpack()
        if ruta in self.objetos:
            for i in ifaces:
                self.objetos[ruta].pop(i, None)
            if not self.objetos[ruta]:
                del self.objetos[ruta]
            self._pedir_reconciliar()

    def _al_cambiar(self, _c, _e, ruta, _i, _s, params):
        interfaz, cambios, _invalidadas = params.unpack()
        if interfaz not in (ADAPTADOR, DISPOSITIVO) or ruta not in self.objetos:
            return
        props = self.objetos[ruta].setdefault(interfaz, {})
        props.update(cambios)
        # Recien emparejado mientras escuchabamos: merece una ronda ya.
        if interfaz == DISPOSITIVO and cambios.get("Paired") is True:
            self._despertar()
        self._pedir_reconciliar()

    def _al_desconectar(self, _c, _e, ruta, _i, _s, params):
        razon = params.unpack()[0]
        props = self.objetos.get(ruta, {}).get(DISPOSITIVO, {})
        mac = str(props.get("Address", "")).upper()
        if not mac:
            return
        echado = time.monotonic() - self._echados.get(mac, -1e9) < MARGEN_ECHADO
        llevaba = time.monotonic() - self._activo_desde
        if (razon == RAZON_LOCAL and not echado and mac == self._ultimo_activo
                and llevaba >= MINIMO_EN_USO):
            self.recuerdo.soltados.add(mac)
            self.recuerdo.guardar()
            log("%s soltado a mano: no lo vuelvo a llamar hasta que apagues y "
                "enciendas el Bluetooth" % self._nombre(mac))
        else:
            log("%s desconectado (%s)" % (self._nombre(mac), razon.rsplit(".", 1)[-1]))

    # --- Decidir y aplicar ----------------------------------------------------

    def _pedir_reconciliar(self):
        # Las senales llegan en rafagas (conectar un auricular son una docena de
        # cambios de propiedad). Se juntan en una sola pasada.
        if not self._pendiente:
            self._pendiente = True
            self.GLib.idle_add(self._reconciliar)

    def _reconciliar(self):
        self._pendiente = False
        if not self.presente:
            return False

        encendido = hay_adaptador_encendido(self.objetos)
        if encendido and self._encendido is False:
            # Apagar y encender es la forma de decir «empieza de cero».
            if self.recuerdo.soltados:
                log("Bluetooth encendido: olvido los soltados a mano")
            self.recuerdo.soltados.clear()
            self.recuerdo.guardar()
            self._despertar()
        self._encendido = encendido

        aparatos = leer_aparatos(self.objetos)
        plan = decidir(aparatos, self.recuerdo)

        antes = self.recuerdo.activo
        if plan.activo != antes:
            self.recuerdo.activo = plan.activo
            if plan.activo:
                self._activo_desde = time.monotonic()
                self._ultimo_activo = plan.activo
                self.recuerdo.ultimo_uso[plan.activo] = time.time()
                self.recuerdo.soltados.discard(plan.activo)
                self.recuerdo.guardar()
                log("en uso: %s" % self._nombre(plan.activo))
            elif encendido:
                log("ningun auricular en uso")
                self._despertar()

        for mac in plan.echar:
            self._echar(mac, plan.activo)
        for mac in plan.bloquear:
            self._poner_blocked(mac, True)
        for mac in plan.desbloquear:
            self._poner_blocked(mac, False)

        if plan.activo or not plan.candidatos:
            self._parar_ronda()
        elif not (self._temporizador or self._cola or self._conectando):
            self._programar(self._espera)
        return False

    def _poner_blocked(self, mac, valor):
        ruta = self._ruta(mac)
        if ruta is None or (mac, valor) in self._en_vuelo:
            return
        if valor:
            # Se apunta ANTES de pedirlo: si el demonio muere entre medias, que
            # sobre un nombre en la lista (desbloquear uno que no lo esta no
            # hace nada) y no que falte uno bloqueado de verdad.
            self.recuerdo.bloqueados.add(mac)
            self.recuerdo.guardar()
            log("bloqueo %s mientras uses %s" % (
                self._nombre(mac), self._nombre(self.recuerdo.activo)))
        self._en_vuelo.add((mac, valor))

        def hecho(bus, resultado, _datos=None):
            self._en_vuelo.discard((mac, valor))
            try:
                bus.call_finish(resultado)
            except self.GLib.Error as e:
                log("no pude %s %s: %s" % ("bloquear" if valor else "desbloquear",
                                            self._nombre(mac), e.message))
                return
            # La foto se corrige ya, sin esperar a la senal: si no, durante un
            # instante el desbloqueado pareceria «bloqueado por ti» y la ronda
            # se lo saltaria.
            props = self.objetos.get(ruta, {}).get(DISPOSITIVO)
            if props is not None:
                props["Blocked"] = valor
            if not valor:
                self.recuerdo.bloqueados.discard(mac)
                self.recuerdo.guardar()
            self._pedir_reconciliar()

        self.bus.call(BLUEZ, ruta, PROPIEDADES, "Set", _variante_blocked(valor),
                      None, self.Gio.DBusCallFlags.NONE, PLAZO_LLAMADA_MS, None,
                      hecho, None)

    def _echar(self, mac, activo):
        ruta = self._ruta(mac)
        if ruta is None:
            return
        # Mientras la desconexion no se complete, cada pasada lo vuelve a ver
        # conectado. Sin esto saldria un aviso por pasada.
        if time.monotonic() - self._echados.get(mac, -1e9) < REINTENTO_ECHAR:
            return
        # Si era la llamada que estabamos haciendo nosotros (se cruzo con otro
        # que entro por su cuenta), no hay nada que explicar.
        nuestro = mac == self._conectando
        self._echados[mac] = time.monotonic()
        log("echo a %s: %s ya esta en uso" % (self._nombre(mac), self._nombre(activo)))
        self._poner_blocked(mac, True)
        self.bus.call(BLUEZ, ruta, DISPOSITIVO, "Disconnect", None, None,
                      self.Gio.DBusCallFlags.NONE, PLAZO_LLAMADA_MS, None,
                      None, None)
        if not nuestro:
            avisar("No se conecto %s" % self._nombre(mac),
                   "Ya estas usando %s. Desconectalo primero: clic central en el "
                   "Bluetooth de la barra." % self._nombre(activo))

    # --- Las rondas de llamadas -----------------------------------------------

    def _despertar(self):
        """Algo cambio (encendido, se fue el que estaba en uso, uno nuevo): la
        proxima ronda va casi en el acto y el ritmo vuelve a empezar."""
        self._espera = ESPERA_MIN
        if self._temporizador:
            self.GLib.source_remove(self._temporizador)
            self._temporizador = None
        if not (self._cola or self._conectando):
            self._programar(ESPERA_PRIMERA)

    def _programar(self, segundos):
        if self._temporizador:
            self.GLib.source_remove(self._temporizador)
        self._temporizador = self.GLib.timeout_add(int(segundos * 1000), self._ronda)

    def _parar_ronda(self):
        if self._temporizador:
            self.GLib.source_remove(self._temporizador)
            self._temporizador = None
        self._cola = []

    def _ronda(self):
        self._temporizador = None
        if not self.presente:
            return False
        plan = decidir(leer_aparatos(self.objetos), self.recuerdo)
        if plan.activo or not plan.candidatos:
            return False
        self._cola = list(plan.candidatos)
        self._llamar_siguiente()
        return False

    def _llamar_siguiente(self):
        plan = decidir(leer_aparatos(self.objetos), self.recuerdo)
        if plan.activo or not plan.candidatos or not self.presente:
            # Ya hay uno, o no queda a quien llamar (apagaste el Bluetooth a
            # media ronda). Cuando vuelva a haberlo, la reconciliacion programa.
            self._cola = []
            return
        # Lo que dejo de ser candidato a media ronda (lo soltaste, lo bloqueaste
        # tu, se desemparejo) se salta.
        while self._cola and (self._cola[0] not in plan.candidatos
                              or self._ruta(self._cola[0]) is None):
            self._cola.pop(0)
        if not self._cola:
            # Nadie contesto. La siguiente, mas tarde.
            self._programar(self._espera)
            self._espera = min(self._espera * 2, ESPERA_MAX)
            return
        mac = self._cola.pop(0)
        ruta = self._ruta(mac)
        self._conectando = mac

        def hecho(bus, resultado, _datos=None):
            self._conectando = None
            try:
                bus.call_finish(resultado)
            except self.GLib.Error as e:
                # Apagado, en el estuche o fuera de alcance: lo normal.
                motivo = e.message.rsplit(":", 1)[-1].strip()
                log("%s no contesta (%s)" % (self._nombre(mac), motivo))
                self._llamar_siguiente()
                return
            log("conectado %s" % self._nombre(mac))
            self._espera = ESPERA_MIN
            self._cola = []
            self._pedir_reconciliar()

        self.bus.call(BLUEZ, ruta, DISPOSITIVO, "Connect", None, None,
                      self.Gio.DBusCallFlags.NONE, PLAZO_CONECTAR_MS, None,
                      hecho, None)

    # --- Salir ----------------------------------------------------------------

    def liberar(self):
        """Al salir no se deja a nadie bloqueado: sin demonio no hay cerrojo, y
        un auricular bloqueado sin nadie que lo suelte parece averiado."""
        if not self.presente:
            return
        for mac in sorted(self.recuerdo.bloqueados):
            ruta = self._ruta(mac)
            if ruta is None:
                continue
            try:
                self.bus.call_sync(BLUEZ, ruta, PROPIEDADES, "Set",
                                   _variante_blocked(False), None, 0,
                                   PLAZO_LLAMADA_MS, None)
                self.recuerdo.bloqueados.discard(mac)
                log("desbloqueo %s al salir" % self._nombre(mac))
            except self.GLib.Error as e:
                log("no pude desbloquear %s al salir: %s" % (self._nombre(mac), e.message))
        self.recuerdo.guardar()

    # --- Utilidades -----------------------------------------------------------

    def _ruta(self, mac):
        for ruta, ifaces in self.objetos.items():
            p = ifaces.get(DISPOSITIVO)
            if p is not None and str(p.get("Address", "")).upper() == mac:
                return ruta
        return None

    def _nombre(self, mac):
        if not mac:
            return "(nadie)"
        ruta = self._ruta(mac)
        p = self.objetos.get(ruta, {}).get(DISPOSITIVO, {}) if ruta else {}
        return str(p.get("Alias") or p.get("Name") or mac)


def demonio():
    _, GLib = _gio()
    try:
        bus = bus_del_sistema()
    except GLib.Error as e:
        log("no hay bus del sistema: %s" % e.message)
        return 1
    d = Demonio(bus)
    bucle = GLib.MainLoop()

    def salir(*_):
        d.liberar()
        bucle.quit()
        return False

    # GLib.unix_signal_add esta obsoleto desde GLib 2.80 y lo dice por stderr
    # en cada arranque; el sustituto vive en GLibUnix. Quien tenga un GLib mas
    # viejo no tiene GLibUnix, y ahi el de siempre sigue valiendo.
    try:
        import gi
        gi.require_version("GLibUnix", "2.0")
        from gi.repository import GLibUnix
        anadir_senal = GLibUnix.signal_add
    except (ImportError, ValueError):
        anadir_senal = GLib.unix_signal_add
    anadir_senal(GLib.PRIORITY_HIGH, signal.SIGTERM, salir)
    anadir_senal(GLib.PRIORITY_HIGH, signal.SIGINT, salir)

    # Sin bus no hay nada que vigilar. Se sale con error para que systemd lo
    # levante cuando vuelva (Restart=on-failure en autostart.conf). El codigo va
    # por una variable: un sys.exit() dentro de un callback de GLib no sale del
    # proceso, PyGObject se lo traga y lo imprime.
    salida = {"codigo": 0}

    def bus_cerrado(*_):
        log("se cerro el bus del sistema")
        salida["codigo"] = 1
        bucle.quit()

    bus.connect("closed", bus_cerrado)
    d.arrancar()
    bucle.run()
    return salida["codigo"]


# ─────────────────────────────────────────────────────────────────────────────
# Las ordenes sueltas
# ─────────────────────────────────────────────────────────────────────────────

def _abrir():
    """El bus y la foto, o un mensaje de por que no."""
    _, GLib = _gio()
    try:
        bus = bus_del_sistema()
        if not bluez_presente(bus):
            return None, None, ("BlueZ no esta corriendo. Si hay Bluetooth en este "
                                "equipo: sudo systemctl enable --now bluetooth")
        return bus, foto(bus), None
    except GLib.Error as e:
        return None, None, "no pude hablar con BlueZ: %s" % e.message


def _demonio_vivo():
    r = subprocess.run(["systemctl", "--user", "is-active", "--quiet",
                        "celiuz-bluetooth"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    return r.returncode == 0


def _cuando(epoch):
    if not epoch:
        return "nunca"
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(epoch))


def ver():
    bus, objetos, error = _abrir()
    if error:
        print(error)
        return 1
    recuerdo = Recuerdo.cargar()
    adaptadores = [(r, i[ADAPTADOR]) for r, i in objetos.items() if ADAPTADOR in i]
    if not adaptadores:
        print("No hay ningun adaptador Bluetooth.")
        return 0
    for ruta, p in adaptadores:
        print("Bluetooth %s (%s): %s" % (
            p.get("Alias", ""), ruta.rsplit("/", 1)[-1],
            "encendido" if p.get("Powered") else "APAGADO"))
    print("Demonio: %s" % ("en marcha" if _demonio_vivo() else
                           "PARADO (lo lanza autostart.conf al entrar en la sesion)"))

    aparatos = leer_aparatos(objetos)
    auriculares = [a for a in aparatos if a.audio and a.emparejado]
    plan = decidir(aparatos, recuerdo)
    print()
    if not auriculares:
        print("No hay auriculares emparejados. Se emparejan con bluetui "
              "(clic en el Bluetooth de la barra).")
    else:
        print("Auriculares, en el orden en que se prueban:")
        for a in por_preferencia(auriculares, recuerdo):
            if a.conectado and a.mac == plan.activo:
                estado = "EN USO"
            elif a.conectado:
                estado = "conectado DE SOBRA (el cerrojo lo echara)"
            elif bloqueado_por_ti(a, recuerdo):
                estado = "bloqueado por ti: no se toca ni se prueba"
            elif a.bloqueado:
                estado = "bloqueado por el cerrojo mientras uses otro"
            elif a.mac in recuerdo.soltados:
                estado = "soltado a mano: no se llama hasta apagar y encender"
            else:
                estado = "esperando"
            print("  %s %-18s %s  usado: %-16s  %s" % (
                "●" if a.conectado else "○", a.nombre, a.mac,
                _cuando(recuerdo.ultimo_uso.get(a.mac)), estado))
    otros = [a.nombre for a in aparatos if a.emparejado and not a.audio]
    if otros:
        print("\nOtros emparejados (no son de audio, no se tocan): %s" % ", ".join(otros))
    return 0


def conectar():
    """Conecta ya, sin esperar a la siguiente ronda del demonio. Prueba tambien
    los soltados a mano: si lo pides tu, es que lo quieres."""
    _, GLib = _gio()
    bus, objetos, error = _abrir()
    if error:
        print(error, file=sys.stderr)
        return 1
    if not hay_adaptador_encendido(objetos):
        print("El Bluetooth esta apagado: bluetooth.py alternar", file=sys.stderr)
        return 1
    recuerdo = Recuerdo.cargar()
    aparatos = leer_aparatos(objetos)
    auriculares = [a for a in aparatos if a.audio and a.emparejado and a.encendido]
    en_uso = [a for a in auriculares if a.conectado]
    if en_uso:
        print("Ya estas usando %s." % en_uso[0].nombre)
        return 0
    for a in por_preferencia(auriculares, recuerdo):
        if bloqueado_por_ti(a, recuerdo):
            continue
        if a.bloqueado:
            # Del cerrojo, y no hay nadie en uso: sobra (el demonio parado lo
            # dejaria asi).
            bus.call_sync(BLUEZ, a.ruta, PROPIEDADES, "Set", _variante_blocked(False),
                          None, 0, PLAZO_LLAMADA_MS, None)
            recuerdo.bloqueados.discard(a.mac)
            recuerdo.guardar()
        print("Llamando a %s..." % a.nombre, flush=True)
        try:
            bus.call_sync(BLUEZ, a.ruta, DISPOSITIVO, "Connect", None, None, 0,
                          PLAZO_CONECTAR_MS, None)
        except GLib.Error as e:
            print("  no contesta (%s)" % e.message.rsplit(":", 1)[-1].strip())
            continue
        print("Conectado: %s" % a.nombre)
        return 0
    print("No contesto ninguno. ¿Estan encendidos?", file=sys.stderr)
    return 1


def soltar():
    _, GLib = _gio()
    bus, objetos, error = _abrir()
    if error:
        print(error, file=sys.stderr)
        return 1
    en_uso = [a for a in leer_aparatos(objetos)
              if a.audio and a.emparejado and a.conectado]
    if not en_uso:
        print("No hay ningun auricular conectado.")
        return 0
    for a in en_uso:
        try:
            bus.call_sync(BLUEZ, a.ruta, DISPOSITIVO, "Disconnect", None, None, 0,
                          PLAZO_LLAMADA_MS, None)
            print("Soltado: %s. No se vuelve a conectar solo hasta que apagues y "
                  "enciendas el Bluetooth." % a.nombre)
        except GLib.Error as e:
            print("No pude soltar %s: %s" % (a.nombre, e.message), file=sys.stderr)
            return 1
    return 0


def _rfkill_bloqueado():
    """(blando, duro) del Bluetooth, leido de /sys: es la fuente, y no hace
    falta ningun programa para mirarlo."""
    blando = duro = False
    base = "/sys/class/rfkill"
    try:
        nombres = os.listdir(base)
    except OSError:
        return False, False
    for n in nombres:
        try:
            with open(os.path.join(base, n, "type")) as f:
                if f.read().strip() != "bluetooth":
                    continue
            with open(os.path.join(base, n, "soft")) as f:
                blando |= f.read().strip() == "1"
            with open(os.path.join(base, n, "hard")) as f:
                duro |= f.read().strip() == "1"
        except OSError:
            continue
    return blando, duro


def alternar():
    _, GLib = _gio()
    blando, duro = _rfkill_bloqueado()
    if duro:
        avisar("Bluetooth bloqueado", "Lo tiene apagado el interruptor o la tecla "
               "de modo avion. Desde aqui no se puede encender.")
        return 1
    if blando:
        # En esta sesion /dev/rfkill es tuyo (lo da systemd-logind), asi que no
        # hace falta sudo. Pasa al tocar la tecla de modo avion del portatil.
        subprocess.run(["rfkill", "unblock", "bluetooth"])
        # BlueZ tarda un momento en ver el adaptador otra vez.
        time.sleep(1)
    bus, objetos, error = _abrir()
    if error:
        avisar("Bluetooth", error)
        return 1
    adaptadores = [r for r, i in objetos.items() if ADAPTADOR in i]
    if not adaptadores:
        avisar("Bluetooth", "No hay ningun adaptador Bluetooth.")
        return 1
    encender = blando or not hay_adaptador_encendido(objetos)
    for ruta in adaptadores:
        try:
            bus.call_sync(BLUEZ, ruta, PROPIEDADES, "Set",
                          GLib.Variant("(ssv)", (ADAPTADOR, "Powered",
                                                 GLib.Variant("b", encender))),
                          None, 0, PLAZO_LLAMADA_MS, None)
        except GLib.Error as e:
            avisar("No pude %s el Bluetooth" % ("encender" if encender else "apagar"),
                   e.message)
            return 1
    return 0


ORDENES = {
    "--demonio": demonio,
    "--ver": ver,
    "conectar": conectar,
    "soltar": soltar,
    "alternar": alternar,
}


def main(argv):
    if len(argv) != 1 or argv[0] not in ORDENES:
        print(__doc__.split("USO\n---\n", 1)[-1].rstrip(), file=sys.stderr)
        return 2
    return ORDENES[argv[0]]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
