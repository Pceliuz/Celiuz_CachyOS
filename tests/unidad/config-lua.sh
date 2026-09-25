#!/usr/bin/env bash
# tests/unidad/config-lua.sh — la config de Hyprland en Lua, sin Hyprland.
#
# QUE VIGILA, Y POR QUE
# ---------------------
# La config es Lua desde el 2026-09-25 (hypr/hyprland.lua + hypr/lua/). Se
# verifico entonces contra la de hyprlang en dos anidados, opcion por opcion;
# esto es lo que queda de guardia para despues, y corre en cualquier sitio
# (tests/lib/hl_falso.lua hace de Hyprland con el `lua` del sistema):
#
#   1. Carga entera, como sobremesa y como portatil, sin un error.
#   2. Portatil y sobremesa cargan lo que toca: 57 atajos y 62, el teclado.
#   3. Ningun atajo repetido (el segundo pisaria al primero sin avisar).
#   4. Todo script al que llama un atajo o el arranque EXISTE y es ejecutable.
#      Un atajo a un script que no esta no falla: no hace nada.
#   5. personal.lua se carga EL ULTIMO (puede pisar cualquier cosa).
#   6. Sin local.lua (quien clona y aun no instalo) arranca igual.
#   7. La paleta sale de conf/colores.conf, no de una copia.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

if ! command -v lua >/dev/null 2>&1; then
    _gris "  (no hay \`lua\` en el sistema: sudo pacman -S lua. Me salto esta prueba)"
    resumen; exit 0
fi

COPIA="$(copiar_repo)"
mkdir -p "$HOME/.config"
ln -sfn "$COPIA/hypr" "$HOME/.config/hypr"
rm -f "$COPIA/hypr/lua/local.lua" "$COPIA/hypr/lua/personal.lua"

cargar() {   # cargar <salida.json> — ejecuta la config con el hl de mentira
    lua "$REPO/tests/lib/hl_falso.lua" "$1" 2>"$1.err"
}
consulta() {   # consulta <json> <expresion python sobre R>
    python3 -c 'import json,sys; R=json.load(open(sys.argv[1])); print(eval(sys.argv[2]))' "$1" "$2"
}

# --- Sobremesa y portatil ------------------------------------------------------

cat > "$COPIA/hypr/lua/local.lua" <<'EOF'
return { terminal = "foot", portatil = false, motivo = "prueba" }
EOF
cargar "$TMP/pc.json"; codigo_pc=$?
cat > "$COPIA/hypr/lua/local.lua" <<'EOF'
return { terminal = "foot", portatil = true, kb_layout = "latam,us", kb_variant = ",altgr-intl", motivo = "prueba" }
EOF
cargar "$TMP/laptop.json"; codigo_laptop=$?

titulo "1. Carga entera, sin errores"
afirmar_igual "0" "$codigo_pc" "como sobremesa"
afirmar "   sin nada por stderr" test ! -s "$TMP/pc.json.err"
afirmar_igual "0" "$codigo_laptop" "como portatil"
afirmar "   sin nada por stderr" test ! -s "$TMP/laptop.json.err"
[ -s "$TMP/pc.json.err" ] && sed 's/^/      /' "$TMP/pc.json.err"

titulo "2. Cada equipo carga lo suyo"
afirmar_igual "57" "$(consulta "$TMP/pc.json" 'len(R["binds"])')" "sobremesa: 57 atajos"
afirmar_igual "62" "$(consulta "$TMP/laptop.json" 'len(R["binds"])')" "portatil: 62 (brillo, avion, tapa x2... )"
afirmar_igual "lv3:switch" "$(consulta "$TMP/pc.json" 'R["opciones"]["input.kb_options"]')" \
    "sobremesa: el Ctrl derecho hace de AltGr (teclado del autor)"
afirmar_igual "" "$(consulta "$TMP/laptop.json" 'R["opciones"]["input.kb_options"]')" \
    "portatil: kb_options vacio, el teclado interno ya tiene AltGr"
afirmar_igual "latam,us" "$(consulta "$TMP/laptop.json" 'R["opciones"]["input.kb_layout"]')" \
    "portatil: la distribucion de local.lua"
