#!/usr/bin/env bash
# ~/dotfiles/instalar.sh
#
# Deja este escritorio funcionando en una maquina nueva. Se puede volver a
# ejecutar cuantas veces haga falta: no repite lo que ya esta hecho.
#
#   ./instalar.sh                 instala
#   ./instalar.sh --revisar       solo dice que haria, sin tocar nada
#   ./instalar.sh --dock          solo rehace el dock de esta maquina
#   ./instalar.sh --sddm          pantalla de inicio de sesion (PIDE SUDO)
#   ./instalar.sh --sddm-quitar   la quita y deja la de antes
#   ./instalar.sh --remoto-sistema         Celiuz Remoto tras reiniciar (PIDE SUDO)
#   ./instalar.sh --remoto-sistema-quitar  lo quita
#   ./instalar.sh --remoto-todo   TODO lo de Celiuz Remoto de una vez (PIDE SUDO)
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
SOLO_SDDM=0
QUITAR_SDDM=0
SOLO_REMOTO_SISTEMA=0
QUITAR_REMOTO_SISTEMA=0
SOLO_REMOTO_TODO=0
for arg in "$@"; do
    case "$arg" in
        --revisar|-n)  SOLO_REVISAR=1 ;;
        --dock)        SOLO_DOCK=1 ;;
        --sddm)        SOLO_SDDM=1 ;;
        --sddm-quitar) QUITAR_SDDM=1 ;;
        --remoto-sistema)        SOLO_REMOTO_SISTEMA=1 ;;
        --remoto-sistema-quitar) QUITAR_REMOTO_SISTEMA=1 ;;
        --remoto-todo)           SOLO_REMOTO_TODO=1 ;;
        -h|--help)     sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'; exit 0 ;;
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

    # Los de las teclas de funcion van APARTE de los imprescindibles: sin ellos
    # el escritorio arranca igual y no se rompe nada. Pero hay que decirlo, y por
    # eso no basta con no listarlos: un bind cuyo `exec` no existe NO da error ni
    # avisa por ninguna parte — pulsas la tecla de volumen y no pasa nada, sin
    # una sola pista de por que. Es exactamente el fallo en silencio que este
    # repo evita en todo lo demas.
    local -A teclas=(
        [wpctl]="wireplumber"        # volumen, mute y micro-mute
        [playerctl]="playerctl"      # play/pausa, siguiente, anterior
    )
    # brightnessctl solo hace falta en un portatil: es quien mueve el brillo en
    # conf/teclado-laptop.conf, y ese fichero un sobremesa no lo lee.
    if "$REPO/hypr/scripts/lib/maquina.py" --es-laptop 2>/dev/null; then
        teclas[brightnessctl]="brightnessctl"
    fi

    local sin_teclas=()
    for binario in "${!teclas[@]}"; do
        command -v "$binario" >/dev/null 2>&1 || sin_teclas+=("${teclas[$binario]}")
    done
    if [ ${#sin_teclas[@]} -gt 0 ]; then
        aviso "las teclas de funcion no haran nada sin: ${sin_teclas[*]}"
        gris "    sudo pacman -S ${sin_teclas[*]}"
    fi

    # Y lo mismo con la grabacion de pantalla: SUPER+R esta puesto en
    # keybinds.conf, pero sin wf-recorder ese bind es una tecla que no hace nada.
    # El escritorio arranca igual, de ahi que sea un aviso y no un error.
    if ! command -v wf-recorder >/dev/null 2>&1; then
        aviso "SUPER+R (grabar la pantalla) no hara nada sin: wf-recorder"
        gris "    sudo pacman -S wf-recorder"
    fi

    # El overlay de FPS del modo gaming (Supr en la PC, Insert en un portatil) lo
    # dibuja MangoHud. Sin el, el modo arranca Steam con MANGOHUD=1 igual y la
    # tecla no hace NADA, sin un error en ningun sitio: paso en la laptop el
    # 2026-10-20. lib32 hace falta para los juegos de 32 bits.
    if ! command -v mangohud >/dev/null 2>&1; then
        aviso "el overlay de FPS del modo gaming no saldra sin: mangohud lib32-mangohud"
        gris "    sudo pacman -S mangohud lib32-mangohud"
    fi

    # El QR de «Compartir red» del panel de red sale de qrencode. Sin el, el
    # panel lo dice en su sitio y enseña la contraseña igual: es un aviso.
    if ! command -v qrencode >/dev/null 2>&1; then
        aviso "«Compartir red» del panel de red no podra hacer el QR sin: qrencode"
        gris "    sudo pacman -S qrencode"
    fi

    # Y el Bluetooth, solo si el equipo tiene: sin adaptador el modulo de la
    # barra se esconde solo y no hay nada que pedir. Con adaptador faltan dos
    # cosas: el «Ajustes avanzados» del panel abre bluetui (sin el, avisa y no
    # abre nada), y sin el servicio de BlueZ no hay icono ni auriculares que se
    # conecten solos.
    if compgen -G '/sys/class/bluetooth/hci*' >/dev/null; then
        if ! command -v bluetui >/dev/null 2>&1; then
            aviso "«Ajustes avanzados» del panel de Bluetooth no hara nada sin: bluetui"
            gris "    sudo pacman -S bluetui"
        fi
        if ! systemctl is-active --quiet bluetooth.service 2>/dev/null; then
            aviso "este equipo tiene Bluetooth pero su servicio esta parado"
            gris "    sudo systemctl enable --now bluetooth"
        fi
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
    # Los kanji del titulo de la pantalla de bloqueo (彼岸花, y el mismo texto en
    # el tema de SDDM). Sin esta fuente no fallan: salen como cuadrados vacios,
    # que es peor, porque parece que la config esta rota y no que falta un
    # paquete. Es un aviso y no un error: quien ponga un titulo en alfabeto
    # latino no la necesita para nada.
    case "$familias" in
        *"Noto Sans CJK"*) ;;
        *) aviso "falta la fuente de los kanji del bloqueo: sudo pacman -S noto-fonts-cjk"
           gris "    sin ella, el titulo 彼岸花 sale como cuadrados (cambialo en hypr/hyprlock.conf)" ;;
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

    for pieza in hypr waybar fuzzel mako mpvpaper fastfetch; do
        enlazar "$REPO/$pieza" "$CONFIG/$pieza"
    done

    # fuzzel lanza las apps de terminal (nmtui, vim...) con lo que diga su opcion
    # `terminal`, y ahi no sirve ni una ruta con ~ —no la expande— ni una
    # absoluta —seria la del equipo del autor—. Por el PATH si funciona.
    hacer mkdir -p "$HOME/.local/bin"
    enlazar "$REPO/hypr/scripts/terminal.sh" "$HOME/.local/bin/celiuz-terminal"

    # El historial de notificaciones, tambien por el PATH: no es solo para
    # teclearlo comodo, es la puerta por la que cualquier otro programa puede
    # preguntar que llego hoy sin saber donde esta clonado este repo.
    enlazar "$REPO/hypr/scripts/avisos.py" "$HOME/.local/bin/avisos"

    # El saludo de la terminal (fastfetch con una imagen al azar), por el PATH
    # para que lo pueda llamar cualquier shell. Lo engancha a fish saludo_fish().
    enlazar "$REPO/hypr/scripts/saludo.sh" "$HOME/.local/bin/celiuz-saludo"

    # La config es LUA desde el 2026-09-25 (hypr/hyprland.lua): Hyprland 0.56 la
    # prefiere a hyprland.conf, y la 0.57 retira la de hyprlang. Un Hyprland mas
    # viejo no sabe leerla y arrancaria con la de hyprlang que queda de puente
    # (o sin nada, cuando el puente se borre), asi que se comprueba la version.
    comprobar_hyprland_lua
}

