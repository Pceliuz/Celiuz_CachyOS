#!/usr/bin/env bash
# tests/unidad/fondos.sh — lib/wallpapers.py: de donde salen los fondos.
#
# Todo esto corre con un HOME de mentira, asi que no depende de que tengas Steam,
# ni Wallpaper Engine, ni fondos de verdad. En una maquina recien clonada da el
# mismo resultado que en la del autor, que es justo lo que se quiere comprobar:
# que la app se adapta al equipo en el que se abre.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
LIB="$REPO/hypr/scripts/lib"

# Pregunta algo a la libreria y lo imprime. Se llama a python de una vez por
# consulta para que cada caso empiece limpio.
consultar() { python3 -c "
import sys; sys.path.insert(0, '$LIB')
import wallpapers as wp
$1"; }

titulo "1. La carpeta de videos, en el idioma que sea"

# Caso espanol, que es como esta el equipo del autor.
mkdir -p "$HOME/Vídeos"
printf 'XDG_VIDEOS_DIR="$HOME/Vídeos"\n' > "$XDG_CONFIG_HOME/user-dirs.dirs"
afirmar_igual "$HOME/Vídeos" "$(consultar 'print(wp.carpeta_videos() or "")')" \
    "encuentra ~/Vídeos con tilde (sistema en espanol)"

# Caso ingles: otra maquina, otro nombre. No se adivina, se pregunta a XDG.
rm -rf "$HOME/Vídeos"; mkdir -p "$HOME/Videos"
printf 'XDG_VIDEOS_DIR="$HOME/Videos"\n' > "$XDG_CONFIG_HOME/user-dirs.dirs"
afirmar_igual "$HOME/Videos" "$(consultar 'print(wp.carpeta_videos() or "")')" \
    "encuentra ~/Videos (sistema en ingles)"

# Caso raro: un nombre que no adivinaria nadie.
rm -rf "$HOME/Videos"; mkdir -p "$HOME/Filmy"
printf 'XDG_VIDEOS_DIR="$HOME/Filmy"\n' > "$XDG_CONFIG_HOME/user-dirs.dirs"
afirmar_igual "$HOME/Filmy" "$(consultar 'print(wp.carpeta_videos() or "")')" \
    "encuentra una carpeta con nombre inesperado (se pregunta, no se adivina)"

# Caso sin configurar: XDG contesta el propio HOME, y recorrer la casa entera
# no es lo que nadie espera.
rm -f "$XDG_CONFIG_HOME/user-dirs.dirs"; rm -rf "$HOME/Filmy"
afirmar_igual "" "$(consultar 'print(wp.carpeta_videos() or "")')" \
    "sin carpeta de videos, no se inventa ninguna (ni usa el HOME entero)"

titulo "1b. La carpeta de imagenes, tambien en el idioma que sea"
mkdir -p "$HOME/Vídeos" "$HOME/Imágenes"
printf 'XDG_VIDEOS_DIR="$HOME/Vídeos"\nXDG_PICTURES_DIR="$HOME/Imágenes"\n' \
    > "$XDG_CONFIG_HOME/user-dirs.dirs"
afirmar_igual "$HOME/Imágenes" "$(consultar 'print(wp.carpeta_imagenes() or "")')" \
    "encuentra ~/Imágenes con tilde (sistema en espanol)"

rm -rf "$HOME/Imágenes"; mkdir -p "$HOME/Pictures"
printf 'XDG_VIDEOS_DIR="$HOME/Vídeos"\nXDG_PICTURES_DIR="$HOME/Pictures"\n' \
    > "$XDG_CONFIG_HOME/user-dirs.dirs"
afirmar_igual "$HOME/Pictures" "$(consultar 'print(wp.carpeta_imagenes() or "")')" \
    "encuentra ~/Pictures (sistema en ingles)"

# Las dos carpetas son DOS modulos distintos, con el nombre que tengan de verdad.
: > "$HOME/Vídeos/clip.mp4"
: > "$HOME/Pictures/fondo.jpg"
afirmar_igual "['Vídeos', 'Pictures']" \
    "$(consultar 'print([f["nombre"] for f in wp.fuentes() if f["id"] in ("videos","imagenes")])')" \
    "salen como dos modulos, cada uno con su nombre real"
afirmar_igual "1" "$(consultar 'print(len(wp.por_fuente().get("imagenes", [])))')" \
    "el modulo de imagenes ensena lo que hay dentro"

# Si un equipo tuviera las dos apuntando al mismo sitio, una sola pestana.
rm -rf "$HOME/Pictures"
printf 'XDG_VIDEOS_DIR="$HOME/Vídeos"\nXDG_PICTURES_DIR="$HOME/Vídeos"\n' \
    > "$XDG_CONFIG_HOME/user-dirs.dirs"
afirmar_igual "1" \
    "$(consultar 'print(len([f for f in wp.fuentes() if f["id"] in ("videos","imagenes")]))')" \
    "si las dos apuntan al mismo sitio, no se duplica la pestana"
rm -f "$HOME/Vídeos/clip.mp4"

titulo "2. Que encuentra dentro"
mkdir -p "$HOME/Vídeos/anime" "$HOME/Vídeos/.oculta"
printf 'XDG_VIDEOS_DIR="$HOME/Vídeos"\n' > "$XDG_CONFIG_HOME/user-dirs.dirs"
rm -rf "$HOME/Imágenes" "$HOME/Pictures"
: > "$HOME/Vídeos/uno.mp4"
: > "$HOME/Vídeos/dos.MKV"
: > "$HOME/Vídeos/anime/tres.webm"
: > "$HOME/Vídeos/.oculta/no-cuenta.mp4"
: > "$HOME/Vídeos/.tambien-oculto.mp4"
: > "$HOME/Vídeos/documento.txt"

afirmar_igual "3" "$(consultar 'print(len(wp.escanear()))')" \
    "coge los videos, entra en subcarpetas y deja fuera ocultos y no-videos"
afirmar_igual "1" "$(consultar 'print(int(any("dos" == f["titulo"] for f in wp.escanear())))')" \
    "reconoce la extension en mayusculas (.MKV)"

titulo "3. Carpetas que anade el usuario"
mkdir -p "$TMP/mis-fondos"
: > "$TMP/mis-fondos/extra.mp4"
afirmar_igual "True" "$(consultar "print(wp.anadir_carpeta('$TMP/mis-fondos'))")" \
    "se puede anadir una carpeta"
afirmar_igual "False" "$(consultar "print(wp.anadir_carpeta('$TMP/mis-fondos'))")" \
    "no se anade dos veces la misma"
afirmar_igual "False" "$(consultar "print(wp.anadir_carpeta(wp.carpeta_videos()))")" \
    "no se anade una que ya cubre otra fuente"
afirmar "se guarda FUERA del repo, en la config del usuario" \
    test -f "$XDG_CONFIG_HOME/celiuzpaper/carpetas.json"
afirmar "no deja rastro dentro del repo" \
    test ! -e "$REPO/celiuzpaper/carpetas.json"
afirmar_igual "4" "$(consultar 'print(len(wp.escanear()))')" \
    "los fondos de la carpeta anadida aparecen"

# Quitarla no borra nada del disco: eso seria una sorpresa muy desagradable.
consultar "wp.quitar_carpeta('$TMP/mis-fondos')" >/dev/null
afirmar "al quitarla, el video sigue en su sitio" test -f "$TMP/mis-fondos/extra.mp4"
afirmar_igual "3" "$(consultar 'print(len(wp.escanear()))')" "y deja de listarse"

titulo "4. Imagenes fijas, no solo videos"
# Casi todo lo que se descarga por ahi (wallhaven.cc y los repos de fondos de
# GitHub) son imagenes, asi que tienen que valer igual que un video.
: > "$HOME/Vídeos/foto.jpg"
: > "$HOME/Vídeos/otra.PNG"
: > "$HOME/Vídeos/mapa.svg"
afirmar_igual "5" "$(consultar 'print(len(wp.escanear()))')" \
    "coge jpg y png (y en mayusculas), pero no un svg"
afirmar_igual "True" "$(consultar 'print(wp.es_imagen("x.WEBP"))')" "reconoce webp como imagen"
afirmar_igual "False" "$(consultar 'print(wp.es_imagen("x.mp4"))')" "y un mp4 no lo es"
afirmar_igual "1" "$(consultar '
f = [x for x in wp.escanear() if x["titulo"] == "foto"][0]
print(int(f["imagen"]))')" "el fondo queda marcado como imagen"
afirmar_igual "1" "$(consultar '
f = [x for x in wp.escanear() if x["titulo"] == "uno"][0]
print(int(not f["imagen"]))')" "y un video, como video"

# Con una imagen DE VERDAD: que salga miniatura y que la ficha no hable de
# segundos, que es lo que ffprobe contestaria (0,04 s) y no significa nada.
if command -v ffmpeg >/dev/null 2>&1; then
    ffmpeg -nostdin -v error -f lavfi -i "testsrc=size=800x600:rate=1" \
        -frames:v 1 -y "$HOME/Vídeos/real.png" 2>/dev/null
    salida="$(consultar '
f = [x for x in wp.escanear() if x["titulo"] == "real"][0]
m = wp.miniatura(f, generar=True)
import os
print("MINI", bool(m) and os.path.exists(m) and os.path.getsize(m) > 0)
print("FICHA", wp.describir(f))')"
    printf '%s' "$salida" > "$TMP/imagen.txt"
    afirmar_contiene "$TMP/imagen.txt" 'MINI True' "genera miniatura de una imagen de verdad"
    afirmar_contiene "$TMP/imagen.txt" 'imagen fija' "la ficha dice «imagen fija»"
    afirmar_no_contiene "$TMP/imagen.txt" 'FICHA.*[0-9] s' "y NO se inventa una duracion"
else
    gris "  (sin ffmpeg: me salto la miniatura de verdad)"
fi
rm -f "$HOME/Vídeos/foto.jpg" "$HOME/Vídeos/otra.PNG" "$HOME/Vídeos/mapa.svg" "$HOME/Vídeos/real.png"

titulo "5. Sin nada instalado (equipo recien clonado)"
rm -f "$XDG_CONFIG_HOME/user-dirs.dirs"
rm -rf "$HOME/Vídeos"
afirmar_igual "[]" "$(consultar 'print([f["id"] for f in wp.fuentes() if f["id"] != "repo"])')" \
    "sin Steam y sin carpeta de videos no hay fuentes propias"
afirmar "no revienta al escanear sin nada" consultar 'wp.escanear()'
afirmar "no revienta al pedir los usables" consultar 'wp.usables()'

titulo "6. No toco nada de tu equipo"
afirmar_intacta_la_casa_real

resumen
