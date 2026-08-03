#!/usr/bin/env python3
"""
~/dotfiles/hypr/scripts/lib/juegos.py

Decide QUE se puede congelar al bloquear la pantalla y que no.

EL PROBLEMA
-----------
Al bloquear queremos parar las aplicaciones (que no gasten CPU ni puedan sacar
ventanas por encima del bloqueo), pero NO los juegos: si dejaste una partida
corriendo, congelarla te la tira. Y una lista fija de juegos escrita a mano
envejece: cada juego nuevo habria que anadirlo.

Asi que un proceso se reconoce como juego por CAPAS, de mas fiable a mas
generica, sin lista que mantener:

  1. STEAM      — el scope viene de Steam, o su linea de comandos pasa por
                  `steamapps` / `SteamLaunch`. Los juegos de Steam cuelgan de ahi.
  2. ANANICY    — `cachyos-ananicy-rules` trae ~13.500 ejecutables clasificados
                  como `"type": "Game"` (2.194 nativos + 11.273 de Wine/Proton),
                  y pacman lo actualiza solo. Es una base de datos de juegos que
                  ya tienes instalada y que se mantiene sola. Hytale esta:
                  { "name": "HytaleClient", "type": "Game" }.
  3. FLATPAK    — por `Categories=Game` del .desktop. Cubre launchers propios
                  aunque el ejecutable no este en ananicy (el caso de Hytale, que
                  es flatpak `com.hypixel.HytaleLauncher`).
  4. PANTALLA COMPLETA — red de ultima hora: lo que este a pantalla completa en
                  el momento de bloquear se salva. Pilla un juego recien salido
                  que ninguna base de datos conozca todavia.
                  AVISO: un video a pantalla completa tambien se salva. Es el
                  precio de esta capa; se apaga con CAPA_PANTALLA_COMPLETA.

Ademas hay un JSON de excepciones a mano (`hypr/congelar-excepciones.json`),
mismo patron que `dock-apps.json`, para que tanto tu como el asistente podais
meter o sacar algo sin tocar este archivo.

POR QUE SCOPES DE SYSTEMD Y NO PIDS SUELTOS
-------------------------------------------
Congelar se hace con el *freezer* de cgroup v2 (`systemctl --user freeze`), que
es atomico y reversible, mucho mejor que repartir SIGSTOP a mano por un arbol de
procesos que puede estar creando hijos justo en ese momento.

Pero eso obliga a que cada aplicacion tenga su propio cgroup. Comprobado el
2026-07-27: sin `uwsm app`, casi todo cae en
`session.slice/wayland-wm@hyprland.desktop.service` — el MISMO cgroup que
Hyprland, waybar y mpvpaper. Congelar ese cgroup congelaria el compositor y
dejaria la pantalla muerta. Por eso las apps se lanzan con `uwsm app --` (ver
fuzzel.ini y gen-dock.py) y por eso aqui solo se consideran unidades `.scope`:
los servicios de la sesion (portales, pipewire, el propio compositor) no se
tocan NUNCA.
"""

import json
import os
import re
import subprocess
import sys

# --- Que se considera congelable -------------------------------------------
# Solo unidades .scope. Un .service de la sesion es infraestructura (portales,
# pipewire, dbus, el compositor); pararlo rompe cosas y no ahorra nada.
# Estas ademas se descartan aunque fueran scopes, por si acaso.
NUNCA_JAMAS = re.compile(
    r"(wayland-wm|init\.scope|dbus|pipewire|wireplumber|xdg-|portal|"
    r"at-spi|dconf|systemd|gvfs|polkit|gnome-keyring)",
    re.I,
)

# Terminales: el usuario pidio expresamente que NO se congelen, para no tirarse
# las sesiones SSH de los laboratorios ni las compilaciones que deje andando.
TERMINALES = {"kitty", "foot", "alacritty", "wezterm", "ghostty", "konsole"}

CAPA_PANTALLA_COMPLETA = True

REGLAS_ANANICY = "/etc/ananicy.d"
# La raiz del repo, resolviendo el enlace simbolico: a este script se le puede
# llamar por ~/.config/hypr/... o por ~/.local/bin/..., y realpath() lleva
# hasta el fichero de verdad dentro del repo, se haya clonado donde se haya
# clonado. Antes ponia "~/dotfiles/...", que obligaba a clonar justo ahi.
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
EXCEPCIONES = os.path.join(RAIZ, "hypr/congelar-excepciones.json")

# Rastros de Steam en la linea de comandos de un juego lanzado desde Steam.
HUELLA_STEAM = re.compile(r"(steamapps|SteamLaunch|steam_app_|/steam/|proton)", re.I)


# --- Capa 2: la base de datos de ananicy ------------------------------------
_cache_ananicy = None


