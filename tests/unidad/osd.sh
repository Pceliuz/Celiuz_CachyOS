#!/usr/bin/env bash
# tests/unidad/osd.sh — las teclas de volumen, micro y brillo (scripts/osd.sh):
# que hagan el cambio Y lo enseñen, sin apilar avisos ni ensuciar el historial.
#
# QUE VIGILA
# ----------
# - Que el cambio se hace igual que antes: el tope del 100% (`-l 1.0`), el suelo
#   del brillo (`-n`), y que subir el volumen quita el silencio.
# - Que el aviso lleva el valor (`int:value`, la barra de mako), la categoria
#   `osd` (lo que en mako/config le quita el sonido y lo pone abajo) y va como
#   transitorio (lo que en avisos.py lo deja fuera del historial).
# - Que una pulsacion REEMPLAZA el aviso de la anterior en vez de apilarse.
# - Que sin notify-send, o sin salida de sonido, la tecla no se rompe.
#
# - Que mueve la salida POR LA QUE SUENA cuando no es la predeterminada (la
#   predeterminada fijada en los altavoces y la musica en unos auriculares
#   Bluetooth: las teclas bajaban unos altavoces mudos), y lo dice en el aviso.
#
# wpctl, brightnessctl, notify-send y pw-dump son de mentira: el volumen de
# verdad no se toca, y lo que suene en la maquina que corre la prueba no cuenta.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

SCRIPT="$REPO/hypr/scripts/osd.sh"
export HYPRLAND_INSTANCE_SIGNATURE="firma_osd"

# wpctl de mentira: el volumen vive en $TMP/vol («0.45» o «0.45 [MUTED]»).
echo "0.45" > "$TMP/vol"
binario_falso wpctl 0 '
case "$1" in
    get-volume) echo "Volume: $(cat "'"$TMP"'/vol")" ;;
    set-mute) v=$(cut -d" " -f1 "'"$TMP"'/vol")
              case "$3" in
                  0) echo "$v" > "'"$TMP"'/vol" ;;
                  toggle) grep -q MUTED "'"$TMP"'/vol" && echo "$v" > "'"$TMP"'/vol" \
                              || echo "$v [MUTED]" > "'"$TMP"'/vol" ;;
              esac ;;
esac'
# pw-dump de mentira: lo que haya en $TMP/pw.json. De entrada, nada sonando.
echo "[]" > "$TMP/pw.json"
binario_falso pw-dump 0 'cat "'"$TMP"'/pw.json"'
binario_falso brightnessctl 0 'case "$*" in *-m*) echo "intel_backlight,backlight,300,40%,750" ;; esac'
# notify-send de mentira: contesta un id nuevo en cada llamada, como mako.
binario_falso notify-send 0 'echo $(( $(wc -l < "'"$REGISTRO"'/notify-send.log") + 100 ))'

correr() { salida="$(bash "$SCRIPT" "$@" 2>&1)"; codigo=$?; }
ultimo_aviso() { tail -1 "$REGISTRO/notify-send.log"; }

titulo "1. Subir el volumen: sube con tope, quita el silencio y lo enseña"
echo "0.45 [MUTED]" > "$TMP/vol"
correr volumen subir
afirmar_igual "0" "$codigo" "termina bien"
afirmar_igual "" "$salida" "sin nada por stderr"
afirmar_contiene "$REGISTRO/wpctl.log" "set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 5%\+" "sube un 5% con el tope del 100%"
afirmar_contiene "$REGISTRO/wpctl.log" "set-mute @DEFAULT_AUDIO_SINK@ 0" "y quita el silencio"
afirmar "el aviso dice el volumen" grep -q "Volumen  45%" <<< "$(ultimo_aviso)"
afirmar "lleva el valor para la barra" grep -q -- "--hint=int:value:45" <<< "$(ultimo_aviso)"
afirmar "va con la categoria osd (mako: abajo y sin sonido)" grep -q -- "--category=osd" <<< "$(ultimo_aviso)"
afirmar "y como transitorio (fuera del historial)" grep -q -- "--transient" <<< "$(ultimo_aviso)"
afirmar "el primero no reemplaza a nadie" bash -c '! grep -q -- --replace-id <<< "$1"' _ "$(ultimo_aviso)"

titulo "2. La siguiente pulsacion reemplaza al aviso anterior"
correr volumen bajar
afirmar_contiene "$REGISTRO/wpctl.log" "set-volume @DEFAULT_AUDIO_SINK@ 5%-" "baja un 5%"
afirmar "reemplaza el aviso 101 (el que devolvio el primero)" grep -q -- "--replace-id=101" <<< "$(ultimo_aviso)"
correr volumen bajar
afirmar "y la tercera, al 102" grep -q -- "--replace-id=102" <<< "$(ultimo_aviso)"
afirmar "el id vive en el runtime, con la firma" test -f "$XDG_RUNTIME_DIR/celiuz-osd.firma_osd.id"

titulo "3. Silenciar"
echo "0.45" > "$TMP/vol"
correr volumen silenciar
afirmar_contiene "$REGISTRO/wpctl.log" "set-mute @DEFAULT_AUDIO_SINK@ toggle" "alterna el silencio"
afirmar "y dice que esta silenciado" grep -q "Silenciado" <<< "$(ultimo_aviso)"
afirmar "con la barra a 0" grep -q -- "int:value:0" <<< "$(ultimo_aviso)"

