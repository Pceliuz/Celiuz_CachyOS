"""
remoto/servidor/celiuz_remoto/red.py — donde escucha el servicio.

- Escucha SOLO en la IP de Tailscale (`tailscale ip -4`), puerto 47110. Sin
  Tailscale no arranca: nunca cae a 0.0.0.0 ni al wifi de casa.
- Y no se fia ni de Tailscale: la IP que conteste tiene que ser de su rango
  (100.64.0.0/10, el CGNAT que reparte) o de bucle local. Cualquier otra cosa
  es un error, aunque la haya dicho el propio `tailscale`.
- El canal USB (127.0.0.1:47111) lo abre solo la app de la PC, unos minutos
  (servidor.py, VentanaUsb).
"""

import ipaddress
import socket
import subprocess

RANGO_TAILSCALE = ipaddress.ip_network("100.64.0.0/10")


class SinRed(Exception):
    pass


def direccion_segura(texto):
    """True si es una IP en la que se puede escuchar sin abrirse al mundo."""
    try:
        ip = ipaddress.ip_address(texto)
    except ValueError:
        return False
    return ip.version == 4 and (ip in RANGO_TAILSCALE or ip.is_loopback)


def ip_tailscale():
    """La IPv4 de Tailscale de este equipo, o SinRed con el porque."""
    try:
        r = subprocess.run(["tailscale", "ip", "-4"], capture_output=True,
                           text=True, timeout=5, check=False)
    except FileNotFoundError:
        raise SinRed("no está instalado tailscale (sudo pacman -S tailscale)") from None
    except subprocess.TimeoutExpired:
        raise SinRed("tailscale no contesta") from None
    if r.returncode != 0:
        detalle = (r.stderr or r.stdout).strip().splitlines()
        raise SinRed("tailscale no está conectado"
                     + (f": {detalle[0]}" if detalle else "")
                     + " (prueba: sudo systemctl enable --now tailscaled && tailscale up)")
    for linea in r.stdout.split():
        if direccion_segura(linea):
            return linea
    raise SinRed(f"tailscale no dio ninguna IP de su rango: {r.stdout.strip()!r}")


def nombre_equipo():
    return socket.gethostname()