# saludo_fish — que fish salude con celiuz-saludo en vez del fastfetch a secas
# de CachyOS. config.fish es del usuario, asi que no se enlaza: se le AÑADE una
# linea marcada, al final (la config de CachyOS define fish_greeting dentro del
# `source` del principio, y gana lo ultimo que se define; conf.d/ no sirve
# porque fish lo lee ANTES que config.fish). Si el usuario ya tiene su propio
# fish_greeting escrito ahi, no se toca. Bash y zsh: README.
SALUDO_MARCA="# celiuz-saludo (lo puso instalar.sh; borra estas dos lineas para quitarlo)"
SALUDO_LINEA="function fish_greeting; celiuz-saludo --fish | source; end"
SALUDO_VIEJA="function fish_greeting; celiuz-saludo; end"
saludo_fish() {
    titulo "2b. El saludo de la terminal"
    local fotos
    fotos="$("$REPO/hypr/scripts/saludo.sh" --carpeta)"
    gris "  las imagenes, en el repo: $fotos ($(find "$fotos" -maxdepth 1 -type f 2>/dev/null | wc -l))"
    if ! command -v fastfetch >/dev/null 2>&1; then
        aviso "el saludo de la terminal necesita: fastfetch"
        gris "    sudo pacman -S fastfetch"
    fi
    command -v fish >/dev/null 2>&1 || { gris "  sin fish: nada que enganchar"; return 0; }
    local conf="${XDG_CONFIG_HOME:-$HOME/.config}/fish/config.fish"
    # La linea de antes del 2026-10-22 llamaba a `celiuz-saludo` a secas; la de
    # ahora deja ademas que fish lo redibuje al cambiar de tamaño la terminal
    # (ver saludo.sh). Solo se cambia NUESTRA linea, tal cual la escribimos.
    if [ -f "$conf" ] && grep -qx "$SALUDO_VIEJA" "$conf"; then
        if [ "$SOLO_REVISAR" -eq 1 ]; then
            gris "  (haria) poner al dia la linea del saludo en $conf"
        else
            sed -i "s/^${SALUDO_VIEJA}\$/${SALUDO_LINEA}/" "$conf"
            hecho "  linea del saludo al dia en $conf"
        fi
    elif [ -f "$conf" ] && grep -qF "celiuz-saludo" "$conf"; then
        gris "  ya enganchado en $conf"
    elif [ -f "$conf" ] && grep -qE '^[[:space:]]*function[[:space:]]+fish_greeting' "$conf"; then
        gris "  tienes tu propio fish_greeting en $conf: no lo toco"
    else
        if [ "$SOLO_REVISAR" -eq 1 ]; then
            gris "  (haria) añadir el saludo al final de $conf"
        else
            mkdir -p "$(dirname "$conf")"
            printf '\n%s\n%s\n' "$SALUDO_MARCA" "$SALUDO_LINEA" >> "$conf"
            hecho "  enganchado en $conf"
        fi
    fi
}

# kitty_iconos — los iconos de Nerd Font a su tamaño en kitty (2026-10-22).
# Como config.fish, kitty.conf es del usuario: se enlaza el script al lado y
# se le AÑADE una linea marcada, una vez. El script elige la fuente cada vez
# que arranca kitty (ver kitty/celiuz-iconos.py).
KITTY_MARCA="# celiuz-iconos (lo puso instalar.sh; borra estas dos lineas para quitarlo)"
KITTY_LINEA="geninclude celiuz-iconos.py"
kitty_iconos() {
    titulo "2c. Los iconos de la terminal (kitty)"
    command -v kitty >/dev/null 2>&1 || { gris "  sin kitty: nada que hacer"; return 0; }
    local dir="${XDG_CONFIG_HOME:-$HOME/.config}/kitty"
    local conf="$dir/kitty.conf" fuente
    hacer mkdir -p "$dir"
    enlazar "$REPO/kitty/celiuz-iconos.py" "$dir/celiuz-iconos.py"
    if [ -f "$conf" ] && grep -qxF "$KITTY_LINEA" "$conf"; then
        gris "  ya enganchado en $conf"
    elif [ "$SOLO_REVISAR" -eq 1 ]; then
        gris "  (haria) añadir los iconos al final de $conf"
    else
        printf '\n%s\n%s\n' "$KITTY_MARCA" "$KITTY_LINEA" >> "$conf"
        hecho "  enganchado en $conf (las terminales nuevas)"
    fi
    fuente="$("$REPO/kitty/celiuz-iconos.py" | awk '{ $1 = $2 = ""; sub(/^ +/, ""); print }')"
    if [ -n "$fuente" ]; then
        gris "    los iconos, de: $fuente"
    else
        aviso "no hay una Nerd Font normal (no Mono): los iconos se quedan pequeños"
        gris "    sudo pacman -S ttf-nerd-fonts-symbols"
    fi
}

# comprobar_hyprland_lua — que el Hyprland instalado lee Lua, y en que idioma
# esta la sesion abierta.
comprobar_hyprland_lua() {
    local version
    version="$(Hyprland --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)"
    if [ -z "$version" ]; then
        aviso "no pude saber la version de Hyprland; esta config necesita la 0.56 o mas nueva (Lua)"
    elif ! printf '%s\n' "0.56" "$version" | sort -V -C; then
        aviso "tienes Hyprland $version y esta config es Lua: hace falta la 0.56 o mas nueva"
        gris "    (sudo pacman -Syu). Mientras tanto se usa la config de hyprlang de puente."
    else
        gris "  Hyprland $version: lee la config en Lua (hypr/hyprland.lua)"
    fi

    # Si hay sesion abierta, se le pregunta en que idioma arranco: la que ya
    # estaba al traer los cambios sigue en hyprlang hasta cerrar sesion.
    if [ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ] && command -v hyprctl >/dev/null 2>&1; then
        case "$(hyprctl eval 'return 1' 2>/dev/null)" in
            ok) gris "  la sesion abierta ya usa la config en Lua" ;;
            *only\ supported\ with\ the\ lua*)
                aviso "tu sesion abierta aun usa la config vieja (hyprlang): cierra sesion y vuelve a entrar"
                gris "    para pasar a la de Lua. Hasta entonces todo sigue funcionando igual." ;;
        esac
    fi
}

# recargar_sesion — un `hyprctl reload` a la sesion abierta, al final.
#
# No es por cortesia: `git pull` reescribe los ficheros de la config BORRANDOLOS
# y creandolos otra vez, y Hyprland, que vigila esos ficheros, a veces recarga
# justo en el hueco. Sale «Your config has errors: cannot open .../hyprland.lua:
# No such file or directory» y, peor, Hyprland DEJA DE VIGILAR: editar despues
# cualquier fichero de la config no recarga nada, y el aviso se queda puesto.
# Medido en anidado el 2026-10-20; solo lo cura un reload. Como el camino de
# siempre es `git pull && ./instalar.sh`, aqui queda curado justo despues.
recargar_sesion() {
    [ "$SOLO_REVISAR" -eq 1 ] && return 0
    [ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ] || return 0
    command -v hyprctl >/dev/null 2>&1 || return 0
    titulo "10. La sesion abierta"
    local errores
    if errores="$("$REPO/hypr/scripts/recargar.sh" -q 2>&1)"; then
        hecho "  config recargada, sin errores"
    else
        aviso "la config recargo con avisos o errores:"
        printf '%s\n' "$errores" | sed 's/^/    /'
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
        *) aviso "~/.local/bin no esta en tu PATH: ni el icono de CeliuzPaper ni las apps de terminal del lanzador abriran nada" ;;
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

