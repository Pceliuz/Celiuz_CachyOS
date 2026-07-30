#!/usr/bin/env bash
#
# recargar.sh — recarga la config de Hyprland y AVISA DE VERDAD si algo falla.
#
# POR QUE EXISTE. `hyprctl reload` contesta "ok" pase lo que pase. Si te
# equivocas en la sintaxis de una regla, el ajuste simplemente NO SE APLICA y
# nadie te dice nada: te quedas mirando la pantalla preguntandote por que no
# cambia. Los errores solo salen en `hyprctl configerrors`, que es un comando
# aparte que hay que acordarse de escribir. Este script se acuerda por ti.
#
# Y de paso comprueba las dos INCOHERENCIAS SILENCIOSAS que ya nos hemos comido
# una vez cada una: son configs perfectamente validas, sin un solo error de
# sintaxis, en las que una opcion anula a otra sin decir nada.
#
# Uso:
#   recargar.sh            recarga, comprueba y avisa
#   recargar.sh -q         solo habla si algo va mal (para scripts)
#   recargar.sh --esperar  no cierra la ventana de golpe (para el bind
#                          SUPER+SHIFT+R, que abre una kitty solo para esto)
#
# Codigos de salida:  0 todo bien  ·  1 errores de config  ·  2 solo avisos

set -uo pipefail

silencioso=0
esperar=0
for arg in "$@"; do
    case "$arg" in
        -q|--silencioso) silencioso=1 ;;
        --esperar)       esperar=1 ;;
    esac
done

rojo=$'\e[31m'; ambar=$'\e[33m'; verde=$'\e[32m'; gris=$'\e[90m'; fin=$'\e[0m'
[[ -t 1 ]] || { rojo=; ambar=; verde=; gris=; fin=; }

decir()  { (( silencioso )) || printf '%s\n' "$*"; }
avisar() { printf '%s\n' "$*" >&2; }

salida=0
avisos=0


# --- 1. Recargar y mirar los errores de verdad -------------------------------

hyprctl reload >/dev/null

# configerrors devuelve una linea vacia cuando todo esta bien. Se recorta el
# espacio en blanco antes de decidir, o la comparacion siempre daria "hay algo".
errores="$(hyprctl configerrors | sed '/^[[:space:]]*$/d')"

if [[ -n "$errores" ]]; then
    avisar "${rojo}La config se recargo CON ERRORES:${fin}"
    avisar "$errores"
    avisar ""
    avisar "${gris}Lo que este en esas lineas no se ha aplicado. El resto si.${fin}"
    salida=1
else
    decir "${verde}Config recargada, sin errores.${fin}"
fi


# --- 2. El degradado que el giro necesita ------------------------------------
#
# `borderangle` en estilo loop gira el ANGULO del degradado del borde. Si
# col.active_border tiene un solo color no hay angulo que girar, asi que la
# animacion se queda puesta, valida y sin efecto ninguno. No es un error: es una
# config coherente que no hace nada.

borde="$(hyprctl getoption general:col.active_border -j | jq -r '.custom // ""')"
# Cuenta solo las paradas de color (8 digitos hex); descarta el "45deg" del final.
paradas="$(grep -oE '\b[0-9a-fA-F]{8}\b' <<<"$borde" | wc -l)"

# OJO: en el JSON de `hyprctl animations`, .enabled es un BOOLEANO (true), no el
# 1 que sale en la salida de texto. Comparar contra 1 no casa nunca y la
# comprobacion se saltaria en silencio — que es justo el fallo que este script
# existe para no tener.
gira="$(hyprctl animations -j 2>/dev/null \
        | jq -r '.[0][]? | select(.name=="borderangle" or .name=="glowangle")
                 | select((.enabled==true or .enabled==1) and (.style|test("loop")))
                 | .name' 2>/dev/null | tr '\n' ' ')"

if [[ -n "${gira// /}" && "$paradas" -lt 2 ]]; then
    avisar "${ambar}Aviso: ${gira}en modo loop, pero el borde no es un degradado.${fin}"
    avisar "${gris}  general:col.active_border tiene $paradas color(es). Hacen falta 2 o mas"
    avisar "  para que haya un angulo que girar. Ahora mismo esa animacion no hace nada.${fin}"
    avisos=1
fi


# --- 3. Las esquinas redondeadas y el hueco donde viven ----------------------
#
# Con rounding > 0 y gaps_in = 0, las esquinas curvas de dos ventanas pegadas
# dejan un agujero con forma de rombo por el que se ve el fondo. Los dos valores
# van atados: si uno cambia, el otro tambien.

rounding="$(hyprctl getoption decoration:rounding -j | jq -r '.int // 0')"
gaps="$(hyprctl getoption general:gaps_in -j | jq -r '.custom // "0"')"
gap_max="$(tr ' ' '\n' <<<"$gaps" | sort -rn | head -1)"

if (( rounding > 0 && gap_max == 0 )); then
    avisar "${ambar}Aviso: rounding = $rounding con gaps_in = 0.${fin}"
    avisar "${gris}  Donde se tocan dos ventanas, sus esquinas curvas dejan un rombo por el"
    avisar "  que se ve el fondo. O subes gaps_in a 4, o bajas rounding a 0.${fin}"
    avisos=1
fi


# --- Veredicto ---------------------------------------------------------------

if (( salida == 0 && avisos == 1 )); then
    salida=2
fi

(( salida == 0 )) && decir "${gris}Comprobaciones de coherencia: bien.${fin}"

# Con --esperar la ventana no se cierra sola cuando hay algo que leer. Si todo
# fue bien se va en 4 segundos: lo suficiente para ver el visto bueno de reojo,
# no tanto como para tener que cerrarla a mano cada vez.
if (( esperar )); then
    if (( salida == 0 )); then
        sleep 4
    else
        printf '\n%sPulsa una tecla para cerrar.%s' "$gris" "$fin"
        read -rsn1
    fi
fi

exit "$salida"
