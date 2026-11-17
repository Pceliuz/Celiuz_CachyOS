#!/usr/bin/env bash
# ~/dotfiles/hypr/scripts/grabar.sh
#
# Grabar la pantalla en video, con su sonido.
#
#   grabar.sh                  abre la tarjeta para elegir que grabar (SUPER+R)
#   grabar.sh --full           el monitor que tengas delante (SUPER+ALT+R)
#   grabar.sh --zona           la zona que marques con el raton
#   grabar.sh --ventana DIR    una ventana (DIR = su direccion en hyprctl clients),
#                              aunque te vayas a otra: se graba ELLA, no la pantalla
#   ... --sin-audio            sin sonido (por defecto se graba)
#   grabar.sh --pausar         pausa o reanuda la grabacion en curso (SUPER+CTRL+R)
#   grabar.sh --parar          la para y la guarda
#   grabar.sh --estado         JSON para el modulo de waybar
#   grabar.sh --estado-tirador JSON para la linea-tirador (roja mientras graba)
#
# El SONIDO depende de lo que se grabe: con la pantalla o una zona, todo lo que
# suena en el equipo; con una ventana, SOLO lo de esa app (el porque y su
# limite, en lib/grabacion.py).
#
# Es un INTERRUPTOR: mientras haya una grabacion viva, SUPER+R (o cualquier
# forma de arriba que empiece una) la para en vez de empezar otra. Un atajo
# para empezar y otro para parar se olvida justo cuando hace falta.
#
# Donde se VE que se esta grabando: en la barra (el punto rojo y la
# linea-tirador roja). En los modos gaming, programador y estudio la barra no
# esta o no se ve, y ahi lo enseña grabar-indicador.py, una pastilla flotante
# que se lanza con cada grabacion y solo aparece dentro de un modo.
#
# El video queda en ~/Videos/grabaciones/. Al portapapeles va su RUTA en texto,
# no el fichero: un mp4 de varios minutos pegado no lo acepta casi nadie.
#
# Se apoya en gpu-screen-recorder (repo oficial `extra`, nada de AUR). Antes era
# wf-recorder, y se cambio el 2026-11-16 por tres cosas que wf-recorder no hace:
# grabar una ventana suelta, grabar el sonido de una sola app, y codificar en la
# GPU con NVIDIA (wf-recorder solo sabe VAAPI, que la NVIDIA no tiene, y caia a
# la CPU a 2560x1440). Y pausa de verdad, con una senal, sin cortar en tramos.

set -uo pipefail

DIR="$(dirname "$(readlink -f "$BASH_SOURCE")")"

# El `source` se comprueba a proposito: en bash uno que falla NO corta el script,
# y seguir sin estas funciones dejaria el interruptor contando grabadores por
# nombre — el `pgrep -x` global que este repo ya se quito de encima una vez.
if ! . "$DIR/lib/canales.sh" 2>/dev/null || ! declare -F pids_de_esta_sesion >/dev/null; then
    echo "grabar: no encuentro lib/canales.sh; me paro antes de tocar nada" >&2
    exit 1
fi

DESTINO="$(xdg-user-dir VIDEOS 2>/dev/null || echo "$HOME/Vídeos")/grabaciones"

# Donde se apunta que hay una grabacion viva. Lleva la firma de la sesion, como
# todo lo demas, para que dos sesiones de Hyprland no se paren la grabacion la
# una a la otra (ver lib/canales.sh).
ESTADO="$(canal grabar estado)"
REGISTRO="${XDG_RUNTIME_DIR:-/tmp}/grabar.log"

# El nombre del proceso tal como sale en /proc/PID/comm: el kernel lo corta a
# 15 caracteres, asi que «gpu-screen-recorder» ahi se llama asi.
COMM="gpu-screen-reco"

# La senal con que waybar repinta los dos indicadores al momento (el modulo de
# la barra y la linea-tirador; "signal": 11 en sus configs). Sin ella, la
# linea tardaria en enterarse de que se empezo a grabar.
SENAL_BARRA=11

