#!/usr/bin/env bash
# hypr/scripts/barras.sh — manda ordenes al demonio de las barras.
#
#   barras.sh show              # saca la barra de arriba
#   barras.sh show dock:show    # saca las dos (lo que hace SUPER+C)
#   barras.sh dock:show
#
# Las ordenes que entiende estan listadas en la cabecera de waybar-autohide.py.
#
# POR QUE EXISTE, Y NO UN `echo` EN CADA SITIO
# --------------------------------------------
# Tres razones, y las tres han mordido en este repo:
#
# 1. **La ruta ya no es fija.** Lleva la firma de la sesion (ver lib/canales.sh),
#    asi que hay que calcularla. Escrita a mano en cuatro sitios se desincroniza
#    el dia que cambie.
#
# 2. **Escribir en un FIFO se BLOQUEA hasta que alguien lea.** Si el demonio esta
#    atascado, un `echo` directo desde un `on-click` de waybar cuelga esa barra
#    para siempre. Va con `timeout`.
#
# 3. **`echo x > ruta-que-no-es-un-FIFO` CREA un fichero normal y sale con 0.**
#    Ese es el fallo silencioso clasico de aqui: los clicks y el atajo parecen ir
#    y no hacen nada, y encima dejan basura con el nombre del canal. Por eso se
#    comprueba con `test -p` antes, y por eso se avisa cuando no esta: waybar se
#    traga el stderr de los `on-click`, asi que sin notificacion no habria ni
#    rastro.
#
# Se usa desde `keybinds.conf` (SUPER+C) y desde los `on-click` de
# `waybar/trigger.jsonc` y `waybar/dock-trigger.jsonc`.

set -u

DIR="$(dirname "$(readlink -f "$BASH_SOURCE")")"
. "$DIR/lib/canales.sh"

[ "$#" -gt 0 ] || { echo "uso: $(basename "$0") <orden> [orden...]" >&2; exit 2; }

FIFO="$(canal_barras)"

if [ ! -p "$FIFO" ]; then
    # Sin canal no hay a quien hablarle. Se avisa porque este es exactamente el
    # caso que antes fallaba callado; `--callado` lo apaga para quien no quiera
    # la notificacion (los tests, sin ir mas lejos).
    if [ "${BARRAS_CALLADO:-0}" != "1" ] && command -v notify-send >/dev/null 2>&1; then
        notify-send -a Celiuz -u critical "Barras" \
            "No encuentro el canal del demonio de las barras. ¿Esta corriendo? (SUPER+SHIFT+C lo reinicia)"
    fi
    echo "barras.sh: no existe el FIFO $FIFO" >&2
    exit 1
fi

# El timeout es por el punto 2 de arriba. `printf` de una vez: el demonio parte
# lo que lee por espacios y saltos, asi que varias ordenes viajan juntas.
printf '%s\n' "$@" | timeout 2 tee "$FIFO" >/dev/null
