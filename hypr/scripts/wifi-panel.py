#!/usr/bin/env python3
"""
hypr/scripts/wifi-panel.py

El menu de red que cuelga de la barra al hacer clic en su icono: el Wi-Fi y el
cable. Es la misma capa que el del Bluetooth (lib/panel_capa.py).

LO QUE ENSEÑA
-------------
  - CONECTADO: la red en uso, con su señal, banda, IP (todas: la secundaria de
    una oficina tambien) y la velocidad, y un boton para desconectar. Si la red
    pide iniciar sesion en una web (hotel, oficina), lo dice y la abre. El cable,
    si esta conectado, tambien sale aqui.
  - MIS REDES: las guardadas. Las que estan al alcance se conectan con un boton,
    y si alguna se oye bastante mejor que la actual, lo avisa. El «⋯» de cada
    una: «Compartir red» (un QR para el movil y la contraseña), si se conecta
    sola, y olvidarla. El cable sin enchufar sale aqui, para verlo de un vistazo.
  - OTRAS REDES: las de alrededor, con candado si piden contraseña; la
    contraseña se escribe ahi mismo. Las mas debiles van plegadas.
  - Abajo, el modo avion (wifi y Bluetooth a la vez, por rfkill) y «Ajustes
    avanzados», que abre nmtui para lo que esto no cubre: IP fija, la IP
    secundaria de la oficina, redes de empresa (802.1X), WEP, redes ocultas.

COMO HABLA CON NETWORKMANAGER
-----------------------------
Para leer y para casi todo lo demas, `nmcli` en modo terso (-t) y con LC_ALL=C:
es la interfaz estable, y en español sus palabras cambian.

Para conectar a una red NUEVA, D-Bus (AddAndActivateConnection2) y no
`nmcli device wifi connect SSID password XXX`: asi la contraseña viaja dentro de
la llamada y no queda a la vista en la lista de procesos (/proc/<pid>/cmdline
lo puede leer cualquier usuario del equipo). La red se crea SOLO EN MEMORIA
(persist=memory): si conecta, se guarda; si falla, se borra. Una contraseña mal
escrita no deja perfiles de basura.

Las contraseñas guardadas se leen con `nmcli -s` (NetworkManager se las da a
quien tiene la sesion abierta) solo al pulsar «Compartir red», y el QR se hace
con `qrencode` por la entrada estandar, por lo mismo.

USO
---
    wifi-panel.py           abre el panel (o lo cierra si ya esta abierto)
    wifi-panel.py --ver     lo que enseñaria, en texto, sin abrir nada
"""

import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field

RAIZ = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(RAIZ, "lib"))

from panel_estilo import _hex, css_base as css  # noqa: E402,F401  (las pruebas los usan)

MAX_OTRAS = 4          # las demas, plegadas
MEJOR_POR = 20         # puntos de señal por encima de la actual para avisar
PLAZO_NMCLI = 20
PLAZO_CONECTAR = 45
REFRESCO_MS = 4000

NM = "org.freedesktop.NetworkManager"
NM_RUTA = "/org/freedesktop/NetworkManager"
NM_ACTIVA = "org.freedesktop.NetworkManager.Connection.Active"
NM_PERFIL = "org.freedesktop.NetworkManager.Settings.Connection"
NM_DISPOSITIVO = "org.freedesktop.NetworkManager.Device"

G_WIFI = "\U000F05A9"
G_WIFI_OFF = "\U000F05AA"
G_SENAL = ["\U000F092F", "\U000F091F", "\U000F0922", "\U000F0925", "\U000F0928"]
G_CABLE = "\U000F0200"
G_CANDADO = "\U000F033E"
G_MAS = "\U000F01D8"
G_GIRO = "\U000F0450"
G_AJUSTES = "\U000F0493"
G_AVISO = "\U000F0026"
G_QR = "\U000F0432"
G_COPIAR = "\U000F018F"
G_OJO = "\U000F0208"
G_OJO_NO = "\U000F0209"
G_WEB = "\U000F059F"


# ─────────────────────────────────────────────────────────────────────────────
# Leer nmcli (sin GTK: es lo que prueba tests/unidad/wifi-panel.sh)
# ─────────────────────────────────────────────────────────────────────────────

def partir(linea):
    """Una linea de `nmcli -t`: campos separados por «:», con «\\:» y «\\\\»
    escapados (un SSID puede llevar dos puntos)."""
    campos, actual, i = [], [], 0
    while i < len(linea):
        c = linea[i]
        if c == "\\" and i + 1 < len(linea):
            actual.append(linea[i + 1])
            i += 2
            continue
        if c == ":":
            campos.append("".join(actual))
            actual = []
        else:
            actual.append(c)
        i += 1
    campos.append("".join(actual))
    return campos


def leer_dispositivos(texto):
    """DEVICE,TYPE,STATE,CONNECTION -> [{dev, tipo, estado, conexion}]."""
    salida = []
    for linea in texto.splitlines():
        c = partir(linea)
        if len(c) >= 4:
            salida.append({"dev": c[0], "tipo": c[1], "estado": c[2], "conexion": c[3]})
    return salida


def banda(freq_mhz):
    if freq_mhz >= 5925:
        return "6 GHz"
    return "5 GHz" if freq_mhz >= 4900 else "2.4 GHz"


def leer_redes(texto):
    """IN-USE,SSID,SIGNAL,SECURITY,FREQ -> {ssid: {senal, bandas, seguridad, en_uso}},
    juntando los puntos de acceso del mismo nombre (un router de doble banda
    son dos). Las ocultas (sin nombre) no salen."""
    redes = {}
    for linea in texto.splitlines():
        c = partir(linea)
        if len(c) < 5 or not c[1]:
            continue
        try:
            senal_ = int(c[2])
        except ValueError:
            senal_ = 0
        try:
            freq = int(c[4].split()[0])
        except (ValueError, IndexError):
            freq = 0
        r = redes.setdefault(c[1], {"senal": 0, "bandas": set(), "seguridad": c[3],
                                    "en_uso": False})
        if senal_ > r["senal"]:
            r["senal"], r["seguridad"] = senal_, c[3]
        if freq:
            r["bandas"].add(banda(freq))
        r["en_uso"] = r["en_uso"] or c[0].strip() == "*"
    return redes


