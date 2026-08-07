#!/usr/bin/env bash
# ~/dotfiles/hypr/scripts/wallpaper.sh
#
# Arranca el fondo de pantalla en video con mpvpaper. Lo llama autostart.conf.
#
#   wallpaper.sh              arranca el fondo y su demonio de ahorro
#   wallpaper.sh --only-mpv   relanza SOLO mpvpaper, sin tocar el demonio
#                             (lo usa wallpaper-pause.py al salir de un juego)
#
# El fondo activo NO se escribe aqui: es el enlace simbolico
# ~/dotfiles/hypr/wallpapers/current, que apunta al video que toque. Asi
# cambiar de fondo es repuntar un enlace (lo hace set-wallpaper.sh) y este
# script no se toca nunca.

set -uo pipefail

# Sacados de donde esta este fichero, no de "$HOME/dotfiles/...": asi el repo
# vale clonado en cualquier ruta, y no solo en ~/dotfiles.
SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT="$SCRIPTS/../wallpapers/current"
RUNTIME="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
# Sin esto no hay forma de saber que canal es de esta sesion. Se comprueba a
# proposito: un `source` que falla en bash NO corta el script, y seguir sin estas
# funciones significaria volver a matar por nombre, que es justo lo que se quito.
if ! . "$SCRIPTS/lib/canales.sh" 2>/dev/null || ! declare -F canal >/dev/null; then
    echo "wallpaper: no encuentro lib/canales.sh; me paro antes de tocar nada" >&2
    exit 1
fi
MPV_SOCK="$(socket_mpv)"

SOLO_MPV=0
[ "${1:-}" = "--only-mpv" ] && SOLO_MPV=1

# Si ya habia uno corriendo, fuera. Sin esto, al recargar Hyprland acabarias
# con varios mpvpaper superpuestos, y cada uno se lleva ~430 MB de RAM.
#
# Pero SOLO el de esta sesion. Antes era `pkill -x mpvpaper`, que mata por
# NOMBRE: con dos sesiones vivas del mismo usuario se llevaba por delante el
# fondo de la otra, y es tambien lo que dejaba el escritorio real sin fondo al
# levantar un Hyprland anidado (2026-08-04).
#
# Se reconoce al nuestro por la ruta de SU socket IPC, que sale en su linea de
# comandos y ya lleva la firma dentro. Es mas exacto que mirar el entorno y no
# tiene el modo de fallo de «sin firma, mato a todos»: sin firma la ruta es la
# de "sin-sesion", que no la lleva ningun mpvpaper vivo.
#
# Hacen falta los dos golpes: si mpvpaper arranco con opciones invalidas se
# queda colgado sin capa y NO responde a SIGTERM, asi que hay que rematarlo.
MIS_MPV="$(pids_con_marca mpvpaper "$MPV_SOCK")"
[ -n "$MIS_MPV" ] && kill $MIS_MPV 2>/dev/null
sleep 0.5
MIS_MPV="$(pids_con_marca mpvpaper "$MPV_SOCK")"
[ -n "$MIS_MPV" ] && kill -9 $MIS_MPV 2>/dev/null
sleep 0.3

# El demonio que pausa el video cuando hay una ventana tapandolo y lo mata
# entero mientras juegas. Va aparte de mpvpaper a proposito: sobrevive a que
# mpvpaper muera y lo vuelve a levantar.
#
# Se arranca AQUI, antes de comprobar si hay fondo elegido, y tambien en modo
# --only-mpv si no estuviera vivo. Las dos cosas por el mismo fallo: en una
# sesion donde todavia no se ha elegido fondo, este script salia por el `exit 0`
# de abajo sin llegar a lanzarlo, y cuando CeliuzPaper elegia el primero llamaba
# con --only-mpv, que tampoco lo lanzaba. Resultado: el fondo no se pausaba en
# toda la sesion, y solo se arreglaba reiniciando.
#
# En modo completo se lanza siempre y no se mata a nadie aqui: el demonio nuevo
# barre al viejo DE ESTA SESION el solo, nada mas arrancar (ver `matar_otros()`
# en wallpaper-pause.py). Antes se hacia aqui con un `pkill -f
# 'wallpaper-paus[e].py'`, que mata por nombre y se llevaba tambien el de otra
# sesion viva; y la comprobacion posterior era una carrera confesada — si el
# viejo tardaba en morir, el pgrep lo veia, no se lanzaba a nadie, y la sesion se
# quedaba sin demonio. Dejar que el nuevo barra quita las dos cosas.
#
# En --only-mpv NO se puede lanzar a ciegas: a este script lo llama el propio
# demonio al salir de un juego, asi que un demonio nuevo barreria a quien nos
# esta llamando. Ahi se pregunta primero, y solo por los de ESTA sesion.
if [ "$SOLO_MPV" -eq 0 ] || [ -z "$(pids_de_esta_sesion_cmd wallpaper-pause.py)" ]; then
    setsid "$SCRIPTS/wallpaper-pause.py" >/dev/null 2>&1 &
