#!/usr/bin/env python3
"""
~/dotfiles/hypr/scripts/lib/apps.py

Que navegador y que terminal usa ESTA maquina.

Existe por un fallo concreto: este repo es publico, y el dock venia con las apps
del autor cableadas dentro (Brave, Steam y dos juegos suyos lanzados por
steam://rungameid). Al clonarlo en otro equipo eso son iconos ajenos —cuando no
directamente muertos—, porque el dock generado —dock.jsonc y dock-icons.css—
tambien estaba versionado, con rutas absolutas a /home/celiuz que en otra maquina
no existen. El dock ya no trae apps de nadie: arranca con
dos, terminal y navegador, averiguadas aqui, y a partir de ahi las pone el
usuario con el clic derecho.

COMO SE AVERIGUA CADA UNA
-------------------------
El navegador SI tiene estandar: xdg-settings y xdg-mime dicen cual es el
predeterminado y devuelven su .desktop, de donde salen el nombre, el icono y el
comando ya listos y correctos. La variable $BROWSER se mira la ULTIMA porque
miente: en CachyOS viene puesta a "firefox" de fabrica aunque el navegador
predeterminado sea otro (comprobado en esta maquina: xdg-settings decia
brave-browser.desktop y $BROWSER decia firefox).

La terminal NO tiene estandar equivalente —no existe "xdg-settings get
default-terminal"—, asi que se mira $TERMINAL y, si no dice nada, se recorre
CONOCIDAS por orden y se coge la primera instalada.

Uso desde la terminal (lo llama instalar.sh, que es bash y no puede importar):
    apps.py terminal          imprime el comando, o nada si no hay
    apps.py navegador --json  imprime {"label":..,"cmd":..,"icon_name":..}
"""

import json
import os
import shutil
import subprocess
import sys

# Por orden de preferencia. No es un ranking de calidad: las primeras son las
# que se configuran solas sin fichero aparte, que es lo que conviene cuando esto
# acierta sin preguntar.
CONOCIDAS = [
    "kitty", "alacritty", "foot", "ghostty", "wezterm", "konsole",
    "gnome-terminal", "xfce4-terminal", "tilix", "terminator", "urxvt", "xterm",
]

# Los .desktop no siempre se llaman como el binario.
IDENTIFICADORES = {
    "konsole": ["org.kde.konsole"],
    "gnome-terminal": ["org.gnome.Terminal"],
    "wezterm": ["org.wezfurlong.wezterm"],
    "ghostty": ["com.mitchellh.ghostty"],
    "foot": ["foot", "footclient"],
}

# Codigos de campo del estandar de .desktop: se sustituyen por los ficheros o
# URLs que se le pasen a la app. Sin argumentos hay que QUITARLOS, o se lanzaria
# el navegador con un literal "%U" como si fuera una direccion.
CODIGOS = ("%f", "%F", "%u", "%U", "%d", "%D", "%n", "%N", "%i", "%c", "%k",
           "%v", "%m")


def _dirs_datos():
    """Las carpetas donde viven los .desktop, en orden de prioridad XDG."""
    casa = os.path.expanduser("~/.local/share")
    dirs = [os.environ.get("XDG_DATA_HOME") or casa]
    resto = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    dirs += resto.split(":")
    return [os.path.join(d, "applications") for d in dirs if d]


def buscar_desktop(ident):
    """Ruta del .desktop a partir de su identificador (con o sin extension)."""
    if not ident:
        return None
    if not ident.endswith(".desktop"):
        ident += ".desktop"
    for base in _dirs_datos():
        ruta = os.path.join(base, ident)
        if os.path.isfile(ruta):
            return ruta
        # Los .desktop de subcarpeta llevan el subdirectorio en el id con un
        # guion: kde-org.kde.konsole.desktop vive en kde/org.kde.konsole.desktop.
        suelto = os.path.join(base, ident.replace("-", "/", 1))
        if os.path.isfile(suelto):
            return suelto
    return None


def limpiar_exec(linea):
    """El comando de un Exec=, sin los codigos de campo."""
    partes = [p for p in linea.split() if p not in CODIGOS]
    # Un codigo pegado a otra cosa ("--url=%u") se queda sin el codigo.
    limpias = []
    for parte in partes:
        for codigo in CODIGOS:
            parte = parte.replace(codigo, "")
        if parte:
            limpias.append(parte)
    return " ".join(limpias).strip()


