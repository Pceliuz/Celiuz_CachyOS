#!/usr/bin/env bash
# tests/e2e/remoto-invitacion.sh — Celiuz Remoto, fase 8: ayudar a un amigo.
# Entrar SIN cable con una invitacion de un solo uso. Servidor de verdad,
# celular de mentira.
#
# POR QUE: es el unico camino para entrar sin el cable, asi que todo lo que lo
# hace pequeño tiene que cumplirse:
#   1. solo la abre la PC (el socket de control), nunca alguien de fuera;
#   2. el codigo vale una vez, 15 min, y cinco codigos mal la QUEMAN;
#   3. lo que entra tiene los permisos que dio la PC, y nada mas;
#   4. y CADUCA: a su hora ya no entra, y una sesion abierta deja de valer.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
igual() { afirmar_igual "$2" "$3" "$1"; }
CLI="$REPO/remoto/servidor/celiuz-remoto.py"
TEL="$REPO/tests/lib/telefono_falso.py"
esperar_a() {
    local limite=$(( $(date +%s%N) + $1 * 1000000000 )); shift
    while [ "$(date +%s%N)" -lt "$limite" ]; do
        "$@" >/dev/null 2>&1 && return 0
        sleep 0.1
    done
    "$@" >/dev/null 2>&1
}
campo() { python3 -c 'import json,sys; d=json.loads(sys.argv[1]); print(eval(sys.argv[2]))' "$1" "$2"; }
puerto_libre() { python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])'; }
RED="$(puerto_libre)"; USB="$(puerto_libre)"
mkdir -p "$XDG_CONFIG_HOME/celiuz"
printf 'puerto_red = %s\npuerto_usb = %s\n' "$RED" "$USB" > "$XDG_CONFIG_HOME/celiuz/remoto.conf"
binario_falso tailscale 0 'case "$*" in "ip -4") echo 127.0.0.1 ;; *) echo "{\"Peer\":{}}" ;; esac'
binario_falso systemctl 0
binario_falso pgrep 1
binario_falso notify-send 0
binario_falso loginctl 0 'echo "[]"'

"$CLI" servir 2>"$TMP/servidor.log" &
PID_SERVIDOR=$!
trap 'kill $PID_SERVIDOR 2>/dev/null; wait $PID_SERVIDOR 2>/dev/null; limpiar_entorno' EXIT INT TERM
esta_arriba() { test -S "$XDG_RUNTIME_DIR/celiuz-remoto.sock"; }
esperar_a 10 esta_arriba
B="http://127.0.0.1:$RED"
control() { python3 - "$REPO/remoto/servidor" "$@" <<'FINPY'
import json, sys
sys.path.insert(0, sys.argv[1])
from celiuz_remoto import control
cuerpo = json.loads(sys.argv[4]) if len(sys.argv) > 4 else None
codigo, d = control.pedir(sys.argv[2], sys.argv[3], cuerpo, timeout=20)
print(json.dumps({"http": codigo, "cuerpo": d}, ensure_ascii=False))
FINPY
}
pedir() { "$TEL" pedir "$@"; }

titulo "1. Sin invitación abierta, nada"
r="$("$TEL" invitacion "$RED" AAAA-BBBB-CCCC-DDDD "$TMP/nadie")"
igual "un código cualquiera: 401 (como una firma mala)" "401" "$(campo "$r" 'd["http"]')"

titulo "2. La abre la PC, con sus permisos y sus horas"
r="$(control POST /control/invitacion '{"horas": 3}')"
igual "horas que no se ofrecen: 400" "400" "$(campo "$r" 'd["http"]')"
r="$(control POST /control/invitacion '{"permisos": ["estado","inventado"]}')"
igual "un permiso que no existe: 400" "400" "$(campo "$r" 'd["http"]')"
r="$(control POST /control/invitacion '{"horas": 1}')"
igual "abierta" "abierta" "$(campo "$r" 'd["cuerpo"]["estado"]')"
igual "de fábrica: estado, ventanas y pantalla (sin apagar, archivos ni terminal)" \
    "['estado', 'ventanas', 'pantalla']" "$(campo "$r" 'd["cuerpo"]["permisos"]')"
CODIGO="$(campo "$r" 'd["cuerpo"]["codigo"]')"
CLAVE="$(campo "$r" 'd["cuerpo"]["contrasena"]')"
afirmar "el código: 16 letras en grupos de 4, sin 0/O ni 1/I/L" python3 -c 'import re,sys; assert re.fullmatch(r"[A-HJKMNP-Z2-9]{4}(-[A-HJKMNP-Z2-9]{4}){3}", sys.argv[1]), sys.argv[1]' "$CODIGO"
afirmar "y un texto para mandar, con dirección, código y contraseña" python3 -c 'import json,sys; t=json.loads(sys.argv[1])["cuerpo"]["texto"]; assert sys.argv[2] in t and sys.argv[3] in t and "127.0.0.1:" in t, t' "$r" "$CODIGO" "$CLAVE"

