#!/usr/bin/env bash
# ~/dotfiles/instalar.sh
#
# Deja este escritorio funcionando en una maquina nueva. Se puede volver a
# ejecutar cuantas veces haga falta: no repite lo que ya esta hecho.
#
#   ./instalar.sh              instala
#   ./instalar.sh --revisar    solo dice que haria, sin tocar nada
#   ./instalar.sh --dock       solo rehace el dock de esta maquina
#
# POR QUE HACE FALTA UN INSTALADOR Y NO VALEN CUATRO `ln`
# ------------------------------------------------------
# Las instrucciones de antes eran `ln -sfn ~/dotfiles/hypr ~/.config/hypr`, y eso
# NO funciona en una instalacion recien hecha: si ~/.config/hypr ya existe como
# carpeta de verdad —y en CachyOS existe—, ln crea el enlace DENTRO, o sea
# ~/.config/hypr/hypr, y tu configuracion no se despliega. Sin ningun error.
# Peor todavia: la carpeta de CachyOS trae un hyprland.lua, y Hyprland 0.56
# prefiere el .lua antes que el .conf, asi que seguias con la config de fabrica
# creyendo que tenias la tuya.
#
# Aqui se aparta lo que haya, se enlaza limpio y se avisa de donde quedo la copia.

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FECHA="$(date +%Y%m%d-%H%M%S)"
CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}"
DATOS="${XDG_DATA_HOME:-$HOME/.local/share}"

SOLO_REVISAR=0
SOLO_DOCK=0
for arg in "$@"; do
    case "$arg" in
        --revisar|-n) SOLO_REVISAR=1 ;;
        --dock)       SOLO_DOCK=1 ;;
        -h|--help)    sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'; exit 0 ;;
        *) echo "instalar: no entiendo «$arg». Prueba --help" >&2; exit 2 ;;
    esac
done

rojo()  { printf '\033[31m%s\033[0m\n' "$*"; }
verde() { printf '\033[32m%s\033[0m\n' "$*"; }
# Para lo que solo es verdad si de verdad se hizo: en --revisar no se dice
# "hecho" de algo que no se ha tocado.
hecho() { [ "$SOLO_REVISAR" -eq 1 ] || verde "$*"; }
gris()  { printf '\033[90m%s\033[0m\n' "$*"; }
titulo() { printf '\n\033[1m%s\033[0m\n' "$*"; }

AVISOS=()
aviso() { AVISOS+=("$1"); rojo "  ! $1"; }

hacer() {
    # Ejecuta, o solo lo cuenta si es --revisar.
    if [ "$SOLO_REVISAR" -eq 1 ]; then
        gris "  (haria) $*"
        return 0
    fi
    "$@"
}

# --- 1. Dependencias ----------------------------------------------------------
# No se instala nada por cuenta propia: se dice lo que falta y se deja elegir.
# Todo esta en los repos oficiales de CachyOS/Arch; nada viene del AUR.

comprobar_dependencias() {
    titulo "1. Programas necesarios"
    local -A necesarios=(
        [Hyprland]="hyprland"        [waybar]="waybar"
        [fuzzel]="fuzzel"            [hyprlock]="hyprlock"
        [hypridle]="hypridle"        [mpvpaper]="mpvpaper"
        [mako]="mako"                [uwsm]="uwsm"
        [grim]="grim"                [slurp]="slurp"
        [wl-copy]="wl-clipboard"     [ffmpeg]="ffmpeg"
        [notify-send]="libnotify"
    )
    local faltan=()
    for binario in "${!necesarios[@]}"; do
        command -v "$binario" >/dev/null 2>&1 || faltan+=("${necesarios[$binario]}")
    done
    # python-gobject no deja binario: se comprueba importandolo.
    python3 -c "import gi" 2>/dev/null || faltan+=("python-gobject")

    if [ ${#faltan[@]} -eq 0 ]; then
        verde "  todo lo imprescindible esta instalado"
    else
        aviso "faltan paquetes: ${faltan[*]}"
        gris "    sudo pacman -S ${faltan[*]}"
    fi

    # La fuente no es un capricho: sin ella los glifos del dock salen como
    # cuadrados vacios. Se comprueba aparte porque no es un ejecutable.
    #
    # Se guarda la lista en una variable en vez de encadenar `fc-list | grep -q`:
    # con `set -o pipefail`, grep -q cierra la tuberia en cuanto encuentra algo,
    # fc-list muere por SIGPIPE y el pipeline devuelve fallo AUNQUE la fuente
    # estuviera. Daba "falta la fuente" con la fuente instalada.
    local familias
    familias="$(fc-list : family 2>/dev/null || true)"
    case "$familias" in
        *"MesloLGS Nerd Font"*) ;;
        *) aviso "falta la fuente de iconos: sudo pacman -S ttf-meslo-nerd" ;;
    esac
}

