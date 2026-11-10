#!/usr/bin/env bash
# tests/unidad/modo-programador.sh — el modo programador sin compositor.
#
# LO QUE VIGILA:
#  - NO se cierra nada (window.close ni kill): lo que no es de trabajo se
#    guarda en el escritorio oculto apuntando su numero, y al salir vuelve.
#  - Lo de trabajo (editor, navegador, terminal, archivos) no se mueve.
#  - Con dos pantallas, la que no es la de trabajo no se toca (el anime).
#  - Bordes, color de fondo, «no molestar», el dock y SUPER+B cambian al entrar
#    y vuelven a lo que habia al salir (no a un valor de fabrica).
#  - Solo el DOCK se va: la barra de arriba se queda.
#  - Los dos modos no se juntan, en ninguna direccion.
#  - Sin tarjeta no se hace nada.
#  - El catalogo: secciones por categoria y por id, sin juegos ni ajustes del
#    escritorio, la busqueda, y las fijadas del menu (de fabrica y las tuyas).
#  - Las apps de terminal se abren en una terminal; «--pantalla» enfoca antes
#    la otra pantalla.
#  - El inicio y el menu se dibujan (a PNG, sin ventana) sin errores.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

S="$REPO/hypr/scripts"
MODO="$S/modo-programador.py"
export HYPRLAND_INSTANCE_SIGNATURE=prueba
ESTADO="$XDG_RUNTIME_DIR/modo-programador.prueba.json"
export XDG_DATA_DIRS="$TMP/sistema"
APPS="$TMP/sistema/applications"
mkdir -p "$APPS" "$XDG_DATA_HOME/applications" "$XDG_CONFIG_HOME/celiuz/modo-programador.d"
# Un tema de iconos vacio: sin ninguno, GTK se queja por stderr de cada icono
# que no encuentra (y aqui no hay ninguno: XDG_DATA_DIRS es solo lo de mentira).
mkdir -p "$TMP/sistema/icons/hicolor"
printf '[Icon Theme]\nName=Hicolor\nDirectories=\n' > "$TMP/sistema/icons/hicolor/index.theme"

escritorio() {   # escritorio <id> <Name> <Exec> <Categories> [extra]
    printf '[Desktop Entry]\nType=Application\nName=%s\nExec=%s\nIcon=%s\nCategories=%s\n%s' \
        "$2" "$3" "$1" "$4" "${5:-}" > "$APPS/$1.desktop"
}
escritorio code "Visual Studio Code" "code %F" "Development;IDE;" "StartupWMClass=Code
"
escritorio org.kde.dolphin "Dolphin" "dolphin %u" "Qt;KDE;System;FileTools;FileManager;"
escritorio brave-browser "Brave" "brave %U" "Network;WebBrowser;"
escritorio org.wireshark.Wireshark "Wireshark" "wireshark %f" "Network;Monitor;Qt;"
escritorio onlyoffice-desktopeditors "ONLYOFFICE" "onlyoffice-desktopeditors %U" "Office;WordProcessor;"
escritorio glassy-music "Glassy Music" "glassy-music" "AudioVideo;Audio;Player;"
escritorio btop "btop++" "btop" "System;Monitor;ConsoleOnly;" "Terminal=true
"
escritorio hades "Hades" "steam steam://rungameid/1145360" "Game;"
escritorio soulframe "Soulframe" "soulframe" "Game;"
escritorio cachyos-hello "CachyOS Hello" "cachyos-hello" "GTK;System;"
escritorio nwg-look "GTK Settings" "nwg-look" "GTK;Settings;DesktopSettings;"
escritorio steam "Steam" "steam %U" "Network;FileTransfer;Game;"
binario_falso xdg-settings 0 'echo brave-browser.desktop'
for b in brave code dolphin wireshark btop glassy-music; do binario_falso "$b"; done
binario_falso notify-send            # nada de avisos a la sesion de verdad
binario_falso uwsm

