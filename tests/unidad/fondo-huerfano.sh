#!/usr/bin/env bash
# tests/unidad/fondo-huerfano.sh — el demonio del fondo se aparta cuando su
# Hyprland ya no esta.
#
# POR QUE EXISTE ESTA PRUEBA
# --------------------------
# wallpaper-pause.py se lanza con `setsid`, asi que NO muere con el Hyprland que
# lo arranco, y su instancia se fija al empezar (HYPR_DIR). Un demonio que
# sobrevive a su compositor no es inofensivo: es PEOR que no tener ninguno,
# porque wallpaper.sh decide si hace falta lanzar uno con un `pgrep` por nombre,
# el zombi contesta que si, y la sesion viva se queda sin nadie que pause el
# fondo. Ademas el FIFO de ordenes tambien es suyo, asi que los `hold` y
# `release` del bloqueo y de CeliuzPaper se los traga sin leerlos.
#
# Paso de verdad el 2026-08-04, y el sintoma despista: parece que el demonio
# funciona al reves —el video corriendo con ventanas encima y quieto en el
# bloqueo— cuando lo que hay es un demonio de otra sesion ocupando el sitio.
#
# Las dos mitades importan. Que se vaya cuando debe, y que NO se vaya mientras
# su Hyprland siga ahi: un demonio que se rinde a la primera dejaria el
# escritorio sin ahorro y sin decir nada.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

# Lo peligroso, sustituido: si algo saliera mal, este demonio sabe matar y
# relanzar mpvpaper, y eso en la sesion de verdad te deja sin fondo.
binario_falso pkill
binario_falso pgrep 1
binario_falso mpvpaper
binario_falso notify-send

# Se corre desde una COPIA del repo a proposito. El demonio saca su raiz de la
# ruta de su propio .py, y en la copia no hay `hypr/wallpapers/current`
# (copiar_repo deja fuera los videos), asi que la parte de "resucitar mpvpaper"
# no se dispara y esta prueba se queda en lo suyo.
COPIA="$(copiar_repo)"
DEMONIO="$COPIA/hypr/scripts/wallpaper-pause.py"
SIG="instancia-de-mentira"
mkdir -p "$XDG_RUNTIME_DIR/hypr/$SIG"

titulo "1. Su Hyprland ya no esta: se aparta"
# El directorio de la instancia existe pero no hay nadie escuchando, que es
# exactamente como queda una instancia muerta: Hyprland no siempre limpia su
# carpeta al irse, asi que "existe la carpeta" NO sirve para saber si vive.
inicio=$(date +%s)
WALLPAPER_PAUSE_ABANDONO=2 HYPRLAND_INSTANCE_SIGNATURE="$SIG" \
    timeout 20 "$DEMONIO" >"$TMP/huerfano.log" 2>&1
codigo=$?
tardo=$(( $(date +%s) - inicio ))

if [ "$codigo" -eq 124 ]; then
    fallo "se va solo cuando no hay compositor" \
          "seguia dando vueltas a los 20 s (asi es como acaba ocupando el sitio)"
else
    ok "se va solo cuando no hay compositor (a los ${tardo} s)"
fi
afirmar_igual "0" "$codigo" "se va por su propio pie, no a golpes"
afirmar_contiene "$TMP/huerfano.log" "dejo el sitio" \
    "y deja dicho por que se fue"

titulo "2. Su Hyprland sigue vivo: se queda"
# Un socket que solo acepta y calla. Al demonio le basta con poder conectarse:
# lo que se prueba aqui es que no confunda "no pasa nada" con "no hay nadie".
SIG2="instancia-viva"
mkdir -p "$XDG_RUNTIME_DIR/hypr/$SIG2"
python3 - "$XDG_RUNTIME_DIR/hypr/$SIG2/.socket2.sock" <<'PY' &
import socket, sys, time
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.bind(sys.argv[1])
s.listen(8)
time.sleep(120)
PY
FALSO_HYPR=$!
sleep 0.5

WALLPAPER_PAUSE_ABANDONO=2 HYPRLAND_INSTANCE_SIGNATURE="$SIG2" \
    "$DEMONIO" >"$TMP/vivo.log" 2>&1 &
VIVO=$!
sleep 6   # tres veces el ABANDONO de la prueba

if kill -0 "$VIVO" 2>/dev/null; then
    ok "sigue en pie mientras haya compositor (6 s, con ABANDONO=2)"
else
    fallo "no se rinde con su Hyprland delante" \
          "se murio a los 6 s: $(cat "$TMP/vivo.log")"
fi

kill "$VIVO" 2>/dev/null
kill "$FALSO_HYPR" 2>/dev/null
wait "$VIVO" "$FALSO_HYPR" 2>/dev/null

titulo "3. No toco nada de tu equipo"
afirmar_intacta_la_casa_real

resumen
