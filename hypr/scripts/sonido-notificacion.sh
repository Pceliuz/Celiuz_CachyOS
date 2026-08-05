#!/usr/bin/env bash
# sonido-notificacion.sh — el aviso sonoro de las notificaciones.
#
# Lo llama mako con `on-notify=exec` cada vez que se abre una notificacion (ver
# mako/config). Existe porque una notificacion que solo se ve no sirve de nada
# si estas jugando, leyendo o mirando a otra pantalla.
#
# POR QUE UN SCRIPT Y NO LA LINEA DE UNA SOLA ORDEN QUE PONE EL MANUAL DE MAKO.
# El manual sugiere `on-notify=exec mpv /usr/share/sounds/.../message.oga`, que
# cablea DOS cosas que este repo no puede dar por hechas (es publico y se usa en
# mas de un equipo, ver la regla de oro del CLAUDE.md): que exista ese
# reproductor y que exista ese fichero, que viene del paquete
# `sound-theme-freedesktop` y no es obligatorio. Si falta cualquiera de los dos,
# la orden falla **en silencio**: mako no enseña el error por ningun lado, asi
# que te quedarias sin sonido sin enterarte y sin nada que mirar.
#
# Aqui se busca lo que HAYA, y si no hay nada se puede preguntar con --revisar.
#
# Ajustes por entorno (para probar sin tocar la config):
#   SONIDO_FICHERO=/ruta/al.oga   usa ese y no busca
#   SONIDO_REPRODUCTOR=paplay     usa ese y no busca

set -uo pipefail

# --- El sonido ---------------------------------------------------------------
# Por orden: lo que hayas puesto tu, luego tu tema de sonidos personal, y luego
# el tema freedesktop, que es el que trae la distro. `message` es un toc corto y
# neutro: los mas largos cansan cuando llegan tres seguidas.
CANDIDATOS_FICHERO=(
    "${XDG_DATA_HOME:-$HOME/.local/share}/sounds/__custom/stereo/message.oga"
    "$HOME/.local/share/sounds/freedesktop/stereo/message.oga"
    "/usr/share/sounds/freedesktop/stereo/message.oga"
    "/usr/share/sounds/freedesktop/stereo/message-new-instant.oga"
    "/usr/share/sounds/freedesktop/stereo/bell.oga"
)

# --- El reproductor ----------------------------------------------------------
# pw-play primero: es el cliente nativo de PipeWire, que es el servidor de audio
# de esta distro, y no arrastra la capa de compatibilidad de PulseAudio.
#
# aplay NO esta en la lista a proposito, aunque casi siempre este instalado:
# solo sabe WAV y estos ficheros son OGG. Diria "no puedo" y te quedarias sin
# sonido teniendo el resto en su sitio.
CANDIDATOS_REPRODUCTOR=(pw-play paplay ffplay mpv)

buscar_fichero() {
    if [ -n "${SONIDO_FICHERO:-}" ]; then
        [ -r "$SONIDO_FICHERO" ] && printf '%s' "$SONIDO_FICHERO"
        return
    fi
    for f in "${CANDIDATOS_FICHERO[@]}"; do
        [ -r "$f" ] && { printf '%s' "$f"; return; }
    done
}

buscar_reproductor() {
    if [ -n "${SONIDO_REPRODUCTOR:-}" ]; then
        command -v "$SONIDO_REPRODUCTOR" >/dev/null && printf '%s' "$SONIDO_REPRODUCTOR"
        return
    fi
    for p in "${CANDIDATOS_REPRODUCTOR[@]}"; do
        command -v "$p" >/dev/null && { printf '%s' "$p"; return; }
    done
}

# Cada reproductor quiere sus propias banderas para no abrir ventana, no pintar
# video y no escribir en la terminal. La tabla esta solo aqui.
reproducir() {
    local prog="$1" fichero="$2"
    case "$prog" in
        pw-play) exec pw-play "$fichero" ;;
        paplay)  exec paplay "$fichero" ;;
        ffplay)  exec ffplay -nodisp -autoexit -loglevel quiet "$fichero" ;;
        mpv)     exec mpv --no-terminal --no-video --really-quiet "$fichero" ;;
        *)       exec "$prog" "$fichero" ;;
    esac
}

fichero="$(buscar_fichero)"
reproductor="$(buscar_reproductor)"

if [ "${1:-}" = "--revisar" ]; then
    # Para saber por que no suena, ya que mako no enseña los errores.
    if [ -z "$fichero" ]; then
        echo "sin sonido: no encuentro ningun fichero. Instala sound-theme-freedesktop"
        echo "            o pon el tuyo con SONIDO_FICHERO=/ruta/al.oga"
    else
        echo "sonido:      $fichero"
    fi
    if [ -z "$reproductor" ]; then
        echo "sin sonido: no encuentro con que reproducirlo (${CANDIDATOS_REPRODUCTOR[*]})"
    else
        echo "reproductor: $reproductor"
    fi
    [ -n "$fichero" ] && [ -n "$reproductor" ] || exit 1
    echo "suena bien. Pruebalo con:  notify-send prueba"
    exit 0
fi

# Sin sonido o sin reproductor no se hace ruido ni se protesta: el aviso visual
# sigue funcionando igual, y una notificacion no es sitio para quejarse de que
# falta un paquete. Para eso esta --revisar.
[ -n "$fichero" ] && [ -n "$reproductor" ] || exit 0

reproducir "$reproductor" "$fichero"
