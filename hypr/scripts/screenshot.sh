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
