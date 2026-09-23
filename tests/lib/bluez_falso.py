#!/usr/bin/env python3
"""
tests/lib/bluez_falso.py — un BlueZ de mentira para probar hypr/scripts/bluetooth.py.

    bluez_falso.py servir <aparatos.json> [--sin-adaptador]
                                              se queda sirviendo org.bluez
    bluez_falso.py <orden> [argumentos...]    le habla al que esta sirviendo

SOLO EN UN BUS PRIVADO. Coge el nombre org.bluez en el bus «del sistema» que
diga DBUS_SYSTEM_BUS_ADDRESS, y la prueba lo apunta a un bus de
`dbus-run-session`. Si ese bus fuera el de verdad no podria ni arrancar: el
nombre ya lo tiene el bluetoothd real, y aqui se pide sin reemplazar a nadie.

Imita lo que bluetooth.py usa de BlueZ, con el comportamiento MEDIDO del de
verdad donde importa:

  - GetManagedObjects, InterfacesAdded, PropertiesChanged.
  - Device1.Connect: si el aparato esta apagado, falla con
    `br-connection-page-timeout` (lo que da el real). Y NO MIRA `Blocked`:
    el 2026-09-21 se comprobo que el BlueZ real se pone a buscar un aparato
    bloqueado igual, asi que el falso se pone en el peor caso y lo conecta.
  - Device1.Disconnect y la senal `Disconnected(motivo, mensaje)`.
  - Blocked=true sobre uno conectado lo desconecta, como el real.
  - Apagar el adaptador desconecta a todos con motivo `Local`.

Y lo que el real no tiene, para mover los hilos desde la prueba (interfaz
org.celiuz.Prueba en /prueba):

  Encender(mac, si/no, motivo)  el auricular se enciende o se apaga; si se apaga
                                conectado, se despide con ese motivo
  Entrante(mac) -> b            el auricular llama por su cuenta: lo rechaza si
                                esta bloqueado, apagado o sin adaptador
  Estado() -> s                 todo, en JSON, con la lista de llamadas a Connect
"""

import json
import sys
import threading

import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

BLUEZ = "org.bluez"
DISPOSITIVO = "org.bluez.Device1"
ADAPTADOR = "org.bluez.Adapter1"
PROPIEDADES = "org.freedesktop.DBus.Properties"
OBJETOS = "org.freedesktop.DBus.ObjectManager"
CONTROL = "org.celiuz.Prueba"
ADAPTADOR_RUTA = "/org/bluez/hci0"

XML = """
<node>
  <interface name="org.freedesktop.DBus.ObjectManager">
    <method name="GetManagedObjects">
      <arg type="a{oa{sa{sv}}}" direction="out"/>
    </method>
    <signal name="InterfacesAdded">
      <arg type="o"/><arg type="a{sa{sv}}"/>
    </signal>
  </interface>
  <interface name="org.bluez.Adapter1">
    <property name="Powered" type="b" access="readwrite"/>
    <property name="Address" type="s" access="read"/>
    <property name="Alias" type="s" access="read"/>
  </interface>
  <interface name="org.bluez.Device1">
    <method name="Connect"/>
    <method name="Disconnect"/>
    <signal name="Disconnected">
      <arg type="s"/><arg type="s"/>
    </signal>
    <property name="Address" type="s" access="read"/>
    <property name="Alias" type="s" access="read"/>
    <property name="Name" type="s" access="read"/>
    <property name="Icon" type="s" access="read"/>
    <property name="UUIDs" type="as" access="read"/>
    <property name="Paired" type="b" access="read"/>
    <property name="Trusted" type="b" access="read"/>
    <property name="Blocked" type="b" access="readwrite"/>
    <property name="Connected" type="b" access="read"/>
    <property name="Adapter" type="o" access="read"/>
  </interface>
  <interface name="org.celiuz.Prueba">
    <method name="Encender">
      <arg type="s" direction="in"/><arg type="b" direction="in"/>
      <arg type="s" direction="in"/>
    </method>
    <method name="Entrante">
      <arg type="s" direction="in"/><arg type="b" direction="out"/>
    </method>
    <method name="Estado">
      <arg type="s" direction="out"/>
    </method>
  </interface>
</node>
"""

FIRMAS = {
    "Address": "s", "Alias": "s", "Name": "s", "Icon": "s", "UUIDs": "as",
    "Paired": "b", "Trusted": "b", "Blocked": "b", "Connected": "b",
    "Adapter": "o", "Powered": "b",
}

# Lo que tarda el falso en «buscar»: poco, para que la prueba vaya rapida, pero
# no cero, para que las respuestas lleguen de verdad por el bucle y no pegadas.
DEMORA_MS = 300


def ruta_de(mac):
    return ADAPTADOR_RUTA + "/dev_" + mac.replace(":", "_")