avisar() {
    # Mismo patron que screenshot.sh: notificacion si hay demonio, y ademas al
    # log de Hyprland, que es donde se puede leer cuando no lo hay.
    #
    # Categoria `de-paso` (mako/config): se ven TAMBIEN en «no molestar», que
    # es justo como estan los avisos jugando o en el modo programador, y no
    # suenan. Sin ella, empezar o pausar una grabacion jugando no daba ni una
    # señal.
    notify-send -a CeliuzRec -c de-paso -i "${2:-camera-video}" "$1" "${3:-}" 2>/dev/null &
    echo "grabar: $1 ${3:-}" >&2
}

repintar_barra() {
    local p
    for p in $(pids_de_esta_sesion waybar); do
        kill -s "RTMIN+$SENAL_BARRA" "$p" 2>/dev/null
    done
    return 0
}

guardar_estado() {
    # Ocho campos por tab: pid, ruta, inicio, pausado, pausa_acum (segundos
    # ya pausados), pausa_inicio (cuando empezo la pausa actual), modo y donde
    # (el monitor, la zona WxH+X+Y o la direccion de la ventana: lo que mira
    # grabar-indicador.py para no ponerse encima de lo que se graba).
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$PID_VIVO" "$RUTA_VIVA" "$INICIO" "$PAUSADO" "$PAUSA_ACUM" "$PAUSA_INICIO" "$MODO_VIVO" "$DONDE_VIVO" > "$ESTADO"
}

# --- Lo primero: saber si ya se esta grabando --------------------------------

PID_VIVO=""; RUTA_VIVA=""; INICIO=""; PAUSADO=0; PAUSA_ACUM=0; PAUSA_INICIO=0; MODO_VIVO=""; DONDE_VIVO=""
if [ -r "$ESTADO" ]; then
    IFS=$'\t' read -r PID_VIVO RUTA_VIVA INICIO PAUSADO PAUSA_ACUM PAUSA_INICIO MODO_VIVO DONDE_VIVO < "$ESTADO"
    PAUSADO="${PAUSADO:-0}"; PAUSA_ACUM="${PAUSA_ACUM:-0}"; PAUSA_INICIO="${PAUSA_INICIO:-0}"
fi
# Que el numero siga siendo NUESTRO grabador y no un proceso cualquiera que haya
# heredado el PID despues: los PIDs se reciclan, y un `kill` a ciegas sobre un
# numero viejo mata a quien no toca (asi llego a cerrarse una sesion entera).
# En pausa el grabador sigue vivo, asi que vale igual.
if [ -n "$PID_VIVO" ] && [ "$(cat "/proc/$PID_VIVO/comm" 2>/dev/null)" != "$COMM" ]; then
    PID_VIVO=""; RUTA_VIVA=""; INICIO=""; PAUSADO=0
    rm -f "$ESTADO"
fi
# Y si no hay fichero de estado utilizable todavia puede quedar un grabador
# huerfano de ESTA sesion (el script matado a medias, el fichero borrado a mano).
# Se busca por la firma de la instancia, que si distingue de que sesion es cada
# proceso; sin fichero no se sabe donde estaba grabando, pero se puede parar.
if [ -z "$PID_VIVO" ]; then
    PID_VIVO="$(pids_de_esta_sesion "$COMM" | head -1)"
fi

# --- --estado: lo que waybar necesita saber, y nada mas ----------------------
#
# Waybar no adivina nada: pregunta aqui y aqui se contesta con el fichero de
# estado que este mismo script escribe. Un solo dueño del estado.

segundos_grabados() {
    [ -n "$INICIO" ] || { printf '0'; return; }
    # En pausa el reloj se para en el instante en que se pauso.
    local fin
    if [ "$PAUSADO" = "1" ]; then fin="$PAUSA_INICIO"; else fin="$(date +%s)"; fi
    local seg=$(( fin - INICIO - PAUSA_ACUM ))
    [ "$seg" -lt 0 ] && seg=0
    printf '%s' "$seg"
}

