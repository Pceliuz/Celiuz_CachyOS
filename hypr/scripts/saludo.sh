#!/usr/bin/env bash
# hypr/scripts/saludo.sh — el saludo al abrir una terminal: fastfetch con una
# imagen al azar al lado. instalar.sh lo enlaza como ~/.local/bin/celiuz-saludo
# y lo pone de fish_greeting.
#
# LAS IMAGENES
# ------------
# Viven en el repo, en fastfetch/imagenes/, y se instalan con los dotfiles:
# para quitar una, se borra de ahi; para poner otra, se copia ahi. PNG, JPG,
# WebP o GIF; las de fondo transparente quedan mejor. OJO: pueden estar aqui
# porque el repo es PRIVADO (desde el 2026-10-20) —las de anime no son nuestras
# para repartir—. Si algun dia se hace publico, esta carpeta sale antes.
#
# Antes de dibujarla se ADAPTA (lib/imagen_saludo.py): se reduce, a un sticker
# se le recorta el aire transparente de alrededor y a una foto se le redondean
# las esquinas. La copia va a ~/.cache/celiuz/saludo y se hace UNA vez por
# imagen (la clave lleva tamaño y fecha: si cambias el fichero, se rehace). El
# original no se toca. Si no se puede adaptar, se usa tal cual.
#
# Se dibujan con el protocolo de imagenes de kitty. Una terminal que no lo
# entienda, o la carpeta vacia, dan el logo de la distro: nunca un saludo roto.
#
#   celiuz-saludo             el saludo
#   celiuz-saludo IMAGEN      con esa imagen (para probar una)
#   celiuz-saludo --carpeta   dice de que carpeta las coge
#   celiuz-saludo --preparar  adapta ya todas (la primera vez de cada una, si
#                             no, tarda un poco mas en abrir esa terminal)
#   celiuz-saludo --medidas FILAS COLUMNAS   las cuentas de abajo, sin dibujar
#
# EL TAMAÑO Y EL SITIO (2026-10-21; antes era fijo, 22x11 celdas pegado arriba
# a la izquierda, y en una terminal grande se quedaba chico y de lado). Se mide
# la terminal al abrirse (`medidas`):
#   - la imagen crece con la terminal hasta el alto del cuadro de datos (unas
#     ALTO_DATOS filas), y si es mas baja se centra en vertical contra el;
#   - imagen y datos van centrados en horizontal;
#   - si al lado no caben (una terminal partida en mosaico), la imagen va
#     ENCIMA de los datos, mas pequeña, en vez de pisarlos.
# Una celda de kitty es el doble de alta que de ancha: una caja de 2N x N
# celdas es cuadrada, y la imagen se ajusta dentro sin deformarse.

# La raiz se saca del propio script atravesando el enlace de ~/.local/bin
# (la regla del CLAUDE.md: nada de ~/dotfiles cableado).
carpeta() {
    local raiz
    raiz="$(dirname "$(dirname "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")")")"
    printf '%s/fastfetch/imagenes\n' "$raiz"
}

# ¿Entiende la terminal el protocolo de imagenes de kitty? Se mira lo que dice
# de si misma; sin preguntar por la propia terminal (eso tarda y ensucia).
sabe_imagenes() {
    [ -n "$KITTY_WINDOW_ID" ] && return 0
    case "$TERM" in xterm-kitty|xterm-ghostty|wezterm) return 0 ;; esac
    case "$TERM_PROGRAM" in ghostty|WezTerm) return 0 ;; esac
    return 1
}

