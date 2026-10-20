#!/usr/bin/env bash
# tests/unidad/mangohud-lanzamiento.sh — el modo gaming pone «mangohud
# %command%» en las opciones de lanzamiento de Steam de los juegos que las
# tienen vacias (modo-gaming.poner_mangohud / juegos_sin_mangohud).
#
# POR QUE: MANGOHUD=1 solo vale para Vulkan; un juego nativo con OpenGL
# (Silksong, 2026-10-20) no enseñaba el overlay con ninguna tecla.
#
#   1. Vacias → se ponen; sin la clave → se añade; sin bloque del juego → se crea.
#   2. Lo que escribio el usuario NO se toca.
#   3. El fichero sigue siendo un VDF que se lee, y una segunda pasada no cambia nada.
#   4. Sin el binario mangohud no se escribe NADA (el juego no arrancaria).
#   5. Se apaga con "mangohud_lanzamiento": false.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

python3 - "$REPO/hypr/scripts" "$FALSOS" > "$TMP/casos.txt" 2>"$TMP/casos.err" <<'PY'
import importlib.util, json, os, sys
scripts, falsos = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(scripts, "lib"))
spec = importlib.util.spec_from_file_location("mg", os.path.join(scripts, "modo-gaming.py"))
mg = importlib.util.module_from_spec(spec); spec.loader.exec_module(mg)
import catalogo

TEXTO = '''"UserLocalConfigStore"
{
\t"Software"
\t{
\t\t"Valve"
\t\t{
\t\t\t"Steam"
\t\t\t{
\t\t\t\t"apps"
\t\t\t\t{
\t\t\t\t\t"1"
\t\t\t\t\t{
\t\t\t\t\t\t"LaunchOptions"\t\t""
\t\t\t\t\t\t"Playtime"\t\t"10"
\t\t\t\t\t}
\t\t\t\t\t"2"
\t\t\t\t\t{
\t\t\t\t\t\t"Playtime"\t\t"5"
\t\t\t\t\t}
\t\t\t\t\t"3"
\t\t\t\t\t{
\t\t\t\t\t\t"LaunchOptions"\t\t"PROTON_LOG=1 %command%"
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\t"apps_otro"
\t\t\t\t{
\t\t\t\t\t"1"\t\t"x"
\t\t\t\t}
\t\t\t}
\t\t}
\t}
}
'''
r = {}
nuevo, puestos = mg.poner_mangohud(TEXTO, ["1", "2", "3", "4"])
r["puestos"] = puestos
apps = catalogo.vdf(nuevo)["userlocalconfigstore"]["software"]["valve"]["steam"]["apps"]
r["opciones"] = {a: apps.get(a, {}).get("launchoptions") for a in "1234"}
r["playtime"] = [apps["1"].get("playtime"), apps["2"].get("playtime")]
r["otro"] = catalogo.vdf(nuevo)["userlocalconfigstore"]["software"]["valve"]["steam"]["apps_otro"]
r["segunda"] = mg.poner_mangohud(nuevo, ["1", "2", "3", "4"])[1]
r["sin_apps"] = mg.poner_mangohud('"UserLocalConfigStore"\n{\n}\n', ["1"])[1]

# juegos_sin_mangohud, con un Steam de mentira
casa = os.environ["HOME"]
loc = os.path.join(casa, ".local/share/Steam/userdata/22/config")
os.makedirs(loc); os.makedirs(os.path.join(casa, ".local/share/Steam/steamapps"))
open(os.path.join(loc, "localconfig.vdf"), "w").write(TEXTO)
catalogo.raiz_steam = lambda: os.path.join(casa, ".local/share/Steam")
catalogo.ruta_localconfig = lambda raiz: os.path.join(loc, "localconfig.vdf")
catalogo.juegos_steam = lambda: [{"id": "steam:1"}, {"id": "steam:2"}, {"id": "steam:3"}, {"id": "flatpak:x"}]
raiz = catalogo.raiz_steam()
os.environ["PATH"] = falsos + ":/usr/bin:/bin"   # sin mangohud en el PATH...
if os.path.exists(os.path.join(falsos, "mangohud")):
    os.remove(os.path.join(falsos, "mangohud"))
