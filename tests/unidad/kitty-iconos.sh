#!/usr/bin/env bash
# tests/unidad/kitty-iconos.sh — los iconos de Nerd Font a su tamaño en kitty
# (kitty/celiuz-iconos.py) y su enganche en kitty.conf (instalar.sh).
#
# QUE VIGILA
# ----------
# - Que elige una Nerd Font NORMAL (la Mono encoge los iconos a una celda):
#   Symbols Nerd Font si esta; si no, la de la familia que pinta hoy; si no,
#   cualquiera. Y sin ninguna, que no imprima nada (kitty queda como estaba).
# - Que no toca los separadores de powerline (descuadrarian un prompt).
# - Que instalar.sh añade UNA linea a kitty.conf, sin tocar lo que hay.
# fc-list y fc-match son de mentira: la fuente del equipo no cuenta.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
SCRIPT="$REPO/kitty/celiuz-iconos.py"

# fuentes "<familias de fc-list, una por linea>" "<lo que dice fc-match>"
fuentes() {
    binario_falso fc-list 0 "printf '%s\n' \"$1\""
    binario_falso fc-match 0 "printf '%s' \"$2\""
}

titulo "1. Que fuente elige"
fuentes $'FantasqueSansM Nerd Font\nFantasqueSansM Nerd Font Mono\nMesloLGS Nerd Font\nNoto Sans' \
    "FantasqueSansM Nerd Font Mono"
afirmar_igual "symbol_map U+E000-U+E09F,U+E0D8-U+F8FF,U+F0000-U+FFFFF FantasqueSansM Nerd Font" \
    "$(python3 "$SCRIPT")" "la normal de la familia cuya Mono pinta hoy los iconos"
fuentes $'MesloLGS Nerd Font\nSymbols Nerd Font,Symbols Nerd Font Mono\nMesloLGS Nerd Font Mono' \
    "MesloLGS Nerd Font Mono"
afirmar "Symbols Nerd Font si esta (aunque fc-list la junte con su Mono)" \
    sh -c "python3 '$SCRIPT' | grep -q ' Symbols Nerd Font\$'"
fuentes $'Zeta Nerd Font\nAlfa Nerd Font\nNoto Sans Mono' "Noto Sans Mono"
afirmar "si la de hoy no es Nerd Font, una cualquiera (la misma siempre)" \
    sh -c "python3 '$SCRIPT' | grep -q ' Alfa Nerd Font\$'"
fuentes $'FantasqueSansM Nerd Font Mono\nNoto Sans' "FantasqueSansM Nerd Font Mono"
afirmar_igual "" "$(python3 "$SCRIPT")" "solo Mono: nada, kitty queda como estaba"
binario_falso fc-list 1
afirmar_igual "0|" "$(python3 "$SCRIPT"; echo "$?|")" "sin fontconfig que conteste: nada, y sin reventar"
afirmar "no toca los separadores de powerline (E0A0-E0D7)" \
    sh -c "! grep -q 'U+E000-U+F8FF' '$SCRIPT'"

titulo "2. instalar.sh engancha kitty.conf una vez y deja lo tuyo"
conf="$XDG_CONFIG_HOME/kitty/kitty.conf"
mkdir -p "$(dirname "$conf")"
printf 'background_opacity 0.6\ninclude themes/x.conf\n' > "$conf"
fuentes $'FantasqueSansM Nerd Font' "FantasqueSansM Nerd Font Mono"
binario_falso kitty 0
cargar() {
    sed -n '/^KITTY_MARCA=/,/^}/p' "$REPO/instalar.sh" > "$TMP/kitty_iconos.sh"
    sed -n '/^enlazar() {/,/^}/p' "$REPO/instalar.sh" >> "$TMP/kitty_iconos.sh"
    SOLO_REVISAR=0
    titulo() { :; }; gris() { :; }; hecho() { :; }; aviso() { :; }; hacer() { "$@"; }
    . "$TMP/kitty_iconos.sh"
}
( cargar; kitty_iconos; kitty_iconos ) >/dev/null 2>&1
afirmar_igual "1" "$(grep -cx 'geninclude celiuz-iconos.py' "$conf")" "dos pasadas dejan UNA linea"
afirmar_igual "background_opacity 0.6" "$(head -n1 "$conf")" "lo que habia sigue delante"
afirmar_igual "$(readlink -f "$SCRIPT")" "$(readlink -f "$XDG_CONFIG_HOME/kitty/celiuz-iconos.py")" \
    "el script, enlazado al lado de kitty.conf (geninclude lo busca ahi)"

afirmar_intacta_la_casa_real
resumen
