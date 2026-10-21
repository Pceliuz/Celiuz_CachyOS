#!/usr/bin/env bash
# tests/e2e/remoto.sh — Celiuz Remoto de punta a punta: el servidor DE VERDAD
# contra un celular de mentira (tests/lib/telefono_falso.py).
#
# POR QUE: lo que protege a la PC (la firma de cada celular, la contraseña con
# sus 5 intentos, el pase que solo da el cable, revocar al instante) solo se
# prueba de verdad atacandolo. Cada bloque es una forma de intentar entrar sin
# derecho, y lo que se mira es que NO entre.
#
# Sin red ni Tailscale: `tailscale` es de mentira y contesta 127.0.0.1, que el
# servidor acepta (es de bucle local) igual que una 100.x. Los puertos son
# libres al azar, puestos en el remoto.conf de la casa de mentira, para no
# chocar con un servicio de verdad que este corriendo en esta PC.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
CLI="$REPO/remoto/servidor/celiuz-remoto.py"
TEL="$REPO/tests/lib/telefono_falso.py"
binario_falso notify-send 0

# campo <json> <expresion python sobre d>
campo() { python3 -c 'import json,sys; d=json.loads(sys.argv[1]); print(eval(sys.argv[2]))' "$1" "$2"; }

esperar_a() {
    local limite=$(( $(date +%s%N) + $1 * 1000000000 )); shift
    while [ "$(date +%s%N)" -lt "$limite" ]; do
        "$@" >/dev/null 2>&1 && return 0
        sleep 0.1
    done
    "$@" >/dev/null 2>&1
}
puerto_libre() { python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])'; }
RED="$(puerto_libre)"; USB="$(puerto_libre)"
mkdir -p "$XDG_CONFIG_HOME/celiuz"
printf 'puerto_red = %s\npuerto_usb = %s\n' "$RED" "$USB" > "$XDG_CONFIG_HOME/celiuz/remoto.conf"
SOCK="$XDG_RUNTIME_DIR/celiuz-remoto.sock"

titulo "1. Solo escucha por Tailscale"
binario_falso tailscale 1 'echo "Tailscale is stopped." >&2'
"$CLI" servir >/dev/null 2>"$TMP/err"; codigo=$?
afirmar_igual "1" "$codigo" "sin Tailscale conectado no arranca (sale con 1, para que systemd reintente)"
afirmar_contiene "$TMP/err" "tailscale no está conectado" "   y dice por qué"

binario_falso tailscale 0 'echo 192.168.1.40'
"$CLI" servir >/dev/null 2>"$TMP/err"; codigo=$?
afirmar_igual "1" "$codigo" "una IP que no es de Tailscale (192.168.1.40) la rechaza aunque la diga tailscale"
afirmar "   y no deja el socket de control" test ! -e "$SOCK"

binario_falso tailscale 0 'echo 127.0.0.1'
"$CLI" servir 2>"$TMP/servidor.log" &
PID_SERVIDOR=$!
trap 'kill $PID_SERVIDOR 2>/dev/null; wait $PID_SERVIDOR 2>/dev/null; limpiar_entorno' EXIT INT TERM
esta_arriba() { test -S "$SOCK"; }
esperar_a 10 esta_arriba
afirmar "con la IP de Tailscale arranca y abre el socket de control" test -S "$SOCK"
afirmar_igual "600" "$(stat -c %a "$SOCK" 2>/dev/null)" "   el socket de control es solo del usuario (0600)"
salida="$("$CLI" estado --json 2>&1)"
afirmar_igual "127.0.0.1:$RED" "$(campo "$salida" 'd["red"]')" "   estado dice dónde escucha"

titulo "2. El canal USB solo está abierto mientras se empareja"
r="$("$TEL" pedir GET "http://127.0.0.1:$USB/usb/hola" 2>&1)"
afirmar "sin emparejar, el puerto USB ni contesta" python3 -c 'import sys; assert "Connection refused" in sys.argv[1] or "URLError" in sys.argv[1], sys.argv[1]' "$r"

