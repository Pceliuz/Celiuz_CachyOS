#!/usr/bin/env bash
# tests/e2e/bluetooth.sh — el demonio de los auriculares entero, hablando por
# D-Bus con un BlueZ falso: que se conecte solo, que el cerrojo aguante por las
# dos puertas, que soltar a mano no se deshaga solo, y que al salir no deje a
# nadie bloqueado.
#
# COMO SE PRUEBA SIN TOCAR TU BLUETOOTH
# -------------------------------------
# La prueba se vuelve a lanzar dentro de `dbus-run-session`, que le da un bus
# privado, y apunta DBUS_SYSTEM_BUS_ADDRESS a ese bus. Gio respeta esa variable,
# asi que bluetooth.py cree que habla con el bus del sistema y habla con
# tests/lib/bluez_falso.py. No hay ninguna variable de pruebas dentro del
# script: se ejerce el codigo tal cual va a correr.
#
# Y se comprueba antes de nada, con tres guardias: que el bus no es el de tu
# sesion, que el falso consiguio el nombre org.bluez (en el bus de verdad lo
# tiene bluetoothd y no podria), y que `bluetooth.py --ver` ve los aparatos
# falsos y no los tuyos. Si falla una, la prueba se para sin arrancar el demonio.
#
# LOS APARATOS DE MENTIRA
#   A   auriculares, usados hace poco        (el preferido)
#   B   auriculares, usados hace mas
#   C   auriculares, bloqueados por el cerrojo en un arranque anterior
#   D   auriculares, bloqueados POR TI: no se tocan nunca
#   R   un raton conectado: no es de audio, no se toca nunca
#   N   unos auriculares vistos pero sin emparejar: tampoco
#
# Los tiempos van con margen (el demonio espera 1 s antes de la primera ronda y
# el falso tarda 0,3 s en cada llamada); cada espera sondea y sale en cuanto se
# cumple, asi que en una maquina rapida la prueba no tarda mas por eso.

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

# La huella del estado de VERDAD, antes de nada. No vale «que no exista»: en un
# equipo donde el demonio ya corre, existe, y es suyo. Lo que no puede pasar es
# que CAMBIE mientras corre la prueba. (Falsa alarma conocida, como la de la
# cache y el bloqueo: si conectas o sueltas un auricular DE VERDAD mientras
# corre, tu demonio lo apunta ahi y esto salta sin culpa de la prueba.)
huella_estado_real() {
    local f="${_BT_STATE_REAL:-$CASA_REAL/.local/state}/celiuz/bluetooth.json"
    [ -e "$f" ] && sha256sum < "$f" | cut -c1-16 || echo "(no existe)"
}
HUELLA_ESTADO_REAL="$(huella_estado_real)"

SCRIPT="$REPO/hypr/scripts/bluetooth.py"
FALSO="$DIR/../lib/bluez_falso.py"
export DBUS_SYSTEM_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS"

A=AA:AA:AA:AA:AA:01 B=AA:AA:AA:AA:AA:02 C=AA:AA:AA:AA:AA:03
D=AA:AA:AA:AA:AA:04 R=AA:AA:AA:AA:AA:05 N=AA:AA:AA:AA:AA:06

# Los avisos se apuntan en vez de salir; systemctl dice que no hay demonio (lo
# pregunta --ver); rfkill no debe llamarse con el adaptador sin bloquear.
binario_falso notify-send 0
binario_falso systemctl 3
binario_falso rfkill 0

PID_FALSO=""
PID_DEMONIO=""
parar() {
    [ -n "$PID_DEMONIO" ] && kill "$PID_DEMONIO" 2>/dev/null
    [ -n "$PID_FALSO" ] && kill "$PID_FALSO" 2>/dev/null
    wait 2>/dev/null
    limpiar_entorno
}
trap parar EXIT INT TERM

# --- Utilidades -----------------------------------------------------------------

