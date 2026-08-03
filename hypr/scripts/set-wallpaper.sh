#!/usr/bin/env bash
# ~/dotfiles/hypr/scripts/set-wallpaper.sh
#
# Este script ya solo es un atajo: quien hace el trabajo es CeliuzPaper.
#
#   set-wallpaper.sh                   abre el selector (la app)
#   set-wallpaper.sh --list            lista los fondos con su tipo y tamano
#   set-wallpaper.sh <ruta-al-video>   pone ese video de fondo, ya
#   set-wallpaper.sh <texto>           pone el fondo cuyo titulo contenga el texto
#
# Se queda porque el nombre es el que se recuerda y porque autostart y los
# comentarios de los .conf lo mencionan, pero la logica (donde estan los fondos,
# cual esta puesto, como se cambia) vive en un solo sitio:
# ~/dotfiles/hypr/scripts/lib/wallpapers.py. Tener dos escaneos distintos era
# pedir que un dia dijeran cosas diferentes.

set -uo pipefail

# La raiz del repo, sacada de donde esta este fichero: asi vale clonado en
# cualquier ruta y no solo en ~/dotfiles.
RAIZ="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../.." && pwd)"
APP="$RAIZ/celiuzpaper/celiuzpaper.py"

case "${1:-}" in
    "")            exec "$APP" ;;
    -l|--list)     exec "$APP" --list ;;
    -h|--help)     exec "$APP" --help ;;
    *)             exec "$APP" --set "$@" ;;
esac
