#!/usr/bin/env bash
# ~/dotfiles/hypr/scripts/lock.sh
#
# Bloquea la pantalla con hyprlock: fondo de pantalla detras, escritorio a salvo
# y las aplicaciones congeladas (menos los juegos y las terminales).
#
# =============================================================================
# LO PRIMERO, PORQUE COSTO DOS REINICIOS
# =============================================================================
# NUNCA ejecutes el binario `hyprlock` a mano en tu sesion para probar algo. Lo
# hicimos dos veces el 2026-07-27 —una con `timeout 3` solo para ver si parseaba
# una config— y las dos veces acabo igual: hyprlock BLOQUEA la sesion nada mas
# arrancar, el proceso que lo lanzo murio, se lo llevo por delante, y quedo la
# pantalla de Hyprland "you locked your screen but the lockscreen app died", que
# solo se sale por otro tty. Para probar hay un Hyprland anidado.
# (Hay un cerrojo automatico en ~/.claude/hooks/guard-hyprlock.py.)
#
# Este script existe para que eso no pueda pasar en el uso normal:
#   1. Se DESPEGA con `setsid -f`: el bloqueo no cuelga de quien lo llamo.
#   2. Lleva un BUCLE VIGILANTE: si hyprlock muere con la sesion bloqueada, lo
#      relanza y RETOMA el bloqueo. Depende de misc:allow_session_lock_restore
#      en conf/misc.conf; las dos piezas van juntas.
#
# =============================================================================
# QUE HACE, EN ORDEN
# =============================================================================
#   1. Guarda el escritorio en el que estas y salta a uno vacio.
#   2. Esconde las barras (arriba y dock).
#   3. Congela las aplicaciones, salvo juegos y terminales (lib/congelar.py).
#   4. Enciende el xray y escribe el fragmento de fondo transparente.
#   5. Bloquea, y no se rinde si hyprlock cae.
#   6. Al desbloquear DESHACE TODO, pase lo que pase (trap EXIT).
#
# POR QUE EL ESCRITORIO VACIO Y LAS BARRAS ESCONDIDAS
# ---------------------------------------------------
# Porque el xray no ensena solo el fondo: ensena todo lo que hay debajo. En la
# prueba del 2026-07-27 se leia el texto de una ventana abierta y, con la barra
# puesta, la temperatura, la CPU, la RAM, el volumen y hasta la IP (10.16.236.x)
# por encima del bloqueo. Un bloqueo que ensena tu escritorio no es un bloqueo.
# Saltar a un escritorio vacio es el mismo truco que ya usa CeliuzPaper.
#
# Y las dos piezas se refuerzan: una app CONGELADA no puede abrir ventanas, que
# es el hueco que le quedaria al xray (una notificacion emergente si se veria).
#
# MODO_FONDO
# ----------
#   xray       el video del fondo se ve MOVIENDOSE detras del bloqueo.
#   fotograma  una foto del fondo, quieta. No toca ninguna opcion de Hyprland.
#              Es el modo de reserva si el xray diera problemas.
#
# MANTENER_VIDEO
# --------------
# Con 1, el video sigue reproduciendose bloqueado. Con MODO_FONDO=xray tiene que
# ser 1 o no habria nada que ver. Con `fotograma` puedes ponerlo a 0 y ahorrar
# ~3,5% de un nucleo, porque la imagen ya esta capturada.
#
# CONGELAR
# --------
# Con 1 se congelan las apps al bloquear. Que se salva lo decide
# lib/juegos.py por capas (Steam, ananicy, flatpaks de juego, pantalla completa)
# mas hypr/congelar-excepciones.json. Si algo se quedara congelado, SIEMPRE
# tienes una terminal viva (no se congelan nunca) para:
#     ~/dotfiles/hypr/scripts/lib/congelar.py descongelar

set -uo pipefail