# al_azar CARPETA → una imagen que no haya salido en esta VUELTA. Las ya vistas
# se apuntan (solo el nombre) en ~/.local/state/celiuz/saludo-vistas; cuando han
# salido todas, empieza otra vuelta SIN la mitad mas reciente de la anterior:
# quitar solo la ultima no basta, la penultima podia volver a la siguiente
# terminal. Asi entre dos veces de la misma imagen salen al menos la mitad de
# las demas (con 450 imagenes, 225 terminales).
# Las que añadas entran en la vuelta en curso y las que borres dejan de contar.
# Con flock: dos terminales abiertas a la vez no sacan la misma.
VISTAS="${XDG_STATE_HOME:-$HOME/.local/state}/celiuz/saludo-vistas"
al_azar() {
    local d="$1" lista=() quedan elegida ultima
    shopt -s nullglob nocaseglob
    lista=("$d"/*.png "$d"/*.jpg "$d"/*.jpeg "$d"/*.webp "$d"/*.gif)
    shopt -u nullglob nocaseglob
    [ ${#lista[@]} -gt 0 ] || return 1
    mkdir -p "$(dirname "$VISTAS")"
    exec 9>>"$VISTAS.lock"
    flock -w 2 9 || true
    touch "$VISTAS"
    quedan="$(printf '%s\n' "${lista[@]##*/}" | grep -Fxv -f "$VISTAS")"
    if [ -z "$quedan" ]; then
        ultima="$(tail -n1 "$VISTAS")"
        local mitad=$(( ${#lista[@]} / 2 )); [ "$mitad" -ge 1 ] || mitad=1
        tail -n "$mitad" "$VISTAS" > "$VISTAS.nuevo" && mv -f "$VISTAS.nuevo" "$VISTAS"
        quedan="$(printf '%s\n' "${lista[@]##*/}" | grep -Fxv -f "$VISTAS")"
        [ -n "$quedan" ] || quedan="$ultima"     # una sola imagen: esa
    fi
    elegida="$(printf '%s\n' "$quedan" | shuf -n1)"
    printf '%s\n' "$elegida" >> "$VISTAS"
    exec 9>&-
    printf '%s/%s\n' "$d" "$elegida"
}

LIB="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/lib"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/celiuz/saludo"
# Lo que ocupa el cuadro de datos de fastfetch/plantilla.jsonc: 14 datos, dos
# saltos y los puntos (uno menos sin GPU dedicada o sin bateria), y de ancho el
# icono, el separador y el dato mas largo («75.55 GiB / 927.51 GiB (8%) - btrfs»).
ALTO_DATOS=16
ANCHO_DATOS=46

# medidas FILAS COLUMNAS → «ancho alto izquierda arriba posicion» de la imagen,
# en celdas; posicion es left (al lado) o top (encima). Ancho 0: sin imagen.
medidas() {
    local filas="$1" cols="$2" alto ancho izq arriba
    # Algo que no sea un numero (stty sin terminal, LINES vacia): 24x80.
    [[ "$filas" =~ ^[0-9]+$ ]] || filas=24
    [[ "$cols" =~ ^[0-9]+$ ]] || cols=80
    alto=$(( filas / 2 ))
    [ "$alto" -le "$ALTO_DATOS" ] || alto=$ALTO_DATOS
    [ "$alto" -ge 8 ] || alto=8
    ancho=$(( alto * 2 ))
    # Si al lado no cabe entera, mas pequeña pero al lado, mientras se vea.
    if [ $(( ancho + 6 + ANCHO_DATOS )) -gt "$cols" ]; then
        ancho=$(( cols - 6 - ANCHO_DATOS ))
        alto=$(( ancho / 2 ))
    fi
    if [ "$ancho" -ge 16 ]; then
        # Al lado. Centrado: lo que sobra, a partes iguales a cada lado.
        izq=$(( (cols - ancho - 4 - ANCHO_DATOS) / 2 ))
        [ "$izq" -ge 2 ] || izq=2
        arriba=$(( 1 + (ALTO_DATOS - alto) / 2 ))
        echo "$ancho $alto $izq $arriba left"
        return
    fi
    # No cabe al lado: encima, y mas pequeña (que se vean los datos sin
    # desplazar la terminal).
    alto=$(( filas / 2 ))
    [ "$alto" -le 10 ] || alto=10
    ancho=$(( alto * 2 ))
    [ "$ancho" -le $(( cols - 4 )) ] || { ancho=$(( cols - 4 )); alto=$(( ancho / 2 )); }
    if [ "$alto" -lt 4 ]; then
        echo "0 0 0 0 none"
        return
    fi
    izq=$(( (cols - ancho) / 2 ))
    [ "$izq" -ge 1 ] || izq=1
    echo "$ancho $alto $izq 1 top"
}

# tamano_terminal → «FILAS COLUMNAS» de la terminal donde se abre el saludo.
tamano_terminal() {
    local t
    # Solo si se pinta en una terminal de verdad (en una prueba, con la
    # salida a un fichero, valen LINES y COLUMNS).
    if [ -t 1 ]; then
        t="$(stty size 2>/dev/null </dev/tty)" && [ -n "$t" ] && { echo "$t"; return; }
    fi
    echo "${LINES:-24} ${COLUMNS:-80}"
}

# copia_de RUTA → donde va (o esta) la copia adaptada de esa imagen. La clave
# lleva tamaño y fecha: si cambias el fichero, se rehace.
copia_de() {
    printf '%s/%s-%s.png\n' "$CACHE" "$(stat -Lc '%s-%Y' "$1" 2>/dev/null)" \
        "$(printf '%s' "$1" | md5sum | cut -c1-16)"
}

# adaptada RUTA → la copia adaptada si ya esta; si no, la ORIGINAL, y la copia
# se hace en segundo plano para la proxima vez. Hacerla aqui costaria ~0,4 s
# (arrancar python con GTK) a la terminal que se esta abriendo.
adaptada() {
    local copia
    copia="$(copia_de "$1")"
    if [ -s "$copia" ]; then
        printf '%s\n' "$copia"
        return
    fi
    mkdir -p "$CACHE"
    setsid python3 "$LIB/imagen_saludo.py" "$1" "$copia" >/dev/null 2>&1 </dev/null &
    printf '%s\n' "$1"
}

case "$1" in
    --carpeta) carpeta; exit 0 ;;
    --medidas) medidas "$2" "$3"; exit 0 ;;
    --preparar)
        pares=(); n=0
        shopt -s nullglob nocaseglob
        for f in "$(carpeta)"/*.{png,jpg,jpeg,webp,gif}; do
            n=$((n + 1))
            c="$(copia_de "$f")"
            [ -s "$c" ] || pares+=("$f" "$c")
        done
        mkdir -p "$CACHE"
        [ ${#pares[@]} -eq 0 ] || python3 "$LIB/imagen_saludo.py" "${pares[@]}"
        echo "$n imagenes, $(( ${#pares[@]} / 2 )) adaptadas ahora, en $CACHE"
        exit 0 ;;
    -h|--help) sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
esac

command -v fastfetch >/dev/null 2>&1 || exit 0

imagen="$1"
[ -n "$imagen" ] || imagen="$(al_azar "$(carpeta)")"

if [ -n "$imagen" ] && [ -f "$imagen" ] && sabe_imagenes; then
    imagen="$(adaptada "$imagen")"
    read -r filas cols <<< "$(tamano_terminal)"
    read -r ancho alto izq arriba posicion <<< "$(medidas "$filas" "$cols")"
    if [ "$ancho" -gt 0 ]; then
        # Ancho y alto en CELDAS de texto; se respeta la proporcion de la imagen.
        exec fastfetch --logo-type kitty --logo "$imagen" --logo-position "$posicion" \
            --logo-width "$ancho" --logo-height "$alto" --logo-preserve-aspect-ratio true \
            --logo-padding-left "$izq" --logo-padding-top "$arriba" --logo-padding-right 4
    fi
    # Tan pequeña que no cabe ni encima: solo los datos, sin el logo de la
    # distro (que es mas grande todavia que la imagen).
    exec fastfetch --logo-type none
fi
exec fastfetch