orden() { python3 "$FALSO" "$@"; }

# prop <mac> <propiedad> -> true/false
prop() {
    orden Estado | python3 -c '
import json, sys
e = json.load(sys.stdin)
print(str(e["aparatos"][sys.argv[1]][sys.argv[2]]).lower())' "$1" "$2"
}

llamadas() {   # llamadas <mac>: cuantas veces se llamo a Connect sobre el
    orden Estado | python3 -c '
import json, sys
print(json.load(sys.stdin)["llamadas"].count(sys.argv[1]))' "$1"
}

primeras_llamadas() {   # las macs de las primeras N llamadas, en orden
    orden Estado | python3 -c '
import json, sys
print(",".join(json.load(sys.stdin)["llamadas"][:int(sys.argv[1])]))' "$1"
}

# esperar_a <segundos> <comando...>: sondea hasta que el comando se cumpla.
#
# OJO: el comando tiene que MIRAR en cada vuelta. `esperar_a 5 test "$(x)" = y`
# no espera nada: el $(x) lo expande bash una sola vez, antes de llamar, y el
# sondeo repite la misma comparacion con el mismo valor viejo. Por eso todo lo
# que se espera va por una funcion de las de abajo, que pregunta de nuevo.
esperar_a() {
    local limite=$(( $(date +%s%N) + $1 * 1000000000 )); shift
    while [ "$(date +%s%N)" -lt "$limite" ]; do
        "$@" >/dev/null 2>&1 && return 0
        sleep 0.1
    done
    "$@" >/dev/null 2>&1
}
es() { [ "$(prop "$1" "$2")" = "$3" ]; }
llamado_al_menos() { [ "$(llamadas "$1")" -ge "$2" ]; }
potencia_es() { orden Estado | grep -q "\"powered\": $1"; }

estado_recuerdo() {   # estado_recuerdo <clave>: la lista guardada, separada por comas
    python3 -c '
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except OSError:
    d = {}
v = d.get(sys.argv[2], [])
print(",".join(sorted(v)) if isinstance(v, list) else ",".join(sorted(v.keys())))' "$1" "$2"
}
lista_es() { [ "$(estado_recuerdo "$1" "$2")" = "$3" ]; }
ESTADO="$XDG_STATE_HOME/celiuz/bluetooth.json"
SUELTOS="$XDG_RUNTIME_DIR/celiuz-bluetooth.json"

# --- El mundo inicial -------------------------------------------------------------

SINK='"0000110b-0000-1000-8000-00805f9b34fb", "0000111e-0000-1000-8000-00805f9b34fb"'
cat > "$TMP/aparatos.json" <<EOF
[
  {"mac": "$A", "nombre": "Auris A", "uuids": [$SINK]},
  {"mac": "$B", "nombre": "Auris B", "uuids": [$SINK]},
  {"mac": "$C", "nombre": "Auris C", "uuids": [$SINK], "bloqueado": true},
  {"mac": "$D", "nombre": "Auris D", "uuids": [$SINK], "bloqueado": true, "encendido": true},
  {"mac": "$R", "nombre": "Raton", "icono": "input-mouse",
   "uuids": ["00001124-0000-1000-8000-00805f9b34fb"], "conectado": true, "encendido": true},
  {"mac": "$N", "nombre": "Sin emparejar", "uuids": [$SINK], "emparejado": false,
   "encendido": true}
]
EOF

# Lo que dejo un arranque anterior: A usado despues que B, y C bloqueado por el
# cerrojo (el equipo se apago con otro puesto).
mkdir -p "$(dirname "$ESTADO")"
cat > "$ESTADO" <<EOF
{"ultimo_uso": {"$A": 2000.0, "$B": 1000.0}, "bloqueados": ["$C"]}
EOF

