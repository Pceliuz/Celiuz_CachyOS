#!/usr/bin/env bash
# tests/unidad/modo-gaming.sh — entrar y salir del modo gaming sin compositor.
#
# LO QUE VIGILA:
#  - Solo se cierran las ventanas que no son juego, lanzador, app permitida,
#    terminal ni pantalla completa. Y se cierran PIDIÉNDOLO (window.close), no
#    matando.
#  - Los efectos se apagan y al salir vuelven a lo que había, no a «true».
#  - El «no molestar» solo se quita al salir si lo puso el modo.
#  - Las órdenes llegan a los FIFO de las barras y del fondo, y si un FIFO no
#    existe NO se crea un fichero normal en su lugar (la trampa del CLAUDE.md).
#  - Los ganchos reciben on y off.
#  - SIN TARJETA NO SE HACE NADA: el atajo sin pantalla donde preguntar no
#    puede cerrarte las ventanas.
#  - El estado lleva la firma de la sesión.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

MODO="$REPO/hypr/scripts/modo-gaming.py"
export HYPRLAND_INSTANCE_SIGNATURE=prueba
ESTADO="$XDG_RUNTIME_DIR/modo-gaming.prueba.json"
export XDG_DATA_DIRS="$TMP/sistema"
mkdir -p "$TMP/sistema/applications" "$XDG_DATA_HOME/applications" "$XDG_CONFIG_HOME/celiuz/modo-gaming.d"

# --- El mundo de mentira ------------------------------------------------------
cat > "$TMP/clientes.json" <<'EOF'
[
 {"address": "0xa1", "workspace": {"id": 2, "name": "2"}, "class": "brave-browser", "title": "WhatsApp", "pid": 0, "mapped": true, "fullscreen": 0},
 {"address": "0xa2", "workspace": {"id": 3, "name": "3"}, "class": "kitty", "title": "zsh", "pid": 0, "mapped": true, "fullscreen": 0},
 {"address": "0xa3", "workspace": {"id": 1, "name": "1"}, "class": "steam", "title": "Steam", "pid": 0, "mapped": true, "fullscreen": 0},
 {"address": "0xa4", "workspace": {"id": 1, "name": "1"}, "class": "org.kde.dolphin", "title": "Archivos", "pid": 0, "mapped": true, "fullscreen": 0},
 {"address": "0xa5", "workspace": {"id": 4, "name": "4"}, "class": "juego-raro", "title": "Juego", "pid": 0, "mapped": true, "fullscreen": 2},
 {"address": "0xa6", "workspace": {"id": 5, "name": "5"}, "class": "mi-musica", "title": "Música", "pid": 0, "mapped": true, "fullscreen": 0},
 {"address": "0xa8", "workspace": {"id": 3, "name": "3"}, "class": "celiuz-video", "title": "Modo gaming", "pid": 0, "mapped": true, "fullscreen": 0},
 {"address": "0xa9", "workspace": {"id": 5, "name": "5"}, "class": "nankill.xyz.glassymusic.mod", "title": "Glassy", "pid": 0, "mapped": true, "fullscreen": 0},
 {"address": "0xa7", "workspace": {"id": 6, "name": "6"}, "class": "obsidian", "title": "Notas", "pid": 0, "mapped": true, "fullscreen": 0}
]
EOF
# hyprctl en modo Lua: getoption contesta lo que haya en $TMP/opciones/<clave>.
mkdir -p "$TMP/opciones"
printf 'true'  > "$TMP/opciones/decoration:blur:enabled"
printf 'false' > "$TMP/opciones/decoration:shadow:enabled"
printf 'true'  > "$TMP/opciones/animations:enabled"
binario_falso hyprctl 0 '
case "$1" in
  eval) [ "$2" = "return 1" ] && echo ok || echo ok ;;
  getoption) printf "{\"option\": \"%s\", \"bool\": %s, \"set\": true}\n" "$2" "$(cat "'"$TMP"'/opciones/$2")" ;;
  clients) cat "'"$TMP"'/clientes.json" ;;
  activeworkspace) echo "{\"id\": 3, \"name\": \"3\"}" ;;
  dispatch) echo ok ;;
