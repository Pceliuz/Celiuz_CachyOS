#!/usr/bin/env bash
# ~/dotfiles/hypr/scripts/fondo-tras-dormir.sh
#
# Relanza el fondo de video al volver de suspender o de hibernar. Lo llama
# hypridle en `after_sleep_cmd` (hypr/hypridle.conf).
#
# POR QUE EXISTE: el driver de NVIDIA tiene PreserveVideoMemoryAllocations
# activo pero nvidia-suspend/-resume/-hibernate desactivados, asi que al
# despertar la GPU pierde su memoria y mpvpaper —que sigue vivo— pinta negro.
# Es lo que ve Parzival: «el fondo no se recarga, se queda todo negro»
# (2026-11-13). Un mpvpaper vivo y roto no se distingue de uno sano sin
# preguntarle a la GPU, asi que se relanza siempre.
#
# NO se copia la linea de mpvpaper: se usa el lanzador de siempre,
# `wallpaper.sh --only-mpv`, que mata solo los mpvpaper de ESTA sesion y lanza
# uno por pantalla. El demonio wallpaper-pause.py no se toca (sigue vivo).
#
# Se espera a que Hyprland conteste y tenga salidas: al despertar tarda un
# instante, y lanzar mpvpaper antes de eso lo deja sin pantalla donde pintar.
# Si no contesta a tiempo, NO se lanza a ciegas y se deja rastro en el diario.

set -uo pipefail

DIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
ESPERA_S="${ESPERA_S:-10}"

# listo — true si Hyprland contesta y tiene al menos una salida. Sin hyprctl
# (equipo a medio instalar) se da por bueno: el fondo que decida el lanzador.
listo() {
    command -v hyprctl >/dev/null 2>&1 || return 0
    local i
    for ((i = 0; i < ESPERA_S; i++)); do
        if hyprctl monitors -j 2>/dev/null | grep -q '"name"'; then
            return 0
        fi
        sleep 1
    done
    return 1
}

if ! listo; then
    echo "fondo-tras-dormir: Hyprland no contesta tras ${ESPERA_S}s;" \
         "no relanzo el fondo (mejor negro que roto)." >&2
    exit 1
fi

# La pantalla puede quedarse apagada esperando una tecla al volver; eso lo hacia
# este mismo after_sleep_cmd (`despachar.sh dpms on`). Ahora la orden vive aqui,
# para que hypridle siga teniendo UN solo comando que lanzar al despertar.
if [ -x "$DIR/despachar.sh" ]; then
    "$DIR/despachar.sh" dpms on >/dev/null 2>&1 || true
fi

exec "$DIR/wallpaper.sh" --only-mpv
