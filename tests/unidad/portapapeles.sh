#!/usr/bin/env bash
# tests/unidad/portapapeles.sh — el historial del portapapeles (SUPER+SHIFT+V),
# con sus fijados y sus guardados.
#
# QUE VIGILA
# ----------
# - Que se apunta lo que se copia (texto e imagen) y que copiar dos veces lo
#   mismo no lo duplica: lo sube arriba.
# - Que NO se apunta lo secreto (un gestor de contraseñas), ni el vacio, ni solo
#   espacios, ni lo que pese mas de `max_mb`.
# - Que el historial se olvida solo: por edad (`horas`) y por cantidad (`maximo`).
# - Que fijar dura LA SESION y guardar dura SIEMPRE: con otra firma de Hyprland,
#   los fijados no estan y los guardados si.
# - El menu: Enter copia (las imagenes con su tipo), Ctrl+F/G/D fijan, guardan y
#   borran, y la segunda pulsacion deshace la primera (desfijar, quitar).
# - Que al arrancar se barren las carpetas de sesiones MUERTAS, nunca la de una
#   sesion viva, y sin firma nada.
# - Que el demonio es uno por sesion.
#
# Todo con un wl-paste, un wl-copy y un fuzzel de mentira: el portapapeles de
# verdad no se toca.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

SCRIPT="$REPO/hypr/scripts/portapapeles.py"
export HYPRLAND_INSTANCE_SIGNATURE="firma_uno"
SESION="$XDG_RUNTIME_DIR/celiuz-portapapeles.firma_uno"
GUARDADOS="$XDG_DATA_HOME/celiuz/portapapeles"

# El wl-paste de mentira: los tipos salen de $TMP/tipos y el contenido de
# $TMP/contenido, pida el tipo que pida (la prueba ya pone lo que toca).
binario_falso wl-paste 0 '
case "$*" in
    *--list-types*) cat "'"$TMP"'/tipos" ;;
    *--watch*) sleep 30 ;;
    *) cat "'"$TMP"'/contenido" ;;
esac'
binario_falso wl-copy 0 'cat > "'"$REGISTRO"'/copiado"'
binario_falso notify-send 0

# El fuzzel de mentira contesta, por orden, las lineas «codigo indice» de
# $TMP/respuestas, y apunta lo que se le ofrecio en cada vuelta.
binario_falso fuzzel 0 '
n=$(wc -l < "'"$REGISTRO"'/fuzzel.log")
cat > "'"$REGISTRO"'/ofrecido.$n"
set -- $(sed -n "${n}p" "'"$TMP"'/respuestas")
[ -n "${2:-}" ] && echo "$2"
exit "${1:-1}"'