esac'
# makoctl: `mode` lista los modos de $TMP/modos; -a y -r los cambian.
printf 'default\n' > "$TMP/modos"
binario_falso makoctl 0 '
if [ "$1" = mode ] && [ "$2" = "-a" ]; then echo "$3" >> "'"$TMP"'/modos"
elif [ "$1" = mode ] && [ "$2" = "-r" ]; then grep -vx "$3" "'"$TMP"'/modos" > "'"$TMP"'/m2"; mv "'"$TMP"'/m2" "'"$TMP"'/modos"
elif [ "$1" = mode ]; then cat "'"$TMP"'/modos"; fi'
# uwsm apunta tambien con que entorno le llegó (el overlay).
binario_falso uwsm 0 'printf "MANGOHUD=%s CONF=%s\n" "$MANGOHUD" "$MANGOHUD_CONFIGFILE" >> "'"$REGISTRO"'/uwsm-entorno.log"'
# Un Steam falso: `preparar-steam` le habla. El de verdad del usuario corre con
# OTRA casa y modo-gaming.py no lo reclama (ver pids_de()).
binario_falso steam
# El navegador predeterminado y una app añadida por el usuario.
printf '[Desktop Entry]\nType=Application\nName=Brave\nExec=brave %%U\nIcon=brave-desktop\n' \
    > "$TMP/sistema/applications/brave-browser.desktop"
binario_falso brave
binario_falso xdg-settings 0 'echo brave-browser.desktop'
cat > "$XDG_CONFIG_HOME/celiuz/modo-gaming.json" <<'EOF'
{"apps": [{"label": "Mi música", "cmd": "mi-musica", "icon_name": "mi-musica"},
          {"label": "Glassy Music", "cmd": "glassy-music", "icon_name": "glassy-music-nankill-mod"}]}
EOF
printf '#!/bin/sh\necho "$1" >> "%s/ganchos.log"\n' "$TMP" > "$XDG_CONFIG_HOME/celiuz/modo-gaming.d/10-prueba"
chmod +x "$XDG_CONFIG_HOME/celiuz/modo-gaming.d/10-prueba"
printf 'no soy ejecutable\n' > "$XDG_CONFIG_HOME/celiuz/modo-gaming.d/20-sin-permiso"

# Un Steam de mentira (su carpeta), para lo que preparar-steam le toca con
# Steam cerrado: el procesado de shaders de fondo, los hilos y la cola.
STEAMD="$HOME/.local/share/Steam"
mkdir -p "$STEAMD/steamapps" "$STEAMD/config"
cat > "$STEAMD/config/config.vdf" <<'EOF'
"InstallConfigStore"
{
	"Software"
	{
		"Valve"
		{
			"Steam"
			{
				"ShaderCacheManager"
				{
					"HasCurrentBucket"		"1"
					"ProcessingQueue"		"431960;1593500;550;"
				}
			}
		}
	}
}
EOF
printf '"AppState"\n{\n\t"appid"\t\t"550"\n\t"name"\t\t"Left 4 Dead 2"\n\t"StateFlags"\t\t"4"\n\t"LastPlayed"\t\t"1790000000"\n}\n' > "$STEAMD/steamapps/appmanifest_550.acf"

# Los FIFO de los dos demonios, con un lector que los tiene abiertos (como el
# demonio de verdad, que los abre O_RDWR).
BARRAS="$XDG_RUNTIME_DIR/waybar-autohide.prueba.fifo"
mkfifo "$BARRAS"
exec 3<>"$BARRAS"
FONDO="$XDG_RUNTIME_DIR/wallpaper-pause.prueba.fifo"

leer_fifo() { local l; read -r -t 1 -u 3 l && printf '%s' "$l"; }

# --- Sin tarjeta no se hace nada ------------------------------------------------
titulo "Sin pantalla donde preguntar"
python3 "$MODO" toggle >"$TMP/salida" 2>&1; codigo=$?
afirmar "sale con error" test "$codigo" -ne 0
afirmar "no queda estado" test ! -e "$ESTADO"
afirmar "no se cerró nada" test ! -s "$REGISTRO/hyprctl.log" -o -z "$(grep dispatch "$REGISTRO/hyprctl.log")"
afirmar "no se tocó mako" test -z "$(grep -- '-a' "$REGISTRO/makoctl.log" 2>/dev/null)"