titulo "Guardias: esto es un bus privado con un BlueZ falso"
if [ -n "${_BT_BUS_DE_FUERA:-}" ] && [ "$DBUS_SESSION_BUS_ADDRESS" = "$_BT_BUS_DE_FUERA" ]; then
    fallo "el bus es privado" "es el de tu sesion: no sigo"
    resumen; exit 1
fi
ok "el bus es privado ($DBUS_SESSION_BUS_ADDRESS)"

python3 "$FALSO" servir "$TMP/aparatos.json" > "$TMP/falso.log" 2>&1 &
PID_FALSO=$!
if ! esperar_a 5 grep -q '^listo' "$TMP/falso.log"; then
    fallo "el BlueZ falso consigue org.bluez" "$(cat "$TMP/falso.log")"
    resumen; exit 1
fi
ok "el BlueZ falso consigue org.bluez"

"$SCRIPT" --ver > "$TMP/ver-inicial.txt" 2>&1
# Toda MAC que salga tiene que ser de las falsas (AA:AA:AA:AA:AA:0x). Una sola
# de otra forma es un aparato de verdad, sea de quien sea el equipo.
ajenas="$(grep -o -E '([0-9A-F]{2}:){5}[0-9A-F]{2}' "$TMP/ver-inicial.txt" | grep -v '^AA:AA:AA:AA:AA:0')"
if ! grep -q "$A" "$TMP/ver-inicial.txt" || [ -n "$ajenas" ]; then
    fallo "bluetooth.py --ver ve los aparatos falsos" "$(cat "$TMP/ver-inicial.txt")"
    resumen; exit 1
fi
ok "bluetooth.py --ver ve los aparatos falsos, y ninguno de verdad"
afirmar_contiene "$TMP/ver-inicial.txt" "Auris D .*bloqueado por ti" \
    "--ver distingue el bloqueado por ti..."
afirmar_contiene "$TMP/ver-inicial.txt" "Auris C .*bloqueado por el cerrojo" \
    "...del bloqueado por el cerrojo"
afirmar_no_contiene "$TMP/ver-inicial.txt" "Sin emparejar" \
    "--ver no lista como auriculares a los que no estan emparejados"

# --- 1. Arranca con todo apagado -------------------------------------------------

titulo "1. Arranca sin ningun auricular encendido"
"$SCRIPT" --demonio > "$TMP/demonio.log" 2>&1 &
PID_DEMONIO=$!

afirmar "suelta a C, que el cerrojo dejo bloqueado en un arranque anterior" \
    esperar_a 5 es "$C" Blocked false
afirmar "y lo borra de su lista" esperar_a 3 lista_es "$ESTADO" bloqueados ""
afirmar "hace una ronda entera, hasta C" esperar_a 6 llamado_al_menos "$C" 1
afirmar_igual "$A,$B,$C" "$(primeras_llamadas 3)" \
    "en orden: A (el ultimo usado), B, y C (nunca usado) al final"
afirmar_igual "0" "$(llamadas "$D")" "a D, bloqueado por ti, no lo llama"
afirmar_igual "true" "$(prop "$D" Blocked)" "ni le quita tu bloqueo"
afirmar_igual "0" "$(llamadas "$N")" "al que no esta emparejado no lo llama"
afirmar_igual "0" "$(llamadas "$R")" "al raton no lo llama"

# --- 2. Enciendes A y B: gana el de la ultima vez ---------------------------------