copiar() {   # copiar <contenido> [tipos...] — como si lo copiaras en una app
    local contenido="$1"; shift
    printf '%s' "$contenido" > "$TMP/contenido"
    printf '%s\n' "${@:-text/plain;charset=utf-8}" > "$TMP/tipos"
    printf 'x' | CLIPBOARD_STATE="${ESTADO:-data}" python3 "$SCRIPT" recibir
}
en() { ls "$1" 2>/dev/null | grep -v '^\.' | grep -v -e fuzzel.ini -e demonio.lock | wc -l | tr -d ' '; }
contenido_de() { local e; for e in "$1"/*; do cat "$e"; echo; done 2>/dev/null; }
menu() {   # menu "codigo indice"... — abre el menu con esas pulsaciones
    rm -f "$REGISTRO"/fuzzel.log "$REGISTRO"/ofrecido.* "$REGISTRO/copiado"
    printf '%s\n' "$@" > "$TMP/respuestas"
    salida="$(python3 "$SCRIPT" menu 2>&1)"; codigo=$?
}
ofrecido() { tr '\0\037' '|#' < "$REGISTRO/ofrecido.$1"; }
# volcar <comando...> — lo deja en un fichero normal e imprime su ruta. Hace
# falta porque afirmar_contiene exige un fichero (`-f`): con un `<(...)`, el
# «no contiene» daria verde sin haber mirado nada.
volcar() { local f; f="$(mktemp "$TMP/volcado.XXXXXX")"; "$@" > "$f"; echo "$f"; }

# --- 1. Se apunta lo que copias -------------------------------------------------

titulo "1. Lo copiado se apunta, sin duplicar"
copiar "hola mundo"
afirmar_igual "1" "$(en "$SESION/historial")" "un texto copiado es una entrada"
copiar "otra cosa"
touch -d '-1 minute' "$SESION"/historial/*   # que «hola mundo» sea el mas viejo
copiar "hola mundo"
afirmar_igual "2" "$(en "$SESION/historial")" "copiar otra vez lo mismo no lo duplica"
mas_nuevo="$(ls -t "$SESION/historial" | head -1)"
afirmar_igual "hola mundo" "$(cat "$SESION/historial/$mas_nuevo")" "y lo sube arriba"
afirmar_igual "600" "$(stat -c %a "$SESION/historial/$mas_nuevo")" "solo lo lees tu (600)"

titulo "1b. Una imagen se apunta como imagen"
printf '\x89PNG\r\n\x1a\n\0\0\0\rIHDR\0\0\x05\x56\0\0\x03\0' > "$TMP/contenido"
printf 'image/png\n' > "$TMP/tipos"
printf x | CLIPBOARD_STATE=data python3 "$SCRIPT" recibir
afirmar "queda un .png en el historial" compgen -G "$SESION/historial/*.png"

# --- 2. Lo que NO se apunta -------------------------------------------------------

titulo "2. Lo secreto, lo vacio y lo enorme no se apuntan"
antes="$(en "$SESION/historial")"
ESTADO=sensitive copiar "contraseña1"
copiar "contraseña2" "text/plain" "x-kde-passwordManagerHint"
ESTADO=nil copiar ""
copiar "   "
afirmar_igual "$antes" "$(en "$SESION/historial")" "nada de eso entra en el historial"
afirmar_no_contiene "$(volcar contenido_de "$SESION/historial")" "contraseña" "ni rastro de las contraseñas"
mkdir -p "$XDG_CONFIG_HOME/celiuz"
echo "max_mb = 0.001" > "$XDG_CONFIG_HOME/celiuz/portapapeles.conf"
copiar "$(head -c 5000 /dev/zero | tr '\0' a)"
afirmar_igual "$antes" "$(en "$SESION/historial")" "lo que pesa mas de max_mb tampoco"
rm "$XDG_CONFIG_HOME/celiuz/portapapeles.conf"

# --- 3. Se olvida solo ------------------------------------------------------------

titulo "3. El historial se olvida por edad y por cantidad"
touch -d '-25 hours' "$SESION/historial/$mas_nuevo"
copiar "reciente"
afirmar_no_contiene "$(volcar contenido_de "$SESION/historial")" "hola mundo" "lo de hace 25 h se olvida (24 de fabrica)"
echo "maximo = 3" > "$XDG_CONFIG_HOME/celiuz/portapapeles.conf"
for i in 1 2 3 4 5; do copiar "cosa $i"; touch -d "-$((10 - i)) seconds" "$SESION"/historial/*; done
afirmar_igual "3" "$(en "$SESION/historial")" "con maximo = 3 quedan 3"
afirmar_contiene "$(volcar contenido_de "$SESION/historial")" "cosa 5" "y son las mas nuevas"
rm "$XDG_CONFIG_HOME/celiuz/portapapeles.conf"

# --- 4. El menu -------------------------------------------------------------------

python3 "$SCRIPT" vaciar
afirmar_igual "0" "$(en "$SESION/historial")" "vaciar deja el historial a cero"
copiar "primero"; touch -d '-3 seconds' "$SESION"/historial/*
copiar "segundo"; touch -d '-2 seconds' "$(ls -t "$SESION"/historial/* | head -1)"
copiar "tercero"

titulo "4. Enter copia lo elegido"
menu "0 1"
afirmar_igual "0" "$codigo" "el menu termina bien"
afirmar_igual "" "$salida" "sin nada por stderr"
afirmar_contiene "$REGISTRO/ofrecido.1" "tercero" "lo mas nuevo sale el primero"
afirmar_igual "segundo" "$(cat "$REGISTRO/copiado" 2>/dev/null)" "se copia la segunda fila"
afirmar_no_contiene "$REGISTRO/wl-copy.log" "--type" "un texto va sin tipo (wl-copy ofrece todos los de texto)"
afirmar_contiene "$REGISTRO/fuzzel.log" "Ctrl\+F fija" "la ayuda de las teclas va en la caja"

titulo "4b. Ctrl+F fija: sale arriba con su marca, y otra vez lo desfija"
menu "10 2" "1"   # fijar «primero» (tercera fila) y cancelar
afirmar_igual "1" "$(en "$SESION/fijados")" "queda un fijado"
afirmar_igual "2" "$(veces_llamado fuzzel)" "el menu se vuelve a abrir tras fijar"
primera="$(ofrecido 2 | head -1)"
afirmar "y en la segunda vuelta el fijado es la primera fila" grep -q "󰐃.*primero" <<< "$primera"
afirmar_igual "1" "$(ofrecido 2 | grep -c primero)" "sin repetirse en el historial"
afirmar_contiene "$REGISTRO/fuzzel.log" "select-index 0" "y el cursor le sigue arriba"
menu "10 0" "1"   # desfijar
afirmar_igual "0" "$(en "$SESION/fijados")" "Ctrl+F sobre un fijado lo desfija"

titulo "4c. Ctrl+G guarda en disco, y otra vez lo quita"
menu "11 0" "1"
afirmar_igual "1" "$(en "$GUARDADOS")" "queda un guardado"
afirmar_contiene "$(volcar contenido_de "$GUARDADOS")" "tercero" "es lo elegido"
afirmar "la carpeta de guardados es solo tuya (700)" test "$(stat -c %a "$GUARDADOS")" = 700
menu "11 0" "1"
afirmar_igual "0" "$(en "$GUARDADOS")" "Ctrl+G sobre un guardado lo quita"

titulo "4d. Ctrl+D borra, de todas las listas"
menu "10 0" "1"; menu "11 0" "1"   # «tercero» fijado y guardado
afirmar_contiene "$REGISTRO/ofrecido.2" "󰐃󰆓" "fijado y guardado sale una vez con las dos marcas"
menu "12 0" "1"
afirmar_igual "0" "$(en "$SESION/fijados")" "ya no esta fijado"
afirmar_igual "0" "$(en "$GUARDADOS")" "ni guardado"
afirmar_no_contiene "$(volcar contenido_de "$SESION/historial")" "tercero" "ni en el historial"
afirmar_contiene "$REGISTRO/notify-send.log" "Borrado de guardados" "y borrar un guardado avisa, porque no vuelve solo"

titulo "4e. Una imagen se copia con su tipo, y lleva miniatura"
printf '\x89PNG\r\n\x1a\n\0\0\0\rIHDR\0\0\x05\x56\0\0\x03\0' > "$TMP/contenido"
printf 'image/png\n' > "$TMP/tipos"
printf x | CLIPBOARD_STATE=data python3 "$SCRIPT" recibir
menu "0 0"
afirmar_contiene "$(volcar ofrecido 1)" "Imagen 1366×768" "la fila dice que es una imagen y sus medidas"
afirmar_contiene "$(volcar ofrecido 1)" "\|icon#/.*\.png" "con la propia imagen de icono"
afirmar_contiene "$REGISTRO/wl-copy.log" "--type image/png" "y se copia como image/png"

titulo "4f. Escape no hace nada"
menu "1"
afirmar_igual "0" "$codigo" "termina bien"
afirmar "no se copia nada" test ! -f "$REGISTRO/copiado"

# --- 5. Fijar es de la sesion; guardar, para siempre -----------------------------

titulo "5. Otra sesion: los fijados no estan, los guardados si"
copiar "de la sesion uno"
menu "10 0" "1"; menu "11 1" "1"   # fija la primera fila, guarda la segunda
afirmar_igual "1" "$(en "$SESION/fijados")" "en la sesion uno hay un fijado"
export HYPRLAND_INSTANCE_SIGNATURE="firma_dos"
menu "1"
afirmar_no_contiene "$(volcar ofrecido 1)" "󰐃" "en la sesion dos no sale ningun fijado"
afirmar_contiene "$(volcar ofrecido 1)" "󰆓" "pero el guardado si"

titulo "5b. Al arrancar se barren las sesiones muertas, no las vivas"
mkdir -p "$XDG_RUNTIME_DIR/celiuz-portapapeles.firma_viva" "$XDG_RUNTIME_DIR/hypr/firma_viva"
python3 - "$XDG_RUNTIME_DIR/hypr/firma_viva/.socket.sock" <<'EOF' &
import socket, sys, time
s = socket.socket(socket.AF_UNIX); s.bind(sys.argv[1]); s.listen(8)
s.settimeout(0.2); fin = time.time() + 20
while time.time() < fin:
    try: s.accept()[0].close()
    except OSError: pass
EOF
VIVO=$!
for _ in $(seq 50); do [ -S "$XDG_RUNTIME_DIR/hypr/firma_viva/.socket.sock" ] && break; sleep 0.1; done
python3 "$SCRIPT" demonio >/dev/null 2>&1 &
DEMONIO=$!
sleep 1
afirmar "la carpeta de la sesion uno (muerta) se borro" test ! -d "$SESION"
afirmar "la de una sesion viva sigue" test -d "$XDG_RUNTIME_DIR/celiuz-portapapeles.firma_viva"
afirmar "la propia existe" test -d "$XDG_RUNTIME_DIR/celiuz-portapapeles.firma_dos"
afirmar_contiene "$REGISTRO/wl-paste.log" "--watch .*portapapeles.py recibir" "y se queda vigilando con wl-paste --watch"

titulo "5c. Uno por sesion"
segundo="$(timeout 5 python3 "$SCRIPT" demonio 2>&1)"; codigo=$?
afirmar_igual "0" "$codigo" "el segundo sale bien (y no se queda colgado)"
afirmar_igual "1" "$(grep -c -- --watch "$REGISTRO/wl-paste.log")" "y no lanza otro wl-paste"
afirmar "--ver dice que hay uno vigilando" grep -q "vigilando:  si" <<< "$(python3 "$SCRIPT" --ver)"
kill "$DEMONIO" "$VIVO" 2>/dev/null; wait 2>/dev/null

titulo "5d. Sin firma no se reclama nada"
mkdir -p "$XDG_RUNTIME_DIR/celiuz-portapapeles.firma_muerta"
( unset HYPRLAND_INSTANCE_SIGNATURE
  python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import importlib.util as u
s = u.spec_from_file_location("p", sys.argv[2]); m = u.module_from_spec(s); s.loader.exec_module(m)
print(m.limpiar_sesiones_muertas())' "$REPO/hypr/scripts" "$SCRIPT" > "$TMP/sin-firma" )
afirmar_igual "[]" "$(cat "$TMP/sin-firma")" "no borra ninguna"
afirmar "la muerta sigue ahi" test -d "$XDG_RUNTIME_DIR/celiuz-portapapeles.firma_muerta"

afirmar_intacta_la_casa_real
resumen