# --- Entrar ---------------------------------------------------------------------
titulo "Entrar"
: > "$REGISTRO/hyprctl.log"
python3 "$MODO" on --sin-preguntar >"$TMP/salida" 2>"$TMP/err"; codigo=$?
afirmar "sale con 0" test "$codigo" -eq 0
afirmar "sin nada en stderr" test ! -s "$TMP/err"
afirmar "el estado lleva la firma" test -s "$ESTADO"
afirmar_contiene "$REGISTRO/hyprctl.log" 'dispatch hl.dsp.window.close\(\{ window = "address:0xa4" \}\)' "cierra Dolphin, pidiéndolo"
afirmar_contiene "$REGISTRO/hyprctl.log" 'address:0xa7' "cierra Obsidian"
for dir_ in 0xa1:navegador 0xa2:terminal 0xa3:Steam 0xa5:"pantalla completa" 0xa6:"app del usuario"; do
    afirmar_no_contiene "$REGISTRO/hyprctl.log" "close.*address:${dir_%%:*}" "deja ${dir_#*:}"
done
afirmar_no_contiene "$REGISTRO/hyprctl.log" "window.kill" "no mata nada"
afirmar_no_contiene "$REGISTRO/hyprctl.log" "address:0xa8" "no cierra ni esconde el video del propio modo"
oculta() { grep -F "workspace = \"special:modo-gaming\", window = \"address:$1\", follow = false" "$REGISTRO/hyprctl.log" >/dev/null; }
afirmar "la terminal se guarda en el escritorio oculto" oculta 0xa2
afirmar "el navegador también" oculta 0xa1
afirmar "la ventana principal de Steam también" oculta 0xa3
afirmar "la app del usuario también" oculta 0xa6
afirmar_no_contiene "$REGISTRO/hyprctl.log" 'close.*address:0xa9' "Glassy Music NO se cierra (se lanza «glassy-music», su clase es «nankill.xyz.glassymusic.mod»)"
afirmar "lo que está a pantalla completa (no es un juego) también" oculta 0xa5
guardada() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["guardadas"].get(sys.argv[2]))' "$ESTADO" "$1"; }
afirmar_igual "3" "$(guardada 0xa2)" "apunta en qué escritorio estaba cada una (la terminal, en el 3)"
afirmar_igual "2" "$(guardada 0xa1)" "(el navegador, en el 2)"
afirmar_contiene "$REGISTRO/hyprctl.log" 'hl.dsp.focus\(\{ workspace = 1 \}\)' "te lleva al escritorio 1"
vigilante="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["vigilante"] or "")' "$ESTADO")"
afirmar "arranca el vigilante de ventanas" test -n "$vigilante"
afirmar_igual "3" "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["origen"])' "$ESTADO")" "apunta de qué escritorio venías"
afirmar "genera la config del overlay" test -s "$XDG_CACHE_HOME/celiuz/mangohud.conf"
afirmar_contiene "$XDG_CACHE_HOME/celiuz/mangohud.conf" '^toggle_hud=Delete$' "el overlay se alterna con Supr"
afirmar_contiene "$XDG_CACHE_HOME/celiuz/mangohud.conf" '^no_display$' "y empieza escondido"
afirmar_contiene "$XDG_CACHE_HOME/celiuz/mangohud.conf" '^position=top-center$' "centrado"
afirmar_contiene "$XDG_CACHE_HOME/celiuz/mangohud.conf" '^horizontal_stretch=0$' "y del ancho de lo que enseña, no de la pantalla"
afirmar_contiene "$REGISTRO/hyprctl.log" 'hl.unbind\("SUPER \+ 3"\); hl.bind\("SUPER \+ 3", hl.dsp.exec_cmd\(".*modo-gaming.py ir 3"\)' "SUPER+3 pasa por «ir 3» (no va a uno vacío)"
steam_preparado() { grep -q '"EnableShaderBackgroundProcessing"' "$STEAMD/config/config.vdf" 2>/dev/null; }
esperar_prep() { for _ in $(seq 30); do steam_preparado && return 0; sleep 0.1; done; return 1; }
afirmar "enciende el procesado de shaders de fondo de Steam" esperar_prep
afirmar_contiene "$STEAMD/config/config.vdf" '^	{5}"EnableShaderBackgroundProcessing"		"1"$' "dentro de su bloque, con su sangría"
afirmar_contiene "$STEAMD/config/config.vdf" '"ProcessingQueue"		"550;431960;1593500;"' "y pone primero en la cola el último jugado"
afirmar_contiene "$STEAMD/steam_dev.cfg" '^unShaderBackgroundProcessingThreads [0-9]+$' "con más hilos"
steam_lanzado() { grep -q "app -- steam -silent" "$REGISTRO/uwsm.log" 2>/dev/null; }
esperar_steam() { for _ in $(seq 30); do steam_lanzado && return 0; sleep 0.1; done; return 1; }
afirmar "arranca Steam en la bandeja" esperar_steam
afirmar_contiene "$REGISTRO/uwsm-entorno.log" "MANGOHUD=1 CONF=$XDG_CACHE_HOME/celiuz/mangohud.conf" "y con el overlay puesto"
afirmar "no le manda -shutdown a ningún Steam (no había ninguno de esta casa)" test ! -s "$REGISTRO/steam.log"
afirmar_contiene "$REGISTRO/hyprctl.log" 'eval hl.config\(\{ decoration = \{ blur = \{ enabled = false \} \} \}\)' "apaga el blur (en Lua)"
afirmar_contiene "$REGISTRO/hyprctl.log" 'animations = \{ enabled = false' "apaga las animaciones"
afirmar_contiene "$TMP/modos" '^no-molestar$' "pone el no molestar"
afirmar_igual "gaming-on dock:gaming-on" "$(leer_fifo)" "manda gaming-on a las dos barras"
afirmar "no crea un fichero donde no hay FIFO del fondo" test ! -e "$FONDO"
sleep 0.5
afirmar_igual "on" "$(cat "$TMP/ganchos.log" 2>/dev/null)" "corre el gancho con on"
afirmar_igual "1" "$(python3 -c 'import json,sys; print(int(json.load(open(sys.argv[1]))["activo"]))' "$ESTADO")" "estado activo"

