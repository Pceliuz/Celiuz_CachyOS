#!/usr/bin/env bash
# tests/unidad/transparencia.sh — el fondo translucido de las apps (2026-11-02):
# GTK, kitty y el tema Kvantum «Celiuz» para Qt.
#
# POR QUE EXISTE ESTA PRUEBA
# --------------------------
# Tres modos de fallo, los tres silenciosos:
#
#   1. Una copia de la paleta. El CSS de GTK y el tema de Kvantum pintan con
#      los colores del repo; un hex escrito a mano se dibuja igual, del tono de
#      otro, y quien clone el repo con su color se queda con el violeta del
#      autor (ver paleta-bloqueo.sh). Aqui se le da a gen-kvantum.py una
#      paleta VERDE imposible de confundir.
#   2. Que gen-kvantum.py deje algo del tema base: el gris del boton con el
#      raton encima o el azul de la seleccion. Fue lo que vio el usuario en
#      Dolphin; el tema base tiene esos colores escondidos dentro de GRUPOS
#      del SVG, no en la etiqueta del grupo, y por ahi se escapaban.
#   3. Que instalar.sh, que toca ficheros del USUARIO (gtk.css, kitty.conf,
#      qt6ct.conf), los ensucie: lineas repetidas en cada pasada, o pisar un
#      tema de Kvantum que eligio el.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
GEN="$REPO/hypr/scripts/gen-kvantum.py"
CSS="$REPO/gtk/celiuz-transparente.css"

titulo "1. El CSS de GTK no lleva ningun color escrito a mano"
afirmar "ni un #hex" sh -c "! grep -v '^ *\\*\\|^/\\*' '$CSS' | grep -qiE '#[0-9a-f]{3,8}\\b'"
afirmar "ni un rgb()/rgba()" sh -c "! grep -v '^ *\\*\\|^/\\*' '$CSS' | grep -qiE 'rgba?\\('"
usados="$(grep -oE '@[a-z_]+' "$CSS" | sort -u | sed 's/^@//' | grep -vx 'import')"
definidos="$(grep -oE '^@define-color [a-z_]+' "$REPO/waybar/colores.css" | awk '{print $2}')"
faltan="$(comm -23 <(printf '%s\n' "$usados") <(printf '%s\n' "$definidos" | sort -u))"
afirmar_igual "" "$faltan" "cada @color que usa existe en waybar/colores.css"
afirmar "importa la paleta por el enlace de ~/.config/waybar" \
    grep -qF '@import url("../waybar/colores.css");' "$CSS"

titulo "2. gen-kvantum.py: el tema sale de la paleta"
# Un tema base minimo con las piezas que se recolorean, cada una con su trampa.
BASE="$TMP/KvBase"; mkdir -p "$BASE"
cat > "$BASE/KvBase.kvconfig" <<'EOF'
[%General]
translucent_windows=false
reduce_window_opacity=0
reduce_menu_opacity=0

[GeneralColors]
window.color=#353535
base.color=#2d2d2d
highlight.color=#15539e
inactive.highlight.color=#15539e
text.color=white
window.text.color=white

[Hacks]
blur_translucent=false

