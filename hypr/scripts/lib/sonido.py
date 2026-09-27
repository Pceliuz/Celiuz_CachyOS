#!/usr/bin/env python3
"""
hypr/scripts/lib/sonido.py — el sonido del menu rapido: volumen por grupos
(juego / musica / chat), el microfono y la musica que suene (MPRIS).

EL VOLUMEN POR GRUPOS
---------------------
PipeWire sabe de que programa es cada flujo de audio (`pw-dump`), y eso basta
para agruparlos. Lo que NO vale es el PID de la ventana: medido el 2026-09-25,
el flujo de Brave lo abre un subproceso suyo, no el de su ventana. Por eso:

  juego   el flujo es del arbol de procesos de la ventana del juego, o de Wine
          (`wine64-preloader`, un `.exe`): con Proton el sonido sale de ahi.
  chat    el navegador predeterminado (WhatsApp Web, Discord web) y los
          programas de voz conocidos.
  musica  las apps que el usuario anadio al modo gaming y los reproductores
          conocidos.
Lo que no cae en ninguno no se toca (avisos del sistema, el microfono de otro).

El volumen se pone con `wpctl`, en su escala (la cubica, la que ensena todo
el mundo), y se lee de `pw-dump` pasando la lineal a esa escala.

LA MUSICA (MPRIS)
-----------------
Por D-Bus a pelo, sin playerctl: quien clona el repo no tiene por que tenerlo.
Se elige el reproductor que este sonando, y si no, el que este en pausa.
"""

import json
import os
import subprocess

CHAT = {"discord", "vesktop", "webcord", "armcord", "teamspeak", "ts3client",
        "teamspeak3", "mumble", "zoom", "skypeforlinux", "element-desktop",
        "signal-desktop", "telegram-desktop", "whatsapp-for-linux", "zapzap"}
MUSICA = {"spotify", "glassy-music", "rhythmbox", "elisa", "strawberry", "amberol",
          "clementine", "audacious", "deadbeef", "cider", "youtube-music",
          "tidal-hifi", "lollypop", "cantata", "g4music", "gapless"}
WINE = {"wine64-preloader", "wine-preloader", "wine64", "wine", "wineserver"}


def _pw_dump():
    try:
        return json.loads(subprocess.run(["pw-dump"], capture_output=True, text=True,
                                         timeout=3).stdout or "[]")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []


def flujos(dump=None):
    """Los flujos de SALIDA de audio: [{id, nombre, binario, pid, volumen}]."""
    salida = []
    for o in (dump if dump is not None else _pw_dump()):
        if o.get("type") != "PipeWire:Interface:Node":
            continue
        info = o.get("info") or {}
        p = info.get("props") or {}
        if p.get("media.class") != "Stream/Output/Audio":
            continue
        volumen = None
        for prop in (info.get("params") or {}).get("Props") or []:
            if isinstance(prop, dict) and prop.get("channelVolumes"):
                volumen = max(prop["channelVolumes"]) ** (1 / 3)
        try:
            pid = int(p.get("application.process.id") or 0)
        except (TypeError, ValueError):
            pid = 0
        salida.append({"id": o.get("id"), "nombre": p.get("application.name") or "",
                       "binario": p.get("application.process.binary") or "",
                       "pid": pid, "volumen": volumen})
    return salida


