#!/usr/bin/env bash
# tests/unidad/barras-por-pantalla.sh — con dos pantallas, cada una lleva SUS
# barras y decide por su cuenta (2026-11-02).
#
# POR QUE EXISTE ESTA PRUEBA
# --------------------------
# Habia una waybar para todas las pantallas y el demonio decidia por el
# escritorio con el FOCO: el usuario saltaba a un escritorio vacio en una
# pantalla para ver el fondo, y las barras salian tambien encima de las apps
# de la otra. Con una sola waybar no habia arreglo: su toggle mueve todas sus
# superficies a la vez. Lo que se vigila:
#
#   1. una pareja de waybar POR PANTALLA, cada una con "output" (una config
#      minima en el runtime que incluye la del repo), y se quitan las de una
#      pantalla que se desenchufa;
#   2. cada barra decide con las ventanas y las capas de SU pantalla;
#   3. el raton solo saca la barra de la pantalla donde esta;
#   4. show/toggle/hold van a la barra de la pantalla del raton; release, lock y
#      gaming, a todas; y una barra que nace con el bloqueo puesto, muerta.
#
# Se importa el demonio en una COPIA del repo, con `query()` sustituida (como
# barras-multipantalla.sh) y un `waybar` de mentira que conserva sus argumentos
# (como barras-supervisor.sh): no se dibuja nada ni se toca ninguna waybar real.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

COPIA="$(copiar_repo)"
DEMONIO="$COPIA/hypr/scripts/waybar-autohide.py"
export HYPRLAND_INSTANCE_SIGNATURE="prueba-por-pantalla"
mkdir -p "$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE"
cat > "$FALSOS/waybar" <<'EOF'
#!/usr/bin/env bash
exec python3 -c 'import time; time.sleep(600)' "$@"
EOF
chmod +x "$FALSOS/waybar"

trap 'limpiar_entorno' EXIT INT TERM
RES="$TMP/resultados"

python3 - "$DEMONIO" "$XDG_RUNTIME_DIR" > "$RES" 2>"$TMP/py.err" <<'PYEOF'
import importlib.util, json, os, sys, time