echo "clave-de-prueba" | "$CLI" emparejar --sin-adb --nombre "Mi celular" > "$TMP/emparejar.out" 2>"$TMP/emparejar.err" &
PID_EMP=$!
hay_codigo() { grep -q '^CODIGO ' "$TMP/emparejar.out"; }
esperar_a 10 hay_codigo
CODIGO="$(sed -n 's/^CODIGO //p' "$TMP/emparejar.out")"
afirmar "emparejar abre la ventana y da un código" test -n "$CODIGO"
r="$("$TEL" pedir GET "http://127.0.0.1:$USB/usb/hola")"
afirmar_igual "emparejar" "$(campo "$r" 'd["cuerpo"]["modo"]')" "   /usb/hola dice que toca emparejar"

r="$("$TEL" emparejar "$USB" "codigo-inventado" "$TMP/intruso")"
afirmar_igual "401" "$(campo "$r" 'd["http"]')" "otra app del celular sin el código no se empareja"
r="$("$TEL" pedir GET "http://127.0.0.1:$USB/usb/hola")"
afirmar_igual "200" "$(campo "$r" 'd["http"]')" "   y su intento no cierra la ventana al bueno"

r="$("$TEL" emparejar "$USB" "$CODIGO" "$TMP/tel")"
afirmar_igual "200" "$(campo "$r" 'd["http"]')" "con el código, el celular se empareja"
afirmar_igual "127.0.0.1:$RED" "$(campo "$r" 'd["cuerpo"]["direccion"]')" "   y se lleva la dirección de la red"
afirmar_igual "['estado', 'energia']" "$(campo "$r" 'd["cuerpo"]["permisos"]')" "   con los permisos de fábrica: ver y apagar"
wait $PID_EMP; codigo=$?
afirmar_igual "0" "$codigo" "   la CLI que esperaba termina bien"
DISP="$(cat "$TMP/tel/dispositivo")"

r="$("$TEL" emparejar "$USB" "$CODIGO" "$TMP/otro")"
afirmar "el código no vale dos veces (el canal ya se cerró)" python3 -c 'import sys; assert "refused" in sys.argv[1] or "\"http\": 404" in sys.argv[1], sys.argv[1]' "$r"

ALMACEN="$XDG_STATE_HOME/celiuz/remoto/dispositivos.json"
afirmar_igual "600" "$(stat -c %a "$ALMACEN")" "dispositivos.json es 0600"
afirmar_no_contiene "$ALMACEN" "clave-de-prueba" "   y no lleva la contraseña, solo su hash"
afirmar_contiene "$ALMACEN" "\"nombre\": \"Mi celular\"" "   el nombre lo pone la PC"
PUBLICA="$(python3 -c 'import sys; sys.path.insert(0,sys.argv[1]); from telefono_falso import Telefono; print(Telefono(sys.argv[2]).publica)' "$REPO/tests/lib" "$TMP/tel")"
# grep -F: el base64 lleva «+», que para afirmar_contiene (grep -E) es un cuantificador
afirmar "   guarda la clave PÚBLICA del celular (la privada no salió de él)" grep -qF -- "$PUBLICA" "$ALMACEN"

titulo "2b. Por el cable: adb reverse, el código por intent explícito, y cerrar al acabar"
# adb de mentira con UN celular: contesta a la sonda y, cuando la PC abre la
# app con el código, hace lo que haría la app de verdad (emparejarse).
# `adb shell` de verdad se COME la entrada de quien lo llama: el de mentira
# tambien, para que la contraseña por stdin de la CLI no llegue si adb la hereda
# (paso emparejando el HONOR el 2026-10-20: «al menos 4 caracteres»).
binario_falso adb 0 '
case "$*" in
    "devices -l") printf "List of devices attached\nSERIE123 device usb:1-1 model:Celu_Prueba\n" ;;
    *"shell echo"*) cat > /dev/null; printf "nombre=null\ncomercial=Celu Prueba\nandroid=14\ntailscale=package:/x\napp=    versionName=0.1.0\n" ;;
    *"am start"*)
        uri="${*##* -d }"; uri="${uri%%\?p=*}"; codigo="${uri##*/}"
        echo "$*" | grep -q "?p='"$USB"'$" || echo "SIN PUERTO" >> "'"$TMP"'/cable.json"
        "'"$TEL"'" emparejar "'"$USB"'" "$codigo" "'"$TMP"'/cable" > "'"$TMP"'/cable.json" 2>&1 &
        echo "Starting: Intent" ;;
