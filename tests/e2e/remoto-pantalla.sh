#!/usr/bin/env bash
# tests/e2e/remoto-pantalla.sh — Celiuz Remoto, fase 8: el escritorio remoto.
# Servidor de verdad, celular de mentira, y un wayvnc de MENTIRA (un socket unix
# que saluda como un servidor VNC y devuelve lo que le llega).
#
# POR QUE: ver y manejar la pantalla es tan poderoso como la terminal. Lo que
# se mira: que pide permiso propio, pase y la contraseña otra vez; que el
# billete (la unica llave del WebSocket, que lo abre un WebView sin cabeceras)
# es de un solo uso; que wayvnc arranca en la sesion de Hyprland viva y en un
# SOCKET UNIX, no en un puerto; que el puente pasa los bytes en los dos
# sentidos; que quitar el permiso con la pantalla abierta la cierra; y que al
# cerrar, wayvnc se para.

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
FIRMA="prueba_1792449598_1"
binario_falso tailscale 0 'case "$*" in "ip -4") echo 127.0.0.1 ;; *) echo "{\"Peer\":{}}" ;; esac'
binario_falso systemctl 0
binario_falso pgrep 1
binario_falso notify-send 0
binario_falso loginctl 0 'echo "[]"'
binario_falso hyprctl 0 'case "$*" in
    "instances -j") echo "[{\"instance\":\"'"$FIRMA"'\",\"wl_socket\":\"wayland-prueba\"}]" ;;
    "monitors -j") echo "[{\"name\":\"HDMI-A-1\",\"focused\":true}]" ;;
esac'

# El wayvnc de mentira: apunta con que lo llamaron y con que entorno, y sirve.
cat > "$TMP/wayvnc" <<FIN
#!/usr/bin/env python3
import os, socket, sys
open("$TMP/wayvnc.args", "w").write(" ".join(sys.argv[1:]) + "\\n" + os.environ.get("WAYLAND_DISPLAY", "") + "\\n")
ruta = sys.argv[-1]
s = socket.socket(socket.AF_UNIX); s.bind(ruta); s.listen(1)
c, _ = s.accept()
c.sendall(b"RFB 003.008\\n")
while True:
    d = c.recv(65536)
    if not d:
        break
    c.sendall(b"eco:" + d)
FIN
chmod +x "$TMP/wayvnc"
export CELIUZ_REMOTO_WAYVNC="$TMP/wayvnc"

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
trap 'kill $PID_SERVIDOR $PID_HYPR 2>/dev/null; pkill -f "$TMP/wayvnc" 2>/dev/null; wait $PID_SERVIDOR 2>/dev/null; limpiar_entorno' EXIT INT TERM
esta_arriba() { test -S "$XDG_RUNTIME_DIR/celiuz-remoto.sock"; }
esperar_a 10 esta_arriba

hay_codigo() { grep -q '^CODIGO ' "$1"; }
emparejar() {
    echo "clave-vnc" | "$CLI" emparejar --sin-adb --permisos "$2" > "$TMP/emp.out" 2>/dev/null &
    esperar_a 10 hay_codigo "$TMP/emp.out"
    "$TEL" emparejar "$USB" "$(sed -n 's/^CODIGO //p' "$TMP/emp.out")" "$1" > /dev/null
    wait $!
    rm -f "$TMP/emp.out"
}
emparejar "$TMP/tel" estado,pantalla
emparejar "$TMP/sinpermiso" estado,terminal
token() { campo "$("$TEL" entrar "$RED" "$1" clave-vnc)" 'd["cuerpo"]["token"]'; }
TOKEN="$(token "$TMP/tel")"; SINPERMISO="$(token "$TMP/sinpermiso")"
DISP="$(cat "$TMP/tel/dispositivo")"
B="http://127.0.0.1:$RED"

cat > "$TMP/vnc.py" <<'FINPY'
import asyncio, json, sys
import aiohttp
B = sys.argv[1]
async def billete(token, contrasena):
    async with aiohttp.ClientSession() as s:
        async with s.post(f"{B}/v0/pantalla", json={"contrasena": contrasena},
                          headers={"Authorization": "Bearer " + token}) as r:
            return {"http": r.status, "cuerpo": await r.json()}
async def mirar(ident, enviar, esperar):
    # Como el WebView: SIN cabecera Authorization, con el subprotocolo binary.
    async with aiohttp.ClientSession() as s:
        try:
            ws = await s.ws_connect(f"{B}/v0/pantalla/{ident}", protocols=("binary",))
        except aiohttp.WSServerHandshakeError as e:
            return {"http": e.status}
        recibido, cierre = b"", None
        primero = await ws.receive(timeout=10)
        if primero.type == aiohttp.WSMsgType.BINARY:
            recibido += primero.data
        if enviar:
            await ws.send_bytes(enviar.encode())
        fin = asyncio.get_running_loop().time() + esperar
        while asyncio.get_running_loop().time() < fin:
            try:
                m = await ws.receive(timeout=0.5)
            except asyncio.TimeoutError:
                continue
            if m.type == aiohttp.WSMsgType.BINARY:
                recibido += m.data
            else:
                cierre = ws.close_code
                break
        if cierre is None:
            await ws.close()
        return {"http": 101, "protocolo": ws.protocol, "recibido": recibido.decode("utf-8", "replace"), "cierre": cierre}
