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
afirmar_contiene "$TMP" "$TMP" "(sin comprobacion de ruta)"
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

titulo "3. Pausar cierra el tramo y congela el tiempo"
TRAMO1="$(campo ruta)"
bash "$SCRIPT" --pausar >/dev/null 2>&1
[ "$(campo pausado)" = "True" ] && ok "el estado dice pausado" || fallo "no dice pausado tras --pausar"
[ -s "$TRAMO1" ] && ok "el primer tramo quedo escrito" || fallo "el primer tramo quedo vacio: '$TRAMO1'"
case "$(campo text)" in
    *⏸*) ok "el modulo ensena la pausa" ;;
    *) fallo "el modulo no ensena la pausa: '$(campo text)'" ;;
esac
t1="$(campo transcurrido)"
sleep 1.2
t2="$(campo transcurrido)"
afirmar_igual "$t1" "$t2" "en pausa el tiempo transcurrido no corre"

# --- 4. Reanudar: otro tramo de la misma zona --------------------------------

titulo "4. Reanudar abre un segundo tramo"
bash "$SCRIPT" --pausar >/dev/null 2>&1
[ "$(campo pausado)" = "False" ] && ok "vuelve a decir grabando" || fallo "no reanuda"
[ "$(campo grabando)" = "True" ] && ok "y sigue grabando" || fallo "dejo de decir grabando"
TRAMO2="$(campo ruta)"
[ "$TRAMO2" != "$TRAMO1" ] && ok "el segundo tramo es otro archivo" \
    || fallo "el segundo tramo reusa el primero: '$TRAMO2'"
afirmar_contiene "$REGISTRO/wf-recorder.log" "-g 10,20 300x200" "el segundo tramo graba la misma zona"

# --- 5. Parar: un solo archivo final ----------------------------------------

titulo "5. Parar une los tramos en un solo archivo"
bash "$SCRIPT" --parar >/dev/null 2>&1
[ "$(campo grabando)" = "False" ] && ok "ya no dice grabando" || fallo "sigue diciendo grabando"
[ "$(campo text)" = "" ] && ok "el modulo desaparece" || fallo "el modulo sigue ahi: '$(campo text)'"
afirmar_igual "1" "$(veces_llamado ffmpeg)" "se llama a ffmpeg una vez para unir los tramos"
afirmar_contiene "$REGISTRO/ffmpeg.log" "concat" "el union es por concat (sin recodificar)"
FINAL="$(ls "$TMP/videos/grabaciones"/*.mp4 2>/dev/null | head -1)"
[ -n "$FINAL" ] && [ -s "$FINAL" ] && ok "queda un mp4 final con contenido" \
    || fallo "no quedo un mp4 final: '$FINAL'"
[ "$(ls "$TMP/videos/grabaciones"/*.mp4 2>/dev/null | wc -l)" -eq 1 ] \
    && ok "queda UN solo archivo, no dos" || fallo "quedaron varios archivos"

resumen