esac'
echo "otra-clave" | "$CLI" emparejar > "$TMP/cable.out" 2> "$TMP/cable.err"; codigo=$?
afirmar_igual "0" "$codigo" "emparejar por el cable termina bien"
afirmar_contiene "$REGISTRO/adb.log" "^-s SERIE123 reverse tcp:$USB tcp:$USB$" "   abre el adb reverse al puerto USB"
afirmar_contiene "$REGISTRO/adb.log" "^-s SERIE123 shell am start -n com.celiuz.remoto/.MainActivity " \
    "   abre NUESTRA app con un intent explícito (-n), no cualquiera que entienda el esquema"
afirmar_no_contiene "$TMP/cable.json" "SIN PUERTO" "   y le pasa el puerto USB en el enlace (?p=), que en la PC se puede cambiar"
afirmar_contiene "$REGISTRO/adb.log" "^-s SERIE123 reverse --remove tcp:$USB$" "   y cierra el canal al acabar"
afirmar_igual "SERIE123" "$(campo "$(cat "$ALMACEN")" '[x["serie"] for x in d["dispositivos"].values() if x["nombre"]=="Celu Prueba"][0]')" \
    "   el teléfono queda con su serie USB (para reconocerlo al enchufarlo)"
# El puerto se suelta 0,2 s después de contestar (para no cortar la respuesta)
# A una variable y no a una tuberia: con pipefail, el telefono que sale con 1
# al no poder conectar haria fallar el `| grep` aunque casara.
usb_cerrado() { local s; s="$("$TEL" pedir GET "http://127.0.0.1:$USB/usb/hola" 2>&1)"; [[ "$s" == *refused* ]]; }
afirmar "   y el puerto USB se suelta del todo" esperar_a 3 usb_cerrado

# Si el celular no contesta (la app no hace nada), el canal se cierra igual
: > "$REGISTRO/adb.log"
binario_falso adb 0 '
case "$*" in
    "devices -l") printf "List of devices attached\nSERIE123 device usb:1-1 model:Celu_Prueba\n" ;;
    *"shell echo"*) printf "comercial=Celu Prueba\napp=    versionName=0.1.0\n" ;;
    *"am start"*) echo "Error: Activity class does not exist." ;;
esac'
echo "otra-clave" | "$CLI" emparejar > /dev/null 2> "$TMP/cable.err"; codigo=$?
afirmar_igual "1" "$codigo" "si la app del celular no abre, emparejar falla"
afirmar_contiene "$TMP/cable.err" "no pude abrir la app" "   diciendo por qué"
afirmar_contiene "$REGISTRO/adb.log" "reverse --remove tcp:$USB$" "   y aun así cierra el canal"
r="$("$CLI" estado --json)"
afirmar_igual "None" "$(campo "$r" 'd["ventana"]')" "   y la ventana USB (no se queda 2 minutos abierta)"

# Sin la app instalada, ni lo intenta
binario_falso adb 0 '
case "$*" in
    "devices -l") printf "List of devices attached\nSERIE123 device usb:1-1 model:Celu_Prueba\nOTRO unauthorized usb:2-1\n" ;;
    *"shell echo"*) printf "comercial=Celu Prueba\napp=\n" ;;
esac'
echo "otra-clave" | "$CLI" emparejar --celular SERIE123 > /dev/null 2> "$TMP/cable.err"; codigo=$?
afirmar_igual "1" "$codigo" "sin la app en el celular no abre nada"
afirmar_contiene "$TMP/cable.err" "no tiene la app" "   y lo dice"
echo "otra-clave" | "$CLI" emparejar --celular OTRO > /dev/null 2> "$TMP/cable.err"
afirmar_contiene "$TMP/cable.err" "no ha autorizado la depuración USB" "un celular sin autorizar: dice que toque «Permitir»"
binario_falso adb 0