def leer_desktop(ruta):
    """Nombre, icono y comando de un .desktop. None si no sirve.

    Se lee SOLO el grupo [Desktop Entry]. Hace falta acotarlo: los .desktop
    traen ademas grupos [Desktop Action ...] con sus propios Name y Exec —el de
    Brave tiene uno "New Window"— y leerlos de corrido se queda con el ultimo,
    que es el equivocado.
    """
    try:
        with open(ruta, encoding="utf-8", errors="replace") as fh:
            lineas = fh.read().splitlines()
    except OSError:
        return None

    datos = {}
    dentro = False
    for linea in lineas:
        linea = linea.strip()
        if linea.startswith("["):
            if dentro:
                break              # empieza otro grupo: se acabo lo nuestro
            dentro = linea == "[Desktop Entry]"
            continue
        if not dentro or "=" not in linea or linea.startswith("#"):
            continue
        clave, valor = linea.split("=", 1)
        # Se ignoran las traducciones (Name[es]): la clave pelada vale para todos
        # y ademas es la que coincide con lo que el usuario ve en su idioma solo
        # si el sistema lo esta en ese idioma. Menos sorpresas asi.
        if clave not in datos:
            datos[clave] = valor.strip()

    comando = limpiar_exec(datos.get("Exec", ""))
    if not comando:
        return None
    return {
        "label": datos.get("Name") or os.path.basename(ruta)[:-8],
        "cmd": comando,
        "icon_name": datos.get("Icon") or "",
        "try_exec": datos.get("TryExec", ""),
    }


def _existe(comando):
    """Si el primer trozo de un comando se puede ejecutar de verdad."""
    if not comando:
        return False
    primero = comando.split()[0]
    return bool(shutil.which(primero)) or os.access(primero, os.X_OK)


def _preguntar(orden):
    try:
        salida = subprocess.run(orden, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return salida.stdout.strip() if salida.returncode == 0 else ""


def _desde_desktop(ident):
    """Entrada de dock a partir de un id de .desktop, si su comando existe."""
    ruta = buscar_desktop(ident)
    if not ruta:
        return None
    entrada = leer_desktop(ruta)
    if not entrada:
        return None
    # TryExec es justo para esto: el .desktop puede quedarse tras desinstalar.
    if entrada["try_exec"] and not _existe(entrada["try_exec"]):
        return None
    if not _existe(entrada["cmd"]):
        return None
    entrada.pop("try_exec", None)
    return entrada


def _desde_binario(binario, etiqueta=None):
    """Entrada de dock a partir del nombre de un ejecutable.

    Se intenta ademas encontrar su .desktop, que es de donde salen el nombre
    bonito y el icono; si no aparece, el dock caera al glifo generico y seguira
    funcionando, que es lo que importa.
    """
    if not shutil.which(binario):
        return None
    for ident in IDENTIFICADORES.get(binario, []) + [binario]:
        entrada = _desde_desktop(ident)
        if entrada:
            return entrada
    return {"label": etiqueta or binario, "cmd": binario, "icon_name": binario}


def navegador():
    """El navegador predeterminado, listo para meter en el dock. None si no hay."""
    for ident in (_preguntar(["xdg-settings", "get", "default-web-browser"]),
                  _preguntar(["xdg-mime", "query", "default",
                              "x-scheme-handler/https"])):
        # xdg-mime puede devolver varios separados por ';'.
        for uno in ident.split(";"):
            entrada = _desde_desktop(uno.strip())
            if entrada:
                return entrada

    # $BROWSER va la ultima a proposito (ver la cabecera): puede ser una lista
    # separada por ':' y puede nombrar algo que no esta instalado.
    for binario in (os.environ.get("BROWSER") or "").split(":"):
        binario = binario.strip().split()[0] if binario.strip() else ""
        entrada = _desde_binario(binario) if binario else None
        if entrada:
            return entrada
    return None


def terminal():
    """La terminal de esta maquina, lista para meter en el dock. None si no hay."""
    pedida = (os.environ.get("TERMINAL") or "").strip()
    if pedida:
        entrada = _desde_binario(pedida.split()[0])
        if entrada:
            return entrada
    for binario in CONOCIDAS:
        entrada = _desde_binario(binario)
        if entrada:
            return entrada
    return None


def main():
    orden = sys.argv[1] if len(sys.argv) > 1 else ""
    if orden not in ("terminal", "navegador"):
        sys.exit(f"apps.py: dime «terminal» o «navegador» (me diste «{orden}»)")
    entrada = terminal() if orden == "terminal" else navegador()
    if not entrada:
        sys.exit(1)               # sin nada que decir: el que llama lo maneja
    if "--json" in sys.argv:
        print(json.dumps(entrada, ensure_ascii=False))
    else:
        print(entrada["cmd"])


if __name__ == "__main__":
    main()
