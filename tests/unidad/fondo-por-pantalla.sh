#!/usr/bin/env bash
# tests/unidad/fondo-por-pantalla.sh — con dos pantallas, cada una pausa SU fondo
# por lo que haya en el escritorio que enseña (2026-11-02).
#
# POR QUE EXISTE ESTA PRUEBA
# --------------------------
# Antes habia un solo mpvpaper para todas las pantallas y el demonio miraba
# solo el escritorio con el FOCO: el usuario saltaba a un escritorio vacio en
# una pantalla para ver su fondo moverse, y el fondo se ponia en marcha tambien
# detras de las apps de la otra (y al reves). Ahora hay uno por pantalla; lo
# que vigila esta prueba:
#
#   1. cada mpvpaper se pausa por SU pantalla, no por la del foco;
#   2. un escritorio especial abierto encima (scratchpad) tambien tapa;
#   3. si a una pantalla le falta su fondo, se relanza (y no antes de la
#      gracia: al enchufar una, monitores.py ya lo relanza).
#
# Montaje como fondo-gaming.sh: el demonio de verdad en una COPIA del repo, un
# Hyprland de mentira que contesta j/monitors y j/workspaces leyendo un JSON que
# la prueba cambia en marcha, y dos mpvpaper de mentira (se llaman asi para el
# kernel y llevan su socket en la linea de ordenes) que contestan a
# get/set_property pause como mpv y apuntan su estado en un fichero.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
binario_falso notify-send

COPIA="$(copiar_repo)"
DEMONIO="$COPIA/hypr/scripts/wallpaper-pause.py"
cat > "$COPIA/hypr/scripts/wallpaper.sh" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$REGISTRO/wallpaper.log"
EOF
chmod +x "$COPIA/hypr/scripts/wallpaper.sh"
mkdir -p "$COPIA/hypr/wallpapers"
touch "$COPIA/hypr/wallpapers/fondo.mp4"
ln -sfn fondo.mp4 "$COPIA/hypr/wallpapers/current"

SIG="sesion-dos-pantallas"
export HYPRLAND_INSTANCE_SIGNATURE="$SIG"
mkdir -p "$XDG_RUNTIME_DIR/hypr/$SIG"
ESTADO="$TMP/hypr.json"

# estado <ws de DP-1> <ws de HDMI> <ventanas por ws: "1:2 2:0"> [especial de HDMI]
estado() {
    python3 - "$ESTADO" "$@" <<'PY'
import json, sys
ruta, ws_dp, ws_hdmi, ventanas = sys.argv[1:5]
especial = int(sys.argv[5]) if len(sys.argv) > 5 else 0
v = {int(a): int(b) for a, b in (x.split(":") for x in ventanas.split())}
monitores = [
    {"name": "DP-1", "focused": True, "activeWorkspace": {"id": int(ws_dp)},
     "specialWorkspace": {"id": 0}},
    {"name": "HDMI-A-1", "focused": False, "activeWorkspace": {"id": int(ws_hdmi)},
     "specialWorkspace": {"id": especial}},
]
json.dump({"monitors": monitores,
           "workspaces": [{"id": k, "windows": n} for k, n in v.items()]},
          open(ruta + ".nuevo", "w"))
import os; os.replace(ruta + ".nuevo", ruta)
PY
}
estado 1 2 "1:2 2:0"

python3 - "$XDG_RUNTIME_DIR/hypr/$SIG" "$ESTADO" <<'PY' &
import json, os, socket, sys, threading, time
base, ruta = sys.argv[1:3]
def servir(nombre, contestar):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(os.path.join(base, nombre)); s.listen(16)
    while True:
        c, _ = s.accept()
        if contestar:
            try:
                pedido = c.recv(4096).decode()
                datos = json.load(open(ruta))
                clave = pedido[2:] if pedido.startswith("j/") else pedido
                c.sendall(json.dumps(datos.get(clave, [])).encode())
            except (OSError, ValueError):
                pass
            c.close()
        else:
            threading.Thread(target=lambda c=c: (time.sleep(300), c.close()), daemon=True).start()
threading.Thread(target=servir, args=(".socket.sock", True), daemon=True).start()
servir(".socket2.sock", False)
PY
FALSO_HYPR=$!

