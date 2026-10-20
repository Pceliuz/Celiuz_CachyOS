#!/usr/bin/env bash
# tests/unidad/paneles-exclusivos.sh — los paneles de la barra (Bluetooth,
# WiFi, reloj) se excluyen: abrir uno cierra los otros (lib/panel_capa.py).
#
# QUE VIGILA
# ----------
# - Que abrir un panel cierra el que hubiera abierto, y no se cierra a si mismo.
# - Que ESPERA a que el otro salga: al salir manda `release` a la barra, y si
#   llegara despues del `hold` del nuevo la barra se esconderia con el panel
#   abierto (el demonio de las barras guarda un si/no, no una cuenta).
# - Que un .pid viejo cuyo numero lo heredo otro proceso no mata a ese proceso.
#
# Los paneles son de mentira (un python que se llama como el panel y tarda en
# salir); no se abre ninguna ventana.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
export HYPRLAND_INSTANCE_SIGNATURE="firma_paneles"
LIB="$REPO/hypr/scripts/lib"
RUN="$XDG_RUNTIME_DIR"

# Un panel de mentira: se llama como el de verdad, apunta su pid donde lo
# apunta lanzar(), y al recibir SIGTERM tarda un poco y deja «release» escrito.
cat > "$TMP/falso.py" <<'PY'
import os, signal, sys, time
nombre, orden = sys.argv[1], sys.argv[2]
def salir(*_):
    time.sleep(0.4)
    with open(orden, "a") as f:
        f.write("release %s\n" % nombre)
    sys.exit(0)
signal.signal(signal.SIGTERM, salir)
while True:
    time.sleep(1)
PY

panel_falso() {   # panel_falso NOMBRE → deja el pid en $PID_FALSO
    cp "$TMP/falso.py" "$TMP/$1.py"
    python3 "$TMP/$1.py" "$1" "$TMP/orden" &
    PID_FALSO=$!
    echo "$PID_FALSO" > "$RUN/$1.$HYPRLAND_INSTANCE_SIGNATURE.pid"
    sleep 0.2
}

vivo() { kill -0 "$1" 2>/dev/null; }

titulo "1. Abrir el reloj cierra el WiFi y espera a que salga"
panel_falso wifi-panel; WIFI=$PID_FALSO
: > "$TMP/orden"
python3 - "$LIB" "$TMP/orden" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import panel_capa as pc
pc._cerrar_los_otros("calendar-panel")
with open(sys.argv[2], "a") as f:
    f.write("hold calendar-panel\n")
PY
sleep 0.1
afirmar "el WiFi ya no esta abierto" bash -c "! kill -0 $WIFI 2>/dev/null"
afirmar_igual "release wifi-panel|hold calendar-panel|" \
    "$(tr '\n' '|' < "$TMP/orden")" "el release del WiFi llega ANTES del hold del reloj"

titulo "2. No se cierra a si mismo"
panel_falso bluetooth-panel; BT=$PID_FALSO
python3 -c "import sys; sys.path.insert(0, '$LIB'); import panel_capa as pc; pc._cerrar_los_otros('bluetooth-panel')"
afirmar "el Bluetooth sigue abierto" vivo "$BT"
kill "$BT"; wait "$BT" 2>/dev/null

titulo "3. Un pid viejo heredado por otro proceso no se toca"
sleep 300 &
AJENO=$!
echo "$AJENO" > "$RUN/wifi-panel.$HYPRLAND_INSTANCE_SIGNATURE.pid"
echo "$AJENO" > "$RUN/calendar-panel.$HYPRLAND_INSTANCE_SIGNATURE.pid"
salida="$(python3 -c "
import sys; sys.path.insert(0, '$LIB'); import panel_capa as pc
pc._cerrar_los_otros('bluetooth-panel')
print(pc._ya_abierto_lo_cierro('calendar-panel'))" 2>&1)"; codigo=$?
afirmar_igual "0 False" "$codigo $salida" "sale bien y no cree que el reloj este abierto"
afirmar "el proceso ajeno sigue vivo" vivo "$AJENO"
kill "$AJENO"; wait "$AJENO" 2>/dev/null

titulo "4. Los tres paneles llaman a lanzar() con su nombre de la lista"
python3 -c "import sys; sys.path.insert(0, '$LIB'); import panel_capa as pc; print(pc.PANELES)" > "$TMP/lista"
for p in bluetooth-panel wifi-panel calendar-panel; do
    afirmar_contiene "$TMP/lista" "'$p'" "$p esta en PANELES"
    afirmar_contiene "$REPO/hypr/scripts/$p.py" "pc\.lanzar\(\"$p\"" "$p.py usa lanzar(\"$p\", ...)"
done

afirmar_intacta_la_casa_real
resumen
