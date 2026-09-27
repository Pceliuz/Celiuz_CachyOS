#!/usr/bin/env bash
# tests/unidad/catalogo.sh — que la biblioteca del modo gaming sepa qué es un
# juego, qué un lanzador y qué nada, y que el dock deje de enseñar juegos.
#
# LO QUE VIGILA:
#  - Steam mete en su biblioteca cosas que no son juegos: Proton, los runtimes,
#    los redistribuibles y Wallpaper Engine. Lo único que los distingue es el
#    TIPO de su appinfo.vdf (binario). Aquí se fabrica uno de mentira, en el
#    formato v29 medido en la PC del autor, y se comprueba que solo sale el juego.
#  - Si Steam cambia el formato y no se puede leer, Proton y compañía siguen
#    fuera (por nombre).
#  - Las imágenes se encuentran estén sueltas o dentro de una carpeta con nombre
#    de hash, que es como Steam las guarda según el juego.
#  - Los accesos directos que crea Steam no duplican el juego; un flatpak con
#    Categories=Game sí es juego; las herramientas que se apuntan a Game no.
#  - El navegador sale del predeterminado de la máquina, no de uno cableado.
#  - El dock salta los juegos SIN renumerar los botones: el clic derecho sobre
#    el botón N quita la entrada N de dock-apps.json.
#
# Todo en un HOME de mentira: nada de esto mira el Steam de verdad.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

CAT="$REPO/hypr/scripts/lib/catalogo.py"
STEAM="$HOME/.local/share/Steam"
HDD="$TMP/hdd/SteamLibrary"
SISTEMA="$TMP/sistema"
FLATPAK="$HOME/.local/share/flatpak/exports/share"
export XDG_DATA_DIRS="$FLATPAK:$SISTEMA"
mkdir -p "$STEAM/steamapps" "$HDD/steamapps" "$STEAM/config" "$SISTEMA/applications" \
         "$FLATPAK/applications" "$XDG_DATA_HOME/applications" "$XDG_CONFIG_HOME/celiuz"

# --- Un Steam de mentira -----------------------------------------------------
cat > "$STEAM/steamapps/libraryfolders.vdf" <<EOF
"libraryfolders"
{
	"0"
	{
		"path"		"$STEAM"
	}
	"1"
	{
		"path"		"$HDD"
	}
}
EOF

manifiesto() {  # biblioteca appid nombre stateflags [lastplayed]
    cat > "$1/steamapps/appmanifest_$2.acf" <<EOF
"AppState"
{
	"appid"		"$2"
	"name"		"$3"
	"StateFlags"		"$4"
	"LastPlayed"		"${5:-0}"
}
EOF
}
manifiesto "$STEAM" 1593500 "God of War" 4 1789525348
manifiesto "$HDD" 4126040 "Aniimo" 4 1790377545
manifiesto "$HDD" 550 "Left 4 Dead 2" 4
manifiesto "$STEAM" 1493710 "Proton Experimental" 4
manifiesto "$STEAM" 1628350 "Steam Linux Runtime 3.0 (sniper)" 4
manifiesto "$HDD" 431960 "Wallpaper Engine" 4
manifiesto "$HDD" 999999 "Juego a medio bajar" 1026

# appinfo.vdf v29: cabecera, entradas con sus claves como índices de una tabla
# de cadenas que va al final. Los tipos, con las mayúsculas reales de Steam.
python3 - "$STEAM/appcache/appinfo.vdf" <<'PY'
import os, struct, sys
ruta = sys.argv[1]
os.makedirs(os.path.dirname(ruta), exist_ok=True)
tabla = ["appinfo", "common", "type", "name"]
def kv(tipo, nombre):
    b = bytes([0]) + struct.pack("<I", 0)            # appinfo {
    b += bytes([0]) + struct.pack("<I", 1)           #   common {
    b += bytes([1]) + struct.pack("<I", 2) + tipo.encode() + b"\0"
    b += bytes([1]) + struct.pack("<I", 3) + nombre.encode() + b"\0"
    return b + b"\x08\x08\x08"