afirmar_igual "us,latam" "$(consulta "$TMP/pc.json" 'R["opciones"]["input.kb_layout"]')" \
    "sobremesa: la de fabrica"
afirmar_igual "True" "$(consulta "$TMP/laptop.json" 'R["opciones"]["input.touchpad.tap_to_click"]')" \
    "portatil: tocar para hacer clic"
afirmar_igual "True" "$(consulta "$TMP/pc.json" 'any("lanzar.sh foot" in b["accion"]["args"][0] for b in R["binds"] if b["accion"]["dsp"]=="exec_cmd")')" \
    "SUPER+RETURN abre la terminal de local.lua"

titulo "3. Ningun atajo repetido"
for f in pc laptop; do
    rep="$(consulta "$TMP/$f.json" '", ".join(sorted({b["teclas"] for b in R["binds"] if [x["teclas"] for x in R["binds"]].count(b["teclas"]) > 1}))')"
    afirmar_igual "" "$rep" "$f: cada combinacion una sola vez"
done

titulo "4. Todo script que se llama existe y es ejecutable"
consulta "$TMP/laptop.json" '"\n".join([b["accion"]["args"][0] for b in R["binds"] if b["accion"]["dsp"]=="exec_cmd"] + R["exec"])' \
    | grep -oE '\$HOME/\.config/hypr/scripts/[A-Za-z0-9_./-]+' | sort -u > "$TMP/scripts"
afirmar "hay scripts que comprobar" test -s "$TMP/scripts"
while read -r s; do
    ruta="${s/\$HOME/$HOME}"
    afirmar "${s#\$HOME/.config/hypr/}" test -x "$ruta"
done < "$TMP/scripts"
afirmar_igual "1" "$(consulta "$TMP/laptop.json" 'R["arranques"]')" "un solo arranque (hyprland.start)"
afirmar_igual "9" "$(consulta "$TMP/laptop.json" 'len(R["exec"])')" "que lanza los nueve de autostart"

titulo "5. personal.lua va el ultimo y puede pisarlo todo"
cat > "$COPIA/hypr/lua/personal.lua" <<'EOF'
hl.config({ general = { gaps_in = 9 }, input = { kb_options = "caps:escape" } })
EOF
cargar "$TMP/personal.json"
afirmar_igual "9" "$(consulta "$TMP/personal.json" 'R["opciones"]["general.gaps_in"]')" "pisa gaps_in de general.lua"
afirmar_igual "caps:escape" "$(consulta "$TMP/personal.json" 'R["opciones"]["input.kb_options"]')" \
    "y pisa hasta lo del portatil, que se carga antes"
rm -f "$COPIA/hypr/lua/personal.lua"

titulo "6. Sin local.lua (aun sin instalar) arranca igual"
rm -f "$COPIA/hypr/lua/local.lua"
cargar "$TMP/sin-local.json"; codigo=$?
afirmar_igual "0" "$codigo" "carga sin error"
afirmar_igual "57" "$(consulta "$TMP/sin-local.json" 'len(R["binds"])')" "como sobremesa"
afirmar_igual "True" "$(consulta "$TMP/sin-local.json" 'any(b["teclas"]=="SUPER + RETURN" and "lanzar.sh " in b["accion"]["args"][0] and not b["accion"]["args"][0].rstrip().endswith("lanzar.sh") for b in R["binds"])')" \
    "y SUPER+RETURN tiene alguna terminal (la pregunta a lib/apps.py)"

titulo "7. La paleta sale de conf/colores.conf"
sed -i 's/^\$amatista *= *rgba([0-9a-f]*)/$amatista = rgba(00ff00ff)/' "$COPIA/hypr/conf/colores.conf"
cargar "$TMP/verde.json"
afirmar_igual "True" "$(consulta "$TMP/verde.json" '"rgba(00ff00ff)" in R["opciones"]["general.col.active_border"]["colors"]')" \
    "un color cambiado en colores.conf llega al borde (no hay copia en Lua)"

afirmar_intacta_la_casa_real
resumen
