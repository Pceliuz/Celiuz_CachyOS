#!/usr/bin/env bash
# tests/e2e/bluetooth-panel.sh — los botones del panel de Bluetooth, de verdad
# por D-Bus, con el demonio (bluetooth.py --demonio) corriendo delante, contra un
# BlueZ falso en un bus privado. Ni una ventana: se ejerce `Control`, que es lo
# que llaman los botones.
#
# QUE VIGILA
# ----------
#   1. «Usar este» con unos auriculares puestos y el cerrojo: entra el nuevo,
#      sale el viejo, y el demonio NO echa al nuevo ni recupera al viejo.
#   2. Buscar enseña lo que aparece con nombre, y nada mas.
#   3. Emparejar unos auriculares nuevos con otros puestos: la busqueda se para
#      antes (con ella en marcha el Pair real fallo el 2026-10-19, y el falso
#      falla igual), queda emparejado, de confianza y conectado, el que estaba
#      sale, y el demonio no echa al nuevo. Y la busqueda vuelve despues.
#   4. El agente dice que si SOLO al aparato que se esta emparejando, y se va
#      al cerrar.
#   5. Renombrar y olvidar.
#
# Las guardias para no tocar tu Bluetooth son las de tests/e2e/bluetooth.sh: bus
# privado de dbus-run-session, y el falso tiene que conseguir org.bluez.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "${_BT_BUS_PRIVADO:-}" ]; then
    if ! command -v dbus-run-session >/dev/null 2>&1; then
        printf '\033[31m  ✗ falta dbus-run-session (paquete dbus)\033[0m\n'
        exit 1
    fi
    exec env _BT_BUS_PRIVADO=1 _BT_BUS_DE_FUERA="${DBUS_SESSION_BUS_ADDRESS:-}" \
        _BT_STATE_REAL="${XDG_STATE_HOME:-$HOME/.local/state}" \
        dbus-run-session -- bash "${BASH_SOURCE[0]}" "$@"
fi

. "$DIR/../lib/comun.sh"

preparar_entorno

huella_estado_real() {
    local f="${_BT_STATE_REAL:-$CASA_REAL/.local/state}/celiuz/bluetooth.json"
    [ -e "$f" ] && sha256sum < "$f" | cut -c1-16 || echo "(no existe)"
}
HUELLA_ESTADO_REAL="$(huella_estado_real)"

DEMONIO="$REPO/hypr/scripts/bluetooth.py"
PANEL="$REPO/hypr/scripts/bluetooth-panel.py"
FALSO="$DIR/../lib/bluez_falso.py"
export DBUS_SYSTEM_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS"

A=AA:AA:AA:AA:AA:01 B=AA:AA:AA:AA:AA:02 N=AA:AA:AA:AA:AA:06
M=AA:AA:AA:AA:AA:07 X=AA:AA:AA:AA:AA:08

binario_falso notify-send 0
binario_falso systemctl 3
binario_falso rfkill 0

PID_FALSO=""
PID_DEMONIO=""
parar() {
    [ -n "$PID_DEMONIO" ] && kill "$PID_DEMONIO" 2>/dev/null
    [ -n "$PID_FALSO" ] && kill "$PID_FALSO" 2>/dev/null
    wait 2>/dev/null
    [ -n "${_BT_GUARDAR:-}" ] && cp "$TMP/demonio.log" "$REGISTRO/notify-send.log" "$_BT_GUARDAR/" 2>/dev/null
    limpiar_entorno
}
trap parar EXIT INT TERM

orden() { python3 "$FALSO" "$@"; }
prop() {
    orden Estado | python3 -c '
import json, sys
e = json.load(sys.stdin)
a = e["aparatos"].get(sys.argv[1])
print("(no esta)" if a is None else str(a[sys.argv[2]]).lower())' "$1" "$2"
}
estado() {   # estado <clave>: un campo de Estado, en JSON
    orden Estado | python3 -c '
import json, sys
print(json.dumps(json.load(sys.stdin)[sys.argv[1]]))' "$1"
}
esperar_a() {
    local limite=$(( $(date +%s%N) + $1 * 1000000000 )); shift
    while [ "$(date +%s%N)" -lt "$limite" ]; do
        "$@" >/dev/null 2>&1 && return 0
        sleep 0.1
    done
    "$@" >/dev/null 2>&1
}
es() { [ "$(prop "$1" "$2")" = "$3" ]; }
no_busca() { [ "$(estado buscando)" = false ]; }
# sigue_siendo <segundos> <mac> <prop> <valor>: que NO cambie en ese rato.
sigue_siendo() {
    local fin=$(( $(date +%s%N) + $1 * 1000000000 ))
    while [ "$(date +%s%N)" -lt "$fin" ]; do
        es "$2" "$3" "$4" || return 1
        sleep 0.2
    done
}

