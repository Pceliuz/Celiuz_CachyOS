#!/usr/bin/env bash
# tests/unidad/catalogo-apps.sh — el catalogo de apps (lib/apps_catalogo.py y lo
# que pone instalar.sh para Celiuz Remoto y la radio).
#
# QUE VIGILA
# ----------
# - Que una app de fuera sin instalar se ensena con su ficha bajada a la cache
#   (solo la ficha y sus imagenes, no el repo), y que una ficha que intenta
#   escribir fuera de la cache no escribe nada.
# - Instalar: clona en ~/.local/share/celiuz/apps/<id>, lanza su instalador,
#   y la parte del sistema pasa por un sudo con -A, con la tarjeta del repo de
#   askpass y el motivo de la ficha. Y que ese sudo lo lanza el INSTALADOR y no
#   el envoltorio (sin terminal, sudo recuerda la contraseña por proceso padre:
#   sin el exec, preguntaria en cada sudo).
# - Version nueva en GitHub: se ve, y «actualizar» la trae y reinstala.
# - Quitar: sistema, usuario, anuncio y la carpeta clonada; pero una app que
#   clonaste TU en otra carpeta no se borra.
# - instalar.sh: --remoto / --remoto-quitar / --remoto-revisar, la radio con
#   --radio-aplica / --radio-elegir, y que la instalacion normal NO pone
#   Celiuz Remoto a quien no lo eligio, pero no se lo quita a quien ya lo tenia.
#
# GitHub es una carpeta (CELIUZ_CATALOGO_GITHUB), sudo y systemctl binarios
# falsos: no sale nada a la red ni se toca el sistema.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
CAT="$REPO/hypr/scripts/lib/apps_catalogo.py"
export CELIUZ_CATALOGO_GITHUB="$TMP/github"
export CELIUZ_APPS_LISTA="$TMP/lista.json"
export GIT_AUTHOR_NAME=prueba GIT_AUTHOR_EMAIL=p@p GIT_COMMITTER_NAME=prueba GIT_COMMITTER_EMAIL=p@p
ANUNCIOS="$XDG_DATA_HOME/celiuz/apps.d"
CLON="$XDG_DATA_HOME/celiuz/apps/app-falsa"
MARCA="$TMP/sistema-puesto"

# sudo falso: apunta sus argumentos, el askpass, el motivo y QUIEN lo lanzo, y
# ejecuta lo que le pidan (sin -A delante).
binario_falso sudo 0 '
{ echo "askpass=$SUDO_ASKPASS"; echo "motivo=$CELIUZ_CLAVE_MOTIVO"
  echo "padre=$(tr "\0" " " < /proc/$PPID/cmdline)"; } >> "$REGISTRO/sudo.entorno"
[ "$1" = -A ] && shift
"$@"; exit $?'
binario_falso systemctl 0
binario_falso update-desktop-database 0
binario_falso gtk-update-icon-cache 0

# --- La app de mentira, en su «GitHub» ---------------------------------------
GH="$TMP/github/prueba/app-falsa"
mkdir -p "$GH/img"
printf '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"/>\n' > "$GH/img/icono.svg"
cat > "$GH/celiuz-app.json" <<'EOF'
{"ficha": 1, "id": "app-falsa", "nombre": "App falsa", "resumen": "r", "descripcion": "d",
 "categoria": "stream", "icono": "img/icono.svg", "capturas": [], "necesita": [],
 "pide_sudo": "para poner la marca del sistema",
 "ordenes": {"instalar": "./instalar.sh", "revisar": "./instalar.sh --revisar",
             "quitar": "./instalar.sh --quitar", "sistema": "./instalar.sh --sistema",
             "sistema_quitar": "./instalar.sh --sistema-quitar"}}
