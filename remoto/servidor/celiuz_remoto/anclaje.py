"""
remoto/servidor/celiuz_remoto/anclaje.py — que vuelva el internet del celular
por USB al reiniciar la PC.

EL PROBLEMA (la PC del autor, 2026-10-21): sale a internet por un Redmi
enchufado por USB con el anclaje puesto. Al reiniciar, el puerto USB se apaga
un momento, el celular cree que lo desenchufaron y APAGA el anclaje. La PC
llega a la pantalla de inicio sin internet y sin Tailscale, y el celular de
Celiuz Remoto ya no puede entrar: lo que la fase 5 existe para hacer.

EL ARREGLO: si el celular tiene la depuracion USB autorizada para esta PC, se
le vuelve a pedir con `svc usb setFunctions rndis`. Medido en ese Redmi
(Android 13, MIUI): con el anclaje apagado y sin ruta, a los 3 s volvio la
ruta y el ping. MIUI escupe una traza de Java por stderr en cada `svc`; es
ruido (no encuentra un fichero de temas) y el comando funciona igual. El
estado se lee con `getprop sys.usb.config` («rndis,adb»), que no la escupe.

A QUIEN, y esto es lo que lo hace seguro para cualquiera que clone el repo:
  - solo a un celular que YA se vio dando internet a esta PC (se apunta su
    serie en ~/.local/state/celiuz/remoto/anclaje.json). Un celular enchufado
    para cargar, aunque tenga la depuracion puesta, no se toca nunca;
  - solo si la PC no tiene otra salida a internet (sin ruta por defecto): con
    wifi o cable no hace falta molestar al celular;
  - y no si lo apagaste TU: si en esta vuelta del demonio se le vio con el
    anclaje y despues sin el, sin dejar de estar enchufado, fue a mano y se
    respeta hasta que se desenchufe.
Algunos Android nuevos usan NCM en vez de RNDIS; se le pide el que tenia.

LO QUE NO ARREGLA SOLO: en la pantalla de inicio el permiso del USB (la ACL que
da logind) es del usuario `sddm`, no tuyo, y adb dice «no permissions». Hace
falta una regla de udev que no dependa de la sesion: el paquete android-udev y
estar en su grupo adbusers. Y el demonio es del usuario, asi que sin linger no
arranca hasta que entras. `revisar()` dice las dos cosas.
"""

import grp
import json
import os
import pwd
import time

from . import adb, rutas

FUNCIONES = ("rndis", "ncm")
PAUSA = 5           # s entre pasadas
RESPIRO = 30        # s sin volver a pedirselo al mismo celular
REGLAS_UDEV = ("/usr/lib/udev/rules.d/51-android.rules", "/etc/udev/rules.d/51-android.rules")


def fichero():
    return os.path.join(rutas.estado(), "anclaje.json")


def recordados():
    """{serie: {"funcion": "rndis", "nombre": "M2101K7BL"}}"""
    try:
        with open(fichero()) as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def _guardar(datos):
    os.makedirs(os.path.dirname(fichero()), exist_ok=True)
    tmp = fichero() + ".nuevo"
    with open(tmp, "w") as f:
        json.dump(datos, f, indent=1)
    os.replace(tmp, fichero())


def funcion_de(config):
    """«rndis,adb» -> "rndis"; «mtp,adb» -> None."""
    partes = (config or "").strip().split(",")
    return next((f for f in FUNCIONES if f in partes), None)


def hay_internet(ruta_proc="/proc/net/route"):
    """¿Hay ruta por defecto (IPv4)? Tailscale no pone una (salvo con exit
    node), asi que no cuenta como internet."""
    try:
        with open(ruta_proc) as f:
            next(f)
            for linea in f:
                campos = linea.split()
                if len(campos) > 3 and campos[1] == "00000000" and int(campos[3], 16) & 1:
                    return True
    except (OSError, StopIteration, ValueError):
        return True   # sin saberlo, no se toca al celular
    return False


