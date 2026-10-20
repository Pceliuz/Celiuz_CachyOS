#!/usr/bin/env bash
# hypr/scripts/saludo.sh — el saludo al abrir una terminal: fastfetch con una
# imagen al azar al lado. instalar.sh lo enlaza como ~/.local/bin/celiuz-saludo
# y lo pone de fish_greeting.
#
# LAS IMAGENES
# ------------
# Las pones tu en la carpeta «terminal» de tus imágenes (xdg-user-dir PICTURES:
# ~/Imágenes/terminal en español, ~/Pictures/terminal en inglés). PNG, JPG,
# WebP o GIF; las de fondo transparente quedan mejor. El repo no trae ninguna:
# es publico y las de anime no son nuestras para repartir.
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

carpeta() {
    local fotos
    fotos="$(xdg-user-dir PICTURES 2>/dev/null)"
    # xdg-user-dir devuelve $HOME si no hay carpeta de imagenes definida.
    if [ -z "$fotos" ] || [ "$fotos" = "$HOME" ]; then
        fotos="$HOME/Pictures"
    fi
    printf '%s/terminal\n' "$fotos"
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
    # Ancho y alto en CELDAS de texto; se respeta la proporcion de la imagen.
    exec fastfetch --logo-type kitty --logo "$imagen" \
        --logo-width 22 --logo-height 11 --logo-preserve-aspect-ratio true
fi
exec fastfetch
