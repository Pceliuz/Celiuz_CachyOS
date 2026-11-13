#!/usr/bin/env bash
# ~/dotfiles/hypr/scripts/grabar.sh
#
# Grabar la pantalla en video.
#
#   grabar.sh            graba la zona que elijas con el raton (lo normal)
#   grabar.sh --full     graba entero el monitor que tengas delante
#   grabar.sh --audio    ademas del video, el sonido que este saliendo
#   grabar.sh --parar    para la grabacion que haya en curso
#
# Es un INTERRUPTOR: mientras haya una grabacion viva, cualquiera de las formas
# de arriba la para en vez de empezar otra. Un atajo para empezar y otro distinto
# para parar se olvida justo cuando hace falta —con la grabacion corriendo y la
# pantalla llena de lo que estabas grabando—, asi que el mismo atajo hace las dos
# cosas.
#
# El video queda en ~/Videos/grabaciones/. A diferencia de screenshot.sh, al
# portapapeles NO va el fichero sino su RUTA en texto: un mp4 de varios minutos
# pegado no lo acepta casi ningun sitio, y la ruta se pega en cualquiera.
#
# Se apoya en wf-recorder (repo oficial, nada de AUR) y en slurp, que ya estaba
# aqui para las capturas.

set -uo pipefail

DIR="$(dirname "$(readlink -f "$BASH_SOURCE")")"

# El `source` se comprueba a proposito: en bash uno que falla NO corta el script,
# y seguir sin estas funciones dejaria el interruptor contando wf-recorders por
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

avisar() {
    # Mismo patron que screenshot.sh: notificacion si hay demonio, y ademas al
    # log de Hyprland, que es donde se puede leer cuando no lo hay.
    notify-send -a CeliuzRec -i "${2:-camera-video}" "$1" "${3:-}" 2>/dev/null &
    echo "grabar: $1 ${3:-}" >&2
}

# --- Lo primero: saber si ya se esta grabando --------------------------------

PID_VIVO=""; RUTA_VIVA=""; INICIO=""; PAUSADO=0; PAUSA_ACUM=0; PAUSA_INICIO=0; TRAMOS=""; ZONA_VIVA=""
if [ -r "$ESTADO" ]; then
    IFS=$'\t' read -r PID_VIVO RUTA_VIVA INICIO PAUSADO PAUSA_ACUM PAUSA_INICIO TRAMOS ZONA_VIVA < "$ESTADO"
    PAUSADO="${PAUSADO:-0}"; PAUSA_ACUM="${PAUSA_ACUM:-0}"; PAUSA_INICIO="${PAUSA_INICIO:-0}"
fi
# Que el numero siga siendo NUESTRO wf-recorder y no un proceso cualquiera que
# haya heredado el PID despues: los PIDs se reciclan, y un `kill` a ciegas sobre
# un numero viejo mata a quien no toca.
# En pausa el wf-recorder murio a proposito (el SIGINT cierra el tramo): un
# PID muerto aqui NO invalida el estado, o pausar borraria la propia grabacion.
if [ -n "$PID_VIVO" ] && [ "$PAUSADO" != "1" ] && [ "$(cat "/proc/$PID_VIVO/comm" 2>/dev/null)" != "wf-recorder" ]; then
    PID_VIVO=""; RUTA_VIVA=""; INICIO=""
    rm -f "$ESTADO"
fi
# Y si no hay fichero de estado utilizable todavia puede quedar un wf-recorder
# huerfano de ESTA sesion (el script matado a medias, el fichero borrado a mano).
# Se busca por la firma de la instancia, que si distingue de que sesion es cada
# proceso; sin fichero no se sabe donde estaba grabando, pero se puede parar.
if [ -z "$PID_VIVO" ]; then
    PID_VIVO="$(pids_de_esta_sesion wf-recorder | head -1)"
fi

# --- --estado: lo que waybar necesita saber, y nada mas ----------------------
#
# Waybar no adivina nada: pregunta aqui y aqui se contesta con el fichero de
# estado que este mismo script escribe. Un solo dueño del estado.

