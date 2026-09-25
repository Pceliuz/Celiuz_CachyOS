#!/usr/bin/env bash
# tests/unidad/migrar-personal.sh — que lo tuyo sobreviva al paso a Lua.
#
# QUE VIGILA, Y POR QUE
# ---------------------
# personal.conf no se versiona, asi que al pasar la config a Lua el repo no
# puede traerte la version nueva: la traduce instalar.sh con
# lib/migrar_personal.py. Si se equivoca, lo pierdes EN SILENCIO al volver a
# entrar (en la laptop del autor: la escala 1.5 del televisor). Y si traduce a
# medias algo que no entiende, peor: parece que funciona.
#
#   1. Lo que se sabe traducir sale bien, y el Lua resultante es valido.
#   2. Lo que no, sale COMENTADO con su marca y con aviso — nunca inventado.
#   3. Las variables de hyprlang ($terminal, $mainMod) no pasan: en Lua no
#      existen y llegarian vacias al shell. Las de entorno ($HOME) si.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

SCRIPT="$REPO/hypr/scripts/lib/migrar_personal.py"

cat > "$TMP/personal.conf" <<'EOF'
# mis pantallas
monitor = eDP-1, preferred, 0x0, 1
monitor = HDMI-A-1, preferred, auto-right, 1.5
monitor = DP-2, disable
exec-once = nm-applet --indicator   # la red
env = GDK_SCALE,2
bind = SUPER, G, exec, $HOME/bin/g.sh "con comillas"
bindel = , XF86Launch1, exec, notify-send tecla
bind = $mainMod, X, exec, algo
bind = SUPER, Q, killactive
exec-once = $terminal
input {
    kb_options =
}
EOF

salida="$(python3 "$SCRIPT" "$TMP/personal.conf" 2>"$TMP/avisos")"; codigo=$?
printf '%s\n' "$salida" > "$TMP/personal.lua"

titulo "1. Lo que se traduce"
afirmar_igual "0" "$codigo" "termina bien"
afirmar "el Lua resultante es valido (luac)" luac -p "$TMP/personal.lua"
afirmar_contiene "$TMP/personal.lua" '^hl\.monitor\(\{ output = "eDP-1", mode = "preferred", position = "0x0", scale = 1 \}\)$' \
    "la pantalla interna, con su sitio"
afirmar_contiene "$TMP/personal.lua" '^hl\.monitor\(\{ output = "HDMI-A-1", mode = "preferred", position = "auto-right", scale = 1\.5 \}\)$' \
    "el televisor, con su escala 1.5 como numero"
afirmar_contiene "$TMP/personal.lua" 'output = "DP-2", disabled = true' "una salida apagada"
afirmar_contiene "$TMP/personal.lua" '^hl\.on\("hyprland\.start", function\(\) hl\.exec_cmd\("nm-applet --indicator"\) end\) -- la red$' \
    "exec-once, al arrancar, con su comentario"
afirmar_contiene "$TMP/personal.lua" '^hl\.env\("GDK_SCALE", "2"\)$' "una variable de entorno"
afirmar_contiene "$TMP/personal.lua" '^hl\.bind\("SUPER \+ G", hl\.dsp\.exec_cmd\("\$HOME/bin/g\.sh \\"con comillas\\""\)\)$' \
    "un atajo de exec, con \$HOME y las comillas escapadas"
afirmar_contiene "$TMP/personal.lua" '^hl\.bind\("XF86Launch1", hl\.dsp\.exec_cmd\("notify-send tecla"\), \{ repeating = true, locked = true \}\)$' \
    "bindel: repite y funciona bloqueado"
afirmar_contiene "$TMP/personal.lua" '^-- mis pantallas$' "los comentarios se conservan"

titulo "2. Lo que no se sabe, se deja comentado y se avisa"
for linea in 'bind = \$mainMod, X, exec, algo' 'bind = SUPER, Q, killactive' 'exec-once = \$terminal' 'input \{'; do
    afirmar_contiene "$TMP/personal.lua" "^-- SIN TRADUCIR .*: $linea" "comentada: ${linea//\\/}"
    afirmar_contiene "$TMP/avisos" "sin traducir: $linea" "   y avisada"
done
afirmar_no_contiene "$TMP/personal.lua" '^[^-].*\$terminal' "una variable de hyprlang nunca llega sin comentar"

titulo "3. Un personal.conf solo de comentarios no avisa de nada"
printf '# nada\n\n# de nada\n' > "$TMP/vacio.conf"
python3 "$SCRIPT" "$TMP/vacio.conf" > /dev/null 2>"$TMP/avisos2"
afirmar "sin avisos" test ! -s "$TMP/avisos2"

afirmar_intacta_la_casa_real
resumen
