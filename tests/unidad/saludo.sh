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

titulo "5b. La imagen sigue al tamaño de la terminal (2026-10-21)"
medidas() { bash "$SCRIPT" --medidas "$1" "$2"; }
afirmar_igual "32 16 26 1 left" "$(medidas 36 130)" "la laptop a pantalla completa: grande, al lado y centrada"
afirmar_igual "24 12 5 3 left" "$(medidas 24 80)" "una de 80x24: mas chica, centrada en vertical contra los datos"
afirmar_igual "32 16 76 1 left" "$(medidas 60 230)" "una enorme: hasta el alto del cuadro, no mas"
afirmar_igual "left" "$(medidas 38 82 | cut -d' ' -f5)" "si al lado no cabe entera, mas chica pero al lado"
afirmar_igual "top" "$(medidas 40 60 | cut -d' ' -f5)" "estrecha pero alta: la imagen ENCIMA, no pisando los datos"
# 2026-10-22: con los datos partidos en dos lineas el saludo crecia el doble y
# se llevaba la imagen por arriba. Si no caben imagen, datos y prompt: la
# imagen sola, y que quepa entera con el prompt debajo.
afirmar_igual "28 14 4 1 solo" "$(medidas 18 36)" "tres terminales en fila en la laptop: la imagen sola, centrada"
afirmar_igual "solo" "$(medidas 18 60 | cut -d' ' -f5)" "estrecha y baja: la imagen sola, no encima de unos datos que no caben"
afirmar_igual "solo" "$(medidas 12 100 | cut -d' ' -f5)" "ancha pero muy baja: tampoco al lado"
afirmar_igual "left" "$(medidas 18 74 | cut -d' ' -f5)" "media pantalla de la laptop (18 filas): al lado, como antes"
# Dos terminales lado a lado en la laptop: 34x67 (medido). Con el cuadro de
# datos reservando 46 columnas la imagen iba encima; el usuario la queria al
# lado, como con una sola (2026-10-22).
afirmar_igual "21 10 1 4 left" "$(medidas 34 67)" "dos terminales lado a lado en la laptop: la imagen al lado"
afirmar_igual "solo" "$(medidas 15 67 | cut -d' ' -f5)" "cuatro (15 filas): la imagen sola, como se aprobo"
for t in "18 36" "12 100" "25 40" "18 60" "30 50"; do
    read -r ancho alto izq arriba pos <<< "$(medidas $t)"
    read -r f c <<< "$t"
    afirmar "$t: la imagen sola cabe entera, a lo ancho y con el prompt debajo" \
        test "$pos" != solo -o \( $(( arriba + alto + 2 )) -le "$f" -a $(( izq + ancho )) -le "$c" \)
done
afirmar_igual "24 12 5 3 left" "$(medidas x '')" "algo que no es un numero: como 80x24, sin reventar"
: > "$REGISTRO/fastfetch.log"
KITTY_WINDOW_ID=1 LINES=36 COLUMNS=130 "$SCRIPT" > /dev/null
afirmar "se lo pasa a fastfetch (ancho, alto, sitio)" grep -q -- \
    "--logo-position left --logo-width 32 --logo-height 16 .*--logo-padding-left 26 --logo-padding-top 1" \
    "$REGISTRO/fastfetch.log"
: > "$REGISTRO/fastfetch.log"
KITTY_WINDOW_ID=1 LINES=6 COLUMNS=60 "$SCRIPT" > /dev/null
afirmar "tan pequeña que no cabe la imagen: solo los datos, sin el logo de la distro" \
    grep -qx -- "--logo-type none" "$REGISTRO/fastfetch.log"
: > "$REGISTRO/fastfetch.log"
KITTY_WINDOW_ID=1 LINES=5 COLUMNS=30 "$SCRIPT" > /dev/null
afirmar_igual "" "$(ultima)" "y si tampoco caben los datos a lo ancho: nada"
: > "$REGISTRO/fastfetch.log"
KITTY_WINDOW_ID=1 LINES=18 COLUMNS=36 "$SCRIPT" > /dev/null
afirmar "la imagen sola: fastfetch sin datos, con tantas lineas vacias como alto" \
    grep -q -- "--logo-position left .*-s break\(:break\)\{14\}$" "$REGISTRO/fastfetch.log"

titulo "5c2. El cuadro de datos de verdad cabe en lo que se le reserva"
# ANCHO_DATOS de saludo.sh es una reserva escrita a mano; si un dato crece (un
# disco en TiB, una CPU de nombre largo) y no cabe, las lineas se parten y la
# imagen se descoloca. Se mide el fastfetch de ESTE equipo con la config del
# repo: el icono cuenta dos celdas (kitty/celiuz-iconos.py).
if command -v fastfetch >/dev/null 2>&1 && [ -x /usr/bin/fastfetch ]; then
    reserva="$(sed -n 's/^ANCHO_DATOS=//p' "$REPO/hypr/scripts/saludo.sh")"
    ancho="$(/usr/bin/fastfetch -c "$REPO/fastfetch/config.jsonc" --pipe -l none 2>/dev/null \
        | awk '{ n = length($0) + 1; if (n > m) m = n } END { print m + 0 }')"
    afirmar "el dato mas ancho de este equipo ($ancho columnas) cabe en la reserva ($reserva)" \
        test "$ancho" -gt 0 -a "$ancho" -le "$reserva"
