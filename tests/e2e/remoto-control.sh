#!/usr/bin/env bash
# tests/e2e/remoto-control.sh — Celiuz Remoto, fase 4: apagar con cuenta atras,
# ver y cerrar apps, el latido, y armar la vigilancia. Servidor de verdad,
# celular de mentira (tests/lib/telefono_falso.py).
#
# POR QUE: apagar es lo mas gordo que puede pedir el celular. Lo que se mira:
# que nada pasa sin confirmar, que la cuenta atras se cancela desde el celular
# Y desde la PC (y entonces systemctl NO se llama), que al acabar se piden
# cerrar las ventanas antes de apagar, y que cerrar apps pide el pase.
#
# systemctl, hyprctl y notify-send son de mentira. Hyprland tambien: un socket
# que solo acepta conexiones, para que el servidor crea que hay sesion.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
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
printf 'puerto_red = %s\npuerto_usb = %s\ncuenta_atras = 3\n' "$RED" "$USB" > "$XDG_CONFIG_HOME/celiuz/remoto.conf"

binario_falso tailscale 0 'case "$*" in "ip -4") echo 127.0.0.1 ;; *) echo "{\"Peer\":{}}" ;; esac'
binario_falso systemctl 0
binario_falso pgrep 0
# El aviso de la PC: con --wait se queda «abierto» hasta que lo cierran (o,
# si existe $TMP/pulsar, contesta «cancelar» como si se pulsara el boton).
binario_falso notify-send 0 'case "$*" in *--wait*)
    echo 4242
    if [ -e "'"$TMP"'/pulsar" ]; then sleep 1; echo cancelar; exit 0; fi
    sleep 30 ;; esac'
binario_falso gdbus 0
binario_falso hyprctl 0 'case "$*" in
    "clients -j") echo "[{\"address\":\"0xaaa\",\"class\":\"brave-browser\",\"title\":\"Frieren\",\"mapped\":true,\"workspace\":{\"id\":2,\"name\":\"2\"},\"pid\":11},
                    {\"address\":\"0xbbb\",\"class\":\"kitty\",\"title\":\"~/dotfiles\",\"mapped\":true,\"workspace\":{\"id\":1,\"name\":\"1\"},\"pid\":12}]" ;;
    "eval return 1") echo ok ;;
esac'

# Un Hyprland que solo atiende su socket (el servidor lo busca en caliente)
FIRMA="prueba_1792449598_1"
mkdir -p "$XDG_RUNTIME_DIR/hypr/$FIRMA"
python3 - "$XDG_RUNTIME_DIR/hypr/$FIRMA/.socket.sock" <<'FINPY' &
import socket, sys
s = socket.socket(socket.AF_UNIX); s.bind(sys.argv[1]); s.listen(16)
while True:
    s.accept()[0].close()
FINPY
PID_HYPR=$!

"$CLI" servir 2>"$TMP/servidor.log" &
PID_SERVIDOR=$!
trap 'kill $PID_SERVIDOR $PID_HYPR 2>/dev/null; wait $PID_SERVIDOR 2>/dev/null; limpiar_entorno' EXIT INT TERM
esta_arriba() { test -S "$XDG_RUNTIME_DIR/celiuz-remoto.sock"; }
esperar_a 10 esta_arriba

# Emparejar un celular con permiso de ventanas, y entrar
hay_codigo() { grep -q '^CODIGO ' "$1"; }
echo "clave-control" | "$CLI" emparejar --sin-adb --permisos estado,energia,ventanas > "$TMP/emp.out" 2>/dev/null &
esperar_a 10 hay_codigo "$TMP/emp.out"
"$TEL" emparejar "$USB" "$(sed -n 's/^CODIGO //p' "$TMP/emp.out")" "$TMP/tel" > /dev/null
wait $!
DISP="$(cat "$TMP/tel/dispositivo")"
TOKEN="$(campo "$("$TEL" entrar "$RED" "$TMP/tel" clave-control)" 'd["cuerpo"]["token"]')"
B="http://127.0.0.1:$RED"
pedir() { python3 - "$REPO/tests/lib" "$@" <<'FINPY'
import json, sys
sys.path.insert(0, sys.argv[1])
from telefono_falso import pedir
metodo, url, token = sys.argv[2], sys.argv[3], sys.argv[4]
cuerpo = json.loads(sys.argv[5]) if len(sys.argv) > 5 else None
http, c = pedir(metodo, url, cuerpo, token)
print(json.dumps({"http": http, "cuerpo": c}))
FINPY
}
llamadas() { grep -c "$1" "$REGISTRO/systemctl.log" 2>/dev/null || echo 0; }