# El JSON se arma a mano en vez de con python3: waybar lo pregunta cada segundo
# y arrancar un interprete por segundo para esto sobra. La ruta la pone
# nombre_libre(), que nunca mete comillas; el resto son numeros y booleanos.
estado_json() {
    local gjson=false pjson=false text="" clase="" seg
    seg="$(segundos_grabados)"
    if [ -n "$PID_VIVO" ]; then
        gjson=true; clase="grabando"
        local reloj
        reloj=$(printf '%02d:%02d' $((seg / 60)) $((seg % 60)))
        if [ "$PAUSADO" = "1" ]; then
            pjson=true; clase="pausado"; text="⏸ $reloj"
        else
            text="🔴 $reloj"
        fi
    fi
    printf '{"grabando": %s, "pausado": %s, "pid": "%s", "ruta": "%s", "transcurrido": %s, "text": "%s", "class": "%s", "modo": "%s", "donde": "%s"}\n' \
        "$gjson" "$pjson" "$PID_VIVO" "$RUTA_VIVA" "$seg" "$text" "$clase" "$MODO_VIVO" "$DONDE_VIVO"
}

case "${1:-}" in
    --estado)
        estado_json
        exit 0 ;;
    --estado-tirador)
        # La linea-tirador no lleva texto (es una raya dibujada con CSS): solo
        # cambia de clase, y con ella de color.
        clase=""
        if [ -n "$PID_VIVO" ]; then
            if [ "$PAUSADO" = "1" ]; then clase="pausado"; else clase="grabando"; fi
        fi
        printf '{"text": " ", "class": "%s"}\n' "$clase"
        exit 0 ;;
esac

parar() {
    # SIGINT, nunca SIGKILL: el grabador cierra el contenedor al recibirlo, y un
    # mp4 sin cerrar no tiene indice — no lo abre ningun reproductor. Matarlo a
    # lo bruto no pierde el ultimo segundo, pierde la grabacion entera.
    kill -INT "$PID_VIVO" 2>/dev/null

    # Y se le espera de verdad, hasta 10 s, lo que tarde en vaciar su cola. Dar
    # por hecho que ya esta seria avisar de "guardado" con el fichero a medias.
    local n=0
    while [ -e "/proc/$PID_VIVO" ] && [ "$n" -lt 100 ]; do
        sleep 0.1
        n=$((n + 1))
    done
    rm -f "$ESTADO"
    repintar_barra

    if [ -e "/proc/$PID_VIVO" ]; then
        avisar "La grabación no se cierra" dialog-error "sigue viva en el PID $PID_VIVO"
        exit 1
    fi
    if [ -z "$RUTA_VIVA" ] || [ ! -s "$RUTA_VIVA" ]; then
        avisar "La grabación salió vacía" dialog-error "mira $REGISTRO"
        exit 1
    fi

    # Cuanto duro y cuanto ocupa, que es lo que uno quiere saber al parar. La
    # duracion SIN las pausas: es lo que dura el video.
    local detalle="$(basename "$RUTA_VIVA")"
    local tam="$(du -h "$RUTA_VIVA" 2>/dev/null | cut -f1)"
    if [ -n "$INICIO" ]; then
        local seg
        seg="$(segundos_grabados)"
        detalle="$detalle · $((seg / 60))m $((seg % 60))s"
    fi
    [ -n "$tam" ] && detalle="$detalle · $tam"

    printf '%s' "$RUTA_VIVA" | wl-copy 2>/dev/null
    avisar "Grabación guardada" camera-video "$detalle"
    exit 0
}

pausar() {
    # gpu-screen-recorder pausa y reanuda con SIGUSR2, sin cerrar el fichero:
    # sale UN video, sin tramos que unir despues. Aqui solo se lleva la cuenta
    # del tiempo, para que el reloj de la barra se pare mientras tanto.
    kill -USR2 "$PID_VIVO" 2>/dev/null || { avisar "No pude pausar la grabación" dialog-error; exit 1; }
    local ahora
    ahora="$(date +%s)"
    if [ "$PAUSADO" = "1" ]; then
        PAUSA_ACUM=$(( PAUSA_ACUM + ahora - PAUSA_INICIO ))
        PAUSADO=0; PAUSA_INICIO=0
        guardar_estado
        repintar_barra
        avisar "Grabación reanudada" media-record
    else
        PAUSADO=1; PAUSA_INICIO="$ahora"
        guardar_estado
        repintar_barra
        avisar "Grabación en pausa" media-playback-pause "SUPER+CTRL+R para seguir · SUPER+R para terminar"
    fi
    exit 0
}

# --- Con una grabacion viva: pausar o parar, nunca empezar otra --------------