# lua_cadena <texto> — un literal de cadena de Lua (para escribir local.lua).
lua_cadena() {
    local t="$1"
    t="${t//\\/\\\\}"
    t="${t//\"/\\\"}"
    t="${t//$'\n'/ }"
    printf '"%s"' "$t"
}

# --- 5. Lo de esta maquina ----------------------------------------------------
#
# Un solo escritor para local.conf, a proposito: si la terminal y el tipo de
# equipo lo escribieran dos funciones distintas, la segunda borraria lo de la
# primera y el sintoma seria "se me olvida la terminal cada vez que instalo".

maquina_local() {
    titulo "5. Lo de esta maquina"

    local term
    term="$("$REPO/hypr/scripts/lib/apps.py" terminal 2>/dev/null)"
    if [ -z "$term" ]; then
        aviso "no encuentro ninguna terminal conocida; SUPER+RETURN no abrira nada"
        term="kitty"
    fi
    echo "  SUPER+RETURN abrira: $term"

    # Portatil o sobremesa. Lo decide el DMI de la BIOS; ver lib/maquina.py para
    # el porque de cada fuente y por que la bateria sola no basta.
    local tipo motivo conf_maquina
    tipo="$("$REPO/hypr/scripts/lib/maquina.py" tipo 2>/dev/null || echo escritorio)"
    # Se le PREGUNTA el motivo, no se le saca del --json con un sed. Lo de antes
    # era `sed -n 's/.*"motivo": ...'`, y en cuanto el --json crecio con el
    # perfil de teclado —que tambien trae su "motivo"— el patron empezo a casar
    # DOS veces y la linea salia partida en dos. Raspar JSON con sed se rompe
    # solo con anadir un campo.
    motivo="$("$REPO/hypr/scripts/lib/maquina.py" motivo 2>/dev/null)"

    # La distribucion del teclado, por el mismo camino: se le PREGUNTA, no se
    # deduce aqui. En un portatil sale de /etc/vconsole.conf y en un sobremesa se
    # queda la del autor; el porque de esa asimetria esta en maquina.py.
    local kb_layout kb_variant motivo_layout
    kb_layout="$("$REPO/hypr/scripts/lib/maquina.py" layout 2>/dev/null || echo 'us,latam')"
    kb_variant="$("$REPO/hypr/scripts/lib/maquina.py" variante 2>/dev/null || echo 'altgr-intl,')"
    motivo_layout="$(python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import maquina; print(maquina.perfil_teclado()["motivo_layout"])' "$REPO/hypr/scripts/lib" 2>/dev/null)"

    if [ "$tipo" = "laptop" ]; then
        conf_maquina='$HOME/.config/hypr/conf/teclado-laptop.conf'
        echo "  equipo: portatil  ($motivo)"
        gris "    se carga lua/teclado-laptop.lua: touchpad, tapa, brillo y el"
        gris "    perfil de teclado «completo» (kb_options vacio, o sea que el"
        gris "    Ctrl derecho sigue siendo Ctrl en TODOS los teclados)"
        echo "  teclado: $kb_layout  (la primera arranca activa; SUPER+DEL alterna)"
        gris "    $motivo_layout"
    else
        conf_maquina='$HOME/.config/hypr/conf/nada.conf'
        echo "  equipo: sobremesa  ($motivo)"
        gris "    no se carga nada de portatil"
        # Un sobremesa se queda con el perfil «sin-altgr», que es el teclado del
        # autor (ANSI de 75%, sin AltGr). A quien clone el repo con un teclado
        # completo eso le quita el Ctrl derecho a cambio de nada, y sin decirlo
        # en ningun sitio se pasa media hora buscando el fallo. No se detecta
        # sola —un teclado se enchufa y se desenchufa, y kb_options se lee al
        # arrancar—, asi que lo que toca es AVISAR.
        gris "    perfil de teclado «sin-altgr»: el Ctrl derecho hace de AltGr"
        gris "    (si tu teclado ya tiene AltGr no te hace falta: pon en tu"
        gris "    lua/personal.lua  hl.config({ input = { kb_options = \"\" } })"
    fi

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

# Portatil o sobremesa, segun el DMI de la BIOS (scripts/lib/maquina.py).
# Este fichero lo carga hyprland.conf EL ULTIMO, para que corrija a input.conf y
# a keybinds.conf en vez de que ellos lo pisen a el.
#
# Detectado aqui: $tipo — $motivo
#
# Si se detecto mal, cambia esta linea a mano y recarga con SUPER+SHIFT+R; el
# siguiente ./instalar.sh la volvera a calcular.
\$conf_maquina = $conf_maquina

# La distribucion del teclado de ESTA maquina. La primera es la que arranca
# activa; SUPER+DEL alterna entre las dos.
#
# $motivo_layout
#
# Si no es la tuya, cambiala aqui y recarga con SUPER+SHIFT+R. Los nombres
# validos salen de: localectl list-x11-keymap-layouts
\$kb_layout = $kb_layout
\$kb_variant = $kb_variant
EOF
        hecho "  escrito hypr/conf/local.conf (el de la config vieja, de puente)"

        # Lo mismo para la config en Lua, que es la que usa Hyprland 0.56+.
        # local.conf se sigue escribiendo mientras exista el puente de hyprlang:
        # una sesion que arranco con el lo relee al recargar.
        local portatil=false
        [ "$tipo" = "laptop" ] && portatil=true
        cat > "$REPO/hypr/lua/local.lua" <<EOF
-- hypr/lua/local.lua — GENERADO por instalar.sh. NO se versiona.
--
-- Lo de esta maquina y solo de esta. Lo lee lua/maquina.lua, que pone los
-- valores de fabrica para lo que falte aqui.
--
-- Si algo no es lo tuyo, cambialo aqui y recarga con SUPER+SHIFT+R; el siguiente
-- ./instalar.sh lo volvera a calcular.
return {
    -- La terminal de SUPER+RETURN (scripts/lib/apps.py).
    terminal = $(lua_cadena "$term"),

    -- Portatil o sobremesa, segun el DMI de la BIOS (scripts/lib/maquina.py).
    -- Con true se carga lua/teclado-laptop.lua: touchpad, tapa, brillo y el
    -- teclado «completo».
    -- Detectado aqui: $tipo — $motivo
    portatil = $portatil,
    motivo = $(lua_cadena "$tipo — $motivo"),

    -- La distribucion del teclado de ESTA maquina. La primera es la que arranca
    -- activa; SUPER+DEL alterna entre las dos. Los nombres validos salen de:
    -- localectl list-x11-keymap-layouts
    -- $motivo_layout
    kb_layout = $(lua_cadena "$kb_layout"),
    kb_variant = $(lua_cadena "$kb_variant"),
}
EOF
        hecho "  escrito hypr/lua/local.lua"
    fi

    # --- Tu fichero, el que el repo no toca nunca ---
    #
    # Se crea VACIO si no existe, y no se pisa jamas si ya esta: aqui es donde
    # pones lo tuyo (un exec-once de un programa que solo tienes tu, un bind para
    # algo que no viene en este repo, un ajuste que prefieres distinto). Va el
    # ultimo en hyprland.conf, asi que desde ahi puedes pisar cualquier cosa.
    #
    # Existe porque hyprlang avisa por un `source` que no encuentra, y este repo
    # se toma en serio que `hyprctl configerrors` salga limpio en una instalacion
    # recien hecha.
    if [ ! -e "$REPO/hypr/conf/personal.conf" ]; then
        if [ "$SOLO_REVISAR" -eq 0 ]; then
            cat > "$REPO/hypr/conf/personal.conf" <<'EOF'
# hypr/conf/personal.conf — TUYO. No se versiona, y el repo no lo pisa nunca.
#
# Se carga el ULTIMO de todos, asi que aqui puedes anadir lo que quieras y
# tambien pisar cualquier ajuste o atajo del repo: en hyprlang gana el ultimo.
#
#   exec-once = mi-programa
#   bind = SUPER, G, exec, otra-cosa
#   bind = SUPER, Q, killactive     # pisar uno que ya existe
EOF
            hecho "  creado hypr/conf/personal.conf (vacio, para tus cosas)"
        else
            aviso "falta hypr/conf/personal.conf (lo crea el instalador)"
        fi
    else
        gris "  hypr/conf/personal.conf ya esta (no se toca)"
    fi

    # --- Lo tuyo, en la config Lua ---
    #
    # lua/personal.lua es el personal.conf de la config en Lua: tuyo, sin
    # versionar, cargado el ultimo. Si no existe y tu personal.conf tiene algo,
    # se TRADUCE (lib/migrar_personal.py): sin esto, al volver a entrar con la
    # config en Lua perderias en silencio lo que tuvieras — en la laptop del
    # autor, la escala 1.5 del televisor. Lo que no se sabe traducir se deja
    # comentado y se avisa. personal.conf NO se toca: la sesion que arranco con
    # la config vieja lo sigue leyendo hasta cerrar sesion.
    local personal_lua="$REPO/hypr/lua/personal.lua"
    local personal_conf="$REPO/hypr/conf/personal.conf"
    if [ -e "$personal_lua" ]; then
        gris "  hypr/lua/personal.lua ya esta (no se toca)"
    elif [ "$SOLO_REVISAR" -ne 0 ]; then
        aviso "falta hypr/lua/personal.lua (lo crea el instalador)"
    elif [ -e "$personal_conf" ] && grep -qvE '^[[:space:]]*(#|$)' "$personal_conf"; then
        local avisos_migracion
        if avisos_migracion="$(python3 "$REPO/hypr/scripts/lib/migrar_personal.py" \
                "$personal_conf" 2>&1 >"$personal_lua.nuevo")"; then
            mv "$personal_lua.nuevo" "$personal_lua"
            hecho "  traducido tu conf/personal.conf a hypr/lua/personal.lua"
            if [ -n "$avisos_migracion" ]; then
                aviso "hay lineas de personal.conf que no se tradujeron solas; estan comentadas en lua/personal.lua:"
                sed 's/^/      /' <<<"$avisos_migracion"
            fi
        else
            rm -f "$personal_lua.nuevo"
            aviso "no pude traducir conf/personal.conf: $avisos_migracion"
        fi
    else
        cat > "$personal_lua" <<'EOF'
-- hypr/lua/personal.lua — TUYO. No se versiona, y el repo no lo pisa nunca.
--
-- Se carga el ULTIMO de todos, asi que aqui puedes anadir lo que quieras y
-- tambien pisar cualquier ajuste o atajo del repo: gana el ultimo que habla.
--
--   hl.on("hyprland.start", function() hl.exec_cmd("mi-programa") end)
--   hl.bind("SUPER + G", hl.dsp.exec_cmd("otra-cosa"))
--   hl.monitor({ output = "DP-1", mode = "2560x1440@144", position = "0x0", scale = 1 })
--   hl.config({ input = { kb_options = "" } })
--
-- Mas ejemplos, con su porque, en los modulos de hypr/lua/.
EOF
        hecho "  creado hypr/lua/personal.lua (vacio, para tus cosas)"
    fi

    # --- El lado derecho de la barra, y el sensor de temperatura ---
    #
    # Las dos cosas van al mismo fichero generado (waybar/local.jsonc) porque las
    # dos son de esta caja y de ninguna otra, y porque waybar solo mira el PRIMER
    # sitio donde aparece cada clave: si esto se repartiera en dos generados
    # habria que vigilar el orden de los include.
    #
    # El sensor: la ruta del hwmon de la CPU depende del procesador (k10temp en
    # AMD, coretemp en Intel) y no se puede versionar. La averigua sensores.py.
    # Si no reconoce ninguno se deja la clave fuera a proposito y waybar cae a
    # su thermal_zone0: mejor su valor por defecto que una ruta inventada.
    local sensor_ruta sensor_entrada
    sensor_ruta="$("$REPO/hypr/scripts/lib/sensores.py" ruta 2>/dev/null || true)"
    sensor_entrada="$("$REPO/hypr/scripts/lib/sensores.py" entrada 2>/dev/null || true)"
    if [ -n "$sensor_ruta" ]; then
        gris "    sensor de CPU: $(basename "$(dirname "$sensor_ruta")") ($sensor_ruta)"
    else
        aviso "no reconozco el sensor de temperatura de esta CPU"
        gris "    la barra usara el thermal_zone0 de waybar, que puede no ser la CPU"
        gris "    mira que hay con: hypr/scripts/lib/sensores.py"
    fi
    #
    # La bateria solo tiene sentido en un portatil, y en un sobremesa no basta
    # con que "no se vea": el modulo dejaria un hueco vacio en la barra, porque
    # waybar crea el widget igual aunque no encuentre ninguna bateria (solo deja
    # un aviso "No batteries." en el log). Asi que se decide aqui, sacando el
    # modulo de la lista.
    #
    # La lista NO se escribe a mano en dos sitios: se lee de waybar/derecha.jsonc
    # —la versionada, la del sobremesa— y se le mete "battery" delante de las
    # notificaciones. Quien anada un modulo alli lo tendra en las dos maquinas
    # sin tocar este script.
    if [ "$SOLO_REVISAR" -eq 0 ]; then
        if BATERIA="$( [ "$tipo" = "laptop" ] && echo si || echo no )" \
           SENSOR_RUTA="$sensor_ruta" SENSOR_ENTRADA="$sensor_entrada" \
           python3 - "$REPO/waybar/derecha.jsonc" "$REPO/waybar/local.jsonc" \
                     "$REPO/waybar/sensores.jsonc" <<'PY'
import json, os, re, sys

origen, destino, origen_sensores = sys.argv[1], sys.argv[2], sys.argv[3]
con_bateria = os.environ.get("BATERIA") == "si"

def leer_jsonc(ruta):
    """Un .jsonc del repo, ya sin comentarios.

    json no entiende los comentarios de un .jsonc. Se quitan solo los que ocupan
    la linea entera: quitarlos en cualquier posicion se llevaria por delante
    cualquier "//" que apareciera dentro de una cadena.
    """
    crudo = open(ruta, encoding="utf-8").read()
    limpio = "\n".join(l for l in crudo.splitlines() if not l.lstrip().startswith("//"))
    return json.loads(limpio)

modulos = leer_jsonc(origen)["modules-right"]

if con_bateria and "battery" not in modulos:
    # Junto a los otros indicadores de estado y antes de las notificaciones. Si
    # algun dia ese modulo no esta, va al final: nunca se pierde.
    pos = modulos.index("custom/notificaciones") if "custom/notificaciones" in modulos else len(modulos)
    modulos.insert(pos, "battery")

# El modulo de temperatura sale del versionado y solo se le anade la ruta del
# sensor de esta caja. Asi lo que se ve (formato, iconos, umbral) se toca en un
# solo sitio —waybar/sensores.jsonc— y llega aqui en el siguiente ./instalar.sh.
salida = {"modules-right": modulos}
ruta_sensor = os.environ.get("SENSOR_RUTA", "").strip()
entrada_sensor = os.environ.get("SENSOR_ENTRADA", "").strip()
if ruta_sensor and entrada_sensor:
    temperatura = leer_jsonc(origen_sensores)["temperature"]
    # Delante, para que se lean antes que el resto al abrir el fichero: son lo
    # unico de aqui que no vale en otra maquina.
    salida["temperature"] = dict(
        {"hwmon-path-abs": ruta_sensor, "input-filename": entrada_sensor},
        **temperatura)

cabecera = (
    "// waybar/local.jsonc — GENERADO por instalar.sh. NO se versiona.\n"
    "//\n"
    "// Lo de ESTA maquina: el lado derecho de la barra y la ruta del sensor de\n"
    "// temperatura de la CPU. Lo carga config.jsonc por \"include\", y va el\n"
    "// primero: en waybar gana el primero que define una clave, asi que esto\n"
    "// manda sobre waybar/derecha.jsonc y waybar/sensores.jsonc.\n"
    "//\n"
    "// Equipo detectado: %s.\n"
    "// Sensor de CPU: %s.\n"
    "// Si te lo detecto mal, mira el motivo en hypr/conf/local.conf (el equipo)\n"
    "// o pasa hypr/scripts/lib/sensores.py (el sensor), y repite ./instalar.sh.\n"
    % ("portatil (lleva bateria)" if con_bateria else "sobremesa (sin bateria)",
       ("%s (%s)" % (ruta_sensor, entrada_sensor)) if ruta_sensor
       else "ninguno reconocido; waybar caera a thermal_zone0")
)
with open(destino, "w", encoding="utf-8") as f:
    f.write(cabecera + json.dumps(salida, indent=4, ensure_ascii=False) + "\n")
PY
        then
            hecho "  escrito waybar/local.jsonc"
        else
            aviso "no se pudo generar waybar/local.jsonc"
            gris "    la barra se queda con waybar/derecha.jsonc, sin bateria"
        fi
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
    # La carpeta de videos del sistema, que es un modulo mas del selector. Se
    # pregunta a la libreria para no repetir aqui la logica de XDG.
    local videos
    videos=$(python3 -c "
import sys; sys.path.insert(0, '$REPO/hypr/scripts/lib')
import wallpapers as wp
print(wp.carpeta_videos() or '')" 2>/dev/null)
    if [ -n "$videos" ]; then
        gris "  tu carpeta de videos: $videos  (sale como modulo en celiuzpaper)"
    fi
}

# --- 7. La pantalla -----------------------------------------------------------
# No hay nada que instalar: se mide en caliente cada vez. Se ensena para que se
# vea CON QUE numeros va a trabajar el escritorio en este equipo, que es de donde
# salen las medidas del bloqueo y del selector de fondos.

pantalla() {
    titulo "7. Pantalla"
    local resumen codigo
    # Lo que decide si esto fue bien es el CODIGO DE SALIDA, no que haya salido
    # texto. Antes era `2>/dev/null` con un `-z` delante, y esa pareja tiene un
    # punto ciego: un fallo A MEDIA IMPRESION deja la variable con lo ya escrito
    # —o sea, no vacia—, asi que no saltaba el aviso, el traceback se iba al
    # limbo y el instalador terminaba diciendo «sin pendientes» con esta seccion
    # cortada por la mitad. Paso de verdad, y duro dos sesiones.
    resumen=$("$REPO/hypr/scripts/lib/pantalla.py" 2>&1)
    codigo=$?
    [ -n "$resumen" ] && printf '%s\n' "$resumen" | sed '/^$/d' | sed 's/^/  /'
    if [ "$codigo" -ne 0 ]; then
        aviso "lib/pantalla.py fallo al medir (codigo $codigo): lo de arriba esta incompleto"
        return
    fi
    if [ -z "$resumen" ]; then
        aviso "no se pudo medir la pantalla (lib/pantalla.py)"
        return
    fi
    if printf '%s' "$resumen" | grep -q "NO detectada"; then
        aviso "sin pantalla detectada: se usan medidas de reserva (1920x1080)"
    fi
}

# --- 8. Pantalla de inicio de sesion (SDDM) ----------------------------------
# ES EL UNICO PASO QUE PIDE ROOT, y por eso va aparte y no se ejecuta con el
# resto: un tema de SDDM no tiene equivalente por usuario, tiene que vivir en
# /usr/share/sddm/themes. Todo lo demas de este repo se instala sin contrasena y
# asi debe seguir.
#
# Tampoco es imprescindible: sin correrlo, el escritorio funciona igual y solo
# te falta la pantalla del arranque.

SDDM_TEMA="/usr/share/sddm/themes/celiuz"
SDDM_DROPIN="/etc/sddm.conf.d/10-celiuz.conf"
# La carpeta del fondo del login. Es tuya y la lee el grupo `sddm`; ver
# preparar_fondo_sddm para por que existe y por que va con setgid.
SDDM_COMPARTIDA="${SDDM_COMPARTIDA:-/var/lib/sddm-celiuz}"

# Segundos del video que se copian. El greeter se ve unos segundos y el fichero
# acaba en /usr/share, que no es sitio para los 700 MB de un fondo largo. Se
# puede subir:  SDDM_SEGUNDOS=60 ./instalar.sh --sddm
SDDM_SEGUNDOS="${SDDM_SEGUNDOS:-30}"

# Hacer algo como root, contandolo antes. En --revisar no pide contrasena ni
# toca nada, para que se pueda mirar que haria sin dar permisos.
raiz() {
    if [ "$SOLO_REVISAR" -eq 1 ]; then
        gris "  (haria, como root) $*"
        return 0
    fi
    if [ "$(id -u)" -eq 0 ]; then "$@"; else sudo "$@"; fi
}

# El fondo del arranque NO se copia a /usr/share, y esa es toda la gracia.
#
# La primera version si lo copiaba, y salio mal en cuanto se uso de verdad:
# /usr/share es de root, asi que cada cambio de fondo obligaba a volver a pasar
# `--sddm` y teclear la contrasena. Quien cambia de fondo a menudo simplemente
# se quedaba con el login enseñando un fondo viejo.
#
# Ahora se crea UNA VEZ una carpeta compartida —tuya, legible por el usuario
# `sddm`— y los dos ficheros del tema pasan a ser ENLACES a ella. El QML los
# carga por ruta relativa y no se entera. A partir de ese momento el fondo del
# login lo rehace `hypr/scripts/sddm-fondo.sh` sin permisos de ninguna clase,
# solo, cada vez que fijas un fondo.
#
# El 2750 es lo que hace que funcione: setgid + grupo `sddm`. Los ficheros que
# crees dentro nacen con ese grupo y el greeter puede leerlos. Sin el setgid
# nacerian con TU grupo y el greeter se encontraria un permiso denegado, que en
# el arranque se ve como "el fondo no sale" y nada mas.
preparar_fondo_sddm() {
    local origen="$1"

    echo "  carpeta compartida -> $SDDM_COMPARTIDA"
    if [ "$SOLO_REVISAR" -eq 1 ]; then
        gris "  (haria, como root) install -d -m 2750 -o $USER -g sddm $SDDM_COMPARTIDA"
        gris "  (haria, como root) enlazar fondo.jpg y fondo.mp4 del tema ahi"
        gris "  (haria) generar el fondo con hypr/scripts/sddm-fondo.sh"
        return 0
    fi

    if ! getent group sddm >/dev/null 2>&1; then
        aviso "no existe el grupo sddm: no puedo dejar el fondo automatico"
        return 1
    fi

    raiz install -d -m 2750 -o "$USER" -g sddm "$SDDM_COMPARTIDA"

    # Los enlaces. Se rehacen siempre: si una instalacion vieja dejo ficheros de
    # verdad aqui, hay que sustituirlos o seguirian ganando ellos.
    local f
    for f in fondo.jpg fondo.mp4; do
        raiz ln -sfn "$SDDM_COMPARTIDA/$f" "$SDDM_TEMA/$f"
    done
    hecho "  el tema apunta a la carpeta compartida"

    echo "  fondo: $(basename "$origen")"
    "$REPO/hypr/scripts/sddm-fondo.sh" --forzar
    if [ -f "$SDDM_COMPARTIDA/fondo.jpg" ]; then
        hecho "  fondo generado ($(du -sh "$SDDM_COMPARTIDA" | cut -f1))"
    else
        aviso "no se pudo generar el fondo del login (ffmpeg?)"
    fi
    gris "    a partir de ahora se rehace solo al cambiar de fondo"
}

sddm_instalar() {
    titulo "8. Pantalla de inicio de sesion (SDDM)"

    # El nombre de la funcion NO es `sddm` a proposito: `command -v sddm`
    # encontraria la funcion en vez del programa y esta comprobacion diria que si
    # siempre, hasta en un equipo sin SDDM.
    if ! command -v sddm >/dev/null 2>&1; then
        aviso "SDDM no esta instalado: este tema es solo para el"
        gris "    si usas greetd, ly o gdm, esta pantalla no te sirve"
        gris "    para SDDM:  sudo pacman -S sddm && sudo systemctl enable sddm"
        return
    fi

    # Estar instalado no es estar arrancando.
    if ! systemctl is-enabled sddm.service >/dev/null 2>&1; then
        aviso "SDDM no esta habilitado: el tema se instala, pero no lo veras hasta activarlo"
        gris "    sudo systemctl enable sddm.service"
    fi

    # El modulo QML de video. Se busca la carpeta y no se pregunta a pacman a
    # proposito: asi la comprobacion sigue diciendo la verdad en una distro que
    # no sea Arch.
    if [ ! -d /usr/lib/qt6/qml/QtMultimedia ] && [ ! -d /usr/lib64/qt6/qml/QtMultimedia ]; then
        aviso "falta el modulo QML de video: el fondo saldra quieto (fotograma)"
        gris "    sudo pacman -S qt6-multimedia qt6-multimedia-ffmpeg"
    fi

    # Un `Current=` en /etc/sddm.conf GANA sobre el drop-in, asi que si hay uno
    # el tema se instalaria y no se veria. Mas vale decirlo que dejar a alguien
    # buscando por que no cambia nada.
    if grep -qE '^[[:space:]]*Current[[:space:]]*=' /etc/sddm.conf 2>/dev/null; then
        aviso "/etc/sddm.conf ya fija un tema y ese manda sobre el drop-in"
        gris "    quita esa linea Current= o ponla a: Current=celiuz"
    fi

    echo "  tema -> $SDDM_TEMA"
    raiz install -d -m 755 "$SDDM_TEMA"
    local f
    for f in Main.qml FondoVideo.qml Colores.qml theme.conf metadata.desktop; do
        if [ ! -f "$REPO/sddm/celiuz/$f" ]; then
            aviso "falta $f en el repo: el tema quedaria a medias"
            return
        fi
        raiz install -m 644 "$REPO/sddm/celiuz/$f" "$SDDM_TEMA/$f"
    done
    hecho "  tema copiado"

    local origen=""
    [ -e "$REPO/hypr/wallpapers/current" ] && \
        origen="$(readlink -f "$REPO/hypr/wallpapers/current")"
    if [ -n "$origen" ] && [ -f "$origen" ]; then
        preparar_fondo_sddm "$origen"
    else
        gris "  todavia no hay fondo elegido: la pantalla usara su degradado"
        gris "    elige uno con celiuzpaper y vuelve a pasar ./instalar.sh --sddm"
    fi

    # El drop-in, y no /etc/sddm.conf: ese fichero puede tener ya cosas tuyas
    # (autologin, por ejemplo) y machacarlo seria justo la clase de sorpresa que
    # este repo evita. Un fichero propio se quita borrandolo.
    if [ "$SOLO_REVISAR" -eq 1 ]; then
        gris "  (haria, como root) escribir $SDDM_DROPIN con Current=celiuz"
    else
        raiz install -d -m 755 /etc/sddm.conf.d
        printf '%s\n' \
            "# GENERADO por $REPO/instalar.sh --sddm" \
            "# Se quita con: ./instalar.sh --sddm-quitar" \
            "[Theme]" \
            "Current=celiuz" | raiz tee "$SDDM_DROPIN" >/dev/null
        hecho "  $SDDM_DROPIN escrito"
    fi

    echo
    gris "  pruebalo SIN reiniciar:"
    gris "    sddm-greeter-qt6 --test-mode --theme $SDDM_TEMA"
    gris "  si algo saliera mal en el arranque: Ctrl+Alt+F2, entra por consola y"
    gris "    sudo rm $SDDM_DROPIN"
}

sddm_quitar() {
    titulo "Quitar la pantalla de inicio de sesion"
    raiz rm -f "$SDDM_DROPIN"
    raiz rm -rf "$SDDM_TEMA"
    # La compartida tambien: si no, quedaria una carpeta con tu fondo dentro de
    # /var/lib que ya no usa nadie y que nadie relacionaria con esto.
    raiz rm -rf "$SDDM_COMPARTIDA"
    hecho "  quitado: SDDM vuelve a su tema de siempre en el proximo arranque"
}

# En la instalacion normal no se toca nada de esto (pide root): solo se dice como
# esta, para que nadie tenga que adivinar que existe.
sddm_estado() {
    titulo "8. Pantalla de inicio de sesion"
    if [ -f "$SDDM_TEMA/Main.qml" ]; then
        verde "  el tema celiuz esta puesto"
        # Lo que se ve al arrancar es una COPIA: un git pull con colores o QML
        # nuevos no llega solo (lo vio la laptop, 2026-10-21).
        local f vieja=""
        for f in Main.qml FondoVideo.qml Colores.qml theme.conf metadata.desktop; do
            cmp -s "$REPO/sddm/celiuz/$f" "$SDDM_TEMA/$f" || vieja="$vieja $f"
        done
        [ -z "$vieja" ] || aviso "el tema instalado es una copia VIEJA (${vieja# }): ./instalar.sh --sddm"
        if [ -d "$SDDM_COMPARTIDA" ]; then
            gris "    el fondo se rehace solo al cambiar de fondo"
        else
            aviso "el fondo del login NO se actualiza solo (instalacion antigua)"
            gris "    se arregla pasando una vez:  ./instalar.sh --sddm"
        fi
    else
        echo "  no instalada (es opcional y es lo unico que pide sudo)"
        gris "    ./instalar.sh --sddm"
    fi
}

# --- 9. Celiuz Remoto --------------------------------------------------------
#
# Se deja TODO puesto (la CLI, la app de la PC, su icono y la unidad de
# systemd) pero NO se enciende: abrir un «apagar» hacia fuera es decision de
# cada uno, y se toma desde la app de la PC (remoto/DISEÑO.md). Por eso lo que
# le falte al equipo no es un aviso mientras este apagado: es opcional.

remoto() {
    titulo "9. Celiuz Remoto (manejar el equipo desde el celular)"
    local unidades="$HOME/.config/systemd/user"
    hacer mkdir -p "$HOME/.local/bin" "$DATOS/applications" \
                   "$DATOS/icons/hicolor/scalable/apps" "$unidades"
    enlazar "$REPO/remoto/servidor/celiuz-remoto.py"          "$HOME/.local/bin/celiuz-remoto"
    enlazar "$REPO/remoto/escritorio/celiuz-remoto-config.py" "$HOME/.local/bin/celiuz-remoto-config"
    enlazar "$REPO/remoto/escritorio/celiuz-remoto.desktop"   "$DATOS/applications/celiuz-remoto.desktop"
    enlazar "$REPO/remoto/escritorio/celiuz-remoto.svg"       "$DATOS/icons/hicolor/scalable/apps/celiuz-remoto.svg"
    # La unidad se COPIA, no se enlaza: con una unidad enlazada a un fichero de
    # fuera, `systemctl --user disable` (el boton de apagar de la app) BORRA
    # el enlace, y despues ya no habia servicio que volver a encender. Medido
    # el 2026-10-20. La copia se refresca aqui cada vez que cambie en el repo.
    local nombre unidad
    for nombre in celiuz-remoto.service celiuz-remoto-anclaje.service; do
        unidad="$unidades/$nombre"
        if [ -L "$unidad" ] || ! cmp -s "$REPO/remoto/servidor/$nombre" "$unidad"; then
            hacer rm -f "$unidad"
            hacer install -m 0644 "$REPO/remoto/servidor/$nombre" "$unidad"
            hacer systemctl --user daemon-reload 2>/dev/null
            hecho "  unidad de systemd puesta al dia: $unidad"
        else
            gris "  unidad de systemd al dia: $nombre"
        fi
    done
    # El del anclaje USB SI se enciende: no escucha por la red y solo le pide
    # internet a un celular que ya se lo daba a esta PC (anclaje.py).
    if ! systemctl --user is-enabled --quiet celiuz-remoto-anclaje.service 2>/dev/null; then
        if hacer systemctl --user enable --now celiuz-remoto-anclaje.service 2>/dev/null \
           && [ "$SOLO_REVISAR" -eq 0 ]; then
            hecho "  encendido: que vuelva el internet del celular por USB al reiniciar"
        fi
    fi
    local falta_anclaje
    falta_anclaje="$(python3 -c 'import json,sys; sys.path.insert(0, sys.argv[1])
from celiuz_remoto import anclaje
print("\n".join(anclaje.revisar()["falta"]))' "$REPO/remoto/servidor" 2>/dev/null)"
    if [ -n "$falta_anclaje" ]; then
        while IFS= read -r linea; do
            aviso "internet del celular por USB tras reiniciar: $linea"
        done <<< "$falta_anclaje"
    fi

    local faltan
    faltan="$(python3 "$REPO/remoto/servidor/celiuz-remoto.py" revisar --json 2>/dev/null \
              | python3 -c 'import json,sys; print(" ".join(json.load(sys.stdin)["faltan"]))' 2>/dev/null)"
    if systemctl --user is-enabled --quiet celiuz-remoto.service 2>/dev/null; then
        if systemctl --user is-active --quiet celiuz-remoto.service; then
            verde "  encendido (se apaga desde la app Celiuz Remoto)"
        else
            aviso "Celiuz Remoto esta encendido pero no corre: journalctl --user -u celiuz-remoto"
        fi
        [ -n "$faltan" ] && aviso "a Celiuz Remoto le falta $faltan: ./instalar.sh --remoto-todo (pide sudo)"
    else
        echo "  apagado (es opcional: se enciende desde la app Celiuz Remoto)"
        [ -n "$faltan" ] && gris "    para usarlo hace falta $faltan: ./instalar.sh --remoto-todo (pide sudo)"
    fi
    local opcionales
    opcionales="$(python3 "$REPO/remoto/servidor/celiuz-remoto.py" revisar --json 2>/dev/null \
                  | python3 -c 'import json,sys; print(" ".join(json.load(sys.stdin)["opcionales_faltan"]))' 2>/dev/null)"
    [ -n "$opcionales" ] && gris "    opcional (miniaturas, ver la pantalla): $opcionales — entra en ./instalar.sh --remoto-todo"
    remoto_sistema_estado
    hacer update-desktop-database "$DATOS/applications" 2>/dev/null
    hacer gtk-update-icon-cache -f -t "$DATOS/icons/hicolor" 2>/dev/null
}

# --- 9b. Celiuz Remoto tras reiniciar (PIDE SUDO, aparte) --------------------
#
# Con la PC en la pantalla de inicio (tras un reinicio) el servicio, que es del
# usuario y nunca root, no puede dos cosas: apagarla (sin sesion, polkit pide
# contraseña) y entrar (escribir un autologin de un solo uso en
# /etc/sddm.conf.d y reiniciar SDDM). Esto deja lo minimo para las dos, y nada
# mas (remoto/DISEÑO.md, «Tras reiniciar»):
#   - la regla de polkit, con TU usuario: apagar/reiniciar/suspender, y arrancar
#     UNA unidad, celiuz-remoto-entrar@<tu usuario>.service;
#   - esa unidad y su programa, COPIADOS y de root: si la unidad apuntara al
#     repo, cualquier programa tuyo podria editar lo que ejecuta root;
#   - una linea de tmpfiles que borra el autologin al arrancar, por si un corte
#     de luz lo dejo puesto.
# Como el tema de SDDM: opcional, y lo unico (con --sddm) que pide contraseña.

RS_RAIZ="${CELIUZ_REMOTO_RAIZ_SISTEMA:-}"
RS_PROGRAMA="$RS_RAIZ/usr/local/lib/celiuz-remoto/entrar"
RS_UNIDAD="$RS_RAIZ/etc/systemd/system/celiuz-remoto-entrar@.service"
RS_TMPFILES="$RS_RAIZ/etc/tmpfiles.d/celiuz-remoto.conf"
RS_POLKIT="$RS_RAIZ/etc/polkit-1/rules.d/50-celiuz-remoto.rules"
RS_SDDM_CONF="$RS_RAIZ/etc/sddm.conf"

# El [Autologin] Session= que deja el instalador de CachyOS en /etc/sddm.conf
# pisa la sesion de entrar desde el celular (se entraba SIN uwsm). Lo decide
# remoto/sistema/sddm_conf.py; aqui solo se guarda copia y se pone con sudo.
remoto_sddm_conf() {
    local nuevo codigo
    nuevo="$(mktemp)"
    python3 "$REPO/remoto/sistema/sddm_conf.py" "$RS_SDDM_CONF" > "$nuevo"; codigo=$?
    case "$codigo" in
        0)
            echo "  $RS_SDDM_CONF: se comenta el Session= de [Autologin] (entraria sin uwsm)"
            raiz cp -n "$RS_SDDM_CONF" "$RS_SDDM_CONF.antes-celiuz-remoto"
            raiz install -m 644 -o root -g root "$nuevo" "$RS_SDDM_CONF"
            gris "    la copia de antes: $RS_SDDM_CONF.antes-celiuz-remoto" ;;
        2)  aviso "$RS_SDDM_CONF tiene un autologin tuyo en [Autologin]: no lo toco; al entrar desde el celular mandara SU Session=" ;;
    esac
    rm -f "$nuevo"
}