python3 "$MODO" estado >/dev/null; codigo=$?
afirmar "estado sale con 0 si está puesto" test "$codigo" -eq 0

titulo "Ir de un escritorio a otro (lo usa el menú rápido)"
# Como estarían las ventanas a esas alturas: la terminal guardada, y un navegador
# abierto durante el modo en el 2.
python3 - "$TMP/clientes.json" <<'PY2'
import json, sys
d = json.load(open(sys.argv[1]))
for v in d:
    v["workspace"] = {"id": -98, "name": "special:modo-gaming"}
d[0]["workspace"] = {"id": 2, "name": "2"}
d[0]["address"] = "0xb1"
json.dump(d, open(sys.argv[1], "w"))
PY2
: > "$REGISTRO/hyprctl.log"
python3 "$MODO" ir 2 >/dev/null 2>&1; codigo=$?
afirmar "ir 2 sale con 0 (tiene algo)" test "$codigo" -eq 0
afirmar_contiene "$REGISTRO/hyprctl.log" 'hl.dsp.focus\(\{ workspace = 2 \}\)' "e ir 2 enfoca el 2"
: > "$REGISTRO/hyprctl.log"
python3 "$MODO" ir 5 >/dev/null 2>&1; codigo=$?
afirmar "ir a uno vacío sale con 1" test "$codigo" -eq 1
afirmar "y no se mueve de donde está" test -z "$(grep focus "$REGISTRO/hyprctl.log")"
python3 "$MODO" ir 1 >/dev/null 2>&1; codigo=$?
afirmar "al 1 (la biblioteca) siempre se puede" test "$codigo" -eq 0
python3 "$MODO" ir apps >/dev/null 2>&1; codigo=$?
afirmar "un sitio que no es un número sale con 2" test "$codigo" -eq 2

titulo "Con un juego abierto no se sale"
mkdir -p "$TMP/steamapps/common/Juego"
cp "$(command -v sleep)" "$TMP/steamapps/common/Juego/juego"
"$TMP/steamapps/common/Juego/juego" 60 & JUEGO=$!
cp "$TMP/clientes.json" "$TMP/clientes-sin-juego.json"
python3 - "$TMP/clientes.json" "$JUEGO" <<'PY2'
import json, sys
d = json.load(open(sys.argv[1]))
d.append({"address": "0xc1", "workspace": {"id": 1, "name": "1"}, "class": "steam_app_1",
          "title": "Juego", "pid": int(sys.argv[2]), "mapped": True, "fullscreen": 2})
json.dump(d, open(sys.argv[1], "w"))
PY2
python3 "$MODO" off --sin-preguntar >"$TMP/salida" 2>&1; codigo=$?
afirmar "sale con 1" test "$codigo" -eq 1
afirmar "y el modo sigue puesto" test -s "$ESTADO"
afirmar_contiene "$TMP/salida" "guarda la partida" "diciendo por qué"
kill "$JUEGO" 2>/dev/null; wait "$JUEGO" 2>/dev/null
cp "$TMP/clientes-sin-juego.json" "$TMP/clientes.json"