if [ -n "$PID_VIVO" ]; then
    if [ "${1:-}" = "--pausar" ]; then
        if [ -z "$INICIO" ]; then
            # Un huerfano sin fichero de estado: se puede parar, pero no se sabe
            # ni cuando empezo; pausar a ciegas dejaria el reloj inventado.
            avisar "No sé pausar esa grabación" dialog-error "SUPER+R la para"
            exit 1
        fi
        pausar
    fi
    parar
fi

case "${1:-}" in
    --pausar)
        avisar "No hay ninguna grabación para pausar"
        exit 0 ;;
    --parar|-p)
        avisar "No hay ninguna grabación en curso"
        exit 0 ;;
esac

# --- A partir de aqui, no habia nada grabando --------------------------------

# El bind no falla si falta el programa: pulsas la tecla y NO PASA NADA, sin una
# sola pista de por que. Es el fallo en silencio que este repo evita en todo lo
# demas, asi que se dice.
if ! command -v gpu-screen-recorder >/dev/null 2>&1; then
    avisar "Falta gpu-screen-recorder" dialog-error "sudo pacman -S gpu-screen-recorder"
    exit 1
fi

# Sin argumentos: la tarjeta pregunta que grabar y contesta con los argumentos
# de siempre, en una linea. Cancelarla (Esc) no es un error.
if [ "$#" -eq 0 ]; then
    ELECCION="$(python3 "$DIR/grabar-elegir.py")" || exit 0
    [ -n "$ELECCION" ] || exit 0
    # Lo que contesta son opciones y una direccion hexadecimal: sin espacios
    # dentro de ninguna, asi que partirlas por espacios es exacto.
    # shellcheck disable=SC2086
    set -- $ELECCION
fi

MODO=""
DONDE=""
VENTANA=""
AUDIO=1
while [ "$#" -gt 0 ]; do
    case "$1" in
        --full|-f)  MODO=pantalla ;;
        --zona|-z)  MODO=zona ;;
        --ventana|-w)
            MODO=ventana
            VENTANA="${2:-}"
            shift ;;
        --audio|-a)     AUDIO=1 ;;
        --sin-audio)    AUDIO=0 ;;
        *)
            echo "uso: $(basename "$0") [--full | --zona | --ventana DIR] [--sin-audio] | --pausar | --parar | --estado" >&2
            exit 2 ;;
    esac
    shift
done
[ -n "$MODO" ] || MODO=zona

mkdir -p "$DESTINO" || { avisar "No puedo crear $DESTINO" dialog-error; exit 1; }

# Mismo criterio de nombre que screenshot.sh: el modo, la fecha, y un numero
# detras si ya existe.
nombre_libre() {
    local base="$DESTINO/${1}_$(date +%Y-%m-%d_%H-%M-%S)"
    local ruta="$base.mp4"
    local n=2
    while [ -e "$ruta" ]; do
        ruta="$base-$n.mp4"
        n=$((n + 1))
    done
    printf '%s' "$ruta"
}

# Los mismos colores de seleccion que las capturas (conf/colores del escritorio).
SLURP_COLORES=(-b 09031299 -c b16cffff -s b16cff26 -w 2)