def nombres_de_juego():
    """Todos los ejecutables que ananicy clasifica como `"type": "Game"`.

    Se devuelven en minusculas y sin `.exe` para poder comparar contra el `comm`
    del kernel (que ademas viene cortado a 15 caracteres) y contra el nombre del
    ejecutable, que si es completo.
    """
    global _cache_ananicy
    if _cache_ananicy is not None:
        return _cache_ananicy

    nombres = set()
    patron = re.compile(r'"name"\s*:\s*"([^"]+)"')
    for raiz, _, ficheros in os.walk(os.path.join(REGLAS_ANANICY, "00-default", "Games")):
        for f in ficheros:
            if not f.endswith(".rules"):
                continue
            try:
                with open(os.path.join(raiz, f), encoding="utf-8", errors="replace") as fh:
                    for linea in fh:
                        if '"Game"' not in linea:
                            continue
                        m = patron.search(linea)
                        if m:
                            n = m.group(1).strip().lower()
                            nombres.add(n)
                            if n.endswith(".exe"):
                                nombres.add(n[:-4])
                            # El kernel corta `comm` a 15 caracteres; guardamos
                            # tambien la version corta o no casaria nunca con los
                            # nombres largos (los hay de hasta 59).
                            if len(n) > 15:
                                nombres.add(n[:15])
            except OSError:
                continue
    _cache_ananicy = nombres
    return nombres


# --- Capa 3: flatpaks marcados como juego -----------------------------------
_cache_flatpak = None


def flatpaks_de_juego():
    """IDs de flatpak cuyo .desktop declara `Categories=...Game...`."""
    global _cache_flatpak
    if _cache_flatpak is not None:
        return _cache_flatpak

    ids = set()
    directorios = [
        "/var/lib/flatpak/exports/share/applications",
        os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
    ]
    for d in directorios:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if not f.endswith(".desktop"):
                continue
            try:
                with open(os.path.join(d, f), encoding="utf-8", errors="replace") as fh:
                    texto = fh.read()
            except OSError:
                continue
            for linea in texto.splitlines():
                if linea.startswith("Categories=") and "game" in linea.lower():
                    ids.add(f[:-len(".desktop")].lower())
                    break
    _cache_flatpak = ids
    return ids


# --- Capa 4: lo que este a pantalla completa --------------------------------
def pids_a_pantalla_completa():
    """PIDs de las ventanas que Hyprland reporta a pantalla completa ahora."""
    try:
        salida = subprocess.run(
            ["hyprctl", "clients", "-j"], capture_output=True, text=True, timeout=3
        ).stdout
        return {c["pid"] for c in json.loads(salida) if c.get("fullscreen")}
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        return set()


