#!/usr/bin/env bash
# tests/unidad/mangohud-gpu.sh — la barra de FPS solo enseña la temperatura y
# la VRAM de la GPU si hay algo que medir (modo-gaming.datos_de_gpu).
#
# POR QUE: en la laptop (Intel UHD 620, integrada) salian «0 °C» y «VRAM 0.0
# GiB» (2026-10-20). Se prueba con un /sys/class/drm de mentira por tipo.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

montar() {   # montar <nombre> <driver> [temp] [vram] → crea $TMP/<nombre>/card0
    local raiz="$TMP/$1" d="$TMP/$1/card0/device"
    mkdir -p "$d" "$TMP/drivers/$2" "$raiz/card0-eDP-1"
    ln -s "$TMP/drivers/$2" "$d/driver"
    [ "${3:-}" = temp ] && { mkdir -p "$d/hwmon/hwmon3"; echo 45000 > "$d/hwmon/hwmon3/temp1_input"; }
    [ "${4:-}" = vram ] && echo 8589934592 > "$d/mem_info_vram_total"
    echo "$raiz"
}
INTEL="$(montar intel i915)"
NVIDIA="$(montar nvidia nvidia)"
AMD="$(montar amd amdgpu temp vram)"
VACIO="$TMP/vacio"; mkdir -p "$VACIO"

gpu() {
    python3 - "$REPO/hypr/scripts" "$1" <<'PY'
import importlib.util, os, sys
sys.path.insert(0, os.path.join(sys.argv[1], "lib"))
s = importlib.util.spec_from_file_location("mg", os.path.join(sys.argv[1], "modo-gaming.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
d = m.datos_de_gpu(sys.argv[2]); print(d["temp"], d["vram"])
PY
}

titulo "Que se enseña segun la GPU"
afirmar_igual "False False" "$(gpu "$INTEL")" "Intel integrada: ni temperatura ni VRAM"
afirmar_igual "True True" "$(gpu "$NVIDIA")" "NVIDIA: las dos (por NVML, sin nada en /sys)"
afirmar_igual "True True" "$(gpu "$AMD")" "AMD con sensor y memoria: las dos"
afirmar_igual "False False" "$(gpu "$VACIO")" "sin GPU que mirar: ninguna"

titulo "Y llega a la config del overlay"
python3 - "$REPO/hypr/scripts" "$INTEL" "$NVIDIA" > "$TMP/conf.txt" 2>"$TMP/conf.err" <<'PY'
import importlib.util, os, sys
sys.path.insert(0, os.path.join(sys.argv[1], "lib"))
s = importlib.util.spec_from_file_location("mg", os.path.join(sys.argv[1], "modo-gaming.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
for nombre, drm in (("intel", sys.argv[2]), ("nvidia", sys.argv[3])):
    m.DRM = drm
    lineas = open(m.escribir_mangohud()).read().split("\n")
    print(nombre, "gpu_temp" in lineas, "vram" in lineas, "gpu_stats" in lineas)
PY
afirmar "sin errores al generarla" test ! -s "$TMP/conf.err"
afirmar_igual "intel False False True" "$(grep ^intel "$TMP/conf.txt")" "laptop: el uso de la GPU sí, lo demás no"
afirmar_igual "nvidia True True True" "$(grep ^nvidia "$TMP/conf.txt")" "PC: todo"

afirmar_intacta_la_casa_real
resumen
