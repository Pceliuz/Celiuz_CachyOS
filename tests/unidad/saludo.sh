#!/usr/bin/env bash
# tests/unidad/saludo.sh — el saludo de la terminal (hypr/scripts/saludo.sh) y
# su config de fastfetch.
#
# QUE VIGILA
# ----------
# - Que en kitty pinta una imagen de la carpeta, al azar entre las que haya.
# - Que sin imagenes, o en una terminal que no sabe dibujarlas, sale el
#   fastfetch normal: nunca un saludo roto ni un error.
# - Que la carpeta es fastfetch/imagenes del repo donde este el script, se
#   llame por donde se llame (tambien por el enlace de ~/.local/bin).
# - Que fastfetch/config.jsonc es JSON valido para el fastfetch instalado.
# - Que instalar.sh engancha fish UNA vez y respeta un fish_greeting propio.
#
# fastfetch es de mentira, y se trabaja en una COPIA del repo con la carpeta
# de imagenes vaciada (salvo en la comprobacion de la config).

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
COPIA="$(copiar_repo)"
SCRIPT="$COPIA/hypr/scripts/saludo.sh"
IMAGENES="$COPIA/fastfetch/imagenes"
rm -rf "$IMAGENES"; mkdir -p "$IMAGENES"
binario_falso fastfetch 0

ultima() { tail -n1 "$REGISTRO/fastfetch.log" 2>/dev/null; }

titulo "1. La carpeta"
afirmar_igual "$IMAGENES" "$("$SCRIPT" --carpeta)" "la del repo donde esta el script"
mkdir -p "$HOME/.local/bin"; ln -sfn "$SCRIPT" "$HOME/.local/bin/celiuz-saludo"
afirmar_igual "$IMAGENES" "$("$HOME/.local/bin/celiuz-saludo" --carpeta)" \
    "   tambien llamado por el enlace de ~/.local/bin"
afirmar "el repo de verdad trae la carpeta, con imagenes" \
    test -n "$(ls "$REPO/fastfetch/imagenes" 2>/dev/null | head -n1)"

titulo "2. Sin imagenes: el fastfetch de siempre"
salida="$(KITTY_WINDOW_ID=1 "$SCRIPT" 2>&1)"; codigo=$?
afirmar_igual "0|" "$codigo|$salida" "sale bien y sin escribir nada"
afirmar_igual "" "$(ultima)" "fastfetch sin --logo"

titulo "3. Con imagenes, en kitty: una de ellas"
for n in uno dos tres; do : > "$IMAGENES/$n.png"; done
: > "$IMAGENES/cuatro.JPG"
: > "$IMAGENES/notas.txt"
: > "$REGISTRO/fastfetch.log"
for _ in $(seq 40); do KITTY_WINDOW_ID=1 TERM=xterm-kitty "$SCRIPT"; done
vistas="$(grep -o -- '--logo [^ ]*' "$REGISTRO/fastfetch.log" | sort -u | sed 's|.*/||' | tr '\n' ' ')"
afirmar_contiene "$REGISTRO/fastfetch.log" "--logo-type kitty" "usa el protocolo de kitty"
afirmar_igual "cuatro.JPG dos.png tres.png uno.png " "$vistas" \
    "en 40 aperturas salen las cuatro imagenes (y el .txt nunca)"
# Sin repetir: cada vuelta de 4 saca las 4, y entre vueltas no se repite seguida.
orden="$(grep -o -- '--logo [^ ]*' "$REGISTRO/fastfetch.log" | sed 's|.*/||')"
malas=0; seguidas=0; i=0; previa=""
while read -r v; do
    [ "$v" = "$previa" ] && seguidas=$((seguidas + 1)); previa="$v"
done <<< "$orden"
# La primera vuelta saca las 4; despues, cualquier tramo de 3 seguidas (las 4
# menos la ultima de la vuelta anterior) son 3 distintas.
afirmar_igual "4" "$(head -n4 <<< "$orden" | sort -u | wc -l)" "la primera vuelta saca las 4"
for k in $(seq 1 38); do
    n="$(sed -n "${k},$((k + 2))p" <<< "$orden" | sort -u | wc -l)"
    [ "$n" -eq 3 ] || malas=$((malas + 1))
done
afirmar_igual "0" "$malas" "en 40 aperturas, ninguna se repite antes de 3 terminales"
afirmar_igual "0" "$seguidas" "nunca sale la misma dos veces seguidas (ni al cambiar de vuelta)"
rm "$IMAGENES/tres.png"
: > "$IMAGENES/cinco.png"
: > "$REGISTRO/fastfetch.log"
for _ in $(seq 4); do KITTY_WINDOW_ID=1 "$SCRIPT"; done
salieron="$(grep -o -- '--logo [^ ]*' "$REGISTRO/fastfetch.log" | sed 's|.*/||')"
afirmar_igual "si no" "$(grep -qx cinco.png <<< "$salieron" && echo si || echo no) $(grep -qx tres.png <<< "$salieron" && echo si || echo no)" \
    "una nueva entra en la vuelta y una borrada deja de salir"
rm "$IMAGENES/cinco.png"; : > "$IMAGENES/tres.png"

titulo "4. Una terminal que no dibuja imagenes"
: > "$REGISTRO/fastfetch.log"
env -u KITTY_WINDOW_ID TERM=xterm-256color TERM_PROGRAM= "$SCRIPT"
afirmar_igual "" "$(ultima)" "fastfetch sin imagen"

