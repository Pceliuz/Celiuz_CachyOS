#!/usr/bin/env bash
# tests/unidad/maquina.sh — lib/maquina.py y el cableado que decide si se carga
# conf/teclado-laptop.conf.
#
# Lo que se comprueba aqui es que un sobremesa NO se coma los ajustes de portatil
# y al reves, porque ese es el fallo que motivo todo esto: el bloque `input {}`
# de Hyprland es global y el apano del teclado Attack Shark X820 se le aplicaba
# tambien al teclado interno del portatil, que no lo necesita.
#
# La deteccion NO se prueba contra el equipo donde corre la prueba: eso solo
# comprobaria una de las dos respuestas y ademas daria distinto en cada maquina.
# Se le da un /sys de mentira y se comprueban los dos casos, y los raros.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
MAQUINA="$REPO/hypr/scripts/lib/maquina.py"

titulo "1. Responde en el equipo de verdad"
salida="$("$MAQUINA" tipo 2>&1)"
case "$salida" in
    laptop|escritorio) ok "dice «$salida», que es una de las dos respuestas validas" ;;
    *)                 fallo "responde laptop o escritorio" "obtuve «$salida»" ;;
esac
afirmar "el --json es json de verdad" \
        sh -c "'$MAQUINA' --json | python3 -c 'import json,sys; json.load(sys.stdin)'"

titulo "2. Los dos casos, con un /sys de mentira"
# Se monta un arbol falso por caso y se apuntan ahi las constantes del modulo.
python3 - "$REPO/hypr/scripts/lib" "$TMP" > "$TMP/casos.txt" <<'PY'
import os, sys
sys.path.insert(0, sys.argv[1])
tmp = sys.argv[2]
import maquina

def montar(nombre, chasis=None, bateria=False, tapa=False):
    """Construye un /sys de mentira y apunta el modulo a el."""
    raiz = os.path.join(tmp, "sys-" + nombre)
    dmi, power, lid = (os.path.join(raiz, d) for d in ("dmi", "power", "lid"))
    for d in (dmi, power, lid):
        os.makedirs(d, exist_ok=True)
    if chasis is not None:
        open(os.path.join(dmi, "chassis_type"), "w").write(f"{chasis}\n")
    if bateria:
        os.makedirs(os.path.join(power, "BAT0"), exist_ok=True)
        open(os.path.join(power, "BAT0", "type"), "w").write("Battery\n")
    # El cargador va SIEMPRE: es lo que distingue "hay bateria" de "hay algo
    # enchufado". Su type es Mains, asi que no debe contar como bateria.
    os.makedirs(os.path.join(power, "ADP0"), exist_ok=True)
    open(os.path.join(power, "ADP0", "type"), "w").write("Mains\n")
    if tapa:
        os.makedirs(os.path.join(lid, "LID0"), exist_ok=True)
    maquina.DMI, maquina.POWER, maquina.LID_PROC = dmi, power, lid
    maquina.INPUT_SYS = os.path.join(raiz, "sin-input")
    return maquina.detalle()

def di(clave, d):
    print(clave, d["tipo"])

# Los normales.
di("portatil_notebook", montar("n", chasis=10, bateria=True, tapa=True))
di("portatil_laptop",   montar("l", chasis=9,  bateria=True, tapa=True))
di("sobremesa_tower",   montar("t", chasis=7))
di("sobremesa_mini",    montar("m", chasis=6))

# Los raros, que son los que de verdad se equivocan.
# Un sobremesa con un SAI por USB TIENE bateria. Si la bateria decidiera sola,
# se llevaria los ajustes de portatil: touchpad, tapa y brillo en una torre.
di("torre_con_sai",     montar("s", chasis=7, bateria=True))
# Maquina virtual: el DMI dice "Other" (1) y no hay nada mas. Sobremesa.
di("virtual_sin_dmi",   montar("v", chasis=1))
di("sin_dmi_ninguno",   montar("x"))
# Un chasis desconocido pero con bateria Y tapa es un portatil raro, no una torre.
di("chasis_raro_pero_portatil", montar("r", chasis=99, bateria=True, tapa=True))
# Bateria sin tapa NO basta: ese es el SAI otra vez, sin chasis que ayude.
di("bateria_sin_tapa",  montar("b", bateria=True))
PY
leer() { grep "^$1 " "$TMP/casos.txt" | cut -d' ' -f2; }
afirmar_igual "laptop"     "$(leer portatil_notebook)"          "chasis 10 (Notebook) es portatil"
afirmar_igual "laptop"     "$(leer portatil_laptop)"            "chasis 9 (Laptop) es portatil"
afirmar_igual "escritorio" "$(leer sobremesa_tower)"            "chasis 7 (Tower) es sobremesa"
afirmar_igual "escritorio" "$(leer sobremesa_mini)"             "chasis 6 (Mini Tower) es sobremesa"
afirmar_igual "escritorio" "$(leer torre_con_sai)"              "una torre con SAI sigue siendo sobremesa"
afirmar_igual "escritorio" "$(leer virtual_sin_dmi)"            "una virtual sin DMI util cae en sobremesa"
afirmar_igual "escritorio" "$(leer sin_dmi_ninguno)"            "sin DMI y sin nada, sobremesa"
afirmar_igual "laptop"     "$(leer chasis_raro_pero_portatil)"  "chasis desconocido con bateria y tapa es portatil"
afirmar_igual "escritorio" "$(leer bateria_sin_tapa)"           "bateria sin tapa no basta para ser portatil"

