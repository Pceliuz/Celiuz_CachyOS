#!/usr/bin/env bash
# tests/unidad/monitores.sh — que cada pantalla reciba el refresco mas alto de su
# resolucion nativa, y que eso no pise nunca lo que hayas puesto tu.
#
# QUE VIGILA
# ----------
# Hyprland no sabe hacer esto solo. Sus cuatro palabras para el modo de un
# monitor no se pueden combinar (lo dice el wiki: «Predefined modes cannot be
# combined»), y ninguna pide lo que uno quiere:
#
#   preferred  el del EDID — un monitor de 100 Hz suele declarar 60.
#   highrr     el refresco mas alto MIRANDO SOLO EL REFRESCO.
#   highres    la resolucion mas alta, con el refresco sin especificar.
#   maxwidth   la mas ancha, igual.
#
# `highrr` es una trampa medida, no una hipotesis: el televisor de las pruebas
# (2026-08-13) anuncia 800x600@60.32, que tiene MAS refresco que su
# 1920x1080@60.00, asi que lo dejaba en 800x600. Por eso el orden de los dos
# criterios —resolucion primero, refresco despues— es el corazon de esto y tiene
# su propia comprobacion aqui abajo: al reves, la prueba cae.
#
# Y vigila lo contrario con el mismo cuidado: que un script que ajusta pantallas
# solo NO se lleve por delante la linea que pusiste a mano. En este repo el
# orden de capas es sagrado —conf/personal.conf se carga el ultimo y gana—, asi
# que una salida nombrada ahi se salta entera.
#
# COMO SE PRUEBA SIN PANTALLAS (ni sesion). Todo lo que decide vive en cuatro
# funciones que solo hablan con Hyprland por `query()`. Se importa el modulo y se
# sustituye `query()` por una que devuelve el JSON de un escritorio inventado y
# que ADEMAS APUNTA los `keyword monitor` que se le mandan — asi se comprueba no
# solo que elige bien, sino que no manda nada cuando no hace falta.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

COPIA="$(copiar_repo)"
SCRIPT="$COPIA/hypr/scripts/monitores.py"

trap 'limpiar_entorno' EXIT INT TERM

RES="$TMP/resultados"

python3 - "$SCRIPT" "$COPIA" > "$RES" 2>"$TMP/py.err" <<'PYEOF'
import importlib.util
import json
import os
import sys

ruta, copia = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("monitores", ruta)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# --- El escritorio inventado --------------------------------------------------
#
# El monitor de la PC: 100 Hz de verdad, pero su EDID declara 60 como preferido,
# que es exactamente el caso por el que existe todo esto.
PC = {"name": "HDMI-A-1", "x": 0, "y": 0, "width": 1920, "height": 1080,
      "refreshRate": 60.0, "scale": 1.0,
      "availableModes": ["1920x1080@100.00Hz", "1920x1080@60.00Hz",
                         "1680x1050@60.00Hz", "1280x720@60.00Hz"]}

# El televisor, con su 800x600 de mas refresco: la trampa de `highrr`.
TELE = {"name": "HDMI-A-1", "x": 1366, "y": 0, "width": 1920, "height": 1080,
        "refreshRate": 60.0, "scale": 1.5,
        "availableModes": ["1920x1080@60.00Hz", "800x600@60.32Hz",
                           "1280x720@59.94Hz"]}

# La laptop: un solo modo. Aqui no hay nada que hacer, y hacer algo seria el
# fallo (relanzar un modo identico en cada evento).
LAPTOP = {"name": "eDP-1", "x": 0, "y": 0, "width": 1366, "height": 768,
          "refreshRate": 59.973, "scale": 1.0,
          "availableModes": ["1366x768@59.97Hz"]}

# Una salida que no anuncia ningun modo legible: no se toca, no se revienta.
MUDA = {"name": "DP-3", "x": 0, "y": 0, "width": 1024, "height": 768,
        "refreshRate": 60.0, "scale": 1.0, "availableModes": []}

estado = {"monitores": [], "ordenes": []}


def query_falso(cmd):
    if cmd == "j/monitors":
        return json.dumps(estado["monitores"])
    if cmd.startswith("keyword monitor "):
        estado["ordenes"].append(cmd[len("keyword monitor "):])
        return "ok"
    return ""