remoto_sistema_instalar() {
    titulo "Celiuz Remoto tras reiniciar (apagar y entrar desde la pantalla de inicio)"
    if [ "$(id -u)" -eq 0 ]; then
        # La regla lleva TU usuario: con sudo delante, $USER seria root.
        aviso "pásalo como tu usuario, sin sudo delante (ya lo pide él)"
        return
    fi
    if ! command -v sddm >/dev/null 2>&1; then
        aviso "SDDM no esta instalado: apagar sin sesion funcionara, entrar no"
    fi
    local f
    for f in entrar.py celiuz-remoto-entrar@.service celiuz-remoto.tmpfiles celiuz-remoto.rules.in; do
        if [ ! -f "$REPO/remoto/sistema/$f" ]; then
            aviso "falta remoto/sistema/$f en el repo"
            return
        fi
    done
    local regla
    regla="$(mktemp)"
    sed "s/@USUARIO@/$USER/g" "$REPO/remoto/sistema/celiuz-remoto.rules.in" > "$regla"
    raiz install -D -m 755 -o root -g root "$REPO/remoto/sistema/entrar.py" "$RS_PROGRAMA"
    raiz install -D -m 644 -o root -g root "$REPO/remoto/sistema/celiuz-remoto-entrar@.service" "$RS_UNIDAD"
    raiz install -D -m 644 -o root -g root "$REPO/remoto/sistema/celiuz-remoto.tmpfiles" "$RS_TMPFILES"
    raiz install -D -m 644 -o root -g root "$regla" "$RS_POLKIT"
    rm -f "$regla"
    raiz systemctl daemon-reload
    remoto_sddm_conf
    hecho "  puesto: polkit para $USER, la unidad celiuz-remoto-entrar@$USER y su programa"
    gris "    se quita con: ./instalar.sh --remoto-sistema-quitar"
    gris "    para que arranque sin entrar: enciende el servicio desde la ventana (linger)"
}