# --- El mundo de mentira ------------------------------------------------------
# Dos pantallas: HDMI-A-1 (la de trabajo, enfocada: escritorios 1-5) y HDMI-A-2
# (escritorio 6, el anime).
cat > "$TMP/clientes.json" <<'EOF'
[
 {"address": "0xa1", "workspace": {"id": 1, "name": "1"}, "monitor": 0, "class": "code", "title": "main.py", "pid": 0, "mapped": true},
 {"address": "0xa2", "workspace": {"id": 2, "name": "2"}, "monitor": 0, "class": "brave-browser", "title": "Docs", "pid": 0, "mapped": true},
 {"address": "0xa3", "workspace": {"id": 3, "name": "3"}, "monitor": 0, "class": "kitty", "title": "zsh", "pid": 0, "mapped": true},
 {"address": "0xa4", "workspace": {"id": 4, "name": "4"}, "monitor": 0, "class": "steam", "title": "Steam", "pid": 0, "mapped": true},
 {"address": "0xa5", "workspace": {"id": 5, "name": "5"}, "monitor": 0, "class": "juego-raro", "title": "Juego", "pid": 0, "mapped": true},
 {"address": "0xa6", "workspace": {"id": 3, "name": "3"}, "monitor": 0, "class": "org.kde.dolphin", "title": "Archivos", "pid": 0, "mapped": true},
 {"address": "0xa7", "workspace": {"id": 6, "name": "6"}, "monitor": 1, "class": "anime-player", "title": "Anime", "pid": 0, "mapped": true},
 {"address": "0xa8", "workspace": {"id": 2, "name": "2"}, "monitor": 0, "class": "Code", "title": "otra", "pid": 0, "mapped": true}
]
EOF
cat > "$TMP/monitores.json" <<'EOF'
[{"id": 0, "name": "HDMI-A-1", "focused": true}, {"id": 1, "name": "HDMI-A-2", "focused": false}]
EOF
cat > "$TMP/escritorios.json" <<'EOF'
[{"id": 1, "monitor": "HDMI-A-1"}, {"id": 2, "monitor": "HDMI-A-1"}, {"id": 3, "monitor": "HDMI-A-1"},
 {"id": 4, "monitor": "HDMI-A-1"}, {"id": 5, "monitor": "HDMI-A-1"}, {"id": 6, "monitor": "HDMI-A-2"}]
EOF
cat > "$TMP/atajos.json" <<'EOF'
[{"modmask": 64, "key": "B", "submap": "", "dispatcher": "__lua", "arg": "16", "description": "pkill fuzzel || fuzzel"}]
EOF
# getoption: un borde violeta con degradado, el inactivo de un color, el logo
# apagado y el fondo negro (como en la sesion del autor).
binario_falso hyprctl 0 '
case "$1" in
  eval) echo ok ;;
  getoption)
    case "$2" in
      general:col.active_border) echo "{\"option\": \"$2\", \"gradient\": \"ff6a00f4 ffb16cff 45deg\", \"set\": true}" ;;
      general:col.inactive_border) echo "{\"option\": \"$2\", \"gradient\": \"ff2d1b4e 0deg\", \"set\": true}" ;;
      misc:background_color) echo "{\"option\": \"$2\", \"int\": 4278190080, \"set\": true}" ;;
      misc:force_default_wallpaper) echo "{\"option\": \"$2\", \"int\": -1, \"set\": true}" ;;
      *) echo "{\"option\": \"$2\", \"bool\": false, \"set\": true}" ;;
    esac ;;
  clients) cat "'"$TMP"'/clientes.json" ;;
  monitors) cat "'"$TMP"'/monitores.json" ;;
  workspaces) cat "'"$TMP"'/escritorios.json" ;;
  binds) cat "'"$TMP"'/atajos.json" ;;
  activeworkspace) echo "{\"id\": 3, \"name\": \"3\"}" ;;
  dispatch) echo ok ;;
