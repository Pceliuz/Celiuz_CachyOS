#!/usr/bin/env bash
# tests/unidad/barras-multipantalla.sh — con dos pantallas, las barras no pueden
# quedarse invertidas ni medir las zonas de raton contra el monitor que no es.
#
# EL FALLO QUE VIGILA (2026-08-13, al conectar un televisor por HDMI a la
# laptop). waybar dibuja UNA SUPERFICIE POR SALIDA, pero waybar-autohide.py
# estaba escrito como si solo hubiera una pantalla, en tres sitios a la vez:
#
#   1. `layer_levels()` devolvia `{namespace: nivel}` y lo escribia dentro del
#      bucle de monitores, asi que con dos salidas GANABA LA ULTIMA y las demas
#      ni se miraban. Como waybar solo ofrece el toggle (SIGUSR1) y lo aplica a
#      todas sus superficies a la vez, dos superficies en niveles distintos ya
#      no se pueden juntar con senales: la senal mueve las dos y CONSERVA el
#      desfase. Es la trampa del "toggle perdido" del 2026-08-01, pero entre
#      monitores. Lo medido: barra y dock puestos en la laptop y escondidos en
#      el televisor, para siempre.
#   2. `SCREEN_W/SCREEN_H` se median UNA vez al arrancar el modulo, del monitor
#      enfocado. La franja del dock (`y >= SCREEN_H - 90`) salia a 678 con el
#      alto de la laptop, o sea una banda de 400 px A MEDIA PANTALLA del
#      televisor que abria el dock sola — y su borde de abajo de verdad, a
#      1080, no lo abria nunca.
#   3. `dock_geometry()` devolvia la PRIMERA capa `waybar-dock` que encontrara,
#      de la pantalla que fuera, y sus coordenadas son globales. Con el dock del
#      televisor centrado en x=2039 y el de la laptop en x=396, la zona sensible
#      caia entera en una sola de las dos.
#
# COMO SE PRUEBA SIN DOS PANTALLAS (ni una). Las cuatro funciones que deciden
# esto —monitor_en, in_top_zone, in_dock_zone, layer_levels— solo hablan con
# Hyprland por `query()`. Se importa el modulo y se sustituye `query()` por una
# que devuelve las dos respuestas JSON de un escritorio de dos pantallas. Asi se
# prueba la aritmetica de verdad, que es donde vivia el fallo, sin compositor y
# sin tocar la sesion de nadie.
#
# Las medidas son las del caso real: laptop 1366x768 en 0x0 y televisor
# 1920x1080 a su derecha, en 1366x0. Un escritorio de dos pantallas es UN plano,
# asi que el cursor sobre el televisor viene con x >= 1366.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

COPIA="$(copiar_repo)"
DEMONIO="$COPIA/hypr/scripts/waybar-autohide.py"

# `SOCKET = hypr_socket()` corre al importar y se planta si no encuentra ninguna
# instancia. La carpeta vacia le basta: aqui no se habla con el socket, se
# sustituye `query()` entera.
mkdir -p "$XDG_RUNTIME_DIR/hypr/prueba-multipantalla"

trap 'limpiar_entorno' EXIT INT TERM

RES="$TMP/resultados"

# El guion de python escribe una linea `clave=valor` por comprobacion, y luego
# cada afirmacion de bash lee la suya. Se importa una sola vez.
python3 - "$DEMONIO" > "$RES" 2>"$TMP/py.err" <<'PYEOF'
import importlib.util
import json
import sys

ruta = sys.argv[1]
spec = importlib.util.spec_from_file_location("autohide", ruta)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

LAPTOP = {"name": "eDP-1", "x": 0, "y": 0,
          "width": 1366, "height": 768, "scale": 1.0}
TELE = {"name": "HDMI-A-1", "x": 1366, "y": 0,
        "width": 1920, "height": 1080, "scale": 1.0}


def capa(ns, x, y, w, h):
    return {"namespace": ns, "x": x, "y": y, "w": w, "h": h}


# Niveles: 2 = top (barra puesta), 1 = bottom (escondida).
def escritorio(nivel_laptop, nivel_tele):
    """Las cuatro capas en cada pantalla, con el dock centrado en la suya."""
    def lado(mon, nivel):
        # El dock mide 574x88 y va centrado abajo; el tirador 180x10.
        cx = mon["x"] + (mon["width"] - 574) // 2
        tx = mon["x"] + (mon["width"] - 180) // 2
        abajo = mon["y"] + mon["height"]
        otro = 1 if nivel == 2 else 2
        niveles = {"0": [], "1": [], "2": [], "3": []}
        niveles[str(nivel)] = [
            capa("waybar-main", mon["x"], mon["y"], mon["width"], 44),
            capa("waybar-dock", cx, abajo - 88, 574, 88),
        ]
        niveles[str(otro)] = [
            capa("waybar-trigger", tx, mon["y"], 180, 10),
            capa("waybar-dock-trigger", tx, abajo - 10, 180, 10),
        ]
        return {"levels": niveles}

    return {"eDP-1": lado(LAPTOP, nivel_laptop),
            "HDMI-A-1": lado(TELE, nivel_tele)}