titulo "3. El perfil de teclado que sale de cada caja"
# perfil_teclado() es lo que decide si el Ctrl derecho sobrevive. Se prueba con
# el mismo /sys de mentira: contra el equipo de verdad solo se veria una de las
# dos respuestas.
python3 - "$REPO/hypr/scripts/lib" "$TMP" > "$TMP/teclado.txt" <<'PY'
import os, sys
sys.path.insert(0, sys.argv[1])
tmp = sys.argv[2]
import maquina

def montar(nombre, chasis):
    raiz = os.path.join(tmp, "kb-" + nombre)
    dmi = os.path.join(raiz, "dmi")
    os.makedirs(dmi, exist_ok=True)
    open(os.path.join(dmi, "chassis_type"), "w").write(f"{chasis}\n")
    maquina.DMI = dmi
    maquina.POWER = os.path.join(raiz, "sin-power")
    maquina.LID_PROC = os.path.join(raiz, "sin-lid")
    maquina.INPUT_SYS = os.path.join(raiz, "sin-input")
    return maquina.perfil_teclado()

p = montar("portatil", 10)
print("portatil_perfil", p["perfil"])
# La cadena vacia se imprime como «-» para que no se pierda en el cut.
print("portatil_options", p["kb_options"] or "-")
print("portatil_conf", p["conf"])
print("portatil_motivo", int(bool(p["motivo"])))

s = montar("sobremesa", 7)
print("sobremesa_perfil", s["perfil"])
print("sobremesa_options", s["kb_options"] or "-")
PY
leer_t() { grep "^$1 " "$TMP/teclado.txt" | cut -d' ' -f2; }
afirmar_igual "completo"   "$(leer_t portatil_perfil)"   "un portatil pide el perfil «completo»"
afirmar_igual "-"          "$(leer_t portatil_options)"  "y ahi kb_options va VACIO: el Ctrl derecho se queda siendo Ctrl"
afirmar_igual "conf/teclado-laptop.conf" "$(leer_t portatil_conf)" "y lo aplica conf/teclado-laptop.conf"
afirmar_igual "1"          "$(leer_t portatil_motivo)"   "dice por que lo ha decidido"
afirmar_igual "sin-altgr"  "$(leer_t sobremesa_perfil)"  "un sobremesa se queda en «sin-altgr»"
afirmar_igual "lv3:switch" "$(leer_t sobremesa_options)" "y conserva el apaño del teclado sin AltGr"

# Y que la CLI conteste lo mismo, que es por donde lo mira una persona.
salida_kb="$("$MAQUINA" teclado 2>&1)"
case "$salida_kb" in
    completo|sin-altgr) ok "«maquina.py teclado» dice «$salida_kb»" ;;
    *) fallo "maquina.py teclado responde completo o sin-altgr" "obtuve «$salida_kb»" ;;
esac
afirmar "el --json lleva tambien el teclado" \
        sh -c "'$MAQUINA' --json | python3 -c 'import json,sys; d=json.load(sys.stdin); raise SystemExit(0 if d[\"teclado\"][\"perfil\"] else 1)'"

titulo "4. El cableado de hyprland.conf"
HYPR="$REPO/hypr/hyprland.conf"
# El patron va con `\$` porque afirmar_contiene usa grep -E, y en ERE un `$`
# suelto es el ancla de fin de linea: `source = $conf_maquina` no casaria nunca.
afirmar_contiene "$HYPR" 'conf_maquina = '          "declara un valor de fabrica para \$conf_maquina"
afirmar_contiene "$HYPR" 'source = \$conf_maquina'  "y lo carga"

# El orden es TODO el asunto: si se cargara antes que input.conf o keybinds.conf,
# esos lo pisarian y los ajustes de portatil no harian nada. Sintoma: "puse el
# fichero y no pasa nada".
python3 - "$HYPR" > "$TMP/orden.txt" <<'PY'
import sys
lineas = open(sys.argv[1], encoding="utf-8").read().splitlines()
def n(txt):
    return next((i for i, l in enumerate(lineas) if l.strip().startswith("source") and txt in l), -1)
defecto = next((i for i, l in enumerate(lineas) if l.strip().startswith("$conf_maquina")), -1)
print("declarado_antes", int(0 <= defecto < n("local.conf")))
print("tras_input",   int(n("$conf_maquina") > n("input.conf") > -1))
print("tras_binds",   int(n("$conf_maquina") > n("keybinds.conf") > -1))
print("el_ultimo",    int(n("$conf_maquina") == max(
    i for i, l in enumerate(lineas) if l.strip().startswith("source"))))