# Todos los ajustes se pueden forzar desde el entorno. Sirve para dos cosas:
# probar el script en un Hyprland ANIDADO sin tocar tu sesion (apagando el
# congelado y desviando los FIFOs), y para que mas adelante el auto-bloqueo por
# inactividad pueda llamar aqui con otros valores sin duplicar el script.
MODO_FONDO="${MODO_FONDO:-xray}"
MANTENER_VIDEO="${MANTENER_VIDEO:-1}"
CONGELAR="${CONGELAR:-1}"
# Escritorio al que saltar para que el xray no ensene tus ventanas. Va fuera de
# tu numeracion (tienes binds del 1 al 7) para no ocuparte ninguno.
WORKSPACE_LIMPIO="${WORKSPACE_LIMPIO:-99}"
REINTENTOS="${REINTENTOS:-5}"

RUNTIME="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
FIFO="${FIFO:-$RUNTIME/wallpaper-pause.fifo}"
FIFO_BARRAS="${FIFO_BARRAS:-$RUNTIME/waybar-autohide.fifo}"
MPV="$RUNTIME/mpvpaper.sock"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/celiuzpaper"
FONDO="$CACHE/lock-bg.jpg"
# El temporal lleva el .jpg AL FINAL a proposito: ffmpeg elige el formato de
# salida por la extension, y un `lock-bg.jpg.tmp` le hace fallar con "Unable to
# choose an output format".
FONDO_TMP="$CACHE/lock-bg.tmp.jpg"
# Fragmento que hyprlock.conf carga con `source`. Ver el comentario de alli.
FRAGMENTO="$CACHE/lock-fondo.conf"
LOG="$CACHE/lock.log"
SCRIPTS="$HOME/dotfiles/hypr/scripts"

# --- 0. Despegarse de quien nos llamo ----------------------------------------
# `setsid -f` nos pone en una sesion nueva y devuelve el control al instante
# (0,003 s), asi que el bind de Hyprland no espera y, sobre todo, el bloqueo ya
# no muere si muere el invocador.
if [ "${LOCK_DESPEGADO:-0}" != "1" ]; then
    mkdir -p "$CACHE"
    [ -f "$LOG" ] && [ "$(stat -c%s "$LOG")" -gt 1048576 ] && mv -f "$LOG" "$LOG.1"
    LOCK_DESPEGADO=1 exec setsid -f "$0" "$@" >>"$LOG" 2>&1
fi

exec 2>&1
echo "=== $(date '+%F %T') lock.sh arranca (pid $$, modo $MODO_FONDO) ==="

# Si ya hay un hyprlock corriendo, no se apilan dos.
if pgrep -x hyprlock >/dev/null; then
    echo "lock: ya hay un hyprlock corriendo, no hago nada"
    exit 0
fi

# --- Utilidades ---------------------------------------------------------------
avisar() {
    # Escribir en un FIFO se BLOQUEA hasta que alguien lea; el timeout evita que
    # un demonio atascado deje la pantalla sin bloquear.
    local fifo="$1" orden="$2"
    [ -p "$fifo" ] || return 0
    timeout 2 bash -c "printf '%s\n' \"\$1\" > \"\$2\"" _ "$orden" "$fifo" 2>/dev/null || true
}

mpv_propiedad() {
    [ -S "$MPV" ] || return 1
    python3 - "$MPV" "$1" <<'PY'
import json, socket, sys
try:
    s = socket.socket(socket.AF_UNIX)
    s.settimeout(2)
    s.connect(sys.argv[1])
    f = s.makefile("rw")
    f.write(json.dumps({"command": ["get_property", sys.argv[2]]}) + "\n")
    f.flush()
    while True:
        r = json.loads(f.readline())
        if "request_id" not in r:      # los eventos no llevan request_id
            continue
        if r.get("error") != "success":
            sys.exit(1)
        print(r["data"])
        break
except (OSError, ValueError, KeyError):
    sys.exit(1)
PY
}

mpv_orden() {
    [ -S "$MPV" ] || return 1
    python3 - "$MPV" "$1" <<'PY'
import socket, sys
try:
    s = socket.socket(socket.AF_UNIX)
    s.settimeout(2)
    s.connect(sys.argv[1])
    s.sendall((sys.argv[2] + "\n").encode())
    s.recv(4096)
except OSError:
    sys.exit(1)
PY
}

