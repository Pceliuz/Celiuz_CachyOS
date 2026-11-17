#!/usr/bin/env bash
# tests/unidad/grabar.sh — grabar.sh (pantalla, zona, ventana, sonido, pausa,
# interruptor y los indicadores de waybar), lib/grabacion.py y el selector del
# portal (grabar-portal.py).
#
# NADA real: gpu-screen-recorder, slurp, hyprctl, pw-dump, wl-copy,
# notify-send y hyprland-share-picker son de mentira. El grabador falso es un
# proceso que lanza esta prueba y para esta prueba.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

SCRIPT="$REPO/hypr/scripts/grabar.sh"
PORTAL="$REPO/hypr/scripts/grabar-portal.py"
LIB="$REPO/hypr/scripts/lib/grabacion.py"

# El grabador de mentira apunta sus argumentos, se queda vivo hasta que le llega
# SIGINT —que es como cierra el de verdad— y entonces deja escrito el mp4 que
# se le pidio con -o. SIGUSR2 es la pausa: se apunta cada vez que llega.
#
# En Python y no en bash, a proposito: un proceso lanzado con `&` desde un
# script no interactivo NACE con SIGINT ignorada, y bash no puede atrapar una
# senal que ya se ignoraba al arrancar —el falso no se paraba nunca—. Python
# (como el grabador de verdad, que es C) si puede volver a ponerle un manejador.
cat > "$FALSOS/gsr_falso.py" <<FIN
import signal, sys, time
try:
    # grabar.sh comprueba /proc/PID/comm antes de fiarse del PID: se pone el
    # nombre que tiene el de verdad (el kernel lo corta a 15 caracteres).
    open("/proc/self/comm", "w").write("gpu-screen-reco")
except OSError:
    pass
with open("$REGISTRO/gsr.log", "a") as f:
    f.write(" ".join(sys.argv[1:]) + "\\n")
salida = sys.argv[sys.argv.index("-o") + 1]
def pausa(*_):
    with open("$REGISTRO/gsr-senales.log", "a") as f:
        f.write("usr2\\n")
def parar(*_):
    open(salida, "w").write("mp4")
    sys.exit(0)
signal.signal(signal.SIGUSR2, pausa)
signal.signal(signal.SIGINT, parar)
signal.signal(signal.SIGTERM, parar)
while True:
    time.sleep(0.05)
FIN
binario_falso gpu-screen-recorder 0 "exec python3 $FALSOS/gsr_falso.py \"\$@\""

# Un proceso cualquiera que haga de "la app de la ventana": lo que importa es
# que exista su PID, para que lib/grabacion.py busque su sonido por el.
sleep 600 & APP_PID=$!

binario_falso slurp 0 "echo '300x200+10+20'"
binario_falso hyprctl 0 'case "$*" in
    *activeworkspace*) echo "{\"monitor\":\"DP-1\"}" ;;
    *clients*) echo "[{\"address\":\"0xabc123\",\"class\":\"PruebaApp\",\"title\":\"Una clase\",\"workspace\":{\"name\":\"3\"},\"pid\":'"$APP_PID"',\"mapped\":true,\"hidden\":false,\"focusHistoryID\":1}]" ;;
esac'
binario_falso pw-dump 0 'echo "[{\"info\":{\"props\":{\"media.class\":\"Stream/Output/Audio\",\"application.name\":\"TonoPrueba\",\"application.process.id\":'"$APP_PID"'}}},{\"info\":{\"props\":{\"media.class\":\"Stream/Output/Audio\",\"application.name\":\"MusicaAjena\",\"application.process.id\":1}}}]"'
binario_falso wl-copy 0 "cat > /dev/null"
binario_falso xdg-user-dir 0 "echo $TMP/videos"
binario_falso notify-send 0
binario_falso celiuz-grabar-portal 0
binario_falso hyprland-share-picker 0 "echo '[SELECTION]/screen:DP-1'"