estado = {"monitores": [LAPTOP, TELE], "capas": escritorio(2, 2)}


def query_falso(cmd):
    if cmd == "j/monitors":
        return json.dumps(estado["monitores"])
    if cmd == "j/layers":
        return json.dumps(estado["capas"])
    return ""


mod.query = query_falso


def olvidar_cache():
    """Las dos consultas se recuerdan GEO_REFRESH segundos; entre escenarios no."""
    mod._monitores["t"] = -1e9
    mod._dock_geo["t"] = -1e9


def di(clave, valor):
    print("%s=%s" % (clave, valor))


olvidar_cache()

# --- Que pantalla contiene cada punto -------------------------------------
di("mon_laptop", mod.monitor_en(200, 400)["x"])
di("mon_tele", mod.monitor_en(2000, 400)["x"])
# El borde exacto pertenece ya al televisor: la laptop ocupa 0..1365.
di("mon_borde", mod.monitor_en(1366, 400)["x"])
# Un punto fuera de todo (una pantalla recien desenchufada) cae en la primera,
# no revienta.
di("mon_fuera", mod.monitor_en(9999, 9999)["x"])

# --- La franja de arriba, en cada pantalla --------------------------------
di("arriba_laptop", mod.in_top_zone(200, 10))
di("arriba_tele", mod.in_top_zone(2000, 10))
di("medio_tele", mod.in_top_zone(2000, 700))

# --- La zona del dock, que es la que se iba de pantalla --------------------
# El dock de la laptop esta centrado en x=396..970, y=680.
di("dock_laptop", mod.in_dock_zone(600, 700))
# El del televisor, en x=2039..2613, y=992. Este es el que no se abria.
di("dock_tele", mod.in_dock_zone(2300, 1000))
# Y a media altura del televisor NO hay dock. Con el alto global de la laptop
# (768-90=678) esto daba True: una banda enorme que lo abria sola.
di("dock_medio_tele", mod.in_dock_zone(2300, 700))
# Abajo del todo pero en el lado equivocado del televisor: fuera del dock.
di("dock_esquina_tele", mod.in_dock_zone(1500, 1070))

# Sin datos de capas se cae a la franja de abajo DE SU PANTALLA.
estado["capas"] = {}
olvidar_cache()
di("reserva_tele_abajo", mod.in_dock_zone(2300, 1050))
di("reserva_tele_medio", mod.in_dock_zone(2300, 700))
di("reserva_laptop_abajo", mod.in_dock_zone(600, 740))
estado["capas"] = escritorio(2, 2)
olvidar_cache()

# --- Los niveles: una lista por namespace, no un numero --------------------
capas = mod.layer_levels()
di("niveles_main_alineados", ",".join(str(n) for n in sorted(capas["waybar-main"])))

# Barra puesta en la laptop y escondida en el televisor: EL DESFASE.
estado["capas"] = escritorio(2, 1)
olvidar_cache()
capas_desfase = mod.layer_levels()
di("niveles_main_desfase",
   ",".join(str(n) for n in sorted(capas_desfase["waybar-main"])))

# --- Bar.desalineada() y su freno -----------------------------------------
# Se construye sin __init__ a proposito: __init__ lanza cuatro waybar de verdad
# y aqui solo se prueba aritmetica sobre un diccionario.
bar = mod.Bar.__new__(mod.Bar)
bar.namespace = "waybar-main"
bar.trigger_namespace = "waybar-trigger"
bar.realineado_en = -mod.REALINEO_ESPERA

di("desalineada_con_desfase", bar.desalineada(capas_desfase))
di("desalineada_alineadas", bar.desalineada(capas))
# Una barra que aun no tiene superficie no es un desfase, es que no esta.
di("desalineada_sin_capas", bar.desalineada({}))

# El freno: relanzar cuesta, y sin el se llamaria a 10 Hz mientras dure el
# desfase. Se cuenta cuantas veces se relanzaria de verdad.
relanzados = {"n": 0}
bar.reload = lambda: relanzados.__setitem__("n", relanzados["n"] + 1)
for _ in range(30):
    bar.realinear()
di("realineos_en_rafaga", relanzados["n"])

# Pasado el tiempo de espera, vuelve a poder intentarlo.
bar.realineado_en -= mod.REALINEO_ESPERA + 1
bar.realinear()
di("realineos_tras_esperar", relanzados["n"])