segundos_grabados() {
    [ -n "$INICIO" ] || { printf '0'; return; }
    # En pausa el reloj se para en el instante en que se pauso: el tiempo
    # transcurrido no avanza mientras el tramo cerrado no forme parte del video.
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
    local grabando=False pausado=False text="" seg
    [ -n "$PID_VIVO" ] && grabando=True
    [ "$grabando" = "True" ] && [ "$PAUSADO" = "1" ] && pausado=True
    seg="$(segundos_grabados)"
    if [ "$grabando" = "True" ]; then
        local reloj
        reloj=$(printf '%02d:%02d' $((seg / 60)) $((seg % 60)))
        if [ "$pausado" = "True" ]; then text="⏸ $reloj"; else text="🔴 $reloj"; fi
    fi
    # JSON de verdad: true/false en minuscula. Python los lee como bool y bash
    # los compara como texto; con True/False de bash, waybar no podria leerlo.
    local gjson=false pjson=false
    [ "$grabando" = "True" ] && gjson=true
    [ "$pausado" = "True" ] && pjson=true
    printf '{"grabando": %s, "pausado": %s, "pid": "%s", "ruta": "%s", "transcurrido": %s, "text": "%s"}\n' \
        "$gjson" "$pjson" "$PID_VIVO" "$RUTA_VIVA" "$seg" "$text"
}

if [ "${1:-}" = "--estado" ]; then
    estado_json
    exit 0
fi

parar() {
    # SIGINT, nunca SIGKILL: wf-recorder cierra el contenedor al recibirlo, y un
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

    if [ -e "/proc/$PID_VIVO" ]; then
        avisar "La grabación no se cierra" dialog-error "sigue viva en el PID $PID_VIVO"
        exit 1
    fi
    if [ -z "$RUTA_VIVA" ] || [ ! -s "$RUTA_VIVA" ]; then
        avisar "La grabación salió vacía" dialog-error "mira $REGISTRO"
        exit 1
    fi

    # Cuanto duro y cuanto ocupa, que es lo que uno quiere saber al parar.
    local detalle="$(basename "$RUTA_VIVA")"
    local tam="$(du -h "$RUTA_VIVA" 2>/dev/null | cut -f1)"
    if [ -n "$INICIO" ]; then
        local seg=$(( $(date +%s) - INICIO ))
        detalle="$detalle · $((seg / 60))m $((seg % 60))s"
    fi
    [ -n "$tam" ] && detalle="$detalle · $tam"

    printf '%s' "$RUTA_VIVA" | wl-copy
    avisar "Grabación guardada" camera-video "$detalle"
    exit 0
}

# --pausar NO para: cierra el tramo y sigue viva la grabacion (se atiende mas
# abajo, cuando ya existen nombre_libre() y DESTINO).
if [ -n "$PID_VIVO" ] && [ "${1:-}" != "--pausar" ]; then
    parar
fi

# --- A partir de aqui, no habia nada grabando (o se solicita pausar/reanudar) -

if [ "${1:-}" = "--pausar" ]; then
    if [ -z "$PID_VIVO" ]; then
        avisar "No hay ninguna grabación para pausar"
        exit 0
    fi
    if [ "$PAUSADO" -eq 1 ]; then
        # Reanudar: arrancar un nuevo tramo con los mismos argumentos
        kill -INT "$PID_VIVO" 2>/dev/null
        n=0
        while [ -e "/proc/$PID_VIVO" ] && [ "$n" -lt 100 ]; do
            sleep 0.1
            n=$((n + 1))
        done
        # El tramo que cierra se apunta con los ya cerrados, uno por linea.
        if [ -n "$TRAMOS" ]; then
            TRAMOS="$TRAMOS
$RUTA_VIVA"
        else
            TRAMOS="$RUTA_VIVA"
        fi
        ARCHIVO=$(nombre_libre "$MODO")
        RUTA_VIVA="$ARCHIVO"
        # La misma zona que se guardo al empezar: en este proceso nuevo DONDE no
        # existe, lo que hay es ZONA_VIVA leido del estado.
        OPCIONES=("${ZONA_VIVA[@]}")
        [ "$AUDIO" -eq 1 ] && OPCIONES+=(-a)
        wf-recorder "$@" "${OPCIONES[@]}" -f "$ARCHIVO" >"$REGISTRO" 2>&1 < /dev/null &
        PID_VIVO=$!
        sleep 0.5
        PAUSADO=0
        PAUSA_INICIO=0
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
            "$PID_VIVO" "$RUTA_VIVA" "$INICIO" "$PAUSADO" "$PAUSA_ACUM" "$PAUSA_INICIO" "$TRAMOS" "${ZONA_VIVA[*]}" > "$ESTADO"
        avisar "Grabación reanudada" media-record
        exit 0
    else
        # Pausar: cerrar el tramo actual con SIGINT y marcar pausado
        kill -INT "$PID_VIVO" 2>/dev/null
        n=0
        while [ -e "/proc/$PID_VIVO" ] && [ "$n" -lt 100 ]; do
            sleep 0.1
            n=$((n + 1))
        done
        PAUSADO=1
        PAUSA_INICIO=$(date +%s)
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
            "$PID_VIVO" "$RUTA_VIVA" "$INICIO" "$PAUSADO" "$PAUSA_ACUM" "$PAUSA_INICIO" "$TRAMOS" "${ZONA_VIVA[*]}" > "$ESTADO"
        avisar "Grabación pausada" media-pause "SUPER+R o clic para parar; clic derecho para reanudar"
        exit 0
    fi
