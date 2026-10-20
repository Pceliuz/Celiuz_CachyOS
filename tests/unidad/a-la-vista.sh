#!/usr/bin/env bash
# tests/unidad/a-la-vista.sh — lib/a_la_vista.py: ¿se ve alguna ventana en
# alguna pantalla? Lo usa lock.sh para no encender el xray con una app delante
# (Minecraft detras del bloqueo, 2026-10-20). Y que el modo gaming conoce el
# escritorio del bloqueo, que es lo que lo causaba.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
L="$REPO/hypr/scripts/lib"

v() {   # v '<monitores json>' '<clientes json>'
    python3 -c 'import json,sys; sys.path.insert(0,sys.argv[1]); import a_la_vista as a
print(a.visibles(json.loads(sys.argv[2]), json.loads(sys.argv[3])))' "$L" "$1" "$2"
}
M99='[{"activeWorkspace":{"id":99},"specialWorkspace":{"id":0}}]'

titulo "1. Que se ve"
afirmar_igual "[]" "$(v "$M99" '[{"class":"kitty","workspace":{"id":3}}]')" \
    "en el 99, una ventana del 3 no se ve"
afirmar_igual "[('kitty', 99)]" "$(v "$M99" '[{"class":"kitty","workspace":{"id":99}}]')" \
    "una ventana en el 99 si"
afirmar_igual "[('mpv', 4)]" \
    "$(v '[{"activeWorkspace":{"id":99}},{"activeWorkspace":{"id":4}}]' '[{"class":"mpv","workspace":{"id":4}}]')" \
    "con dos pantallas, la de la otra tambien"
afirmar_igual "[('pip', 2)]" "$(v "$M99" '[{"class":"pip","workspace":{"id":2},"pinned":true}]')" \
    "una ventana fijada sale en todos"
afirmar_igual "[('nota', -98)]" \
    "$(v '[{"activeWorkspace":{"id":99},"specialWorkspace":{"id":-98}}]' '[{"class":"nota","workspace":{"id":-98}}]')" \
    "el escritorio especial, si esta abierto"
afirmar_igual "[]" "$(v "$M99" '[{"class":"x","workspace":{"id":99},"hidden":true},{"class":"y","workspace":{"id":99},"mapped":false}]')" \
    "las escondidas y las sin dibujar, no"

titulo "2. Tres salidas"
binario_falso hyprctl 0 'case "$1" in monitors) echo '"'"'[{"activeWorkspace":{"id":99}}]'"'"' ;; clients) echo "[]" ;; esac'
"$L/a_la_vista.py" >/dev/null; afirmar_igual "0" "$?" "nada a la vista: 0"
binario_falso hyprctl 0 'case "$1" in monitors) echo '"'"'[{"activeWorkspace":{"id":99}}]'"'"' ;; clients) echo '"'"'[{"class":"a","workspace":{"id":99}}]'"'"' ;; esac'
"$L/a_la_vista.py" >/dev/null; afirmar_igual "1" "$?" "algo a la vista: 1"
binario_falso hyprctl 1 'echo "HYPRLAND_INSTANCE_SIGNATURE not set"'
"$L/a_la_vista.py" >/dev/null; afirmar_igual "2" "$?" "sin Hyprland: 2 (no lo se), que lock.sh trata como un si"

titulo "3. El modo gaming conoce el escritorio del bloqueo"
ws_lock="$(sed -n 's/^WORKSPACE_LIMPIO="\${WORKSPACE_LIMPIO:-\([0-9]*\)}"/\1/p' "$REPO/hypr/scripts/lock.sh")"
ws_mg="$(sed -n 's/^WS_BLOQUEO = \([0-9]*\)/\1/p' "$REPO/hypr/scripts/modo-gaming.py")"
afirmar "lock.sh dice cual es" test -n "$ws_lock"
afirmar_igual "$ws_lock" "$ws_mg" "y modo-gaming.py usa el mismo"
afirmar_contiene "$REPO/hypr/scripts/modo-gaming.py" 'if n == WS_BLOQUEO:' \
    "el vigilante no te saca de el"

afirmar_intacta_la_casa_real
resumen