titulo "5. La config es valida"
if [ -x /usr/bin/fastfetch ]; then
    err="$(/usr/bin/fastfetch --config "$REPO/fastfetch/config.jsonc" --logo none 2>&1 >/dev/null)"
    afirmar_igual "" "$err" "fastfetch la lee sin quejarse"
    afirmar "es JSON con comentarios valido" python3 -c "
import json, re, sys
t = open('$REPO/fastfetch/config.jsonc').read()
t = re.sub(r'^\s*//.*$', '', t, flags=re.M)
json.loads(t)"
else
    _gris "  (sin fastfetch en el equipo: se salta)"
fi

titulo "6. instalar.sh engancha fish una vez y respeta lo tuyo"
conf="$XDG_CONFIG_HOME/fish/config.fish"
mkdir -p "$(dirname "$conf")"
printf 'source /usr/share/cachyos-fish-config/cachyos-config.fish\n#function fish_greeting\n#end\n' > "$conf"
# Solo la funcion, sin correr el instalador entero.
cargar() {
    sed -n '/^SALUDO_MARCA=/,/^}/p' "$REPO/instalar.sh" > "$TMP/saludo_fish.sh"
    SOLO_REVISAR=0; REPO="$REPO"
    titulo() { :; }; gris() { :; }; hecho() { :; }; aviso() { :; }; hacer() { "$@"; }
    . "$TMP/saludo_fish.sh"
}
binario_falso fish 0
( cargar; saludo_fish; saludo_fish )
afirmar_igual "1" "$(grep -c '^function fish_greeting; celiuz-saludo; end$' "$conf")" \
    "dos pasadas dejan UNA linea"
afirmar_igual "source /usr/share/cachyos-fish-config/cachyos-config.fish" "$(head -n1 "$conf")" \
    "lo que habia sigue delante"
printf 'function fish_greeting\n    echo hola\nend\n' > "$conf"
( cargar; saludo_fish )
afirmar_igual "0" "$(grep -c celiuz-saludo "$conf")" "un fish_greeting propio no se toca"

titulo "7. La adaptacion de la imagen (lib/imagen_saludo.py)"
# Un sticker: 300x300 transparente con un cuadrado opaco en (100..199, 50..149).
# Una foto: 300x200 opaca entera.
python3 - "$TMP" <<'PY2'
import sys, gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf
d = sys.argv[1]
pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 300, 300)
pb.fill(0x00000000)
pb.new_subpixbuf(100, 50, 100, 100).fill(0xff3366ff)
pb.savev(d + "/sticker.png", "png", [], [])
foto = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 300, 200)
foto.fill(0x3366ffff)
foto.savev(d + "/foto.jpg", "jpeg", [], [])
grande = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 2000, 1000)
grande.fill(0x808080ff)
grande.savev(d + "/grande.png", "png", [], [])
PY2
A="$REPO/hypr/scripts/lib/imagen_saludo.py"
salida="$(python3 "$A" "$TMP/sticker.png" "$TMP/s.png" "$TMP/foto.jpg" "$TMP/f.png" \
          "$TMP/grande.png" "$TMP/g.png" 2>&1)"; codigo=$?
afirmar_igual "0|" "$codigo|$salida" "adapta tres en una llamada, sin quejarse"
medir() {
    python3 - "$1" <<'PY2'
import sys, gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf
pb = GdkPixbuf.Pixbuf.new_from_file(sys.argv[1])
px = pb.get_pixels(); n = pb.get_n_channels(); st = pb.get_rowstride()
alfa = lambda x, y: px[y * st + x * n + 3] if n == 4 else 255
w, h = pb.get_width(), pb.get_height()
print("%dx%d esquina=%d centro=%d" % (w, h, alfa(0, 0), alfa(w // 2, h // 2)))
PY2
}
s="$(medir "$TMP/s.png")"
case "$s" in
    10[0-9]x10[0-9]*|11[0-9]x11[0-9]*) ok "el sticker se recorta a su dibujo ($s)" ;;
    *) fallo "el sticker se recorta a su dibujo" "salio $s, esperaba ~108x108" ;;
esac
afirmar_igual "300x200 esquina=0 centro=255" "$(medir "$TMP/f.png")" \
    "la foto conserva su tamaño y redondea las esquinas"
afirmar_igual "400x200" "$(medir "$TMP/g.png" | cut -d' ' -f1)" "la grande baja a 400 de lado"
: > "$TMP/rota.png"
python3 "$A" "$TMP/rota.png" "$TMP/r.png" 2>/dev/null; codigo=$?
afirmar_igual "1 no" "$codigo $( [ -e "$TMP/r.png" ] && echo si || echo no)" \
    "una imagen rota sale con 1 y no deja copia"

titulo "8. saludo.sh usa la copia adaptada si ya esta"
cp "$TMP/sticker.png" "$IMAGENES/"
rm -f "$IMAGENES/"{uno,dos,tres}.png "$IMAGENES/cuatro.JPG"
salida="$("$SCRIPT" --preparar)"
copia="$(ls "$XDG_CACHE_HOME/celiuz/saludo/"*.png 2>/dev/null | head -n1)"
afirmar "--preparar deja la copia en la cache" test -s "$copia"
: > "$REGISTRO/fastfetch.log"
KITTY_WINDOW_ID=1 "$SCRIPT"
afirmar_contiene "$REGISTRO/fastfetch.log" "--logo $copia" "la terminal dibuja la copia, no el original"

afirmar_intacta_la_casa_real
resumen
