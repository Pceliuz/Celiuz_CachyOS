#!/usr/bin/env bash
# ~/dotfiles/hypr/scripts/terminal.sh
#
# Abre un comando en una terminal con una CLASE de ventana concreta, sea cual sea
# la terminal que tengas instalada.
#
#   terminal.sh monitor-tui btop
#   terminal.sh config-reload ~/dotfiles/hypr/scripts/recargar.sh --esperar
#   terminal.sh --sin-uwsm fuzzel-term btop     (quien llama ya puso el uwsm)
#
# POR QUE
# -------
# Las ventanitas flotantes de este escritorio (btop al pulsar la CPU, nmtui al
# pulsar la red, el aviso de recarga de config) se abrian con `kitty --class X
# -e ...` escrito a mano en cinco sitios: waybar/config.jsonc y keybinds.conf.
# En una maquina sin kitty eso no abre nada. Y la clase no es decorativa: es lo
# que hace que windowrules.conf las saque flotantes y centradas en vez de
# encajarlas en el mosaico.
#
# Cada terminal nombra esa opcion a su manera, asi que la tabla vive aqui y solo
# aqui. Si la tuya no esta, se abre igual pero sin clase propia: la ventana
# saldra en mosaico en lugar de flotando. Anadir la tuya es una linea.

set -u

# Normalmente cada app nace en su propio scope de systemd (ver mas abajo). Pero
# fuzzel ya lo hace por su cuenta con `launch-prefix=uwsm app --`, y anidar un
# uwsm dentro de otro no tiene sentido: para ese caso, --sin-uwsm.
PREFIJO=(uwsm app --)
if [ "${1:-}" = "--sin-uwsm" ]; then
    PREFIJO=()
    shift
fi

[ $# -ge 2 ] || { echo "uso: terminal.sh [--sin-uwsm] <clase> <comando> [args...]" >&2; exit 2; }

CLASE="$1"; shift

# La terminal la decide lib/apps.py, igual que para el dock y para SUPER+RETURN.
TERM_BIN="$("$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/lib/apps.py" terminal 2>/dev/null)"
TERM_BIN="${TERM_BIN%% *}"

if [ -z "$TERM_BIN" ] || ! command -v "$TERM_BIN" >/dev/null 2>&1; then
    notify-send -a "Escritorio" -u critical -i dialog-error \
        "No hay ninguna terminal instalada" \
        "Instala una (kitty, alacritty, foot...) y vuelve a pasar ./instalar.sh"
    exit 1
fi

# Como pide cada terminal "esta ventana se llama asi" y "ejecuta esto".
case "$TERM_BIN" in
    kitty|alacritty)  exec "${PREFIJO[@]}" "$TERM_BIN" --class "$CLASE" -e "$@" ;;
    ghostty)          exec "${PREFIJO[@]}" ghostty "--class=$CLASE" -e "$@" ;;
    foot)             exec "${PREFIJO[@]}" foot --app-id "$CLASE" "$@" ;;
    wezterm)          exec "${PREFIJO[@]}" wezterm start --class "$CLASE" -- "$@" ;;
    xterm)            exec "${PREFIJO[@]}" xterm -class "$CLASE" -e "$@" ;;
    terminator)       exec "${PREFIJO[@]}" terminator --classname "$CLASE" -e "$@" ;;
    *)
        # Sin clase propia: se abre, pero windowrules no la reconocera y saldra
        # en mosaico. Mejor eso que no abrir nada.
        exec "${PREFIJO[@]}" "$TERM_BIN" -e "$@"
        ;;
esac
