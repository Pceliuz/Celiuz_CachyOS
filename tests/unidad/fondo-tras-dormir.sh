#!/usr/bin/env bash
# tests/unidad/fondo-tras-dormir.sh — que al despertar el fondo se relance, y
# que si Hyprland no contesta NO se lance a ciegas.
#
# QUE VIGILA, Y POR QUE
# ---------------------
# El 13 nov 2026, al volver de suspender, Parzival se encontro «el fondo no se
# recarga, se queda todo negro»: el driver de NVIDIA pierde la memoria de la GPU
# y el mpvpaper que sigue vivo pinta negro. hypridle llama a este script en
# `after_sleep_cmd`. Aqui se comprueba que relanza el fondo por el lanzador de
# siempre (`wallpaper.sh --only-mpv`) y que, si Hyprland no contesta, no lanza a
# ciegas y lo deja dicho. hyprctl y wallpaper.sh de mentira: nada real se toca.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

mkdir -p "$TMP/scripts"
cp "$REPO/hypr/scripts/fondo-tras-dormir.sh" "$TMP/scripts/"
# El lanzador de mentira solo apunta con que se le llamo.
printf '#!/bin/sh\necho "$@" >> "%s/wallpaper.log"\n' "$REGISTRO" > "$TMP/scripts/wallpaper.sh"
chmod +x "$TMP/scripts/wallpaper.sh"

SCRIPT="$TMP/scripts/fondo-tras-dormir.sh"

correr() { salida="$(ESPERA_S="$1" bash "$SCRIPT" 2>&1)"; codigo=$?;
           printf '%s\n' "$salida" > "$TMP/salida.txt"; }

# --- 1. Hyprland contesta: se relanza el fondo --------------------------------

titulo "1. Con Hyprland vivo, el fondo se relanza por el lanzador de siempre"
rm -f "$REGISTRO"/*.log
binario_falso hyprctl 0 'echo "{\"name\": \"eDP-1\"}"'
correr 2
afirmar_igual "0" "$codigo" "termina bien"
afirmar_contiene "$REGISTRO/wallpaper.log" "^--only-mpv$" "relanza con --only-mpv"
afirmar_igual "1" "$(wc -l < "$REGISTRO/wallpaper.log")" "un solo relanzamiento"

# --- 2. Hyprland no contesta: no se lanza a ciegas ----------------------------

titulo "2. Sin Hyprland, no se lanza a ciegas y lo dice"
rm -f "$REGISTRO"/*.log
binario_falso hyprctl 0 'exit 0'          # contesta, pero sin ninguna salida
correr 0
afirmar_igual "1" "$codigo" "sale con error"
afirmar "no relanza el fondo" test ! -f "$REGISTRO/wallpaper.log"
afirmar_contiene "$TMP/salida.txt" "no relanzo el fondo" "deja rastro de por que"

# --- 3. hyprctl que falla tampoco sirve ---------------------------------------

titulo "3. Si hyprctl falla, tampoco se lanza"
rm -f "$REGISTRO"/*.log
binario_falso hyprctl 1
correr 0
afirmar_igual "1" "$codigo" "sale con error"
afirmar "no relanza el fondo" test ! -f "$REGISTRO/wallpaper.log"

resumen
