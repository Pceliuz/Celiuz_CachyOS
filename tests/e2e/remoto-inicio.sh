#!/usr/bin/env bash
# tests/e2e/remoto-inicio.sh — Celiuz Remoto, fase 5: el celular ve que la PC
# esta en la pantalla de inicio (SDDM) y entra. Servidor de verdad, celular de
# mentira (tests/lib/telefono_falso.py).
#
# POR QUE: «Entrar» abre la sesion del usuario sin su contraseña de Linux. Lo
# que se mira: que pide permiso de energia, el PASE y confirmar; que solo se
# ofrece y se hace con la PC de verdad en la pantalla de inicio (con una sesion
# abierta, no); que pide la unidad de root de ESTE usuario; y que la sesion
# que se abra asi se encuentra la marca de arrancar bloqueada.
#
# Sin Hyprland (es lo que hay tras reiniciar), con un logind de mentira que
# enseña el greeter de SDDM, y systemctl de mentira: la unidad de root no
# corre (eso lo prueba tests/unidad/remoto-inicio.sh).

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
igual() { afirmar_igual "$2" "$3" "$1"; }   # con la descripcion delante, como afirmar
CLI="$REPO/remoto/servidor/celiuz-remoto.py"
TEL="$REPO/tests/lib/telefono_falso.py"
YO="$(id -un)"

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
binario_falso systemctl 0 'case "$*" in start*) [ -e "'"$TMP"'/polkit-no" ] && { echo "Access denied" >&2; exit 1; } ;; esac'
binario_falso pgrep 1
binario_falso notify-send 0
binario_falso hyprctl 0
GREETER='{"session":"c1","uid":968,"user":"sddm","seat":"seat0","class":"greeter"}'
PERSONA='{"session":"2","uid":'"$(id -u)"',"user":"'"$YO"'","seat":"seat0","class":"user"}'
echo "[$GREETER]" > "$TMP/sesiones.json"
binario_falso loginctl 0 'cat "'"$TMP"'/sesiones.json"'

# Lo de root, «instalado» en una raiz de mentira
export CELIUZ_REMOTO_RAIZ_SISTEMA="$TMP/raiz"
mkdir -p "$TMP/raiz/etc/systemd/system" "$TMP/raiz/usr/local/lib/celiuz-remoto"
cp "$REPO/remoto/sistema/celiuz-remoto-entrar@.service" "$TMP/raiz/etc/systemd/system/"
install -m 755 "$REPO/remoto/sistema/entrar.py" "$TMP/raiz/usr/local/lib/celiuz-remoto/entrar"

"$CLI" servir 2>"$TMP/servidor.log" &
PID_SERVIDOR=$!
trap 'kill $PID_SERVIDOR 2>/dev/null; wait $PID_SERVIDOR 2>/dev/null; limpiar_entorno' EXIT INT TERM
esta_arriba() { test -S "$XDG_RUNTIME_DIR/celiuz-remoto.sock"; }
esperar_a 10 esta_arriba

hay_codigo() { grep -q '^CODIGO ' "$1"; }
emparejar() {   # <carpeta> <permisos>
    echo "clave-inicio" | "$CLI" emparejar --sin-adb --permisos "$2" > "$TMP/emp.out" 2>/dev/null &
    esperar_a 10 hay_codigo "$TMP/emp.out"
    "$TEL" emparejar "$USB" "$(sed -n 's/^CODIGO //p' "$TMP/emp.out")" "$1" > /dev/null
    wait $!
    rm -f "$TMP/emp.out"
}
emparejar "$TMP/tel" estado,energia
emparejar "$TMP/mirar" estado
TOKEN="$(campo "$("$TEL" entrar "$RED" "$TMP/tel" clave-inicio)" 'd["cuerpo"]["token"]')"
MIRA="$(campo "$("$TEL" entrar "$RED" "$TMP/mirar" clave-inicio)" 'd["cuerpo"]["token"]')"
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
MARCA="$XDG_RUNTIME_DIR/celiuz-remoto/entrar-bloqueada"
pedidas() { grep -c "^start --no-block celiuz-remoto-entrar@$YO.service$" "$REGISTRO/systemctl.log" 2>/dev/null || echo 0; }

titulo "1. El celular ve que la PC está en la pantalla de inicio"
r="$(pedir GET "$B/v0/escritorio" "$TOKEN")"
igual "pantalla_inicio" "pantalla_inicio" "$(campo "$r" 'd["cuerpo"]["sesion"]')"
igual "y se puede entrar" "True" "$(campo "$r" 'd["cuerpo"]["puede_entrar"]')"
v="$("$TEL" vivo "$RED" "$TOKEN" 1)"
igual "/v0/vivo lo lleva en cada mensaje" "pantalla_inicio" \
    "$(campo "$v" 'd["mensajes"][0]["escritorio"]["sesion"]')"
