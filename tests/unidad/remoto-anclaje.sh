#!/usr/bin/env bash
# tests/unidad/remoto-anclaje.sh — que vuelva el internet del celular por USB
# al reiniciar (remoto/servidor/celiuz_remoto/anclaje.py), con un adb de
# mentira: ningun celular de verdad cambia de modo.
#
# POR QUE: el demonio le cambia el modo USB a un celular por su cuenta. Los
# dos fallos posibles: no pedirselo y quedarse la PC sin internet en la
# pantalla de inicio (lo que pasaba), o pedirselo a quien no toca — un celular
# enchufado para cargar, o uno al que le apagaste el anclaje tu.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
SERV="$REPO/remoto/servidor"

titulo "1. A quien se le pide, una regla cada vez"
python3 - "$SERV" "$TMP" > "$TMP/piezas.txt" 2>"$TMP/piezas.err" <<'FINPY'
import sys
sys.path.insert(0, sys.argv[1])
TMP = sys.argv[2]
from celiuz_remoto import anclaje as an

def comprobar(desc, cond, detalle=None):
    print(("ok|" if cond else "fallo|") + desc + ("" if cond or detalle is None else f" -> {detalle}"))

cel = lambda funcion=None, serie="R", estado="listo": {"serie": serie, "estado": estado,
                                                     "modelo": "Redmi", "funcion": funcion}
REDMI = {"R": {"funcion": "rndis", "nombre": "Redmi"}}
T = 1_800_000_000.0

comprobar("«rndis,adb» es rndis; «mtp,adb» y «adb» no son anclaje",
          an.funcion_de("rndis,adb\n") == "rndis" and an.funcion_de("mtp,adb") is None
          and an.funcion_de("adb") is None and an.funcion_de("ncm,adb") == "ncm")

v = an.Vuelta()
pedir, mem = v.decidir([cel()], {}, False, T)
comprobar("un celular que nunca dio internet aquí no se toca (enchufado para cargar)", not pedir and not mem)

v = an.Vuelta()
pedir, mem = v.decidir([cel("rndis")], {}, True, T)
comprobar("dándole internet: se apunta, y no se le pide nada", not pedir and mem == REDMI)

v = an.Vuelta()
pedir, mem = v.decidir([cel()], REDMI, False, T)
comprobar("tras reiniciar (vuelta nueva): recordado, sin anclaje y sin internet → se le pide",
          pedir == [("R", "rndis")], pedir)
pedir, _ = v.decidir([cel()], REDMI, False, T + 5)
comprobar("   y no otra vez a los 5 s (respiro)", not pedir)
pedir, _ = v.decidir([cel()], REDMI, False, T + an.RESPIRO)
comprobar("   pero sí pasado el respiro, si sigue sin", pedir == [("R", "rndis")])

v = an.Vuelta()
pedir, _ = v.decidir([cel()], REDMI, True, T)
comprobar("con otra salida a internet (wifi, cable) no se molesta al celular", not pedir)

v = an.Vuelta()
v.decidir([cel("rndis")], REDMI, True, T)
pedir, _ = v.decidir([cel()], REDMI, False, T + 5)
comprobar("se lo apagaste tú (lo tenía y sigue enchufado): se respeta", not pedir)
pedir, _ = v.decidir([cel()], REDMI, False, T + 500)
comprobar("   y se sigue respetando", not pedir)
v.decidir([], REDMI, False, T + 505)
pedir, _ = v.decidir([cel()], REDMI, False, T + 510)
comprobar("   hasta que se desenchufa y se vuelve a enchufar", pedir == [("R", "rndis")])

v = an.Vuelta()
pedir, _ = v.decidir([cel(estado="sin_permisos")], REDMI, False, T)
comprobar("sin permiso del USB (pantalla de inicio sin android-udev) no se intenta", not pedir)

v = an.Vuelta()
pedir, _ = v.decidir([cel()], {"R": {"funcion": "ncm", "nombre": "Pixel"}}, False, T)
comprobar("se le pide el modo que tenía (NCM en los Android nuevos)", pedir == [("R", "ncm")])

def ruta(texto):
    p = f"{TMP}/route"
    open(p, "w").write("Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\n" + texto)
    return an.hay_internet(p)
comprobar("ruta por defecto en /proc/net/route → hay internet",
          ruta("enp48s0f3u2\t00000000\t0E39340A\t0003\t0\t0\t100\t00000000\n"))
