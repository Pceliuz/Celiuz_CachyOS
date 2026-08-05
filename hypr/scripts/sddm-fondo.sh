#!/usr/bin/env bash
# sddm-fondo.sh — pone TU fondo actual en la pantalla de inicio de sesion,
# sin pedir permisos de root.
#
# EL PROBLEMA QUE RESUELVE. El tema del greeter vive en /usr/share, que es de
# root, asi que al principio cambiar el fondo del login pedia pasar
# `./instalar.sh --sddm` a mano y teclear la contrasena. Para quien cambia de
# fondo a menudo eso es inservible: el login se quedaba con un fondo viejo.
#
# LA VUELTA QUE SE LE DIO. `instalar.sh --sddm` crea UNA VEZ (esa si con sudo)
# la carpeta compartida de abajo, tuya y legible por el usuario `sddm`, y deja
# `fondo.jpg` y `fondo.mp4` del tema como ENLACES a ella. El QML los carga por
# ruta relativa, asi que no se entera de nada. A partir de ahi esto escribe en
# una carpeta tuya y no hace falta root nunca mas.
#
# La carpeta es setgid y del grupo `sddm` (2750), que es lo que hace que los
# ficheros que crees aqui nazcan con ese grupo y el greeter pueda leerlos. Sin
# el setgid naceria con TU grupo y el greeter veria un permiso denegado — y en
# el arranque eso se traduce en "el fondo no sale", sin mas explicacion.
#
# Lo llama solo `lib/wallpapers.py` al fijar un fondo, en segundo plano. Tambien
# se puede a mano:
#
#   sddm-fondo.sh              # rehace el fondo si hace falta
#   sddm-fondo.sh --forzar     # rehacelo aunque parezca al dia
#   sddm-fondo.sh --revisar    # di como esta, sin tocar nada

set -uo pipefail

RAIZ="$(cd "$(dirname "$(readlink -f "$BASH_SOURCE")")/../.." && pwd)"
COMPARTIDA="${SDDM_COMPARTIDA:-/var/lib/sddm-celiuz}"
ACTUAL="$RAIZ/hypr/wallpapers/current"
PANTALLA="$RAIZ/hypr/scripts/lib/pantalla.py"

# Segundos de video que se copian. El greeter se ve unos segundos y esto acaba
# en /var/lib, que no es sitio para los 700 MB de un fondo largo.
SEGUNDOS="${SDDM_SEGUNDOS:-30}"

# La huella de lo ultimo que se genero. Sirve para no reencodear 7,5 segundos de
# video cada vez que fijas el MISMO fondo, que pasa mas de lo que parece.
HUELLA="$COMPARTIDA/.origen"

FORZAR=0
REVISAR=0
case "${1:-}" in
    --forzar)  FORZAR=1 ;;
    --revisar) REVISAR=1 ;;
    "")        ;;
    *) echo "sddm-fondo: no entiendo «$1». Prueba --forzar o --revisar" >&2; exit 2 ;;
esac

decir() { [ "$REVISAR" -eq 1 ] && echo "$@"; return 0; }

# --- Se puede? ---------------------------------------------------------------
# Sin carpeta compartida no hay nada que hacer, y NO es un error: significa que
# esta maquina no tiene puesta la pantalla de inicio de sesion, o que se instalo
# con el metodo viejo. Se sale en silencio porque a esto lo llama el cambio de
# fondo, y un fallo ruidoso ahi estropearia algo que funciona.
if [ ! -d "$COMPARTIDA" ]; then
    decir "sin pantalla de inicio propia: no hay $COMPARTIDA"
    decir "  se pone con:  ./instalar.sh --sddm"
    exit 0
fi
if [ ! -w "$COMPARTIDA" ]; then
    decir "$COMPARTIDA existe pero no puedo escribir en ella"
    decir "  se arregla volviendo a pasar:  ./instalar.sh --sddm"
    exit 0
fi

# SDDM_ORIGEN existe para poder probar esto sin cambiar el fondo de verdad de
# nadie: con el se prueban el camino de la imagen fija y el del video sin tocar
# el enlace `current` de la sesion viva. Igual que los ajustes por entorno de
# lock.sh, y por la misma razon.
origen="${SDDM_ORIGEN:-}"
[ -z "$origen" ] && [ -e "$ACTUAL" ] && origen="$(readlink -f "$ACTUAL")"
if [ -z "$origen" ] || [ ! -f "$origen" ]; then
    decir "todavia no hay fondo elegido"
    exit 0
fi

ancho="$("$PANTALLA" ancho 2>/dev/null)"; [ -n "$ancho" ] || ancho=1920
alto="$("$PANTALLA" alto  2>/dev/null)"; [ -n "$alto"  ] || alto=1080

# La huella lleva la pantalla ademas del fichero: si cambias de monitor hay que
# rehacerlo aunque el fondo sea el mismo.
nueva="$origen|$(stat -c %Y "$origen" 2>/dev/null)|${ancho}x${alto}|$SEGUNDOS"