apps = [(1593500, "Game", "God of War"), (4126040, "Game", "Aniimo"),
        (550, "game", "Left 4 Dead 2"), (1493710, "Tool", "Proton Experimental"),
        (1628350, "Tool", "Steam Linux Runtime"), (431960, "Application", "Wallpaper Engine"),
        (999999, "Game", "Juego a medio bajar")]
cuerpo = b""
for appid, tipo, nombre in apps:
    datos = struct.pack("<IIQ", 2, 0, 0) + b"\0" * 20 + struct.pack("<I", 1) + b"\0" * 20 + kv(tipo, nombre)
    cuerpo += struct.pack("<II", appid, len(datos)) + datos
cuerpo += struct.pack("<I", 0)
inicio = 16 + len(cuerpo)
cadenas = struct.pack("<I", len(tabla)) + b"".join(t.encode() + b"\0" for t in tabla)
with open(ruta, "wb") as fh:
    fh.write(struct.pack("<IIq", 0x07564429, 1, inicio) + cuerpo + cadenas)
PY

# Imágenes: God of War sueltas, Aniimo dentro de carpetas con nombre de hash.
CACHE="$STEAM/appcache/librarycache"
mkdir -p "$CACHE/1593500" "$CACHE/4126040/aaa111" "$CACHE/4126040/bbb222"
touch "$CACHE/1593500/library_600x900.jpg" "$CACHE/1593500/library_hero.jpg" "$CACHE/1593500/logo.png"
touch "$CACHE/4126040/aaa111/library_capsule.jpg" "$CACHE/4126040/bbb222/library_hero.jpg" \
      "$CACHE/4126040/bbb222/logo.png"

# Horas jugadas: de la cuenta con la que se entró la última vez.
cat > "$STEAM/config/loginusers.vdf" <<'EOF'
"users"
{
	"76561197960265829"
	{
		"AccountName"		"otra"
		"MostRecent"		"0"
		"Timestamp"		"1700000000"
	}
	"76561199193830930"
	{
		"AccountName"		"yo"
		"MostRecent"		"1"
		"Timestamp"		"1790369734"
	}
}
EOF
mkdir -p "$STEAM/userdata/1233565202/config"
cat > "$STEAM/userdata/1233565202/config/localconfig.vdf" <<'EOF'
"UserLocalConfigStore"
{
	"Software"
	{
		"Valve"
		{
			"Steam"
			{
				"apps"
				{
					"4126040"
					{
						"LastPlayed"		"1790377545"
						"Playtime"		"2149"
					}
					"1593500"
					{
						"LastPlayed"		"1789525348"
						"Playtime"		"1657"
					}
				}
			}
		}
	}
}
EOF

# --- .desktop de todo tipo -----------------------------------------------------
desktop() {  # carpeta id nombre categorias exec [extra]
    printf '[Desktop Entry]\nType=Application\nName=%s\nCategories=%s\nExec=%s\nIcon=%s\n%s\n' \
        "$3" "$4" "$5" "$2" "${6:-}" > "$1/$2.desktop"
}
desktop "$SISTEMA/applications" steam "Steam" "Network;FileTransfer;Game;" "/usr/bin/steam %U"
desktop "$SISTEMA/applications" com.vysp3r.ProtonPlus "ProtonPlus" "Game;" "protonplus"
desktop "$SISTEMA/applications" antimicro-x "Mapeador" "Game;Utility;" "mapeador"
desktop "$SISTEMA/applications" oculto "Oculto" "Game;" "oculto" "NoDisplay=true"
desktop "$SISTEMA/applications" navegadorx "NavegadorX" "Network;WebBrowser;" "navegadorx %U"
desktop "$XDG_DATA_HOME/applications" "God of War" "God of War" "Game;" "steam steam://rungameid/1593500"
desktop "$XDG_DATA_HOME/applications" soulframe "Soulframe" "Game;" "$HOME/Games/soulframe/soulframe.sh"
desktop "$FLATPAK/applications" com.hypixel.HytaleLauncher "Hytale Launcher" "Game;" \
    "/usr/bin/flatpak run --command=hytale com.hypixel.HytaleLauncher"