# --- 1. El fotograma del fondo (modo `fotograma`) ----------------------------
# mpvpaper dibuja con la API de render de libmpv y ese VO no implementa
# capturas: `screenshot-to-file` responde "error running command" en todas sus
# variantes. Por eso se le pregunta el archivo y el segundo, y corta ffmpeg.
capturar_fondo() {
    local video pos ancho
    video=$(mpv_propiedad path) || return 1
    pos=$(mpv_propiedad time-pos) || return 1
    video=$(realpath -e "$video" 2>/dev/null) || return 1

    ancho=$(hyprctl monitors -j 2>/dev/null \
        | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["width"])' 2>/dev/null)
    [[ "$ancho" =~ ^[0-9]+$ ]] || ancho=1920

    ffmpeg -nostdin -loglevel error -ss "$pos" -i "$video" \
           -frames:v 1 -vf "scale=${ancho}:-2" -q:v 3 -y "$FONDO_TMP" \
        && mv -f "$FONDO_TMP" "$FONDO"
}

escribir_fragmento() {
    # Un `background` transparente para que se vea lo de debajo (xray), o con la
    # imagen capturada. Se escribe entero cada vez: no hay estado que arrastrar.
    mkdir -p "$CACHE"
    if [ "$1" = "xray" ]; then
        cat > "$FRAGMENTO" <<'EOF'
# GENERADO POR lock.sh — NO EDITAR A MANO.
# Modo xray: transparente a proposito, para que se vea el video del fondo
# moviendose por debajo (misc:session_lock_xray).
background {
    monitor =
    color = rgba(00000000)
    blur_passes = 0
}
EOF
    else
        cat > "$FRAGMENTO" <<EOF
# GENERADO POR lock.sh — NO EDITAR A MANO.
# Modo fotograma: la imagen que lock.sh saco del video con ffmpeg.
background {
    monitor =
    path = $FONDO
    color = rgba(120621ff)
    blur_passes = 0
}
EOF
    fi
}

# --- 2. Preparar el escritorio ------------------------------------------------
WS_ORIGINAL=""
XRAY_ORIGINAL=""
BARRAS_ESCONDIDAS=0
CONGELADO=0

