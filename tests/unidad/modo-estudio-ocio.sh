#!/usr/bin/env bash
# modo-estudio-ocio.sh — el modo estudio aparta el OCIO al escritorio oculto
# (en todas las pantallas) y no toca lo de trabajar. Con hyprctl falso: contra
# el Hyprland de verdad movería las ventanas del usuario.
DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
. "$DIR/../lib/comun.sh"
preparar_entorno

S="$REPO/hypr/scripts"
MODO="$S/modo-estudio.py"
export HYPRLAND_INSTANCE_SIGNATURE=prueba
ESTADO="$XDG_CONFIG_HOME/celiuz/modo-estudio.json"
GANCHOS="$XDG_CONFIG_HOME/celiuz/modo-estudio.d"

# --- Lo que ve el catalogo: un .desktop de ocio y uno de trabajo --------------
mkdir -p "$XDG_DATA_HOME/applications"
cat > "$XDG_DATA_HOME/applications/spotify.desktop" <<'FIN'
[Desktop Entry]
Type=Application
Name=Spotify
Categories=AudioVideo;Player;
FIN
cat > "$XDG_DATA_HOME/applications/code.desktop" <<'FIN'
[Desktop Entry]
Type=Application
Name=Visual Studio Code
Categories=Development;TextEditor;
FIN

# --- Las ventanas abiertas: musica en la pantalla 1, el editor en la 3 ---------
cat > "$TMP/clientes.json" <<FIN
[
  {"address": "0xaaa", "class": "spotify", "initialClass": "spotify", "title": "Spotify", "workspace": {"id": 1, "name": "1"}, "monitor": 0, "mapped": true},
  {"address": "0xbbb", "class": "code", "initialClass": "code", "title": "main.py - Code", "workspace": {"id": 3, "name": "3"}, "monitor": 1, "mapped": true}
]
FIN
cat > "$TMP/monitores.json" <<FIN
[
  {"id": 0, "name": "eDP-1", "focused": true, "activeWorkspace": {"id": 1, "name": "1"}},
  {"id": 1, "name": "HDMI-A-1", "focused": false, "activeWorkspace": {"id": 3, "name": "3"}}
]
FIN
cat > "$TMP/escritorios.json" <<FIN
[
  {"id": 1, "name": "1", "monitor": "eDP-1", "monitorID": 0},
  {"id": 3, "name": "3", "monitor": "HDMI-A-1", "monitorID": 1}
]
FIN
cat > "$TMP/atajos.json" <<FIN
[]
FIN

# --- hyprctl falso: el mismo protocolo que usa modo-programador.sh -------------
binario_falso hyprctl 0 '
case "$1" in
  eval) echo ok ;;
  getoption)
    case "$2" in
      general:col.active_border) echo "{\"option\": \"$2\", \"gradient\": \"ff00ff00 ff00ff00 45deg\", \"set\": true}" ;;
      general:col.inactive_border) echo "{\"option\": \"$2\", \"gradient\": \"ff000000 0deg\", \"set\": true}" ;;
      misc:background_color) echo "{\"option\": \"$2\", \"int\": 4278190080, \"set\": true}" ;;
      misc:force_default_wallpaper) echo "{\"option\": \"$2\", \"int\": -1, \"set\": true}" ;;
      *) echo "{\"option\": \"$2\", \"bool\": false, \"set\": true}" ;;
    esac ;;
  clients) cat "'"$TMP"'/clientes.json" ;;
  monitors) cat "'"$TMP"'/monitores.json" ;;
  workspaces) cat "'"$TMP"'/escritorios.json" ;;
  binds) cat "'"$TMP"'/atajos.json" ;;
  activeworkspace) echo "{\"id\": 3, \"name\": \"3\"}" ;;
  dispatch|keyword) echo ok ;;
  *) echo ok ;;
esac'

# Los avisos: se guardan para poder mirados despues.
binario_falso notify-send 0 'echo "$@" >> "'"$TMP"'/avisos.log"'

# --- Un gancho para ver que corre al entrar y al salir ------------------------
mkdir -p "$GANCHOS"
cat > "$GANCHOS/anotar" <<FIN
#!/usr/bin/env bash
echo "\$1" >> "$TMP/ganchos.log"
FIN
chmod +x "$GANCHOS/anotar"

# --- Entrar: el ocio se aparta, lo de trabajo se queda -----------------------
titulo "Entrar aparta la musica y no toca el editor"
python3 "$MODO" on --sin-preguntar >"$TMP/salida" 2>&1
codigo=$?
afirmar_igual "0" "$codigo" "entra sin preguntar (salida: $(cat "$TMP/salida"))"
afirmar "deja el estado" test -s "$ESTADO"
afirmar "el gancho corrio con on" grep -qx "on" "$TMP/ganchos.log"

movidas="$(grep -c . "$REGISTRO/hyprctl.log" 2>/dev/null || true)"
afirmar "hyprctl se uso" test -n "$movidas"
afirmar "la musica va a un escritorio oculto" \
    bash -c "grep '0xaaa' '$REGISTRO/hyprctl.log' | grep -q 'special:'"
afirmar "el editor no se mueve" \
    bash -c "! grep '0xbbb' '$REGISTRO/hyprctl.log' | grep -q 'special:'"
afirmar "avisa y anima" grep -qi "animo" "$TMP/avisos.log"

# --- Salir: el estado se apaga y el gancho recibe off ------------------------
titulo "Salir apaga y avisa a los ganchos"
python3 "$MODO" off --sin-preguntar >"$TMP/salida" 2>&1
codigo=$?
afirmar_igual "0" "$codigo" "sale sin preguntar (salida: $(cat "$TMP/salida"))"
afirmar "el gancho corrio con off" grep -qx "off" "$TMP/ganchos.log"
python3 "$MODO" estado >/dev/null 2>&1
codigo=$?
afirmar_igual "1" "$codigo" "ya no esta puesto"

# --- Los tres modos no se juntan ---------------------------------------------
titulo "Con el modo gaming puesto no entra"
rm -f "$ESTADO"
printf '{"activo": true}' > "$XDG_RUNTIME_DIR/modo-gaming.prueba.json"
python3 "$MODO" on --sin-preguntar >"$TMP/salida" 2>&1
codigo=$?
afirmar "sale con error" test "$codigo" -ne 0
afirmar "lo dice" grep -qi "gaming" "$TMP/salida"
afirmar "no queda estado" test ! -e "$ESTADO"
