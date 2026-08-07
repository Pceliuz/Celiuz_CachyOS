#!/usr/bin/env bash
# tests/unidad/barras-huerfanas.sh — el demonio de las barras se aparta cuando su
# Hyprland ya no esta, y barre a los competidores al arrancar.
#
# POR QUE EXISTE ESTA PRUEBA
# --------------------------
# Es la misma enfermedad que ya tenia el demonio del fondo (ver
# `fondo-huerfano.sh`), y a este no se le habia puesto la vacuna.
# waybar-autohide.py se lanza desde `exec-once` y sobrevive al compositor que lo
# arranco; SOCKET se fija al empezar, asi que un Hyprland nuevo tampoco lo
# recupera. Y aqui hay un agravante que el fondo no tiene: **`WAYLAND_DISPLAY` se
# reutiliza entre sesiones** (`wayland-1` las dos veces), asi que las cuatro
# waybar del huerfano se DIBUJAN en la sesion nueva.
#
# Paso de verdad el 2026-08-07: un demonio de la sesion del 05, adoptado por
# `systemd --user`, seguia vivo dos dias despues. Se veia como tres fallos
# distintos, y ninguno se parece a la causa:
#
#   - las barras no se ocultaban aunque hubiera apps abiertas (el socket muerto
#     no contesta y el valor de reserva de read_state() es 0 ventanas, o sea
#     "escritorio vacio", que es cuando las barras se quedan puestas);
#   - se veian por encima de la pantalla de bloqueo (el `lock` de lock.sh entra
#     por el FIFO, que era del demonio bueno; el huerfano lo habia perdido y
#     estaba sordo);
#   - al desbloquear parecian dos barras peleandose, porque lo eran: ocho capas.
#
# Las dos mitades importan, igual que en el fondo: que se vaya cuando debe, y que
# NO se vaya mientras su Hyprland siga ahi.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

# Lo peligroso, sustituido: este demonio lanza y mata waybar.
binario_falso waybar
binario_falso notify-send

# Desde una COPIA del repo: el demonio saca su raiz de la ruta de su propio .py.
COPIA="$(copiar_repo)"
DEMONIO="$COPIA/hypr/scripts/waybar-autohide.py"

# Un Hyprland de mentira: acepta y contesta lo justo para que el demonio lo dé
# por vivo. Tiene que ATENDER de verdad, en bucle, y no solo quedarse escuchando:
# un socket que acepta y calla llena su cola de `accept` —el demonio pregunta a
# 10 Hz— y a partir de ahi los `connect` empiezan a fallar, o sea que el doble
# acabaria fingiendo justo lo que la prueba quiere descartar. Costo una vuelta.
FALSO_HYPR_PY='
import socket, sys
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.bind(sys.argv[1])
s.listen(64)
while True:
    try:
        c, _ = s.accept()
    except OSError:
        break
    try:
        c.settimeout(1.0)
        c.recv(4096)
        # Lo que espera read_state(): ventanas del workspace y posicion del
        # cursor. 0 ventanas y el cursor en el centro es un escritorio vacio, que
        # es el estado mas neutro para lo que se mide aqui.
        c.sendall(b"windows: 0\n960, 540\n")
    except OSError:
        pass
    finally:
        c.close()
'

levantar_falso_hypr() {
    mkdir -p "$1/hypr/$2"
    python3 -c "$FALSO_HYPR_PY" "$1/hypr/$2/.socket.sock" &
    LANZADOS="$LANZADOS $!"
    sleep 0.5
}

# Todo lo que se lanza al fondo se apunta aqui y se barre al salir. `fallo()` no
# corta la prueba, asi que en el camino normal bastaria con matarlos al final;
# esto es para el Ctrl+C y para el caso de que una afirmacion nueva se cuele
# antes de la limpieza. `preparar_entorno` ya dejo su propio trap: se encadena,
# no se pisa, o el HOME de mentira se quedaria sin borrar.
LANZADOS=""
trap 'for p in $LANZADOS; do kill "$p" 2>/dev/null; done; limpiar_entorno' \
    EXIT INT TERM

titulo "1. Su Hyprland ya no esta: se aparta"
# El directorio de la instancia existe pero no hay nadie escuchando, que es
# exactamente como queda una instancia muerta: Hyprland no siempre limpia su
# carpeta al irse, asi que "existe la carpeta" NO sirve para saber si vive.
SIG="instancia-de-mentira"
mkdir -p "$XDG_RUNTIME_DIR/hypr/$SIG"

inicio=$(date +%s)
WAYBAR_AUTOHIDE_ABANDONO=2 HYPRLAND_INSTANCE_SIGNATURE="$SIG" \
    timeout 25 "$DEMONIO" >"$TMP/huerfano.log" 2>&1
codigo=$?
tardo=$(( $(date +%s) - inicio ))

if [ "$codigo" -eq 124 ]; then
    fallo "se va solo cuando no hay compositor" \
          "seguia dando vueltas a los 25 s (asi es como acaba ocupando el sitio)"
else
    ok "se va solo cuando no hay compositor (a los ${tardo} s)"
fi
afirmar_igual "0" "$codigo" "se va por su propio pie, no a golpes"
afirmar_contiene "$TMP/huerfano.log" "dejo el sitio" \
    "y deja dicho por que se fue"

titulo "2. Su Hyprland sigue vivo: se queda"
SIG2="instancia-viva"
levantar_falso_hypr "$XDG_RUNTIME_DIR" "$SIG2"