esac'
printf 'default\n' > "$TMP/modos"
binario_falso makoctl 0 '
if [ "$1" = mode ] && [ "$2" = "-a" ]; then echo "$3" >> "'"$TMP"'/modos"
elif [ "$1" = mode ] && [ "$2" = "-r" ]; then grep -vx "$3" "'"$TMP"'/modos" > "'"$TMP"'/m2"; mv "'"$TMP"'/m2" "'"$TMP"'/modos"
elif [ "$1" = mode ]; then cat "'"$TMP"'/modos"; fi'
printf '#!/bin/sh\necho "$1" >> "%s/ganchos.log"\n' "$TMP" > "$XDG_CONFIG_HOME/celiuz/modo-programador.d/10-prueba"
chmod +x "$XDG_CONFIG_HOME/celiuz/modo-programador.d/10-prueba"

BARRAS="$XDG_RUNTIME_DIR/waybar-autohide.prueba.fifo"
mkfifo "$BARRAS"
exec 3<>"$BARRAS"
FONDO="$XDG_RUNTIME_DIR/wallpaper-pause.prueba.fifo"
mkfifo "$FONDO"
exec 4<>"$FONDO"
leer_fifo() { local l; read -r -t 1 -u "$1" l && printf '%s' "$l"; }

# --- El catalogo ------------------------------------------------------------------
titulo "Qué apps salen, y dónde"
seccion_de() {
    python3 -c "
import sys; sys.path.insert(0, '$S/lib'); import programador as p
print(next((a['seccion'] for a in p.apps_de_trabajo() if a['nombre'] == sys.argv[1]), '-'))" "$1"
}
afirmar_igual "codigo" "$(seccion_de 'Visual Studio Code')" "VS Code, en código"
afirmar_igual "seguridad" "$(seccion_de Wireshark)" "Wireshark (se dice Network) en seguridad, por su id"
afirmar_igual "sistemas" "$(seccion_de Dolphin)" "Dolphin, en sistemas"
afirmar_igual "documentos" "$(seccion_de ONLYOFFICE)" "OnlyOffice, en documentos"
afirmar_igual "web" "$(seccion_de Brave)" "el navegador, en web"
afirmar_igual "web" "$(seccion_de 'Glassy Music')" "la música, en web"
afirmar_igual "sistemas" "$(seccion_de 'btop++')" "btop, en sistemas"
for nada in Hades Soulframe Steam "CachyOS Hello" "GTK Settings"; do
    afirmar_igual "-" "$(seccion_de "$nada")" "$nada no sale"
done
terminal_de() {
    python3 -c "
import sys; sys.path.insert(0, '$S/lib'); import programador as p
print(next((a['terminal'] for a in p.apps_de_trabajo() if a['nombre'] == sys.argv[1]), '-'))" "$1"
}
afirmar_igual "True" "$(terminal_de 'btop++')" "btop se abre en una terminal (Terminal=true)"
busca() {
    python3 -c "
import sys; sys.path.insert(0, '$S/lib'); import programador as p
print(','.join(a['nombre'] for a in p.buscar(p.apps_de_trabajo(), sys.argv[1])))" "$1"
}
afirmar_igual "Wireshark" "$(busca wire)" "buscar «wire» da Wireshark"
afirmar_igual "Visual Studio Code" "$(busca 'vsc')" "y las letras en orden valen (vsc)"
fijadas() {
    python3 -c "
import sys; sys.path.insert(0, '$S/lib'); import programador as p
print(','.join(a['nombre'] for a in p.favoritas()))"
}
afirmar_igual "Brave,Dolphin,Visual Studio Code,ONLYOFFICE,Glassy Music" "$(fijadas)" \
    "las fijadas de fábrica: navegador, archivos, editor, oficina y música"
python3 -c "import sys; sys.path.insert(0, '$S/lib'); import programador as p; p.desfijar('desktop:org.kde.dolphin'); p.fijar('desktop:org.wireshark.Wireshark')"
afirmar_igual "Brave,Visual Studio Code,ONLYOFFICE,Glassy Music,Wireshark" "$(fijadas)" "quitar y fijar se guardan, en orden"