trap 'bash "$SCRIPT" --parar >/dev/null 2>&1 || true; kill "$APP_PID" 2>/dev/null; limpiar_entorno' EXIT

# campo <nombre> — un campo del JSON que contesta --estado.
campo() {
    bash "$SCRIPT" --estado | python3 -c "import json,sys;print(json.load(sys.stdin).get('$1',''))"
}
tirador() {
    bash "$SCRIPT" --estado-tirador | python3 -c "import json,sys;print(json.load(sys.stdin)['class'])"
}
ultima_llamada() { tail -1 "$REGISTRO/gsr.log" 2>/dev/null; }
parar() { bash "$SCRIPT" --parar >/dev/null 2>&1; }

# --- 1. Sin grabar ----------------------------------------------------------

titulo "1. Sin grabar no hay indicador y no se toca el grabador"
[ "$(campo grabando)" = "False" ] && ok "el estado dice que no se graba" || fallo "el estado no dice false"
[ "$(campo text)" = "" ] && ok "el modulo de la barra va vacio" || fallo "el modulo no va vacio: '$(campo text)'"
afirmar_igual "" "$(tirador)" "la linea-tirador sin clase (color de siempre)"
afirmar_igual "0" "$(veces_llamado gpu-screen-recorder)" "preguntar el estado no arranca nada"

# Sin argumentos se abre la tarjeta; sin Wayland (como aqui) no se puede, y
# eso tiene que acabar en nada, no en una grabacion de algo que nadie eligio.
bash "$SCRIPT" >/dev/null 2>&1
afirmar_igual "0" "$(veces_llamado gpu-screen-recorder)" "sin tarjeta que contestar no se graba nada"

# --- 2. Pantalla completa ---------------------------------------------------

titulo "2. --full graba el monitor delante, con el sonido del equipo"
bash "$SCRIPT" --full >/dev/null 2>&1
L="$(ultima_llamada)"
case "$L" in *"-w DP-1 "*) ok "graba DP-1, el monitor del escritorio activo" ;; *) fallo "no graba DP-1: $L" ;; esac
case "$L" in *"-a default_output"*) ok "con el sonido del equipo" ;; *) fallo "sin sonido del equipo: $L" ;; esac
case "$L" in *"-k h264"*"-o $TMP/videos/grabaciones/pantalla_"*.mp4) ok "h264 y el mp4 en grabaciones/" ;; *) fallo "codec o destino raros: $L" ;; esac
PID="$(campo pid)"
[ -n "$PID" ] && [ -e "/proc/$PID" ] && ok "hay un grabador vivo (PID $PID)" || fallo "no quedo grabador vivo"
[ "$(campo grabando)" = "True" ] && ok "el estado dice grabando" || fallo "el estado no dice grabando"
case "$(campo text)" in
    *[0-9][0-9]:[0-9][0-9]*) ok "el modulo enseña el tiempo mm:ss" ;;
    *) fallo "el modulo no enseña el tiempo: '$(campo text)'" ;;
esac
afirmar_igual "grabando" "$(tirador)" "la linea-tirador se pone en «grabando» (roja)"
afirmar_contiene "$REGISTRO/notify-send.log" "SUPER\\+R para terminar" "el aviso dice como se termina"
afirmar_contiene "$REGISTRO/notify-send.log" "SUPER\\+CTRL\\+R para pausar" "y como se pausa, con el teclado"
afirmar_contiene "$REGISTRO/notify-send.log" "-c de-paso" "los avisos son «de paso»: se ven tambien en «no molestar» (jugando)"
afirmar_igual "pantalla" "$(campo modo)" "el estado dice que se graba la pantalla"
afirmar_igual "DP-1" "$(campo donde)" "y cual (para que la pastilla se ponga en otra)"

# --- 3. Pausa ---------------------------------------------------------------