WAYBAR_AUTOHIDE_ABANDONO=2 HYPRLAND_INSTANCE_SIGNATURE="$SIG2" \
    "$DEMONIO" >"$TMP/vivo.log" 2>&1 &
VIVO=$!
LANZADOS="$LANZADOS $VIVO"
sleep 8   # cuatro veces el ABANDONO de la prueba

if kill -0 "$VIVO" 2>/dev/null; then
    ok "sigue en pie mientras haya compositor (8 s, con ABANDONO=2)"
else
    fallo "no se rinde con su Hyprland delante" \
          "se murio a los 8 s: $(cat "$TMP/vivo.log")"
fi

titulo "3. Al arrancar barre al que ya estuviera en el mismo escritorio"
# Esta es la otra mitad del arreglo, y la que cierra el caso del 2026-08-07: el
# barrido corria SOLO con `--reiniciar`, asi que al abrir sesion el demonio nuevo
# convivia tan tranquilo con el huerfano de la sesion anterior.
SEGUNDO_LOG="$TMP/segundo.log"
WAYBAR_AUTOHIDE_ABANDONO=2 HYPRLAND_INSTANCE_SIGNATURE="$SIG2" \
    "$DEMONIO" >"$SEGUNDO_LOG" 2>&1 &
SEGUNDO=$!
LANZADOS="$LANZADOS $SEGUNDO"
sleep 6

if kill -0 "$VIVO" 2>/dev/null; then
    fallo "el que arranca se queda solo" \
          "los dos siguen vivos: es exactamente el estado de las dos barras peleandose"
else
    ok "el que arranca echa al anterior (sin pasarle --reiniciar)"
fi
if kill -0 "$SEGUNDO" 2>/dev/null; then
    ok "y el que se queda es el nuevo"
else
    fallo "el nuevo sobrevive al barrido" \
          "se fue el que tenia que quedarse: $(cat "$SEGUNDO_LOG")"
fi

titulo "4. Pero NO barre a uno de otro escritorio"
# El discriminante es XDG_RUNTIME_DIR, no el nombre del proceso. Sin esto, el
# barrido seria el `pkill` por nombre que ya mordio con wallpaper.sh: un `$HOME`
# desechable no aisla de eso, asi que esta misma prueba mataria el demonio de la
# sesion real de quien la ejecuta.
OTRO_RUNTIME="$TMP/otro-runtime"
levantar_falso_hypr "$OTRO_RUNTIME" "$SIG2"

XDG_RUNTIME_DIR="$OTRO_RUNTIME" WAYBAR_AUTOHIDE_ABANDONO=2 \
    HYPRLAND_INSTANCE_SIGNATURE="$SIG2" "$DEMONIO" >"$TMP/ajeno.log" 2>&1 &
AJENO=$!
LANZADOS="$LANZADOS $AJENO"
sleep 2

# Y ahora arranca otro en el runtime de la prueba: no debe tocar al de arriba.
WAYBAR_AUTOHIDE_ABANDONO=2 HYPRLAND_INSTANCE_SIGNATURE="$SIG2" \
    "$DEMONIO" >"$TMP/tercero.log" 2>&1 &
TERCERO=$!
LANZADOS="$LANZADOS $TERCERO"
sleep 5

if kill -0 "$AJENO" 2>/dev/null; then
    ok "un demonio con otro XDG_RUNTIME_DIR se queda donde esta"
else
    fallo "no se mata por nombre a traves de runtimes" \
          "se llevo por delante un demonio de otro escritorio"
fi

titulo "5. Ni a otra sesion del mismo escritorio que siga VIVA"
# El runtime a secas no bastaba como discriminante, y este es el caso que lo
# demuestra: dos sesiones Hyprland vivas del MISMO usuario comparten
# XDG_RUNTIME_DIR (dos TTY, o un cambio rapido de usuario). Con el filtro solo
# por runtime, el segundo en entrar dejaba al primero sin barras teniendo su
# compositor delante — peor que el fallo que se estaba arreglando, y ABANDONO no
# lo salva, porque a ese demonio no le pasa nada: lo matan.
#
# Se mata solo al duplicado de la propia instancia (caso 3) y al huerfano. Una
# tercera sesion viva se deja en paz.
SIG3="otra-sesion-viva"
levantar_falso_hypr "$XDG_RUNTIME_DIR" "$SIG3"

WAYBAR_AUTOHIDE_ABANDONO=2 HYPRLAND_INSTANCE_SIGNATURE="$SIG3" \
    "$DEMONIO" >"$TMP/vecino.log" 2>&1 &
VECINO=$!
LANZADOS="$LANZADOS $VECINO"
sleep 2

# Y ahora entra uno de la instancia SIG2, que sigue viva y es otra distinta.
WAYBAR_AUTOHIDE_ABANDONO=2 HYPRLAND_INSTANCE_SIGNATURE="$SIG2" \
    "$DEMONIO" >"$TMP/cuarto.log" 2>&1 &
CUARTO=$!
LANZADOS="$LANZADOS $CUARTO"
sleep 5

if kill -0 "$VECINO" 2>/dev/null; then
    ok "una sesion viva conserva sus barras cuando entra otra"
else
    fallo "no se mata a una sesion viva del mismo runtime" \
          "se quedo sin demonio teniendo su Hyprland delante: $(cat "$TMP/vecino.log")"
fi

for p in $LANZADOS; do kill "$p" 2>/dev/null; done
wait $LANZADOS 2>/dev/null

titulo "6. No toco nada de tu equipo"
afirmar_intacta_la_casa_real

resumen
