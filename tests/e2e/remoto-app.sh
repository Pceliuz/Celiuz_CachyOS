#!/usr/bin/env bash
# tests/e2e/remoto-app.sh — el codigo de la app del celular contra el servidor
# de verdad. No es un imitador: es remoto/app/src (lo que va en el APK),
# ejecutado con Node (tests/lib/app_remoto.ts).
#
# POR QUE: la firma la hace JavaScript (@noble/ed25519) y la comprueba Python
# (cryptography). Que los dos lados entiendan lo mismo por «firmar el reto» solo
# se sabe haciendolo: un base64 con otro alfabeto, un prefijo distinto o un
# byte de mas y no entraria nadie, con cada lado en verde en sus propias pruebas.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
CLI="$REPO/remoto/servidor/celiuz-remoto.py"
APP="$REPO/remoto/app"
binario_falso notify-send 0

if ! command -v node >/dev/null || [ ! -d "$APP/node_modules/@noble/ed25519" ]; then
    _gris "  sin node o sin las dependencias de la app (cd remoto/app && npm install): se salta"
    resumen
    exit 0
fi

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
binario_falso tailscale 0 'echo 127.0.0.1'

"$CLI" servir 2>"$TMP/servidor.log" &
PID_SERVIDOR=$!
trap 'kill $PID_SERVIDOR 2>/dev/null; wait $PID_SERVIDOR 2>/dev/null; limpiar_entorno' EXIT INT TERM
esta_arriba() { test -S "$XDG_RUNTIME_DIR/celiuz-remoto.sock"; }
esperar_a 10 esta_arriba

# node: sin el aviso de «MODULE_TYPELESS_PACKAGE_JSON», que no es de la prueba
app() { node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON "$REPO/tests/lib/app_remoto.ts" "$@"; }
leer() {
    while IFS='|' read -r res desc; do
        case "$res" in
            ok) ok "$desc" ;;
            fallo) fallo "$desc" ;;
            "") ;;
            *) fallo "salida inesperada de la app" "$res $desc" ;;
        esac
    done < "$1"
}
hay_codigo() { grep -q '^CODIGO ' "$1"; }

titulo "1. Emparejar, entrar y ver el estado, con el código de la app"
echo "clave-app" | "$CLI" emparejar --sin-adb > "$TMP/emp.out" 2>/dev/null &
esperar_a 10 hay_codigo "$TMP/emp.out"
TMP="$TMP" app "$RED" "$USB" "$(sed -n 's/^CODIGO //p' "$TMP/emp.out")" clave-app emparejar > "$TMP/app1.txt" 2>"$TMP/app1.err"
leer "$TMP/app1.txt"
afirmar "   la app no escribió nada por stderr" test ! -s "$TMP/app1.err"
afirmar "   y dijo algo (no reventó antes de empezar)" test "$(grep -c '^ok|' "$TMP/app1.txt")" -ge 20

titulo "2. Renovar el pase por el cable"
"$CLI" renovar --sin-adb > "$TMP/ren.out" 2>/dev/null &
PID_REN=$!
esperar_a 10 hay_codigo "$TMP/ren.out"
TMP="$TMP" app "$RED" "$USB" "$(sed -n 's/^CODIGO //p' "$TMP/ren.out")" clave-app renovar > "$TMP/app2.txt" 2>"$TMP/app2.err"
leer "$TMP/app2.txt"
afirmar "   sin nada por stderr" test ! -s "$TMP/app2.err"
wait "$PID_REN"; codigo=$?
afirmar_igual "0" "$codigo" "   y la PC da la renovación por hecha"
afirmar "el servidor sigue vivo después de todo" kill -0 "$PID_SERVIDOR"

afirmar_no_contiene "$TMP/servidor.log" "Traceback" "el servidor no tuvo ni un traceback"
afirmar_intacta_la_casa_real
resumen