mod.query = query_falso


def di(clave, valor):
    print("%s=%s" % (clave, valor))


def escribir_personal(texto):
    with open(copia + "/hypr/conf/personal.conf", "w", encoding="utf-8") as fh:
        fh.write(texto)


def correr(monitores, personal=""):
    """Monta el escritorio, vacia el registro y aplica. Devuelve las ordenes."""
    estado["monitores"] = monitores
    estado["ordenes"] = []
    escribir_personal(personal)
    mod.aplicar(raiz=copia)
    return estado["ordenes"]


# --- 1. La eleccion del modo, que es donde vivia la trampa --------------------
di("pc_mejor", mod.mejor_modo(mod.parsear_modos(PC["availableModes"])))
di("tele_mejor", mod.mejor_modo(mod.parsear_modos(TELE["availableModes"])))
di("laptop_mejor", mod.mejor_modo(mod.parsear_modos(LAPTOP["availableModes"])))
di("muda_mejor", mod.mejor_modo(mod.parsear_modos(MUDA["availableModes"])))

# Lo que habria elegido `highrr`: el refresco mas alto sin mirar la resolucion.
peor = max(mod.parsear_modos(TELE["availableModes"]), key=lambda m: m[2])
di("tele_highrr", "%dx%d" % (peor[0], peor[1]))

# Modos con basura por medio: se ignora lo que no se entiende, no tumba al resto.
di("sucio_mejor", mod.mejor_modo(mod.parsear_modos(
    ["1920x1080@100.00Hz", "esto no es un modo", "", "1920x1080"])))

# --- 2. Que se le manda al compositor -----------------------------------------
ordenes = correr([PC])
di("pc_ordenes", len(ordenes))
di("pc_linea", ordenes[0] if ordenes else "")

# El televisor: se le sube el refresco... a nada, porque 60 ya es su maximo a
# 1920x1080. No se manda ninguna orden.
di("tele_ordenes", len(correr([TELE])))

# La laptop, un solo modo: ni una orden.
di("laptop_ordenes", len(correr([LAPTOP])))

# La salida muda: ni una orden, y sin reventar.
di("muda_ordenes", len(correr([MUDA])))

# --- 3. Se conservan sitio y escala -------------------------------------------
# El televisor a escala 1.5 y en 1366x0, pero con 100 Hz disponibles: la orden
# tiene que llevar SU posicion y SU escala, no un 0x0 y un 1 inventados. Es el
# fallo del que salio todo esto (una linea que clavaba la posicion ajena).
TELE_100 = dict(TELE, availableModes=["1920x1080@100.00Hz", "1920x1080@60.00Hz",
                                      "800x600@60.32Hz"])
ordenes = correr([TELE_100])
di("escala_linea", ordenes[0] if ordenes else "")

# --- 4. Lo que pones tu gana --------------------------------------------------
# Esa misma pantalla, pero nombrada en personal.conf: no se toca.
di("fijada_ordenes", len(correr([PC], "monitor = HDMI-A-1, preferred, 0x0, 1\n")))

# La generica de monitors.conf NO fija ninguna salida, asi que no bloquea nada.
di("generica_ordenes", len(correr([PC], "monitor = , preferred, auto-right, 1\n")))

# Un comentario que mencione una salida tampoco la fija.
di("comentada_ordenes", len(correr([PC], "# monitor = HDMI-A-1, preferred\n")))

# Con dos pantallas y una fijada, la otra si se ajusta.
dos = [dict(PC, name="DP-1"), dict(PC, name="HDMI-A-1", x=1920)]
ordenes = correr(dos, "monitor = DP-1, preferred, 0x0, 1\n")
di("mixta_ordenes", len(ordenes))
di("mixta_cual", ordenes[0].split(",")[0] if ordenes else "")

# Sin fichero personal.conf ninguno, no falla: no hay nada fijado.
os.remove(copia + "/hypr/conf/personal.conf")
estado["monitores"] = [PC]
estado["ordenes"] = []
mod.aplicar(raiz=copia)
di("sin_personal_ordenes", len(estado["ordenes"]))

