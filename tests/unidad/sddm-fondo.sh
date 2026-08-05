#!/usr/bin/env bash
# tests/unidad/sddm-fondo.sh — el fondo de la pantalla de inicio de sesion.
#
# Este script corre SOLO, en segundo plano, cada vez que cambias de fondo. O sea
# que si falla, falla sin que nadie mire: no hay ventana donde salga el error, y
# lo unico que notarias es que el login se quedo con un fondo viejo. Por eso se
# prueba aqui, y por eso se prueba sobre todo lo que ya salio mal.
#
# NO SE EJECUTA ffmpeg DE VERDAD. Se pone uno falso en el PATH que apunta con
# que argumentos le llamaron y crea el fichero de salida. Asi la prueba tarda
# milisegundos en vez de ocho segundos por caso, y ademas permite comprobar lo
# que de verdad importaba: COMO SE LLAMA EL FICHERO TEMPORAL.
#
# Ese fue el fallo que costo encontrar al escribirlo: el temporal se llamaba
# `fondo.jpg.nuevo`, y ffmpeg elige el formato de salida POR LA EXTENSION, asi
# que respondia «Unable to choose an output format» y no escribia nada. Con el
# stderr silenciado —como corresponde a algo que corre en segundo plano— el
# sintoma era, exactamente, que no pasaba nada. El repo ya habia tropezado con
# esto en la pantalla de bloqueo. La prueba 3 es el cerrojo para que no vuelva.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

GEN="$REPO/hypr/scripts/sddm-fondo.sh"
COMPARTIDA="$TMP/compartida"

# El ffmpeg falso crea su fichero de salida (el ultimo argumento), que es lo que
# hace el de verdad y lo que necesita el `mv` de despues.
binario_falso ffmpeg 0 'salida="${@: -1}"; : > "$salida"'

# Fuentes de mentira. La extension es lo unico que mira el script para decidir
# si hay video o no, asi que no hace falta que sean ficheros reales.
VIDEO="$TMP/fondo-falso.mp4"; : > "$VIDEO"
IMAGEN="$TMP/fondo-falso.png"; : > "$IMAGEN"

correr() { SDDM_COMPARTIDA="$COMPARTIDA" SDDM_ORIGEN="$1" "$GEN" "${2:-}"; }

titulo "1. Sin carpeta compartida no hace nada (ni falla)"
# Es el caso de una maquina sin pantalla de inicio propia. Como a esto lo llama
# el cambio de fondo, tiene que irse en silencio: un fallo ruidoso aqui
# estropearia algo que funciona.
rm -rf "$COMPARTIDA"
correr "$VIDEO" >/dev/null 2>&1
afirmar_igual "0" "$?"                  "sale bien aunque no haya donde escribir"
afirmar_igual "0" "$(veces_llamado ffmpeg)" "no llama a ffmpeg para nada"
afirmar "no se inventa la carpeta" test ! -d "$COMPARTIDA"

titulo "2. Con un fondo de video deja las dos piezas"
mkdir -p "$COMPARTIDA"
correr "$VIDEO" >/dev/null 2>&1
afirmar "deja el fotograma de reserva" test -f "$COMPARTIDA/fondo.jpg"
afirmar "deja el video"                test -f "$COMPARTIDA/fondo.mp4"
afirmar_igual "2" "$(veces_llamado ffmpeg)" "llama a ffmpeg dos veces"
afirmar "no deja temporales tirados" test -z "$(find "$COMPARTIDA" -name '*nuevo*' -print -quit)"

titulo "3. El temporal lleva la extension AL FINAL (el fallo de ffmpeg)"
# Si alguien vuelve a llamarlo `fondo.jpg.nuevo`, ffmpeg no sabra que formato
# escribir y esto dejara de funcionar en silencio.
malos=$(grep -c -E '\.(jpg|mp4)\.[a-z]+( |$)' "$REGISTRO/ffmpeg.log" || true)
afirmar_igual "0" "$malos" "ningun fichero de salida entierra su extension"
afirmar_contiene "$REGISTRO/ffmpeg.log" '\.jpg( |$)' "el fotograma sale a un .jpg"
afirmar_contiene "$REGISTRO/ffmpeg.log" '\.mp4( |$)' "el video sale a un .mp4"

titulo "4. La huella evita rehacerlo por gusto"
antes=$(veces_llamado ffmpeg)
correr "$VIDEO" >/dev/null 2>&1
afirmar_igual "$antes" "$(veces_llamado ffmpeg)" "el mismo fondo no se reencodea"
correr "$VIDEO" --forzar >/dev/null 2>&1
[ "$(veces_llamado ffmpeg)" -gt "$antes" ] \
    && ok "con --forzar si lo rehace" \
    || fallo "con --forzar si lo rehace"

titulo "5. Un fondo de imagen no deja el video del anterior"
# Sin esto, el login enseñaria el video del fondo VIEJO por debajo de la imagen
# nueva, que es de las cosas que se ven raras y no sabrias explicar.
afirmar "de partida hay un video" test -f "$COMPARTIDA/fondo.mp4"
correr "$IMAGEN" >/dev/null 2>&1
afirmar "la imagen deja su fotograma"  test -f "$COMPARTIDA/fondo.jpg"
afirmar "y QUITA el video que habia"   test ! -f "$COMPARTIDA/fondo.mp4"

titulo "6. Si ffmpeg falla, NO se marca como al dia"
# Era el segundo fallo de la primera version: la huella se escribia pasara lo
# que pasara, asi que un ffmpeg roto dejaba el fondo sin generar Y marcado como
# bueno, y no se reintentaba nunca mas.
rm -rf "$COMPARTIDA"; mkdir -p "$COMPARTIDA"
binario_falso ffmpeg 1
correr "$VIDEO" >/dev/null 2>&1
afirmar "no deja huella si no salio nada" test ! -f "$COMPARTIDA/.origen"
afirmar "y no deja ficheros a medias"     test ! -f "$COMPARTIDA/fondo.jpg"

titulo "7. No toco nada de tu equipo"
afirmar_intacta_la_casa_real

resumen
