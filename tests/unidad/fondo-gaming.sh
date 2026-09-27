#!/usr/bin/env bash
# tests/unidad/fondo-gaming.sh — con el modo gaming puesto, el fondo en vídeo se
# apaga (mpvpaper muerto: es VRAM que el juego necesita) y al salir se levanta.
#
# Montaje: el demonio de verdad en una COPIA del repo, con un Hyprland de
# mentira que atiende conexiones (un doble que solo escucha acaba fingiendo un
# compositor muerto, ver CLAUDE.md), un `mpvpaper` de mentira que lleva el
# socket de ESTA sesión en su línea de órdenes —que es como el demonio reconoce
# el suyo— y un wallpaper.sh que solo apunta que lo llamaron. Nada de esto toca
# el mpvpaper de verdad: el demonio mata por PID y por socket, no por nombre.

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
# Con un fondo elegido, como en cualquier equipo en uso. Sin `current` el
# demonio no intenta nunca resucitar mpvpaper, y justo ahi vivia un fallo: lo
# resucitaba en la vuelta siguiente a matarlo por el juego.
mkdir -p "$COPIA/hypr/wallpapers"
touch "$COPIA/hypr/wallpapers/fondo.mp4"
ln -sfn fondo.mp4 "$COPIA/hypr/wallpapers/current"

SIG="sesion-gaming"
export HYPRLAND_INSTANCE_SIGNATURE="$SIG"
mkdir -p "$XDG_RUNTIME_DIR/hypr/$SIG"
python3 - "$XDG_RUNTIME_DIR/hypr/$SIG" <<'PY' &
import os, socket, sys, threading, time
base = sys.argv[1]
def servir(nombre, contestar):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(os.path.join(base, nombre)); s.listen(16)
    while True:
        c, _ = s.accept()
        if contestar:
            try:
                c.recv(4096); c.sendall(b"[]")
            except OSError:
                pass
            c.close()
        else:
            threading.Thread(target=lambda c=c: (time.sleep(300), c.close()), daemon=True).start()
threading.Thread(target=servir, args=(".socket.sock", True), daemon=True).start()
servir(".socket2.sock", False)
PY
FALSO_HYPR=$!

# Un mpvpaper de mentira: se llama así para el kernel (`comm`, que es lo que
# mira el demonio; un script con `#!/usr/bin/env bash` se llamaría «bash») y
# lleva el socket de esta sesión en su línea de órdenes.
python3 -c 'import ctypes, time; ctypes.CDLL(None).prctl(15, b"mpvpaper", 0, 0, 0); time.sleep(600)' \
    "--input-ipc-server=$XDG_RUNTIME_DIR/mpvpaper.$SIG.sock" &
FALSO_MPV=$!

# Vivo de verdad: muerto y sin recoger (zombi, hijo de este script) no cuenta.
vivo() { local e; e="$(ps -o stat= -p "$1" 2>/dev/null)"; [ -n "$e" ] && [ "${e#Z}" = "$e" ]; }

limpiar() {
    kill "$PID_DEMONIO" "$FALSO_HYPR" "$FALSO_MPV" 2>/dev/null
    wait 2>/dev/null
    limpiar_entorno
}
trap limpiar EXIT INT TERM

sleep 0.5
"$DEMONIO" >"$TMP/demonio.log" 2>&1 &
PID_DEMONIO=$!
FIFO="$XDG_RUNTIME_DIR/wallpaper-pause.$SIG.fifo"
for _ in $(seq 20); do [ -p "$FIFO" ] && break; sleep 0.2; done
afirmar "el demonio abre su FIFO con la firma" test -p "$FIFO"
sleep 1
afirmar "sin modo gaming, el fondo sigue" vivo "$FALSO_MPV"

titulo "gaming-on"
printf 'gaming-on\n' > "$FIFO"
sleep 2
if vivo "$FALSO_MPV"; then
    fallo "mata mpvpaper" "seguía vivo a los 2 s: $(cat "$TMP/demonio.log")"
else
    ok "mata mpvpaper"
fi
sleep 6   # mas que el latido del demonio (PERIODO = 5 s): varias vueltas del bucle
afirmar "no lo resucita mientras dure el modo" test ! -s "$REGISTRO/wallpaper.log"

titulo "gaming-off"
printf 'gaming-off\n' > "$FIFO"
sleep 3
afirmar_contiene "$REGISTRO/wallpaper.log" "--only-mpv" "pide levantar el fondo otra vez"
afirmar "el demonio sigue en pie" kill -0 "$PID_DEMONIO"

afirmar_intacta_la_casa_real
resumen