comprobar("solo la red local (sin ruta por defecto) → no hay",
          not ruta("enp48s0f3u2\t0039340A\t00000000\t0001\t0\t0\t100\t00FFFFFF\n"))
comprobar("una ruta por defecto CAÍDA (sin la bandera U) no cuenta",
          not ruta("enp34s0\t00000000\t0101A8C0\t0002\t0\t0\t100\t00000000\n"))
comprobar("sin poder leerlo: «hay» (sin saberlo, no se toca al celular)",
          an.hay_internet(f"{TMP}/no-existe"))
FINPY
while IFS='|' read -r res desc; do
    case "$res" in
        ok) ok "$desc" ;;
        fallo) fallo "$desc" ;;
        *) fallo "salida inesperada" "$res $desc" ;;
    esac
done < "$TMP/piezas.txt"
afirmar "   dijeron algo (no reventó antes de empezar)" test "$(grep -c '^ok|' "$TMP/piezas.txt")" -ge 14
afirmar "   sin nada por stderr" test ! -s "$TMP/piezas.err"

titulo "2. Una pasada entera, con un adb de mentira"
# El celular de mentira: su modo USB vive en un fichero; `setFunctions` lo
# cambia como el de verdad, y la traza de Java de MIUI sale por stderr.
echo "mtp,adb" > "$TMP/modo"
binario_falso adb 0 "
case \"\$*\" in
    'devices -l') printf 'List of devices attached\nSERIE1  device usb:3-2 product:maltose model:M2101K7BL\n\n' ;;
    *'getprop sys.usb.config') cat '$TMP/modo' ;;
    *'svc usb setFunctions '*) echo 'java.io.FileNotFoundException: theme_compatibility.xml' >&2
                               ultimo=\"\${@: -1}\"; echo \"\${ultimo##* },adb\" > '$TMP/modo' ;;
esac"
pasada() {
    python3 - "$SERV" "$1" <<'FINPY'
import sys
sys.path.insert(0, sys.argv[1])
from celiuz_remoto import anclaje as an
an.hay_internet = lambda: sys.argv[2] == "si"
print(len(an.pasada(an.Vuelta())))
FINPY
}
afirmar_igual "0" "$(pasada no 2>&1)" "un celular sin apuntar no se toca"
afirmar_igual "mtp,adb" "$(cat "$TMP/modo")" "   y sigue en su modo"

echo "rndis,adb" > "$TMP/modo"
afirmar_igual "0" "$(pasada si 2>&1)" "dándole internet: se apunta"
afirmar_contiene "$XDG_STATE_HOME/celiuz/remoto/anclaje.json" '"SERIE1"' "   en el estado del usuario, fuera del repo"

echo "mtp,adb" > "$TMP/modo"     # «reinició la PC»: el celular apagó el anclaje
salida="$(pasada no 2>"$TMP/err")"; codigo=$?
afirmar_igual "0" "$codigo" "tras reiniciar la pasada no revienta"
afirmar "   ni dice nada por stderr (lo de MIUI se lo queda adb)" test ! -s "$TMP/err"
afirmar_igual "1" "$(echo "$salida" | tail -1)" "   y se lo pide"
afirmar_igual "rndis,adb" "$(cat "$TMP/modo")" "   y el celular vuelve a dar internet"
afirmar "   con su orden de verdad" grep -qF -- "-s SERIE1 shell svc usb setFunctions rndis" "$REGISTRO/adb.log"

titulo "3. Lo que se instala"
afirmar_contiene "$SERV/celiuz-remoto-anclaje.service" "^ExecStart=%h/.local/bin/celiuz-remoto anclaje --vigilar$" \
    "la unidad llama a la CLI por el enlace de ~/.local/bin"
afirmar_contiene "$REPO/instalar.sh" "celiuz-remoto.service celiuz-remoto-anclaje.service" \
    "instalar.sh la copia como la otra (enlazada, un disable la borraría)"
salida="$(python3 "$SERV/celiuz-remoto.py" anclaje 2>"$TMP/err")"; codigo=$?
afirmar_igual "0" "$codigo" "\`celiuz-remoto anclaje\` sale con 0"
afirmar "   sin nada por stderr" test ! -s "$TMP/err"
echo "$salida" > "$TMP/salida"
afirmar_contiene "$TMP/salida" "M2101K7BL \(SERIE1\)" "   y nombra al celular apuntado"

afirmar_intacta_la_casa_real
resumen
