#!/usr/bin/env python3
"""
tests/lib/nm_falso.py — un NetworkManager de mentira para probar la conexion a
una red NUEVA de hypr/scripts/wifi-panel.py (ConexionNueva).

    nm_falso.py servir      se queda sirviendo org.freedesktop.NetworkManager
    nm_falso.py estado      le pide lo que ha visto, en JSON

SOLO EN UN BUS PRIVADO, como tests/lib/bluez_falso.py: coge el nombre en el bus
«del sistema» que diga DBUS_SYSTEM_BUS_ADDRESS, y en el de verdad no podria
(ya lo tiene NetworkManager).

Imita lo que usa el panel, en el orden del real:
  - GetDeviceByIpIface("wlan0") -> la ruta del dispositivo.
  - AddAndActivateConnection2(ajustes, dispositivo, "/", opciones) -> (perfil,
    activa, {}). La activa empieza en 1 (activando) y a los 300 ms pasa a 2
    (activada) si la contraseña es «buena-clave» o la red es abierta, y si no a
    4 (desactivada), con StateReason del dispositivo = (120, 7): NO_SECRETS, lo
    que da el real con una contraseña mala.
  - Settings.Connection.Save / Delete sobre el perfil.
  - Properties.Get de State (la activa) y de StateReason (el dispositivo).
"""

import json
import sys
import threading

import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

NM = "org.freedesktop.NetworkManager"
RUTA = "/org/freedesktop/NetworkManager"
DISPOSITIVO = RUTA + "/Devices/3"
PERFIL = RUTA + "/Settings/9"
ACTIVA = RUTA + "/ActiveConnection/5"
BUENA = "buena-clave"

XML = """
<node>
  <interface name="org.freedesktop.NetworkManager">
    <method name="GetDeviceByIpIface">
      <arg type="s" direction="in"/><arg type="o" direction="out"/>
    </method>
    <method name="AddAndActivateConnection2">
      <arg type="a{sa{sv}}" direction="in"/><arg type="o" direction="in"/>
      <arg type="o" direction="in"/><arg type="a{sv}" direction="in"/>
      <arg type="o" direction="out"/><arg type="o" direction="out"/>
      <arg type="a{sv}" direction="out"/>
    </method>
    <method name="DeactivateConnection">
      <arg type="o" direction="in"/>
    </method>
  </interface>
  <interface name="org.freedesktop.NetworkManager.Connection.Active">
    <signal name="StateChanged">
      <arg type="u"/><arg type="u"/>
    </signal>
    <property name="State" type="u" access="read"/>
  </interface>
  <interface name="org.freedesktop.NetworkManager.Device">
    <property name="StateReason" type="(uu)" access="read"/>
  </interface>
  <interface name="org.freedesktop.NetworkManager.Settings.Connection">
    <method name="Save"/>
    <method name="Delete"/>
  </interface>
  <interface name="org.celiuz.Prueba">
    <method name="Estado">
      <arg type="s" direction="out"/>
    </method>
  </interface>
</node>
"""


def _plano(v):
    """Una variante a algo que json entiende (los bytes del SSID, a texto)."""
    if isinstance(v, (bytes, bytearray)):
        return bytes(v).decode(errors="replace")
    if isinstance(v, list) and v and all(isinstance(x, int) for x in v):
        return bytes(v).decode(errors="replace")
    if isinstance(v, dict):
        return {k: _plano(x) for k, x in v.items()}
    return v


class Falso:
    def __init__(self, c):
        self.c = c
        self.info = Gio.DBusNodeInfo.new_for_xml(XML)
        self.estado_activa = 0
        self.razon = (100, 0)
        self.vistos = {"ajustes": None, "opciones": None, "guardado": 0, "borrado": 0,
                       "desactivado": 0, "dispositivo_pedido": None}
        for ruta, interfaz in ((RUTA, NM), (DISPOSITIVO, NM + ".Device"),
                               ("/prueba", "org.celiuz.Prueba")):
            self._registrar(ruta, interfaz)

    def _registrar(self, ruta, interfaz):
        registrar = getattr(self.c, "register_object_with_closures2", self.c.register_object)
        registrar(ruta, self.info.lookup_interface(interfaz), self._llamada, None, None)

    def _llamada(self, _c, _e, ruta, interfaz, metodo, params, inv):
        try:
            if interfaz == "org.freedesktop.DBus.Properties" and metodo == "Get":
                _i, nombre = params.unpack()
                if nombre == "State":
                    return inv.return_value(GLib.Variant("(v)", (GLib.Variant("u", self.estado_activa),)))
                if nombre == "StateReason":
                    return inv.return_value(GLib.Variant("(v)", (GLib.Variant("(uu)", self.razon),)))
            if metodo == "GetDeviceByIpIface":
                self.vistos["dispositivo_pedido"] = params.unpack()[0]
                return inv.return_value(GLib.Variant("(o)", (DISPOSITIVO,)))
            if metodo == "AddAndActivateConnection2":
                return self._activar(params, inv)
            if metodo == "DeactivateConnection":
                self.vistos["desactivado"] += 1
                return inv.return_value(None)
            if metodo == "Save":
                self.vistos["guardado"] += 1
                return inv.return_value(None)
            if metodo == "Delete":
                self.vistos["borrado"] += 1
                return inv.return_value(None)
            if metodo == "Estado":
                return inv.return_value(GLib.Variant("(s)", (json.dumps(self.vistos),)))
        except Exception as e:  # noqa: BLE001
            return inv.return_dbus_error("org.celiuz.Prueba.Error", repr(e))
        inv.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod", metodo)

    def _activar(self, params, inv):
        ajustes, _disp, _ap, opciones = params.unpack()
        self.vistos["ajustes"] = _plano(ajustes)
        self.vistos["opciones"] = _plano(opciones)
        if not getattr(self, "_registrados", False):
            for ruta, interfaz in ((PERFIL, NM + ".Settings.Connection"),
                                   (ACTIVA, NM + ".Connection.Active")):
                self._registrar(ruta, interfaz)
            self._registrados = True
        self.estado_activa = 1
        self.razon = (100, 0)
        seg = ajustes.get("802-11-wireless-security", {})
        bien = not seg or seg.get("psk") == BUENA
        inv.return_value(GLib.Variant("(ooa{sv})", (PERFIL, ACTIVA, {})))

        def acabar():
            self.estado_activa = 2 if bien else 4
            if not bien:
                self.razon = (120, 7)
            self.c.emit_signal(None, ACTIVA, NM + ".Connection.Active", "StateChanged",
                               GLib.Variant("(uu)", (self.estado_activa, 0 if bien else 3)))
            return False
        GLib.timeout_add(300, acabar)


def servir():
    c = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    Falso(c)
    bucle = GLib.MainLoop()
    listo = threading.Event()

    def conseguido(*_):
        print("listo", flush=True)
        listo.set()

    def perdido(*_):
        print("no pude coger el nombre: ¿es el bus de verdad?", file=sys.stderr, flush=True)
        bucle.quit()
    Gio.bus_own_name_on_connection(c, NM, Gio.BusNameOwnerFlags.DO_NOT_QUEUE,
                                   conseguido, perdido)
    bucle.run()
    return 0 if listo.is_set() else 1


def estado():
    c = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    r = c.call_sync(NM, "/prueba", "org.celiuz.Prueba", "Estado", None, None,
                    Gio.DBusCallFlags.NONE, 5000, None)
    print(r.unpack()[0])
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["servir"]:
        sys.exit(servir())
    if sys.argv[1:] == ["estado"]:
        sys.exit(estado())
    print(__doc__, file=sys.stderr)
    sys.exit(2)
