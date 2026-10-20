#!/usr/bin/env bash
# tests/unidad/hardware.sh — lib/hardware.py (que tiene este equipo) y la barra
# de FPS del modo gaming, que enseña solo eso.
#
# POR QUE: en la laptop (Intel UHD 620, integrada) MangoHud pintaba «0 °C» y
# «VRAM 0.0 GiB» (2026-10-20). Se prueba con un /sys/class/drm de mentira por
# cada clase de equipo, y lspci de mentira para no leer la GPU de verdad.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
binario_falso lspci 0

# tarjeta <drm> <n> <vendor> <pci> <driver> [hwmon: temp fan cap]... [vram]
tarjeta() {
    local drm="$1" n="$2" vendor="$3" pci="$4" driver="$5"; shift 5
    local d="$TMP/pci/$pci"
    mkdir -p "$d" "$TMP/drivers/$driver" "$drm/card$n" "$drm/card$n-HDMI-A-$n"
    echo "$vendor" > "$d/vendor"
    ln -sfn "$TMP/drivers/$driver" "$d/driver"
    ln -sfn "$d" "$drm/card$n/device"
    for x in "$@"; do
        case "$x" in
            temp) mkdir -p "$d/hwmon/hwmon1"; : > "$d/hwmon/hwmon1/temp1_input" ;;
            fan)  mkdir -p "$d/hwmon/hwmon1"; : > "$d/hwmon/hwmon1/fan1_input" ;;
            cap)  mkdir -p "$d/hwmon/hwmon1"; : > "$d/hwmon/hwmon1/power1_cap" ;;
            vram) : > "$d/mem_info_vram_total" ;;
        esac
    done
}
tarjeta "$TMP/intel"   1 0x8086 0000:00:02.0 i915
tarjeta "$TMP/arc"     0 0x8086 0000:03:00.0 xe temp
tarjeta "$TMP/nvidia"  0 0x10de 0000:01:00.0 nvidia
tarjeta "$TMP/apu"     0 0x1002 0000:30:00.0 amdgpu temp vram
tarjeta "$TMP/radeon"  0 0x1002 0000:2d:00.0 amdgpu temp fan cap vram
tarjeta "$TMP/hibrido" 0 0x8086 0000:00:02.1 i915
tarjeta "$TMP/hibrido" 1 0x10de 0000:01:00.1 nvidia
mkdir -p "$TMP/nada"

python3 - "$REPO/hypr/scripts" "$TMP" > "$TMP/r.json" 2>"$TMP/r.err" <<'PY'
import importlib.util, json, os, sys
scripts, tmp = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(scripts, "lib"))
import hardware
r = {}
for caso in ("intel", "arc", "nvidia", "apu", "radeon", "hibrido", "nada"):
    g = hardware.gpus(os.path.join(tmp, caso))
    r[caso] = {"n": len(g), "dedicadas": [x["dedicada"] for x in g],
               "overlay": hardware.overlay({"gpus": g, "cpu": {"sensor": "k10temp"}, "bateria": False})}
r["sin_sensor"] = hardware.overlay({"gpus": [], "cpu": {"sensor": None}, "bateria": True})

# La config de MangoHud, con un equipo de mentira de cada clase
spec = importlib.util.spec_from_file_location("mg", os.path.join(scripts, "modo-gaming.py"))
mg = importlib.util.module_from_spec(spec); spec.loader.exec_module(mg)
def config(caso, sensor, bateria):
    hardware.detectar = lambda drm=None: {"gpus": hardware.gpus(os.path.join(tmp, caso)),
                                          "cpu": {"sensor": sensor}, "bateria": bateria}
    return [l for l in open(mg.escribir_mangohud()).read().split("\n") if "=" not in l]
r["conf_laptop"] = config("intel", "coretemp", True)
r["conf_pc"] = config("nvidia", "k10temp", False)
r["conf_hibrido"] = config("hibrido", "coretemp", True)
print(json.dumps(r))
PY
codigo=$?
R() { python3 -c 'import json,sys; R=json.load(open(sys.argv[1])); print(eval(sys.argv[2]))' "$TMP/r.json" "$1"; }