[Tab]
text.focus.color=#3a90eb
EOF
cat > "$BASE/KvBase.svg" <<'EOF'
<svg xmlns="http://www.w3.org/2000/svg">
<rect id="menubar-normal" style="fill:url(#gris);fill-rule:evenodd"/>
<rect id="menubar-normal-bottom" style="fill:#080808"/>
<rect id="button-focused" style="fill:#373737"/>
<g id="button-focused-left"><path style="fill:#555555"/><g><path style="fill:#444444;fill-opacity:0.8"/></g></g>
<g id="btn-focused-top"><path style="fill:#565656"/></g>
<use id="tbutton-focused" href="#button-focused"/>
<rect id="tbutton-toggled" style="fill:#1e1e1e"/>
<rect id="itemview-pressed" style="fill:#15539e"/>
<rect id="lineedit-focused" style="fill:#2b2b2b"/>
<g id="le-focused-top"><path style="fill:#3d3d3d"/></g>
<g id="scrollbarslider-normal-left"><path style="fill:#5c5c5c"/></g>
<rect id="header-normal" style="fill:#2c2c2c"/>
<rect id="otra-cosa" style="fill:#121212"/>
</svg>
EOF
# Paleta verde: si sale algo violeta, es que hay un color cableado.
cat > "$TMP/colores.conf" <<'EOF'
$negro          = rgba(000000ff)
$abismo         = rgba(001100ff)
$superficie     = rgba(002200ff)
$apagado        = rgba(003300ff)
$violeta        = rgba(00aa00ff)
$amatista       = rgba(00cc00ff)
$neon           = rgba(00dd00ff)
$luz            = rgba(ccffccff)
$tenue          = rgba(668866ff)
EOF
DEST="$TMP/kv"
"$GEN" --base "$BASE" --destino "$DEST" --paleta "$TMP/colores.conf" >/dev/null 2>"$TMP/err"; codigo=$?
afirmar_igual "0" "$codigo" "genera"
afirmar "sin nada por stderr" test ! -s "$TMP/err"
KV="$DEST/Celiuz.kvconfig"; SVG="$DEST/Celiuz.svg"
afirmar "ventanas translucidas" grep -qx 'translucent_windows=true' "$KV"
afirmar "la vista de Dolphin tambien (la clave se anade en [Hacks])" grep -qx 'transparent_dolphin_view=true' "$KV"
afirmar "el fondo es \$abismo" grep -qx 'window.color=#001100' "$KV"
afirmar "la seleccion es \$violeta" grep -qx 'highlight.color=#00aa00' "$KV"
afirmar "el texto es \$luz" grep -qx 'text.color=#ccffcc' "$KV"
afirmar "la barra: \$apagado translucido" grep -qF 'id="menubar-normal" style="fill:#003300;fill-opacity:0.55' "$SVG"
afirmar "su linea de abajo: \$amatista" grep -qF 'fill:#00cc00;fill-opacity:0.55' "$SVG"
afirmar "el boton con el raton encima: \$violeta" grep -qF 'id="button-focused" style="fill:#00aa00;fill-opacity:0.35' "$SVG"
for gris in 15539e 3a90eb 373737 555555 444444 565656 080808 1e1e1e 2b2b2b 3d3d3d 5c5c5c 2c2c2c; do
    afirmar "no queda #$gris del tema base" sh -c "! grep -qi '#$gris' '$SVG' '$KV'"
done
afirmar "el campo de texto con foco: borde \$neon (la busqueda de Dolphin era gris)" \
    grep -qF '<g id="le-focused-top"><path style="fill:#00dd00;fill-opacity:0.85' "$SVG"
afirmar "la barrita del scroll: \$amatista" \
    grep -qF '<g id="scrollbarslider-normal-left"><path style="fill:#00cc00;fill-opacity:0.45' "$SVG"
afirmar "la cabecera de columnas: \$apagado" grep -qF 'id="header-normal" style="fill:#003300;fill-opacity:0.55' "$SVG"
afirmar "lo que no se recolorea se queda como estaba" grep -qF 'id="otra-cosa" style="fill:#121212"' "$SVG"
afirmar "el <use> no se toca (hereda del original)" grep -qF '<use id="tbutton-focused" href="#button-focused"/>' "$SVG"

titulo "3. gen-kvantum.py: --check y los errores"
"$GEN" --base "$BASE" --destino "$DEST" --paleta "$TMP/colores.conf" --check 2>/dev/null
afirmar_igual "0" "$?" "--check: al dia recien generado"
echo "# tocado" >> "$KV"
"$GEN" --base "$BASE" --destino "$DEST" --paleta "$TMP/colores.conf" --check 2>/dev/null
afirmar_igual "1" "$?" "--check: 1 si alguien lo toco"
"$GEN" --base "$TMP/no-existe" --destino "$DEST" --paleta "$TMP/colores.conf" 2>/dev/null
afirmar_igual "2" "$?" "sin el tema base (sin el paquete kvantum): 2"
grep -v tenue "$TMP/colores.conf" > "$TMP/corta.conf"
"$GEN" --base "$BASE" --destino "$TMP/kv2" --paleta "$TMP/corta.conf" 2>"$TMP/err"
afirmar_igual "1" "$?" "a la paleta le falta un color: 1"
afirmar "   y dice cual" grep -q tenue "$TMP/err"
afirmar "   sin dejar un tema a medias" test ! -e "$TMP/kv2"
if [ -f /usr/share/Kvantum/KvGnomeDark/KvGnomeDark.kvconfig ]; then
    "$GEN" --destino "$TMP/kv-real" >/dev/null 2>&1
    afirmar "con el KvGnomeDark de verdad: sin el azul de seleccion" \
        sh -c "! grep -qi '#15539e' '$TMP/kv-real/Celiuz.svg'"
    # Dentro de cada pieza del raton-encima y de pulsado (con sus grupos),
    # solo colores de la paleta: los fill que queden son los que pone el
    # generador, todos con su fill-opacity al lado.
    grises="$(python3 - "$TMP/kv-real/Celiuz.svg" <<'PY'