def leer_conexiones(texto):
    """NAME,UUID,TYPE,AUTOCONNECT,DEVICE -> [{nombre, uuid, tipo, auto, dev}]."""
    salida = []
    for linea in texto.splitlines():
        c = partir(linea)
        if len(c) >= 5:
            salida.append({"nombre": c[0], "uuid": c[1], "tipo": c[2],
                           "auto": c[3] == "yes", "dev": c[4]})
    return salida


def leer_ssids(texto):
    """`nmcli -t -f connection.uuid,802-11-wireless.ssid connection show U1 U2`:
    bloques separados por una linea en blanco -> {uuid: ssid}."""
    ssids, uuid = {}, None
    for linea in texto.splitlines():
        clave, _, valor = linea.partition(":")
        if clave == "connection.uuid":
            uuid = valor
        elif clave == "802-11-wireless.ssid" and uuid:
            ssids[uuid] = valor
    return ssids


def tipo_seguridad(seguridad):
    """abierta | psk | sae | empresa | wep, de la columna SECURITY de nmcli."""
    s = (seguridad or "").upper()
    if not s or s == "--":
        return "abierta"
    if "802.1X" in s or "EAP" in s:
        return "empresa"
    if "WEP" in s:
        return "wep"
    if "WPA3" in s and "WPA2" not in s and "WPA1" not in s:
        return "sae"
    return "psk"


def glifo_senal(senal_):
    """Cuatro rayas desde el 75%, tres desde el 50, dos desde el 25, una con
    algo, y el contorno vacio sin señal."""
    s_ = int(senal_ or 0)
    return G_SENAL[4 if s_ >= 75 else 3 if s_ >= 50 else 2 if s_ >= 25 else 1 if s_ > 0 else 0]


def texto_seguridad(seguridad):
    s = (seguridad or "").strip()
    return "abierta" if not s or s == "--" else s.replace("WPA1 WPA2", "WPA2")


def explicar(mensaje):
    """El error de nmcli, en algo que se entienda."""
    m = (mensaje or "").lower()
    if "secrets were required" in m or "no-secrets" in m or "802-1x supplicant" in m:
        return "Contraseña incorrecta. Revísala y prueba otra vez."
    if "timeout" in m or "timed out" in m:
        return "No contesta. ¿Está cerca el router?"
    if "no network with ssid" in m or "not available" in m or "no suitable" in m:
        return "Fuera de alcance."
    if "ip configuration" in m or "ip-config" in m:
        return "Conecta, pero el router no le da IP."
    if "not authorized" in m or "insufficient privileges" in m:
        return "NetworkManager no deja hacer eso desde esta sesión."
    ultima = [l for l in (mensaje or "").splitlines() if l.strip()]
    return (ultima[-1] if ultima else "error").replace("Error: ", "").strip()


# Las razones de NetworkManager (NMDeviceStateReason) que se ven al conectar.
RAZONES = {
    7: "Contraseña incorrecta. Revísala y prueba otra vez.",
    8: "Contraseña incorrecta. Revísala y prueba otra vez.",
    9: "La red no admite esta forma de conectar. Prueba en «Ajustes avanzados».",
    10: "No se pudo conectar. Prueba otra vez.",
    11: "No contesta. ¿Está cerca el router?",
    5: "Conecta, pero el router no le da IP.",
    6: "Conecta, pero el router no le da IP.",
    53: "Fuera de alcance.",
}


@dataclass
class Fila:
    clave: str              # uuid de la conexion, o el SSID si no esta guardada
    nombre: str
    glifo: str
    detalle: str = ""
    accion: str = None      # desconectar | conectar | nueva | cable | avanzado | None
    senal: int = None
    candado: bool = False
    seguridad: str = "psk"  # abierta | psk | sae | empresa | wep (las nuevas)
    marca: str = ""         # «mejor señal»
    ips: list = field(default_factory=list)
    dev: str = ""
    editable: bool = False  # tiene «⋯»
    auto: bool = True
    lejos: bool = False
    portal: bool = False


@dataclass
class Modelo:
    hay_wifi: bool = False
    wifi_on: bool = False
    wifi_hw: bool = True
    iface: str = ""
    avion: bool = False
    avion_duro: bool = False
    conectados: list = field(default_factory=list)
    guardadas: list = field(default_factory=list)
    otras: list = field(default_factory=list)
    mas_otras: int = 0
    resto: list = field(default_factory=list)   # las plegadas, ya como Fila