remoto_sistema_quitar() {
    titulo "Quitar Celiuz Remoto tras reiniciar"
    raiz rm -f "$RS_POLKIT" "$RS_UNIDAD" "$RS_TMPFILES" "$RS_PROGRAMA" \
               "$RS_RAIZ/etc/sddm.conf.d/zz-celiuz-remoto-entrar.conf"
    raiz rmdir "$(dirname "$RS_PROGRAMA")" 2>/dev/null
    raiz systemctl daemon-reload
    hecho "  quitado: sin sesion abierta ya no se puede apagar ni entrar desde el celular"
}

# En la instalacion normal: solo se dice como esta, y si la copia de root se
# quedo vieja respecto al repo (una copia que se separa no avisa sola).
remoto_sistema_estado() {
    if [ ! -f "$RS_UNIDAD" ]; then
        gris "    tras reiniciar, apagar y entrar desde SDDM: ./instalar.sh --remoto-sistema (pide sudo)"
        return
    fi
    if ! cmp -s "$REPO/remoto/sistema/entrar.py" "$RS_PROGRAMA" || \
       ! cmp -s "$REPO/remoto/sistema/celiuz-remoto-entrar@.service" "$RS_UNIDAD" || \
       ! cmp -s "$REPO/remoto/sistema/celiuz-remoto.tmpfiles" "$RS_TMPFILES"; then
        aviso "la parte de root de Celiuz Remoto está vieja: ./instalar.sh --remoto-sistema"
    elif python3 "$REPO/remoto/sistema/sddm_conf.py" "$RS_SDDM_CONF" >/dev/null 2>&1; then
        aviso "$RS_SDDM_CONF fija la sesion sin uwsm para el autologin: ./instalar.sh --remoto-sistema"
    else
        gris "    tras reiniciar: apagar y entrar desde SDDM, puesto"
    fi
}