titulo "3. Entrar: firma primero, contraseña después"
echo 0123456789abcdef > "$TMP/intruso/dispositivo"   # un id que no existe
r="$("$TEL" entrar "$RED" "$TMP/intruso" "clave-de-prueba")"
afirmar_igual "401 firma" "$(campo "$r" 'd["http"]') $(campo "$r" 'd["cuerpo"]["error"]')" \
    "un celular sin emparejar no entra ni con la contraseña buena"

# Otro celular que se hace pasar por el bueno (sabe su id, no su clave)
r="$(python3 - "$REPO/tests/lib" "$TMP/intruso" "$RED" "$DISP" <<'PY'
import json, sys
sys.path.insert(0, sys.argv[1])
from telefono_falso import Telefono
t = Telefono(sys.argv[2])
buena = t.entrar(int(sys.argv[3]), "clave-de-prueba", ident=sys.argv[4])[0]
# Y con contraseñas MALAS: si se mirara la contraseña antes que la firma,
# esto le gastaria los intentos al bueno hasta bloquearlo.
malas = [t.entrar(int(sys.argv[3]), "mal", ident=sys.argv[4])[0] for _ in range(6)]
print(json.dumps([buena] + malas))
PY
)"
afirmar_igual "[401, 401, 401, 401, 401, 401, 401]" "$r" "sabiendo el id del bueno pero sin su clave, tampoco"
afirmar_igual "0" "$(campo "$(cat "$ALMACEN")" 'd["dispositivos"]["'"$DISP"'"]["fallos"]')" \
    "   y una firma mala NO le gasta intentos al bueno (si no, se le podría bloquear adrede)"

r="$(python3 - "$REPO/tests/lib" "$RED" "$DISP" "$TMP/tel" <<'PY'
import json, sys
sys.path.insert(0, sys.argv[1])
from telefono_falso import Telefono, pedir
t = Telefono(sys.argv[4]); base = f"http://127.0.0.1:{sys.argv[2]}"
_, r = pedir("GET", f"{base}/v0/reto?dispositivo={sys.argv[3]}")
cuerpo = {"dispositivo": sys.argv[3], "reto": r["reto"],
          "firma": t.firmar("sesion", r["reto"]), "contrasena": "clave-de-prueba"}
uno = pedir("POST", f"{base}/v0/sesion", cuerpo)[0]
dos = pedir("POST", f"{base}/v0/sesion", cuerpo)[0]
# Y una firma de OTRA cosa (la de emparejar) no vale para entrar
_, r = pedir("GET", f"{base}/v0/reto?dispositivo={sys.argv[3]}")
tres = pedir("POST", f"{base}/v0/sesion", dict(cuerpo, reto=r["reto"],
             firma=t.firmar("emparejar", r["reto"])))[0]
print(json.dumps([uno, dos, tres]))
PY
)"
afirmar_igual "[200, 401, 401]" "$r" "un reto vale una sola vez, y una firma de otra cosa no sirve para entrar"

r="$("$TEL" entrar "$RED" "$TMP/tel" "mal")"
afirmar_igual "401 contrasena 4" "$(campo "$r" 'd["http"]') $(campo "$r" 'd["cuerpo"]["error"]') $(campo "$r" 'd["cuerpo"]["intentos_restantes"]')" \
    "contraseña mal: 401 y cuántos intentos quedan"
r="$("$TEL" entrar "$RED" "$TMP/tel" "clave-de-prueba")"
afirmar_igual "200" "$(campo "$r" 'd["http"]')" "con la buena, entra"
TOKEN="$(campo "$r" 'd["cuerpo"]["token"]')"
afirmar "   recién emparejado ya tiene su pase de 24 h (cable + contraseña recién creada)" test "$(campo "$r" 'd["cuerpo"]["pase_hasta"] is not None')" = True
afirmar_igual "0" "$(campo "$(cat "$ALMACEN")" 'd["dispositivos"]["'"$DISP"'"]["fallos"]')" \
    "   y entrar bien pone los fallos a cero"

