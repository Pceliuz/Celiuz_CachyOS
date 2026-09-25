#!/usr/bin/env bash
# ~/dotfiles/hypr/scripts/osd.sh
#
# Las teclas de volumen, microfono y brillo: hace el cambio Y ENSEÑA COMO QUEDO.
#
#   osd.sh volumen subir|bajar|silenciar
#   osd.sh micro silenciar
#   osd.sh brillo subir|bajar
#
# POR QUE EXISTE: antes las teclas cambiaban el volumen a ciegas, sin forma de
# saber si habia pasado algo ni cuanto. Ahora cada pulsacion saca un aviso abajo
# en el centro con el valor y una barra (la «progress» de mako, que rellena el
# fondo del aviso hasta el porcentaje).
#
# EL AVISO ES UNO SOLO, que se va reescribiendo: cada pulsacion reemplaza al
# anterior (`--replace-id`), asi que mantener la tecla pulsada no apila veinte.
# El id del ultimo se apunta en $XDG_RUNTIME_DIR, con la firma de la sesion en
# el nombre (la regla de lib/canales.py).
#
# Y SE MANDA COMO TRANSITORIO (`-e`) y con categoria `osd`, que es lo que lo
# aparta del resto de avisos:
#   - avisos.py no apunta los transitorios en el historial (SUPER+H);
#   - mako/config le quita el sonido, lo pone abajo en el centro y lo deja ver
#     tambien en «no molestar»: es la respuesta a algo que acabas de pulsar, no
#     un aviso que te llega.
#
# Sin mako (o sin servidor de avisos) el cambio se hace igual: enseñarlo es un
# extra y nunca frena la tecla.

set -uo pipefail

PASO=5   # por ciento en cada pulsacion

ID="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/celiuz-osd.${HYPRLAND_INSTANCE_SIGNATURE:-sin-sesion}.id"

# mostrar <icono> <titulo> <valor 0-100>
mostrar() {
    local icono="$1" titulo="$2" valor="$3" anterior nuevo
    command -v notify-send >/dev/null 2>&1 || return 0
    anterior="$(cat "$ID" 2>/dev/null)"
    [[ "$anterior" =~ ^[0-9]+$ ]] || anterior=""
    nuevo="$(notify-send --app-name=OSD --category=osd --transient \
        --expire-time=1500 --print-id \
        --hint="int:value:$valor" \
        ${anterior:+--replace-id="$anterior"} \
        "$icono  $titulo" 2>/dev/null)"
    [[ "$nuevo" =~ ^[0-9]+$ ]] && printf '%s' "$nuevo" > "$ID"
    return 0
}

# El volumen de un dispositivo de wpctl, como «porcentaje silenciado(0|1)».
# `wpctl get-volume` dice «Volume: 0.45» o «Volume: 0.45 [MUTED]».
leer_wpctl() {
    local linea
    linea="$(wpctl get-volume "$1" 2>/dev/null)" || return 1
    awk '{ printf "%d %d\n", $2 * 100 + 0.5, /MUTED/ ? 1 : 0 }' <<< "$linea"
}

volumen() {
    local sink=@DEFAULT_AUDIO_SINK@ pct mudo icono
    case "${1:-}" in
        subir)     wpctl set-mute "$sink" 0
                   wpctl set-volume -l 1.0 "$sink" "$PASO%+" ;;
        bajar)     wpctl set-volume "$sink" "$PASO%-" ;;
        silenciar) wpctl set-mute "$sink" toggle ;;
        *)         echo "uso: osd.sh volumen subir|bajar|silenciar" >&2; return 2 ;;
    esac
    if ! read -r pct mudo < <(leer_wpctl "$sink"); then
        mostrar "󰖁" "Sin salida de sonido" 0
        return 0
    fi
    if [ "$mudo" = 1 ]; then
        mostrar "󰖁" "Silenciado" 0
        return 0
    fi
    if   [ "$pct" -ge 66 ]; then icono="󰕾"
    elif [ "$pct" -ge 33 ]; then icono="󰖀"
    elif [ "$pct" -gt 0 ];  then icono="󰕿"
    else                         icono="󰝟"
    fi
    mostrar "$icono" "Volumen  $pct%" "$pct"
}

micro() {
    local fuente=@DEFAULT_AUDIO_SOURCE@ pct mudo
    [ "${1:-}" = silenciar ] || { echo "uso: osd.sh micro silenciar" >&2; return 2; }
    wpctl set-mute "$fuente" toggle
    if ! read -r pct mudo < <(leer_wpctl "$fuente"); then
        mostrar "󰍭" "Sin micrófono" 0
    elif [ "$mudo" = 1 ]; then
        mostrar "󰍭" "Micrófono silenciado" 0
    else
        mostrar "󰍬" "Micrófono activo" "$pct"
    fi
}

brillo() {
    local pct
    command -v brightnessctl >/dev/null 2>&1 || return 0
    case "${1:-}" in
        subir) brightnessctl -q set "$PASO%+" ;;
        # -n: no bajar del minimo, que una pantalla a 0 parece apagada
        bajar) brightnessctl -q -n set "$PASO%-" ;;
        *)     echo "uso: osd.sh brillo subir|bajar" >&2; return 2 ;;
    esac
    # -m da «dispositivo,clase,actual,porcentaje%,maximo»
    pct="$(brightnessctl -m 2>/dev/null | head -1 | cut -d, -f4 | tr -d '%')"
    [[ "$pct" =~ ^[0-9]+$ ]] || return 0
    mostrar "$([ "$pct" -ge 50 ] && echo 󰃠 || echo 󰃞)" "Brillo  $pct%" "$pct"
}

case "${1:-}" in
    volumen) volumen "${2:-}" ;;
    micro)   micro "${2:-}" ;;
    brillo)  brillo "${2:-}" ;;
    *)       echo "uso: osd.sh volumen|micro|brillo <accion>" >&2; exit 2 ;;
esac