# --- Sin tarjeta no se hace nada ----------------------------------------------------
titulo "Sin pantalla donde preguntar"
python3 "$MODO" toggle >"$TMP/salida" 2>&1; codigo=$?
afirmar "sale con error" test "$codigo" -ne 0
afirmar "no queda estado" test ! -e "$ESTADO"
afirmar "no se movió nada" test -z "$(grep dispatch "$REGISTRO/hyprctl.log" 2>/dev/null)"

titulo "Con el modo gaming puesto no entra"
printf '{"activo": true}' > "$XDG_RUNTIME_DIR/modo-gaming.prueba.json"
python3 "$MODO" on --sin-preguntar >"$TMP/salida" 2>&1; codigo=$?
afirmar "sale con 1" test "$codigo" -eq 1
afirmar_contiene "$TMP/salida" "modo gaming" "diciendo por qué"
afirmar "y no queda estado" test ! -e "$ESTADO"
rm -f "$XDG_RUNTIME_DIR/modo-gaming.prueba.json"

# --- Entrar -------------------------------------------------------------------------
titulo "Entrar"
: > "$REGISTRO/hyprctl.log"
python3 "$MODO" on --sin-preguntar >"$TMP/salida" 2>"$TMP/err"; codigo=$?
afirmar "sale con 0" test "$codigo" -eq 0
afirmar "sin nada en stderr" test ! -s "$TMP/err"
afirmar "el estado lleva la firma" test -s "$ESTADO"
afirmar_no_contiene "$REGISTRO/hyprctl.log" "window.close" "no cierra NADA"
afirmar_no_contiene "$REGISTRO/hyprctl.log" "window.kill" "ni mata nada"
oculta() { grep -F "workspace = \"special:modo-programador\", window = \"address:$1\", follow = false" "$REGISTRO/hyprctl.log" >/dev/null; }
afirmar "Steam se guarda en el escritorio oculto" oculta 0xa4
afirmar "lo que no es de trabajo, también" oculta 0xa5
for d in 0xa1:VS\ Code 0xa2:el\ navegador 0xa3:la\ terminal 0xa6:Dolphin 0xa8:"otra ventana de Code (clase Code)"; do
    afirmar "${d#*:} se queda donde estaba" sh -c "! grep -qF 'address:${d%%:*}' '$REGISTRO/hyprctl.log'"
done
afirmar "lo de la otra pantalla (el anime) no se toca" sh -c "! grep -qF 'address:0xa7' '$REGISTRO/hyprctl.log'"
guardada() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["guardadas"].get(sys.argv[2]))' "$ESTADO" "$1"; }
afirmar_igual "4" "$(guardada 0xa4)" "apunta en qué escritorio estaba (Steam, en el 4)"
afirmar_igual "HDMI-A-1" "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["pantalla"])' "$ESTADO")" "apunta cuál es la pantalla de trabajo"
afirmar_contiene "$REGISTRO/hyprctl.log" 'active_border = \{ colors = \{ "rgba\(7ee787ff\)", "rgba\(56d4ddff\)" \}, angle = 45' "el borde, verde a cian"
afirmar_contiene "$REGISTRO/hyprctl.log" 'misc = \{ background_color = "rgba\(0b0e14ff\)"' "el fondo, el del tema"
afirmar_contiene "$TMP/modos" '^no-molestar$' "pone el no molestar"
afirmar_igual "dock:gaming-on" "$(leer_fifo 3)" "a las barras solo les llega lo del DOCK (la de arriba se queda)"
afirmar_igual "gaming-on" "$(leer_fifo 4)" "el fondo en video se va"
afirmar_contiene "$REGISTRO/hyprctl.log" 'hl.unbind\("SUPER \+ B"\); hl.bind\("SUPER \+ B", hl.dsp.exec_cmd\(".*modo-programador.py inicio"\)' "SUPER+B abre el inicio"
afirmar_igual "pkill fuzzel || fuzzel" "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["atajo_inicio"])' "$ESTADO")" "apuntando el de antes"
sleep 0.5
afirmar_igual "on" "$(cat "$TMP/ganchos.log" 2>/dev/null)" "corre el gancho con on"
python3 "$MODO" estado >/dev/null; codigo=$?
afirmar "estado sale con 0" test "$codigo" -eq 0

