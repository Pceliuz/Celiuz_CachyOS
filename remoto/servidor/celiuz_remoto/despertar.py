"""
remoto/servidor/celiuz_remoto/despertar.py — encender a distancia (Wake-on-LAN).

Fase 8 (remoto/DISEÑO.md, «Extras»). Una PC apagada no contesta a nadie, asi
que no se puede despertar a si misma: la despierta OTRO equipo encendido de la
misma red de casa (la laptop, por ejemplo), mandando el «paquete magico» a la
MAC de la tarjeta de cable. El celular le pide a la laptop «despierta a la PC»
por Tailscale, y la laptop lo grita por la red de casa.

Dos piezas:
  - info():      lo de ESTE equipo que hace falta para despertarlo despues: la
                 MAC de su tarjeta de cable y si tiene pinta de poder. Lo
                 guarda el celular al entrar (/v0/equipo).
  - despertar(): mandar el paquete a otra MAC, por todas las redes de cable y
                 wifi de este equipo (no por Tailscale: el paquete no cruza
                 routers, tiene que salir a la red de casa).

LA TARJETA es la de cable de la placa, no «la de la ruta por defecto»: el
Wake-on-LAN lo hace la tarjeta con el equipo apagado, y eso no lo hace ni el
wifi (casi nunca) ni un adaptador USB (sin corriente al apagar). En la PC del
autor la salida a internet iba por un USB (enp22s0f0u1) y la que vale es
enp34s0.

«¿Esta activado?» no se puede saber sin root (`ethtool` solo enseña la linea
de Wake-on a root), asi que la respuesta tiene tres salidas, como en el resto
del repo: «si», «no» o «no_lo_se», con el porque.
"""

import json
import os
import re
import socket
import subprocess

MAC = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")


def _leer(ruta):
    try:
        with open(ruta, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return None


def _es_de_placa(dev):
    """Cable y fisica: con dispositivo, sin wireless, no USB, no virtual."""
    base = f"/sys/class/net/{dev}"
    if not os.path.exists(f"{base}/device") or os.path.exists(f"{base}/wireless"):
        return False
    if "/usb" in os.path.realpath(f"{base}/device"):
        return False
    return _leer(f"{base}/type") == "1"      # ARPHRD_ETHER


def tarjeta():
    """La tarjeta de cable de la placa (la primera con cable puesto, si hay
    varias), o None."""
    try:
        devs = sorted(os.listdir("/sys/class/net"))
    except OSError:
        return None
    de_placa = [d for d in devs if _es_de_placa(d)]
    con_cable = [d for d in de_placa if _leer(f"/sys/class/net/{d}/carrier") == "1"]
    return (con_cable or de_placa or [None])[0]


def _wol_ethtool(dev):
    try:
        r = subprocess.run(["ethtool", dev], capture_output=True, text=True, timeout=5,
                           check=False, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r"^\s*Wake-on:\s*(\S+)", r.stdout, re.MULTILINE)
    return m.group(1) if m else None


def info():
    """{"mac", "tarjeta", "wol": si|no|no_lo_se, "motivo"} de este equipo."""
    dev = tarjeta()
    if dev is None:
        return {"mac": None, "tarjeta": None, "wol": "no",
                "motivo": "este equipo no tiene tarjeta de red de cable"}
    mac = (_leer(f"/sys/class/net/{dev}/address") or "").lower()
    salida = {"mac": mac if MAC.match(mac) else None, "tarjeta": dev}
    modo = _wol_ethtool(dev)
    if modo is not None:
        if "g" in modo:
            salida.update(wol="si", motivo=f"{dev}: Wake-on-LAN activado (magic packet)")
        else:
            salida.update(wol="no", motivo=f"{dev}: Wake-on-LAN apagado (ethtool dice «{modo}»)")
    else:
        salida.update(wol="no_lo_se", motivo=f"{dev}: sin root no se puede leer si está activado")
    if _leer(f"/sys/class/net/{dev}/carrier") != "1":
        salida["motivo"] += "; ahora mismo no tiene el cable conectado"
        if salida["wol"] == "si":
            salida["wol"] = "no_lo_se"
    return salida


def paquete(mac):
    return b"\xff" * 6 + bytes.fromhex(mac.replace(":", "")) * 16


def _difusiones():
    """Las direcciones de difusion de las redes IPv4 de este equipo, menos
    Tailscale y el bucle local: por ahi el paquete no llega a nadie de casa."""
    try:
        r = subprocess.run(["ip", "-j", "-4", "addr"], capture_output=True, text=True, timeout=5,
                           check=False, stdin=subprocess.DEVNULL)
        redes = json.loads(r.stdout or "[]")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        redes = []
    salida = []
    for red in redes:
        if red.get("ifname") in ("lo", "tailscale0") or red.get("link_type") == "none":
            continue
        for a in red.get("addr_info", []):
            if a.get("broadcast"):
                salida.append(a["broadcast"])
    return salida


def despertar(mac, puerto=9):
    """Manda el paquete magico. Devuelve por donde salio (las difusiones)."""
    mac = str(mac or "").lower().replace("-", ":")
    if not MAC.match(mac):
        raise ValueError("eso no es una MAC (aa:bb:cc:dd:ee:ff)")
    datos = paquete(mac)
    destinos = [(d, p) for d in dict.fromkeys(_difusiones() + ["255.255.255.255"]) for p in (puerto, 7)]
    # Solo para las pruebas: a donde mandarlo en vez de gritarlo por la red de
    # casa de quien las corre («127.0.0.1:40009»).
    prueba = os.environ.get("CELIUZ_REMOTO_WOL_DESTINO")
    if prueba:
        h, _, p = prueba.rpartition(":")
        destinos = [(h, int(p))]
    enviados = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for d, p in destinos:
            try:
                s.sendto(datos, (d, p))
                enviados.append(f"{d}:{p}")
            except OSError:
                pass
    return enviados