EOF
cat > "$GH/instalar.sh" <<EOF
#!/usr/bin/env bash
echo "\${1:-instalar}" >> "$REGISTRO/app-falsa.log"
case "\${1:-}" in
    --revisar) [ -e "$MARCA" ] || { echo "falta lo del sistema"; exit 1; } ;;
    --sistema) sudo touch "$MARCA" ;;
    --sistema-quitar) sudo rm -f "$MARCA" ;;
    --quitar) rm -f "$ANUNCIOS/app-falsa" ;;
    *) mkdir -p "$ANUNCIOS" && ln -sfn "\$PWD" "$ANUNCIOS/app-falsa"; echo "version \$(cat version)" ;;
esac
EOF
chmod +x "$GH/instalar.sh"
echo 1 > "$GH/version"
git -C "$GH" init -q -b main && git -C "$GH" add -A && git -C "$GH" commit -qm uno
echo '{"apps": [{"id": "app-falsa", "repo": "https://github.com/prueba/app-falsa"}]}' > "$CELIUZ_APPS_LISTA"

estado() { python3 "$CAT" estado "$@" 2>&1 | awk '$1 == "app-falsa" {$1 = $2 = ""; print}' | sed 's/^ *//; s/ *$//'; }

titulo "1. Sin instalar: la ficha se baja a la cache"
afirmar_igual "sin instalar" "$(estado)" "sin red, la ve sin instalar"
salida="$(python3 "$CAT" estado --red 2>&1)"; codigo=$?
afirmar_igual "0" "$codigo" "estado --red no revienta"
afirmar "la ficha llega a la cache" test -f "$XDG_CACHE_HOME/celiuz/catalogo/app-falsa/celiuz-app.json"
afirmar "  y su icono" test -f "$XDG_CACHE_HOME/celiuz/catalogo/app-falsa/img/icono.svg"
afirmar "  y nada mas del repo" test ! -e "$XDG_CACHE_HOME/celiuz/catalogo/app-falsa/instalar.sh"
afirmar "nada clonado aun" test ! -e "$CLON"

# Una ficha de la red que intenta escribir fuera de la cache.
MALA="$TMP/github/prueba/mala"
mkdir -p "$MALA"
echo '{"ficha": 1, "id": "mala", "icono": "../../../../fuera.svg", "capturas": ["/etc/x"]}' > "$MALA/celiuz-app.json"
echo '<svg/>' > "$TMP/fuera.svg"
echo '{"apps": [{"id": "mala", "repo": "https://github.com/prueba/mala"}]}' > "$TMP/lista-mala.json"
CELIUZ_APPS_LISTA="$TMP/lista-mala.json" python3 "$CAT" estado --red >/dev/null 2>&1
afirmar_igual "" "$(find "$XDG_CACHE_HOME" -name 'fuera.svg')" "una ruta con .. en la ficha no escribe fuera"
afirmar "  y una ficha mala no se queda en la cache" test ! -e "$XDG_CACHE_HOME/celiuz/catalogo/mala"

titulo "2. Instalar"
salida="$(python3 "$CAT" instalar app-falsa 2>&1)"; codigo=$?
afirmar_igual "0" "$codigo" "instala"
afirmar "se clona en ~/.local/share/celiuz/apps/app-falsa" test -d "$CLON/.git"
afirmar "se anuncia" test -L "$ANUNCIOS/app-falsa"
afirmar_igual "instalar --sistema" "$(paste -sd' ' "$REGISTRO/app-falsa.log")" \
    "su instalador y despues la parte del sistema"
afirmar "la parte del sistema se puso (por el sudo)" test -e "$MARCA"
afirmar_contiene "$REGISTRO/sudo.log" '^-A touch ' "sudo va con -A (sin terminal, la tarjeta)"
afirmar_contiene "$REGISTRO/sudo.entorno" "^askpass=$REPO/hypr/scripts/pedir-clave.py\$" \
    "el askpass es la tarjeta del repo"
afirmar_contiene "$REGISTRO/sudo.entorno" '^motivo=Para App falsa: para poner la marca del sistema' \
    "la tarjeta dice el motivo de la ficha"