titulo "Con el modo programador puesto, el gaming no entra"
python3 "$S/modo-gaming.py" on --sin-preguntar >"$TMP/salida" 2>&1; codigo=$?
afirmar "sale con 1" test "$codigo" -eq 1
afirmar_contiene "$TMP/salida" "modo programador" "diciendo por qué"
afirmar "no queda estado del gaming" test ! -e "$XDG_RUNTIME_DIR/modo-gaming.prueba.json"

titulo "Abrir apps"
: > "$REGISTRO/uwsm.log"
python3 "$MODO" lanzar desktop:code >/dev/null 2>&1; codigo=$?
afirmar "lanzar sale con 0" test "$codigo" -eq 0
esperar_log() { for _ in $(seq 30); do grep -q -- "$1" "$REGISTRO/uwsm.log" 2>/dev/null && return 0; sleep 0.1; done; return 1; }
afirmar "VS Code se abre por lanzar.sh (uwsm app)" esperar_log "app -- code"
python3 "$MODO" lanzar desktop:btop >/dev/null 2>&1
afirmar "btop, dentro de una terminal con su clase" esperar_log "prog-term.*btop"
: > "$REGISTRO/hyprctl.log"
python3 "$MODO" lanzar desktop:brave-browser --pantalla HDMI-A-2 >/dev/null 2>&1
afirmar_contiene "$REGISTRO/hyprctl.log" 'hl.dsp.focus\(\{ monitor = "HDMI-A-2" \}\)' "--pantalla enfoca antes la otra pantalla"
python3 "$MODO" lanzar desktop:nada >/dev/null 2>&1; codigo=$?
afirmar "una app que no existe sale con 1" test "$codigo" -eq 1

titulo "Un juego que se abre durante el modo"
python3 - "$S" <<'PY' >"$TMP/salida" 2>&1
import importlib.util, sys
spec = importlib.util.spec_from_file_location("mp", sys.argv[1] + "/modo-programador.py")
mp = importlib.util.module_from_spec(spec); spec.loader.exec_module(mp)
juego = {"address": "0xc1", "workspace": {"id": 3, "name": "3"}, "class": "steam_app_550", "pid": 0}
otra = {"address": "0xc2", "workspace": {"id": 6, "name": "6"}, "class": "steam_app_551", "pid": 0}
app = {"address": "0xc3", "workspace": {"id": 3, "name": "3"}, "class": "gimp", "pid": 0}
print(mp.apartar_si_juego("lua", juego), mp.apartar_si_juego("lua", otra), mp.apartar_si_juego("lua", app))
PY
afirmar_igual "True False False" "$(tail -1 "$TMP/salida")" "se guarda en la pantalla de trabajo, no en la otra, y una app cualquiera se queda"
afirmar_igual "3" "$(guardada 0xc1)" "apuntando su escritorio"
afirmar "y avisa" test -s "$REGISTRO/notify-send.log"

titulo "Se dibujan (a PNG, sin ventana)"
python3 "$S/programador-inicio.py" --png "$TMP/inicio.png" 1366 768 >"$TMP/salida" 2>"$TMP/err"; codigo=$?
afirmar "el inicio sale con 0" test "$codigo" -eq 0
afirmar "sin nada en stderr" test ! -s "$TMP/err"
afirmar "y deja la imagen" test -s "$TMP/inicio.png"
python3 "$S/programador-inicio.py" --png "$TMP/busqueda.png" 1920 1080 --buscar zzz >/dev/null 2>"$TMP/err"; codigo=$?
afirmar "con una búsqueda sin resultados, también" test "$codigo" -eq 0 -a ! -s "$TMP/err"
python3 "$S/programador-menu.py" --png "$TMP/menu.png" 1920 1080 >"$TMP/salida" 2>"$TMP/err"; codigo=$?
afirmar "el menú sale con 0" test "$codigo" -eq 0
afirmar "sin nada en stderr" test ! -s "$TMP/err"

