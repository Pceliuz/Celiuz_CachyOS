#!/usr/bin/env bash
# tests/unidad/teclados.sh — la pregunta por la distribucion de cada teclado
# (hypr/scripts/teclados.py) y su relectura en cada recarga (hypr/lua/teclados.lua).
#
# QUE VIGILA
#   1. Que es «un teclado»: solo lo que tiene letras, agrupado por aparato, sin
#      el raton que se anuncia como teclado (el de la laptop, copiado de su
#      /proc), sin el teclado interno de un portatil y sin los virtuales. Pero
#      un i8042 en un SOBREMESA (teclado PS/2) si se pregunta.
#   2. Se pregunta UNA vez por aparato aunque tenga varios nombres, y nunca mas.
#   3. «Ahora no» no vuelve a preguntar mientras siga enchufado; al volver a
#      enchufarlo, si.
#   4. Un nombre nuevo de un aparato ya contestado se apunta sin preguntar.
#   5. Que distribucion sale de cada respuesta.
#   6. Se aplica en caliente con hl.device por eval, y solo con config en Lua.
#   7. lua/teclados.lua registra un hl.device por linea, y se salta los «-».
#   8. No escribe nada fuera de la casa de mentira.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
SCRIPTS="$REPO/hypr/scripts"

# hyprctl de mentira: «ok» al eval (o sea config en Lua) y una lista de teclados.
binario_falso hyprctl 0 '
case "$1" in
    eval) echo ok ;;
    devices) cat "$REGISTRO/devices.json" 2>/dev/null ;;
esac'
cat > "$REGISTRO/devices.json" <<'EOF'
{"keyboards": [
 {"name": "usb-optical-mouse--keyboard"}, {"name": "at-translated-set-2-keyboard"},
 {"name": "power-button"}, {"name": "video-bus"},
 {"name": "x820uitra"}, {"name": "x820uitra-keyboard"}, {"name": "x820uitra-consumer-control"}
]}
EOF

python3 - "$SCRIPTS" "$TMP" > "$TMP/casos.txt" 2>"$TMP/casos.err" <<'PY'
import importlib.util, json, os, sys
scripts, tmp = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(scripts, "lib"))
spec = importlib.util.spec_from_file_location("teclados", os.path.join(scripts, "teclados.py"))
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)

LETRAS = "ffffffffffffffff fffffffffffffffe"
def bloque(bus, ven, pro, nombre, ev="120013", key=LETRAS):
    return (f'I: Bus={bus} Vendor={ven} Product={pro} Version=0111\n'
            f'N: Name="{nombre}"\nB: EV={ev}\n' + (f'B: KEY={key}\n' if key else ''))

# El /proc de la laptop, tal cual (2026-10-20), sin los de audio.
LAPTOP = "\n".join([
    bloque("0019", "0000", "0001", "Power Button", "3", "10000000000000 0"),
    bloque("0011", "0001", "0001", "AT Translated Set 2 keyboard", "120013",
           "402000007 ff803078f800d001 feffffdfffcfffff fffffffffffffffe"),
    bloque("0003", "4e53", "5406", "USB OPTICAL MOUSE ", "17", "1f0000 0 0 0 0"),
    bloque("0003", "4e53", "5406", "USB OPTICAL MOUSE  Keyboard", "10001f",
           "733eff 0 0 483ffff17aff32d bfd4444600000000 1 130ff38b17c007 "
           "ffff7bfad941dfff febeffdfffefffff fffffffffffffffe"),
    bloque("0019", "0000", "0006", "Video Bus", "3", "3e000b00000000 0 0 0"),
])
X820 = "\n".join([
    bloque("0003", "3151", "5002", "X820UItra"),
    bloque("0003", "3151", "5002", "X820UItra Keyboard"),
    bloque("0003", "3151", "5002", "X820UItra Consumer Control", "1f", "1 0"),
])
VIRTUAL = bloque("0006", "0000", "0000", "ydotoold virtual device")
nombres = {k["name"] for k in json.load(open(os.path.join(tmp, "registro", "devices.json")))["keyboards"]}
nombres.add("ydotoold-virtual-device")

def ver(texto, portatil):
    return {a["id"]: a for a in t.aparatos(t.leer_proc(texto), portatil, nombres)}

r = {}
lap = ver(LAPTOP, True)
r["laptop_ids"] = sorted(lap)
r["raton"] = lap["0003:4e53:5406"]["motivo"] or ""
r["interno_laptop"] = lap["0011:0001:0001"]["motivo"] or ""
pc = ver(LAPTOP, False)
r["interno_pc"] = pc["0011:0001:0001"]["motivo"]
r["nombre_raton"] = t.nombre_hypr("USB OPTICAL MOUSE  Keyboard")
x = ver(X820 + "\n" + VIRTUAL, False)
r["x820_nombres"] = x["0003:3151:5002"]["nombres"]
r["x820_motivo"] = x["0003:3151:5002"]["motivo"]
r["virtual"] = x["0006:0000:0000"]["motivo"] or ""

