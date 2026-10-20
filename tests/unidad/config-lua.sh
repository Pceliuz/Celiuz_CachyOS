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
#   2. Portatil y sobremesa cargan lo que toca: 61 atajos y 66, el teclado.
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
afirmar_igual "61" "$(consulta "$TMP/pc.json" 'len(R["binds"])')" "sobremesa: 61 atajos"
afirmar_igual "66" "$(consulta "$TMP/laptop.json" 'len(R["binds"])')" "portatil: 66 (brillo, avion, tapa x2... )"
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
afirmar_igual "10" "$(consulta "$TMP/laptop.json" 'len(R["exec"])')" "que lanza los diez de autostart"

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
afirmar_igual "61" "$(consulta "$TMP/sin-local.json" 'len(R["binds"])')" "como sobremesa"
afirmar_igual "True" "$(consulta "$TMP/sin-local.json" 'any(b["teclas"]=="SUPER + RETURN" and "lanzar.sh " in b["accion"]["args"][0] and not b["accion"]["args"][0].rstrip().endswith("lanzar.sh") for b in R["binds"])')" \
    "y SUPER+RETURN tiene alguna terminal (la pregunta a lib/apps.py)"

titulo "7. La paleta sale de conf/colores.conf"
sed -i 's/^\$amatista *= *rgba([0-9a-f]*)/$amatista = rgba(00ff00ff)/' "$COPIA/hypr/conf/colores.conf"
cargar "$TMP/verde.json"
afirmar_igual "True" "$(consulta "$TMP/verde.json" '"rgba(00ff00ff)" in R["opciones"]["general.col.active_border"]["colors"]')" \
    "un color cambiado en colores.conf llega al borde (no hay copia en Lua)"

titulo "8. Cada pantalla encendida, a su refresco mas alto (lua/monitors.lua)"
# Una recarga reaplica las reglas: con `preferred` a secas la PC bajaba a 60 Hz
# y monitores.py la subia despues (2026-10-20). La regla con nombre lo evita, y
# el numero sale de los modos de cada pantalla, no de la del autor.
sed -i 's/^\$amatista *= *rgba(00ff00ff)/$amatista = rgba(b16cffff)/' "$COPIA/hypr/conf/colores.conf"
cat > "$TMP/pantallas.lua" <<'EOF'
local function m(w, h, r, p) return { width = w, height = h, refresh_rate = r, preferred = p } end
return {
    -- La PC: el EDID prefiere 60 y admite 100.
    { name = "HDMI-A-1", width = 1920, height = 1080,
      available_modes = { m(1920, 1080, 60.0, true), m(1920, 1080, 100.0), m(1280, 720, 60.0) } },
    -- El televisor: su 800x600@60.32 es la trampa de `highrr`.
    { name = "HDMI-A-2", width = 1920, height = 1080,
      available_modes = { m(1920, 1080, 60.0, true), m(800, 600, 60.32) } },
    -- Un 1440p de 144 que anuncia 143.91, y un modo de 1080p a 240 que no toca.
    { name = "DP-1", width = 2560, height = 1440,
      available_modes = { m(2560, 1440, 59.95, true), m(2560, 1440, 143.91), m(1920, 1080, 240.0) } },
    -- Una pantalla que no anuncia nada: sin regla propia, se queda la generica.
    { name = "DP-2", width = 1024, height = 768, available_modes = {} },
}
EOF
cat > "$COPIA/hypr/lua/personal.lua" <<'EOF'
hl.monitor({ output = "HDMI-A-2", mode = "preferred", position = "auto-right", scale = 1.5 })
EOF
HL_PANTALLAS="$TMP/pantallas.lua" cargar "$TMP/pantallas.json"; codigo=$?
rm -f "$COPIA/hypr/lua/personal.lua"
afirmar_igual "0" "$codigo" "carga sin error con pantallas"
modo_de() { consulta "$TMP/pantallas.json" "[m.get('mode') for m in R['monitores'] if m.get('output')=='$1'][$2]"; }
afirmar_igual "preferred" "$(modo_de '' 0)" "la regla generica sigue (para lo que se enchufe despues)"
afirmar_igual "1920x1080@100" "$(modo_de HDMI-A-1 0)" "la PC: sus 100, aunque el EDID prefiera 60"
afirmar_igual "1920x1080@60" "$(modo_de HDMI-A-2 0)" "el televisor: 1080p, no su 800x600 de mas refresco"
afirmar_igual "2560x1440@143.91" "$(modo_de DP-1 0)" "un 144: a su resolucion preferida, no los 240 de 1080p"
afirmar_igual "0" "$(consulta "$TMP/pantallas.json" "len([m for m in R['monitores'] if m.get('output')=='DP-2'])")" \
    "sin modos que leer no se inventa ninguna regla"
afirmar_igual "preferred" "$(modo_de HDMI-A-2 -1)" "y lo de personal.lua llega DESPUES, asi que gana"
afirmar_igual "1" "$(consulta "$TMP/pc.json" "len(R['monitores'])")" \
    "sin pantallas (la primera carga de la sesion) solo queda la generica"

afirmar_intacta_la_casa_real
resumen
