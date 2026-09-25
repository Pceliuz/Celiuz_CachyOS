#!/usr/bin/env bash
# tests/unidad/hypr-compat.sh — hablarle a Hyprland en su idioma (lib/hypr.py y
# su gemelo lib/hypr.sh).
#
# QUE VIGILA, Y POR QUE
# ---------------------
# Con la config en Lua, `hyprctl dispatch workspace 3` y `hyprctl keyword` dan
# error; con la de hyprlang, la forma Lua da «Invalid dispatcher». Medido el
# 2026-09-25 en dos anidados. Si la traduccion se rompe, se rompen EN SILENCIO
# el bloqueo (lock.sh), el apagado de pantalla (hypridle), la rueda de la barra
# y los modos de monitores.py.
#
#   1. Las traducciones, contra lo que se midio que Hyprland acepta.
#   2. Que python y shell dicen EXACTAMENTE lo mismo en cada caso (la convencion
#      esta escrita dos veces a la fuerza, como la de lib/canales).
#   3. Que el modo se deduce bien de la respuesta, con «no lo se» aparte.
#   4. Que con un hyprctl de mentira de cada modo, lo que sale es lo que ese
#      modo acepta.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

PY="$REPO/hypr/scripts/lib/hypr.py"
. "$REPO/hypr/scripts/lib/hypr.sh"

py_dispatch() { python3 "$PY" dispatch "$@" 2>/dev/null; }
py_keyword()  { python3 "$PY" keyword "$@" 2>/dev/null; }

# --- 1 y 2. Las traducciones, y que los gemelos coinciden --------------------

titulo "1. dispatch: lo que se traduce, y lo mismo en python y en shell"
comparar_dispatch() {   # comparar_dispatch <modo> <esperado> <dispatcher> [arg]
    local modo="$1" esperado="$2"; shift 2
    local sh py
    sh="$(hypr_peticion_dispatch "$modo" "$@" 2>/dev/null)"
    py="$(py_dispatch "$modo" "$@")"
    afirmar_igual "$esperado" "$py" "[$modo] $* → $esperado"
    afirmar_igual "$py" "$sh" "   y el shell dice lo mismo"
}
comparar_dispatch lua 'hl.dsp.focus({ workspace = 3 })'       workspace 3
comparar_dispatch lua 'hl.dsp.focus({ workspace = "e+1" })'   workspace e+1
comparar_dispatch lua 'hl.dsp.dpms({ action = "on" })'        dpms on
comparar_dispatch lua 'hl.dsp.dpms({ action = "off" })'       dpms off
comparar_dispatch lua 'hl.dsp.exit()'                         exit
comparar_dispatch lua 'hl.dsp.exec_cmd("echo \"hola\" \\ yo")' exec 'echo "hola" \ yo'
comparar_dispatch conf 'workspace 3'                          workspace 3
comparar_dispatch conf 'dpms on'                              dpms on
comparar_dispatch conf 'exit'                                 exit

titulo "1b. keyword: hl.config anidado, y los monitores"
comparar_keyword() {   # comparar_keyword <modo> <esperado> <clave> <valor>
    local modo="$1" esperado="$2" sh py
    sh="$(hypr_peticion_keyword "$modo" "$3" "$4" 2>/dev/null)"
    py="$(py_keyword "$modo" "$3" "$4")"
    afirmar_igual "$esperado" "$py" "[$modo] keyword $3 $4"
    afirmar_igual "$py" "$sh" "   y el shell dice lo mismo"
}
comparar_keyword lua 'eval hl.config({ misc = { enable_anr_dialog = false } })' misc:enable_anr_dialog false
comparar_keyword lua 'eval hl.config({ misc = { session_lock_xray = true } })'  misc:session_lock_xray true
comparar_keyword lua 'eval hl.config({ general = { col = { active_border = "rgba(ffffffff)" } } })' general:col.active_border 'rgba(ffffffff)'
comparar_keyword lua 'eval hl.config({ decoration = { blur = { passes = 3 } } })' decoration:blur:passes 3
comparar_keyword lua 'eval hl.config({ decoration = { dim_strength = 0.3 } })'  decoration:dim_strength 0.3
comparar_keyword lua 'eval hl.monitor({ output = "HDMI-A-1", mode = "1920x1080@100", position = "1366x0", scale = 1.5 })' \
    monitor 'HDMI-A-1,1920x1080@100,1366x0,1.5'
