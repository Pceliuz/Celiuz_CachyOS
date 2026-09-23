#!/usr/bin/env bash
# tests/unidad/captura.sh — que la captura de una zona (SUPER+S) no se lleve
# dentro la capa de seleccion, y que las otras dos capturas no paguen esa espera.
#
# QUE VIGILA, Y POR QUE
# ---------------------
# El 2026-09-23 las capturas de zona salian con un recuadro violeta dentro. No
# era slurp pintando de mas: cuando sueltas el boton, slurp termina, pero su capa
# NO desaparece de golpe — Hyprland la desvanece (`fadeLayersOut`), y eso dura
# entre 90 y 125 ms (medido, viendola pasar por 65%, 55%, 47% y 39% de
# opacidad). grim pide su fotograma mucho antes de eso, asi que retrataba el
# escritorio con media seleccion encima. En la captura del usuario el borde
# estaba al 42%: justo a mitad de la transicion.
#
# `--full` y `--ventana` no lo sufrian NUNCA, y esa era la pista: ahi no hay
# slurp. Por eso esta prueba comprueba las tres.
#
# Lo unico que se puede comprobar sin un compositor delante es la SECUENCIA: que
# entre slurp y grim el script espera de verdad. Si alguien quita la espera,
# esto falla. Lo otro —que la captura salga limpia— se mide con un Hyprland de
# verdad; la receta esta en SIGUIENTE.md.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

SCRIPT="$REPO/hypr/scripts/screenshot.sh"

# Cada falso apunta su nombre Y el instante en que se le llamo, en nanosegundos:
# con eso se mide cuanto tarda el script entre uno y otro.
apuntar='printf "%s %s\n" "$(basename "$0")" "$(date +%s%N)" >> "'"$REGISTRO"'/orden.log"'

binario_falso slurp 0 "$apuntar; echo '10,20 300x200'"
binario_falso grim 0 "$apuntar; printf 'captura' > \"\${@: -1}\""
binario_falso wl-copy 0 "$apuntar; cat > /dev/null"
binario_falso notify-send 0 "$apuntar"
binario_falso xdg-user-dir 0 "echo \"$TMP/imagenes\""
# El hyprctl de mentira contesta SIN la capa de seleccion: o sea, ya se fue.
binario_falso hyprctl 0 "$apuntar; echo 'Layer level 3 (overlay):'"

momento() {   # momento <programa> — cuando se le llamo, en ms desde el arranque
    awk -v p="$1" '$1 == p { printf "%.0f\n", $2 / 1000000; exit }' "$REGISTRO/orden.log"
}

# --- 1. Zona (SUPER+S): espera entre slurp y grim ------------------------------

titulo "1. Capturar una zona espera a que la seleccion se borre"
: > "$REGISTRO/orden.log"
salida="$(bash "$SCRIPT" 2>&1)"; codigo=$?

afirmar_igual "0" "$codigo" "el script termina bien"
afirmar_contiene "$REGISTRO/slurp.log" "b16cff" "se le piden a slurp los colores del escritorio"
afirmar_contiene "$REGISTRO/grim.log" "-g 10,20 300x200" \
    "grim recorta justo la zona que devolvio slurp"

t_slurp="$(momento slurp)"
t_grim="$(momento grim)"
espera=$((t_grim - t_slurp))
if [ "$espera" -ge 200 ]; then
    ok "entre slurp y grim pasan $espera ms (>= 200)"
else
    fallo "entre slurp y grim se espera lo suficiente" \
        "solo pasaron $espera ms; la capa de seleccion tarda hasta 125 ms en
      apagarse, asi que grim la retrataria. Es el fallo del 2026-09-23."
fi
afirmar_contiene "$REGISTRO/hyprctl.log" "layers" \
    "y antes se le pregunta a Hyprland si la capa sigue puesta"

# --- 2. Pantalla completa (SUPER+SHIFT+S): sin espera ---------------------------

titulo "2. La pantalla entera no paga esa espera (ahi no hay slurp)"
: > "$REGISTRO/orden.log"
rm -f "$REGISTRO/slurp.log" "$REGISTRO/hyprctl.log"
inicio="$(date +%s%N)"
bash "$SCRIPT" --full >/dev/null 2>&1
fin="$(date +%s%N)"
tardo=$(( (fin - inicio) / 1000000 ))

afirmar "no se llama a slurp" test ! -f "$REGISTRO/slurp.log"
afirmar_no_contiene "$REGISTRO/hyprctl.log" "layers" "ni se pregunta por la capa"
if [ "$tardo" -lt 200 ]; then
    ok "tarda $tardo ms, sin la espera de la seleccion"
else
    fallo "la captura completa no espera" "tardo $tardo ms"
fi

# --- 3. Ventana (SUPER+ALT+S) ---------------------------------------------------

titulo "3. La ventana enfocada pregunta a Hyprland, y tampoco espera"
: > "$REGISTRO/orden.log"
rm -f "$REGISTRO/slurp.log" "$REGISTRO/hyprctl.log" "$REGISTRO/grim.log"
binario_falso hyprctl 0 "$apuntar; echo '{\"at\":[100,50],\"size\":[640,480]}'"
inicio="$(date +%s%N)"
bash "$SCRIPT" --ventana >/dev/null 2>&1
fin="$(date +%s%N)"
tardo=$(( (fin - inicio) / 1000000 ))

afirmar_contiene "$REGISTRO/hyprctl.log" "activewindow" "pide la ventana activa"
afirmar_contiene "$REGISTRO/grim.log" "-g 100,50 640x480" \
    "y recorta su geometria"
afirmar "no se llama a slurp" test ! -f "$REGISTRO/slurp.log"
if [ "$tardo" -lt 200 ]; then
    ok "tarda $tardo ms, sin la espera de la seleccion"
else
    fallo "la captura de ventana no espera" "tardo $tardo ms"
fi

# --- 4. Con las animaciones apagadas no se espera --------------------------------
#
# Quien las apaga —por gusto o por ahorrar en una maquina justa— no tiene
# desvanecido que esperar: la capa se va con su proceso. Cobrarle el plazo igual
# seria hacerle lento lo que en su equipo es instantaneo.

titulo "4. Sin animaciones, la captura no espera"
: > "$REGISTRO/orden.log"
rm -f "$REGISTRO/slurp.log" "$REGISTRO/hyprctl.log" "$REGISTRO/grim.log"
binario_falso slurp 0 "$apuntar; echo '10,20 300x200'"
# Este hyprctl contesta que las animaciones estan apagadas.
binario_falso hyprctl 0 "$apuntar; echo 'int: 0'"
bash "$SCRIPT" >/dev/null 2>&1
t_slurp="$(momento slurp)"; t_grim="$(momento grim)"
espera=$((t_grim - t_slurp))
if [ "$espera" -lt 200 ]; then
    ok "entre slurp y grim pasan solo $espera ms"
else
    fallo "sin animaciones no se espera" "pasaron $espera ms"
fi
afirmar_no_contiene "$REGISTRO/hyprctl.log" "layers" \
    "ni se llega a preguntar por la capa"

# --- 5. Cancelar no deja nada ----------------------------------------------------

titulo "5. Si cancelas la seleccion no se captura nada"
rm -f "$REGISTRO/grim.log"
binario_falso slurp 1 "$apuntar"     # Escape o clic derecho: sale con 1
bash "$SCRIPT" >/dev/null 2>&1
afirmar_igual "0" "$(veces_llamado grim)" "no se llega a llamar a grim"

afirmar_intacta_la_casa_real

resumen