titulo "2. Dos encendidos a la vez: gana el que usaste la ultima vez"
orden Encender "$B" si >/dev/null
orden Encender "$A" si >/dev/null
# Apagar y encender con la orden de la barra: pone la ronda en marcha ya, sin
# esperar al ritmo lento, y de paso prueba `alternar`.
"$SCRIPT" alternar
afirmar "alternar apaga el Bluetooth" esperar_a 3 potencia_es false
"$SCRIPT" alternar
afirmar "y lo vuelve a encender" esperar_a 3 potencia_es true
# Apagar el adaptador desconecta a todos, raton incluido, como el real. Un raton
# de verdad vuelve a llamar solo en cuanto hay radio: aqui se le hace llamar.
afirmar_igual "true" "$(orden Entrante "$R")" "el raton vuelve a entrar por su cuenta"
afirmar "se conecta A" esperar_a 6 es "$A" Connected true
afirmar_igual "false" "$(prop "$B" Connected)" "B, aunque estaba encendido, no"
afirmar "B queda bloqueado por el cerrojo" esperar_a 3 es "$B" Blocked true
afirmar "C tambien" esperar_a 3 es "$C" Blocked true
afirmar_igual "$B,$C" "$(estado_recuerdo "$ESTADO" bloqueados)" \
    "y los dos quedan apuntados como suyos"
afirmar_igual "true" "$(prop "$R" Connected)" "el raton sigue conectado"
afirmar_igual "false" "$(prop "$R" Blocked)" "y sin bloquear"
afirmar_igual "false" "$(prop "$N" Blocked)" "al que no esta emparejado no se le bloquea"
afirmar_igual "0" "$(veces_llamado rfkill)" "rfkill no se toca si no hay bloqueo de rfkill"

# --- 3. El cerrojo, por la puerta de fuera ---------------------------------------

titulo "3. Con A en uso, B llama por su cuenta"
afirmar_igual "false" "$(orden Entrante "$B")" "B no puede entrar: esta bloqueado"
afirmar_igual "true" "$(prop "$A" Connected)" "A sigue en uso"

# --- 4. El cerrojo, por la puerta de dentro --------------------------------------

titulo "4. Con A en uso, alguien llama a B desde aqui (como haria bluetui)"
orden Connect "$B" >/dev/null
afirmar "B se cuela un instante y se le echa" esperar_a 4 es "$B" Connected false
afirmar_igual "true" "$(prop "$A" Connected)" "A sigue en uso"
sleep 1.5
afirmar_igual "1" "$(veces_llamado notify-send)" "sale UN aviso, no uno por pasada"
afirmar_contiene "$REGISTRO/notify-send.log" "No se conecto Auris B" \
    "el aviso dice a quien se echo"
afirmar_contiene "$REGISTRO/notify-send.log" "Ya estas usando Auris A" \
    "y por que"

# --- 5. Soltar a mano para cambiar de auricular ----------------------------------

titulo "5. Sueltas A: entra B, y A no vuelve solo"
# El demonio no cuenta como «soltado» una caida de menos de MINIMO_EN_USO (3 s).
sleep 3
"$SCRIPT" soltar > "$TMP/soltar.txt" 2>&1
afirmar_contiene "$TMP/soltar.txt" "Soltado: Auris A" "soltar dice a quien solto"
afirmar "entra B, que estaba encendido" esperar_a 6 es "$B" Connected true
afirmar_igual "false" "$(prop "$A" Connected)" "A no se ha vuelto a conectar"
afirmar "y ahora el bloqueado es A" esperar_a 3 es "$A" Blocked true
afirmar_igual "$A" "$(estado_recuerdo "$SUELTOS" soltados)" \
    "A queda apuntado como soltado, en XDG_RUNTIME_DIR"
afirmar_contiene "$TMP/demonio.log" "Auris A soltado a mano" \
    "el diario lo cuenta como soltado a mano"

titulo "6. Apagas B (motivo Remote): A sigue soltado y no se le llama"
antes_a="$(llamadas "$A")"
# Pasados los 3 s de MINIMO_EN_USO, para que lo unico que distinga «se apago»
# de «lo soltaste» sea el MOTIVO. Con menos, esa otra regla lo tapaba: una
# version que tomara cualquier caida por soltada pasaba esta prueba en verde.
sleep 3.5
orden Encender "$B" no org.bluez.Reason.Remote >/dev/null
afirmar "B se va" esperar_a 3 es "$B" Connected false
afirmar "se suelta el cerrojo sobre A" esperar_a 3 es "$A" Blocked false
sleep 3
afirmar_igual "$antes_a" "$(llamadas "$A")" \
    "a A no se le llama aunque esta encendido: lo soltaste tu"