comparar_keyword conf 'keyword misc:session_lock_xray true' misc:session_lock_xray true

titulo "1c. Lo que no se sabe traducir falla, y no inventa"
afirmar "python: un dispatcher desconocido falla" bash -c '! python3 "$1" dispatch lua movewindow l 2>/dev/null' _ "$PY"
afirmar "shell: tambien" bash -c '. "$1"; ! hypr_peticion_dispatch lua movewindow l 2>/dev/null' _ "$REPO/hypr/scripts/lib/hypr.sh"
afirmar "python: un monitor mal formado falla" bash -c '! python3 "$1" keyword lua monitor "HDMI-A-1,preferred" 2>/dev/null' _ "$PY"
afirmar "shell: tambien" bash -c '. "$1"; ! hypr_peticion_keyword lua monitor "HDMI-A-1,preferred" 2>/dev/null' _ "$REPO/hypr/scripts/lib/hypr.sh"
afirmar "una opcion con caracteres raros falla" bash -c '. "$1"; ! hypr_peticion_keyword lua "misc:x;os.exit()" 1 2>/dev/null' _ "$REPO/hypr/scripts/lib/hypr.sh"

# --- 3. El modo ------------------------------------------------------------------

titulo "3. El modo sale de la respuesta a «eval return 1»"
for caso in "ok|lua" "eval is only supported with the lua config manager|conf" \
            "unknown request|conf" "|" "HYPRLAND_INSTANCE_SIGNATURE not set!|"; do
    resp="${caso%|*}"; esp="${caso##*|}"
    afirmar_igual "$esp" "$(python3 "$PY" modo-de "$resp")" "python: «${resp:-(nada)}» → «${esp:-no lo se}»"
    afirmar_igual "$esp" "$(hypr_modo_de "$resp")" "   shell: igual"
done

# --- 4. Con un hyprctl de mentira de cada modo ------------------------------------

titulo "4. Lo que sale hacia Hyprland, en cada modo"
binario_falso hyprctl 0 'case "$1" in eval) [ "$2" = "return 1" ] && echo ok || echo ok ;; *) echo ok ;; esac'
( unset HYPR_MODO; hypr_despachar workspace 4 >/dev/null; hypr_ajustar misc:session_lock_xray true >/dev/null )
afirmar_contiene "$REGISTRO/hyprctl.log" '^dispatch hl\.dsp\.focus\(\{ workspace = 4 \}\)$' "Lua: dispatch con la forma Lua"
afirmar_contiene "$REGISTRO/hyprctl.log" '^eval hl\.config\(\{ misc = \{ session_lock_xray = true \} \}\)$' "Lua: keyword se vuelve eval"
afirmar_igual "1" "$(grep -c 'return 1' "$REGISTRO/hyprctl.log")" "el modo se pregunta UNA vez por proceso"

rm -f "$REGISTRO/hyprctl.log"
binario_falso hyprctl 0 'case "$1" in eval) echo "eval is only supported with the lua config manager" ;; *) echo ok ;; esac'
( unset HYPR_MODO; hypr_despachar workspace 4 >/dev/null; hypr_ajustar misc:session_lock_xray true >/dev/null )
afirmar_contiene "$REGISTRO/hyprctl.log" '^dispatch workspace 4$' "hyprlang: dispatch de siempre"
afirmar_contiene "$REGISTRO/hyprctl.log" '^keyword misc:session_lock_xray true$' "hyprlang: keyword de siempre"

rm -f "$REGISTRO/hyprctl.log"
salida="$(bash "$REPO/hypr/scripts/despachar.sh" dpms on 2>&1)"; codigo=$?
afirmar_igual "0" "$codigo" "despachar.sh termina bien"
afirmar_contiene "$REGISTRO/hyprctl.log" '^dispatch dpms on$' "despachar.sh manda la orden"

afirmar_intacta_la_casa_real
resumen