# --- Y con UNA sola pantalla todo sigue igual que siempre ------------------
estado["monitores"] = [LAPTOP]
estado["capas"] = {"eDP-1": escritorio(2, 2)["eDP-1"]}
olvidar_cache()
di("solo_una_arriba", mod.in_top_zone(200, 10))
di("solo_una_dock", mod.in_dock_zone(600, 700))
di("solo_una_fuera_dock", mod.in_dock_zone(100, 400))
una = mod.layer_levels()
di("solo_una_niveles", ",".join(str(n) for n in sorted(una["waybar-main"])))
bar.realineado_en = -mod.REALINEO_ESPERA
di("solo_una_desalineada", bar.desalineada(una))
PYEOF

# Un traceback a medias dejaria el fichero con las primeras claves y las
# afirmaciones siguientes fallarian sin decir por que. Se exige stderr vacio,
# que es la leccion del 2026-08-10 con pantalla.py.
if [ -s "$TMP/py.err" ]; then
    _gris "    stderr de python:"
    sed 's/^/      /' "$TMP/py.err"
fi
afirmar "el guion no escribe nada en stderr" test ! -s "$TMP/py.err"

# valor <clave> — lee una clave del volcado.
valor() { sed -n "s/^$1=//p" "$RES"; }


titulo "1. Cada punto del escritorio sabe de que pantalla es"
afirmar_igual "0" "$(valor mon_laptop)" "un punto de la izquierda es de la laptop"
afirmar_igual "1366" "$(valor mon_tele)" "uno de la derecha es del televisor"
afirmar_igual "1366" "$(valor mon_borde)" "el borde justo ya es del televisor"
afirmar_igual "0" "$(valor mon_fuera)" "un punto de ninguna cae en la primera, sin reventar"


titulo "2. Las zonas de raton se miden contra SU pantalla"
afirmar_igual "True" "$(valor arriba_laptop)" "el borde de arriba de la laptop abre la barra"
afirmar_igual "True" "$(valor arriba_tele)" "y el del televisor tambien"
afirmar_igual "False" "$(valor medio_tele)" "media pantalla del televisor no es el borde"

afirmar_igual "True" "$(valor dock_laptop)" "el dock de la laptop se abre desde su borde"
afirmar_igual "True" "$(valor dock_tele)" "el del televisor se abre desde el suyo"
# Esta es LA comprobacion del fallo 2: con el alto global daba True.
afirmar_igual "False" "$(valor dock_medio_tele)" \
        "a media altura del televisor NO hay dock (era una banda de 400 px)"
afirmar_igual "False" "$(valor dock_esquina_tele)" \
        "abajo pero lejos del dock del televisor, tampoco"


titulo "3. Sin datos de capas, la franja de reserva tambien es la de su pantalla"
afirmar_igual "True" "$(valor reserva_tele_abajo)" "el borde de abajo del televisor"
afirmar_igual "False" "$(valor reserva_tele_medio)" "pero no media pantalla"
afirmar_igual "True" "$(valor reserva_laptop_abajo)" "y el borde de abajo de la laptop"


titulo "4. Los niveles se guardan TODOS, no solo el ultimo monitor"
afirmar_igual "2,2" "$(valor niveles_main_alineados)" \
        "dos pantallas alineadas dan dos niveles iguales"
afirmar_igual "1,2" "$(valor niveles_main_desfase)" \
        "y desfasadas dan los dos, no uno solo (era lo que se perdia)"


titulo "5. El desfase se ve, y corregirlo tiene freno"
afirmar_igual "True" "$(valor desalineada_con_desfase)" \
        "puesta en una pantalla y escondida en la otra: desalineada"
afirmar_igual "False" "$(valor desalineada_alineadas)" "las dos igual: no lo esta"
afirmar_igual "False" "$(valor desalineada_sin_capas)" \
        "y sin superficies no es un desfase, es que aun no nacio"
afirmar_igual "1" "$(valor realineos_en_rafaga)" \
        "treinta ciclos seguidos relanzan UNA vez, no treinta"
afirmar_igual "2" "$(valor realineos_tras_esperar)" \
        "pasada la espera vuelve a intentarlo"


titulo "6. Con una sola pantalla no cambia nada"
afirmar_igual "True" "$(valor solo_una_arriba)" "la franja de arriba sigue"
afirmar_igual "True" "$(valor solo_una_dock)" "el dock sigue"
afirmar_igual "False" "$(valor solo_una_fuera_dock)" "y lejos de el, sigue sin abrirse"
afirmar_igual "2" "$(valor solo_una_niveles)" "un solo nivel, como siempre"
afirmar_igual "False" "$(valor solo_una_desalineada)" "y nunca esta desalineada"


titulo "7. No toco nada de tu equipo"
afirmar_intacta_la_casa_real

resumen
