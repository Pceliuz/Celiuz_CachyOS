#!/usr/bin/env bash
# tests/e2e/remoto-terminal.sh — Celiuz Remoto, fase 7: la terminal. Servidor
# de verdad, celular de mentira, y una shell de verdad (bash, en la casa de
# mentira: $SHELL y $HOME los da la prueba).
#
# POR QUE: es lo mas poderoso del remoto. Lo que se mira:
#   1. que pide el permiso de terminal, el pase y la contraseña OTRA VEZ (y que
#      una mal cuenta como fallo, como al entrar);
#   2. que el billete es de un solo uso y de ESE telefono;
#   3. que la shell funciona: lo que se teclea llega, lo que sale vuelve, el
#      tamaño se cambia (stty size), y `exit` cierra con su codigo;
#   4. que quitarle el pase con la terminal abierta la CIERRA y mata la shell y
#      lo que dejo corriendo;
#   5. que la PC lo cuenta (aviso y registro) y que lo tecleado no queda en el
#      registro (ahi pasa la contraseña de sudo).

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
igual() { afirmar_igual "$2" "$3" "$1"; }
CLI="$REPO/remoto/servidor/celiuz-remoto.py"
TEL="$REPO/tests/lib/telefono_falso.py"
export SHELL=/bin/bash
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
trap 'kill $PID_SERVIDOR 2>/dev/null; wait $PID_SERVIDOR 2>/dev/null; [ -n "${GUARDAR:-}" ] && cp -r "$TMP" "$GUARDAR"; limpiar_entorno' EXIT INT TERM
esta_arriba() { test -S "$XDG_RUNTIME_DIR/celiuz-remoto.sock"; }
esperar_a 10 esta_arriba

hay_codigo() { grep -q '^CODIGO ' "$1"; }
emparejar() {
    echo "clave-term" | "$CLI" emparejar --sin-adb --permisos "$2" > "$TMP/emp.out" 2>/dev/null &
    esperar_a 10 hay_codigo "$TMP/emp.out"
    "$TEL" emparejar "$USB" "$(sed -n 's/^CODIGO //p' "$TMP/emp.out")" "$1" > /dev/null
    wait $!
    rm -f "$TMP/emp.out"
}
emparejar "$TMP/tel" estado,terminal
emparejar "$TMP/sinpermiso" estado,archivos
token() { campo "$("$TEL" entrar "$RED" "$1" clave-term)" 'd["cuerpo"]["token"]'; }
TOKEN="$(token "$TMP/tel")"; SINPERMISO="$(token "$TMP/sinpermiso")"
DISP="$(cat "$TMP/tel/dispositivo")"
B="http://127.0.0.1:$RED"

# El celular de mentira de la terminal: pide el billete y abre el WebSocket.
#   term.py billete <token> <contrasena>        -> {"http", "cuerpo"}
#   term.py hablar <token> <billete> <guion>     -> {"salida", "cierre"}
# El guion es JSON: [["escribe", "texto"], ["tamano", f, c], ["espera", s], ["hasta", "texto"]]
cat > "$TMP/term.py" <<'FINPY'
import asyncio, json, sys
import aiohttp
B = sys.argv[1]
async def billete(token, contrasena):
    async with aiohttp.ClientSession() as s:
        async with s.post(f"{B}/v0/terminal", json={"contrasena": contrasena},
                          headers={"Authorization": "Bearer " + token}) as r:
            return {"http": r.status, "cuerpo": await r.json()}