afirmar_contiene "$REGISTRO/sudo.entorno" '^padre=bash \./instalar\.sh --sistema' \
    "a sudo lo lanza el instalador, no el envoltorio (una tarjeta por orden)"
afirmar "el envoltorio no se queda en el runtime" \
    test -z "$(find "$XDG_RUNTIME_DIR" -name 'celiuz-catalogo-*')"
afirmar_igual "instalada" "$(estado)" "ahora sale instalada"

titulo "3. Version nueva"
echo 2 > "$GH/version"
git -C "$GH" commit -qam dos
afirmar_igual "hay versión nueva" "$(estado --red)" "se ve que hay una nueva"
: > "$REGISTRO/app-falsa.log"
salida="$(python3 "$CAT" actualizar app-falsa 2>&1)"; codigo=$?
afirmar_igual "0" "$codigo" "actualiza"
afirmar "  y trae la nueva" grep -q 'version 2' <<< "$salida"
afirmar_igual "instalar" "$(paste -sd' ' "$REGISTRO/app-falsa.log")" \
    "  y pasa su instalador, sin volver a pedir contraseña"
afirmar_igual "instalada" "$(estado --red)" "ya no hay nueva"

titulo "4. Le falta algo"
rm -f "$MARCA"
salida="$(python3 "$CAT" estado --json 2>&1)"
afirmar "revisar dice que le falta algo" grep -q '"estado": "le falta algo"' <<< "$salida"
afirmar "  y que" grep -q 'falta lo del sistema' <<< "$salida"
touch "$MARCA"

titulo "5. Quitar"
: > "$REGISTRO/app-falsa.log"
salida="$(python3 "$CAT" quitar app-falsa 2>&1)"; codigo=$?
afirmar_igual "0" "$codigo" "quita"
afirmar_igual "--sistema-quitar --quitar" "$(paste -sd' ' "$REGISTRO/app-falsa.log")" \
    "primero lo del sistema (aun con el repo ahi), despues lo suyo"
afirmar "lo del sistema se fue" test ! -e "$MARCA"
afirmar "el anuncio se fue" test ! -e "$ANUNCIOS/app-falsa"
afirmar "la carpeta clonada se borra" test ! -e "$CLON"
afirmar_igual "sin instalar" "$(estado)" "vuelve a estar sin instalar"

titulo "6. Una app clonada a mano en otra carpeta"
git clone -q "$GH" "$TMP/mia"
touch "$MARCA"
(cd "$TMP/mia" && ./instalar.sh >/dev/null)
afirmar_igual "instalada" "$(estado)" "se ve instalada (se anuncio sola)"
python3 "$CAT" quitar app-falsa --sin-sistema >/dev/null 2>&1
afirmar "quitarla no borra tu carpeta" test -d "$TMP/mia/.git"
afirmar "  pero si el anuncio" test ! -e "$ANUNCIOS/app-falsa"

titulo "7. instalar.sh: Celiuz Remoto y la radio, desde el catalogo"
unset CELIUZ_APPS_LISTA
afirmar_igual "sin instalar" "$(python3 "$CAT" estado | awk '$1 == "celiuz-remoto" {print $3, $4}')" \
    "Celiuz Remoto no viene puesto"
"$REPO/instalar.sh" --remoto > "$TMP/remoto.out" 2>&1
afirmar "--remoto lo marca como elegido" test -L "$ANUNCIOS/celiuz-remoto"
afirmar "  y deja la orden celiuz-remoto" test -L "$HOME/.local/bin/celiuz-remoto"
afirmar "  y su unidad (COPIADA, no enlazada)" \
    test -f "$HOME/.config/systemd/user/celiuz-remoto.service" -a ! -L "$HOME/.config/systemd/user/celiuz-remoto.service"