def mirar():
    """[{serie, estado, modelo, funcion}] de lo que hay enchufado."""
    r = adb._adb("devices", "-l")
    if r.returncode != 0:
        return []
    lista = adb.leer_lista(r.stdout)
    for c in lista:
        c["funcion"] = None
        if c["estado"] == "listo":
            p = adb._adb("shell", "getprop sys.usb.config", serie=c["serie"])
            if p.returncode == 0:
                c["funcion"] = funcion_de(p.stdout)
    return lista


class Vuelta:
    """La memoria de una vuelta del demonio: quien tenia el anclaje en la
    pasada anterior, a quien se le apago a mano, y cuando se le pidio a cada
    uno. Lo que se guarda en disco es solo `recordados`."""

    def __init__(self):
        self.con_anclaje = set()
        self.respetar = set()
        self.pedido = {}

    def decidir(self, lista, memoria, internet, ahora):
        """-> (a_quien_pedirselo [(serie, funcion)], memoria nueva). Sin
        efectos: la prueba la llama con listas de mentira."""
        memoria = dict(memoria)
        presentes = {c["serie"] for c in lista}
        # Desenchufado: lo de «lo apagaste tu» se olvida
        self.respetar &= presentes
        self.con_anclaje &= presentes
        pedir = []
        for c in lista:
            serie = c["serie"]
            if c["estado"] != "listo":
                continue
            if c.get("funcion"):
                memoria[serie] = {"funcion": c["funcion"], "nombre": c.get("modelo") or serie}
                self.con_anclaje.add(serie)
                self.respetar.discard(serie)
                continue
            if serie in self.con_anclaje:
                # Lo tenia hace un momento y no se desenchufo: fue a mano
                self.con_anclaje.discard(serie)
                self.respetar.add(serie)
                continue
            if (serie in memoria and serie not in self.respetar and not internet
                    and ahora - self.pedido.get(serie, 0) >= RESPIRO):
                self.pedido[serie] = ahora
                pedir.append((serie, memoria[serie].get("funcion") or "rndis"))
        return pedir, memoria


def pedir(serie, funcion):
    r = adb._adb("shell", f"svc usb setFunctions {funcion}", serie=serie)
    return r.returncode == 0


def pasada(vuelta, ahora=None):
    lista = mirar()
    memoria = recordados()
    a_pedir, nueva = vuelta.decidir(lista, memoria, hay_internet(), ahora or time.time())
    if nueva != memoria:
        _guardar(nueva)
    for serie, funcion in a_pedir:
        ok = pedir(serie, funcion)
        print(f"anclaje: {nueva[serie]['nombre']} ({serie}) sin anclaje y la PC sin internet: "
              f"{'pedido' if ok else 'NO se pudo pedir'} ({funcion})", flush=True)
    return a_pedir


def vigilar():
    if not adb.hay_adb():
        print("anclaje: no hay adb, no hay nada que vigilar", flush=True)
        return 0
    vuelta = Vuelta()
    while True:
        try:
            pasada(vuelta)
        except adb.ErrorAdb as e:
            print(f"anclaje: {e}", flush=True)
        time.sleep(PAUSA)


def _usuario():
    return pwd.getpwuid(os.getuid()).pw_name


def permiso_sin_sesion():
    """¿Puede este usuario abrir el USB del celular sin sesion abierta? Hace
    falta la regla de android-udev (grupo adbusers) y estar en ese grupo."""
    if not any(os.path.exists(r) for r in REGLAS_UDEV):
        return False
    try:
        g = grp.getgrnam("adbusers")
    except KeyError:
        return False
    yo = pwd.getpwuid(os.getuid())
    return _usuario() in g.gr_mem or yo.pw_gid == g.gr_gid


def revisar():
    """Lo que dice `celiuz-remoto anclaje` y lo que avisa instalar.sh. Solo
    tiene algo que decir si algun celular ya dio internet por USB."""
    from . import inicio
    memoria = recordados()
    falta = []
    if memoria:
        if not permiso_sin_sesion():
            falta.append(f"sudo pacman -S android-udev && sudo gpasswd -a {_usuario()} adbusers")
        if not inicio.linger():
            falta.append("encender Celiuz Remoto desde su ventana (linger), o: loginctl enable-linger")
    return {"recordados": memoria, "permiso_sin_sesion": permiso_sin_sesion(),
            "linger": inicio.linger(), "falta": falta}