def construir(datos):
    """Lo leido de nmcli (ver Fuente.leer) -> lo que enseña el panel."""
    m = Modelo(avion=datos.get("avion", False), avion_duro=datos.get("avion_duro", False))
    dispositivos = datos.get("dispositivos", [])
    redes = datos.get("redes", {})
    conexiones = datos.get("conexiones", [])
    ssids = datos.get("ssids", {})
    ips = datos.get("ips", {})
    wifis = [d for d in dispositivos if d["tipo"] == "wifi"]
    m.hay_wifi = bool(wifis)
    m.iface = wifis[0]["dev"] if wifis else ""
    m.wifi_hw = datos.get("wifi_hw", True)
    m.wifi_on = m.hay_wifi and datos.get("wifi_on", False) and m.wifi_hw
    portal = datos.get("conectividad") == "portal"

    activas = {d["conexion"]: d for d in dispositivos
               if d["estado"] == "connected" and d["tipo"] in ("wifi", "ethernet")}
    por_nombre = {c["nombre"]: c for c in conexiones}
    guardadas_wifi = [c for c in conexiones if c["tipo"] == "802-11-wireless"]
    ssid_de = {c["uuid"]: ssids.get(c["uuid"], c["nombre"]) for c in guardadas_wifi}

    # --- Conectado ---
    senal_actual = None
    for nombre, d in activas.items():
        c = por_nombre.get(nombre, {})
        if d["tipo"] == "wifi":
            ssid = ssid_de.get(c.get("uuid"), nombre)
            r = redes.get(ssid, {})
            senal_actual = r.get("senal")
            partes = ["%d%%" % r["senal"]] if r.get("senal") is not None else []
            partes += sorted(r.get("bandas", ()))[:1] + [texto_seguridad(r.get("seguridad"))]
            m.conectados.append(Fila(
                c.get("uuid", nombre), ssid, glifo_senal(r.get("senal", 0)),
                " · ".join(partes), accion="desconectar", senal=r.get("senal"),
                ips=ips.get(d["dev"], []), dev=d["dev"], editable=bool(c.get("uuid")),
                auto=c.get("auto", True), portal=portal))
        else:
            m.conectados.append(Fila(
                c.get("uuid", nombre), "Cable (%s)" % d["dev"], G_CABLE, "Conectado",
                accion="desconectar", ips=ips.get(d["dev"], []), dev=d["dev"]))

    # --- Mis redes ---
    activas_uuid = {f.clave for f in m.conectados}
    filas = []
    for c in guardadas_wifi:
        if c["uuid"] in activas_uuid:
            continue
        ssid = ssid_de[c["uuid"]]
        r = redes.get(ssid) if m.wifi_on else None
        if r:
            partes = ["%d%%" % r["senal"]] + sorted(r["bandas"])[-1:] + [
                "se conecta sola" if c["auto"] else "no se conecta sola"]
            marca = ("mejor señal" if senal_actual is not None
                     and r["senal"] >= senal_actual + MEJOR_POR else "")
            filas.append((0, -r["senal"], Fila(
                c["uuid"], ssid, glifo_senal(r["senal"]), " · ".join(partes),
                accion="conectar", senal=r["senal"], candado=tipo_seguridad(
                    r["seguridad"]) != "abierta", marca=marca, editable=True,
                auto=c["auto"])))
        else:
            filas.append((1, 0, Fila(c["uuid"], ssid, G_SENAL[0], "Fuera de alcance",
                                     editable=True, auto=c["auto"], lejos=True)))
    m.guardadas = [f for _, _, f in sorted(filas, key=lambda t: (t[0], t[1], t[2].nombre.lower()))]
    for d in dispositivos:
        if d["tipo"] != "ethernet" or d["conexion"] in activas:
            continue
        if d["estado"] == "unavailable":
            m.guardadas.append(Fila(d["dev"], "Cable (%s)" % d["dev"], G_CABLE,
                                    "Sin cable enchufado", lejos=True, dev=d["dev"]))
        elif d["estado"] in ("disconnected", "deactivating"):
            m.guardadas.append(Fila(d["dev"], "Cable (%s)" % d["dev"], G_CABLE,
                                    "Enchufado, sin conectar", accion="cable", dev=d["dev"]))

    # --- Otras redes ---
    if m.wifi_on:
        conocidas = set(ssid_de.values()) | {f.nombre for f in m.conectados}
        nuevas = sorted(((s, r) for s, r in redes.items() if s not in conocidas),
                        key=lambda t: (-t[1]["senal"], t[0].lower()))
        for ssid, r in nuevas[:MAX_OTRAS]:
            seg = tipo_seguridad(r["seguridad"])
            partes = ["%d%%" % r["senal"], " y ".join(
                sorted((b.replace(" GHz", "") for b in r["bandas"]), key=float)) + " GHz"
                if r["bandas"] else ""]
            if seg in ("empresa", "wep"):
                partes.append("de empresa" if seg == "empresa" else "WEP")
            m.otras.append(Fila(ssid, ssid, glifo_senal(r["senal"]),
                                " · ".join(p for p in partes if p),
                                accion="avanzado" if seg in ("empresa", "wep") else "nueva",
                                senal=r["senal"], candado=seg != "abierta", seguridad=seg))
        m.mas_otras = max(0, len(nuevas) - MAX_OTRAS)
        for ssid, r in nuevas[MAX_OTRAS:]:
            seg = tipo_seguridad(r["seguridad"])
            m.resto.append(Fila(ssid, ssid, glifo_senal(r["senal"]), "%d%%" % r["senal"],
                                accion="avanzado" if seg in ("empresa", "wep") else "nueva",
                                senal=r["senal"], candado=seg != "abierta", seguridad=seg))
    return m


def escapar_qr(texto):
    """El formato WIFI: de los QR escapa \\ ; , : y comillas con una barra."""
    return "".join("\\" + c if c in '\\;,:"' else c for c in texto)


def texto_qr(ssid, clave, seguridad="psk"):
    if not clave or seguridad == "abierta":
        return "WIFI:T:nopass;S:%s;;" % escapar_qr(ssid)
    return "WIFI:T:WPA;S:%s;P:%s;;" % (escapar_qr(ssid), escapar_qr(clave))


def velocidad(antes, ahora, segundos):
    """(rx, tx) en bytes/s -> «↓ 1.2 MB/s   ↑ 48 kB/s»."""
    def fmt(b):
        for unidad, tam in (("MB/s", 1e6), ("kB/s", 1e3)):
            if b >= tam:
                return "%.1f %s" % (b / tam, unidad) if b < 10 * tam else "%d %s" % (b / tam, unidad)
        return "%d B/s" % b
    if not antes or segundos <= 0:
        return ""
    rx = max(0, ahora[0] - antes[0]) / segundos
    tx = max(0, ahora[1] - antes[1]) / segundos
    return "↓ %s   ↑ %s" % (fmt(rx), fmt(tx))


# ─────────────────────────────────────────────────────────────────────────────
# Hablar con el sistema
# ─────────────────────────────────────────────────────────────────────────────

def nmcli(*args, entrada=None, plazo=PLAZO_NMCLI):
    """(codigo, salida, error). Sin nmcli, (127, "", explicacion)."""
    if shutil.which("nmcli") is None:
        return 127, "", "No está nmcli (NetworkManager)."
    entorno = dict(os.environ, LC_ALL="C")
    try:
        r = subprocess.run(["nmcli", *args], input=entrada, capture_output=True,
                           text=True, timeout=plazo, env=entorno)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "Timeout"
    except OSError as e:
        return 126, "", str(e)


def rfkill():
    """(todo_bloqueado_blando, alguno_duro) del wifi y el Bluetooth, leido de /sys."""
    blandos, duro, hay = [], False, False
    base = "/sys/class/rfkill"
    try:
        nombres = os.listdir(base)
    except OSError:
        return False, False
    for n in nombres:
        try:
            with open(os.path.join(base, n, "type")) as f:
                if f.read().strip() not in ("wlan", "bluetooth"):
                    continue
            hay = True
            with open(os.path.join(base, n, "soft")) as f:
                blandos.append(f.read().strip() == "1")
            with open(os.path.join(base, n, "hard")) as f:
                duro |= f.read().strip() == "1"
        except OSError:
            continue
    return hay and all(blandos), duro


def bytes_de(dev):
    try:
        with open("/sys/class/net/%s/statistics/rx_bytes" % dev) as f:
            rx = int(f.read())
        with open("/sys/class/net/%s/statistics/tx_bytes" % dev) as f:
            tx = int(f.read())
        return rx, tx
    except (OSError, ValueError):
        return None


