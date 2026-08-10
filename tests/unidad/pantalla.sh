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
# El codigo de salida se guarda EN LA MISMA LINEA y se compara aparte. Antes
# esto era `afirmar "no revienta" test $? -eq 0` puesto detras de otro
# `afirmar`, o sea que medía el codigo del afirmar anterior y no el de
# pantalla.py; y como el `2>&1` mete el traceback dentro de la variable, la otra
# comprobacion —«responde algo»— salia en verde PRECISAMENTE porque reventaba.
# Asi se colo un KeyError que vivio dos sesiones con las pruebas en verde.
salida="$("$PANTALLA" 2>&1)"; codigo=$?
afirmar "responde algo aunque no haya compositor" test -n "$salida"
afirmar_igual "0" "$codigo" "no se cuelga ni revienta"
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
afirmar_igual "18" "$cuantas" "define 18 medidas"
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
print("vertical_no_cero", int(vertical["lock_banda_w"] > 0))
print("legible", int(laptop["lock_reloj"] >= 20))
print("velo_proporcional", int(abs(laptop["paper_velo"] / 768 - base["paper_velo"] / 1080) < 0.01))

# La banda del bloqueo y el desplazamiento que centra el titulo dentro de ella.
#
# `px()` tiene un SUELO (FACTOR_MIN), asi que en una pantalla estrecha devuelve
# mas ancho del que cabe. Medido en el Hyprland anidado con una salida de 351px:
# la banda salia de 409 —se comia la pantalla— y lock_col_centro se volvia
# POSITIVO, o sea que el titulo se iba a la derecha en vez de centrarse en la
# columna. Y no falla nada: se dibuja igual, solo que al reves.
minusculo = p.medidas(mon(351, 453))
anchos = {"base": (base, 1920), "laptop": (laptop, 1366),
          "4k": (cuatrok, 3840), "vertical": (vertical, 1080),
          "minusculo": (minusculo, 351)}
print("banda_cabe", int(all(m["lock_banda_w"] < w for m, w in anchos.values())))
print("centro_negativo", int(all(m["lock_col_centro"] < 0 for m, _ in anchos.values())))
# El borde derecho de la banda va SIEMPRE dos pixeles antes de su final: es un
# shape aparte porque hyprlang no sabe restar.
print("borde_pegado", int(all(m["lock_banda_borde_x"] == m["lock_banda_w"] - 2
                              for m, _ in anchos.values())))
# Y la columna tiene que empezar dentro de la banda, no fuera.
print("columna_dentro", int(all(0 < m["lock_col_x"] < m["lock_banda_w"]
                                for m, _ in anchos.values())))
PY
leer() { grep "^$1 " "$TMP/escalas.txt" | cut -d' ' -f2; }
afirmar_igual "1.0" "$(leer base_factor)" "en 1920x1080 el factor es 1 (no cambia nada)"
afirmar_igual "1" "$(leer laptop_menor)" "en 1366x768 el reloj encoge"
afirmar_igual "1" "$(leer 4k_mayor)" "en 4K el reloj crece"
afirmar_igual "1" "$(leer escala_cuenta)" "una 4K con escala 1.5 se mide como 2560 logicos"
afirmar_igual "1" "$(leer vertical_no_cero)" "una pantalla vertical no da medidas en cero"
afirmar_igual "1" "$(leer legible)" "por pequena que sea la pantalla, el reloj sigue legible"
afirmar_igual "1" "$(leer velo_proporcional)" "el velo del selector ocupa la misma proporcion de pantalla"
afirmar_igual "1" "$(leer banda_cabe)" "la banda del bloqueo cabe en la pantalla, por estrecha que sea"
afirmar_igual "1" "$(leer centro_negativo)" "el titulo se centra en la banda, nunca se va a la derecha"
afirmar_igual "1" "$(leer borde_pegado)" "el filo va pegado al borde derecho de la banda"
afirmar_igual "1" "$(leer columna_dentro)" "la columna empieza dentro de la banda"

titulo "4. El resumen que ensena instalar.sh"
# Las secciones de arriba miden `medidas()`, que es la parte que usa el
# escritorio. Nadie ejecutaba la CLI, y ahi vive el otro consumidor de esas
# claves: el resumen las pide UNA A UNA por su nombre. Cuando la tarjeta del
# bloqueo paso a ser columna, `lock_tarjeta_w` dejo de generarse y el resumen
# siguio pidiendola: KeyError, seccion 7 de `instalar.sh --revisar` cortada a la
# mitad, y «sin pendientes» al final. Con 18 pruebas en verde.
"$PANTALLA" > "$TMP/resumen.txt" 2> "$TMP/resumen-err.txt"; codigo=$?
afirmar_igual "0" "$codigo" "el resumen sale con codigo 0"
afirmar "no deja nada en stderr" test ! -s "$TMP/resumen-err.txt"
afirmar_no_contiene "$TMP/resumen-err.txt" 'Traceback' "no suelta un traceback"
afirmar_contiene "$TMP/resumen.txt" 'PANTALLA' "ensena la cabecera"
afirmar_contiene "$TMP/resumen.txt" 'De ahi salen' "ensena las medidas que salen de ahi"
afirmar_contiene "$TMP/resumen.txt" '^ +bloqueo ' "ensena la linea del bloqueo"
afirmar_contiene "$TMP/resumen.txt" '^ +fondos ' "ensena la linea del selector de fondos"
# El cerrojo de verdad: `_medida()` degrada a «?» para que a quien clone el repo
# no se le lleve por delante toda la seccion, pero aqui un «?» es un fallo. Sin
# esto, renombrar una medida volveria a pasar desapercibido — solo que en vez de
# reventar, mentiria mas bajito.
afirmar_no_contiene "$TMP/resumen.txt" '\?' "ninguna medida del resumen se ha quedado sin generar"

titulo "5. No toco nada de tu equipo"
afirmar_intacta_la_casa_real

resumen
