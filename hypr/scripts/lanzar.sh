#!/usr/bin/env bash
# ~/dotfiles/hypr/scripts/lanzar.sh
#
# Lanza una app del dock (o de un bind) diciendo QUE ha fallado y que hacer, si
# es que falla.
#
# POR QUE EXISTE
# --------------
# uwsm por su cuenta no se queda callado: manda una notificacion y sale con 1.
# Pero lo que manda es un «Error — Command not found: "brave"» firmado por UWSM,
# y puesto asi no lleva a ningun lado: no dice que venga del dock, ni cual de los
# iconos es, ni que se pueda quitar. Con un dock heredado de otra maquina, donde
# varios iconos estan muertos a la vez, ese mensaje no basta para arreglarlo.
#
# (Ojo al medirlo: `uwsm app -- inexistente | head; echo $?` imprime 0, pero ese
# 0 es el de head, no el de uwsm. Sin la tuberia sale 1.)
#
# El prefijo de uwsm sigue siendo imprescindible y por eso se conserva aqui: hace
# que cada app nazca en su PROPIO scope de systemd. Sin el, todas caen en el
# cgroup de Hyprland y el congelado selectivo al bloquear la pantalla no puede
# distinguir una app del compositor (ver scripts/lib/congelar.py).

set -u

[ $# -gt 0 ] || exit 0

# Solo se comprueba el primer trozo: el resto son argumentos ("steam
# steam://rungameid/123", "kitty -e btop").
if ! command -v "$1" >/dev/null 2>&1 && [ ! -x "$1" ]; then
    notify-send -a "Dock" -u critical -i dialog-error \
        "No se puede abrir «$1»" \
        "No esta instalado o no esta en el PATH. Clic derecho en el dock para quitarlo o cambiarlo."
    exit 1
fi

exec uwsm app -- "$@"
