#!/usr/bin/env bash
# tests/unidad/sesion.sh — que el menu de salida (SUPER+SHIFT+P) no cierre nada
# sin que se lo confirmes.
#
# QUE VIGILA, Y POR QUE
# ---------------------
# SUPER+SHIFT+P era un `exit` a secas y rozarlo cerro la sesion con todo abierto
# mas de una vez. Ahora abre un menu, y cerrar sesion, reiniciar y apagar
# preguntan otra vez con «No» en la PRIMERA linea: fuzzel preselecciona la
# primera, asi que un Enter por inercia tiene que volver atras. Eso es lo que se
# comprueba aqui, con un fuzzel de mentira que contesta lo que le digamos y un
# systemctl / uwsm / hyprctl de mentira que solo apuntan — nada se apaga de
# verdad.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

# Una copia del script con un lock.sh de mentira al lado: sesion.sh lo busca en
# su propia carpeta, y el de verdad bloquearia la pantalla.
mkdir -p "$TMP/scripts"
mkdir -p "$TMP/scripts/lib"
cp "$REPO/hypr/scripts/sesion.sh" "$REPO/hypr/scripts/despachar.sh" "$TMP/scripts/"
cp "$REPO/hypr/scripts/lib/hypr.sh" "$TMP/scripts/lib/"
SCRIPT="$TMP/scripts/sesion.sh"
printf '#!/bin/sh\necho lock >> "%s/lock.log"\n' "$REGISTRO" > "$TMP/scripts/lock.sh"
chmod +x "$TMP/scripts/lock.sh"

# El fuzzel de mentira contesta, por orden, las respuestas de $TMP/respuestas
# (una por llamada; vacia = Escape). Apunta tambien lo que se le ofrecio.
binario_falso fuzzel 0 '
cat >> "'"$REGISTRO"'/ofrecido.log"; echo "---" >> "'"$REGISTRO"'/ofrecido.log"
n=$(wc -l < "'"$REGISTRO"'/fuzzel.log")
sed -n "${n}p" "'"$TMP"'/respuestas"'
binario_falso systemctl 0
binario_falso hyprctl 0
binario_falso notify-send 0
binario_falso uwsm 0   # `uwsm check is-active` sale con 0: sesion con uwsm

# responder <linea>... — lo que "pulsara" el usuario en cada menu
responder() { printf '%s\n' "$@" > "$TMP/respuestas"; }
limpiar() { rm -f "$REGISTRO"/*.log; }
correr() { salida="$(bash "$SCRIPT" 2>&1)"; codigo=$?; }

# --- 1. Lo peligroso pide confirmacion, y Enter la rechaza ----------------------

for caso in "2:cerrar sesión" "3:reiniciar" "4:apagar"; do
    idx="${caso%%:*}"; verbo="${caso#*:}"
    titulo "1. «$verbo» con Enter en la pregunta (primera linea) no hace nada"
    limpiar; responder "$idx" "0"; correr
    afirmar_igual "0" "$codigo" "el script termina bien"
    afirmar_igual "" "$salida" "sin nada por stderr ni stdout"
    afirmar_igual "2" "$(veces_llamado fuzzel)" "se pregunta dos veces"
    afirmar_contiene "$REGISTRO/ofrecido.log" "No, volver" "la pregunta ofrece volver"
    primera="$(awk '/^---$/{b++; next} b==1{print; exit}' "$REGISTRO/ofrecido.log")"
    afirmar "y «No» es la PRIMERA linea (la preseleccionada)" grep -q "No, volver" <<< "$primera"
    afirmar "no se apaga ni reinicia" test ! -f "$REGISTRO/systemctl.log"
    afirmar "no se cierra la sesion" test ! -f "$REGISTRO/hyprctl.log"
    afirmar_no_contiene "$REGISTRO/uwsm.log" "stop" "uwsm no recibe un stop"

    titulo "1b. «$verbo» con Escape en la pregunta tampoco"
    limpiar; responder "$idx" ""; correr
    afirmar "no se apaga ni reinicia" test ! -f "$REGISTRO/systemctl.log"
    afirmar_no_contiene "$REGISTRO/uwsm.log" "stop" "uwsm no recibe un stop"
done

# --- 2. Confirmado, hace lo que dice -------------------------------------------

titulo "2. Confirmado, cada opcion hace lo suyo"
limpiar; responder 4 1; correr
afirmar_contiene "$REGISTRO/systemctl.log" "^poweroff$" "apagar -> systemctl poweroff"
limpiar; responder 3 1; correr
afirmar_contiene "$REGISTRO/systemctl.log" "^reboot$" "reiniciar -> systemctl reboot"
limpiar; responder 2 1; correr
afirmar_contiene "$REGISTRO/uwsm.log" "^stop$" "cerrar sesion con uwsm -> uwsm stop"
afirmar "y no se mata a Hyprland a pelo" test ! -f "$REGISTRO/hyprctl.log"

titulo "2b. Sin uwsm, cerrar sesion es el exit de Hyprland"
binario_falso uwsm 1
limpiar; responder 2 1; correr
afirmar_contiene "$REGISTRO/hyprctl.log" "dispatch exit" "-> hyprctl dispatch exit"
binario_falso uwsm 0

# --- 3. Lo inofensivo no pregunta ----------------------------------------------

titulo "3. Bloquear y suspender van a la primera"
limpiar; responder 0; correr
afirmar_igual "1" "$(veces_llamado fuzzel)" "bloquear: un solo menu"
afirmar_contiene "$REGISTRO/lock.log" "lock" "bloquear -> lock.sh"
limpiar; responder 1; correr
afirmar_igual "1" "$(veces_llamado fuzzel)" "suspender: un solo menu"
afirmar_contiene "$REGISTRO/systemctl.log" "^suspend$" "suspender -> systemctl suspend"

titulo "4. Escape en el primer menu no hace nada"
limpiar; responder ""; correr
afirmar_igual "0" "$codigo" "termina bien"
afirmar "nada de systemctl" test ! -f "$REGISTRO/systemctl.log"
afirmar "nada de lock" test ! -f "$REGISTRO/lock.log"

afirmar_intacta_la_casa_real
resumen