titulo "1. Apagar: nada sin confirmar, y se cancela desde el celular"
r="$(pedir POST "$B/v0/energia" "$TOKEN" '{"accion":"apagar"}')"
afirmar_igual "409 confirmar" "$(campo "$r" 'd["http"]') $(campo "$r" 'd["cuerpo"]["error"]')" "sin «confirmado» no hace nada"
r="$(pedir POST "$B/v0/energia" "$TOKEN" '{"accion":"formatear","confirmado":true}')"
afirmar_igual "400" "$(campo "$r" 'd["http"]')" "una acción que no existe, 400"
r="$(pedir POST "$B/v0/energia" "$TOKEN" '{"accion":"apagar","confirmado":true}')"
afirmar_igual "200 3" "$(campo "$r" 'd["http"]') $(campo "$r" 'd["cuerpo"]["cuenta_atras"]')" "con confirmar: cuenta atrás (3 s en esta prueba)"
afirmar_contiene "$REGISTRO/notify-send.log" "--wait.*--action=cancelar=Cancelar.*La PC se apagará en 3 s" \
    "   y en la PC sale el aviso con su botón Cancelar"
r="$("$TEL" vivo "$RED" "$TOKEN" 1)"
afirmar_igual "apagar" "$(campo "$r" 'd["mensajes"][0]["energia"]["accion"]')" "   el estado en vivo lo dice (para la cuenta atrás de la app)"
r="$(pedir DELETE "$B/v0/energia" "$TOKEN")"
afirmar_igual "True" "$(campo "$r" 'd["cuerpo"]["cancelada"]')" "el celular lo cancela"
# 3 s de cuenta + 5 de esperar a que se cierren las ventanas: pasado eso, si
# la cancelacion no hubiera parado nada, ya se habria apagado.
sleep 9
afirmar_igual "0" "$(llamadas poweroff)" "   y systemctl poweroff NO se llama"
afirmar_contiene "$XDG_STATE_HOME/celiuz/remoto/registro.jsonl" '"energia_cancelada".*"por": "celular"' "   queda en el registro, cancelado desde el celular"
afirmar_contiene "$REGISTRO/gdbus.log" "CloseNotification 4242" \
    "   y el aviso de la PC se QUITA (matar notify-send no lo quitaba)"

titulo "2. Se cancela desde la PC: el botón del aviso y la CLI"
touch "$TMP/pulsar"
pedir POST "$B/v0/energia" "$TOKEN" '{"accion":"reiniciar","confirmado":true}' > /dev/null
sleep 4.5
afirmar_igual "0" "$(llamadas reboot)" "pulsar Cancelar en el aviso de la PC lo para"
afirmar_contiene "$XDG_STATE_HOME/celiuz/remoto/registro.jsonl" '"energia_cancelada".*"por": "pc"' "   y se apunta que fue desde la PC"
rm -f "$TMP/pulsar"
pedir POST "$B/v0/energia" "$TOKEN" '{"accion":"suspender","confirmado":true}' > /dev/null
"$CLI" cancelar > "$TMP/cancelar.out"
afirmar_contiene "$TMP/cancelar.out" "Cancelado" "celiuz-remoto cancelar también"
sleep 4
afirmar_igual "0" "$(llamadas suspend)" "   y no suspende"

