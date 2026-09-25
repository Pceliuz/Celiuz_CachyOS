# hypr/scripts/lib/hypr.sh — el gemelo en shell de lib/hypr.py.
#
# Hablarle a Hyprland en el idioma que entienda: con la config en Lua,
# `hyprctl dispatch workspace 3` y `hyprctl keyword ...` dan ERROR (medido el
# 2026-09-25); con la de hyprlang, la forma Lua da «Invalid dispatcher». El
# porque entero y la tabla de lo que se traduce estan en la cabecera de
# lib/hypr.py.
#
# Existe en shell por lo mismo que lib/canales.sh: lock.sh corre en cada
# bloqueo y los binds en cada pulsacion, y no pueden pagar un arranque de
# python. `tests/unidad/hypr-compat.sh` compara las dos implementaciones caso
# por caso.
#
#   . lib/hypr.sh
#   hypr_modo                         lua | conf | (vacio: no se sabe)
#   hypr_despachar workspace 3        hyprctl dispatch, en el idioma que toque
#   hypr_ajustar misc:session_lock_xray true
#
# El modo se pregunta UNA vez por proceso y se guarda en HYPR_MODO: no cambia
# mientras viva el mismo Hyprland.

# _hypr_cadena <texto> — literal de cadena Lua entre comillas dobles.
_hypr_cadena() {
    local t="$1"
    t="${t//\\/\\\\}"
    t="${t//\"/\\\"}"
    t="${t//$'\n'/\\n}"
    t="${t//$'\r'/\\r}"
    t="${t//$'\t'/\\t}"
    printf '"%s"' "$t"
}

_hypr_es_numero() { [[ "$1" =~ ^-?[0-9]+(\.[0-9]+)?$ ]]; }

# _hypr_valor <texto> — true/false y numeros tal cual; lo demas, cadena.
_hypr_valor() {
    local t="${1#"${1%%[![:space:]]*}"}"
    t="${t%"${t##*[![:space:]]}"}"
    case "$t" in
        true|false) printf '%s' "$t" ;;
        yes|on)     printf 'true' ;;
        no|off)     printf 'false' ;;
        *) if _hypr_es_numero "$t"; then printf '%s' "$t"; else _hypr_cadena "$t"; fi ;;
    esac
}

# hypr_modo_de <respuesta de «eval return 1»>
hypr_modo_de() {
    local r="$1"
    r="${r#"${r%%[![:space:]]*}"}"; r="${r%"${r##*[![:space:]]}"}"
    if [ "$r" = "ok" ]; then
        echo lua
    elif [[ "$r" == *"only supported with the lua config manager"* ]] \
         || [[ "${r,,}" == *"unknown request"* ]]; then
        echo conf
    else
        echo ""
    fi
}

# _hypr_saber_modo — rellena HYPR_MODO en ESTE shell. Tiene que ser asi y no
# `m="$(hypr_modo)"`: eso corre en un subshell, lo que guarda se pierde al
# volver, y se preguntaba a Hyprland en cada orden (lo pillo la prueba).
_hypr_saber_modo() {
    if [ -z "${HYPR_MODO+x}" ]; then
        HYPR_MODO="$(hypr_modo_de "$(hyprctl eval 'return 1' 2>/dev/null)")"
    fi
}

hypr_modo() {
    _hypr_saber_modo
    printf '%s\n' "$HYPR_MODO"
}

# hypr_dispatch_lua <dispatcher> [arg...] — la expresion Lua, o falla (1).
hypr_dispatch_lua() {
    local d="$1"; shift
    local a="$*"
    a="${a#"${a%%[![:space:]]*}"}"; a="${a%"${a##*[![:space:]]}"}"
    case "$d" in
        workspace)
            [ -n "$a" ] || { echo "hypr.sh: workspace sin escritorio" >&2; return 1; }
            if _hypr_es_numero "$a"; then
                printf 'hl.dsp.focus({ workspace = %s })' "$a"
            else
                printf 'hl.dsp.focus({ workspace = %s })' "$(_hypr_cadena "$a")"
            fi ;;
        dpms)
            local accion="${a%% *}"; [ -n "$accion" ] || accion=toggle
            case "$accion" in on|off|toggle) ;; *)
                echo "hypr.sh: dpms: accion desconocida «$accion»" >&2; return 1 ;; esac
            printf 'hl.dsp.dpms({ action = "%s" })' "$accion" ;;
        exit)
            printf 'hl.dsp.exit()' ;;
        exec)
            [ -n "$a" ] || { echo "hypr.sh: exec sin orden" >&2; return 1; }
            printf 'hl.dsp.exec_cmd(%s)' "$(_hypr_cadena "$a")" ;;
        *)
            echo "hypr.sh: no se traducir el dispatcher «$d»" >&2; return 1 ;;
    esac
}