# accion <orden> [mac] [argumento]: lo que haria el boton, y lo que contesto.
# Imprime «ok» o el error ya explicado. Con «buscar-y-emparejar» se busca antes,
# como en el panel abierto. Con «agente» se prueba el agente desde dentro.
accion() {
    python3 - "$PANEL" "$@" <<'PYEOF'
import importlib.util
import json
import sys

spec = importlib.util.spec_from_file_location("panel", sys.argv[1])
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
Gio, GLib = p.bt._gio()
orden, args = sys.argv[2], sys.argv[3:]

bus = p.bt.bus_del_sistema()
c = p.Control(bus)
c.foto()
bucle = GLib.MainLoop()
salida = {}


def listo(error):
    salida["r"] = error or "ok"
    bucle.quit()


if orden == "buscar":
    c.buscar(True)

    def mirar():
        m = p.construir(c.foto(), p.bt.Recuerdo.cargar(), p.bt.Ajustes.cargar())
        salida["r"] = json.dumps([f.mac for f in m.cerca])
        bucle.quit()
        return False
    GLib.timeout_add(1200, mirar)
elif orden == "buscar-y-emparejar":
    c.buscar(True)

    def emparejar():
        c.foto()
        c.emparejar(args[0], listo)
        return False
    GLib.timeout_add(1200, emparejar)
elif orden == "agente":
    c.registrar_agente()
    c.emparejando = c.ruta(args[0])
    respuestas = []

    def preguntar(mac, fin):
        def hecho(b, res, _d=None):
            try:
                b.call_finish(res)
                respuestas.append("si")
            except GLib.Error as e:
                respuestas.append("no" if "Rejected" in e.message else e.message)
            fin()
        bus.call(bus.get_unique_name(), p.RUTA_AGENTE, p.AGENTE, "RequestConfirmation",
                 GLib.Variant("(ou)", (c.ruta(mac), 123456)), None,
                 Gio.DBusCallFlags.NONE, 5000, None, hecho, None)

    def registrado():
        preguntar(args[0], lambda: preguntar(args[1], terminar))
        return False

    def terminar():
        salida["r"] = ",".join(respuestas)
        bucle.quit()
    GLib.timeout_add(400, registrado)
elif orden == "renombrar":
    c.renombrar(args[0], args[1], listo)
else:
    getattr(c, orden)(args[0], listo)

GLib.timeout_add(90_000, bucle.quit)
bucle.run()
c.cerrar()
print(salida.get("r", "(sin respuesta)"))
PYEOF
}

SINK='"0000110b-0000-1000-8000-00805f9b34fb", "0000111e-0000-1000-8000-00805f9b34fb"'
cat > "$TMP/aparatos.json" <<EOF
[
  {"mac": "$A", "nombre": "Auris A", "uuids": [$SINK], "encendido": true, "bateria": 70},
  {"mac": "$B", "nombre": "Auris B", "uuids": [$SINK], "encendido": true},
  {"mac": "$N", "nombre": "Auris nuevos", "uuids": [$SINK], "emparejado": false,
   "al_buscar": true, "encendido": true, "rssi": -50},
  {"mac": "$M", "nombre": "Movil", "icono": "phone", "emparejado": false,
   "al_buscar": true, "rssi": -60},
  {"mac": "$X", "nombre": "x", "icono": "", "emparejado": false, "al_buscar": true,
   "sin_nombre": true, "rssi": -40}
]
EOF
mkdir -p "$XDG_STATE_HOME/celiuz"
cat > "$XDG_STATE_HOME/celiuz/bluetooth.json" <<EOF
{"ultimo_uso": {"$A": 2000.0, "$B": 1000.0}, "bloqueados": []}
EOF

titulo "Guardias: bus privado y BlueZ falso"
if [ -n "${_BT_BUS_DE_FUERA:-}" ] && [ "$DBUS_SESSION_BUS_ADDRESS" = "$_BT_BUS_DE_FUERA" ]; then
    fallo "el bus es privado" "es el de tu sesion: no sigo"
    resumen; exit 1
fi
ok "el bus es privado"
python3 "$FALSO" servir "$TMP/aparatos.json" > "$TMP/falso.log" 2>&1 &
PID_FALSO=$!
if ! esperar_a 5 grep -q '^listo' "$TMP/falso.log"; then
    fallo "el BlueZ falso consigue org.bluez" "$(cat "$TMP/falso.log")"
    resumen; exit 1