desktop "$FLATPAK/applications" com.heroicgameslauncher.hgl "Heroic" "Game;" "heroic"

# El navegador predeterminado de ESTA máquina de mentira.
binario_falso xdg-settings 0 'echo navegadorx.desktop'
binario_falso xdg-mime 0 'echo navegadorx.desktop'
binario_falso navegadorx

cat > "$XDG_CONFIG_HOME/celiuz/modo-gaming.json" <<'EOF'
{
    "apps": [{"label": "Mi música", "cmd": "mi-musica", "icon_name": "mi-musica"}],
    "ocultar": ["steam:550"]
}
EOF

# --- El catálogo -----------------------------------------------------------------
titulo "El catálogo"
python3 "$CAT" --json >"$TMP/cat.json" 2>"$TMP/err"; codigo=$?; json="$(cat "$TMP/cat.json")"
afirmar "sale con 0" test "$codigo" -eq 0
afirmar "sin nada en stderr" test ! -s "$TMP/err"

campo() { python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print($2)" <(printf '%s' "$json"); }

afirmar_igual "Aniimo|God of War|Hytale Launcher|Soulframe" \
    "$(campo x '"|".join(j["nombre"] for j in d["juegos"])')" \
    "juegos, en orden de última vez"
afirmar_no_contiene "$TMP/cat.json" "Proton Experimental" "Proton fuera"
afirmar_no_contiene "$TMP/cat.json" "Steam Linux Runtime" "el runtime fuera"
afirmar_no_contiene "$TMP/cat.json" "Wallpaper Engine" "Wallpaper Engine fuera (es Application)"
afirmar_no_contiene "$TMP/cat.json" "medio bajar" "lo que está a medio bajar fuera"
afirmar_no_contiene "$TMP/cat.json" "Left 4 Dead 2" "lo oculto por el usuario fuera"
afirmar_no_contiene "$TMP/cat.json" "ProtonPlus" "ProtonPlus fuera (herramienta)"
afirmar_no_contiene "$TMP/cat.json" "Mapeador" "Game;Utility fuera"
afirmar_no_contiene "$TMP/cat.json" "Oculto" "NoDisplay fuera"
afirmar_igual "1" "$(campo x 'sum(j["nombre"] == "God of War" for j in d["juegos"])')" \
    "el acceso directo de Steam no duplica el juego"
afirmar_igual "steam steam://rungameid/4126040" "$(campo x 'd["juegos"][0]["cmd"]')" \
    "se lanza por la URL de Steam"
afirmar_igual "2149" "$(campo x 'd["juegos"][0]["jugado"]["minutos"]')" "horas de la cuenta más reciente"
afirmar_igual "library_capsule.jpg" "$(campo x 'd["juegos"][0]["arte"]["caratula"].rsplit("/",1)[1]')" \
    "caratula dentro de una carpeta hash"
afirmar_igual "library_hero.jpg logo.png" "$(campo x '" ".join(d["juegos"][1]["arte"][k].rsplit("/",1)[1] for k in ("fondo","logo"))')" \
    "fondo y logo sueltos"
afirmar_igual "flatpak" "$(campo x 'd["juegos"][2]["origen"]')" \
    "el flatpak sale como flatpak"
afirmar_igual "Heroic|Steam" "$(campo x '"|".join(j["nombre"] for j in d["lanzadores"])')" \
    "lanzadores: Heroic y Steam"
afirmar_igual "NavegadorX|Mi música" "$(campo x '"|".join(j["nombre"] for j in d["apps"])')" \
    "apps: el navegador predeterminado y la del usuario"

# --- Sin poder leer appinfo.vdf ------------------------------------------------------
titulo "Si Steam cambia el formato de appinfo.vdf"
printf 'formato nuevo' > "$STEAM/appcache/appinfo.vdf"
python3 "$CAT" --json >"$TMP/cat.json" 2>"$TMP/err"; codigo=$?; json="$(cat "$TMP/cat.json")"
afirmar "sigue saliendo con 0" test "$codigo" -eq 0
afirmar_contiene "$TMP/cat.json" "God of War" "los juegos siguen"
afirmar_no_contiene "$TMP/cat.json" "Proton Experimental" "Proton sigue fuera, por nombre"
afirmar_no_contiene "$TMP/cat.json" "Steam Linux Runtime" "el runtime sigue fuera, por nombre"

# --- Clase de una orden (lo que pregunta el dock) ---------------------------------------
titulo "La clase de lo que lanza un botón del dock"
afirmar_igual "lanzador" "$(python3 "$CAT" clase steam)" "steam es lanzador"
afirmar_igual "juego" "$(python3 "$CAT" clase 'steam steam://rungameid/1')" "una URL de Steam es juego"
afirmar_igual "juego" "$(python3 "$CAT" clase otra-cosa soulframe)" "por el icono del .desktop"
afirmar_igual "juego" "$(python3 "$CAT" clase "$HOME/Games/soulframe/soulframe.sh")" \
    "por el Exec del .desktop"
afirmar_igual "app" "$(python3 "$CAT" clase navegadorx navegadorx)" "el navegador es app"

# --- El dock sin juegos -------------------------------------------------------------------
titulo "El dock no enseña juegos"
COPIA="$(copiar_repo)"
cat > "$COPIA/waybar/dock-apps.json" <<EOF
{"apps": [
  {"label": "NavegadorX", "cmd": "navegadorx", "icon": "f489"},
  {"label": "Soulframe", "cmd": "$HOME/Games/soulframe/soulframe.sh", "icon_name": "soulframe", "icon": "f489"},
  {"label": "Steam", "cmd": "steam", "icon_name": "steam", "icon": "f489"},
  {"label": "Dios de la guerra", "cmd": "steam steam://rungameid/1593500", "icon": "f489"}
]}
EOF
"$COPIA/hypr/scripts/gen-dock.py" gen --no-reload >/dev/null 2>"$TMP/err"; codigo=$?
afirmar "gen-dock sale con 0" test "$codigo" -eq 0
afirmar_no_contiene "$COPIA/waybar/dock.jsonc" "Soulframe" "sin Soulframe"
afirmar_no_contiene "$COPIA/waybar/dock.jsonc" "Dios de la guerra" "sin el juego de Steam"
afirmar_contiene "$COPIA/waybar/dock.jsonc" '"tooltip-format": "Steam"' "el lanzador se queda"
afirmar_contiene "$COPIA/waybar/dock.jsonc" '"custom/app1": {' "el navegador es app1"
afirmar_contiene "$COPIA/waybar/dock.jsonc" '"custom/app3": {' "Steam sigue siendo app3 (no se renumera)"
afirmar_no_contiene "$COPIA/waybar/dock.jsonc" '"custom/app2"' "no hay botón app2"
afirmar_contiene "$COPIA/waybar/dock.jsonc" "dock-manager.py app3" "el clic derecho de Steam apunta a su entrada"
afirmar_contiene "$COPIA/waybar/dock.jsonc" '"width": 164' "el ancho es de dos botones"
"$COPIA/hypr/scripts/gen-dock.py" list >"$TMP/lista" 2>/dev/null
afirmar_contiene "$TMP/lista" "Soulframe.*JUEGO: sale en el modo gaming" "list dice dónde fue el juego"
afirmar "el juego sigue en dock-apps.json" grep -q Soulframe "$COPIA/waybar/dock-apps.json"

afirmar_intacta_la_casa_real
resumen
