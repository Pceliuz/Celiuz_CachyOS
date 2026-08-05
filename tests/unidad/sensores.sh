#!/usr/bin/env bash
# tests/unidad/sensores.sh — que el sensor de temperatura de la CPU se averigue
# solo, y no se quede escrito el del equipo del autor.
#
# EL FALLO QUE VIGILA. waybar/config.jsonc llevaba a mano
# "hwmon-path-abs": "/sys/devices/pci0000:00/0000:00:18.3/hwmon", que es el
# k10temp de un Ryzen 5 5500 — el sobremesa del autor. En el portatil del mismo
# autor (Intel, sensor "coretemp") esa ruta NO EXISTE, y en la maquina de quien
# clone el repo tampoco: cada familia de CPU nombra su sensor de otra forma y lo
# cuelga de otro sitio del /sys.
#
# POR QUE CON UN /sys DE MENTIRA. Contra el /sys de verdad solo se veria la
# respuesta de ESTA caja: la de Intel o la de AMD, nunca las dos, y justo lo que
# hay que probar es que contesta bien en la maquina que no tienes delante. Se
# montan arboles falsos y se le cambia a sensores.py la constante HWMON.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

python3 - "$REPO/hypr/scripts/lib" "$TMP" > "$TMP/salida.txt" <<'PY'
import os, sys
sys.path.insert(0, sys.argv[1])
tmp = sys.argv[2]
import sensores

def montar(nombre, sensores_falsos):
    """Un /sys/class/hwmon de mentira.

    `sensores_falsos` es una lista de (nombre_del_driver, ruta_del_dispositivo,
    {fichero: contenido}). El enlace hwmonN apunta a la carpeta del dispositivo,
    igual que en el kernel: eso es lo que hace que la ruta estable se pueda
    sacar con realpath.
    """
    raiz = os.path.join(tmp, "sys-" + nombre)
    clase = os.path.join(raiz, "class", "hwmon")
    os.makedirs(clase, exist_ok=True)
    for n, (driver, dispositivo, ficheros) in enumerate(sensores_falsos):
        destino = os.path.join(raiz, dispositivo.lstrip("/"), "hwmon", f"hwmon{n}")
        os.makedirs(destino, exist_ok=True)
        open(os.path.join(destino, "name"), "w").write(driver + "\n")
        for fichero, contenido in ficheros.items():
            open(os.path.join(destino, fichero), "w").write(contenido + "\n")
        os.symlink(destino, os.path.join(clase, f"hwmon{n}"))
    sensores.HWMON = clase
    return raiz

# --- Un portatil Intel: coretemp, con etiquetas y varios nucleos -------------
raiz = montar("intel", [
    ("BAT0", "devices/LNXSYSTM:00/PNP0C0A:00", {"temp1_input": "30000"}),
    ("coretemp", "devices/platform/coretemp.0", {
        "temp1_input": "47000", "temp1_label": "Package id 0",
        "temp2_input": "45000", "temp2_label": "Core 0",
        "temp3_input": "62000", "temp3_label": "Core 1",
    }),
])
d = sensores.cpu()
print("intel_nombre", d["nombre"])
print("intel_entrada", d["entrada"])
print("intel_grados", d["grados"])
# La ruta que se le da a waybar es la carpeta `hwmon` del DISPOSITIVO, no el
# /sys/class/hwmon/hwmonN, cuyo numero cambia entre reinicios.
print("intel_ruta_estable", int(d["ruta"] == os.path.join(raiz, "devices/platform/coretemp.0/hwmon")))
print("intel_sin_class", int("/class/" not in d["ruta"]))

# --- Un sobremesa AMD: k10temp, y encima con zenpower delante ----------------
montar("amd", [
    ("zenpower", "devices/pci0000:00/0000:00:18.3", {
        "temp1_input": "51000", "temp1_label": "Tdie"}),
    ("k10temp", "devices/pci0000:00/0000:00:18.4", {
        "temp1_input": "53000", "temp1_label": "Tctl"}),
])
d = sensores.cpu()
print("amd_nombre", d["nombre"])
print("amd_etiqueta", d["etiqueta"].replace(" ", "_"))

# --- Un driver que no etiqueta nada: cae a temp1_input ----------------------
montar("sin-etiquetas", [("coretemp", "devices/platform/coretemp.0",
                          {"temp1_input": "40000", "temp2_input": "41000"})])