class Fuente:
    """Lee el estado entero con nmcli. Tarda unos 100 ms: se llama en un hilo."""

    def leer(self):
        d = {}
        _, out, _ = nmcli("-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device")
        d["dispositivos"] = leer_dispositivos(out)
        _, out, _ = nmcli("-t", "-f", "WIFI-HW,WIFI", "radio")
        campos = partir(out.strip()) if out.strip() else []
        d["wifi_hw"] = (campos[0] == "enabled") if campos else True
        d["wifi_on"] = (campos[1] == "enabled") if len(campos) > 1 else False
        _, out, _ = nmcli("-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY,FREQ",
                          "device", "wifi", "list", "--rescan", "no")
        d["redes"] = leer_redes(out)
        _, out, _ = nmcli("-t", "-f", "NAME,UUID,TYPE,AUTOCONNECT,DEVICE", "connection", "show")
        d["conexiones"] = leer_conexiones(out)
        uuids = [c["uuid"] for c in d["conexiones"] if c["tipo"] == "802-11-wireless"]
        d["ssids"] = {}
        if uuids:
            _, out, _ = nmcli("-t", "-f", "connection.uuid,802-11-wireless.ssid",
                              "connection", "show", *uuids)
            d["ssids"] = leer_ssids(out)
        d["ips"] = {}
        for disp in d["dispositivos"]:
            if disp["estado"] == "connected" and disp["tipo"] in ("wifi", "ethernet"):
                _, out, _ = nmcli("-g", "IP4.ADDRESS", "device", "show", disp["dev"])
                d["ips"][disp["dev"]] = [x.strip().split("/")[0] for x in out.split("|")
                                         if x.strip()]
        _, out, _ = nmcli("-t", "-f", "CONNECTIVITY", "general")
        d["conectividad"] = out.strip()
        d["avion"], d["avion_duro"] = rfkill()
        return d


class Control:
    """Lo que hacen los botones. Cada accion corre en un hilo (o por D-Bus,
    asincrona) y acaba llamando a `listo(error)` en el hilo de GTK, con error
    None si fue bien o un texto ya explicado."""

    def __init__(self, en_gtk=None):
        # en_gtk(funcion): ejecutarla en el hilo principal. Sin GTK (pruebas),
        # se ejecuta en el acto.
        self.en_gtk = en_gtk or (lambda f: f())

    def _en_hilo(self, trabajo, listo):
        def correr():
            try:
                error = trabajo()
            except Exception as e:  # noqa: BLE001 — que la tecla no se quede colgada
                error = str(e)
            self.en_gtk(lambda: listo(error))
        threading.Thread(target=correr, daemon=True).start()

    def _orden(self, *args, plazo=PLAZO_NMCLI):
        codigo, _, err = nmcli(*args, plazo=plazo)
        return None if codigo == 0 else explicar(err)

    def conectar(self, uuid, listo):
        self._en_hilo(lambda: self._orden("connection", "up", "uuid", uuid,
                                          plazo=PLAZO_CONECTAR), listo)

    def desconectar(self, uuid, listo):
        self._en_hilo(lambda: self._orden("connection", "down", "uuid", uuid), listo)

    def cable(self, dev, listo):
        self._en_hilo(lambda: self._orden("device", "connect", dev, plazo=PLAZO_CONECTAR),
                      listo)

    def olvidar(self, uuid, listo):
        self._en_hilo(lambda: self._orden("connection", "delete", "uuid", uuid), listo)

    def autoconectar(self, uuid, si, listo):
        self._en_hilo(lambda: self._orden("connection", "modify", "uuid", uuid,
                                          "connection.autoconnect", "yes" if si else "no"),
                      listo)

    def buscar(self, listo):
        self._en_hilo(lambda: self._orden("device", "wifi", "rescan"), listo)

    def wifi(self, si, listo):
        self._en_hilo(lambda: self._orden("radio", "wifi", "on" if si else "off"), listo)

    def avion(self, si, listo):
        def trabajo():
            # /dev/rfkill es de quien tiene la sesion (uaccess): sin sudo.
            try:
                r = subprocess.run(["rfkill", "block" if si else "unblock", "all"],
                                   capture_output=True, text=True, timeout=5)
            except (OSError, subprocess.TimeoutExpired) as e:
                return str(e)
            return None if r.returncode == 0 else (r.stderr.strip() or "rfkill falló")
        self._en_hilo(trabajo, listo)

    def clave(self, uuid, listo):
        """listo(error, clave). La contraseña guardada, solo cuando se pide."""
        resultado = {}

        def trabajo():
            codigo, out, err = nmcli("-s", "-g", "802-11-wireless-security.psk",
                                     "connection", "show", "uuid", uuid)
            if codigo != 0:
                return explicar(err)
            resultado["clave"] = out.strip()
            return None
        self._en_hilo(trabajo, lambda e: listo(e, resultado.get("clave", "")))

    # --- Una red nueva, por D-Bus (ver la cabecera) ---------------------------

    def nueva(self, iface, ssid, clave, seguridad, listo):
        try:
            import gi
            gi.require_version("Gio", "2.0")
            from gi.repository import Gio, GLib
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        except Exception as e:  # noqa: BLE001
            listo(str(e))
            return
        ConexionNueva(Gio, GLib, bus, iface, ssid, clave, seguridad, listo).empezar()


