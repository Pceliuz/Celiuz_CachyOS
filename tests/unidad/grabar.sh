#!/usr/bin/env bash
# tests/unidad/grabar.sh — el indicador de grabacion (--estado), la pausa por
# tramos y la union de los tramos al parar.
#
# NADA real: wf-recorder, slurp, hyprctl, ffmpeg y notify-send son de mentira, y
# el wf-recorder falso es un proceso que lanza esta prueba y para esta prueba.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

SCRIPT="$REPO/hypr/scripts/grabar.sh"

# El wf-recorder de mentira se queda vivo hasta que le llega SIGINT —que es como
# cierra el de verdad— y entonces deja escrito el mp4 que se le pidio con -f. Si
# la prueba se va a medias, el trap de abajo para la grabacion por el propio
# script, que es quien sabe que PID lanzo.
cat > "$FALSOS/wf_falso" <<'FIN'
#!/usr/bin/env bash
# El script de verdad comprueba /proc/PID/comm antes de fiarse del PID (§ E-43);
# este falso es bash, asi que se pone el nombre para que esa comprobacion valga.
printf 'wf-recorder' > "/proc/$$/comm" 2>/dev/null || true
archivo=""
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
    [ "${args[i]}" = "-f" ] && archivo="${args[i+1]}"
done
trap 'printf "mp4" > "$archivo"; exit 0' INT TERM
while :; do sleep 0.05; done
FIN
chmod +x "$FALSOS/wf_falso"

binario_falso wf-recorder 0 "exec $FALSOS/wf_falso \"\$@\""
binario_falso slurp 0 "echo '10,20 300x200'"
binario_falso hyprctl 0 "echo '{\"monitor\":\"DP-1\"}'"
binario_falso wl-copy 0 "cat > /dev/null"
binario_falso xdg-user-dir 0 "echo $TMP/videos"
binario_falso notify-send 0
# El concat de verdad escribe el archivo de salida, que es el ultimo argumento.
binario_falso ffmpeg 0 "printf 'mp4' > \"\${@: -1}\""

trap 'bash "$SCRIPT" --parar >/dev/null 2>&1 || true' EXIT

# campo <nombre> — un campo del JSON que contesta --estado.
campo() {
    bash "$SCRIPT" --estado | python3 -c "import json,sys;print(json.load(sys.stdin).get('$1',''))"
}

# --- 1. Sin grabar, el modulo no sale ---------------------------------------

titulo "1. Sin grabar no hay indicador y no se toca wf-recorder"
estado="$(bash "$SCRIPT" --estado)"
[ "$(bash "$SCRIPT" --estado | python3 -c "import json,sys;print(json.load(sys.stdin)['grabando'])")" = "False" ] \
    && ok "sin grabacion el estado dice que no" || fallo "sin grabacion el estado no dice false: $estado"
[ "$(campo text)" = "" ] && ok "el texto del modulo va vacio" || fallo "el modulo no va vacio: '$(campo text)'"
afirmar_igual "0" "$(veces_llamado wf-recorder)" "no se arranca ninguna grabacion al preguntar el estado"

# --- 2. Empezar -------------------------------------------------------------

titulo "2. Grabar deja un estado que dice grabando"
bash "$SCRIPT" >/dev/null 2>&1
PID="$(campo pid)"
[ -n "$PID" ] && [ -e "/proc/$PID" ] && ok "hay un wf-recorder vivo (PID $PID)" \
    || fallo "no quedo ningun wf-recorder vivo (PID '$PID')"
[ "$(campo grabando)" = "True" ] && ok "el estado dice grabando" || fallo "el estado no dice grabando"
[ "$(campo pausado)" = "False" ] && ok "y no dice pausado" || fallo "dice pausado sin estarlo"
case "$(campo text)" in
    *[0-9][0-9]:[0-9][0-9]*) ok "el modulo ensena el tiempo mm:ss" ;;
    *) fallo "el modulo no ensena el tiempo: '$(campo text)'" ;;
esac

# El aviso de arranque dice como se para y como se pausa.
afirmar_contiene "$REGISTRO/notify-send.log" "pausar" "el aviso de arranque dice como se pausa"
afirmar_contiene "$REGISTRO/notify-send.log" "parar" "el aviso de arranque dice como se para"

# --- 3. Pausar: se cierra el tramo y el tiempo se queda quieto ---------------

resumen