def descendientes(pids):
    """Los pids dados y todos sus hijos, nietos... (leyendo /proc)."""
    hijos = {}
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open("/proc/%s/stat" % pid) as fh:
                ppid = int(fh.read().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            continue
        hijos.setdefault(ppid, []).append(int(pid))
    todos, pendientes = set(), [p for p in pids if p]
    while pendientes:
        p = pendientes.pop()
        if p in todos:
            continue
        todos.add(p)
        pendientes.extend(hijos.get(p, []))
    return todos


def clasificar(flujo, pids_juego, chat, musica):
    """juego | chat | musica | None para un flujo. `chat` y `musica` son
    conjuntos de nombres de programa (en minusculas); se compara con el binario
    y con el nombre de la aplicacion."""
    binario = (flujo.get("binario") or "").lower()
    nombre = (flujo.get("nombre") or "").lower()
    if flujo.get("pid") in pids_juego or binario in WINE or binario.endswith(".exe") \
            or nombre.endswith(".exe"):
        return "juego"
    if binario in chat or nombre in chat:
        return "chat"
    if binario in musica or nombre in musica:
        return "musica"
    return None


def grupos(pids_juego, chat_extra=(), musica_extra=(), dump=None):
    """{"juego": [flujos], "chat": [...], "musica": [...]}."""
    chat = CHAT | {x.lower() for x in chat_extra if x}
    musica = MUSICA | {x.lower() for x in musica_extra if x}
    arbol = descendientes(pids_juego)
    salida = {"juego": [], "chat": [], "musica": []}
    for f in flujos(dump):
        g = clasificar(f, arbol, chat, musica)
        if g:
            salida[g].append(f)
    return salida


def poner_volumen(flujos_, valor):
    valor = max(0.0, min(1.0, valor))
    for f in flujos_:
        try:
            subprocess.run(["wpctl", "set-volume", str(f["id"]), "%.2f" % valor],
                           capture_output=True, timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            return                      # sin wpctl (sin WirePlumber) no hay volumen que tocar


def micro():
    """(volumen, silenciado) del microfono por defecto, o None si no hay."""
    try:
        r = subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"],
                           capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0 or "Volume:" not in r.stdout:
        return None
    try:
        vol = float(r.stdout.split("Volume:")[1].split()[0])
    except (ValueError, IndexError):
        vol = 0.0
    return vol, "MUTED" in r.stdout


def alternar_micro():
    try:
        subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"],
                       capture_output=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        pass


# --- MPRIS ---------------------------------------------------------------------
def _bus():
    from gi.repository import Gio
    return Gio.bus_get_sync(Gio.BusType.SESSION, None)


def _llamar(bus, nombre, ruta, interfaz, metodo, args=None, tipo=None):
    from gi.repository import Gio, GLib
    return bus.call_sync(nombre, ruta, interfaz, metodo, args,
                         GLib.VariantType(tipo) if tipo else None,
                         Gio.DBusCallFlags.NONE, 1000, None)


def reproductor():
    """El reproductor a enseñar (el que suena, o el que este en pausa), o None."""
    todos = reproductores()
    return todos[0] if todos else None


def reproductores():
    """Todos los reproductores con algo puesto: [{bus, pid, titulo, artista,
    portada, estado}], el que suena primero. El `pid` es el del proceso dueño
    del nombre en el bus (el de la ventana de su app: medido con Brave y Glassy
    Music), para saber de que app es cada uno."""
    try:
        from gi.repository import GLib
        bus = _bus()
        nombres = _llamar(bus, "org.freedesktop.DBus", "/org/freedesktop/DBus",
                          "org.freedesktop.DBus", "ListNames", None, "(as)").unpack()[0]
    except Exception:  # noqa: BLE001 — sin bus de sesion no hay musica que enseñar
        return None
    candidatos = []
    for n in nombres:
        if not n.startswith("org.mpris.MediaPlayer2.") or n.endswith(".playerctld"):
            continue
        try:
            props = _llamar(bus, n, "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties",
                            "GetAll", GLib.Variant("(s)", ("org.mpris.MediaPlayer2.Player",)),
                            "(a{sv})").unpack()[0]
        except Exception:  # noqa: BLE001 — un reproductor que no contesta se salta
            continue
        try:
            pid = _llamar(bus, "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                          "GetConnectionUnixProcessID", GLib.Variant("(s)", (n,)), "(u)").unpack()[0]
        except Exception:  # noqa: BLE001 — sin pid, sigue sirviendo para los controles
            pid = 0
        meta = props.get("Metadata") or {}
        estado = props.get("PlaybackStatus") or "Stopped"
        artistas = meta.get("xesam:artist") or []
        portada = meta.get("mpris:artUrl") or ""
        candidatos.append({
            "bus": n,
            "pid": pid,
            "titulo": meta.get("xesam:title") or "",
            "artista": ", ".join(artistas) if isinstance(artistas, list) else str(artistas),
            "portada": portada[7:] if portada.startswith("file://") else "",
            "estado": estado,
        })
    orden = {"Playing": 0, "Paused": 1}
    candidatos = [c for c in candidatos if c["titulo"] or c["estado"] == "Playing"]
    candidatos.sort(key=lambda c: orden.get(c["estado"], 2))
    return candidatos


def controlar(bus_nombre, metodo):
    """PlayPause | Next | Previous."""
    try:
        _llamar(_bus(), bus_nombre, "/org/mpris/MediaPlayer2",
                "org.mpris.MediaPlayer2.Player", metodo)
    except Exception:  # noqa: BLE001 — el reproductor pudo cerrarse entre medias
        pass