fi

if [ ! -e "$CURRENT" ]; then
    echo "wallpaper: no hay fondo elegido todavia." >&2
    echo "           Usa: $SCRIPTS/set-wallpaper.sh <ruta-al-video>" >&2
    exit 0
fi

# --- Las banderas, y por que ---
#
#  -f          se desdobla y suelta la terminal, para que exec-once no se quede
#              colgado esperandolo.
#  ALL         todas las salidas. Con un solo monitor da igual, pero si algun
#              dia conectas otro no hay que tocar nada.
#
# NO se pasan -p ni -s, y esto es importante. Las dos prometen ahorrar recursos
# cuando el fondo esta tapado, pero **bajo Hyprland ninguna funciona**: se
# apoyan en el "surface frame callback" de Wayland y Hyprland sigue pidiendo
# fotogramas a la capa de fondo aunque tenga una ventana encima a pantalla
# completa. Comprobado de dos formas: con -p, la propiedad `pause` de mpv se
# queda en False con el fondo totalmente tapado; con -s, ni el PID ni la RSS se
# mueven. Y encima -s se pelea con la pausa que manda el demonio: ve mpv parado,
# decide descargarlo y lo relanza, cambiando de PID cada pocos segundos.
# Todo el ahorro lo lleva wallpaper-pause.py, que si sabe lo que hay en pantalla.
#
# El manual de la rama master (1.9) documenta ademas un `-a/--auto-mode
# <FULL|MAX>` que en la 1.8 del repo NO EXISTE, y falla de forma confusa: dice
# `invalid option -- 'a'`, se traga el argumento siguiente y el error que ves es
# "Cannot open file 'ALL'". Comprueba siempre con `mpvpaper --help`, no con el
# manual de internet.
#
# Y las de mpv (-o):
#  --no-audio      un fondo que suene seria una tortura. Ademas evita que se
#                  meta en el mezclador de PipeWire y aparezca en pavucontrol.
#  --loop-file=inf bucle infinito.
#  --hwdec=auto    decodificacion por hardware en la 3050: baja el uso de CPU
#                  a casi nada y lo deja en el bloque de video dedicado, que no
#                  compite con lo que la GPU este renderizando.
#  --panscan=1.0   recorta para llenar la pantalla en vez de dejar franjas
#                  negras cuando el video no es 16:9.
#  --input-ipc-server  abre el socket por el que wallpaper-pause.py pone y quita
#                  la pausa. Sin esto el demonio no tiene por donde hablarle.
# --- Video o imagen fija ---
# Un fondo puede ser cualquiera de las dos cosas, y mpv sirve para ambas. La
# diferencia es una sola bandera: sin ella, mpv ensena una imagen 5 segundos
# (--image-display-duration por defecto) y luego se queda en negro, que es
# exactamente el sintoma de "puse un fondo y a los pocos segundos desaparecio".
# Con `inf` se queda fija para siempre.
#
# Se mira la extension del fichero al que APUNTA el enlace, no la del enlace.
EXTRA=""
DESTINO="$(readlink -f "$CURRENT" 2>/dev/null || echo "$CURRENT")"
case "${DESTINO,,}" in
    *.jpg|*.jpeg|*.png|*.webp|*.bmp|*.avif|*.jxl)
        EXTRA="--image-display-duration=inf"
        ;;
esac

mpvpaper -f \
    -o "--no-audio --loop-file=inf --hwdec=auto --panscan=1.0 $EXTRA --input-ipc-server=$MPV_SOCK" \
    ALL "$CURRENT"