titulo "0. Corre"
afirmar_igual "0" "$codigo" "sale con 0"
afirmar "   sin nada por stderr" test ! -s "$TMP/r.err"
[ -s "$TMP/r.err" ] && sed 's/^/      /' "$TMP/r.err"

titulo "1. Integrada o dedicada"
afirmar_igual "[False]" "$(R 'R["intel"]["dedicadas"]')" "Intel en el bus 0: integrada (y la salida card1-HDMI no cuenta)"
afirmar_igual "[True]"  "$(R 'R["arc"]["dedicadas"]')" "Intel en otro bus: una Arc, dedicada"
afirmar_igual "[True]"  "$(R 'R["nvidia"]["dedicadas"]')" "NVIDIA: dedicada"
afirmar_igual "[False]" "$(R 'R["apu"]["dedicadas"]')" "AMD sin ventilador ni limite: la de una APU"
afirmar_igual "[True]"  "$(R 'R["radeon"]["dedicadas"]')" "AMD con ventilador: dedicada"
afirmar_igual "[False, True]" "$(R 'R["hibrido"]["dedicadas"]')" "portatil hibrido: las dos"
afirmar_igual "0" "$(R 'R["nada"]["n"]')" "sin tarjetas: ninguna"

titulo "2. Que enseña la barra"
o() { R "[k for k, v in R['$1']['overlay'].items() if v]"; }
afirmar_igual "['gpu', 'cpu_temp']" "$(o intel)" "integrada Intel: el uso, sin temperatura ni VRAM"
afirmar_igual "['gpu', 'gpu_temp', 'vram', 'cpu_temp']" "$(o nvidia)" "NVIDIA: todo lo de la GPU"
afirmar_igual "['gpu', 'gpu_temp', 'cpu_temp']" "$(o apu)" "APU: su temperatura, pero no la «VRAM» prestada de la RAM"
afirmar_igual "['gpu', 'gpu_temp', 'vram', 'cpu_temp']" "$(o radeon)" "Radeon dedicada: todo"
afirmar_igual "['gpu', 'gpu_nombre', 'gpu_temp', 'vram', 'cpu_temp']" "$(o hibrido)" \
    "hibrido: ademas el NOMBRE, para saber en cual corre el juego"
afirmar_igual "['bateria']" "$(R "[k for k, v in R['sin_sensor'].items() if v]")" \
    "sin GPU ni sensor de CPU: nada de eso; con bateria, la bateria"

titulo "3. Y llega a la config de MangoHud"
afirmar_igual "['gpu_stats', 'cpu_stats', 'cpu_temp', 'battery']" \
    "$(R "[l for l in R['conf_laptop'] if l in ('gpu_stats','gpu_name','gpu_temp','vram','cpu_stats','cpu_temp','battery')]")" \
    "laptop con integrada: GPU %, CPU con temperatura y bateria"
afirmar_igual "['gpu_stats', 'gpu_temp', 'vram', 'cpu_stats', 'cpu_temp']" \
    "$(R "[l for l in R['conf_pc'] if l in ('gpu_stats','gpu_name','gpu_temp','vram','cpu_stats','cpu_temp','battery')]")" \
    "PC con NVIDIA: GPU con temperatura y VRAM, sin bateria"
afirmar_igual "['gpu_stats', 'gpu_name', 'gpu_temp', 'vram', 'cpu_stats', 'cpu_temp', 'battery']" \
    "$(R "[l for l in R['conf_hibrido'] if l in ('gpu_stats','gpu_name','gpu_temp','vram','cpu_stats','cpu_temp','battery')]")" \
    "portatil hibrido: todo, con el nombre de la GPU"

titulo "4. La CLI"
salida="$("$REPO/hypr/scripts/lib/hardware.py" --json 2>&1)"; codigo=$?
afirmar_igual "0" "$codigo" "hardware.py --json sale con 0 en esta maquina"
afirmar "   y es json con gpus y overlay" python3 -c 'import json,sys; d=json.loads(sys.argv[1]); d["gpus"]; d["overlay"]' "$salida"

afirmar_intacta_la_casa_real
resumen