async def hablar(token, ident, guion):
    salida, cierre = b"", None
    async with aiohttp.ClientSession() as s:
        try:
            ws = await s.ws_connect(f"{B}/v0/terminal/{ident}?filas=24&columnas=80",
                                    headers={"Authorization": "Bearer " + token})
        except aiohttp.WSServerHandshakeError as e:
            return {"http": e.status, "salida": "", "cierre": None}
        async def leer(hasta=None, plazo=10):
            nonlocal salida, cierre
            fin = asyncio.get_running_loop().time() + plazo
            while asyncio.get_running_loop().time() < fin:
                if hasta and hasta.encode() in salida:
                    return True
                try:
                    m = await asyncio.wait_for(ws.receive(), 0.3)
                except asyncio.TimeoutError:
                    continue
                if m.type == aiohttp.WSMsgType.BINARY:
                    salida += m.data
                elif m.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING):
                    cierre = ws.close_code
                    return False
            return False
        for paso in guion:
            if paso[0] == "escribe":
                await ws.send_bytes(paso[1].encode())
            elif paso[0] == "texto":
                await ws.send_str(json.dumps({"texto": paso[1]}))
            elif paso[0] == "tamano":
                await ws.send_str(json.dumps({"tamano": [paso[1], paso[2]]}))
            elif paso[0] == "espera":
                await leer(None, paso[1])
            elif paso[0] == "hasta":
                await leer(paso[1], paso[2] if len(paso) > 2 else 10)
        if cierre is None:
            await leer(None, 0.5)
        if cierre is None:
            await ws.close()
        return {"http": 101, "salida": salida.decode("utf-8", "replace"), "cierre": cierre}
orden = sys.argv[2]
if orden == "billete":
    print(json.dumps(asyncio.run(billete(sys.argv[3], sys.argv[4]))))
else:
    print(json.dumps(asyncio.run(hablar(sys.argv[3], sys.argv[4], json.loads(sys.argv[5])))))
FINPY
T() { python3 "$TMP/term.py" "$B" "$@"; }
billete() { campo "$(T billete "$TOKEN" clave-term)" 'd["cuerpo"]["terminal"]'; }

titulo "1. Pide permiso, pase y la contraseña otra vez"
igual "sin permiso de terminal: 403" "403" "$(campo "$(T billete "$SINPERMISO" clave-term)" 'd["http"]')"
r="$(T billete "$TOKEN" mal)"
igual "contraseña mal: 401" "401" "$(campo "$r" 'd["http"]')"
igual "  y cuenta como fallo (quedan 4)" "4" "$(campo "$r" 'd["cuerpo"]["intentos_restantes"]')"
r="$(T billete "$TOKEN" clave-term)"
igual "bien: 200 y un billete" "200" "$(campo "$r" 'd["http"]')"
igual "  que dura 30 s" "30" "$(campo "$r" 'd["cuerpo"]["caduca"]')"
igual "  y la contraseña buena pone los fallos a cero" "0" \
    "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["dispositivos"][sys.argv[2]].get("fallos",0))' \
       "$XDG_STATE_HOME/celiuz/remoto/dispositivos.json" "$DISP" 2>/dev/null || echo "?")"
"$CLI" quitar-pase "$DISP" >/dev/null
igual "sin pase: 423" "423" "$(campo "$(T billete "$TOKEN" clave-term)" 'd["http"]')"
echo "clave-term" | "$CLI" renovar --sin-adb > "$TMP/ren.out" 2>/dev/null &
esperar_a 10 hay_codigo "$TMP/ren.out"
"$TEL" renovar "$USB" "$(sed -n 's/^CODIGO //p' "$TMP/ren.out")" "$TMP/tel" clave-term > /dev/null
wait $!

titulo "2. El billete es de un solo uso y de este telefono"
BIL="$(billete)"
igual "un billete inventado: 401" "401" "$(campo "$(T hablar "$TOKEN" inventado '[]')" 'd["http"]')"
igual "otro celular, sin permiso de terminal: 403" "403" "$(campo "$(T hablar "$SINPERMISO" "$BIL" '[]')" 'd["http"]')"
r="$(T hablar "$TOKEN" "$BIL" '[["escribe","exit\n"],["espera",3]]')"
igual "con el bueno: se abre" "101" "$(campo "$r" 'd["http"]')"
igual "y otra vez el mismo: 401" "401" "$(campo "$(T hablar "$TOKEN" "$BIL" '[]')" 'd["http"]')"