titulo "3. --pausar pausa con SIGUSR2 y el reloj se queda quieto"
bash "$SCRIPT" --pausar >/dev/null 2>&1
sleep 0.2
afirmar_igual "1" "$(veces_llamado gsr-senales)" "le llega una SIGUSR2 al grabador"
[ "$(campo pausado)" = "True" ] && ok "el estado dice pausado" || fallo "el estado no dice pausado"
afirmar_igual "pausado" "$(tirador)" "la linea-tirador pasa a «pausado» (ambar)"
antes="$(campo transcurrido)"; sleep 1.2; despues="$(campo transcurrido)"
afirmar_igual "$antes" "$despues" "en pausa el tiempo no avanza"
[ -e "/proc/$PID" ] && ok "en pausa el grabador sigue vivo (un solo video, sin tramos)" || fallo "pausar mato el grabador"

bash "$SCRIPT" --pausar >/dev/null 2>&1
sleep 0.2
afirmar_igual "2" "$(veces_llamado gsr-senales)" "otra SIGUSR2 para reanudar"
[ "$(campo pausado)" = "False" ] && ok "ya no dice pausado" || fallo "sigue diciendo pausado"

# --- 4. El interruptor ------------------------------------------------------

titulo "4. SUPER+R con una grabacion viva la para y la guarda"
bash "$SCRIPT" >/dev/null 2>&1
[ ! -e "/proc/$PID" ] && ok "el grabador se cerro" || fallo "el grabador sigue vivo"
ls "$TMP"/videos/grabaciones/pantalla_*.mp4 >/dev/null 2>&1 && ok "el video quedo guardado" || fallo "no hay video"
[ "$(campo grabando)" = "False" ] && ok "el estado vuelve a vacio" || fallo "el estado sigue grabando"
afirmar_contiene "$REGISTRO/notify-send.log" "Grabación guardada" "avisa de que se guardo"
afirmar_igual "1" "$(veces_llamado gpu-screen-recorder)" "y NO empezo otra grabacion"
afirmar_igual "1" "$(veces_llamado wl-copy)" "la ruta va al portapapeles"

# --- 5. Zona ----------------------------------------------------------------

titulo "5. --zona graba lo que marca slurp, en el formato de -region"
bash "$SCRIPT" --zona >/dev/null 2>&1
case "$(ultima_llamada)" in
    *"-w region -region 300x200+10+20 "*) ok "zona 300x200+10+20" ;;
    *) fallo "zona mal pasada: $(ultima_llamada)" ;;
esac
parar

# --- 6. Ventana -------------------------------------------------------------

titulo "6. --ventana: la imagen por el portal y SOLO el sonido de esa app"
bash "$SCRIPT" --ventana 0xabc123 >/dev/null 2>&1
L="$(ultima_llamada)"
case "$L" in *"-w portal "*) ok "la imagen va por el portal" ;; *) fallo "no va por el portal: $L" ;; esac
case "$L" in *"-a app:TonoPrueba|"*) ok "el sonido que PipeWire dice que sale de su proceso" ;; *) fallo "no coge su flujo: $L" ;; esac
case "$L" in *"app:PruebaApp"*) ok "y de reserva su clase, por si empieza a sonar despues" ;; *) fallo "falta la clase de reserva: $L" ;; esac
case "$L" in *MusicaAjena*|*default_output*) fallo "se cuela sonido de otra app: $L" ;; *) ok "no se cuela el sonido de nadie mas" ;; esac
RECADO="$(ls "$XDG_RUNTIME_DIR"/grabar-ventana.*recado 2>/dev/null | head -1)"
[ -n "$RECADO" ] && grep -q '"0xabc123"' "$RECADO" && ok "deja el recado para el selector del portal" \
    || fallo "no hay recado con la ventana"
afirmar_contiene "$REGISTRO/notify-send.log" "solo con el sonido de esa app" "el aviso dice de quien es el sonido"
parar