if [ "$REVISAR" -eq 1 ]; then
    echo "fondo:     $(basename "$origen")"
    echo "pantalla:  ${ancho}x${alto}"
    echo "carpeta:   $COMPARTIDA"
    for f in fondo.jpg fondo.mp4; do
        if [ -f "$COMPARTIDA/$f" ]; then
            echo "  $f  $(du -h "$COMPARTIDA/$f" | cut -f1)"
        else
            echo "  $f  (no esta)"
        fi
    done
    if [ "$(cat "$HUELLA" 2>/dev/null)" = "$nueva" ]; then
        echo "al dia: si"
    else
        echo "al dia: NO — se rehara al fijar un fondo, o con --forzar"
    fi
    exit 0
fi

if [ "$FORZAR" -eq 0 ] && [ "$(cat "$HUELLA" 2>/dev/null)" = "$nueva" ]; then
    exit 0
fi

# Un solo generador a la vez. Sin esto, fijar tres fondos seguidos deja tres
# ffmpeg peleandose por el mismo fichero de salida. `-n` = si ya hay uno
# trabajando, este se va: el que esta dentro hara el ultimo fondo de todos
# modos, porque relee `current` al empezar.
exec 9>"$COMPARTIDA/.candado"
flock -n 9 || exit 0

# Llenar la pantalla aunque la proporcion no cuadre, igual que --panscan=1.0 en
# el escritorio: mejor recortar que dejar franjas negras.
escalar="scale=$ancho:$alto:force_original_aspect_ratio=increase,crop=$ancho:$alto"

# Se escribe al lado y se mueve encima, para que el greeter no pueda pillar un
# fichero a medias si arrancara justo ahora.
#
# LOS TEMPORALES SE LLAMAN `fondo.nuevo.jpg`, NO `fondo.jpg.nuevo`, Y ES
# OBLIGATORIO: ffmpeg elige el formato de salida POR LA EXTENSION, asi que con
# `.nuevo` al final responde «Unable to choose an output format» y no escribe
# nada. Este repo ya tropezo con esto en la pantalla de bloqueo (el temporal se
# llama `lock-bg.tmp.jpg` por lo mismo). Si mueves esto, deja la extension real
# al final.
TMP_JPG="$COMPARTIDA/fondo.nuevo.jpg"
TMP_MP4="$COMPARTIDA/fondo.nuevo.mp4"

poner() {
    local tmp="$1" destino="$2"
    chmod 644 "$tmp" 2>/dev/null
    mv -f "$tmp" "$destino"
}

es_imagen=0
case "${origen,,}" in
    *.jpg|*.jpeg|*.png|*.webp|*.bmp|*.avif|*.jxl) es_imagen=1 ;;
esac

# El fotograma va SIEMPRE y va primero: es la red de seguridad. Pesa nada y
# sirve aunque el equipo no tenga con que decodificar video, en cuyo caso el
# tema se queda en la imagen fija en vez de en el degradado.
#
# El `-ss 1` (saltar al segundo 1) es solo para video: muchos empiezan en negro
# y el fotograma saldria una pantalla oscura. En una imagen no hay a donde
# saltar, y pedirlo la deja sin decodificar.
salto=()
[ "$es_imagen" -eq 1 ] || salto=(-ss 1)

algo=0   # se llego a generar algo utilizable?

if nice -n 15 ffmpeg -v error -y "${salto[@]}" \
        -i "$origen" -frames:v 1 -vf "$escalar" -q:v 3 \
        "$TMP_JPG" 2>/dev/null; then
    poner "$TMP_JPG" "$COMPARTIDA/fondo.jpg"
    algo=1
else
    rm -f "$TMP_JPG"
fi

if [ "$es_imagen" -eq 1 ]; then
    # Un fondo de imagen no tiene video. Se quita el que hubiera, o el login
    # seguiria enseñando el video del fondo ANTERIOR sobre la imagen nueva.
    rm -f "$COMPARTIDA/fondo.mp4"
else
    if nice -n 15 ffmpeg -v error -y -i "$origen" -t "$SEGUNDOS" -an \
            -vf "$escalar" -c:v libx264 -preset veryfast -crf 26 \
            -pix_fmt yuv420p "$TMP_MP4" 2>/dev/null; then
        poner "$TMP_MP4" "$COMPARTIDA/fondo.mp4"
        algo=1
    else
        rm -f "$TMP_MP4"
    fi
fi

# La huella SOLO si salio algo. Escribirla pasara lo que pasara era un fallo de
# la primera version: con ffmpeg fallando, el fondo se quedaba sin generar Y
# ademas quedaba marcado como "al dia", asi que no se reintentaba nunca mas —
# ni al cambiar de fondo. Fallar y que se note es preferible.
[ "$algo" -eq 1 ] && printf '%s' "$nueva" > "$HUELLA"
exit 0
