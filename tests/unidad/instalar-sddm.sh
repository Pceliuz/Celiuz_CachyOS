#!/usr/bin/env bash
# tests/unidad/instalar-sddm.sh — la pantalla de inicio de sesion entra en la
# instalacion normal (2026-11-05).
#
# QUE VIGILA
# ----------
# - Que `./instalar.sh` pone el tema de SDDM si falta o si la copia es vieja,
#   y que si ya esta al dia NO pide contraseña.
# - Que la contraseña se pide UNA vez y en el sitio que toca: en la terminal
#   (con un «¿lo hago ahora?» delante), en la tarjeta de pedir-clave.py si no
#   hay terminal pero si sesion grafica (asi la ve quien instala con Claude
#   Code), y en ningun sitio si no hay ninguna de las dos.
# - Que decir que no, o --sin-sddm, deja el resto de la instalacion igual.
# - Que ningun `raiz` va detras de una tuberia: sudo lo veria como otro
#   proceso y volveria a preguntar.
# sudo, sddm y la tarjeta son de mentira: aqui no se pide nada de verdad.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
REAL="$REPO/instalar.sh"

# Un repo minimo: el tema, lo de logind y una tarjeta de mentira que contesta
# lo que haya en $TMP/clave (o «Ahora no» si no hay fichero).
FALSO_REPO="$TMP/repo"
mkdir -p "$FALSO_REPO/sddm" "$FALSO_REPO/sistema/logind" "$FALSO_REPO/hypr/scripts"
cp -r "$REPO/sddm/celiuz" "$FALSO_REPO/sddm/"
cp "$REPO/sistema/logind/celiuz-sin-sak.conf" "$FALSO_REPO/sistema/logind/"
cat > "$FALSO_REPO/hypr/scripts/pedir-clave.py" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$CELIUZ_CLAVE_MOTIVO" >> "$REGISTRO/tarjeta.log"
[ -f "$TMP/clave" ] || exit 1
cat "$TMP/clave"
EOF
chmod +x "$FALSO_REPO/hypr/scripts/pedir-clave.py"

# sudo de mentira: -n contesta lo de $TMP/sudo-n (por defecto, «hace falta
# contraseña»); -A llama a la tarjeta y acepta «bien»; lo demas, lo apunta.
binario_falso sudo 0 '
case "$1" in
    -n) [ -f "'"$TMP"'/sudo-n" ] && exit 0; exit 1 ;;
    -A) [ "$2" = -v ] || exit 0
        [ "$("$SUDO_ASKPASS" "[sudo] contraseña: ")" = bien ] && exit 0; exit 1 ;;
esac'

funciones() {
    local f
    {
        echo 'SUDO_TARJETA=0 SDDM_TITULO=0'
        for f in raiz pedir_permiso sddm_titulo sddm_pendiente sddm_paso; do
            sed -n "/^$f() {/,/^}/p" "$REAL"
        done
    } > "$TMP/funciones.sh"
}
funciones

# cargar — las funciones de verdad, con el resto de instalar.sh de mentira.
cargar() {
    REPO="$FALSO_REPO"
    SOLO_REVISAR=0 SIN_SDDM=0
    SDDM_TEMA="$TMP/tema"
    SDDM_SAK_ORIGEN="$FALSO_REPO/sistema/logind/celiuz-sin-sak.conf"
    SDDM_SAK="$TMP/logind/celiuz-sin-sak.conf"
    SDDM_COMPARTIDA="$TMP/compartida"
    titulo() { :; }; gris() { :; }; hecho() { :; }; aviso() { echo "AVISO $*"; }
    sddm_instalar() { echo INSTALAR; }
    sddm_estado() { echo ESTADO; }
    . "$TMP/funciones.sh"
}