afirmar_no_contiene "$REGISTRO/systemctl.log" '(^| )enable .*celiuz-remoto\.service' "  y NO lo enciende"
salida="$("$REPO/instalar.sh" --remoto-revisar 2>&1)"; codigo=$?
afirmar_igual "1" "$codigo" "--remoto-revisar: sin lo del sistema no esta listo"
afirmar "  y lo dice" grep -q 'tras reiniciar' <<< "$salida"
afirmar "  sin colores (lo lee el catalogo)" test -z "$(grep -c $'\033' <<< "$salida" | grep -v '^0$')"
"$REPO/instalar.sh" --remoto-quitar > "$TMP/quitar.out" 2>&1
afirmar "--remoto-quitar le quita la orden" test ! -e "$HOME/.local/bin/celiuz-remoto"
afirmar "  la unidad" test ! -e "$HOME/.config/systemd/user/celiuz-remoto.service"
afirmar "  y el anuncio" test ! -e "$ANUNCIOS/celiuz-remoto"
afirmar_contiene "$REGISTRO/systemctl.log" 'disable --now celiuz-remoto\.service' "  y la apaga"

SYS="$TMP/sys"; mkdir -p "$SYS/bus/pci/drivers" "$SYS/bus/usb/drivers/btusb"
salida="$(CELIUZ_RADIO_SYS="$SYS" "$REPO/instalar.sh" --radio-aplica 2>&1)"; codigo=$?
afirmar_igual "1" "$codigo" "radio: sin wifi rtw88 ni Bluetooth USB no aplica"
CELIUZ_RADIO_SYS="$SYS" "$REPO/instalar.sh" --radio-elegir >/dev/null 2>&1
afirmar "  y no se deja elegir" test ! -e "$ANUNCIOS/radio"
mkdir -p "$SYS/devices/u/1-7:1.0"; ln -s "$SYS/devices/u/1-7:1.0" "$SYS/bus/usb/drivers/btusb/1-7:1.0"
salida="$(CELIUZ_RADIO_SYS="$SYS" "$REPO/instalar.sh" --radio-aplica 2>&1)"; codigo=$?
afirmar_igual "0 este equipo tiene Bluetooth USB" "$codigo $salida" "con Bluetooth USB si aplica, y dice por que"

titulo "8. La instalacion normal: lo opcional no se pone solo"
# Las funciones de instalar.sh, sin ejecutar el final.
cargar() {
    # REPO sale de BASH_SOURCE: desde la copia apuntaria a $TMP.
    sed -n '1,/^# --- Adelante/p' "$REPO/instalar.sh" \
        | sed "s|^REPO=.*|REPO=\"$REPO\"|" > "$TMP/instalar_fn.sh"
    . "$TMP/instalar_fn.sh"
}
rm -rf "$HOME/.local" "$HOME/.config/systemd"
( cargar; CELIUZ_RADIO_SYS="$TMP/sin-sys" apps_opcionales ) > "$TMP/normal.out" 2>&1
afirmar "deja el catalogo a mano (celiuz-catalogo)" test -L "$HOME/.local/bin/celiuz-catalogo"
afirmar "  y en el lanzador" test -L "$XDG_DATA_HOME/applications/celiuz-catalogo.desktop"
afirmar "NO pone Celiuz Remoto a quien no lo eligio" test ! -e "$HOME/.local/bin/celiuz-remoto"
afirmar "  ni lo marca" test ! -e "$ANUNCIOS/celiuz-remoto"
mkdir -p "$HOME/.local/bin"
ln -s "$REPO/remoto/servidor/celiuz-remoto.py" "$HOME/.local/bin/celiuz-remoto"
( cargar; CELIUZ_RADIO_SYS="$TMP/sin-sys" apps_opcionales ) > "$TMP/normal.out" 2>&1
afirmar "a quien ya lo tenia (de antes del catalogo) se le queda" test -L "$ANUNCIOS/celiuz-remoto"
afirmar "  y se le pone al dia" test -f "$HOME/.config/systemd/user/celiuz-remoto.service"
afirmar_contiene "$TMP/normal.out" 'ya estaba instalado' "  y se le dice"

afirmar_intacta_la_casa_real
resumen