titulo "4. El estado del equipo"
r="$("$TEL" pedir GET "http://127.0.0.1:$RED/v0/equipo")"
afirmar_igual "401 sin_sesion" "$(campo "$r" 'd["http"]') $(campo "$r" 'd["cuerpo"]["error"]')" "sin token, nada"
r="$("$TEL" pedir GET "http://127.0.0.1:$RED/v0/equipo" "token-inventado")"
afirmar_igual "401" "$(campo "$r" 'd["http"]')" "con un token inventado, nada"
r="$("$TEL" pedir GET "http://127.0.0.1:$RED/v0/equipo" "$TOKEN")"
afirmar_igual "200" "$(campo "$r" 'd["http"]')" "con sesión, /v0/equipo contesta"
afirmar "   con nombre, cpu y ram" python3 -c '
import json, sys; d = json.loads(sys.argv[1])["cuerpo"]
assert d["nombre"] and d["cpu"] is not None and d["ram"] > 0 and d["protocolo"] == 0, d' "$r"

r="$("$TEL" vivo "$RED" "$TOKEN" 2)"
afirmar "/v0/vivo manda el estado cada segundo" python3 -c '
import json, sys; d = json.loads(sys.argv[1])
assert d["http"] == 101 and len(d["mensajes"]) == 2, d
m = d["mensajes"][1]
assert 0 <= m["cpu"]["uso"] <= 100 and m["ram"][1] > 0 and m["disco"][1] > 0, m
assert {"bajada", "subida"} <= m["red"].keys() and "encendida_desde" in m, m
assert m["pase_hasta"] is not None and m["vigilancia"] == "desarmada", m' "$r"
r="$("$TEL" vivo "$RED" "token-inventado" 1)"
afirmar_igual "401" "$(campo "$r" 'd["http"]')" "   sin sesión el WebSocket ni se abre"

"$CLI" permisos "$DISP" -estado >/dev/null
r="$("$TEL" pedir GET "http://127.0.0.1:$RED/v0/equipo" "$TOKEN")"
afirmar_igual "403 sin_permiso" "$(campo "$r" 'd["http"]') $(campo "$r" 'd["cuerpo"]["error"]')" \
    "quitarle el permiso desde la PC vale al instante, con la sesión abierta"
"$CLI" permisos "$DISP" +estado >/dev/null

titulo "5. Cinco contraseñas mal y queda bloqueado"
for i in 1 2 3 4; do "$TEL" entrar "$RED" "$TMP/tel" "mal-$i" >/dev/null; done
afirmar_igual "0" "$(veces_llamado notify-send)" "cuatro fallos todavía no avisan en la PC"
r="$("$TEL" entrar "$RED" "$TMP/tel" "mal-5")"
afirmar_igual "403 bloqueado" "$(campo "$r" 'd["http"]') $(campo "$r" 'd["cuerpo"]["error"]')" "el 5.º lo bloquea"
afirmar_igual "1" "$(veces_llamado notify-send)" "   y avisa en la PC (una vez)"
r="$("$TEL" entrar "$RED" "$TMP/tel" "clave-de-prueba")"
afirmar_igual "403" "$(campo "$r" 'd["http"]')" "   bloqueado, ni con la buena"
r="$("$TEL" pedir GET "http://127.0.0.1:$RED/v0/equipo" "$TOKEN")"
afirmar_igual "401" "$(campo "$r" 'd["http"]')" "   y la sesión que tenía abierta se cae"
afirmar_igual "1" "$(veces_llamado notify-send)" "   más intentos no repiten el aviso"
"$CLI" desbloquear "$DISP" >/dev/null
r="$("$TEL" entrar "$RED" "$TMP/tel" "clave-de-prueba")"
afirmar_igual "200" "$(campo "$r" 'd["http"]')" "desbloqueado desde la PC, vuelve a entrar"
TOKEN="$(campo "$r" 'd["cuerpo"]["token"]')"