PY
leer_o() { grep "^$1 " "$TMP/orden.txt" | cut -d' ' -f2; }
afirmar_igual "1" "$(leer_o declarado_antes)" "el valor de fabrica se declara antes de leer local.conf"
afirmar_igual "1" "$(leer_o tras_input)"      "se carga DESPUES de input.conf"
afirmar_igual "1" "$(leer_o tras_binds)"      "se carga DESPUES de keybinds.conf"
afirmar_igual "1" "$(leer_o el_ultimo)"       "es el ultimo source de todos"

titulo "5. Los dos destinos existen y dicen lo que deben"
NADA="$REPO/hypr/conf/nada.conf"
LAPTOP="$REPO/hypr/conf/teclado-laptop.conf"
afirmar "nada.conf existe (un sobremesa lo carga)" test -f "$NADA"
afirmar "teclado-laptop.conf existe"               test -f "$LAPTOP"

# nada.conf tiene que estar VACIO de verdad: si alguien le mete una directiva
# sin querer, se la come el sobremesa, que es justo lo que esto evita.
# `grep -c` sale con 1 cuando no cuenta nada, asi que un `|| echo 0` detras
# imprimiria DOS ceros y la comparacion fallaria contando bien. Se separa el
# conteo de la salida.
sueltas=$(grep -vE '^[[:space:]]*(#.*)?$' "$NADA" | wc -l)
afirmar_igual "0" "$sueltas" "nada.conf no tiene ni una directiva, solo comentarios"

afirmar_contiene "$LAPTOP" 'switch:on:Lid Switch'         "ata la tapa"
afirmar_contiene "$LAPTOP" 'XF86MonBrightness'            "ata el brillo"

# El Ctrl derecho de vuelta, y para TODOS los teclados.
#
# Esto estuvo en un bloque `device { name = at-translated-set-2-keyboard }`, que
# solo rescataba el teclado interno: cualquier otro —un teclado USB enchufado al
# portatil, y hasta los pseudo-teclados `video-bus` y `power-button`— seguia con
# `lv3:switch` y perdia su Ctrl derecho. Medido en anidado el 2026-08-05: con el
# fichero viejo y perfil de portatil, un teclado que no fuera el interno salia
# con `o "lv3:switch"`; con el nuevo sale vacio.
#
# Por eso se exige que el vaciado este en un bloque `input {}` GLOBAL y no en uno
# de dispositivo. Si alguien lo devuelve a un `device`, esto lo caza.
python3 - "$LAPTOP" > "$TMP/device.txt" <<'PY'
import re, sys
txt = open(sys.argv[1], encoding="utf-8").read()
# Fuera comentarios: el fichero EXPLICA el `device` de antes y la vuelta atras
# con `kb_options = lv3:switch`, y sin esto las dos cosas contarian como codigo.
vivo = re.sub(r'#.*', '', txt)

def cuerpo(clase):
    m = re.search(clase + r'\s*\{(.*?)\}', vivo, re.S)
    return m.group(1) if m else ""

glob = cuerpo("input")
print("vacia_options", int(bool(re.search(r'^\s*kb_options\s*=\s*$', glob, re.M))))
print("sin_device", int(not re.search(r'device\s*\{', vivo)))
# Y que no quede ningun kb_options con valor, que seria volver al apaño.
print("sin_lv3", int("lv3:switch" not in vivo))
PY
leer_d() { grep "^$1 " "$TMP/device.txt" | cut -d' ' -f2; }
afirmar_igual "1" "$(leer_d vacia_options)" "el bloque input GLOBAL vacia kb_options (Ctrl derecho de vuelta)"
afirmar_igual "1" "$(leer_d sin_device)"    "y no lo hace por nombre de dispositivo, que dejaba fuera a los demas"
afirmar_igual "1" "$(leer_d sin_lv3)"       "no queda ningun lv3:switch activo en el perfil de portatil"

titulo "6. El instalador escribe las dos cosas en local.conf"
# Un solo escritor: si la terminal y el tipo de equipo los escribieran dos
# funciones, la segunda borraria lo de la primera. El sintoma seria "se me
# olvida la terminal cada vez que instalo".
afirmar_contiene "$REPO/instalar.sh" 'conf_maquina = \$conf_maquina' "escribe \$conf_maquina en local.conf"
afirmar_contiene "$REPO/instalar.sh" 'terminal = \$term'             "y sigue escribiendo \$terminal"
escritores=$(grep -c 'cat > "$REPO/hypr/conf/local.conf"' "$REPO/instalar.sh")
afirmar_igual "1" "$escritores" "solo hay UN sitio que escribe local.conf"

titulo "7. No toco nada de tu equipo"
afirmar_intacta_la_casa_real

resumen