# --- Salir --------------------------------------------------------------------------
titulo "Salir"
# A esas alturas, lo guardado esta en el oculto.
python3 - "$TMP/clientes.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
for v in d:
    if v["address"] in ("0xa4", "0xa5"):
        v["workspace"] = {"id": -98, "name": "special:modo-programador"}
d.append({"address": "0xc1", "workspace": {"id": -98, "name": "special:modo-programador"},
          "monitor": 0, "class": "steam_app_550", "title": "Juego", "pid": 0, "mapped": True})
json.dump(d, open(sys.argv[1], "w"))
PY
vigilante="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["vigilante"] or "")' "$ESTADO")"
: > "$REGISTRO/hyprctl.log"
python3 "$MODO" off --sin-preguntar >"$TMP/salida" 2>"$TMP/err"; codigo=$?
afirmar "sale con 0" test "$codigo" -eq 0
afirmar "sin nada en stderr" test ! -s "$TMP/err"
afirmar "borra el estado" test ! -e "$ESTADO"
afirmar "el vigilante no sigue" test ! -d "/proc/$vigilante"
afirmar_contiene "$REGISTRO/hyprctl.log" 'window.move\(\{ workspace = 4, window = "address:0xa4", follow = false' "Steam vuelve a SU escritorio (el 4)"
afirmar_contiene "$REGISTRO/hyprctl.log" 'window.move\(\{ workspace = 3, window = "address:0xc1", follow = false' "el juego guardado durante el modo, al suyo (el 3)"
afirmar_no_contiene "$REGISTRO/hyprctl.log" "window.close" "y sigue sin cerrar nada"
afirmar_contiene "$REGISTRO/hyprctl.log" 'active_border = \{ colors = \{ "rgba\(6a00f4ff\)", "rgba\(b16cffff\)" \}, angle = 45' "el borde vuelve al que había (no a uno de fábrica)"
afirmar_contiene "$REGISTRO/hyprctl.log" 'inactive_border = \{ colors = \{ "rgba\(2d1b4eff\)" \}, angle = 0' "y el inactivo también"
afirmar_contiene "$REGISTRO/hyprctl.log" 'background_color = 4278190080' "el color de fondo, el de antes"
afirmar_contiene "$REGISTRO/hyprctl.log" 'hl.bind\("SUPER \+ B", hl.dsp.exec_cmd\("pkill fuzzel \|\| fuzzel"\)' "SUPER+B vuelve a ser fuzzel"
afirmar_no_contiene "$TMP/modos" '^no-molestar$' "quita el no molestar que puso"
afirmar_igual "dock:gaming-off" "$(leer_fifo 3)" "el dock vuelve"
afirmar_igual "gaming-off" "$(leer_fifo 4)" "y el fondo"
sleep 0.5
afirmar_igual "on off" "$(tr '\n' ' ' < "$TMP/ganchos.log" | sed 's/ $//')" "corre el gancho con off"
python3 "$MODO" estado >/dev/null; codigo=$?
afirmar "estado sale con 1" test "$codigo" -eq 1

titulo "Si el no molestar ya lo tenías puesto"
printf 'default\nno-molestar\n' > "$TMP/modos"
python3 "$MODO" on --sin-preguntar >/dev/null 2>&1
python3 "$MODO" off --sin-preguntar >/dev/null 2>&1
afirmar_contiene "$TMP/modos" '^no-molestar$' "al salir se queda como estaba"

titulo "Sin FIFO del fondo no se crea un fichero en su lugar"
exec 4>&-
rm -f "$FONDO"
python3 "$MODO" on --sin-preguntar >/dev/null 2>&1
afirmar "no aparece un fichero normal" test ! -e "$FONDO"
python3 "$MODO" off --sin-preguntar >/dev/null 2>&1

exec 3>&-
afirmar_intacta_la_casa_real
resumen