titulo "Salir"
: > "$REGISTRO/hyprctl.log"
python3 "$MODO" off --sin-preguntar >"$TMP/salida" 2>"$TMP/err"; codigo=$?
afirmar "sale con 0" test "$codigo" -eq 0
afirmar "sin nada en stderr" test ! -s "$TMP/err"
afirmar "borra el estado" test ! -e "$ESTADO"
sleep 0.5
afirmar "para el vigilante" test ! -d "/proc/$vigilante"
afirmar_contiene "$REGISTRO/hyprctl.log" 'window.move\(\{ workspace = 3, window = "address:0xa2", follow = false' "la terminal vuelve a SU escritorio (el 3)"
afirmar_contiene "$REGISTRO/hyprctl.log" 'window.move\(\{ workspace = 4, window = "address:0xa5", follow = false' "la de pantalla completa, al suyo (el 4)"
afirmar_contiene "$REGISTRO/hyprctl.log" 'window.close\(\{ window = "address:0xb1" \}\)' "lo abierto DURANTE el modo se cierra al salir (pidiéndolo)"
afirmar_no_contiene "$REGISTRO/hyprctl.log" 'window.close\(\{ window = "address:0xa2" \}\)' "y lo que ya estaba abierto antes, no"
afirmar_contiene "$REGISTRO/hyprctl.log" 'hl.dsp.focus\(\{ workspace = 3 \}\)' "y te devuelve a él"
afirmar_contiene "$REGISTRO/hyprctl.log" 'hl.bind\("SUPER \+ 3", hl.dsp.focus\(\{ workspace = 3 \}\), \{ description = "ir al escritorio 3" \}\)' "SUPER+3 vuelve a ser el de siempre"
afirmar_contiene "$REGISTRO/hyprctl.log" 'blur = \{ enabled = true' "devuelve el blur como estaba (true)"
afirmar_contiene "$REGISTRO/hyprctl.log" 'shadow = \{ enabled = false' "devuelve la sombra como estaba (false)"
afirmar_no_contiene "$TMP/modos" '^no-molestar$' "quita el no molestar que puso"
afirmar_igual "gaming-off dock:gaming-off" "$(leer_fifo)" "manda gaming-off a las barras"
sleep 0.5
afirmar_igual "on off" "$(tr '\n' ' ' < "$TMP/ganchos.log" | sed 's/ $//')" "corre el gancho con off"
python3 "$MODO" estado >/dev/null; codigo=$?
afirmar "estado sale con 1 si no está puesto" test "$codigo" -eq 1
python3 "$MODO" ir apps >/dev/null 2>&1; codigo=$?
afirmar "fuera del modo, ir no hace nada" test "$codigo" -eq 1

# --- Si el no molestar ya estaba puesto ---------------------------------------------
titulo "Si el no molestar ya lo tenías puesto"
printf 'default\nno-molestar\n' > "$TMP/modos"
python3 "$MODO" on --sin-preguntar >/dev/null 2>&1
python3 "$MODO" off --sin-preguntar >/dev/null 2>&1
afirmar_contiene "$TMP/modos" '^no-molestar$' "al salir se queda como estaba"

# --- Otra sesión no ve este modo ------------------------------------------------------
titulo "Otra sesión"
python3 "$MODO" on --sin-preguntar >/dev/null 2>&1
HYPRLAND_INSTANCE_SIGNATURE=otra python3 "$MODO" estado >/dev/null; codigo=$?
afirmar "otra firma no se cree en modo gaming" test "$codigo" -eq 1
python3 "$MODO" off --sin-preguntar >/dev/null 2>&1

exec 3>&-

# Nada grafico se puede haber escapado de la prueba (ver `unset DISPLAY` en
# comun.sh): ni biblioteca ni tarjeta vivas con el HOME de mentira.
escapados=""
for d in /proc/[0-9]*; do
    orden="$(tr '\0' ' ' 2>/dev/null < "$d/cmdline")"
    case "$orden" in *biblioteca.py*|*modo-gaming-tarjeta.py*) ;; *) continue ;; esac
    grep -qz "^HOME=$HOME\$" "$d/environ" 2>/dev/null && escapados="$escapados ${d#/proc/}"
done
afirmar "no queda ninguna ventana de la prueba abierta por ahí" test -z "$escapados"

afirmar_intacta_la_casa_real
resumen