class ConexionNueva:
    """AddAndActivateConnection2 con persist=memory, mirar en que acaba, y
    guardarla (Save) si conecto o borrarla (Delete) si no."""

    def __init__(self, Gio, GLib, bus, iface, ssid, clave, seguridad, listo):
        self.Gio, self.GLib, self.bus = Gio, GLib, bus
        self.iface, self.ssid, self.clave, self.seguridad = iface, ssid, clave, seguridad
        self.listo = listo
        self.perfil = self.activa = self.dispositivo = None
        self.sub = None
        self.hecho = False

    def _llamar(self, ruta, interfaz, metodo, params, tipo, al_acabar, plazo=10_000):
        def fin(bus, res, _d=None):
            try:
                al_acabar(bus.call_finish(res), None)
            except self.GLib.Error as e:
                al_acabar(None, e.message)
        self.bus.call(NM, ruta, interfaz, metodo, params,
                      self.GLib.VariantType(tipo) if tipo else None,
                      self.Gio.DBusCallFlags.NONE, plazo, None, fin, None)

    def empezar(self):
        V = self.GLib.Variant
        self._llamar(NM_RUTA, NM, "GetDeviceByIpIface", V("(s)", (self.iface,)), "(o)",
                     self._con_dispositivo)

    def _con_dispositivo(self, r, error):
        if error:
            return self._terminar(explicar(error))
        self.dispositivo = r.unpack()[0]
        V = self.GLib.Variant
        ajustes = {
            "connection": {"id": V("s", self.ssid), "type": V("s", "802-11-wireless"),
                           "autoconnect": V("b", True)},
            "802-11-wireless": {"ssid": V("ay", self.ssid.encode()),
                                "mode": V("s", "infrastructure")},
        }
        if self.seguridad in ("psk", "sae"):
            ajustes["802-11-wireless-security"] = {
                "key-mgmt": V("s", "sae" if self.seguridad == "sae" else "wpa-psk"),
                "psk": V("s", self.clave)}
        opciones = {"persist": V("s", "memory")}
        self._llamar(NM_RUTA, NM, "AddAndActivateConnection2",
                     V("(a{sa{sv}}ooa{sv})", (ajustes, self.dispositivo, "/", opciones)),
                     "(ooa{sv})", self._activando, plazo=PLAZO_CONECTAR * 1000)

    def _activando(self, r, error):
        if error:
            return self._terminar(explicar(error))
        self.perfil, self.activa, _ = r.unpack()
        self.sub = self.bus.signal_subscribe(
            NM, NM_ACTIVA, "StateChanged", self.activa, None,
            self.Gio.DBusSignalFlags.NONE,
            lambda *a: self._estado(a[5].unpack()[0]))
        # Por si ya acabo antes de suscribirse, y como red de seguridad.
        self._mirar_id = self.GLib.timeout_add(1000, self._mirar)
        self._plazo_id = self.GLib.timeout_add_seconds(PLAZO_CONECTAR, self._sin_tiempo)

    def _mirar(self):
        if self.hecho:
            return False
        V = self.GLib.Variant

        def leido(r, error):
            if error:   # el objeto ya no existe: se desactivo y lo quitaron
                self._estado(4)
                return
            self._estado(r.unpack()[0])
        self._llamar(self.activa, "org.freedesktop.DBus.Properties", "Get",
                     V("(ss)", (NM_ACTIVA, "State")), "(v)", leido)
        return True

    def _estado(self, estado):
        if self.hecho:
            return
        if estado == 2:            # activada
            self.hecho = True
            self._llamar(self.perfil, NM_PERFIL, "Save", None, None,
                         lambda _r, e: self._terminar(None if not e else
                                                      "Conectada, pero no pude guardarla: " + e))
        elif estado == 4:          # desactivada: fallo
            self.hecho = True
            V = self.GLib.Variant

            def razon(r, _e):
                motivo = r.unpack()[0][1] if r is not None else 0
                texto = RAZONES.get(motivo, "No se pudo conectar (código %d)." % motivo)
                self._borrar(lambda: self._terminar(texto))
            self._llamar(self.dispositivo, "org.freedesktop.DBus.Properties", "Get",
                         V("(ss)", (NM_DISPOSITIVO, "StateReason")), "(v)", razon)

    def _sin_tiempo(self):
        if not self.hecho:
            self.hecho = True
            V = self.GLib.Variant
            self._llamar(NM_RUTA, NM, "DeactivateConnection", V("(o)", (self.activa,)), None,
                         lambda _r, _e: self._borrar(
                             lambda: self._terminar("No contesta. ¿Está cerca el router?")))
        return False

    def _borrar(self, despues):
        if not self.perfil:
            return despues()
        self._llamar(self.perfil, NM_PERFIL, "Delete", None, None, lambda _r, _e: despues())

    def _terminar(self, error):
        if self.sub is not None:
            self.bus.signal_unsubscribe(self.sub)
            self.sub = None
        self.hecho = True
        self.listo(error)