# --- 2. Enlaces de configuracion ---------------------------------------------

enlazar() {
    # enlazar <origen-en-el-repo> <destino>
    local origen="$1" destino="$2"

    if [ -L "$destino" ]; then
        if [ "$(readlink -f "$destino")" = "$(readlink -f "$origen")" ]; then
            gris "  ya enlazado: $destino"
            return 0
        fi
        gris "  reemplazando enlace viejo: $destino -> $(readlink "$destino")"
        hacer rm -f "$destino"
    elif [ -e "$destino" ]; then
        # Lo importante de todo el script: NUNCA enlazar sobre una carpeta que
        # existe, o el enlace acaba dentro de ella.
        local copia="$destino.antes-de-dotfiles-$FECHA"
        echo "  aparto lo que habia: $(basename "$destino") -> $(basename "$copia")"
        hacer mv "$destino" "$copia"
        if [ -e "$copia/hyprland.lua" ] || [ -e "$copia/hyprland.conf" ]; then
            aviso "tenias una config de Hyprland en $destino; esta guardada en $copia"
        fi
    fi
    hacer mkdir -p "$(dirname "$destino")"
    hacer ln -s "$origen" "$destino"
    hecho "  enlazado: $destino"
}

desplegar() {
    titulo "2. Configuracion (~/.config)"

    # git guarda el bit de ejecucion, pero se pierde si alguien descarga el repo
    # como .zip desde GitHub en vez de clonarlo. Sin el, los binds y los clics de
    # waybar fallan con "permiso denegado" y, como waybar se traga la salida, no
    # se ve por ningun lado.
    hacer chmod +x "$REPO/instalar.sh" \
                   "$REPO/celiuzpaper/celiuzpaper.py" \
                   "$REPO"/hypr/scripts/*.sh "$REPO"/hypr/scripts/*.py \
                   "$REPO"/waybar/scripts/*.sh

    for pieza in hypr waybar fuzzel mako mpvpaper; do
        enlazar "$REPO/$pieza" "$CONFIG/$pieza"
    done

    # Hyprland 0.56 busca hyprland.lua ANTES que hyprland.conf. Si aparece uno
    # —lo repone cualquier reinstalacion de CachyOS— nuestra config queda
    # ignorada en silencio, con un solo "Lua config not found" de diferencia en
    # el log. Se comprueba siempre, no solo al enlazar.
    if [ -e "$CONFIG/hypr/hyprland.lua" ]; then
        aviso "hay un hyprland.lua en $CONFIG/hypr: Hyprland lo usara EN LUGAR de hyprland.conf"
    fi
}

# --- 3. CeliuzPaper ----------------------------------------------------------

celiuzpaper() {
    titulo "3. CeliuzPaper (selector de fondos)"
    hacer mkdir -p "$HOME/.local/bin" "$DATOS/applications" \
                   "$DATOS/icons/hicolor/scalable/apps"
    enlazar "$REPO/celiuzpaper/celiuzpaper.py"      "$HOME/.local/bin/celiuzpaper"
    enlazar "$REPO/celiuzpaper/celiuzpaper.desktop" "$DATOS/applications/celiuzpaper.desktop"
    enlazar "$REPO/celiuzpaper/celiuzpaper.svg"     "$DATOS/icons/hicolor/scalable/apps/celiuzpaper.svg"

    # El .desktop lanza `celiuzpaper` a secas y eso solo funciona si ~/.local/bin
    # esta en el PATH: las entradas de escritorio no expanden ~ ni $HOME, asi que
    # una ruta absoluta ahi seria la ruta del que hizo el repo (era el fallo:
    # Exec=/home/celiuz/...).
    case ":$PATH:" in
        *":$HOME/.local/bin:"*) ;;
        *) aviso "~/.local/bin no esta en tu PATH: el icono de CeliuzPaper no abrira nada" ;;
    esac

    hacer update-desktop-database "$DATOS/applications" 2>/dev/null
    hacer gtk-update-icon-cache -f -t "$DATOS/icons/hicolor" 2>/dev/null
    hecho "  cachés de iconos y .desktop actualizadas"
}

# --- 4. El dock --------------------------------------------------------------

dock() {
    titulo "4. Dock"
    local gen="$REPO/hypr/scripts/gen-dock.py"
    if [ ! -e "$REPO/waybar/dock-apps.json" ]; then
        echo "  primera vez: busco tu terminal y tu navegador"
        hacer "$gen" seed --no-reload
    else
        gris "  ya tienes tu propio dock-apps.json (no lo toco)"
        # dock.jsonc y dock-icons.css SI se rehacen siempre: llevan las rutas
        # absolutas de los iconos de ESTA maquina.
        hacer "$gen" gen --no-reload
    fi
}

# --- 5. Terminal para los atajos ---------------------------------------------

terminal_local() {
    titulo "5. Terminal de los atajos"
    local term
    term="$("$REPO/hypr/scripts/lib/apps.py" terminal 2>/dev/null)"
    if [ -z "$term" ]; then
        aviso "no encuentro ninguna terminal conocida; SUPER+RETURN no abrira nada"
        term="kitty"
    fi
    echo "  SUPER+RETURN abrira: $term"
    if [ "$SOLO_REVISAR" -eq 0 ]; then
        cat > "$REPO/hypr/conf/local.conf" <<EOF
# hypr/conf/local.conf — GENERADO por instalar.sh. NO se versiona.
#
# Lo de esta maquina y solo de esta. Se carga antes que keybinds.conf porque las
# variables de hyprlang son sustitucion de texto: si se definieran despues, los
# binds ya se habrian leido con el valor viejo.
#
# Para cambiar de terminal: edita la linea y recarga con SUPER+SHIFT+R.
\$terminal = $term
EOF
        hecho "  escrito hypr/conf/local.conf"
    fi
}

# --- 6. Fondo de pantalla ----------------------------------------------------

fondo() {
    titulo "6. Fondo de pantalla"
    if [ -e "$REPO/hypr/wallpapers/current" ]; then
        verde "  ya hay uno elegido: $(basename "$(readlink -f "$REPO/hypr/wallpapers/current")")"
    else
        echo "  todavia no hay ninguno (los videos no se versionan, pesan mucho)"
        gris "    elige uno con: celiuzpaper"
        gris "    o a mano con:  hypr/scripts/set-wallpaper.sh <ruta-al-video>"
    fi
}

# --- Adelante ----------------------------------------------------------------

if [ "$SOLO_REVISAR" -eq 1 ]; then
    printf '\033[1mREVISION — no se va a tocar nada\033[0m\n'
fi

if [ "$SOLO_DOCK" -eq 1 ]; then
    dock
else
    comprobar_dependencias
    desplegar
    celiuzpaper
    dock
    terminal_local
    fondo
fi

titulo "Resumen"
if [ ${#AVISOS[@]} -eq 0 ]; then
    verde "  sin pendientes"
else
    for a in "${AVISOS[@]}"; do rojo "  ! $a"; done
fi
echo
echo "Cierra la sesion y vuelve a entrar para que Hyprland lea todo esto."
gris "(recargar con SUPER+SHIFT+R no basta la primera vez: los exec-once solo"
gris " corren al arrancar la sesion)"