afirmar_igual "false" "$(prop "$A" Connected)" "y sigue sin conectarse"
afirmar_contiene "$TMP/demonio.log" "Auris B desconectado \(Remote\)" \
    "apagar B no cuenta como soltarlo"

# --- 7. Apagar y encender el Bluetooth: se empieza de cero -----------------------

titulo "7. Apagas y enciendes el Bluetooth: se olvidan los soltados"
"$SCRIPT" alternar
afirmar "apagado, no queda nada del cerrojo" esperar_a 3 lista_es "$ESTADO" bloqueados ""
afirmar_igual "true" "$(prop "$D" Blocked)" "salvo lo tuyo: D sigue bloqueado"
"$SCRIPT" alternar
afirmar "encendido, A vuelve a entrar solo" esperar_a 6 es "$A" Connected true
afirmar_igual "true" "$(orden Entrante "$R")" "(el raton vuelve a entrar)"
afirmar_igual "" "$(estado_recuerdo "$SUELTOS" soltados)" "ya no hay soltados"

# --- 7b. Pedirlo tu gana a «soltado» ---------------------------------------------

titulo "7b. Sueltas A y luego lo pides con «conectar»: entra, aunque este soltado"
sleep 3.5   # MINIMO_EN_USO: que la caida cuente como soltarlo
"$SCRIPT" soltar >/dev/null 2>&1
afirmar "A queda soltado" esperar_a 3 lista_es "$SUELTOS" soltados "$A"
sleep 2
afirmar_igual "false" "$(prop "$A" Connected)" "y el demonio no lo vuelve a llamar"
"$SCRIPT" conectar > "$TMP/conectar.txt" 2>&1
codigo=$?
afirmar_igual "0" "$codigo" "conectar sale bien"
afirmar_contiene "$TMP/conectar.txt" "Conectado: Auris A" "conectar llama a A aunque lo soltaste"
afirmar "A en uso otra vez, y ya no esta soltado" esperar_a 3 lista_es "$SUELTOS" soltados ""
"$SCRIPT" conectar > "$TMP/conectar2.txt" 2>&1
afirmar_contiene "$TMP/conectar2.txt" "Ya estas usando Auris A" \
    "con uno en uso, conectar no llama a nadie mas"

# --- 8. Una caida por distancia SI se recupera ------------------------------------

titulo "8. A se sale de alcance (Timeout) y vuelve: se recupera solo"
sleep 3.5   # por lo mismo que en el paso 6
orden Encender "$A" no org.bluez.Reason.Timeout >/dev/null
afirmar "A se cae" esperar_a 3 es "$A" Connected false
# Se deja que el demonio lo llame AL MENOS UNA VEZ con A todavia fuera, y que
# falle. Si A volviera antes de esa primera ronda (a 1 s), entraria a la
# primera y no se estaria probando que insiste; y si volviera justo despues,
# el reintento llega a los ESPERA_MIN (10 s). Encenderlo al azar entre las dos
# cosas era una prueba que pasaba o no segun la carga de la maquina.
antes_a="$(llamadas "$A")"
afirmar "el demonio lo busca aunque no conteste" \
    esperar_a 5 llamado_al_menos "$A" $((antes_a + 1))
orden Encender "$A" si >/dev/null
afirmar "y cuando vuelve, en el siguiente intento entra" \
    esperar_a 15 es "$A" Connected true

# --- 9. Al salir no deja a nadie bloqueado ----------------------------------------