import shutil
r["con_mangohud_del_sistema"] = bool(shutil.which("mangohud"))
os.environ["PATH"] = falsos + ":/bin-que-no-existe"
r["sin_binario"] = mg.juegos_sin_mangohud(raiz, escribir=True)
r["intacto_sin_binario"] = open(os.path.join(loc, "localconfig.vdf")).read() == TEXTO
open(os.path.join(falsos, "mangohud"), "w").write("#!/bin/sh\n"); os.chmod(os.path.join(falsos, "mangohud"), 0o755)
os.makedirs(os.path.dirname(catalogo.config_usuario()), exist_ok=True)
json.dump({"mangohud_lanzamiento": False}, open(catalogo.config_usuario(), "w"))
r["apagado"] = mg.juegos_sin_mangohud(raiz, escribir=True)
os.remove(catalogo.config_usuario())
r["con_binario"] = mg.juegos_sin_mangohud(raiz, escribir=True)
r["escrito"] = catalogo.vdf(open(os.path.join(loc, "localconfig.vdf")).read())[
    "userlocalconfigstore"]["software"]["valve"]["steam"]["apps"]["2"].get("launchoptions")
r["despues"] = mg.juegos_sin_mangohud(raiz)
print(json.dumps(r))
PY
codigo=$?
R() { python3 -c 'import json,sys; R=json.load(open(sys.argv[1])); print(eval(sys.argv[2]))' "$TMP/casos.txt" "$1"; }

titulo "0. Corre"
afirmar_igual "0" "$codigo" "el guion de casos sale con 0"
afirmar "   sin nada por stderr" test ! -s "$TMP/casos.err"
[ -s "$TMP/casos.err" ] && sed 's/^/      /' "$TMP/casos.err"

titulo "1-3. Que se pone y donde"
afirmar_igual "['1', '2', '4']" "$(R 'R["puestos"]')" "a los vacios, al sin clave y al sin bloque"
afirmar_igual "mangohud %command%" "$(R 'R["opciones"]["1"]')" "   el vacio"
afirmar_igual "mangohud %command%" "$(R 'R["opciones"]["2"]')" "   el que no tenia la clave"
afirmar_igual "mangohud %command%" "$(R 'R["opciones"]["4"]')" "   el que no tenia bloque"
afirmar_igual "PROTON_LOG=1 %command%" "$(R 'R["opciones"]["3"]')" "lo escrito por el usuario no se toca"
afirmar_igual "['10', '5']" "$(R 'R["playtime"]')" "lo demas del juego sigue ahi"
afirmar_igual "{'1': 'x'}" "$(R 'R["otro"]')" "un bloque que no es «apps» no se toca"
afirmar_igual "[]" "$(R 'R["segunda"]')" "una segunda pasada no cambia nada"
afirmar_igual "[]" "$(R 'R["sin_apps"]')" "sin bloque apps, nada"

titulo "4-5. Cuando NO se escribe"
afirmar_igual "[]" "$(R 'R["sin_binario"]')" "sin el binario mangohud no se pone en ninguno"
afirmar_igual "True" "$(R 'R["intacto_sin_binario"]')" "   y el fichero queda igual"
afirmar_igual "[]" "$(R 'R["apagado"]')" "con \"mangohud_lanzamiento\": false, tampoco"
afirmar_igual "['1', '2']" "$(R 'R["con_binario"]')" "con mangohud: los juegos de Steam (no el flatpak)"
afirmar_igual "mangohud %command%" "$(R 'R["escrito"]')" "   y queda escrito en localconfig.vdf"
afirmar_igual "[]" "$(R 'R["despues"]')" "   y ya no falta en ninguno"

afirmar_intacta_la_casa_real
resumen