# --- 9c. Celiuz Remoto, todo de una vez (PIDE SUDO, aparte) -----------------
#
# Al clonar el repo en un equipo nuevo, ir de paquete en paquete según lo pide
# cada pantalla es justo lo que se quiere evitar. Esto deja lo que hace falta
# para usarlo y para compilar la app del celular en una sola pasada:
#   1. los paquetes (la lista es de `celiuz-remoto.py paquetes`, no de aqui:
#      una copia de la lista se separaria sola);
#   2. tailscaled encendido y con el equipo, y la sesion de Tailscale iniciada
#      si aun no lo esta (sale un enlace para abrir en el navegador);
#   3. lo de tras reiniciar (remoto_sistema_instalar).
# NO enciende el servicio: eso se decide en la ventana (remoto/DISEÑO.md).
# El SDK de Android tampoco: no esta en los repos (Android Studio).

remoto_todo() {
    titulo "Celiuz Remoto: todo lo que necesita, de una vez"
    if [ "$(id -u)" -eq 0 ]; then
        aviso "pásalo como tu usuario, sin sudo delante (ya lo pide él)"
        return
    fi
    local paquetes
    paquetes="$(python3 "$REPO/remoto/servidor/celiuz-remoto.py" paquetes)" || {
        aviso "no pude leer la lista de paquetes de celiuz-remoto.py"
        return
    }
    echo "  paquetes: $paquetes"
    # shellcheck disable=SC2086  # la lista va partida a proposito
    raiz pacman -S --needed $paquetes || { aviso "pacman no pudo instalar los paquetes"; return; }

    raiz systemctl enable --now tailscaled || aviso "no pude encender tailscaled"
    if [ "$SOLO_REVISAR" -eq 0 ] && ! tailscale ip -4 >/dev/null 2>&1; then
        echo "  Tailscale sin sesion: abre el enlace que sale y entra con TU cuenta"
        echo "  (la misma que pondras en el celular)"
        raiz tailscale up || aviso "Tailscale sigue sin sesion: sudo tailscale up"
    fi
    tailscale ip -4 >/dev/null 2>&1 && hecho "  Tailscale conectado: $(tailscale ip -4 | head -1)"

    remoto_sistema_instalar

    titulo "Lo que queda (no pide sudo)"
    if [ -d "${ANDROID_HOME:-$HOME/Android/Sdk}/platforms" ]; then
        echo "  1. compila la app del celular:  remoto/app/compilar.sh"
    else
        echo "  1. instala el SDK de Android (Android Studio) y compila: remoto/app/compilar.sh"
    fi
    echo "  2. abre «Celiuz Remoto», enciende el servicio y conecta el celular por cable"
}

# --- Adelante ----------------------------------------------------------------

if [ "$SOLO_REVISAR" -eq 1 ]; then
    printf '\033[1mREVISION — no se va a tocar nada\033[0m\n'
fi

if [ "$SOLO_REMOTO_TODO" -eq 1 ]; then
    remoto_todo
elif [ "$QUITAR_REMOTO_SISTEMA" -eq 1 ]; then
    remoto_sistema_quitar
elif [ "$SOLO_REMOTO_SISTEMA" -eq 1 ]; then
    remoto_sistema_instalar
elif [ "$QUITAR_SDDM" -eq 1 ]; then
    sddm_quitar
elif [ "$SOLO_SDDM" -eq 1 ]; then
    sddm_instalar
elif [ "$SOLO_DOCK" -eq 1 ]; then
    dock
else
    comprobar_dependencias
    desplegar
    saludo_fish
    kitty_iconos
    celiuzpaper
    dock
    maquina_local
    fondo
    pantalla
    sddm_estado
    remoto
    recargar_sesion
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