# Un mpvpaper de mentira por pantalla: atiende su socket como mpv (pause) y
# apunta lo que tiene puesto en $REGISTRO/pausa.<salida>.
mpv_falso() {
    local salida="$1" sock="$XDG_RUNTIME_DIR/mpvpaper.$SIG.$1.sock"
    python3 - "$sock" "$REGISTRO/pausa.$salida" "--input-ipc-server=$sock" <<'PY' &
import ctypes, json, os, socket, sys
ctypes.CDLL(None).prctl(15, b"mpvpaper", 0, 0, 0)
sock, registro = sys.argv[1:3]
pausa = False
open(registro, "w").write("False")
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.bind(sock); s.listen(8)
while True:
    c, _ = s.accept()
    try:
        orden = json.loads(c.recv(4096).decode().splitlines()[0])["command"]
        if orden[0] == "set_property" and orden[1] == "pause":
            pausa = bool(orden[2])
            open(registro, "w").write(str(pausa))
            c.sendall(b'{"error":"success"}\n')
        else:
            c.sendall(json.dumps({"error": "success", "data": pausa}).encode() + b"\n")
    except (OSError, ValueError, IndexError, KeyError):
        pass
    c.close()
PY
}
mpv_falso DP-1;     MPV_DP=$!
mpv_falso HDMI-A-1; MPV_HDMI=$!

limpiar() {
    kill "$PID_DEMONIO" "$FALSO_HYPR" "$MPV_DP" "$MPV_HDMI" 2>/dev/null
    wait 2>/dev/null
    limpiar_entorno
}
trap limpiar EXIT INT TERM

pausa() { cat "$REGISTRO/pausa.$1" 2>/dev/null; }
# esperar hasta que las dos pantallas digan lo esperado (el latido es de 5 s)
esperar_pausas() {
    local dp="$1" hdmi="$2" i
    for i in $(seq 40); do
        [ "$(pausa DP-1)" = "$dp" ] && [ "$(pausa HDMI-A-1)" = "$hdmi" ] && return 0
        sleep 0.25
    done
    return 1
}

sleep 0.5
"$DEMONIO" >"$TMP/demonio.log" 2>&1 &
PID_DEMONIO=$!

titulo "1. Cada pantalla, por SU escritorio"
afirmar "apps en el Gigabyte (DP-1) y escritorio vacio en el TES: pausa solo DP-1" \
    esperar_pausas True False
estado 1 2 "1:0 2:3"
afirmar "se da la vuelta: el foco sigue en DP-1, y aun asi se pausa la del TES" \
    esperar_pausas False True
estado 3 2 "1:4 2:3 3:0"
afirmar "saltar a un escritorio vacio en DP-1 pone en marcha SOLO el fondo de DP-1" \
    esperar_pausas False True

titulo "2. Un escritorio especial encima tambien tapa"
estado 3 4 "3:0 4:0 -98:1" -98
afirmar "el TES con el escritorio vacio pero el scratchpad abierto: pausado" \
    esperar_pausas False True

titulo "3. Cada pantalla con su fondo vivo"
afirmar "con los dos vivos no relanza nada" test ! -s "$REGISTRO/wallpaper.log"
kill "$MPV_HDMI"; wait "$MPV_HDMI" 2>/dev/null
rm -f "$XDG_RUNTIME_DIR/mpvpaper.$SIG.HDMI-A-1.sock"
sleep 2
afirmar "a los 2 s todavia no (gracia: al enchufar, monitores.py ya lo relanza)" \
    test ! -s "$REGISTRO/wallpaper.log"
for _ in $(seq 40); do [ -s "$REGISTRO/wallpaper.log" ] && break; sleep 0.25; done
afirmar_contiene "$REGISTRO/wallpaper.log" "--only-mpv" \
    "al TES le falta su fondo: lo relanza (con --only-mpv, sin matar al demonio)"
afirmar "el demonio sigue en pie" kill -0 "$PID_DEMONIO"
afirmar "y sin nada por stderr" test ! -s "$TMP/demonio.log"
[ -s "$TMP/demonio.log" ] && sed 's/^/      /' "$TMP/demonio.log" | head -10

afirmar_intacta_la_casa_real
resumen
