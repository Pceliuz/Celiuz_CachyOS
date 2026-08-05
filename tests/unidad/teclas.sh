#!/usr/bin/env bash
# tests/unidad/teclas.sh — lib/teclas.py, el que dice si SUPER sigue pulsada.
#
# LO QUE SE VIGILA AQUI ES UN FALLO DE PORTABILIDAD, no la lectura del teclado.
#
# Leer /dev/input pide estar en el grupo `input`. En la maquina del autor se
# puede; en otra, o en integracion continua, puede que no. Si en ese caso el
# modulo devolviera False —"SUPER no esta pulsada"— el cambiador de escritorios
# entenderia que ya la has soltado y **se cerraria solo nada mas abrirse**: el
# gesto entero, roto, y sin ningun mensaje de error. Por eso devuelve None
# cuando no ha podido mirar, y por eso eso es lo primero que se comprueba.
#
# La otra mitad es la aritmetica de bits, que es lo mas facil de equivocar del
# modulo y ademas lo unico que se puede comprobar sin un teclado de verdad: el
# mapa del kernel viene por bytes y cada tecla es un bit dentro de uno.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

python3 - "$REPO" > "$TMP/salida.txt" 2>"$TMP/error.txt" <<'PY'
import sys, os
sys.path.insert(0, os.path.join(sys.argv[1], "hypr", "scripts", "lib"))
import teclas

r = {}

# --- La aritmetica de bits ---------------------------------------------------
vacio = bytearray(16)
r["vacio_nada"] = not any(teclas.bit(vacio, k) for k in range(128))

izq = bytearray(16)
izq[teclas.KEY_LEFTMETA // 8] |= 1 << (teclas.KEY_LEFTMETA % 8)
r["izq_si"] = teclas.bit(izq, teclas.KEY_LEFTMETA)
# La 125 y la 126 son bits VECINOS del mismo byte: si la mascara estuviera mal
# calculada, encender una encenderia la otra y no se notaria nunca.
r["izq_no_contagia"] = not teclas.bit(izq, teclas.KEY_RIGHTMETA)

der = bytearray(16)
der[teclas.KEY_RIGHTMETA // 8] |= 1 << (teclas.KEY_RIGHTMETA % 8)
r["der_si"] = teclas.bit(der, teclas.KEY_RIGHTMETA)
r["der_no_contagia"] = not teclas.bit(der, teclas.KEY_LEFTMETA)

# Fuera del mapa NO puede reventar: seria un IndexError en mitad del gesto.
r["fuera_no_revienta"] = teclas.bit(vacio, 5000) is False

# --- Lo importante: None no es False -----------------------------------------
# Sin ningun teclado a la vista, la respuesta es "no lo se", nunca "no pulsada".
teclas._teclados = []
r["sin_teclados_es_none"] = teclas.pulsada(teclas.KEY_LEFTMETA) is None
r["sin_teclados_super_none"] = teclas.super_pulsada() is None

# Y con un dispositivo que no se puede abrir, igual: no se pudo mirar.
teclas._teclados = ["/dev/input/no-existe-de-verdad"]
r["ilegible_es_none"] = teclas.super_pulsada() is None

# --- super_pulsada mira LAS DOS teclas ---------------------------------------
# El X820 no trae SUPER derecha, pero otro teclado si, y con el diseño de
# "sueltas SUPER y entras" mirar solo una dejaria el gesto a medias en ese
# equipo. Se comprueba interceptando la llamada, sin tocar /dev/input.
vistos = []
original = teclas.pulsada
teclas.pulsada = lambda *c: vistos.extend(c)
teclas.super_pulsada()
teclas.pulsada = original
r["mira_las_dos"] = (teclas.KEY_LEFTMETA in vistos
                     and teclas.KEY_RIGHTMETA in vistos)

# --- teclados() no repite ----------------------------------------------------
# Un mismo teclado trae varios enlaces by-path; si se colaran repetidos se
# abriria el mismo dispositivo tres veces por consulta, y esto se llama cada
# 30 ms mientras el gesto esta abierto.
teclas._teclados = None
lista = teclas.teclados()
r["sin_repetidos"] = len(lista) == len(set(lista))
r["todos_absolutos"] = all(p.startswith("/") for p in lista)

for k, v in r.items():
    print(f"{k}={1 if v else 0}")
PY

leer() { grep -m1 "^$1=" "$TMP/salida.txt" 2>/dev/null | cut -d= -f2; }

afirmar "el modulo se importa sin quejarse" test ! -s "$TMP/error.txt"

titulo "1. La aritmetica de bits del mapa del kernel"
afirmar_igual "1" "$(leer vacio_nada)"        "un mapa vacio no da ninguna tecla pulsada"
afirmar_igual "1" "$(leer izq_si)"            "reconoce la SUPER izquierda"
afirmar_igual "1" "$(leer der_si)"            "reconoce la SUPER derecha"
afirmar_igual "1" "$(leer izq_no_contagia)"   "la izquierda no enciende a su vecina de bit"
afirmar_igual "1" "$(leer der_no_contagia)"   "la derecha no enciende a su vecina de bit"
afirmar_igual "1" "$(leer fuera_no_revienta)" "una tecla fuera del mapa no revienta"

titulo "2. «No lo se» NUNCA se confunde con «no esta pulsada»"
afirmar_igual "1" "$(leer sin_teclados_es_none)"   "sin teclados devuelve None, no False"
afirmar_igual "1" "$(leer sin_teclados_super_none)" "y super_pulsada() tambien"
afirmar_igual "1" "$(leer ilegible_es_none)"       "un dispositivo ilegible devuelve None"

titulo "3. Las dos SUPER, y sin abrir nada dos veces"
afirmar_igual "1" "$(leer mira_las_dos)"     "super_pulsada() mira la izquierda Y la derecha"
afirmar_igual "1" "$(leer sin_repetidos)"    "teclados() no devuelve el mismo dos veces"
afirmar_igual "1" "$(leer todos_absolutos)"  "teclados() devuelve rutas resueltas"

titulo "4. No toco nada de tu equipo"
afirmar_intacta_la_casa_real

resumen