# --- Excepciones a mano ------------------------------------------------------
def excepciones():
    """{'nunca_congelar': [...], 'siempre_congelar': [...]} con subcadenas."""
    vacio = {"nunca_congelar": [], "siempre_congelar": []}
    try:
        with open(EXCEPCIONES, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return vacio
    for clave in vacio:
        d.setdefault(clave, [])
        d[clave] = [str(x).lower() for x in d[clave]]
    return d


# --- Inventario de scopes ----------------------------------------------------
def _procesos_de(unidad):
    """Radiografia de un scope: (pids, nombres, rutas de ejecutable, cmdlines).

    Se separan a proposito tres cosas que es tentador mezclar:

    - `nombres`  el `comm` del kernel (cortado a 15 caracteres) mas el basename
                 del ejecutable real y el de argv[0]. Es lo que se compara con la
                 base de datos de ananicy.
    - `rutas`    el destino de /proc/PID/exe. Sirve para ver si el binario vive
                 dentro de una biblioteca de Steam.
    - `ordenes`  la linea de comandos ENTERA. Solo se usa para buscar IDs de
                 flatpak, que son cadenas muy especificas.

    Mezclarlas cuesta caro: la primera version buscaba la huella de Steam en
    `ordenes`, y marco como juego el scope de una terminal — porque en esa
    terminal se habian escrito ordenes que mencionaban "steam". El texto que una
    shell tenga en su argv no dice nada de lo que esa shell ES.
    """
    ruta = subprocess.run(
        ["systemctl", "--user", "show", "-p", "ControlGroup", "--value", unidad],
        capture_output=True, text=True,
    ).stdout.strip()
    if not ruta:
        return [], [], [], []
    procs = os.path.join("/sys/fs/cgroup", ruta.lstrip("/"), "cgroup.procs")
    try:
        with open(procs) as fh:
            pids = [int(p) for p in fh.read().split()]
    except (OSError, ValueError):
        return [], [], [], []

    nombres, rutas, ordenes = [], [], []
    for pid in pids:
        try:
            with open(f"/proc/{pid}/comm") as fh:
                nombres.append(fh.read().strip())
        except OSError:
            pass
        try:
            destino = os.readlink(f"/proc/{pid}/exe")
            rutas.append(destino)
            nombres.append(os.path.basename(destino))
        except OSError:
            pass
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as fh:
                crudo = fh.read().split(b"\0")
            if crudo and crudo[0]:
                argv0 = crudo[0].decode("utf-8", "replace")
                # Chromium (y con el Brave) reescribe su propio argv[0] y le mete
                # las banderas dentro, asi que el basename sale como
                # "renderd128 --crashpad-handler-pid=...". Si lleva espacios no
                # es un nombre de programa: se descarta.
                if " " not in argv0:
                    nombres.append(os.path.basename(argv0))
            ordenes.append(b" ".join(crudo).decode("utf-8", "replace"))
        except OSError:
            pass
    return pids, nombres, rutas, ordenes


def inventario():
    """Todos los scopes de usuario congelables, ya clasificados.

    Devuelve una lista de diccionarios:
        unidad, pids, nombres, congelar (bool), motivo (str)
    """
    salida = subprocess.run(
        ["systemctl", "--user", "list-units", "--type=scope", "--all",
         "--no-legend", "--no-pager", "--plain"],
        capture_output=True, text=True,
    ).stdout

    juegos = nombres_de_juego()
    flatpaks = flatpaks_de_juego()
    pantalla = pids_a_pantalla_completa() if CAPA_PANTALLA_COMPLETA else set()
    exc = excepciones()

    resultado = []
    for linea in salida.splitlines():
        unidad = linea.split()[0] if linea.split() else ""
        if not unidad.endswith(".scope") or NUNCA_JAMAS.search(unidad):
            continue

        pids, nombres, rutas, ordenes = _procesos_de(unidad)
        if not pids:
            continue

        bajos = {n.lower() for n in nombres}
        unidad_baja = unidad.lower()
        rutas_bajas = " ".join(rutas).lower()
        ordenes_bajas = " ".join(ordenes).lower()
        # Para las excepciones a mano SI vale mirarlo todo: las escribes tu, y si
        # pones una subcadena demasiado suelta el fallo es tuyo y visible.
        todo = f"{unidad_baja} {rutas_bajas} {ordenes_bajas}"

        motivo, congelar = None, True

        # Excepciones a mano: mandan sobre todo lo demas.
        if any(p in todo or p in bajos for p in exc["nunca_congelar"]):
            motivo, congelar = "excepcion a mano", False
        elif any(p in todo or p in bajos for p in exc["siempre_congelar"]):
            motivo, congelar = "excepcion a mano (forzado)", True
        # Terminales: decision del usuario, para no tirar sus SSH.
        # Se mira tambien el nombre del scope porque kitty se crea el suyo
        # (`kitty-1747-0.scope`) y su proceso principal puede no estar dentro.
        elif (bajos & TERMINALES) or any(t in unidad_baja for t in TERMINALES):
            motivo, congelar = "terminal (SSH a salvo)", False
        # Capa 1: Steam. Solo por el nombre del scope, el ejecutable o su ruta —
        # nunca por texto suelto de la linea de comandos.
        elif ("steam" in unidad_baja or "steam" in bajos
              or HUELLA_STEAM.search(rutas_bajas)):
            motivo, congelar = "capa 1: Steam", False
        # Capa 2
        elif bajos & juegos:
            cual = sorted(bajos & juegos)[0]
            motivo, congelar = f"capa 2: ananicy lo llama juego ({cual})", False
        # Capa 3: los IDs de flatpak son cadenas con punto y muy especificas
        # (com.hypixel.hytalelauncher), asi que buscarlas en la cmdline es seguro.
        elif any(fid in ordenes_bajas or fid in unidad_baja for fid in flatpaks):
            motivo, congelar = "capa 3: flatpak con Categories=Game", False
        # Capa 4
        elif pantalla & set(pids):
            motivo, congelar = "capa 4: a pantalla completa", False
        else:
            motivo = "aplicacion normal"

        resultado.append({
            "unidad": unidad,
            "pids": pids,
            "nombres": sorted(bajos),
            "congelar": congelar,
            "motivo": motivo,
        })
    return resultado


def _cli():
    inv = inventario()
    if not inv:
        print("No hay ningun scope de aplicacion corriendo.")
        print("Si acabas de poner `uwsm app --`, las apps ya abiertas siguen sin scope:")
        print("hay que volver a lanzarlas para que lo tengan.")
        return 0
    ancho = max(len(x["unidad"]) for x in inv)
    for x in inv:
        marca = "CONGELA" if x["congelar"] else "  salva"
        print(f"{marca}  {x['unidad']:<{ancho}}  {x['motivo']}")
        print(f"         {len(x['pids'])} procs: {' '.join(x['nombres'])[:90]}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