d = sensores.cpu()
print("sinetq_entrada", d["entrada"])

# --- Una caja sin ningun sensor conocido: None, y NO una ruta inventada ------
montar("desconocido", [("acpitz", "devices/virtual/thermal", {"temp1_input": "35000"}),
                       ("BAT0", "devices/LNXSYSTM:00/PNP0C0A:00", {"temp1_input": "30000"})])
print("desconocido_es_none", int(sensores.cpu() is None))

# --- Y sin /sys/class/hwmon siquiera: tampoco revienta ----------------------
sensores.HWMON = os.path.join(tmp, "no-existe")
print("sin_hwmon_es_none", int(sensores.cpu() is None))
PY

leer() { grep "^$1 " "$TMP/salida.txt" | cut -d' ' -f2; }

titulo "1. Un portatil Intel"
afirmar_igual "coretemp"    "$(leer intel_nombre)"        "reconoce el sensor «coretemp»"
afirmar_igual "temp1_input" "$(leer intel_entrada)"       "coge la entrada del encapsulado, no la de un nucleo suelto"
afirmar_igual "47"          "$(leer intel_grados)"        "y lee bien los grados"
afirmar_igual "1"           "$(leer intel_ruta_estable)"  "la ruta es la del dispositivo, la que no cambia al reiniciar"
afirmar_igual "1"           "$(leer intel_sin_class)"     "y NO es /sys/class/hwmon/hwmonN, cuyo numero se reparte por orden de arranque"

titulo "2. Un sobremesa AMD"
afirmar_igual "k10temp" "$(leer amd_nombre)"   "prefiere k10temp aunque zenpower salga antes en la lista"
afirmar_igual "Tctl"    "$(leer amd_etiqueta)" "y dentro coge la Tctl"

titulo "3. Los casos raros no rompen nada"
afirmar_igual "temp1_input" "$(leer sinetq_entrada)"    "un driver sin etiquetas cae a temp1_input"
afirmar_igual "1" "$(leer desconocido_es_none)"         "un sensor que no es de CPU devuelve None, NO una ruta inventada"
afirmar_igual "1" "$(leer sin_hwmon_es_none)"           "y sin /sys/class/hwmon tampoco revienta"

titulo "4. La CLI contesta lo mismo"
# Es por donde lo mira una persona, y por donde lo lee instalar.sh.
salida="$("$REPO/hypr/scripts/lib/sensores.py" ruta 2>&1)"
if [ -n "$salida" ] && [ -d "$salida" ]; then
    ok "«sensores.py ruta» da una carpeta que existe ($salida)"
elif [ -z "$salida" ]; then
    ok "«sensores.py ruta» no inventa nada cuando no reconoce el sensor"
else
    fallo "sensores.py ruta da una carpeta que existe" "obtuve «$salida»"
fi

titulo "5. Ningun .jsonc versionado cablea una ruta de /sys"
# Es el fallo original: la ruta del sensor del autor, escrita a mano en un
# fichero que se sube a git. La de esta maquina va en local.jsonc, que no se
# versiona y lo genera instalar.sh.
encontradas=""
for f in "$REPO"/waybar/*.jsonc; do
    case "$(basename "$f")" in local.jsonc|dock.jsonc) continue ;; esac
    # Los comentarios se quitan ANTES de buscar: sensores.jsonc explica en su
    # cabecera cual era la ruta cableada, y eso no es una ruta viva. (Filtrar
    # despues no vale: `grep -n` antepone el numero de linea y el patron de
    # comentario deja de casar por el principio.)
    linea="$(awk '!/^[[:space:]]*\/\//' "$f" | grep -E '"[^"]*(hwmon-path|thermal-zone)[^"]*"[[:space:]]*:' || true)"
    [ -n "$linea" ] && encontradas="$encontradas$(basename "$f"): $linea"$'\n'
done
if [ -z "$encontradas" ]; then
    ok "ningun .jsonc versionado escribe la ruta de un sensor"
else
    fallo "ningun .jsonc versionado escribe la ruta de un sensor" "$encontradas"
fi

titulo "6. No toco nada de tu equipo"
afirmar_intacta_la_casa_real

resumen
