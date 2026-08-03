#!/usr/bin/env bash
# tests/unidad/pantalla.sh — lib/pantalla.py, la pieza de la que salen todas las
# medidas del escritorio.
#
# Lo que se comprueba aqui es exactamente lo que rompio en la laptop: que en una
# pantalla que no sea la de 1920x1080 del autor los numeros SE ADAPTEN, y que si
# no se puede medir nada siga saliendo un numero utilizable en vez de un hueco.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
PANTALLA="$REPO/hypr/scripts/lib/pantalla.py"

titulo "1. Sin sesion de Hyprland (respaldo)"
# preparar_entorno ya quito HYPRLAND_INSTANCE_SIGNATURE, asi que no hay a quien
# preguntar: tiene que caer al kernel o a los valores de reserva.
salida="$("$PANTALLA" 2>&1)"
afirmar "responde algo aunque no haya compositor" test -n "$salida"
afirmar "no se cuelga ni revienta" test $? -eq 0
ancho="$("$PANTALLA" ancho 2>/dev/null)"
afirmar "da un ancho que es un numero" test -n "$ancho"
case "$ancho" in
    ''|*[!0-9]*) fallo "el ancho es un entero" "obtuve «$ancho»" ;;
    *)           ok "el ancho es un entero ($ancho)" ;;
esac

titulo "2. El fragmento para la pantalla de bloqueo"
frag="$("$PANTALLA" --hyprlock 2>/dev/null)"
printf '%s' "$frag" > "$TMP/frag.conf"
cuantas=$(grep -c '^\$lock_' "$TMP/frag.conf" 2>/dev/null || echo 0)
afirmar_igual "15" "$cuantas" "define 15 medidas"
afirmar_contiene "$TMP/frag.conf" 'NO EDITAR' "avisa de que es generado"

# Y lo que de verdad importa: que TODAS las que usa hyprlock.conf esten aqui.
# Si alguien anade una variable a hyprlock.conf y se olvida de pantalla.py, el
# bloqueo saldria con la medida de 1080p sin que nadie se entere.
python3 - "$REPO/hypr/hyprlock.conf" "$TMP/frag.conf" > "$TMP/faltan.txt" <<'PY'
import re, sys
conf = open(sys.argv[1], encoding="utf-8").read()
frag = open(sys.argv[2], encoding="utf-8").read()
usadas = set(re.findall(r'\$(lock_\w+)', conf))
generadas = set(re.findall(r'^\$(lock_\w+)', frag, re.M))
defecto = set(re.findall(r'^\$(lock_\w+)\s*=', conf, re.M))
for nombre in sorted(usadas - generadas):
    print("sin generar:", nombre)
for nombre in sorted(usadas - defecto):
    print("sin valor por defecto:", nombre)
PY
if [ -s "$TMP/faltan.txt" ]; then
    fallo "cada medida de hyprlock.conf tiene generado Y valor por defecto" "$(cat "$TMP/faltan.txt")"
else
    ok "cada medida de hyprlock.conf tiene generado Y valor por defecto"
fi

titulo "3. Las medidas se adaptan a la pantalla"
python3 - "$REPO/hypr/scripts/lib" > "$TMP/escalas.txt" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import pantalla as p

def mon(w, h, esc=1.0):
    return {"nombre": "X", "descripcion": "", "ancho": w, "alto": h,
            "refresco": 60.0, "escala": esc, "x": 0, "y": 0,
            "activo": True, "origen": "prueba"}

base = p.medidas(mon(1920, 1080))
laptop = p.medidas(mon(1366, 768))
cuatrok = p.medidas(mon(3840, 2160))
escalada = p.medidas(mon(3840, 2160, 1.5))
vertical = p.medidas(mon(1080, 1920))

print("base_factor", base["factor"])
print("laptop_menor", int(laptop["lock_reloj"] < base["lock_reloj"]))
print("4k_mayor", int(cuatrok["lock_reloj"] > base["lock_reloj"]))
print("escala_cuenta", int(escalada["ancho"] == 2560))
print("vertical_no_cero", int(vertical["lock_tarjeta_w"] > 0))
print("legible", int(laptop["lock_reloj"] >= 20))
print("velo_proporcional", int(abs(laptop["paper_velo"] / 768 - base["paper_velo"] / 1080) < 0.01))
PY
leer() { grep "^$1 " "$TMP/escalas.txt" | cut -d' ' -f2; }
afirmar_igual "1.0" "$(leer base_factor)" "en 1920x1080 el factor es 1 (no cambia nada)"
afirmar_igual "1" "$(leer laptop_menor)" "en 1366x768 el reloj encoge"
afirmar_igual "1" "$(leer 4k_mayor)" "en 4K el reloj crece"
afirmar_igual "1" "$(leer escala_cuenta)" "una 4K con escala 1.5 se mide como 2560 logicos"
afirmar_igual "1" "$(leer vertical_no_cero)" "una pantalla vertical no da medidas en cero"
afirmar_igual "1" "$(leer legible)" "por pequena que sea la pantalla, el reloj sigue legible"
afirmar_igual "1" "$(leer velo_proporcional)" "el velo del selector ocupa la misma proporcion de pantalla"

titulo "4. No toco nada de tu equipo"
afirmar_intacta_la_casa_real

resumen
