#!/usr/bin/env bash
# tests/unidad/remoto.sh — Celiuz Remoto (remoto/), lo que ya existe del
# servicio: su CLI, y que todo lo suyo vive FUERA del repo.
#
# POR QUE: el remoto guarda claves, telefonos y un historial. Eso es de cada
# equipo (la regla de oro del CLAUDE.md), y con un $HOME de mentira tiene que
# caer dentro de esa casa, no en la de verdad ni en el repo.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
CLI="$REPO/remoto/servidor/celiuz-remoto.py"

titulo "1. revisar dice que falta, sin fallar"
salida="$("$CLI" revisar --json 2>"$TMP/err")"; codigo=$?
afirmar_igual "0" "$codigo" "sale con 0 aunque falten cosas (que falte es la respuesta)"
afirmar "   sin nada por stderr" test ! -s "$TMP/err"
afirmar "   es json con necesidades y faltan" python3 -c '
import json, sys
d = json.loads(sys.argv[1])
assert {n["que"] for n in d["necesidades"]} >= {"tailscale", "aiohttp", "adb"}
assert all(n["paquete"] in d["faltan"] for n in d["necesidades"] if not n["hay"])
' "$salida"

# Sin tailscale ni adb en el PATH, los dos tienen que salir como que faltan
mkdir -p "$TMP/vacio"
salida="$(PATH="$TMP/vacio" /usr/bin/python3 "$CLI" revisar --json 2>/dev/null)"
afirmar "   sin tailscale ni adb en el PATH, salen en «faltan»" python3 -c '
import json, sys
f = json.loads(sys.argv[1])["faltan"]
assert "tailscale" in f and "android-tools" in f, f
' "$salida"

titulo "2. Lo suyo vive fuera del repo, en la casa de quien lo corre"
salida="$("$CLI" rutas --json 2>"$TMP/err")"; codigo=$?
afirmar_igual "0" "$codigo" "rutas sale con 0"
afirmar "   todas dentro del \$HOME de mentira" python3 -c '
import json, os, sys
casa, repo = os.path.realpath(sys.argv[2]), os.path.realpath(sys.argv[3])
for clave, ruta in json.loads(sys.argv[1]).items():
    r = os.path.realpath(ruta)
    assert r.startswith(casa + os.sep), (clave, r)
    assert not r.startswith(repo + os.sep), (clave, r)
' "$salida" "$HOME" "$REPO"

titulo "3. Lo que aun no existe lo dice, y no hace nada"
"$CLI" servir >/dev/null 2>"$TMP/err"; codigo=$?
afirmar_igual "2" "$codigo" "servir: todavia no existe, sale con 2"
afirmar_contiene "$TMP/err" "fase 1" "   y dice de que fase es"
afirmar "   sin crear nada en la casa" test ! -e "$HOME/.local/state/celiuz/remoto"

afirmar_intacta_la_casa_real
resumen