if sys.argv[2] == "billete":
    print(json.dumps(asyncio.run(billete(sys.argv[3], sys.argv[4]))))
else:
    print(json.dumps(asyncio.run(mirar(sys.argv[3], sys.argv[4], float(sys.argv[5])))))
FINPY
V() { python3 "$TMP/vnc.py" "$B" "$@"; }
billete() { campo "$(V billete "$TOKEN" clave-vnc)" 'd["cuerpo"]["pantalla"]'; }

titulo "1. Pide permiso de pantalla, pase y la contraseña otra vez"
igual "sin permiso: 403" "403" "$(campo "$(V billete "$SINPERMISO" clave-vnc)" 'd["http"]')"
r="$(V billete "$TOKEN" mal)"
igual "contraseña mal: 401 (y cuenta como fallo)" "401" "$(campo "$r" 'd["http"]')"
"$CLI" quitar-pase "$DISP" >/dev/null
igual "sin pase: 423" "423" "$(campo "$(V billete "$TOKEN" clave-vnc)" 'd["http"]')"
echo "clave-vnc" | "$CLI" renovar --sin-adb > "$TMP/ren.out" 2>/dev/null &
esperar_a 10 hay_codigo "$TMP/ren.out"
"$TEL" renovar "$USB" "$(sed -n 's/^CODIGO //p' "$TMP/ren.out")" "$TMP/tel" clave-vnc > /dev/null
wait $!
igual "con todo: un billete" "200" "$(campo "$(V billete "$TOKEN" clave-vnc)" 'd["http"]')"

titulo "2. El puente: wayvnc en la sesion viva, en un socket unix, y los bytes en los dos sentidos"
BIL="$(billete)"
igual "un billete inventado: 401" "401" "$(campo "$(V mirar inventado '' 1)" 'd["http"]')"
r="$(V mirar "$BIL" hola 2)"
igual "se abre (sin cabecera Authorization: la llave es el billete)" "101" "$(campo "$r" 'd["http"]')"
igual "  con el subprotocolo binary (el de noVNC)" "binary" "$(campo "$r" 'd["protocolo"]')"
afirmar "  llega el saludo del servidor VNC" grep -q "RFB 003.008" <<<"$(campo "$r" 'd["recibido"]')"
afirmar "  y lo que manda el celular llega a wayvnc (eco)" grep -q "eco:hola" <<<"$(campo "$r" 'd["recibido"]')"
igual "el mismo billete otra vez: 401" "401" "$(campo "$(V mirar "$BIL" '' 1)" 'd["http"]')"
afirmar "wayvnc en un socket unix, no en un puerto" grep -q -- "--unix-socket" "$TMP/wayvnc.args"
afirmar "  dentro de su XDG_RUNTIME_DIR" grep -qF "$XDG_RUNTIME_DIR/celiuz-remoto/vnc.sock" "$TMP/wayvnc.args"
afirmar "  en la pantalla enfocada" grep -q -- "--output=HDMI-A-1" "$TMP/wayvnc.args"
igual "  y con el WAYLAND_DISPLAY de la sesion viva" "wayland-prueba" "$(sed -n 2p "$TMP/wayvnc.args")"
parado() { ! pgrep -f "$TMP/wayvnc" >/dev/null; }
esperar_a 5 parado
afirmar "al cerrar, wayvnc se para" parado
afirmar "  y no deja sus sockets" sh -c "! ls '$XDG_RUNTIME_DIR/celiuz-remoto/' | grep -q vnc"

titulo "3. Quitar el permiso con la pantalla abierta la cierra"
BIL="$(billete)"
( sleep 2; "$CLI" permisos "$DISP" -pantalla >/dev/null ) &
r="$(V mirar "$BIL" '' 12)"
igual "se cierra con 4403" "4403" "$(campo "$r" 'd["cierre"]')"
esperar_a 5 parado
afirmar "  y wayvnc se para" parado
igual "y ya no da billetes" "403" "$(campo "$(V billete "$TOKEN" clave-vnc)" 'd["http"]')"

titulo "4. La PC lo cuenta"
afirmar "aviso en la PC" grep -q "pantalla compartida" "$REGISTRO/notify-send.log"
REG="$XDG_STATE_HOME/celiuz/remoto/registro.jsonl"
dos_cerradas() { [ "$(grep -c '"accion": "pantalla_cerrada"' "$REG")" -ge 2 ]; }
esperar_a 10 dos_cerradas
igual "registro: abierta dos veces" "2" "$(grep -c '"accion": "pantalla_abierta"' "$REG")"
afirmar "  y cerrada, con el porqué" grep -q '"por": "sin_permiso"' "$REG"
afirmar "el servidor no se quejo" sh -c "! grep -q Traceback '$TMP/servidor.log'"

afirmar_intacta_la_casa_real
resumen