# --- revisar(): en un sobremesa, con la X820 y la laptop enchufadas ---------
t.maquina.detalle = lambda: {"tipo": "escritorio"}
t.maquina.distribucion_del_sistema = lambda: (None, None)
preguntas = []
def contesta(valor):
    def f(desc):
        preguntas.append(desc)
        return valor
    return f
aplazados = t.revisar(X820, set(), contesta("us"))
r["pregunto"] = list(preguntas)
r["conf"] = {n: [e["layout"], e["variant"], e["id"]] for n, e in t.leer_conf().items()}
t.revisar(X820, aplazados, contesta("latam"))
r["preguntas_segunda"] = len(preguntas)
# Un nombre nuevo del mismo aparato
nombres.add("x820uitra-system-control")
ruta = os.path.join(tmp, "registro", "devices.json")
lista = json.load(open(ruta)); lista["keyboards"].append({"name": "x820uitra-system-control"})
json.dump(lista, open(ruta, "w"))
t.revisar(X820 + "\n" + bloque("0003", "3151", "5002", "X820UItra System Control"),
          set(), contesta("latam"))
r["preguntas_nombre_nuevo"] = len(preguntas)
r["nombre_nuevo"] = t.leer_conf().get("x820uitra-system-control", {}).get("layout")

# «Ahora no»: el PS/2 del sobremesa
preguntas.clear()
ap = t.revisar(LAPTOP, set(), contesta(None))
ap = t.revisar(LAPTOP, ap, contesta(None))
r["ahora_no"] = len(preguntas)
ap = t.revisar("", ap, contesta(None))            # desenchufado
t.revisar(LAPTOP, ap, contesta("latam"))           # y vuelto a enchufar
r["tras_reenchufar"] = len(preguntas)
r["ps2"] = t.leer_conf().get("at-translated-set-2-keyboard", {}).get("layout")

# --- distribucion() ------------------------------------------------------
r["dist_us"] = list(t.distribucion("us"))
r["dist_no"] = list(t.distribucion("no"))
r["dist_latam"] = list(t.distribucion("latam"))
r["dist_es"] = list(t.distribucion("es"))
r["nombres"] = [t.nombre_distribucion(x) for x in ("es,us", "latam,us", "us,latam")]

# --- El aviso al conectar ------------------------------------------------------
avisos = []
anota = lambda d, l, nuevo: avisos.append([d, l, nuevo])
guardado = open(t.ruta_conf()).read()
open(t.ruta_conf(), "w").write("")
vistos = set()
t.revisar(X820, set(), contesta("es"), vistos=vistos, avisar_=anota)
r["aviso_al_contestar"] = list(avisos); avisos.clear()
t.revisar(X820, set(), contesta("us"), vistos=vistos, avisar_=anota)
r["aviso_sigue_puesto"] = list(avisos)
t.revisar("", set(), contesta("us"), vistos=vistos, avisar_=anota)       # desenchufado
t.revisar(X820, set(), contesta("us"), vistos=vistos, avisar_=anota)     # y otra vez
r["aviso_al_reconectar"] = list(avisos); avisos.clear()
t.revisar(X820, set(), contesta("us"), vistos=None, avisar_=anota)
r["aviso_sin_vistos"] = list(avisos)
open(t.ruta_conf(), "w").write(guardado)

# --- olvidar ---------------------------------------------------------------
import contextlib, io
with contextlib.redirect_stdout(io.StringIO()):
    r["olvidar"] = t.olvidar("0003:3151:5002")
r["tras_olvidar"] = sorted(t.leer_conf())
print(json.dumps(r))
PY
codigo=$?
R() { python3 -c 'import json,sys; R=json.load(open(sys.argv[1])); print(eval(sys.argv[2]))' "$TMP/casos.txt" "$1"; }

titulo "0. Corre sin fallar"
afirmar_igual "0" "$codigo" "el guion de casos sale con 0"
afirmar "   sin nada por stderr" test ! -s "$TMP/casos.err"
[ -s "$TMP/casos.err" ] && sed 's/^/      /' "$TMP/casos.err"

titulo "1. Que es un teclado"
afirmar_igual "['0003:4e53:5406', '0011:0001:0001']" "$(R 'R["laptop_ids"]')" \
    "en la laptop: el interno y el raton; ni el boton de encendido ni Video Bus (sin letras)"
afirmar "el raton que se anuncia como teclado no se pregunta" \
    test "$(R 'bool(R["raton"])')" = True
afirmar "el teclado interno de un portatil no se pregunta" \
    test "$(R 'bool(R["interno_laptop"])')" = True
afirmar_igual "None" "$(R 'R["interno_pc"]')" "un i8042 en un sobremesa (PS/2) SI se pregunta"
afirmar_igual "usb-optical-mouse--keyboard" "$(R 'R["nombre_raton"]')" \
    "el nombre de Hyprland: minusculas y espacios a guiones (dos espacios, dos guiones)"
afirmar_igual "['x820uitra', 'x820uitra-consumer-control', 'x820uitra-keyboard']" \
    "$(R 'R["x820_nombres"]')" "un aparato con tres nombres es UN teclado, con los tres"