titulo "3. Si nadie cancela: se piden cerrar las apps y se apaga"
: > "$REGISTRO/hyprctl.log"
pedir POST "$B/v0/energia" "$TOKEN" '{"accion":"reiniciar","confirmado":true}' > /dev/null
reinicio() { [ "$(llamadas reboot)" = "1" ]; }
afirmar "systemctl reboot, al acabar la cuenta" esperar_a 15 reinicio
afirmar_contiene "$REGISTRO/hyprctl.log" 'dispatch hl.dsp.window.close\(\{ window = "address:0xaaa" \}\)' \
    "   antes, pidió cerrar cada ventana (como SUPER+Q, no matando)"
afirmar_contiene "$REGISTRO/hyprctl.log" 'address:0xbbb' "   todas"
r="$(pedir GET "$B/v0/energia" "$TOKEN")"
afirmar_igual "None" "$(campo "$r" 'd["cuerpo"]["energia"]')" "   y ya no queda nada en marcha"

titulo "4. Las apps: verlas pide sesión; cerrarlas, el pase"
r="$(pedir GET "$B/v0/ventanas" "$TOKEN")"
afirmar_igual "200 2" "$(campo "$r" 'd["http"]') $(campo "$r" 'len(d["cuerpo"]["ventanas"])')" "lista las ventanas de la sesión viva"
afirmar_igual "Brave" "$(campo "$r" '[v["app"] for v in d["cuerpo"]["ventanas"] if v["id"]=="0xaaa"][0]')" "   con un nombre legible (brave-browser → Brave)"
: > "$REGISTRO/hyprctl.log"
r="$(pedir POST "$B/v0/ventanas/0xaaa/cerrar" "$TOKEN" '{}')"
afirmar_igual "409" "$(campo "$r" 'd["http"]')" "cerrar sin confirmar, no"
r="$(pedir POST "$B/v0/ventanas/0xaaa/cerrar" "$TOKEN" '{"confirmado":true}')"
afirmar_igual "200" "$(campo "$r" 'd["http"]')" "con pase y confirmado, la cierra"
afirmar_contiene "$REGISTRO/hyprctl.log" 'window.close\(\{ window = "address:0xaaa" \}\)' "   pidiéndolo, por hyprctl"
r="$(pedir POST "$B/v0/ventanas/0xzzz/cerrar" "$TOKEN" '{"confirmado":true}')"
afirmar_igual "404" "$(campo "$r" 'd["http"]')" "una ventana que no existe: 404 (y no se manda nada a ciegas)"
"$CLI" quitar-pase "$DISP" > /dev/null
r="$(pedir POST "$B/v0/ventanas/0xaaa/cerrar" "$TOKEN" '{"confirmado":true}')"
afirmar_igual "423 pase_vencido" "$(campo "$r" 'd["http"]') $(campo "$r" 'd["cuerpo"]["error"]')" "sin pase, cerrar apps NO"
r="$(pedir GET "$B/v0/ventanas" "$TOKEN")"
afirmar_igual "200" "$(campo "$r" 'd["http"]')" "   pero verlas sí (solo pide la contraseña)"
r="$(pedir POST "$B/v0/energia" "$TOKEN" '{"accion":"apagar","confirmado":true}')"
afirmar_igual "200" "$(campo "$r" 'd["http"]')" "   y apagar también: va sin pase a propósito"
pedir DELETE "$B/v0/energia" "$TOKEN" > /dev/null
"$CLI" permisos "$DISP" -ventanas > /dev/null
r="$(pedir GET "$B/v0/ventanas" "$TOKEN")"
afirmar_igual "403" "$(campo "$r" 'd["http"]')" "sin el permiso de ventanas, ni verlas"