bash "$SCRIPT" --ventana 0xnoexiste >/dev/null 2>&1
afirmar_igual "3" "$(veces_llamado gpu-screen-recorder)" "una ventana que ya no esta no se graba"

# --- 7. Sin sonido ----------------------------------------------------------

titulo "7. --sin-audio no pide sonido"
bash "$SCRIPT" --full --sin-audio >/dev/null 2>&1
case "$(ultima_llamada)" in *" -a "*) fallo "pidio sonido: $(ultima_llamada)" ;; *) ok "sin -a" ;; esac
afirmar_contiene "$REGISTRO/notify-send.log" "sin sonido" "y el aviso lo dice"
parar

# --- 8. El selector del portal ----------------------------------------------

titulo "8. grabar-portal.py contesta con el recado, y si no, el de siempre"
LISTA="111[HC>]otra[HT>]Otra[HE>]123[HA>]222[HC>]PruebaApp[HT>]Una clase[HE>]$((16#abc123))[HA>]"
python3 "$LIB" preseleccionar 0xabc123
R="$(XDPH_WINDOW_SHARING_LIST="$LISTA" python3 "$PORTAL" --allow-token)"
afirmar_igual "[SELECTION]/window:222" "$R" "con recado: la ventana encargada, por su id del portal"
afirmar_igual "0" "$(veces_llamado hyprland-share-picker)" "sin molestar al selector de siempre"

R="$(XDPH_WINDOW_SHARING_LIST="$LISTA" python3 "$PORTAL" --allow-token)"
afirmar_igual "[SELECTION]/screen:DP-1" "$R" "el recado vale UNA vez: la siguiente pregunta va al de siempre"
afirmar_contiene "$REGISTRO/hyprland-share-picker.log" "--allow-token" "y le pasa los mismos argumentos"

python3 - "$LIB" <<'FIN'
import importlib.util, json, sys, time
spec = importlib.util.spec_from_file_location("grabacion", sys.argv[1])
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
ruta = g.ruta_recado()
json.dump({"direccion": "0xabc123", "cuando": time.time() - 3600}, open(ruta, "w"))
FIN
R="$(XDPH_WINDOW_SHARING_LIST="$LISTA" python3 "$PORTAL")"
afirmar_igual "[SELECTION]/screen:DP-1" "$R" "un recado viejo no contesta por su cuenta (una videollamada despues)"

python3 "$LIB" preseleccionar 0xdeadbeef
R="$(XDPH_WINDOW_SHARING_LIST="$LISTA" python3 "$PORTAL")"
afirmar_igual "[SELECTION]/screen:DP-1" "$R" "si la ventana encargada ya no esta, se pregunta en vez de grabar otra"

# --- 8b. Que el portal pueda encontrarlo ----------------------------------