def qr_png(texto, C):
    """El QR como PNG (bytes), con los colores de la paleta, o None sin qrencode.
    El texto (con la contraseña) entra por stdin, no por la linea de ordenes."""
    if shutil.which("qrencode") is None:
        return None
    try:
        r = subprocess.run(["qrencode", "-t", "PNG", "-o", "-", "-s", "5", "-m", "1",
                            "--foreground=" + _hex(C["abismo"])[1:],
                            "--background=" + _hex(C["luz"])[1:]],
                           input=texto.encode(), capture_output=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 and r.stdout else None


def ver():
    m = construir(Fuente().leer())
    if not m.hay_wifi and not m.conectados and not m.guardadas:
        print("Sin Wi-Fi ni cable que enseñar.")
        return 0
    print("Wi-Fi %s: %s%s" % (m.iface or "-", "encendido" if m.wifi_on else "apagado",
                              " · MODO AVION" if m.avion else ""))
    for titulo, filas in (("Conectado", m.conectados), ("Mis redes", m.guardadas),
                          ("Otras redes", m.otras)):
        if not filas:
            continue
        print("\n" + titulo)
        for f in filas:
            extra = " [%s]" % f.marca if f.marca else ""
            ips = "  " + " + ".join(f.ips) if f.ips else ""
            print("  %-24s %s%s%s  [%s]" % (f.nombre, f.detalle, extra, ips, f.accion or "-"))
    if m.mas_otras:
        print("  + %d redes mas" % m.mas_otras)
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# La ventana
# ─────────────────────────────────────────────────────────────────────────────

def abrir_panel():
    def a_nmtui():
        terminal = os.path.join(RAIZ, "terminal.sh")
        subprocess.Popen([terminal, "monitor-tui", "nmtui"], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        import panel_capa as pc
    except (ImportError, ValueError):
        # Sin gtk-layer-shell no hay panel: se dice y se abre nmtui, como antes.
        subprocess.Popen(["notify-send", "-a", "Red", "Falta gtk-layer-shell",
                          "Sin él, el panel de red no puede abrirse; va nmtui.\n"
                          "sudo pacman -S gtk-layer-shell"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        a_nmtui()
        return 1
    if not pc.solo_wayland():
        print("wifi-panel: hace falta una sesion Wayland", file=sys.stderr)
        return 1
    import dibujo
    from gi.repository import GdkPixbuf
    GLib, Gtk, Pango = pc.GLib, pc.Gtk, pc.Pango
    etiqueta, boton, caja = pc.etiqueta, pc.boton, pc.caja

    def en_gtk(f):
        GLib.idle_add(lambda: f() or False)

    class Panel(pc.PanelCapa):
        def __init__(self):
            super().__init__("wifi-panel", G_WIFI, "Wi-Fi")
            self.fuente = Fuente()
            self.control = Control(en_gtk)
            self.modelo = None
            self.ocupados = {}       # clave -> texto mientras se hace algo
            self.editando = None     # clave con el «⋯» abierto
            self.compartiendo = None  # clave con el QR a la vista
            self.confirmar = None    # clave a olvidar, a falta del «si»
            self.escribiendo = None  # SSID con la contraseña abierta
            self.errores = {}        # clave -> error de su ultimo intento
            self.claves = {}         # uuid -> contraseña ya leida (solo en memoria)
            self.ver_clave = False
            self.desplegado = False
            self.buscando_hasta = 0
            self.leyendo = False
            self._bytes = {}         # dev -> ((rx, tx), cuando)
            self._velocidad = {}
            self._entrada = None
            self._escrito = ""
            self._a_la_vista = None

            self.sw_avion = self.opcion("Modo avión", "Apaga el wifi y el Bluetooth",
                                        self._al_avion)
            botones = caja(espacio=8)
            self.b_buscar = boton(G_GIRO + "  Buscar", self._buscar, ("suave",))
            botones.pack_start(self.b_buscar, False, False, 0)
            botones.pack_end(boton(G_AJUSTES + "  Ajustes avanzados", self._avanzado,
                                   ("suave",)), False, False, 0)
            self.pie.pack_start(botones, False, False, 2)

            self.cabecera(G_WIFI, "leyendo…")
            self._buscar()
            GLib.timeout_add(REFRESCO_MS, self._refresco)

        # --- Leer -------------------------------------------------------------

        def _refresco(self):
            self.refrescar()
            return True

        def refrescar(self, forzar=False):
            if self.leyendo:
                return
            self.leyendo = True

            def hilo():
                try:
                    datos = self.fuente.leer()
                except Exception as e:  # noqa: BLE001
                    datos = {"_error": str(e)}
                en_gtk(lambda: self._leido(datos, forzar))
            threading.Thread(target=hilo, daemon=True).start()

        def _leido(self, datos, forzar):
            self.leyendo = False
            if "_error" in datos:
                self.avisar("No pude leer la red: %s" % datos["_error"], True)
                return
            modelo = construir(datos)
            self._medir(modelo)
            if modelo == self.modelo and not forzar:
                self._pintar_velocidad()   # lo unico que cambia sin que cambie nada
                return
            self.modelo = modelo
            self.pintar()

        def _medir(self, m):
            ahora = time.monotonic()
            for f in m.conectados:
                b = bytes_de(f.dev)
                antes = self._bytes.get(f.dev)
                if b and antes:
                    self._velocidad[f.dev] = velocidad(antes[0], b, ahora - antes[1])
                if b:
                    self._bytes[f.dev] = (b, ahora)

        def _pintar_velocidad(self):
            for dev, etq in getattr(self, "_etq_velocidad", {}).items():
                etq.set_text(self._velocidad.get(dev, "") or "midiendo…")

        # --- Pintar -----------------------------------------------------------

        def pintar(self):
            m = self.modelo
            if m is None:
                return
            # Lo que estuvieras escribiendo sobrevive al repintado (llega uno
            # cada vez que termina una busqueda).
            if self._entrada is not None:
                self._escrito = self._entrada.get_text()
            self._entrada = None
            self._a_la_vista = None
            self.poner(self.interruptor, m.wifi_on, m.hay_wifi and m.wifi_hw and not m.avion)
            self.poner(self.sw_avion, m.avion, not m.avion_duro)
            if not m.hay_wifi:
                sub, glifo = "este equipo no tiene wifi", G_WIFI_OFF
            elif m.avion:
                sub, glifo = "modo avión", G_WIFI_OFF
            elif not m.wifi_hw:
                sub, glifo = "apagado por el interruptor del equipo", G_WIFI_OFF
            else:
                sub = "%s · %s" % (m.iface, "encendido" if m.wifi_on else "apagado")
                glifo = G_WIFI if m.wifi_on else G_WIFI_OFF
            self.cabecera(glifo, sub, apagado=glifo == G_WIFI_OFF)
            buscando = time.monotonic() < self.buscando_hasta
            self.b_buscar.set_sensitive(m.wifi_on and not buscando)

            self.vaciar_cuerpo()
            self._etq_velocidad = {}
            self.seccion("Conectado")
            if m.conectados:
                for f in m.conectados:
                    self.cuerpo.pack_start(self._fila(f, "uso"), False, False, 0)
            else:
                self.vacio("Sin conexión." if m.wifi_on or not m.hay_wifi else
                           "El wifi está apagado. Enciéndelo arriba.")
            if m.guardadas:
                self.seccion("Mis redes")
                for f in m.guardadas:
                    self.cuerpo.pack_start(self._fila(f, "guardada"), False, False, 0)
            if m.wifi_on:
                self.seccion("Otras redes", buscando=buscando)
                otras = m.otras + (m.resto if self.desplegado else [])
                for f in otras:
                    self.cuerpo.pack_start(self._fila(f, "otra"), False, False, 0)
                if not otras:
                    self.vacio("No se ve ninguna más." if not buscando else "Buscando…")
                if m.mas_otras:
                    self.cuerpo.pack_start(boton(
                        ("▴  menos" if self.desplegado else
                         "+ %d redes más débiles  ▾" % m.mas_otras),
                        self._plegar, ("plano",)), False, False, 2)
            self.terminar_cuerpo(ver=self._a_la_vista)
            self._pintar_velocidad()

        def _fila(self, f, tipo):
            externa = caja(vertical=True, espacio=8)
            ctx = externa.get_style_context()
            ctx.add_class("uso" if tipo == "uso" else "fila")
            if f.clave in self.errores and tipo == "otra":
                ctx.add_class("error")
            fila = caja(espacio=12)
            ico = etiqueta(f.glifo, ("ico",) + (("lejos",) if f.lejos else ()), xalign=0.5)
            # El candado, pequeño en la esquina del icono, como en la maqueta.
            sobre = Gtk.Overlay()
            sobre.add(ico)
            if f.candado and tipo != "uso":
                candado = etiqueta(G_CANDADO, ("candado",))
                candado.set_halign(Gtk.Align.END)
                candado.set_valign(Gtk.Align.END)
                sobre.add_overlay(candado)
            sobre.set_valign(Gtk.Align.CENTER)
            fila.pack_start(sobre, False, False, 0)

            textos = caja(vertical=True, espacio=1)
            linea = caja(espacio=6)
            nombre = etiqueta(f.nombre, ("nombre",))
            nombre.set_ellipsize(Pango.EllipsizeMode.END)
            linea.pack_start(nombre, False, False, 0)
            if f.marca:
                linea.pack_start(etiqueta(f.marca, ("mejor",)), False, False, 0)
            textos.pack_start(linea, False, False, 0)
            detalle = etiqueta(self.ocupados.get(f.clave) or f.detalle, ("detalle",))
            detalle.set_line_wrap(True)
            detalle.set_max_width_chars(28)
            textos.pack_start(detalle, False, False, 0)
            fila.pack_start(textos, True, True, 0)

            if f.editable:
                fila.pack_end(boton(G_MAS, lambda: self._editar(f.clave), ("mas",)),
                              False, False, 0)
            accion = self._boton_accion(f)
            if accion is not None:
                fila.pack_end(accion, False, False, 0)
            externa.pack_start(fila, False, False, 0)

            if tipo == "uso" and (f.ips or f.dev):
                datos = Gtk.Grid(column_spacing=12, row_spacing=2)
                if f.ips:
                    datos.attach(etiqueta("IP", ("dato",)), 0, 0, 1, 1)
                    datos.attach(etiqueta("  +  ".join(f.ips), ("dato", "valor")), 1, 0, 1, 1)
                datos.attach(etiqueta("Velocidad", ("dato",)), 0, 1, 1, 1)
                vel = etiqueta("midiendo…", ("dato", "valor"))
                self._etq_velocidad[f.dev] = vel
                datos.attach(vel, 1, 1, 1, 1)
                externa.pack_start(datos, False, False, 0)
            if tipo == "uso" and f.portal:
                aviso = caja(espacio=8)
                txt = etiqueta(G_WEB + "  Esta red pide iniciar sesión en la web",
                               ("marca",))
                aviso.pack_start(txt, False, False, 0)
                aviso.pack_end(boton("Abrir", self._portal, ("suave",)), False, False, 0)
                externa.pack_start(aviso, False, False, 0)

            if f.clave in (self.escribiendo, self.editando) or \
                    (f.clave in self.errores and tipo == "otra"):
                self._a_la_vista = externa
            if self.escribiendo == f.clave:
                externa.pack_start(self._contrasena(f), False, False, 0)
            if f.clave in self.errores:
                err = etiqueta(G_AVISO + "  " + self.errores[f.clave], ("error-texto",))
                err.set_line_wrap(True)
                externa.pack_start(err, False, False, 0)
            if self.editando == f.clave:
                externa.pack_start(self._editor(f), False, False, 0)
            return externa

        def _boton_accion(self, f):
            if f.clave in self.ocupados or f.accion is None or self.escribiendo == f.clave:
                return None
            textos = {"desconectar": ("Desconectar", ()), "conectar": ("Conectar", ("suave",)),
                      "nueva": ("Conectar", ("lleno",)), "cable": ("Conectar", ("suave",)),
                      "avanzado": ("En ajustes", ("suave",))}
            texto, clases = textos[f.accion]
            return boton(texto, lambda: self._hacer(f), clases)

        def _contrasena(self, f):
            c = caja(vertical=True, espacio=4)
            linea = caja(espacio=8)
            e = Gtk.Entry()
            e.set_visibility(False)
            e.set_placeholder_text("Contraseña")
            e.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "view-reveal-symbolic")
            e.connect("icon-press", lambda w, *_: w.set_visibility(not w.get_visibility()))
            if f.clave in self.errores:
                e.get_style_context().add_class("error")
            e.set_text(getattr(self, "_escrito", ""))
            e.connect("activate", lambda *_: self._conectar_nueva(f, e.get_text()))
            linea.pack_start(e, True, True, 0)
            linea.pack_start(boton("Reintentar" if f.clave in self.errores else "Conectar",
                                   lambda: self._conectar_nueva(f, e.get_text()), ("lleno",)),
                             False, False, 0)
            c.pack_start(linea, False, False, 0)
            c.pack_start(etiqueta("Enter para conectar · Escape para cancelar", ("tenue",)),
                         False, False, 0)
            self._entrada = e
            GLib.idle_add(lambda: e.grab_focus() or False)
            return c

        def _editor(self, f):
            c = caja(vertical=True, espacio=8)
            if self.confirmar == f.clave:
                fila = caja(espacio=6)
                p = etiqueta("¿Olvidar %s? Habrá que volver a poner su contraseña." % f.nombre,
                             ("detalle",))
                p.set_line_wrap(True)
                fila.pack_start(p, True, True, 0)
                fila.pack_end(boton("No", self._cerrar_editor, ("suave",)), False, False, 0)
                fila.pack_end(boton("Sí, olvidar", lambda: self._olvidar(f), ("peligro",)),
                              False, False, 0)
                c.pack_start(fila, False, False, 0)
                return c
            if self.compartiendo == f.clave:
                c.pack_start(self._compartir(f), False, False, 0)
            botones = Gtk.FlowBox()
            botones.set_selection_mode(Gtk.SelectionMode.NONE)
            botones.set_max_children_per_line(3)
            botones.set_column_spacing(6)
            botones.set_row_spacing(6)
            if self.compartiendo != f.clave:
                botones.add(boton(G_QR + "  Compartir red", lambda: self._compartir_red(f),
                                  ("suave",)))
            botones.add(boton("Conectar sola: %s" % ("sí" if f.auto else "no"),
                              lambda: self._auto(f), ("suave",)))
            botones.add(boton("Olvidar", lambda: self._pedir_olvidar(f.clave), ("peligro",)))
            c.pack_start(botones, False, False, 0)
            return c

        def _compartir(self, f):
            c = caja(espacio=14)
            clave = self.claves.get(f.clave)
            if clave is None:
                c.pack_start(etiqueta("Leyendo la contraseña…", ("detalle",)), False, False, 0)
                return c
            png = qr_png(texto_qr(f.nombre, clave), dibujo.C)
            if png:
                cargador = GdkPixbuf.PixbufLoader.new_with_type("png")
                cargador.write(png)
                cargador.close()
                img = Gtk.Image.new_from_pixbuf(cargador.get_pixbuf())
                marco = Gtk.EventBox()
                marco.set_name("qr")
                marco.add(img)
                marco.set_valign(Gtk.Align.START)
                c.pack_start(marco, False, False, 0)
            textos = caja(vertical=True, espacio=4)
            ayuda = etiqueta("Escanéalo con el móvil para entrar sin escribir."
                             if png else "Para el QR hace falta qrencode:\nsudo pacman -S qrencode",
                             ("detalle",))
            ayuda.set_line_wrap(True)
            ayuda.set_max_width_chars(20)
            textos.pack_start(ayuda, False, False, 0)
            textos.pack_start(etiqueta("Contraseña", ("detalle",)), False, False, 6)
            linea = caja(espacio=4)
            mostrar = clave if self.ver_clave else ("•" * min(len(clave), 12) or "(abierta)")
            linea.pack_start(etiqueta(mostrar, ("dato", "valor")), False, False, 0)
            if clave:
                linea.pack_start(boton(G_OJO_NO if self.ver_clave else G_OJO, self._ver_clave,
                                       ("plano",)), False, False, 0)
            textos.pack_start(linea, False, False, 0)
            if clave and shutil.which("wl-copy"):
                textos.pack_start(boton(G_COPIAR + "  Copiar", lambda: self._copiar(clave),
                                        ("suave",)), False, False, 4)
            c.pack_start(textos, True, True, 0)
            return c

        # --- Acciones ---------------------------------------------------------

        def _hacer(self, f):
            if f.accion == "nueva":
                if f.seguridad == "abierta":
                    return self._conectar_nueva(f, "")
                self.escribiendo = f.clave
                self._escrito = ""
                self.errores.pop(f.clave, None)
                return self.pintar()
            if f.accion == "avanzado":
                return self._avanzado()
            textos = {"desconectar": "Desconectando…", "conectar": "Conectando…",
                      "cable": "Conectando…"}
            self.ocupados[f.clave] = textos[f.accion]
            self.pintar()
            orden = {"desconectar": self.control.desconectar,
                     "conectar": self.control.conectar,
                     "cable": self.control.cable}[f.accion]
            orden(f.dev if f.accion == "cable" else f.clave, lambda e: self._fin(f, e))

        def _conectar_nueva(self, f, clave):
            if f.seguridad != "abierta" and len(clave) < 8:
                self.errores[f.clave] = "Una contraseña de wifi tiene al menos 8 caracteres."
                return self.pintar()
            self.escribiendo = None
            self.errores.pop(f.clave, None)
            self.ocupados[f.clave] = "Conectando…"
            self.pintar()

            def listo(error):
                if error:
                    self.errores[f.clave] = error
                    if f.seguridad != "abierta":
                        # Lo escrito se queda, para corregirlo en vez de
                        # volver a teclearlo entero.
                        self.escribiendo = f.clave
                        self._escrito = clave
                else:
                    self._escrito = ""
                self._fin(f, error, aviso=False)
            self.control.nueva(self.modelo.iface, f.nombre, clave, f.seguridad, listo)

        def _fin(self, f, error, aviso=True):
            self.ocupados.pop(f.clave, None)
            if error and aviso:
                self.avisar("%s: %s" % (f.nombre, error), True)
            self.refrescar(forzar=True)
            self.pintar()

        def _buscar(self):
            self.buscando_hasta = time.monotonic() + 6
            self.control.buscar(lambda _e: self.refrescar(forzar=True))
            self.refrescar(forzar=True)
            GLib.timeout_add(6200, lambda: self.refrescar(forzar=True) or False)

        def _plegar(self):
            self.desplegado = not self.desplegado
            self.pintar()

        def _editar(self, clave):
            self.confirmar = self.compartiendo = None
            self.ver_clave = False
            self.editando = None if self.editando == clave else clave
            self.pintar()

        def _cerrar_editor(self):
            self.editando = self.confirmar = self.compartiendo = None
            self.ver_clave = False
            self.pintar()

        def _compartir_red(self, f):
            self.compartiendo = f.clave
            self.pintar()
            if f.clave in self.claves:
                return

            def listo(error, clave):
                if error:
                    self.compartiendo = None
                    self.avisar("No pude leer la contraseña: %s" % error, True)
                else:
                    self.claves[f.clave] = clave
                self.pintar()
            self.control.clave(f.clave, listo)

        def _ver_clave(self):
            self.ver_clave = not self.ver_clave
            self.pintar()

        def _copiar(self, clave):
            try:
                subprocess.run(["wl-copy"], input=clave.encode(), timeout=3)
                self.avisar("Contraseña copiada.")
            except (OSError, subprocess.TimeoutExpired) as e:
                self.avisar("No pude copiarla: %s" % e, True)

        def _auto(self, f):
            self.control.autoconectar(f.clave, not f.auto, lambda e: self._fin(f, e))

        def _pedir_olvidar(self, clave):
            self.confirmar = clave
            self.pintar()

        def _olvidar(self, f):
            self.editando = self.confirmar = self.compartiendo = None
            self.claves.pop(f.clave, None)

            def listo(error):
                if not error:
                    self.avisar("%s olvidada." % f.nombre)
                self._fin(f, error)
            self.control.olvidar(f.clave, listo)

        def al_interruptor(self, activo):
            self.control.wifi(activo, lambda e: self._fin(Fila("", "Wi-Fi", ""), e))

        def _al_avion(self, activo):
            self.control.avion(activo, lambda e: self._fin(Fila("", "Modo avión", ""), e))

        def _portal(self):
            subprocess.Popen(["xdg-open", "http://neverssl.com"], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        def _avanzado(self):
            a_nmtui()
            self.close()

        # --- Lo de la base ----------------------------------------------------

        def ocupado(self):
            return bool(self.ocupados or self.escribiendo or self.editando)

        def al_escape(self):
            if self.escribiendo:
                self.escribiendo = None
                self._escrito = ""
                self.pintar()
            elif self.editando:
                self._cerrar_editor()
            else:
                self.close()

        def al_cerrar(self):
            self.claves.clear()

    return pc.lanzar("wifi-panel", Panel)


def main(argv):
    if argv == ["--ver"]:
        return ver()
    if argv:
        print(__doc__.split("USO\n---\n", 1)[-1].rstrip(), file=sys.stderr)
        return 2
    return abrir_panel()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
