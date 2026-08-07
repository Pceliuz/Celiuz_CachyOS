#!/usr/bin/env bash
# tests/e2e/fondo.sh — wallpaper.sh: como se lanza el fondo.
#
# Lo que se comprueba es la diferencia entre poner un VIDEO y poner una IMAGEN.
# Es una sola bandera, pero sin ella una imagen se ve 5 segundos y despues la
# pantalla se queda negra: el sintoma seria "puse un fondo y desaparecio solo",
# que es de los que cuesta relacionar con su causa.
#
# CUIDADO AL LEER ESTO: wallpaper.sh empieza matando mpvpaper y el demonio de
# ahorro, porque su trabajo es relanzarlos. Ejecutarlo tal cual durante una
# prueba TE MATARIA EL FONDO DE LA SESION. Por eso aqui son falsos tambien
# `pkill`, `pgrep` y `setsid`: la prueba mira que se llamo a mpvpaper con las
# banderas correctas, sin que muera ni se lance nada de verdad.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

# El PID del mpvpaper de VERDAD, antes de empezar. Si al terminar no es el mismo,
# la prueba le ha matado el fondo al usuario y eso es un fallo gravisimo.
MPV_ANTES="$(pgrep -x mpvpaper 2>/dev/null | head -1)"

preparar_entorno

titulo "Preparando (con pkill y pgrep falsos, para no tocar tu fondo)"
binario_falso mpvpaper 0
# pkill que no mata a nadie: solo apunta a quien le habrian pedido matar.
binario_falso pkill 0
# pgrep que dice "ya esta corriendo", para que no se lance ningun demonio nuevo.
binario_falso pgrep 0
# setsid que no arranca nada.
binario_falso setsid 0
_gris "  ninguno de los cuatro hace nada de verdad"

# El fondo activo es el enlace `current`. Se apunta a un fichero de mentira
# dentro del temporal; wallpaper.sh resuelve el enlace para mirar la extension.
WALLDIR="$TMP/wallpapers"
mkdir -p "$WALLDIR"

poner_fondo() {
    # $1 = nombre del fichero al que apunta `current`
    : > "$TMP/$1"
    ln -sfn "$TMP/$1" "$WALLDIR/current"
    rm -rf "$REGISTRO"; mkdir -p "$REGISTRO"
    # Se copia el script a un sitio donde `..` caiga en nuestro WALLDIR, porque
    # wallpaper.sh busca ../wallpapers/current desde donde esta el.
    mkdir -p "$TMP/scripts"
    cp "$REPO/hypr/scripts/wallpaper.sh" "$TMP/scripts/"
    # Y lib/, porque wallpaper.sh hace `source` de lib/canales.sh. Sin esto el
    # `source` fallaba, el script seguia sin sus funciones —en bash un `source`
    # roto no corta nada— y la prueba estaba midiendo un wallpaper.sh CAPADO:
    # verde, pero sin ejercer la parte que decide a quien matar. Ahora el script
    # se planta si no encuentra la lib, y aqui se le da.
    cp -r "$REPO/hypr/scripts/lib" "$TMP/scripts/"
    "$TMP/scripts/wallpaper.sh" --only-mpv >/dev/null 2>&1
}

titulo "1. Un video se lanza como siempre"
poner_fondo "pelicula.mp4"
afirmar_igual "1" "$(veces_llamado mpvpaper)" "lanza mpvpaper"
afirmar_contiene "$REGISTRO/mpvpaper.log" 'loop-file=inf' "en bucle infinito"
afirmar_contiene "$REGISTRO/mpvpaper.log" 'hwdec=auto' "con decodificacion por hardware"
afirmar_contiene "$REGISTRO/mpvpaper.log" 'input-ipc-server' "con el socket para el demonio de ahorro"
afirmar_no_contiene "$REGISTRO/mpvpaper.log" 'image-display-duration' \
    "SIN la bandera de imagen (a un video le sobra)"

titulo "2. Una imagen se queda fija"
for ext in jpg png webp JPEG; do
    poner_fondo "foto.$ext"
    afirmar_contiene "$REGISTRO/mpvpaper.log" 'image-display-duration=inf' \
        ".$ext se lanza con la bandera que la deja fija"
done

titulo "3. La extension se mira en el DESTINO, no en el enlace"
# `current` no tiene extension: si se mirara su nombre, ninguna imagen se
# detectaria nunca. Se comprueba de verdad que se resuelve el enlace.
poner_fondo "sin-extension-en-el-enlace.png"
afirmar_contiene "$REGISTRO/mpvpaper.log" 'image-display-duration=inf' \
    "resuelve el enlace \"current\" para saber que es una imagen"

titulo "4. No mato nada de tu sesion"
# Ya no se mata por nombre, asi que lo que hay que exigir es lo contrario que
# antes: que NO se llame a pkill. Se reconoce al mpvpaper propio por la ruta de
# su socket, que lleva la firma de la sesion; sin firma —como aqui, que
# preparar_entorno la quita— esa ruta es la de "sin-sesion" y no la lleva nadie,
# asi que no hay a quien matar. Antes, `pkill -x mpvpaper` se llevaba por delante
# el fondo de CUALQUIER sesion del usuario.
afirmar "no se llama a pkill (ya no se mata por nombre)" \
    test ! -f "$REGISTRO/pkill.log"
# Se mira con el PATH original: dentro del entorno de prueba, `pgrep` es falso.
MPV_DESPUES="$(PATH="${PATH#"$FALSOS":}" pgrep -x mpvpaper 2>/dev/null | head -1)"
afirmar_igual "$MPV_ANTES" "$MPV_DESPUES" \
    "tu mpvpaper de verdad sigue siendo el mismo proceso (no se relanzo nada)"
afirmar_intacta_la_casa_real

resumen
