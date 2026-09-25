#!/usr/bin/env bash
# ~/dotfiles/hypr/scripts/screenshot.sh
#
# Capturas de pantalla.
#
#   screenshot.sh            recortar una zona con el raton (lo normal)
#   screenshot.sh --full     la pantalla entera, sin preguntar
#   screenshot.sh --ventana  solo la ventana que tenga el foco
#
# La captura va a DOS sitios a la vez, siempre:
#   - al portapapeles, para poder pegarla al instante con Ctrl+V
#   - a un archivo en ~/Imágenes/capturas/, para no perderla si copias otra cosa
#
# Se apoya en grim (capturar), slurp (elegir la zona) y wl-clipboard (copiar),
# los tres del repo oficial y ya instalados.

set -uo pipefail

DESTINO="$(xdg-user-dir PICTURES 2>/dev/null || echo "$HOME/Imágenes")/capturas"

# El nombre lleva el modo y, si ya existe, un numero detras. Dos capturas en el
# mismo segundo son normales (recortas, no te gusta, recortas otra vez) y sin esto
# la segunda pisaba a la primera.
nombre_libre() {
    local modo="$1"
    local base="$DESTINO/${modo}_$(date +%Y-%m-%d_%H-%M-%S)"
    local ruta="$base.png"
    local n=2
    while [ -e "$ruta" ]; do
        ruta="$base-$n.png"
        n=$((n + 1))
    done
    printf '%s' "$ruta"
}

# Colores de la seleccion, los mismos del resto del escritorio: borde amatista,
# relleno violeta translucido, y lo de fuera oscurecido.
SLURP_COLORES=(-b 09031299 -c b16cffff -s b16cff26 -w 2)

# Cuanto se espera, tras soltar el raton, a que la seleccion se borre de la
# pantalla. Medido el 2026-09-23 en Hyprland 0.56: la capa tarda entre 90 y 125
# ms en apagarse del todo (se la vio pasar por 65%, 55%, 47% y 39% de opacidad).
# 300 ms es ese peor caso por partida doble, y no se nota: acabas de soltar el
# boton.
ESPERA_SELECCION=0.3

# Esperar a que la capa de seleccion de slurp se haya ido DE LA PANTALLA.
#
# POR QUE, si slurp ya termino: que el PROCESO muera no quiere decir que su capa
# deje de dibujarse. Hyprland la desvanece (animacion `fadeLayersOut`), asi que
# sigue ahi un par de decimas mas, cada vez con menos opacidad — y grim, que
# tarda muy poco en pedir su fotograma, llega de sobra a retratarla. La captura
# sale entonces con el relleno amatista de la seleccion y un trozo de su borde
# DENTRO: es el «recuadro en medio» que se reporto el 2026-09-23. En esa captura
# el borde estaba al 42% de opacidad, o sea justo a mitad del desvanecido.
#
# `--full` y `--ventana` no lo sufren nunca, porque ahi no hay slurp. Era la
# pista que lo delataba.
#
# DOS PASOS, y hacen falta los dos (medido, cada uno por separado falla):
#   1. Esperar a que Hyprland deje de listar la capa. Es el fin del PROCESO, y
#      llega enseguida (unos 10 ms), pero no dice nada de lo que se ve.
#   2. Esperar el desvanecido, que empieza justo entonces. Esto no se puede
#      preguntar: no hay forma de que el compositor avise de que ya termino una
#      animacion, asi que es un plazo fijo.
#
# Si no hay hyprctl (otro compositor, otra maquina) se salta el paso 1 y se
# respeta el plazo igual: alli tambien puede haber una transicion al cerrar.
esperar_a_que_se_vaya_la_seleccion() {
    if command -v hyprctl >/dev/null 2>&1; then
        # Quien tenga las animaciones apagadas —por gusto o por ahorrar en una
        # maquina justa— no tiene desvanecido que esperar, y no tiene por que
        # pagar el plazo. La capa se va con su proceso.
        # `"int": 0` con la config en hyprlang, `"bool": false` con la de Lua.
        if hyprctl getoption animations:enabled -j 2>/dev/null \
                | grep -qE '"int": *0\b|"bool": *false'; then
            return 0
        fi
        local intentos=0
        # 60 vueltas de 10 ms como tope. Es un seguro por si el compositor va
        # cargado, no el caso normal.
        while [ "$intentos" -lt 60 ]; do
            hyprctl layers 2>/dev/null | grep -q 'namespace: selection' || break
            sleep 0.01
            intentos=$((intentos + 1))
        done
        if [ "$intentos" -ge 60 ]; then
            # Se agoto: se captura igual —una captura con un tinte es mejor que
            # ninguna— pero queda dicho por que puede salir rara.
            echo "screenshot: la seleccion sigue en pantalla; la captura puede salir con ella" >&2
        fi
    fi
    sleep "$ESPERA_SELECCION"
}

avisar() {
    # Si algun dia hay demonio de notificaciones, esto se vera; mientras no lo
    # haya, notify-send no falla, simplemente no muestra nada. Por eso ademas se
    # escribe en el log de Hyprland con echo.
    notify-send -a CeliuzShot -i "$2" "$1" "${3:-}" 2>/dev/null &
    echo "screenshot: $1 ${3:-}" >&2
}

mkdir -p "$DESTINO"

case "${1:-}" in
    --full|-f)
        ARCHIVO=$(nombre_libre pantalla)
        grim "$ARCHIVO"
        ;;
    --ventana|-w)
        # La geometria de la ventana activa, preguntada a Hyprland.
        GEO=$(hyprctl activewindow -j | python3 -c '
import json, sys
try:
    v = json.load(sys.stdin)
    x, y = v["at"]
    w, h = v["size"]
    print(f"{x},{y} {w}x{h}")
except Exception:
    pass')
        if [ -z "$GEO" ]; then
            avisar "No hay ventana enfocada" dialog-error
            exit 1
        fi
        ARCHIVO=$(nombre_libre ventana)
        grim -g "$GEO" "$ARCHIVO"
        ;;
    *)
        # slurp devuelve vacio y codigo 1 si cancelas con Escape o clic derecho:
        # eso no es un error, es que has cambiado de idea.
        ZONA=$(slurp "${SLURP_COLORES[@]}") || exit 0
        [ -n "$ZONA" ] || exit 0
        esperar_a_que_se_vaya_la_seleccion
        ARCHIVO=$(nombre_libre zona)
        grim -g "$ZONA" "$ARCHIVO"
        ;;
esac

if [ ! -s "$ARCHIVO" ]; then
    avisar "La captura fallo" dialog-error
    exit 1
fi

wl-copy < "$ARCHIVO"
avisar "Captura copiada" "$ARCHIVO" "$(basename "$ARCHIVO")"