titulo "6. El pase: solo por cable y con la contraseña"
"$CLI" renovar --sin-adb > "$TMP/renovar.out" 2>/dev/null &
PID_REN=$!
hay_codigo_r() { grep -q '^CODIGO ' "$TMP/renovar.out"; }
esperar_a 10 hay_codigo_r
CODIGO="$(sed -n 's/^CODIGO //p' "$TMP/renovar.out")"
r="$("$TEL" renovar "$USB" "codigo-inventado" "$TMP/tel" "clave-de-prueba")"
afirmar_igual "401" "$(campo "$r" 'd["http"]')" "sin el código del cable no se renueva"
echo "$DISP" > "$TMP/intruso/dispositivo"   # se hace pasar por el bueno
r="$("$TEL" renovar "$USB" "$CODIGO" "$TMP/intruso" "clave-de-prueba")"
afirmar_igual "401" "$(campo "$r" 'd["http"]')" "con el código pero otro celular, tampoco"
r="$("$TEL" renovar "$USB" "$CODIGO" "$TMP/tel" "mal")"
afirmar_igual "401 contrasena" "$(campo "$r" 'd["http"]') $(campo "$r" 'd["cuerpo"]["error"]')" \
    "con cable y sin la contraseña, no (quien te quite el celular no se lleva 24 h)"
r="$("$TEL" renovar "$USB" "$CODIGO" "$TMP/tel" "clave-de-prueba")"
afirmar_igual "200" "$(campo "$r" 'd["http"]')" "cable + contraseña: renueva"
HASTA="$(campo "$r" 'd["cuerpo"]["pase_hasta"]')"
afirmar "   24 h exactas desde ahora, con el reloj de la PC" python3 -c '
import datetime as dt, sys
h = dt.datetime.fromisoformat(sys.argv[1]); falta = h - dt.datetime.now().astimezone()
assert dt.timedelta(hours=23, minutes=59) < falta <= dt.timedelta(hours=24), falta' "$HASTA"
wait $PID_REN
r="$("$TEL" vivo "$RED" "$TOKEN" 1)"
afirmar_igual "$HASTA" "$(campo "$r" 'd["mensajes"][0]["pase_hasta"]')" "   y el estado en vivo ya lo dice"
"$CLI" quitar-pase "$DISP" >/dev/null
r="$("$TEL" vivo "$RED" "$TOKEN" 1)"
afirmar_igual "None" "$(campo "$r" 'd["mensajes"][0]["pase_hasta"]')" "quitar el pase desde la PC vale al instante"

titulo "7. Revocar corta al instante, también lo que está abierto"
"$TEL" vivo "$RED" "$TOKEN" 30 > "$TMP/vivo.json" &
PID_VIVO=$!
sleep 1.5
"$CLI" revocar "$DISP" >/dev/null
wait $PID_VIVO
r="$(cat "$TMP/vivo.json")"
afirmar "el WebSocket abierto se cierra con 4401" python3 -c '
import json, sys; d = json.loads(sys.argv[1]); assert d["cierre"] == 4401 and len(d["mensajes"]) < 30, d' "$r"
r="$("$TEL" entrar "$RED" "$TMP/tel" "clave-de-prueba")"
afirmar_igual "401 firma" "$(campo "$r" 'd["http"]') $(campo "$r" 'd["cuerpo"]["error"]')" \
    "   y ya no puede volver a entrar (contesta igual que a un desconocido)"

titulo "8. El registro apunta lo que pasó, sin secretos"
LOG="$XDG_STATE_HOME/celiuz/remoto/registro.jsonl"
afirmar_igual "600" "$(stat -c %a "$LOG")" "registro.jsonl es 0600"
for accion in emparejado entrar entrar_mal pase_renovado revocado; do
    afirmar_contiene "$LOG" "\"accion\": \"$accion\"" "   apunta «$accion»"
done
afirmar_no_contiene "$LOG" "clave-de-prueba" "   y ninguna contraseña"
afirmar_no_contiene "$LOG" "$TOKEN" "   ni ningún token"

titulo "9. Se apaga limpio"
kill -TERM "$PID_SERVIDOR"; wait "$PID_SERVIDOR"; codigo=$?
afirmar_igual "0" "$codigo" "con SIGTERM sale con 0"
afirmar "   y borra su socket de control" test ! -e "$SOCK"
afirmar_no_contiene "$TMP/servidor.log" "Traceback" "   sin un solo traceback en todo el rato"

afirmar_intacta_la_casa_real
resumen
