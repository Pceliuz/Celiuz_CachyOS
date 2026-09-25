#!/usr/bin/env bash
# ~/dotfiles/hypr/scripts/despachar.sh — `hyprctl dispatch`, en el idioma que
# entienda el Hyprland de esta sesion (Lua o hyprlang).
#
#   despachar.sh dpms on
#   despachar.sh workspace e+1
#
# Para los sitios que solo pueden llamar a una orden: hypridle.conf, los
# `on-scroll` de waybar. El porque, en lib/hypr.py.

DIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
if ! . "$DIR/lib/hypr.sh"; then
    echo "despachar.sh: no pude cargar lib/hypr.sh" >&2
    exit 1
fi
[ "$#" -ge 1 ] || { echo "uso: despachar.sh <dispatcher> [argumentos]" >&2; exit 2; }
hypr_despachar "$@"