titulo "9. Se para el demonio con A en uso"
afirmar "B esta bloqueado por el cerrojo" esperar_a 3 es "$B" Blocked true
afirmar "C tambien" esperar_a 3 es "$C" Blocked true
kill -TERM "$PID_DEMONIO"
wait "$PID_DEMONIO"
codigo=$?
PID_DEMONIO=""
afirmar_igual "0" "$codigo" "sale limpio con SIGTERM"
afirmar_igual "false" "$(prop "$B" Blocked)" "B queda desbloqueado"
afirmar_igual "false" "$(prop "$C" Blocked)" "C queda desbloqueado"
afirmar_igual "true" "$(prop "$D" Blocked)" "D, el tuyo, sigue como lo dejaste"
afirmar_igual "" "$(estado_recuerdo "$ESTADO" bloqueados)" "la lista del cerrojo queda vacia"
afirmar_igual "true" "$(prop "$R" Connected)" "el raton no se entero de nada"

# --- 10. Un equipo sin Bluetooth -------------------------------------------------
#
# Es el caso de quien clone el repo en un sobremesa sin radio, o con el servicio
# de BlueZ parado. El demonio arranca igual (lo lanza autostart.conf en todas
# partes) y no tiene que romperse, ni gastar, ni ensuciar el diario.

titulo "10. Un equipo sin BlueZ, y otro con BlueZ pero sin adaptador"
kill "$PID_FALSO" 2>/dev/null; wait "$PID_FALSO" 2>/dev/null; PID_FALSO=""
"$SCRIPT" --demonio > "$TMP/sin-bluez.log" 2>&1 &
PID_DEMONIO=$!
sleep 2
afirmar "el demonio sigue vivo sin BlueZ" kill -0 "$PID_DEMONIO"
afirmar_contiene "$TMP/sin-bluez.log" "BlueZ no esta corriendo" \
    "y dice que espera a que aparezca"

# Ahora arranca BlueZ, pero en un equipo sin radio: ningun adaptador.
python3 "$FALSO" servir "$TMP/aparatos.json" --sin-adaptador > "$TMP/falso2.log" 2>&1 &
PID_FALSO=$!
afirmar "el falso sin adaptador coge org.bluez" esperar_a 5 grep -q '^listo' "$TMP/falso2.log"
antes="$(llamadas "$A")"
sleep 3
afirmar_igual "$antes" "$(llamadas "$A")" "no se llama a nadie: no hay radio"
afirmar_igual "false" "$(prop "$B" Blocked)" "ni se bloquea a nadie"
afirmar "el demonio sigue vivo" kill -0 "$PID_DEMONIO"

salida_ver="$("$SCRIPT" --ver 2>&1)"
case "$salida_ver" in
    *"No hay ningun adaptador Bluetooth"*) ok "--ver lo dice con todas las letras" ;;
    *) fallo "--ver dice que no hay adaptador" "$salida_ver" ;;
esac

kill -TERM "$PID_DEMONIO"; wait "$PID_DEMONIO"; PID_DEMONIO=""
cat "$TMP/sin-bluez.log" >> "$TMP/demonio.log"

titulo "El demonio no se quejo de nada raro"
# Todo lo que escribe el demonio empieza por «bluetooth: ». Cualquier otra linea
# es Python quejandose: un traceback, o un aviso de API obsoleta, que no rompe
# nada hoy pero llena el diario en cada arranque (se colo uno asi, y buscar solo
# «Error» no lo vio).
if grep -v '^bluetooth: ' "$TMP/demonio.log" >/dev/null; then
    fallo "el diario del demonio solo trae lo suyo" "$(grep -v '^bluetooth: ' "$TMP/demonio.log" | head -5)"
else
    ok "el diario del demonio solo trae lo suyo"
fi
afirmar "stderr del falso limpio" test "$(grep -v '^listo' "$TMP/falso.log" | wc -l)" -eq 0

afirmar_intacta_la_casa_real
afirmar_igual "$HUELLA_ESTADO_REAL" "$(huella_estado_real)" \
    "no toco el estado de Bluetooth de verdad (el de tu demonio)"

resumen