afirmar_igual "None" "$(R 'R["x820_motivo"]')" "y por el USB si se pregunta"
afirmar "un teclado virtual no se pregunta" test "$(R 'bool(R["virtual"])')" = True

titulo "2-4. Cuando pregunta"
afirmar_igual "['X820UItra']" "$(R 'R["pregunto"]')" "una sola pregunta por el aparato"
afirmar_igual "['us,latam', 'altgr-intl,', '0003:3151:5002']" "$(R 'R["conf"]["x820uitra-keyboard"]')" \
    "y la respuesta vale para cada nombre"
afirmar_igual "3" "$(R 'len(R["conf"])')" "   (los tres)"
afirmar_igual "1" "$(R 'R["preguntas_segunda"]')" "ya contestado: no vuelve a preguntar"
afirmar_igual "1" "$(R 'R["preguntas_nombre_nuevo"]')" "un nombre nuevo del mismo aparato no pregunta"
afirmar_igual "us,latam" "$(R 'R["nombre_nuevo"]')" "   y se apunta con la respuesta de antes"
afirmar_igual "1" "$(R 'R["ahora_no"]')" "«Ahora no»: no vuelve a preguntar mientras siga enchufado"
afirmar_igual "2" "$(R 'R["tras_reenchufar"]')" "   al reenchufarlo, si"
afirmar_igual "latam,us" "$(R 'R["ps2"]')" "   y apunta lo que se conteste"

titulo "5. Que distribucion sale"
afirmar_igual "['us,latam', 'altgr-intl,']" "$(R 'R["dist_us"]')" "«; :» → us, con latam detras"
afirmar_igual "['latam,us', ',altgr-intl']" "$(R 'R["dist_latam"]')" "«Ñ» → latam, con us detras"
afirmar_igual "['es,us', ',altgr-intl']" "$(R 'R["dist_es"]')" "«Ñ Ç» → España, con us detras"
afirmar_igual "['español (España)', 'latinoamericano', 'inglés (US)']" "$(R 'R["nombres"]')" "el nombre del aviso"

titulo "5b. El aviso al conectar"
afirmar_igual "[['X820UItra', 'es,us', True]]" "$(R 'R["aviso_al_contestar"]')" "al contestar: uno, «aplicada»"
afirmar_igual "[]" "$(R 'R["aviso_sigue_puesto"]')" "mientras sigue enchufado, ninguno mas"
afirmar_igual "[['X820UItra', 'es,us', False]]" "$(R 'R["aviso_al_reconectar"]')" "al volver a enchufarlo: «cambiada automaticamente»"
afirmar_igual "[]" "$(R 'R["aviso_sin_vistos"]')" "sin vistos (el arranque), sin aviso"
afirmar_igual "['-', '']" "$(R 'R["dist_no"]')" "«No es un teclado» → no se toca"

titulo "6. Se aplica en caliente, a ese teclado"
afirmar_contiene "$REGISTRO/hyprctl.log" \
    'eval hl.device\(\{ name = "x820uitra-keyboard", kb_layout = "us,latam", kb_variant = "altgr-intl," \}\)' \
    "hl.device por eval, con el nombre de Hyprland"
afirmar_no_contiene "$REGISTRO/hyprctl.log" 'hl.device\(\{ name = "usb-optical' "al raton no le manda nada"
afirmar_igual "0" "$(R 'R["olvidar"]')" "olvidar un aparato"
afirmar_igual "['at-translated-set-2-keyboard']" "$(R 'R["tras_olvidar"]')" "   y solo ese"

titulo "7. lua/teclados.lua"
if command -v lua >/dev/null 2>&1; then
    COPIA="$(copiar_repo)"
    ln -sfn "$COPIA/hypr" "$HOME/.config/hypr"
    rm -f "$COPIA/hypr/lua/local.lua" "$COPIA/hypr/lua/personal.lua"
    printf '# comentario\nx820uitra-keyboard\tus,latam\taltgr-intl,\t0003:3151:5002\tX820\nraton\t-\t\t0003:1:1\tRaton\n' \
        > "$XDG_CONFIG_HOME/celiuz/teclados.conf"
    lua "$REPO/tests/lib/hl_falso.lua" "$TMP/lua.json" 2>"$TMP/lua.err"
    afirmar "carga sin error" test ! -s "$TMP/lua.err"
    afirmar_igual '[{"kb_layout": "us,latam", "kb_variant": "altgr-intl,", "name": "x820uitra-keyboard"}]' \
        "$(python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1]))["dispositivos"], sort_keys=True))' "$TMP/lua.json")" \
        "un hl.device por teclado contestado, y ninguno para el «-»"
    rm -f "$XDG_CONFIG_HOME/celiuz/teclados.conf"
    lua "$REPO/tests/lib/hl_falso.lua" "$TMP/lua2.json" 2>"$TMP/lua2.err"
    afirmar "sin el fichero (quien clona) carga igual" test ! -s "$TMP/lua2.err"
else
    _gris "  (no hay \`lua\`: me salto esta parte)"
fi

afirmar_intacta_la_casa_real
resumen
