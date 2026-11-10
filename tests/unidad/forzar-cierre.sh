#!/usr/bin/env bash
# tests/unidad/forzar-cierre.sh — SUPER+SHIFT+Q (hypr/scripts/forzar-cierre.sh).
#
# QUE VIGILA
# ----------
# 1. Una app que atiende SIGTERM se cierra con eso, sin SIGKILL.
# 2. Una que lo ignora cae con SIGKILL pasado el plazo, y se avisa.
# 3. Sin ventana activa, o con la de Hyprland, o con un pid de otro usuario,
#    no mata nada.
# Los procesos son de mentira (sleep); hyprctl y notify-send, falsos.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
SCRIPT="$REPO/hypr/scripts/forzar-cierre.sh"
export CELIUZ_FORZAR_ESPERA=1
export VENTANA="$TMP/ventana.json"
binario_falso hyprctl 0 'cat "$VENTANA"'
binario_falso notify-send 0

ventana() { printf '{"pid": %s, "class": "%s", "title": "x"}\n' "$1" "$2" > "$VENTANA"; }
vivo() { kill -0 "$1" 2>/dev/null && [ "$(cut -d' ' -f3 "/proc/$1/stat" 2>/dev/null)" != Z ]; }

titulo "1. La que atiende SIGTERM"
sleep 60 & obediente=$!
ventana "$obediente" ONLYOFFICE
"$SCRIPT"; codigo=$?
sleep 0.2
afirmar_igual "0" "$codigo" "sale bien"
afirmar "el proceso ya no esta" sh -c "! kill -0 $obediente 2>/dev/null || grep -q ' Z ' /proc/$obediente/stat"
afirmar "avisa de que lo cerro (sin «a la fuerza»)" sh -c "grep -q 'Cerrado: ONLYOFFICE' '$REGISTRO/notify-send.log' && ! grep -q 'fuerza' '$REGISTRO/notify-send.log'"
wait "$obediente" 2>/dev/null

titulo "2. La que ignora SIGTERM"
rm -f "$REGISTRO/notify-send.log"
bash -c 'trap "" TERM; while :; do sleep 0.1; done' & terco=$!
sleep 0.2
ventana "$terco" Terca
t0=$SECONDS
"$SCRIPT"; codigo=$?
sleep 0.2
afirmar_igual "0" "$codigo" "sale bien"
afirmar "cae con SIGKILL" sh -c "! kill -0 $terco 2>/dev/null || grep -q ' Z ' /proc/$terco/stat"
afirmar "pasado el plazo, no antes" test $((SECONDS - t0)) -ge 1
afirmar "y avisa de que fue a la fuerza" grep -q 'Cerrado a la fuerza: Terca' "$REGISTRO/notify-send.log"
wait "$terco" 2>/dev/null

titulo "3. Lo que no se toca"
sleep 60 & testigo=$!
echo '{}' > "$VENTANA"
"$SCRIPT"; codigo=$?
afirmar_igual "1" "$codigo" "sin ventana activa: sale con 1"
cp "$(command -v sleep)" "$TMP/Hyprland"
"$TMP/Hyprland" 60 & falso_hypr=$!
sleep 0.1
ventana "$falso_hypr" Hyprland
"$SCRIPT"; codigo=$?
afirmar_igual "1" "$codigo" "la ventana dice ser de Hyprland: sale con 1"
afirmar "y Hyprland sigue vivo" vivo "$falso_hypr"
ventana 1 init
"$SCRIPT"; codigo=$?
afirmar_igual "1" "$codigo" "pid 1: sale con 1"
afirmar "el testigo sigue vivo" vivo "$testigo"
kill "$testigo" "$falso_hypr" 2>/dev/null; wait 2>/dev/null

afirmar_intacta_la_casa_real
resumen