titulo "3. Cinco códigos mal la queman"
for i in 1 2 3 4; do "$TEL" invitacion "$RED" "ZZZZ-ZZZZ-ZZZZ-ZZZ$i" "$TMP/malo" >/dev/null; done
r="$(control GET /control/invitacion)"
igual "con cuatro, sigue abierta" "abierta" "$(campo "$r" 'd["cuerpo"]["estado"]')"
"$TEL" invitacion "$RED" "ZZZZ-ZZZZ-ZZZZ-ZZZ5" "$TMP/malo" >/dev/null
igual "con el quinto, quemada" "quemada" "$(campo "$(control GET /control/invitacion)" 'd["cuerpo"]["estado"]')"
igual "y ni el bueno entra ya" "401" "$(campo "$("$TEL" invitacion "$RED" "$CODIGO" "$TMP/amigo")" 'd["http"]')"
afirmar "la PC avisa" grep -q "invitación cancelada" "$REGISTRO/notify-send.log"

titulo "4. Con la buena: entra, con lo que dio la PC y nada más"
r="$(control POST /control/invitacion '{"horas": 2, "permisos": ["estado","pantalla"]}')"
CODIGO="$(campo "$r" 'd["cuerpo"]["codigo"]')"; CLAVE="$(campo "$r" 'd["cuerpo"]["contrasena"]')"
minus="$(echo "$CODIGO" | tr 'A-Z' 'a-z' | tr -d '-' | sed 's/..../& /g')"
r="$("$TEL" invitacion "$RED" "$minus" "$TMP/amigo" Rodrigo)"
igual "el código en minúsculas y con espacios vale igual: 200" "200" "$(campo "$r" 'd["http"]')"
igual "  sus permisos" "['estado', 'pantalla']" "$(campo "$r" 'd["cuerpo"]["permisos"]')"
afirmar "  y caduca (expira) en unas 2 h, con el pase igual" python3 -c '
import datetime as dt, json, sys
d = json.loads(sys.argv[1])["cuerpo"]
e = dt.datetime.fromisoformat(d["expira"]); ahora = dt.datetime.now().astimezone()
assert 7100 < (e - ahora).total_seconds() <= 7200 and d["pase_hasta"] == d["expira"], d' "$r"
igual "la misma invitación otra vez: 401 (un solo uso)" "401" "$(campo "$("$TEL" invitacion "$RED" "$CODIGO" "$TMP/otro")" 'd["http"]')"
r="$("$TEL" entrar "$RED" "$TMP/amigo" "$CLAVE")"
igual "entra con la contraseña de la invitación" "200" "$(campo "$r" 'd["http"]')"
TOKEN="$(campo "$r" 'd["cuerpo"]["token"]')"
igual "  ve el estado" "200" "$(campo "$(pedir GET "$B/v0/equipo" "$TOKEN")" 'd["http"]')"
igual "  pero no apaga (sin permiso de energía)" "403" \
    "$(campo "$(python3 -c "
import json,sys; sys.path.insert(0,'$REPO/tests/lib')
from telefono_falso import pedir
print(json.dumps({'http': pedir('POST','$B/v0/energia',{'accion':'apagar','confirmado':True},'$TOKEN')[0]}))")" 'd["http"]')"
igual "  ni mira archivos" "403" "$(campo "$(pedir GET "$B/v0/archivos?ruta=" "$TOKEN")" 'd["http"]')"
afirmar "la PC avisa de que entró" grep -q "entró un invitado" "$REGISTRO/notify-send.log"
afirmar "y se ve en la lista, marcado como invitado" sh -c "'$CLI' dispositivos | grep -q 'Rodrigo (invitado)'"

titulo "5. A su hora, caduca: ni entra ni sigue dentro"
DISP="$(cat "$TMP/amigo/dispositivo")"
python3 - "$XDG_STATE_HOME/celiuz/remoto/dispositivos.json" "$DISP" <<'FINPY'
import datetime as dt, json, sys
p, ident = sys.argv[1], sys.argv[2]
d = json.load(open(p))
d["dispositivos"][ident]["expira"] = (dt.datetime.now().astimezone() - dt.timedelta(minutes=1)).isoformat(timespec="seconds")
json.dump(d, open(p, "w"))
FINPY
igual "la sesión abierta deja de valer: 401" "401" "$(campo "$(pedir GET "$B/v0/equipo" "$TOKEN")" 'd["http"]')"
igual "y entrar otra vez: 401" "401" "$(campo "$("$TEL" entrar "$RED" "$TMP/amigo" "$CLAVE")" 'd["http"]')"
borrado() { ! "$CLI" dispositivos | grep -q Rodrigo; }
esperar_a 75 borrado
afirmar "y se borra solo de la lista (en la siguiente vuelta, ≤ 60 s)" borrado

afirmar "el servidor no se quejo" sh -c "! grep -q Traceback '$TMP/servidor.log'"
afirmar_intacta_la_casa_real
resumen