titulo "4. Microfono"
echo "0.80" > "$TMP/vol"
correr micro silenciar
afirmar_contiene "$REGISTRO/wpctl.log" "set-mute @DEFAULT_AUDIO_SOURCE@ toggle" "alterna el micro, no los altavoces"
afirmar "y lo dice" grep -q "Micrófono silenciado" <<< "$(ultimo_aviso)"

titulo "5. Brillo"
correr brillo bajar
afirmar_contiene "$REGISTRO/brightnessctl.log" "-q -n set 5%-" "baja con el suelo (-n: nunca a 0)"
afirmar "enseña el brillo que queda" grep -q "Brillo  40%" <<< "$(ultimo_aviso)"
afirmar "con su barra" grep -q -- "int:value:40" <<< "$(ultimo_aviso)"
correr brillo subir
afirmar_contiene "$REGISTRO/brightnessctl.log" "-q set 5%\+" "sube un 5%"

titulo "6. La musica va por otra salida que la predeterminada"
# Lo del 2026-10-19: predeterminada = altavoces (58), Brave sonando en los TWS
# (96), y otro flujo parado en los altavoces, que no cuenta.
pw_json() {   # pw_json <salida de Brave>
    cat > "$TMP/pw.json" <<JSON
[
 {"id": 58, "type": "PipeWire:Interface:Node", "info": {"state": "suspended", "props": {
   "media.class": "Audio/Sink", "node.name": "alsa_output.analog", "node.description": "Audio Interno"}}},
 {"id": 96, "type": "PipeWire:Interface:Node", "info": {"state": "running", "props": {
   "media.class": "Audio/Sink", "node.name": "bluez_output.41_42", "node.description": "TWS", "node.nick": "TWS"}}},
 {"id": 68, "type": "PipeWire:Interface:Node", "info": {"state": "running", "props": {
   "media.class": "Stream/Output/Audio", "application.name": "Brave"}}},
 {"id": 70, "type": "PipeWire:Interface:Node", "info": {"state": "suspended", "props": {
   "media.class": "Stream/Output/Audio", "application.name": "Parado"}}},
 {"id": 200, "type": "PipeWire:Interface:Link", "info": {"output-node-id": 68, "input-node-id": $1}},
 {"id": 201, "type": "PipeWire:Interface:Link", "info": {"output-node-id": 68, "input-node-id": $1}},
 {"id": 202, "type": "PipeWire:Interface:Link", "info": {"output-node-id": 70, "input-node-id": 58}},
 {"id": 40, "type": "PipeWire:Interface:Metadata", "props": {"metadata.name": "default"},
  "metadata": [{"subject": 0, "key": "default.audio.sink", "type": "Spa:String:JSON",
                "value": {"name": "alsa_output.analog"}}]}
]
JSON
}
pw_json 96
echo "0.45" > "$TMP/vol"
: > "$REGISTRO/wpctl.log"
correr volumen bajar
afirmar_contiene "$REGISTRO/wpctl.log" "set-volume 96 5%-" "baja la salida por la que suena (los TWS)"
afirmar_no_contiene "$REGISTRO/wpctl.log" "DEFAULT_AUDIO_SINK" "y no toca la predeterminada"
afirmar "el aviso dice por donde va" grep -q "Volumen  45%  · TWS" <<< "$(ultimo_aviso)"

pw_json 58
: > "$REGISTRO/wpctl.log"
correr volumen subir
afirmar_contiene "$REGISTRO/wpctl.log" "set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 5%\+" \
    "si suena por la predeterminada, se mueve la predeterminada"
afirmar "y el aviso no lleva nombre" bash -c '! grep -q " · " <<< "$1"' _ "$(ultimo_aviso)"

# Si pw-dump falla, la predeterminada: la tecla nunca se queda sin hacer nada.
binario_falso pw-dump 1
: > "$REGISTRO/wpctl.log"
correr volumen bajar
afirmar_contiene "$REGISTRO/wpctl.log" "set-volume @DEFAULT_AUDIO_SINK@ 5%-" \
    "sin pw-dump, la predeterminada como siempre"
echo "[]" > "$TMP/pw.json"
binario_falso pw-dump 0 'cat "'"$TMP"'/pw.json"'

titulo "7. Sin salida de sonido, o sin notify-send, la tecla no se rompe"
binario_falso wpctl 1
correr volumen subir
afirmar_igual "0" "$codigo" "sin salida de sonido termina bien"
afirmar "y lo dice" grep -q "Sin salida de sonido" <<< "$(ultimo_aviso)"
rm "$FALSOS/notify-send"
echo "0.45" > "$TMP/vol"
binario_falso wpctl 0 'case "$1" in get-volume) echo "Volume: 0.50" ;; esac'
PATH="$FALSOS:/usr/bin:/bin" ; hash -r
if command -v notify-send >/dev/null 2>&1; then
    # Hay uno de verdad en el sistema: se tapa con uno que falla y no contesta.
    binario_falso notify-send 1
fi
correr volumen subir
afirmar_igual "0" "$codigo" "sin servidor de avisos el volumen se cambia igual"
afirmar_contiene "$REGISTRO/wpctl.log" "set-volume -l 1.0" "(y se ha cambiado)"

afirmar_intacta_la_casa_real
resumen