# hypr_keyword_lua <clave> <valor> — el Lua de un `keyword` viejo, o falla.
hypr_keyword_lua() {
    local c="$1" v="$2"
    if [ "$c" = monitor ]; then
        local IFS=,
        # shellcheck disable=SC2206
        local p=($v)
        unset IFS
        local i
        for i in "${!p[@]}"; do
            p[$i]="${p[$i]#"${p[$i]%%[![:space:]]*}"}"; p[$i]="${p[$i]%"${p[$i]##*[![:space:]]}"}"
        done
        if [ "${#p[@]}" -ne 4 ] || [ -z "${p[0]}" ]; then
            echo "hypr.sh: monitor: se esperaban 4 campos, «$v»" >&2; return 1
        fi
        printf 'hl.monitor({ output = %s, mode = %s, position = %s, scale = %s })' \
            "$(_hypr_cadena "${p[0]}")" "$(_hypr_cadena "${p[1]}")" \
            "$(_hypr_cadena "${p[2]}")" "$(_hypr_valor "${p[3]}")"
        return 0
    fi
    local trozos=() t sub
    local IFS=:
    for t in $c; do
        [ -n "$t" ] || continue
        [[ "$t" =~ ^[a-z_][a-z0-9_.]*$ ]] || { unset IFS; echo "hypr.sh: no se traducir la opcion «$c»" >&2; return 1; }
        local IFS=.
        for sub in $t; do trozos+=("$sub"); done
        local IFS=:
    done
    unset IFS
    [ "${#trozos[@]}" -ge 2 ] || { echo "hypr.sh: no se traducir la opcion «$c»" >&2; return 1; }
    local lua i
    lua="$(_hypr_valor "$v")"
    for (( i=${#trozos[@]}-1; i>=0; i-- )); do
        lua="{ ${trozos[$i]} = $lua }"
    done
    printf 'hl.config(%s)' "$lua"
}

# hypr_peticion_dispatch <modo> <dispatcher> [arg...] — lo que va detras de
# `dispatch`.
hypr_peticion_dispatch() {
    local m="$1"; shift
    if [ "$m" = lua ]; then
        hypr_dispatch_lua "$@"
    else
        local s="$*"; s="${s%"${s##*[![:space:]]}"}"
        printf '%s' "$s"
    fi
}

# hypr_peticion_keyword <modo> <clave> <valor> — «verbo resto».
hypr_peticion_keyword() {
    if [ "$1" = lua ]; then
        local l; l="$(hypr_keyword_lua "$2" "$3")" || return 1
        printf 'eval %s' "$l"
    else
        printf 'keyword %s %s' "$2" "$3"
    fi
}

# hypr_despachar <dispatcher> [arg...] — lo manda. Sin modo conocido (Hyprland
# no contesta) se intenta como hyprlang, que es lo que haria el script de antes.
hypr_despachar() {
    local peticion
    _hypr_saber_modo
    peticion="$(hypr_peticion_dispatch "$HYPR_MODO" "$@")" || return 1
    hyprctl dispatch "$peticion"
}

# hypr_ajustar <clave> <valor> — el `hyprctl keyword` de siempre, en los dos
# idiomas.
hypr_ajustar() {
    _hypr_saber_modo
    if [ "$HYPR_MODO" = lua ]; then
        local l; l="$(hypr_keyword_lua "$1" "$2")" || return 1
        hyprctl eval "$l"
    else
        hyprctl keyword "$1" "$2"
    fi
}