# Un tema instalado igual que el del repo.
tema_al_dia() {
    rm -rf "$TMP/tema" "$TMP/logind" "$TMP/compartida"
    cp -r "$FALSO_REPO/sddm/celiuz" "$TMP/tema"
    mkdir -p "$TMP/logind" "$TMP/compartida"
    cp "$FALSO_REPO/sistema/logind/celiuz-sin-sak.conf" "$TMP/logind/"
}
reiniciar() { rm -f "$REGISTRO"/*.log "$TMP/sudo-n" "$TMP/clave"; }

titulo "1. Cuando hace falta poner el tema"
sddm_pendiente_() { ( cargar; sddm_pendiente; echo $? ); }
# Sin SDDM: un PATH con solo lo que hace falta (el equipo de verdad puede tenerlo).
mkdir -p "$TMP/sin-sddm"
ln -s "$(command -v cmp)" "$TMP/sin-sddm/cmp"
afirmar_igual "1" "$(PATH="$TMP/sin-sddm" sddm_pendiente_)" "sin SDDM en el equipo: nada que poner"
binario_falso sddm 0
rm -rf "$TMP/tema"
afirmar_igual "0" "$(sddm_pendiente_)" "con SDDM y sin el tema: hay que ponerlo"
tema_al_dia
afirmar_igual "1" "$(sddm_pendiente_)" "con la copia igual a la del repo: nada"
echo "// cambiado" >> "$TMP/tema/Main.qml"
afirmar_igual "0" "$(sddm_pendiente_)" "con una copia VIEJA (un git pull con QML nuevo): hay que ponerlo"
tema_al_dia; rm "$TMP/logind/celiuz-sin-sak.conf"
afirmar_igual "0" "$(sddm_pendiente_)" "sin lo de logind: tambien"
tema_al_dia; rmdir "$TMP/compartida"
afirmar_igual "0" "$(sddm_pendiente_)" "sin la carpeta del fondo: tambien"

titulo "2. Donde se pide la contraseña"
permiso() {
    ( cargar; pedir_permiso "la pantalla de inicio"; echo "R=$?|$SUDO_TARJETA"; raiz true ) \
        < /dev/null 2>&1 | sed -n 's/^R=//p'
}
reiniciar; touch "$TMP/sudo-n"
afirmar_igual "0|0" "$(permiso)" "si sudo ya tiene permiso: no se pregunta nada"
afirmar_igual "0" "$(veces_llamado pedir-clave)" "  ni sale la tarjeta"
reiniciar; unset WAYLAND_DISPLAY
afirmar_igual "1|0" "$(permiso)" "sin terminal y sin sesion grafica: no se pide (y se avisa fuera)"
afirmar "  y no se llama a sudo -v" sh -c "! grep -q -- '-v' '$REGISTRO/sudo.log'"
reiniciar; echo bien > "$TMP/clave"
afirmar_igual "0|1" "$(WAYLAND_DISPLAY=wayland-9 permiso)" "sin terminal pero con sesion (Claude Code): en la tarjeta"
afirmar_contiene "$REGISTRO/tarjeta.log" "Para la pantalla de inicio" "  y la tarjeta dice para que es"
afirmar_contiene "$REGISTRO/sudo.log" "^-A true$" "  y lo de root va despues con sudo -A (sin preguntar otra vez)"
reiniciar
afirmar_igual "1|0" "$(WAYLAND_DISPLAY=wayland-9 permiso)" "«Ahora no» en la tarjeta: no hay permiso"
reiniciar; echo mal > "$TMP/clave"
afirmar_igual "1|0" "$(WAYLAND_DISPLAY=wayland-9 permiso)" "una contraseña mala: tampoco"

# Con terminal: la pregunta va en la terminal. `script` le da un pty.
if command -v script >/dev/null 2>&1; then
    cat > "$TMP/tty.sh" <<EOF
. "$TMP/funciones.sh" 2>/dev/null
$(declare -f cargar)
cargar
pedir_permiso "la pantalla de inicio"
echo "codigo=\$?"
EOF
    reiniciar
    salida="$(printf 'n\n' | script -qec "bash '$TMP/tty.sh'" /dev/null 2>&1)"
    afirmar "con terminal, «n»: no hay permiso" grep -q "codigo=1" <<< "$salida"
    afirmar "  pregunta antes de pedir la contraseña" grep -q "¿Lo hago ahora?" <<< "$salida"
    afirmar "  y no llega a pedirla" sh -c "! grep -q -- '^-v' '$REGISTRO/sudo.log' 2>/dev/null"
    reiniciar
    salida="$(printf '\n' | script -qec "bash '$TMP/tty.sh'" /dev/null 2>&1)"
    afirmar "con terminal, Intro (sí por defecto): la pide alli con sudo -v" \
        grep -qx -- "-v" "$REGISTRO/sudo.log"
    afirmar "  y no saca la tarjeta" test "$(veces_llamado tarjeta)" -eq 0
else
    _gris "  (sin script(1): se salta lo de la terminal)"
fi

titulo "3. El paso 8 de la instalacion normal"
paso() { ( cargar; [ -n "${1:-}" ] && eval "$1"; sddm_paso ) < /dev/null 2>&1 | grep -E '^(INSTALAR|ESTADO)$' | tr '\n' ' '; }
rm -rf "$TMP/tema"
reiniciar; echo bien > "$TMP/clave"
afirmar_igual "INSTALAR " "$(WAYLAND_DISPLAY=wayland-9 paso)" "falta el tema y das la contraseña: se instala"
reiniciar
afirmar_igual "ESTADO " "$(WAYLAND_DISPLAY=wayland-9 paso)" "dices que no: se cuenta como esta y se sigue"
reiniciar; echo bien > "$TMP/clave"
afirmar_igual "ESTADO " "$(WAYLAND_DISPLAY=wayland-9 paso 'SIN_SDDM=1')" "--sin-sddm: ni se pregunta"
afirmar_igual "0" "$(veces_llamado tarjeta)" "  (la tarjeta no salio)"
afirmar_igual "ESTADO " "$(WAYLAND_DISPLAY=wayland-9 paso 'SOLO_REVISAR=1')" "--revisar: tampoco"
tema_al_dia; reiniciar; echo bien > "$TMP/clave"
afirmar_igual "ESTADO " "$(WAYLAND_DISPLAY=wayland-9 paso)" "con el tema al dia: no pide contraseña"
afirmar_igual "0" "$(veces_llamado tarjeta)" "  (la tarjeta no salio)"
afirmar "la instalacion normal pasa por sddm_paso" grep -qx '    sddm_paso' "$REAL"

titulo "4. Lo que haria volver a preguntar"
afirmar_igual "" "$(grep -nE '\|[[:space:]]*raiz[[:space:]]' "$REAL" | grep -vE '^[0-9]+:[[:space:]]*#')" \
    "ningun «| raiz»: en una tuberia sudo lo ve como otro proceso"

titulo "5. La tarjeta de verdad"
salida="$(env -u WAYLAND_DISPLAY -u DISPLAY python3 "$REPO/hypr/scripts/pedir-clave.py" 2>/dev/null)"; codigo=$?
afirmar_igual "1|" "$codigo|$salida" "sin sesion grafica: sale con 1 y no imprime nada (sudo no sigue)"
afirmar "es ejecutable (sudo la llama directamente)" test -x "$REPO/hypr/scripts/pedir-clave.py"
ayuda="$(bash "$REAL" --help)"
afirmar "--help explica --sin-sddm" grep -q -- "--sin-sddm" <<< "$ayuda"
afirmar "  y llega hasta la ultima opcion" grep -q -- "--radio-quitar" <<< "$ayuda"

afirmar_intacta_la_casa_real
resumen