titulo "3. La shell funciona"
BIL="$(billete)"
r="$(T hablar "$TOKEN" "$BIL" '[["escribe","echo hola-$((40+2))\n"],["hasta","hola-42"],
      ["tamano",30,100],["escribe","stty size\n"],["hasta","30 100"],
      ["texto","echo ñandú-$((1+1))\n"],["hasta","ñandú-2"],
      ["escribe","pwd; echo TERM=$TERM\n"],["hasta","TERM=xterm"],
      ["escribe","exit 0\n"],["espera",5]]')"
s="$(campo "$r" 'd["salida"]')"
afirmar "lo que se teclea llega y la salida vuelve" grep -q "hola-42" <<<"$s"
afirmar "el tamaño cambia (stty size)" grep -q "30 100" <<<"$s"
afirmar "el texto en UTF-8 (el teclado del celular)" grep -q "ñandú-2" <<<"$s"
afirmar "en la carpeta personal" grep -qF "$HOME" <<<"$s"
afirmar "con TERM=xterm-256color" grep -q "TERM=xterm-256color" <<<"$s"
igual "exit cierra con 4000" "4000" "$(campo "$r" 'd["cierre"]')"

titulo "4. Quitarle el pase con la terminal abierta la cierra, y mata lo que corria"
BIL="$(billete)"
( sleep 2; "$CLI" quitar-pase "$DISP" >/dev/null ) &
r="$(T hablar "$TOKEN" "$BIL" '[["escribe","sleep 1000 & echo PID=$!\n"],["hasta","PID="],["espera",12]]')"
igual "se cierra sola con 4403" "4403" "$(campo "$r" 'd["cierre"]')"
PID_SLEEP="$(campo "$r" 'd["salida"]' | sed -n 's/.*PID=\([0-9]*\).*/\1/p' | head -1)"
sigue_vivo() { kill -0 "$PID_SLEEP" 2>/dev/null; }
muerto() { ! sigue_vivo; }
esperar_a 5 muerto
afirmar "y el sleep que dejo en segundo plano ya no existe" muerto

titulo "5. La PC lo cuenta, y lo tecleado no queda en ningun sitio"
REG="$XDG_STATE_HOME/celiuz/remoto/registro.jsonl"
tres_cerradas() { [ "$(grep -c '"accion": "terminal_cerrada"' "$REG")" -ge 3 ]; }
esperar_a 10 tres_cerradas
afirmar "aviso en la PC al abrirla" grep -q "terminal abierta" "$REGISTRO/notify-send.log"
igual "el registro: abierta" "3" "$(grep -c '"accion": "terminal_abierta"' "$XDG_STATE_HOME/celiuz/remoto/registro.jsonl")"
igual "  y cerrada, las mismas veces" "3" "$(grep -c '"accion": "terminal_cerrada"' "$XDG_STATE_HOME/celiuz/remoto/registro.jsonl")"
afirmar "  con el porqué (salió, pase_vencido)" grep -q '"por": "pase_vencido"' "$XDG_STATE_HOME/celiuz/remoto/registro.jsonl"
afirmar "lo tecleado no está en el registro" sh -c "! grep -q 'hola-\|stty\|sleep 1000' '$XDG_STATE_HOME/celiuz/remoto/registro.jsonl'"
afirmar "  ni en el diario del servidor" sh -c "! grep -q 'hola-\|stty\|sleep 1000' '$TMP/servidor.log'"
afirmar "el servidor no se quejo" sh -c "! grep -q Traceback '$TMP/servidor.log'"
igual "no queda ninguna terminal abierta" "0" "$(campo "$("$CLI" estado --json)" 'd["terminales"]')"

afirmar_intacta_la_casa_real
resumen