spec = importlib.util.spec_from_file_location("autohide", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
RUNTIME = sys.argv[2]

DP = {"name": "DP-1", "x": 0, "y": 0, "width": 2560, "height": 1440, "scale": 1.0,
      "activeWorkspace": {"id": 1}, "specialWorkspace": {"id": 0}}
HDMI = {"name": "HDMI-A-1", "x": 2560, "y": 0, "width": 1920, "height": 1080,
        "scale": 1.0, "activeWorkspace": {"id": 2}, "specialWorkspace": {"id": 0}}
estado = {"monitores": [DP, HDMI],
          "workspaces": [{"id": 1, "windows": 3}, {"id": 2, "windows": 0}],
          "cursor": (100, 700), "capas": {}}


def query_falso(cmd):
    if cmd == "j/monitors":
        return json.dumps(estado["monitores"])
    if cmd == "j/workspaces":
        return json.dumps(estado["workspaces"])
    if cmd == "j/layers":
        return json.dumps(estado["capas"])
    if cmd.startswith("[[BATCH]]"):
        return "windows: 0\n%d, %d\n" % estado["cursor"]
    return ""


mod.query = query_falso


def olvidar():
    mod._monitores["t"] = -1e9
    mod._dock_geo["t"] = -1e9


def di(clave, valor):
    print("%s=%s" % (clave, valor))


def argv(proc):
    with open("/proc/%d/cmdline" % proc.pid, "rb") as fh:
        return [a.decode() for a in fh.read().split(b"\0") if a]


def cfg_de(proc):
    """El `-c` de waybar: el ULTIMO (el waybar de mentira es python3 -c ...)."""
    a = argv(proc)
    return a[len(a) - a[::-1].index("-c")]


bars = {}
st = {"locked": False, "gaming": False}
try:
    # --- 1. Una pareja por pantalla -----------------------------------------
    olvidar()
    mod.sincronizar_barras(bars, st)
    di("claves", ",".join(sorted("%s@%s" % k for k in bars)))
    main_dp = bars[("main", "DP-1")]
    ruta = cfg_de(main_dp.proc)
    di("ruta_en_runtime", ruta.startswith(RUNTIME))
    cfg = json.load(open(ruta))
    di("output", cfg.get("output"))
    di("incluye_la_del_repo", cfg.get("include") == [os.path.join(mod.WAYBAR_DIR, "config.jsonc")])
    di("otra_ruta_por_pantalla", ruta != cfg_de(bars[("main", "HDMI-A-1")].proc))
    di("tirador_tambien", json.load(open(cfg_de(main_dp.trigger))).get("output"))

    # --- 2. Cada una decide con SU pantalla ---------------------------------
    # Las dos barras puestas (nivel 2); DP-1 con 3 ventanas, HDMI vacia.
    capas_mon = {n: {"waybar-main": [2], "waybar-trigger": [1],
                     "waybar-dock": [2], "waybar-dock-trigger": [1]}
                 for n in ("DP-1", "HDMI-A-1")}
    toggles = {}
    for k, b in bars.items():
        b.manual = False
        b.toggle = (lambda k=k: toggles.__setitem__(k, toggles.get(k, 0) + 1))
    v = mod.ventanas_por_monitor()
    di("ventanas", "%s,%s" % (v["DP-1"], v["HDMI-A-1"]))
    for k, b in bars.items():
        b.update(v[b.salida], 100, 700, capas_mon[b.salida])
    di("esconde_dp", toggles.get(("main", "DP-1"), 0))
    di("deja_hdmi", toggles.get(("main", "HDMI-A-1"), 0))
    # Un escritorio especial abierto encima del vacio tambien tapa.
    estado["monitores"][1] = dict(HDMI, specialWorkspace={"id": -98})
    estado["workspaces"].append({"id": -98, "windows": 1})
    di("especial_tapa", mod.ventanas_por_monitor()["HDMI-A-1"])
    estado["monitores"][1] = HDMI
    estado["workspaces"].pop()

    # --- 3. El raton, solo en su pantalla ------------------------------------
    olvidar()
    di("arriba_dp_para_dp", bars[("main", "DP-1")].in_zone(500, 5))
    di("arriba_dp_para_hdmi", bars[("main", "HDMI-A-1")].in_zone(500, 5))
    di("arriba_hdmi_para_hdmi", bars[("main", "HDMI-A-1")].in_zone(3000, 5))

    # --- 4. A quien va cada orden -------------------------------------------
    recibidas = {}
    for k, b in bars.items():
        b.command = (lambda c, k=k: recibidas.setdefault(k, []).append(c))
    estado["cursor"] = (3000, 5)          # raton en el TES
    mod.repartir_ordenes(bars, "show dock:hold", st)
    di("show_solo_hdmi", "%s|%s" % (recibidas.get(("main", "HDMI-A-1")),
                                    recibidas.get(("main", "DP-1"))))
    di("hold_solo_dock_hdmi", "%s|%s" % (recibidas.get(("dock", "HDMI-A-1")),
                                         recibidas.get(("dock", "DP-1"))))
    recibidas.clear()
    mod.repartir_ordenes(bars, "release lock dock:lock", st)
    di("release_y_lock_a_todas", all(recibidas.get(k) for k in bars))
    di("estado_bloqueado", st["locked"])
    for k, b in bars.items():
        del b.command                     # vuelve el metodo de verdad

    # --- 5. Enchufar y desenchufar ------------------------------------------
    pids_hdmi = [bars[(t, "HDMI-A-1")].proc.pid for t in ("main", "dock")]
    estado["monitores"] = [DP]
    olvidar()
    mod.sincronizar_barras(bars, st)
    di("quedan", ",".join(sorted("%s@%s" % k for k in bars)))
    di("las_del_tes_muertas", not any(os.path.exists("/proc/%d" % p) for p in pids_hdmi))
    estado["monitores"] = [DP, HDMI]
    olvidar()
    mod.sincronizar_barras(bars, st)        # con la pantalla BLOQUEADA
    nueva = bars[("main", "HDMI-A-1")]
    time.sleep(0.3)
    di("nace_bloqueada", "%s,%s" % (nueva.locked, nueva.proc.poll() is not None))

    # --- 6. Sin pantallas conocidas (arranque en frio): una para todas ------
    otro = {}
    estado["monitores"] = []
    olvidar()
    mod._monitores["lista"] = []
    mod.sincronizar_barras(otro, {"locked": False, "gaming": False})
    di("frio", ",".join(sorted("%s@%s" % k for k in otro)))
    di("frio_sin_output", cfg_de(otro[("main", None)].proc)
       == os.path.join(mod.WAYBAR_DIR, "config.jsonc"))
    bars.update({("x" + k[0], k[1]): b for k, b in otro.items()})
finally:
    for b in bars.values():
        for p in (b.proc, b.trigger):
            try:
                p.kill()
                p.wait(timeout=2)
            except Exception:
                pass
PYEOF
codigo=$?
afirmar_igual 0 "$codigo" "la sonda termina bien"
afirmar "   sin nada por stderr" test ! -s "$TMP/py.err"
[ -s "$TMP/py.err" ] && sed 's/^/      /' "$TMP/py.err" | head -15

val() { sed -n "s/^$1=//p" "$RES"; }

titulo "1. Una pareja de waybar por pantalla, cada una con su \"output\""
afirmar_igual "dock@DP-1,dock@HDMI-A-1,main@DP-1,main@HDMI-A-1" "$(val claves)" "dos barras por pantalla"
afirmar_igual "True" "$(val ruta_en_runtime)" "su config va en el runtime de la sesion, no en el repo"
afirmar_igual "DP-1" "$(val output)" "con \"output\" de su pantalla"
afirmar_igual "True" "$(val incluye_la_del_repo)" "e incluye la config del repo (que no se toca)"
afirmar_igual "True" "$(val otra_ruta_por_pantalla)" "cada pantalla, su fichero"
afirmar_igual "DP-1" "$(val tirador_tambien)" "el tirador tambien va por pantalla"

titulo "2. Cada una decide con las ventanas de SU pantalla"
afirmar_igual "3,0" "$(val ventanas)" "ventanas: 3 en el Gigabyte, 0 en el TES"
afirmar_igual "1" "$(val esconde_dp)" "la barra del Gigabyte (con apps) se esconde"
afirmar_igual "0" "$(val deja_hdmi)" "la del TES (vacio) se queda puesta, aunque el foco este en el otro"
afirmar_igual "1" "$(val especial_tapa)" "un escritorio especial encima cuenta como ventanas"

titulo "3. El raton solo cuenta en su pantalla"
afirmar_igual "True" "$(val arriba_dp_para_dp)" "arriba del Gigabyte saca la barra del Gigabyte"
afirmar_igual "False" "$(val arriba_dp_para_hdmi)" "   y NO la del TES"
afirmar_igual "True" "$(val arriba_hdmi_para_hdmi)" "arriba del TES saca la del TES"

titulo "4. A quien va cada orden"
afirmar_igual "['show']|None" "$(val show_solo_hdmi)" "show: solo la de la pantalla del raton"
afirmar_igual "['hold']|None" "$(val hold_solo_dock_hdmi)" "dock:hold: solo el dock de la pantalla del raton"
afirmar_igual "True" "$(val release_y_lock_a_todas)" "release y lock: a todas"
afirmar_igual "True" "$(val estado_bloqueado)" "y el demonio se acuerda de que esta bloqueado"

titulo "5. Enchufar y desenchufar"
afirmar_igual "dock@DP-1,main@DP-1" "$(val quedan)" "al quitar el TES se quitan sus barras"
afirmar_igual "True" "$(val las_del_tes_muertas)" "   y sus waybar mueren"
afirmar_igual "True,True" "$(val nace_bloqueada)" "una pantalla enchufada con el bloqueo puesto: sus barras nacen muertas"

titulo "6. Arranque en frio: una para todas, como antes"
afirmar_igual "dock@None,main@None" "$(val frio)" "sin pantallas conocidas, una pareja sin pantalla"
afirmar_igual "True" "$(val frio_sin_output)" "   con la config del repo tal cual"

afirmar_intacta_la_casa_real
resumen
