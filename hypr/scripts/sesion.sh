#!/usr/bin/env bash
# ~/dotfiles/hypr/scripts/sesion.sh
#
# El menu de salida (SUPER+SHIFT+P): bloquear, suspender, cerrar sesion,
# reiniciar o apagar.
#
#   sesion.sh            abre el menu
#
# POR QUE EXISTE: antes SUPER+SHIFT+P era un `exit` a secas, y rozar la tecla
# cerraba la sesion de golpe con todo lo abierto. Paso mas de una vez. Ahora ese
# atajo abre este menu, y lo que no tiene vuelta atras (cerrar sesion, reiniciar,
# apagar) pregunta OTRA VEZ.
#
# En la pregunta, la PRIMERA linea es «No»: fuzzel preselecciona la primera, asi
# que un Enter por inercia —que es justo el accidente del que venimos— vuelve
# atras en vez de apagar. Escape tambien cancela, en los dos menus.
#
# Bloquear y suspender no preguntan: no se pierde nada.

set -uo pipefail

DIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"

# Cerrar sesion. Si la sesion la lleva uwsm (la de CachyOS, y la que asume el
# `launch-prefix` de fuzzel.ini), se le pide a EL que pare: asi se apagan en
# orden las unidades de systemd de la sesion —las apps lanzadas con `uwsm app`,
# el demonio del Bluetooth— en vez de dejarlas colgando de un compositor muerto.
# Sin uwsm, el `exit` de Hyprland, dicho en el idioma de su config (Lua o
# hyprlang: ver lib/hypr.py).
cerrar_sesion() {
    if command -v uwsm >/dev/null 2>&1 && uwsm check is-active >/dev/null 2>&1; then
        uwsm stop
    else
        "$DIR/despachar.sh" exit
    fi
}

# elegir <titulo> <opcion>... — fuzzel en modo dmenu; imprime el indice elegido
# (desde 0) o nada si se cancelo.
elegir() {
    local titulo="$1"; shift
    local ancho=0 o
    for o in "$@"; do [ "${#o}" -gt "$ancho" ] && ancho="${#o}"; done
    printf '%s\n' "$@" | fuzzel --dmenu --index --prompt "$titulo" \
        --lines "$#" --width $((ancho + 8)) 2>/dev/null
}

# confirmar <verbo> — true solo si se elige explicitamente la segunda linea.
confirmar() {
    local r
    r="$(elegir "¿$1? " "󰜺  No, volver" "󰄬  Sí, $1")"
    [ "$r" = "1" ]
}

if ! command -v fuzzel >/dev/null 2>&1; then
    notify-send -a Sesión "Falta fuzzel" \
        "El menú de salida lo necesita (sudo pacman -S fuzzel)" 2>/dev/null
    exit 1
fi

OPCIONES=(
    "󰌾  Bloquear"
    "󰤄  Suspender"
    "󰍃  Cerrar sesión"
    "󰜉  Reiniciar"
    "󰐥  Apagar"
)

case "$(elegir "󰐥  " "${OPCIONES[@]}")" in
    0) exec "$DIR/lock.sh" ;;
    1) exec systemctl suspend ;;          # el bloqueo lo pone hypridle (before_sleep_cmd)
    2) confirmar "cerrar sesión" && cerrar_sesion ;;
    3) confirmar "reiniciar" && exec systemctl reboot ;;
    4) confirmar "apagar" && exec systemctl poweroff ;;
esac
exit 0