r="$(pedir GET "$B/v0/escritorio" "")"
igual "sin sesion: 401" "401" "$(campo "$r" 'd["http"]')"

titulo "2. Entrar pide permiso, confirmar y el pase"
r="$(pedir POST "$B/v0/escritorio/entrar" "$MIRA" '{"confirmado":true}')"
igual "sin permiso de energia: 403" "403" "$(campo "$r" 'd["http"]')"
r="$(pedir POST "$B/v0/escritorio/entrar" "$TOKEN" '{}')"
igual "sin confirmar: 409 confirmar" "confirmar" "$(campo "$r" 'd["cuerpo"]["error"]')"
"$CLI" quitar-pase "$(cat "$TMP/tel/dispositivo")" >/dev/null
r="$(pedir POST "$B/v0/escritorio/entrar" "$TOKEN" '{"confirmado":true}')"
igual "sin pase: 423" "423" "$(campo "$r" 'd["http"]')"
igual "  y no se ha pedido nada a systemd" "0" "$(pedidas)"
afirmar "  ni hay marca" test ! -e "$MARCA"

titulo "3. Con el pase, entra (y la sesion arrancara bloqueada)"
# Renovar por el cable, como en la vida real
echo "clave-inicio" | "$CLI" renovar --sin-adb > "$TMP/ren.out" 2>/dev/null &
esperar_a 10 hay_codigo "$TMP/ren.out"
"$TEL" renovar "$USB" "$(sed -n 's/^CODIGO //p' "$TMP/ren.out")" "$TMP/tel" clave-inicio > /dev/null
wait $!
r="$(pedir POST "$B/v0/escritorio/entrar" "$TOKEN" '{"confirmado":true}')"
igual "200" "200" "$(campo "$r" 'd["http"]')"
igual "pide la unidad de root de este usuario, una vez" "1" "$(pedidas)"
afirmar "deja la marca de arrancar bloqueada" test -f "$MARCA"
afirmar "lo apunta el registro" grep -q '"accion": "entrar_escritorio"' "$XDG_STATE_HOME/celiuz/remoto/registro.jsonl"
"$CLI" al-entrar; codigo=$?
igual "la sesion que arranque la encuentra (bloquear)" "0" "$codigo"

titulo "4. Con una sesion abierta, no"
echo "[$GREETER,$PERSONA]" > "$TMP/sesiones.json"
sleep 3.2   # la cache de inicio.estado() es de 3 s
r="$(pedir GET "$B/v0/escritorio" "$TOKEN")"
igual "no_lo_se (hay alguien, y no es Hyprland)" "no_lo_se" "$(campo "$r" 'd["cuerpo"]["sesion"]')"
r="$(pedir POST "$B/v0/escritorio/entrar" "$TOKEN" '{"confirmado":true}')"
igual "entrar: 409 estado" "estado" "$(campo "$r" 'd["cuerpo"]["error"]')"
igual "  y no se pide nada mas a systemd" "1" "$(pedidas)"

titulo "5. Si polkit no deja (falta lo de root, o esta viejo), lo dice"
echo "[$GREETER]" > "$TMP/sesiones.json"
touch "$TMP/polkit-no"
r="$(pedir POST "$B/v0/escritorio/entrar" "$TOKEN" '{"confirmado":true}')"
igual "409" "409" "$(campo "$r" 'd["http"]')"
m="$(campo "$r" 'd["cuerpo"]["mensaje"]')"
afirmar "  y dice que pasar en la PC" grep -qF -- "--remoto-sistema" <<<"$m"
afirmar "  sin dejar marca" test ! -e "$MARCA"
rm -f "$TMP/polkit-no"
rm -rf "$TMP/raiz/usr/local/lib/celiuz-remoto"
sleep 3.2
r="$(pedir GET "$B/v0/escritorio" "$TOKEN")"
igual "sin lo de root: pantalla_inicio, pero no se puede entrar" "False" \
    "$(campo "$r" 'd["cuerpo"]["puede_entrar"]')"

titulo "6. El servicio lo cuenta por el control"
e="$("$CLI" estado --json)"
igual "escritorio en /control/estado" "pantalla_inicio" "$(campo "$e" 'd["escritorio"]["sesion"]')"
igual "y si hay linger" "False" "$(campo "$e" 'd["linger"]')"

afirmar "el servidor no se quejo" sh -c "! grep -q Traceback '$TMP/servidor.log'"
afirmar_intacta_la_casa_real
resumen