fi

MODO=zona
AUDIO=0
for arg in "$@"; do
    case "$arg" in
        --full|-f)  MODO=pantalla ;;
        --audio|-a) AUDIO=1 ;;
        --parar|-p)
            avisar "No hay ninguna grabación en curso"
            exit 0 ;;
        *)
            echo "uso: $(basename "$0") [--full] [--audio] | --parar | --pausar" >&2
            exit 2 ;;
    esac
done

# El bind no falla si falta el programa: pulsas la tecla y NO PASA NADA, sin una
# sola pista de por que. Es el fallo en silencio que este repo evita en todo lo
# demas, asi que se dice.
if ! command -v wf-recorder >/dev/null 2>&1; then
    avisar "Falta wf-recorder" dialog-error "sudo pacman -S wf-recorder"
    exit 1
fi

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

case "$MODO" in
    pantalla)
        # El monitor que tengas DELANTE, no "el primero": sin -o, wf-recorder
        # coge la salida que el compositor liste primero, que con dos pantallas
        # no tiene por que ser en la que estas mirando.
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
        DONDE=(-o "$SALIDA")
        ;;
    zona)
        # slurp devuelve vacio y codigo 1 si cancelas con Escape o clic derecho:
        # eso no es un error, es que has cambiado de idea.
        ZONA=$(slurp "${SLURP_COLORES[@]}") || exit 0
        [ -n "$ZONA" ] || exit 0

        # H.264 codifica en bloques de 2x2 pixeles, asi que una zona de ancho o
        # alto IMPAR no se puede codificar: wf-recorder arranca, muere en el
        # sitio, y el atajo se queda en nada. Recortar un pixel no se ve; que no
        # grabe, si. Recortar hasta cero, tampoco vale.
        IFS=', x' read -r ZX ZY ZW ZH <<< "$ZONA"
        ZW=$((ZW - ZW % 2)); ZH=$((ZH - ZH % 2))
        if [ "$ZW" -lt 2 ] || [ "$ZH" -lt 2 ]; then
            avisar "Esa zona es demasiado pequeña" dialog-error
            exit 1
        fi
        DONDE=(-g "$ZX,$ZY ${ZW}x${ZH}")
        ;;
esac

ARCHIVO=$(nombre_libre "$MODO")

OPCIONES=("${DONDE[@]}")
# -a sin nombre de dispositivo coge la fuente por defecto de PipeWire, que es lo
# que uno espera: lo que se este oyendo.
[ "$AUDIO" -eq 1 ] && OPCIONES+=(-a)

# Codificar en la GPU sale casi gratis; por CPU, un portatil de dos nucleos
# pierde fotogramas y encima ralentiza justo lo que estas grabando. Pero NO se da
# por hecho que se pueda: hay maquinas sin /dev/dri y drivers sin H.264. Se
# intenta, y si el proceso se muere en el primer segundo se reintenta por
# software — con aviso, porque grabar por CPU tiene un precio que conviene saber.
arrancar() {
    wf-recorder "$@" "${OPCIONES[@]}" -f "$ARCHIVO" >"$REGISTRO" 2>&1 < /dev/null &
    PID=$!
    sleep 1.2
    kill -0 "$PID" 2>/dev/null
}

COMO="por hardware"
if [ ! -e /dev/dri/renderD128 ] || ! arrancar -c h264_vaapi -d /dev/dri/renderD128; then
    rm -f "$ARCHIVO"
    if ! arrancar; then
        avisar "No arranca la grabación" dialog-error "$(tail -3 "$REGISTRO" 2>/dev/null)"
        exit 1
    fi
    COMO="por CPU"
fi

# El estado lleva ademas la zona (DONDE) y los tramos ya cerrados: es lo que
# permite reanudar en el mismo sitio y unirlos al final. Ocho campos por tab:
# pid, ruta, inicio, pausado, pausa_acum, pausa_inicio, tramos, donde.
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$PID" "$ARCHIVO" "$(date +%s)" 0 0 0 "" "${DONDE[*]}" > "$ESTADO"

DETALLE="$COMO"
[ "$AUDIO" -eq 1 ] && DETALLE="$DETALLE · con sonido"
avisar "Grabando ($MODO)" media-record "$DETALLE · SUPER+R o clic en el punto rojo para parar; clic derecho para pausar"