class Falso:
    def __init__(self, conexion, aparatos, con_adaptador=True):
        self.c = conexion
        self.info = Gio.DBusNodeInfo.new_for_xml(XML)
        # Sin adaptador se imita a un sobremesa sin Bluetooth: BlueZ corriendo
        # pero sin ninguna radio. El demonio tiene que quedarse quieto.
        self.con_adaptador = con_adaptador
        self.adaptador = {"Powered": True, "Address": "00:00:00:00:00:00",
                          "Alias": "falso"}
        self.aparatos = {}      # ruta -> props de Device1
        self.encendidos = {}    # ruta -> el auricular esta encendido
        self.llamadas = []      # macs a las que se llamo con Connect, en orden
        for a in aparatos:
            ruta = ruta_de(a["mac"])
            self.aparatos[ruta] = {
                "Address": a["mac"], "Alias": a["nombre"], "Name": a["nombre"],
                "Icon": a.get("icono", "audio-headset"),
                "UUIDs": a.get("uuids", []),
                "Paired": a.get("emparejado", True),
                "Trusted": a.get("emparejado", True),
                "Blocked": a.get("bloqueado", False),
                "Connected": a.get("conectado", False),
                "Adapter": ADAPTADOR_RUTA,
            }
            self.encendidos[ruta] = a.get("encendido", False)

        # Las llamadas a Properties.Get/Set van al method_call porque no se da
        # manejador de propiedades (asi lo hace GDBus con NULL).
        self._registrar("/", OBJETOS)
        self._registrar("/prueba", CONTROL)
        if con_adaptador:
            self._registrar(ADAPTADOR_RUTA, ADAPTADOR)
        for ruta in self.aparatos:
            self._registrar(ruta, DISPOSITIVO)

    def _registrar(self, ruta, interfaz):
        # register_object esta obsoleto desde GLib 2.84 y avisa por stderr; la
        # prueba exige un stderr limpio, asi que se usa el nuevo si lo hay.
        registrar = getattr(self.c, "register_object_with_closures2",
                            self.c.register_object)
        registrar(ruta, self.info.lookup_interface(interfaz),
                  self._llamada, None, None)

    # --- Senales --------------------------------------------------------------

    def _cambiar(self, ruta, interfaz, props, **cambios):
        props.update(cambios)
        variantes = {k: GLib.Variant(FIRMAS[k], v) for k, v in cambios.items()}
        self.c.emit_signal(None, ruta, PROPIEDADES, "PropertiesChanged",
                           GLib.Variant("(sa{sv}as)", (interfaz, variantes, [])))

    def _desconectar(self, ruta, motivo):
        p = self.aparatos[ruta]
        if not p["Connected"]:
            return
        # Primero la senal con el motivo y despues la propiedad: el orden del
        # real no esta garantizado, y bluetooth.py no debe depender de el.
        self.c.emit_signal(None, ruta, DISPOSITIVO, "Disconnected",
                           GLib.Variant("(ss)", (motivo, "")))
        self._cambiar(ruta, DISPOSITIVO, p, Connected=False)

    def _conectar(self, ruta):
        self._cambiar(ruta, DISPOSITIVO, self.aparatos[ruta], Connected=True)

    # --- Metodos --------------------------------------------------------------

    def _llamada(self, _c, _emisor, ruta, interfaz, metodo, params, invocacion):
        try:
            if interfaz == PROPIEDADES:
                return self._propiedades(ruta, metodo, params, invocacion)
            if interfaz == OBJETOS and metodo == "GetManagedObjects":
                return invocacion.return_value(
                    GLib.Variant("(a{oa{sa{sv}}})", (self._todo(),)))
            if interfaz == DISPOSITIVO:
                return self._dispositivo(ruta, metodo, invocacion)
            if interfaz == CONTROL:
                return self._control(metodo, params, invocacion)
        except Exception as e:  # noqa: BLE001 — que la prueba lo vea, no que cuelgue
            invocacion.return_dbus_error("org.celiuz.Prueba.Error", repr(e))
            return
        invocacion.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod",
                                     metodo)

    def _todo(self):
        def v(props):
            return {k: GLib.Variant(FIRMAS[k], x) for k, x in props.items()}
        todo = {ADAPTADOR_RUTA: {ADAPTADOR: v(self.adaptador)}} if self.con_adaptador else {}
        for ruta, props in self.aparatos.items():
            todo[ruta] = {DISPOSITIVO: v(props)}
        return todo

    def _propiedades(self, ruta, metodo, params, invocacion):
        if metodo != "Set":
            invocacion.return_dbus_error("org.freedesktop.DBus.Error.NotSupported",
                                         "el falso solo sabe Set")
            return
        interfaz, nombre, valor = params.unpack()
        if interfaz == ADAPTADOR and nombre == "Powered":
            if not valor:
                for r in self.aparatos:
                    self._desconectar(r, "org.bluez.Reason.Local")
            self._cambiar(ruta, ADAPTADOR, self.adaptador, Powered=bool(valor))
        elif interfaz == DISPOSITIVO and nombre == "Blocked" and ruta in self.aparatos:
            # En este orden, como el real: `Blocked` cambia en el acto y la
            # desconexion llega DESPUES (device_block pide el corte a la radio y
            # sigue). Durante ese rato el aparato se ve bloqueado y conectado a
            # la vez, y es justo el rato en que bluetooth.py podria echarlo dos
            # veces.
            self._cambiar(ruta, DISPOSITIVO, self.aparatos[ruta], Blocked=bool(valor))
            if valor:
                GLib.timeout_add(DEMORA_MS, lambda: self._desconectar(
                    ruta, "org.bluez.Reason.Local") or False)
        else:
            invocacion.return_dbus_error("org.bluez.Error.InvalidArguments", nombre)
            return
        invocacion.return_value(None)

    def _dispositivo(self, ruta, metodo, invocacion):
        p = self.aparatos[ruta]
        if metodo == "Disconnect":
            # El real contesta cuando el corte se ha completado, no antes.
            def cortar():
                self._desconectar(ruta, "org.bluez.Reason.Local")
                invocacion.return_value(None)
                return False
            GLib.timeout_add(DEMORA_MS // 3, cortar)
            return
        if metodo != "Connect":
            invocacion.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod",
                                         metodo)
            return
        self.llamadas.append(p["Address"])
        if not self.adaptador["Powered"]:
            invocacion.return_dbus_error("org.bluez.Error.NotReady", "Resource Not Ready")
            return

        def responder():
            if p["Connected"]:
                invocacion.return_dbus_error("org.bluez.Error.AlreadyConnected",
                                             "br-connection-already-connected")
            elif self.encendidos[ruta] and self.adaptador["Powered"]:
                self._conectar(ruta)
                invocacion.return_value(None)
            else:
                invocacion.return_dbus_error("org.bluez.Error.Failed",
                                             "br-connection-page-timeout")
            return False

        GLib.timeout_add(DEMORA_MS, responder)

    def _control(self, metodo, params, invocacion):
        if metodo == "Estado":
            estado = {
                "powered": self.adaptador["Powered"],
                "llamadas": self.llamadas,
                "aparatos": {p["Address"]: dict(p) for p in self.aparatos.values()},
            }
            invocacion.return_value(GLib.Variant("(s)", (json.dumps(estado),)))
            return
        if metodo == "Encender":
            mac, encendido, motivo = params.unpack()
            ruta = ruta_de(mac)
            self.encendidos[ruta] = encendido
            if not encendido:
                self._desconectar(ruta, motivo)
            invocacion.return_value(None)
            return
        if metodo == "Entrante":
            (mac,) = params.unpack()
            ruta = ruta_de(mac)
            p = self.aparatos[ruta]
            acepta = (self.adaptador["Powered"] and self.encendidos[ruta]
                      and p["Paired"] and not p["Blocked"] and not p["Connected"])
            if acepta:
                self._conectar(ruta)
            invocacion.return_value(GLib.Variant("(b)", (acepta,)))
            return
        invocacion.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod", metodo)