else
    _gris "  (sin fastfetch en el equipo: se salta)"
fi

titulo "5d. Mide la terminal DE VERDAD, no 80x24 (2026-10-22)"
# La medida iba dentro de un $(...), donde la salida es una tuberia: `[ -t 1 ]`
# daba siempre falso y todo salia como en 80x24. Se pinta en un pty de verdad
# (script) con un tamaño puesto, y SIN LINES ni COLUMNS que lo salven.
if command -v script >/dev/null 2>&1; then
    : > "$REGISTRO/fastfetch.log"
    env -u LINES -u COLUMNS KITTY_WINDOW_ID=1 script -qec \
        "stty rows 18 cols 36; '$SCRIPT'" /dev/null > /dev/null 2>&1
    afirmar "en un pty de 18x36 sale la imagen sola, no el 24x80 de reserva" \
        grep -q -- "--logo-width 28 --logo-height 14" "$REGISTRO/fastfetch.log"
else
    _gris "  (sin script de util-linux: se salta)"
fi

titulo "5e. En fish se redibuja al cambiar de tamaño, hasta el primer comando"
# celiuz-saludo --fish deja en la shell la imagen elegida y un manejador; aqui
# se ejecuta en un fish de verdad con un celiuz-saludo de mentira, y se mira
# a quien llama y con que.
if command -v fish >/dev/null 2>&1; then
    rm -f "$IMAGENES"/*
    python3 -c "open('$IMAGENES/it\'s ñ (1).png','wb').write(b'x')"
    KITTY_WINDOW_ID=1 "$SCRIPT" --fish > "$TMP/saludo.fish"
    binario_falso celiuz-saludo 0
    binario_falso clear 0
    salida="$(fish --no-config -c "
        set -g COLUMNS 80; set -g LINES 24
        source '$TMP/saludo.fish'
        set COLUMNS 40          # la terminal se encoge: redibuja
        set LINES 24            # mismo tamaño que ya pinto: nada
        emit fish_preexec       # el primer comando
        set COLUMNS 30          # desde aqui la pantalla es del usuario
        functions -q __celiuz_saludo_ajustar; and echo sigue-el-manejador
    " 2>&1 >/dev/null)"
    # (commandline se queja fuera de una shell interactiva: es lo esperado aqui)
    afirmar_igual "" "$(grep -v 'commandline' <<< "$salida")" "fish lo carga y lo corre sin un error"
    imagen="$IMAGENES/it's ñ (1).png"
    afirmar_igual "$imagen|$imagen" "$(paste -sd'|' "$REGISTRO/celiuz-saludo.log")" \
        "dos dibujos, el de abrir y uno al encogerse, con la MISMA imagen (aunque lleve comilla y tilde)"
    afirmar_igual "1" "$(veces_llamado clear)" "borra la pantalla solo al redibujar"
    rm -f "$IMAGENES"/*
else
    _gris "  (sin fish en el equipo: se salta)"
fi

titulo "5c. Los colores salen de la paleta, y los iconos siguen ahi"
afirmar "config.jsonc esta al dia con la plantilla y la paleta" \
    "$REPO/hypr/scripts/gen-colores.py" --check
afirmar "   sin un solo @nombre@ sin cambiar" sh -c "! grep -q '@[a-z_]*@' '$REPO/fastfetch/config.jsonc'"
afirmar "cada color del cuadro es uno de colores.conf" python3 - "$REPO" <<'FINPY'
import re, sys
raiz = sys.argv[1]
paleta = {h[:6].lower() for h in re.findall(r"rgba\(([0-9a-fA-F]{8})\)", open(f"{raiz}/hypr/conf/colores.conf").read())}
usados = {"%02x%02x%02x" % tuple(map(int, m)) for m in
          re.findall(r"38;2;(\d+);(\d+);(\d+)", open(f"{raiz}/fastfetch/config.jsonc").read())}
assert usados and usados <= paleta, usados - paleta
FINPY
# Los iconos son de Nerd Font (zona de uso privado de Unicode): no se ven en
# casi ningun editor, y se pierden sin avisar al copiar o reescribir el fichero.
afirmar_igual "14" "$(python3 -c "
import re; t = open('$REPO/fastfetch/plantilla.jsonc', encoding='utf-8').read()
print(sum(1 for k in re.findall(r'\"key\": \"([^\"]*)\"', t) if len(k) == 1 and 0xE000 <= ord(k) <= 0xF8FF))")" \
    "los 14 iconos de la plantilla siguen ahi"

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
afirmar_igual "1" "$(grep -c '^function fish_greeting; celiuz-saludo --fish | source; end$' "$conf")" \
    "dos pasadas dejan UNA linea"
afirmar_igual "source /usr/share/cachyos-fish-config/cachyos-config.fish" "$(head -n1 "$conf")" \
    "lo que habia sigue delante"
printf 'source x\n# celiuz-saludo (lo puso instalar.sh; borra estas dos lineas para quitarlo)\nfunction fish_greeting; celiuz-saludo; end\nset -g y 1\n' > "$conf"
( cargar; saludo_fish )
afirmar_igual "source x|# celiuz-saludo (lo puso instalar.sh; borra estas dos lineas para quitarlo)|function fish_greeting; celiuz-saludo --fish | source; end|set -g y 1" \
    "$(paste -sd'|' "$conf")" "la linea vieja se pone al dia en su sitio, sin tocar lo demas"
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