# --- 5. Lo que NO se hace -----------------------------------------------------
# Una pantalla puesta a una resolucion que no es la mayor que anuncia: se avisa
# y se deja. Cambiar de resolucion a ciegas no es lo que vino a hacer esto.
BAJA = dict(PC, width=1280, height=720, refreshRate=60.0)
estado["monitores"] = [BAJA]
estado["ordenes"] = []
filas = mod.revisar(raiz=copia)
di("baja_motivo", "si" if filas and filas[0][3] and "resolucion" in filas[0][3] else "no")
mod.aplicar(raiz=copia)
di("baja_ordenes", len(estado["ordenes"]))

# Sin sesion (query devuelve vacio) no se inventa nada.
mod.query = lambda cmd: ""
di("sin_sesion", len(mod.revisar(raiz=copia)))
PYEOF

if [ -s "$TMP/py.err" ]; then
    _gris "    stderr de python:"
    sed 's/^/      /' "$TMP/py.err"
fi
afirmar "el guion no escribe nada en stderr" test ! -s "$TMP/py.err"

valor() { sed -n "s/^$1=//p" "$RES"; }


titulo "1. Elegir el modo: resolucion primero, refresco despues"
afirmar_igual "(1920, 1080, 100.0)" "$(valor pc_mejor)" \
        "el monitor de 100 Hz que declara 60: se le ven los 100"
afirmar_igual "(1920, 1080, 60.0)" "$(valor tele_mejor)" \
        "el televisor se queda en 1080p, NO en su 800x600 de mas refresco"
afirmar_igual "800x600" "$(valor tele_highrr)" \
        "(y eso es justo lo que habria elegido «highrr»: la trampa medida)"
afirmar_igual "(1366, 768, 59.97)" "$(valor laptop_mejor)" \
        "con un solo modo, ese es el mejor"
afirmar_igual "None" "$(valor muda_mejor)" \
        "sin modos legibles no se inventa ninguno"
afirmar_igual "(1920, 1080, 100.0)" "$(valor sucio_mejor)" \
        "la basura entre los modos se ignora, no tumba la eleccion"


titulo "2. Solo se habla con el compositor cuando hace falta"
afirmar_igual "1" "$(valor pc_ordenes)" "la PC recibe una orden"
afirmar_igual "HDMI-A-1,1920x1080@100,0x0,1" "$(valor pc_linea)" \
        "y lleva el modo bueno, con su sitio y su escala"
afirmar_igual "0" "$(valor tele_ordenes)" \
        "el televisor ya esta en su mejor modo: ni una orden"
afirmar_igual "0" "$(valor laptop_ordenes)" \
        "la laptop tiene un solo modo: ni una orden"
afirmar_igual "0" "$(valor muda_ordenes)" \
        "una salida que no anuncia modos no se toca"


titulo "3. Se conservan la posicion y la escala"
afirmar_igual "HDMI-A-1,1920x1080@100,1366x0,1.5" "$(valor escala_linea)" \
        "la orden lleva SU sitio y SU escala, no un 0x0 y un 1 inventados"


titulo "4. Lo que pones en personal.conf gana siempre"
afirmar_igual "0" "$(valor fijada_ordenes)" \
        "una salida que nombras tu no se toca"
afirmar_igual "1" "$(valor generica_ordenes)" \
        "la generica «monitor = , preferred» no fija nada y no bloquea"
afirmar_igual "1" "$(valor comentada_ordenes)" \
        "una salida solo mencionada en un comentario tampoco fija nada"
afirmar_igual "1" "$(valor mixta_ordenes)" \
        "con una fijada y otra libre, se ajusta solo la libre"
afirmar_igual "HDMI-A-1" "$(valor mixta_cual)" "y es la que no estaba fijada"
afirmar_igual "1" "$(valor sin_personal_ordenes)" \
        "sin personal.conf no hay nada fijado, y no falla"


titulo "5. Lo que a proposito NO hace"
afirmar_igual "si" "$(valor baja_motivo)" \
        "una pantalla por debajo de su resolucion mayor: lo dice"
afirmar_igual "0" "$(valor baja_ordenes)" \
        "pero no le cambia la resolucion a ciegas"
afirmar_igual "0" "$(valor sin_sesion)" \
        "sin sesion de Hyprland no se inventa ninguna pantalla"


titulo "6. No toco nada de tu equipo"
afirmar_intacta_la_casa_real

resumen
