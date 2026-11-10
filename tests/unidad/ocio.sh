#!/usr/bin/env bash
# tests/unidad/ocio.sh - la clasificacion de «ocio» del modo estudio.
#
# El modo estudio aparta lo que no es estudiar: reproductores (video y
# musica), chats y redes. Se queda el navegador (documentacion), el editor,
# la terminal, la pizarra y Celiuz.
#
# Se prueba con .desktop de mentira en un XDG_DATA_HOME temporal: la maquina
# de quien corre esto no tiene por que tener vlc ni discord.
set -u

AQUI=$(cd "$(dirname "$0")/../.." && pwd)
LIB="$AQUI/hypr/scripts/lib"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

APP="$TMP/datos/applications"
mkdir -p "$APP"

# --- Lo que SI es ocio (se aparta) -------------------------------------------
escribir() {
    printf '[Desktop Entry]\nType=Application\nName=%s\nExec=/bin/true\nCategories=%s\n' \
        "$1" "$2" > "$APP/$3.desktop"
}
escribir "VLC"          "AudioVideo;Player;Video;"              vlc
escribir "Spotify"      "AudioVideo;Audio;Music;Player;"        spotify
escribir "Discord"      "Network;InstantMessaging;Chat;"        discord
escribir "Telegram"     "Network;"                              telegram-desktop
escribir "Transmission" "Network;FileTransfer;P2P;"              transmission-gtk

# --- Lo que NO es ocio (se queda) --------------------------------------------
escribir "Firefox"      "Network;WebBrowser;"                   firefox
escribir "VS Code"      "Development;IDE;TextEditor;"            code
escribir "Alacritty"    "System;TerminalEmulator;"               Alacritty
escribir "Pizarra"      "Development;"                           celiuzpizarra

# --- Un juego (tambien ocio) -------------------------------------------------
escribir "Juego"        "Game;"                                 jueguito

fallos=0
comprobar() {  # comprobar ID ESPERADO(1=ocio 0=se queda)
    esperado=$2
    obtenido=$(XDG_DATA_HOME="$TMP/datos" XDG_DATA_DIRS="/no-existe" \
        python3 -c "
import sys
sys.path.insert(0, '$LIB')
import ocio
print(1 if ocio.es_ocio_id('$1') else 0)
" 2>&1) || true
    if [ "$obtenido" != "$esperado" ]; then
        echo "FALLO $1: esperaba $esperado, salio '$obtenido'"
        fallos=$((fallos + 1))
    fi
}

# Ocio: reproductores, chats, redes y juegos
comprobar vlc 1
comprobar spotify 1
comprobar discord 1
comprobar telegram-desktop 1
comprobar transmission-gtk 1
comprobar jueguito 1
# Se queda: el navegador, el editor, la terminal y la pizarra
comprobar firefox 0
comprobar code 0
comprobar Alacritty 0
comprobar celiuzpizarra 0

if [ "$fallos" -ne 0 ]; then
    echo "ocio.sh: $fallos fallos"
    exit 1
fi
echo "ocio.sh: ok"