def servir(fichero, con_adaptador=True):
    with open(fichero, encoding="utf-8") as f:
        aparatos = json.load(f)
    conexion = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    Falso(conexion, aparatos, con_adaptador)
    bucle = GLib.MainLoop()
    listo = threading.Event()

    def conseguido(*_):
        # La prueba espera a esta linea para empezar.
        print("listo", flush=True)
        listo.set()

    def perdido(*_):
        print("no pude coger org.bluez: ¿es el bus de verdad?", file=sys.stderr, flush=True)
        bucle.quit()

    Gio.bus_own_name_on_connection(conexion, BLUEZ,
                                   Gio.BusNameOwnerFlags.DO_NOT_QUEUE,
                                   conseguido, perdido)
    bucle.run()
    return 0 if listo.is_set() else 1


def orden(nombre, argumentos):
    conexion = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    tipos = {"Encender": "(sbs)", "Entrante": "(s)", "Estado": None}
    if nombre == "Encender":
        mac, encendido = argumentos[0], argumentos[1] == "si"
        motivo = argumentos[2] if len(argumentos) > 2 else "org.bluez.Reason.Remote"
        params = GLib.Variant(tipos[nombre], (mac, encendido, motivo))
        ruta, interfaz = "/prueba", CONTROL
    elif nombre == "Entrante":
        params = GLib.Variant("(s)", (argumentos[0],))
        ruta, interfaz = "/prueba", CONTROL
    elif nombre == "Estado":
        params = None
        ruta, interfaz = "/prueba", CONTROL
    elif nombre == "Connect":
        # Lo que haria bluetui: llamar a un aparato desde este lado.
        params = None
        ruta, interfaz = ruta_de(argumentos[0]), DISPOSITIVO
    else:
        print("orden desconocida: %s" % nombre, file=sys.stderr)
        return 2
    try:
        r = conexion.call_sync(BLUEZ, ruta, interfaz, nombre, params, None,
                               Gio.DBusCallFlags.NONE, 15000, None)
    except GLib.Error as e:
        print("error: %s" % e.message)
        return 1
    valores = r.unpack() if r is not None else ()
    for v in valores:
        print(json.dumps(v) if isinstance(v, bool) else v)
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "servir":
        sys.exit(servir(sys.argv[2], "--sin-adaptador" not in sys.argv))
    if len(sys.argv) >= 2:
        sys.exit(orden(sys.argv[1], sys.argv[2:]))
    print(__doc__, file=sys.stderr)
    sys.exit(2)