titulo "5. El latido «me están apagando», firmado"
r="$(python3 - "$REPO/tests/lib" "$TMP/tel" "$B" "$DISP" <<'FINPY'
import json, sys, time
sys.path.insert(0, sys.argv[1])
from telefono_falso import Telefono, pedir
t, base, disp = Telefono(sys.argv[2]), sys.argv[3], sys.argv[4]
def latido(minuto, firmar_con=None, apagando=True):
    texto = f"{disp}:{minuto}:{1 if apagando else 0}"
    firma = (firmar_con or t).firmar("latido", texto)
    return pedir("POST", f"{base}/v0/latido", {"dispositivo": disp, "minuto": str(minuto),
                                                  "apagando": apagando, "firma": firma})[0]
ahora = int(time.time() // 60)
print(json.dumps([latido(ahora), latido(ahora - 1), latido(ahora - 5),
                  latido(ahora, firmar_con=Telefono(sys.argv[2] + "-otro"))]))
FINPY
)"
afirmar_igual "[200, 200, 401, 401]" "$r" "vale el minuto actual y el anterior; uno viejo o firmado por otro, no"
afirmar "   y queda apuntado (la vigilancia acorta su margen a 1 h)" python3 -c '
import json, sys; d = json.load(open(sys.argv[1]))["dispositivos"][sys.argv[2]]
assert d.get("apagando_en") and d.get("ultima_senal"), d' "$XDG_STATE_HOME/celiuz/remoto/dispositivos.json" "$DISP"

titulo "6. Armar la vigilancia desde la PC"
"$CLI" permisos "$DISP" +ventanas > /dev/null
r="$("$CLI" vigilancia --json)"
afirmar_igual "False" "$(campo "$r" 'd["armada"]')" "viene desarmada"
"$CLI" renovar --sin-adb > "$TMP/ren.out" 2>/dev/null &
esperar_a 10 hay_codigo "$TMP/ren.out"
"$TEL" renovar "$USB" "$(sed -n 's/^CODIGO //p' "$TMP/ren.out")" "$TMP/tel" clave-control > /dev/null
wait $!
r="$("$CLI" vigilancia si --json)"
afirmar_igual "True armada" "$(campo "$r" 'd["armada"]') $(campo "$r" 'd["estado"]')" "armada, vigila al celular con pase"
afirmar_igual "True 127.0.0.1" "$(campo "$r" 'd["telefonos"][0]["vigilado"]') $(campo "$r" 'd["telefonos"][0]["ip_tailscale"]')" \
    "   sabe cuál es por la IP con que entró"
r="$("$TEL" vivo "$RED" "$TOKEN" 1)"
afirmar_igual "armada" "$(campo "$r" 'd["mensajes"][0]["vigilancia"]')" "   y el celular lo ve en el estado en vivo"
r="$("$CLI" vigilancia no --json)"
afirmar_igual "False" "$(campo "$r" 'd["armada"]')" "y se desarma"

titulo "7. El icono de la barra"
r="$("$CLI" barra)"
afirmar_igual "conectado" "$(campo "$r" 'd["class"]')" "con un celular dentro, «conectado» (verde)"
pedir POST "$B/v0/energia" "$TOKEN" '{"accion":"apagar","confirmado":true}' > /dev/null
r="$("$CLI" barra)"
afirmar_igual "apagando" "$(campo "$r" 'd["class"]')" "con un apagado en marcha, «apagando» (rojo)"
"$CLI" cancelar > /dev/null
pedir DELETE "$B/v0/sesion" "$TOKEN" > /dev/null
r="$("$CLI" barra)"
afirmar_igual "activo" "$(campo "$r" 'd["class"]')" "sin nadie dentro, «activo» (discreto)"

afirmar_no_contiene "$TMP/servidor.log" "Traceback" "el servidor no tuvo ni un traceback"
afirmar "el servidor sigue vivo" kill -0 "$PID_SERVIDOR"
kill -TERM "$PID_SERVIDOR"; wait "$PID_SERVIDOR" 2>/dev/null
r="$("$CLI" barra)"
afirmar_igual '{"text": ""}' "$r" "con el servicio apagado, el icono no sale"
afirmar_intacta_la_casa_real
resumen