titulo "8b. xdph.conf nombra el selector por el PATH, y instalar.sh crea ese enlace"
# xdph lanza el selector con execvp, sin shell: ni `~` ni $HOME se expanden.
SEL="$(sed -n 's/^[[:space:]]*custom_picker_binary[[:space:]]*=[[:space:]]*//p' "$REPO/hypr/xdph.conf")"
case "$SEL" in
    */*|*'~'*|*'$'*|"") fallo "el selector va por ruta, y xdph no la expande: '$SEL'" ;;
    *) ok "el selector va por nombre: $SEL" ;;
esac
afirmar_contiene "$REPO/instalar.sh" "enlazar .*grabar-portal\\.py.*\\.local/bin/$SEL\"" "instalar.sh enlaza ese nombre en ~/.local/bin"

# --- 8c. La pastilla de los modos sin barra --------------------------------

titulo "8c. La pastilla sale solo en un modo, y lejos de lo que se graba"
R="$(python3 - "$LIB" <<'FIN'
import importlib.util, json, os, sys
spec = importlib.util.spec_from_file_location("grabacion", sys.argv[1])
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
dos = [{"name": "DP-1", "x": 0, "y": 0, "width": 2560, "height": 1440, "scale": 1, "focused": True},
       {"name": "HDMI-A-1", "x": 2560, "y": 0, "width": 1920, "height": 1080, "scale": 1, "focused": False}]
uno = dos[:1]
print(g.monitor_para_indicador("pantalla", "DP-1", dos)["name"])
print(g.monitor_para_indicador("zona", "300x200+2600+20", dos)["name"])
print(g.monitor_para_indicador("ventana", "0xabc", dos)["name"])
print(g.monitor_para_indicador("pantalla", "DP-1", uno)["name"])
# Con escala: un monitor de 3840 a 1.5 mide 2560 logicos; x=2600 ya es del otro.
esc = [{"name": "A", "x": 0, "y": 0, "width": 3840, "height": 2160, "scale": 1.5, "focused": True},
       {"name": "B", "x": 2560, "y": 0, "width": 1920, "height": 1080, "scale": 1, "focused": False}]
print(g.monitor_capturado("zona", "10x10+2600+5", esc))

# Los modos, preguntando a cada uno con su estado de verdad en la casa de prueba.
print(g.modo_sin_barra())
gaming = g._modulo("modo-gaming")
json.dump({"activo": True}, open(gaming.ruta_estado(), "w"))
print(g.modo_sin_barra())
os.unlink(gaming.ruta_estado())
estudio = g._modulo("modo-estudio")
estudio.guardar({"encendido": True})
print(g.modo_sin_barra())
FIN
)"
linea() { printf '%s\n' "$R" | sed -n "${1}p"; }
afirmar_igual "HDMI-A-1" "$(linea 1)" "grabando DP-1 entero, la pastilla va a la otra pantalla"
afirmar_igual "DP-1" "$(linea 2)" "grabando una zona de la otra, va a DP-1"
afirmar_igual "DP-1" "$(linea 3)" "grabando una ventana, a la que tienes delante (la ventana se graba sola)"
afirmar_igual "DP-1" "$(linea 4)" "con una sola pantalla, en esa (no hay otra)"
afirmar_igual "B" "$(linea 5)" "la escala cuenta: el ancho es el logico"
afirmar_igual "None" "$(linea 6)" "sin modo puesto, no sale (la barra ya lo dice)"
afirmar_igual "gaming" "$(linea 7)" "en el modo gaming, sale"
afirmar_igual "estudio" "$(linea 8)" "en el modo estudio, sale"

# --- 9. Sonido de una ventana: el arbol de procesos -------------------------

titulo "9. lib/grabacion.py busca el sonido en el proceso de la ventana y sus hijos"
R="$(python3 - "$LIB" <<'FIN'
import importlib.util, os, subprocess, sys
spec = importlib.util.spec_from_file_location("grabacion", sys.argv[1])
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
hijo = subprocess.Popen(["sleep", "30"])
try:
    flujos = [("DelHijo", hijo.pid), ("DeOtro", 1), ("Repetido", os.getpid()), ("repetido", os.getpid())]
    print(g.fuente_audio({"pid": os.getpid(), "clase": "Clase|Rara"}, flujos=flujos))
finally:
    hijo.kill()
FIN
)"
case "$R" in app:DelHijo\|*) ok "el flujo de un proceso hijo cuenta (los navegadores suenan desde uno)" ;; *) fallo "no ve el del hijo: $R" ;; esac
case "$R" in *DeOtro*) fallo "se cuela un flujo ajeno: $R" ;; *) ok "el de otro proceso no" ;; esac
case "$R" in *"app:Repetido|"*repetido*) fallo "repite un nombre (sin mirar mayusculas): $R" ;; *) ok "sin repetir nombres" ;; esac
case "$R" in *"app:ClaseRara") ok "un | dentro de un nombre se quita (partiria la fuente)" ;; *) fallo "el | se colo: $R" ;; esac

afirmar_intacta_la_casa_real
resumen