import re, sys
t = open(sys.argv[1]).read()
fams = ("button-focused", "btn-focused", "tbutton-toggled", "tbtn-toggled", "btn-toggled")
malos = set()
for m in re.finditer(r'<g\b[^>]*\bid="([^"]+)"', t):
    if not any(m.group(1).startswith(f + "-") for f in fams):
        continue
    prof, fin = 0, None
    for g in re.finditer(r"<g\b[^>]*?>|</g>", t[m.start():]):
        s = g.group(0)
        prof += -1 if s.startswith("</") else (0 if s.endswith("/>") else 1)
        if prof == 0:
            fin = m.start() + g.end(); break
    for f in re.finditer(r"fill:(#[0-9a-fA-F]{6})(;fill-opacity:)?", t[m.start():fin]):
        if not f.group(2):
            malos.add(m.group(1) + " " + f.group(1))
print(" ".join(sorted(malos)))
PY
)"
    afirmar_igual "" "$grises" "con el KvGnomeDark de verdad: los bordes del raton encima, todos recoloreados"
fi

titulo "4. instalar.sh engancha los ficheros del usuario una vez y deja lo suyo"
cfg="$XDG_CONFIG_HOME"
mkdir -p "$cfg/gtk-3.0" "$cfg/gtk-4.0" "$cfg/kitty" "$cfg/qt6ct"
echo '@import url("mio.css");' | tee "$cfg/gtk-3.0/gtk.css" > "$cfg/gtk-4.0/gtk.css"
printf 'background_opacity 0.6\n' > "$cfg/kitty/kitty.conf"
printf '[Appearance]\ncustom_palette=true\nstyle=Fusion\n' > "$cfg/qt6ct/qt6ct.conf"
binario_falso kitty 0
cargar() {
    sed -n '/^# El tema base de Kvantum/,/^}/p' "$REPO/instalar.sh" > "$TMP/transp.sh"
    sed -n '/^enlazar() {/,/^}/p' "$REPO/instalar.sh" >> "$TMP/transp.sh"
    SOLO_REVISAR=0
    titulo() { :; }; gris() { :; }; hecho() { :; }; aviso() { :; }; hacer() { "$@"; }
    . "$TMP/transp.sh"
}
( export KVANTUM_BASE="$BASE"; cargar; transparencia; transparencia ) >/dev/null 2>&1
for v in 3.0 4.0; do
    afirmar_igual "1" "$(grep -c 'celiuz-transparente.css' "$cfg/gtk-$v/gtk.css")" "GTK $v: dos pasadas dejan UN @import"
    afirmar_igual '@import url("mio.css");' "$(head -n1 "$cfg/gtk-$v/gtk.css")" "   y lo suyo sigue delante"
done
afirmar_igual "$(readlink -f "$CSS")" "$(readlink -f "$cfg/gtk-3.0/celiuz-transparente.css")" "el CSS, enlazado al repo"
afirmar_igual "1" "$(grep -cx 'include celiuz-transparencia.conf' "$cfg/kitty/kitty.conf")" "kitty: UNA linea"
afirmar_igual "include celiuz-transparencia.conf" "$(tail -n1 "$cfg/kitty/kitty.conf")" "   al final (gana a su background_opacity)"
afirmar "Kvantum: el tema generado" test -s "$cfg/Kvantum/Celiuz/Celiuz.svg"
afirmar "Kvantum: elegido Celiuz" grep -qx 'theme=Celiuz' "$cfg/Kvantum/kvantum.kvconfig"
afirmar "qt6ct: estilo kvantum" grep -qx 'style=kvantum' "$cfg/qt6ct/qt6ct.conf"
afirmar "   sin la paleta propia de qt6ct, que pisaria la del tema" grep -qx 'custom_palette=false' "$cfg/qt6ct/qt6ct.conf"
afirmar "   y el de antes guardado" grep -qx 'style=Fusion' "$cfg/qt6ct/qt6ct.conf.antes-celiuz"

printf '[General]\ntheme=KvArc\n' > "$cfg/Kvantum/kvantum.kvconfig"
( export KVANTUM_BASE="$BASE"; cargar; transparencia ) >/dev/null 2>&1
afirmar "un tema de Kvantum elegido por el usuario no se pisa" grep -qx 'theme=KvArc' "$cfg/Kvantum/kvantum.kvconfig"

afirmar_intacta_la_casa_real
resumen