fi
ok "el BlueZ falso consigue org.bluez"
"$PANEL" --ver > "$TMP/ver.txt" 2>&1
# El falso se llama «falso»: si --ver dice otro equipo, esto no es el bus privado.
if ! grep -q "^Bluetooth falso" "$TMP/ver.txt" || ! grep -q "Auris A" "$TMP/ver.txt"; then
    fallo "bluetooth-panel.py --ver ve solo lo falso" "$(cat "$TMP/ver.txt")"
    resumen; exit 1
fi
ok "bluetooth-panel.py --ver ve solo lo falso"

"$DEMONIO" --demonio > "$TMP/demonio.log" 2>&1 &
PID_DEMONIO=$!
afirmar "el demonio conecta A, el preferido" esperar_a 8 es "$A" Connected true
afirmar "y bloquea a B por el cerrojo" esperar_a 5 es "$B" Blocked true
# Lo que hace una persona: lleva un rato con A puesto antes de cambiar. Con menos
# de 3 s (MINIMO_EN_USO) el demonio no cuenta la salida de A como «soltado a
# mano» sino como una conexion que se cayo sola, y lo vuelve a llamar.
sleep 4

# --- 1. Usar este -----------------------------------------------------------------
titulo "1. «Usar este» con A puesto"
r="$(accion cambiar "$B")"
afirmar_igual "ok" "$r" "el boton contesta que fue bien"
afirmar "B entra" esperar_a 5 es "$B" Connected true
afirmar "A sale" es "$A" Connected false
afirmar "y el demonio no echa a B en los 3 s siguientes" sigue_siendo 3 "$B" Connected true
afirmar "ni recupera a A (lo soltaste para cambiar)" es "$A" Connected false
afirmar_no_contiene "$REGISTRO/notify-send.log" "No se conecto" "sin aviso de «no se conecto»"

# --- 2. Buscar ---------------------------------------------------------------------
titulo "2. Buscar"
r="$(accion buscar)"
afirmar_igual "[\"$N\", \"$M\"]" "$r" \
    "salen los nuevos con nombre, los auriculares primero, y el que no dice su nombre no"
afirmar "al cerrar se para la busqueda" esperar_a 3 no_busca

# --- 3. Emparejar con otros puestos -------------------------------------------------
titulo "3. Emparejar unos auriculares nuevos con B puesto"
r="$(accion buscar-y-emparejar "$N")"
afirmar_igual "ok" "$r" "el boton contesta que fue bien"
afirmar_igual "[\"$N\"]" "$(estado emparejos)" \
    "Pair se pidio UNA vez y con la busqueda parada (con ella, el falso falla)"
afirmar "queda emparejado" es "$N" Paired true
afirmar "y de confianza" es "$N" Trusted true
afirmar "y conectado" esperar_a 5 es "$N" Connected true
afirmar "B sale" es "$B" Connected false
afirmar "y el demonio no echa al nuevo en los 3 s siguientes" sigue_siendo 3 "$N" Connected true
afirmar_no_contiene "$REGISTRO/notify-send.log" "No se conecto" "sin aviso de «no se conecto»"

# --- 4. El agente --------------------------------------------------------------------
titulo "4. El agente"
r="$(accion agente "$N" "$M")"
afirmar_igual "si" "$(echo "$r" | tail -1 | cut -d, -f1)" "dice que si al que se empareja"
afirmar_igual "no" "$(echo "$r" | tail -1 | cut -d, -f2)" "y que no a cualquier otro"
afirmar_igual "[]" "$(estado agentes)" "y al cerrar se da de baja"

# --- 5. Renombrar y olvidar --------------------------------------------------------
titulo "5. Renombrar y olvidar"
afirmar_igual "ok" "$(accion renombrar "$A" "Auris negros")" "renombrar contesta bien"
afirmar_igual "auris negros" "$(prop "$A" Alias)" "y BlueZ tiene el nombre nuevo"
afirmar_igual "ok" "$(accion olvidar "$A")" "olvidar contesta bien"
afirmar_igual "(no esta)" "$(prop "$A" Alias)" "y el aparato ya no esta"
afirmar "el demonio sigue vivo" kill -0 "$PID_DEMONIO"

afirmar_igual "$HUELLA_ESTADO_REAL" "$(huella_estado_real)" \
    "el estado de verdad del demonio (~/.local/state) no se toco"
afirmar_intacta_la_casa_real
resumen