SONIDO="default_output"   # todo lo que suena en el equipo
case "$MODO" in
    pantalla)
        # El monitor que tengas DELANTE, no "el primero": con dos pantallas el
        # primero que liste el compositor no tiene por que ser en el que estas.
        SALIDA=$(hyprctl activeworkspace -j | python3 -c '
import json, sys
try:
    print(json.load(sys.stdin)["monitor"])
except Exception:
    pass')
        if [ -z "$SALIDA" ]; then
            avisar "No sé en qué monitor estás" dialog-error
            exit 1
        fi
        CAPTURA=(-w "$SALIDA")
        DONDE="$SALIDA"
        ;;
    zona)
        # slurp devuelve vacio y codigo 1 si cancelas con Escape o clic derecho:
        # eso no es un error, es que has cambiado de idea. El formato es el que
        # entiende -region (el manual de gpu-screen-recorder lo da tal cual).
        ZONA=$(slurp "${SLURP_COLORES[@]}" -f "%wx%h+%x+%y") || exit 0
        [ -n "$ZONA" ] || exit 0
        CAPTURA=(-w region -region "$ZONA")
        DONDE="$ZONA"
        ;;
    ventana)
        if [ -z "$VENTANA" ]; then
            avisar "¿Qué ventana grabo?" dialog-error "falta su dirección: grabar.sh --ventana 0x..."
            exit 1
        fi
        # El sonido de ESA app y de nadie mas. Sin nombre que buscar (una ventana
        # que ya no existe) no se graba nada: mejor que grabar otra cosa.
        SONIDO="$(python3 "$DIR/lib/grabacion.py" audio "$VENTANA")" || {
            avisar "Esa ventana ya no está" dialog-error
            exit 1
        }
        # La imagen llega por el portal, que preguntara "¿que ventana?":
        # grabar-portal.py contesta con el recado que se deja aqui. El portal
        # lo encuentra por el PATH (hypr/xdph.conf); sin el enlace no arranca,
        # y el error que da es mudo, asi que se dice aqui antes de intentarlo.
        if ! command -v celiuz-grabar-portal >/dev/null 2>&1; then
            avisar "Falta el selector del portal" dialog-error "corre ./instalar.sh en el repo del escritorio"
            exit 1
        fi
        python3 "$DIR/lib/grabacion.py" preseleccionar "$VENTANA" || {
            avisar "No pude preparar la grabación de la ventana" dialog-error
            exit 1
        }
        CAPTURA=(-w portal)
        DONDE="$VENTANA"
        ;;
esac

ARCHIVO=$(nombre_libre "$MODO")

# -k h264 y sonido AAC: lo que abre cualquier reproductor, movil o web. La GPU
# codifica (NVENC en NVIDIA, VAAPI en AMD/Intel); donde no se pueda, la CPU, en
# vez de no grabar.
OPCIONES=("${CAPTURA[@]}" -c mp4 -k h264 -f 60 -fallback-cpu-encoding yes)
if [ "$AUDIO" -eq 1 ] && [ -n "$SONIDO" ]; then
    OPCIONES+=(-a "$SONIDO" -ac aac)
fi

gpu-screen-recorder "${OPCIONES[@]}" -o "$ARCHIVO" >"$REGISTRO" 2>&1 < /dev/null &
PID=$!

# Si se muere en el arranque (sin permiso para capturar, el portal sin
# respuesta, una zona imposible...), se dice con las ultimas lineas del registro.
# Por el portal se espera mas: primero pregunta y luego empieza.
ESPERA=12; [ "$MODO" = ventana ] && ESPERA=30
n=0
while [ "$n" -lt "$ESPERA" ] && kill -0 "$PID" 2>/dev/null; do
    sleep 0.1
    n=$((n + 1))
done
if ! kill -0 "$PID" 2>/dev/null; then
    rm -f "$ARCHIVO"
    avisar "No arranca la grabación" dialog-error "$(tail -3 "$REGISTRO" 2>/dev/null)"
    exit 1
fi

PID_VIVO="$PID"; RUTA_VIVA="$ARCHIVO"; INICIO="$(date +%s)"
PAUSADO=0; PAUSA_ACUM=0; PAUSA_INICIO=0; MODO_VIVO="$MODO"; DONDE_VIVO="$DONDE"
guardar_estado
repintar_barra

# La pastilla de los modos sin barra. Se lanza SIEMPRE y decide ella si se
# enseña: asi tambien aparece si se entra al modo gaming con la grabacion ya en
# marcha. Se va sola cuando la grabacion termina. Desligada (setsid) para que no
# muera con este script, y sin que su fallo pueda tocar la grabacion.
setsid python3 "$DIR/grabar-indicador.py" >/dev/null 2>&1 < /dev/null &

case "$MODO" in
    pantalla) QUE="pantalla completa"; DETALLE="con el sonido del equipo" ;;
    zona)     QUE="una zona";          DETALLE="con el sonido del equipo" ;;
    ventana)  QUE="una ventana";       DETALLE="solo con el sonido de esa app" ;;
esac
[ "$AUDIO" -eq 1 ] || DETALLE="sin sonido"
avisar "Grabando $QUE" media-record "$DETALLE · SUPER+R para terminar · SUPER+CTRL+R para pausar"
