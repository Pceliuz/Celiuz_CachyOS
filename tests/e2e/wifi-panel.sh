#!/usr/bin/env bash
# tests/e2e/wifi-panel.sh — conectar a una red NUEVA desde el panel de red
# (ConexionNueva, en hypr/scripts/wifi-panel.py), de verdad por D-Bus, contra un
# NetworkManager falso en un bus privado. Ni una ventana ni una red de verdad.
#
# QUE VIGILA
# ----------
#   1. Con la contraseña buena: se pide en MEMORIA (persist=memory), con el SSID
#      y la contraseña dentro de la llamada, y al conectar se GUARDA (Save).
#   2. Con una mala: no se guarda, se BORRA el perfil a medias (Delete) y el
#      error dice «Contraseña incorrecta», no un codigo.
#   3. WPA3 sola pide key-mgmt «sae»; una red abierta no lleva seguridad.
#   4. La contraseña no sale en la linea de ordenes de ningun proceso: va por
#      D-Bus (lo de /proc/<pid>/cmdline de la cabecera del panel).

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "${_NM_BUS_PRIVADO:-}" ]; then
    if ! command -v dbus-run-session >/dev/null 2>&1; then
        printf '\033[31m  ✗ falta dbus-run-session (paquete dbus)\033[0m\n'
        exit 1
    fi
    exec env _NM_BUS_PRIVADO=1 _NM_BUS_DE_FUERA="${DBUS_SESSION_BUS_ADDRESS:-}" \
        dbus-run-session -- bash "${BASH_SOURCE[0]}" "$@"
fi

. "$DIR/../lib/comun.sh"

preparar_entorno

PANEL="$REPO/hypr/scripts/wifi-panel.py"
FALSO="$DIR/../lib/nm_falso.py"
export DBUS_SYSTEM_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS"

PID_FALSO=""
parar() {
    [ -n "$PID_FALSO" ] && kill "$PID_FALSO" 2>/dev/null
    wait 2>/dev/null
    limpiar_entorno
}
trap parar EXIT INT TERM

titulo "Guardias: bus privado y NetworkManager falso"
if [ -n "${_NM_BUS_DE_FUERA:-}" ] && [ "$DBUS_SESSION_BUS_ADDRESS" = "$_NM_BUS_DE_FUERA" ]; then
    fallo "el bus es privado" "es el de tu sesion: no sigo"
    resumen; exit 1
fi
ok "el bus es privado"

# arrancar_falso: uno nuevo para cada caso, para que no arrastre lo anterior.
arrancar_falso() {
    [ -n "$PID_FALSO" ] && kill "$PID_FALSO" 2>/dev/null && wait "$PID_FALSO" 2>/dev/null
    python3 "$FALSO" servir > "$TMP/falso.log" 2>&1 &
    PID_FALSO=$!
    for _ in $(seq 50); do grep -q '^listo' "$TMP/falso.log" && return 0; sleep 0.1; done
    return 1
}
if ! arrancar_falso; then
    fallo "el NetworkManager falso consigue su nombre" "$(cat "$TMP/falso.log")"
    resumen; exit 1
fi
ok "el NetworkManager falso consigue su nombre"

# conectar <ssid> <clave> <seguridad>: lo que hace el boton, y lo que contesto.
# Mientras dura, se apunta la linea de ordenes de todos los procesos.
conectar() {
    # La contraseña va por el entorno: como argumento saldria en la linea de
    # ordenes de ESTE ayudante y el punto 4 fallaria por culpa de la prueba.
    CLAVE="$2" python3 - "$PANEL" "$1" "$3" <<'PYEOF' &
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("panel", sys.argv[1])
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
from gi.repository import GLib  # noqa: E402

bucle = GLib.MainLoop()
salida = {}


def listo(error):
    salida["r"] = error or "ok"
    bucle.quit()


import os  # noqa: E402
p.Control().nueva("wlan0", sys.argv[2], os.environ["CLAVE"], sys.argv[3], listo)
GLib.timeout_add(20_000, bucle.quit)
bucle.run()
print(salida.get("r", "(sin respuesta)"))
PYEOF
    local pid=$!
    while kill -0 "$pid" 2>/dev/null; do
        cat /proc/[0-9]*/cmdline 2>/dev/null | tr '\0' ' ' >> "$TMP/lineas.txt"
        sleep 0.05
    done
    wait "$pid"
}
visto() {   # visto <expresion python sobre «e»>
    python3 "$FALSO" estado | python3 -c '
import json, sys
e = json.load(sys.stdin)
print(eval(sys.argv[1]))' "$1"
}

titulo "1. Contraseña buena"
r="$(conectar "Casa:5G" "buena-clave" psk)"
afirmar_igual "ok" "$r" "contesta que fue bien"
afirmar_igual "wlan0" "$(visto 'e["dispositivo_pedido"]')" "por el dispositivo de wifi"
afirmar_igual "memory" "$(visto 'e["opciones"]["persist"]')" "pedida solo en memoria"
afirmar_igual "Casa:5G" "$(visto 'e["ajustes"]["802-11-wireless"]["ssid"]')" \
    "con el SSID tal cual (dos puntos incluidos)"
afirmar_igual "wpa-psk" "$(visto 'e["ajustes"]["802-11-wireless-security"]["key-mgmt"]')" \
    "como WPA2"
afirmar_igual "buena-clave" "$(visto 'e["ajustes"]["802-11-wireless-security"]["psk"]')" \
    "la contraseña llega dentro de la llamada"
afirmar_igual "1 0" "$(visto 'str(e["guardado"]) + " " + str(e["borrado"])')" "y al conectar se guarda, sin borrar nada"

titulo "2. Contraseña mala"
arrancar_falso
r="$(conectar "Casa:5G" "mala-clave" psk)"
afirmar "dice que la contraseña es incorrecta (dijo: $r)" grep -q "^Contraseña incorrecta" <<< "$r"
afirmar_igual "0 1" "$(visto 'str(e["guardado"]) + " " + str(e["borrado"])')" \
    "no se guarda, y el perfil a medias se borra"

titulo "3. WPA3 y red abierta"
arrancar_falso
conectar "Nueva" "buena-clave" sae >/dev/null
afirmar_igual "sae" "$(visto 'e["ajustes"]["802-11-wireless-security"]["key-mgmt"]')" \
    "WPA3 sola va como sae"
arrancar_falso
r="$(conectar "Cafe libre" "" abierta)"
afirmar_igual "ok" "$r" "una abierta conecta"
afirmar_igual "False" "$(visto '"802-11-wireless-security" in e["ajustes"]')" \
    "sin seccion de seguridad"

titulo "4. La contraseña no sale en ninguna linea de ordenes"
afirmar_no_contiene "$TMP/lineas.txt" "buena-clave" "ni la buena"
afirmar_no_contiene "$TMP/lineas.txt" "mala-clave" "ni la mala"
afirmar "(y se miro de verdad: hay lineas apuntadas)" test -s "$TMP/lineas.txt"

afirmar_intacta_la_casa_real
resumen
