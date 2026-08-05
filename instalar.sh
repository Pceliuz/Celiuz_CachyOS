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
for arg in "$@"; do
    case "$arg" in
        --revisar|-n)  SOLO_REVISAR=1 ;;
        --dock)        SOLO_DOCK=1 ;;
        --sddm)        SOLO_SDDM=1 ;;
        --sddm-quitar) QUITAR_SDDM=1 ;;
        -h|--help)     sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'; exit 0 ;;
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

    # fuzzel lanza las apps de terminal (nmtui, vim...) con lo que diga su opcion
    # `terminal`, y ahi no sirve ni una ruta con ~ —no la expande— ni una
    # absoluta —seria la del equipo del autor—. Por el PATH si funciona.
    hacer mkdir -p "$HOME/.local/bin"
    enlazar "$REPO/hypr/scripts/terminal.sh" "$HOME/.local/bin/celiuz-terminal"

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
    motivo="$("$REPO/hypr/scripts/lib/maquina.py" --json 2>/dev/null \
              | sed -n 's/.*"motivo": "\(.*\)",/\1/p')"

    if [ "$tipo" = "laptop" ]; then
        conf_maquina='$HOME/.config/hypr/conf/teclado-laptop.conf'
        echo "  equipo: portatil  ($motivo)"
        gris "    se carga conf/teclado-laptop.conf: touchpad, tapa, brillo y el"
        gris "    Ctrl derecho de vuelta en el teclado interno"
    else
        conf_maquina='$HOME/.config/hypr/conf/nada.conf'
        echo "  equipo: sobremesa  ($motivo)"
        gris "    no se carga nada de portatil"
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
EOF
        hecho "  escrito hypr/conf/local.conf"
    fi

    # --- El lado derecho de la barra ---
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
           python3 - "$REPO/waybar/derecha.jsonc" "$REPO/waybar/local.jsonc" <<'PY'
import json, os, re, sys

origen, destino = sys.argv[1], sys.argv[2]
con_bateria = os.environ.get("BATERIA") == "si"

# json no entiende los comentarios de un .jsonc. Se quitan solo los que ocupan
# la linea entera: quitarlos en cualquier posicion se llevaria por delante
# cualquier "//" que apareciera dentro de una cadena.
crudo = open(origen, encoding="utf-8").read()
limpio = "\n".join(l for l in crudo.splitlines() if not l.lstrip().startswith("//"))
modulos = json.loads(limpio)["modules-right"]

if con_bateria and "battery" not in modulos:
    # Junto a los otros indicadores de estado y antes de las notificaciones. Si
    # algun dia ese modulo no esta, va al final: nunca se pierde.
    pos = modulos.index("custom/notificaciones") if "custom/notificaciones" in modulos else len(modulos)
    modulos.insert(pos, "battery")

cabecera = (
    "// waybar/local.jsonc — GENERADO por instalar.sh. NO se versiona.\n"
    "//\n"
    "// El lado derecho de la barra en ESTA maquina. Lo carga config.jsonc por\n"
    "// \"include\", y va el primero: en waybar gana el primero que define una\n"
    "// clave, asi que esto manda sobre waybar/derecha.jsonc.\n"
    "//\n"
    "// Equipo detectado: %s. Si te lo detecto mal, mira el motivo en\n"
    "// hypr/conf/local.conf y vuelve a pasar ./instalar.sh.\n"
    % ("portatil (lleva bateria)" if con_bateria else "sobremesa (sin bateria)")
)
with open(destino, "w", encoding="utf-8") as f:
    f.write(cabecera + json.dumps({"modules-right": modulos}, indent=4, ensure_ascii=False) + "\n")
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
    local resumen
    resumen=$("$REPO/hypr/scripts/lib/pantalla.py" 2>/dev/null)
    if [ -z "$resumen" ]; then
        aviso "no se pudo medir la pantalla (lib/pantalla.py)"
        return
    fi
    printf '%s\n' "$resumen" | sed '/^$/d' | sed 's/^/  /'
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

# --- Adelante ----------------------------------------------------------------

if [ "$SOLO_REVISAR" -eq 1 ]; then
    printf '\033[1mREVISION — no se va a tocar nada\033[0m\n'
fi

if [ "$QUITAR_SDDM" -eq 1 ]; then
    sddm_quitar
elif [ "$SOLO_SDDM" -eq 1 ]; then
    sddm_instalar
elif [ "$SOLO_DOCK" -eq 1 ]; then
    dock
else
    comprobar_dependencias
    desplegar
    celiuzpaper
    dock
    maquina_local
    fondo
    pantalla
    sddm_estado
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