despejar() {
    WS_ORIGINAL=$(hyprctl activeworkspace -j 2>/dev/null \
        | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' 2>/dev/null) || WS_ORIGINAL=""
    if [ -n "$WS_ORIGINAL" ]; then
        hyprctl dispatch workspace "$WORKSPACE_LIMPIO" >/dev/null 2>&1 \
            && echo "lock: escritorio $WS_ORIGINAL -> $WORKSPACE_LIMPIO"
    else
        echo "lock: aviso, no pude leer el escritorio actual; no salto" >&2
    fi

    # OJO: aqui va `lock`, NO `hide` ni `hold`.
    #   `hide` solo suelta el "sacada a mano"; con el escritorio VACIO —que es
    #          justo donde estamos— el demonio la deja visible a proposito.
    #   `hold` hace lo contrario de esconder: la RETIENE visible (es para el
    #          panel de calendario).
    # `lock` es la unica que la esconde y no la deja volver. Sin esto, el xray
    # ensenaria la barra entera —sensores, hora, volumen y tu IP— sobre la
    # pantalla de bloqueo.
    avisar "$FIFO_BARRAS" lock
    avisar "$FIFO_BARRAS" dock:lock
    BARRAS_ESCONDIDAS=1
}

recomponer() {
    if [ "$BARRAS_ESCONDIDAS" -eq 1 ]; then
        avisar "$FIFO_BARRAS" unlock
        avisar "$FIFO_BARRAS" dock:unlock
        BARRAS_ESCONDIDAS=0
    fi
    if [ -n "$WS_ORIGINAL" ]; then
        hyprctl dispatch workspace "$WS_ORIGINAL" >/dev/null 2>&1
    fi
}

# --- 3. El trap: deshacerlo todo pase lo que pase -----------------------------
# Esto es lo que garantiza que ni el video se quede corriendo, ni una app
# congelada, ni el xray encendido (que seria una fuga permanente), ni tu
# escritorio en el 99, aunque el script muera de mala manera.
limpiar() {
    local codigo=$?
    trap - EXIT INT TERM HUP

    if [ -n "$XRAY_ORIGINAL" ]; then
        hyprctl keyword misc:session_lock_xray "$XRAY_ORIGINAL" >/dev/null 2>&1
        echo "lock: xray devuelto a $XRAY_ORIGINAL"
    fi
    if [ "$CONGELADO" -eq 1 ]; then
        "$SCRIPTS/lib/congelar.py" descongelar 2>&1 | sed 's/^/lock: /'
        CONGELADO=0
    fi
    recomponer
    avisar "$FIFO" release
    echo "=== $(date '+%F %T') lock.sh termina (codigo $codigo) ==="
    exit "$codigo"
}
trap limpiar EXIT INT TERM HUP

# --- 4. Manos a la obra -------------------------------------------------------
mkdir -p "$CACHE"

# El fotograma se captura SIEMPRE, tambien en modo xray: si el xray fallara y
# hubiera que caer al modo de reserva, la imagen ya esta lista.
if capturar_fondo; then
    echo "lock: fondo capturado en $FONDO"
else
    rm -f "$FONDO_TMP"
    echo "lock: no se pudo capturar el fondo; se usara el que hubiera" >&2
fi

if [ "$MANTENER_VIDEO" -eq 1 ]; then
    avisar "$FIFO" hold
    mpv_orden '{"command":["set_property","pause",false]}' || true
fi

despejar

if [ "$CONGELAR" -eq 1 ]; then
    echo "lock: congelando aplicaciones..."
    "$SCRIPTS/lib/congelar.py" congelar 2>&1 | sed 's/^/lock: /'
    CONGELADO=1
fi

if [ "$MODO_FONDO" = "xray" ]; then
    # Se guarda el valor de antes para devolverlo tal cual en el trap: dejarlo
    # encendido seria una fuga, porque cualquier otro bloqueo lo aprovecharia.
    XRAY_ORIGINAL=$(hyprctl getoption misc:session_lock_xray -j 2>/dev/null \
        | python3 -c 'import json,sys; print(json.load(sys.stdin)["int"])' 2>/dev/null)
    [ -n "$XRAY_ORIGINAL" ] || XRAY_ORIGINAL=0
    hyprctl keyword misc:session_lock_xray true >/dev/null 2>&1
    echo "lock: xray encendido (estaba en $XRAY_ORIGINAL)"
    escribir_fragmento xray
else
    escribir_fragmento fotograma
fi

# --- 5. Bloquear, y no rendirse si hyprlock cae ------------------------------
# --immediate-render dibuja el fondo sin esperar a tener todo cargado: evita el
# parpadeo negro del primer instante.
#
# Salir con 0 es un desbloqueo de verdad (escribiste bien la contrasena).
for intento in $(seq 1 "$REINTENTOS"); do
    hyprlock --immediate-render
    codigo=$?
    if [ "$codigo" -eq 0 ]; then
        echo "lock: desbloqueo normal"
        break
    fi
    echo "lock: hyprlock murio (codigo $codigo), intento $intento de $REINTENTOS" >&2
    sleep 1
done

if [ "${codigo:-1}" -ne 0 ]; then
    # Se agotaron los intentos. NO se desbloquea la sesion sola a proposito: si
    # te habias ido de la PC, abrirla aqui seria justo el agujero que el bloqueo
    # existe para tapar. Pero SI se descongela y se recompone el escritorio (lo
    # hace el trap), para que lo que encuentres al entrar por tty sea usable.
    echo "lock: agotados los $REINTENTOS intentos; la sesion sigue bloqueada" >&2
fi

exit "${codigo:-1}"
