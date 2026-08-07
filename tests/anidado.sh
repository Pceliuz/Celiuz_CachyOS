#!/usr/bin/env bash
# tests/anidado.sh — un Hyprland anidado que NO puede tocar tu sesion.
#
#   ./tests/anidado.sh                     lo levanta y se queda; Ctrl+C lo tumba
#   ./tests/anidado.sh hyprctl configerrors  corre eso DENTRO y recoge la casa
#
# POR QUE EXISTE
# --------------
# El anidado «a pelo» que documentaba el CLAUDE.md —levantar Hyprland y ya— NO
# es un cajon de arena: usa TU $HOME, asi que corre TU autostart.conf. Y ahi hay
# cinco exec-once, de los que tres muerden a la sesion de verdad:
#
#   wallpaper.sh          empieza con `pkill -x mpvpaper` y
#                         `pkill -f wallpaper-paus[e].py`. No distinguen de que
#                         sesion es cada proceso: te dejan el escritorio REAL sin
#                         fondo y sin el demonio que lo pausa.
#   systemctl --user      hypridle y mako son unidades del USUARIO, no de la
#                         sesion grafica. Arrancarlas desde aqui manosea las de
#                         verdad — y hypridle es quien bloquea tu pantalla.
#   waybar-autohide.py    rehace $XDG_RUNTIME_DIR/waybar-autohide.<firma>.fifo, y con el
#                         se queda sordo el demonio bueno.
#
# Paso el 2026-08-04: un anidado levantado para mirar cuatro cosas dejo el
# escritorio sin fondo, y el sintoma no aparecio hasta horas despues.
#
# COMO SE AISLA
# -------------
#   1. $HOME desechable. Es lo que hace casi todo el trabajo, porque el repo
#      referencia sus trozos por `$HOME/.config/hypr/...` (regla del CLAUDE.md):
#      cambiando $HOME cambia el arbol de configuracion ENTERO.
#   2. Una COPIA del repo, enlazada igual que la enlaza instalar.sh. Igual y no
#      "parecido": los scripts sacan su raiz con realpath(), asi que atraviesan
#      el enlace, y sin el resolverian mal.
#   3. autostart.conf NEUTRALIZADO en la copia. Nada arranca solo. Lo que quieras
#      dentro, lo lanzas tu con el WAYLAND_DISPLAY que imprime este script.
#   4. $XDG_RUNTIME_DIR propio, para que ningun FIFO ni socket pise a los de tu
#      sesion. El socket de Wayland del PADRE se enlaza dentro, que es lo unico
#      que hace falta de fuera para poder anidar.
#
# LO QUE SIGUE SIN CUBRIR
# -----------------------
# `pkill` mata por NOMBRE de proceso, y eso no lo aisla ningun $HOME. Si lanzas
# a mano algo que mate por nombre —wallpaper.sh, sin ir mas lejos—, se llevara
# por delante lo de tu sesion igual. Aqui no se arranca nada solo; a partir de
# ahi, mira lo que lanzas.

set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/.." && pwd)"

_rojo()  { printf '\033[31m%s\033[0m\n' "$*"; }
_verde() { printf '\033[32m%s\033[0m\n' "$*"; }
_gris()  { printf '\033[90m%s\033[0m\n' "$*"; }
_negrita() { printf '\033[1m%s\033[0m\n' "$*"; }

case "${1:-}" in
    -h|--help|--ayuda)
        sed -n '2,45p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
        exit 0
        ;;
esac

# --- Antes de nada ------------------------------------------------------------
if ! command -v Hyprland >/dev/null 2>&1; then
    _rojo "No encuentro Hyprland."
    exit 2
fi
if [ -z "${WAYLAND_DISPLAY:-}" ]; then
    _rojo "Esto se lanza desde DENTRO de una sesion Wayland: el anidado se dibuja"
    _rojo "en una ventana de la de fuera. Desde un TTY no hay donde ponerlo."
    exit 2
fi

# El runtime y el display de FUERA, guardados antes de pisarlos.
PADRE_RUNTIME="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
PADRE_WL="$WAYLAND_DISPLAY"
CASA_REAL="$HOME"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/anidado-XXXXXX")"
HYPR_PID=""
INST=""

# --- Recoger, pase lo que pase ------------------------------------------------
limpiar() {
    local codigo=$?
    trap - EXIT INT TERM HUP

    if [ -n "$HYPR_PID" ] && kill -0 "$HYPR_PID" 2>/dev/null; then
        kill "$HYPR_PID" 2>/dev/null
        # Se le espera de verdad: si se borra el $HOME mientras aun vive, sus
        # ultimos suspiros escriben en rutas que ya no estan.
        for _ in $(seq 1 50); do
            kill -0 "$HYPR_PID" 2>/dev/null || break
            sleep 0.1
        done
        kill -9 "$HYPR_PID" 2>/dev/null
    fi

    # Huerfanos: lo que se lanzo con `setsid` dentro del anidado NO muere con el
    # compositor (asi sobrevivio el demonio del fondo el 2026-08-04). Se buscan
    # por la firma de ESTA instancia, que es la unica forma fiable de saber de
    # quien es cada proceso.
    if [ -n "$INST" ]; then
        local sobran=()
        local pid
        for pid in /proc/[0-9]*; do
            grep -qz "HYPRLAND_INSTANCE_SIGNATURE=$INST" "$pid/environ" 2>/dev/null \
                && sobran+=("${pid#/proc/}")
        done
        if [ "${#sobran[@]}" -gt 0 ]; then
            _gris "  quedaban ${#sobran[@]} proceso(s) del anidado; los cierro"
            kill "${sobran[@]}" 2>/dev/null
        fi
    fi

    # Borrar la casa desechable, con el freno puesto: solo lo que creo mktemp.
    case "$TMP" in
        */anidado-??????)
            [ "$TMP" != "$CASA_REAL" ] && rm -rf "$TMP"
            ;;
        *)
            _rojo "  no borro «$TMP»: no tiene la pinta de lo que yo creo"
            ;;
    esac
    exit "$codigo"
}
trap limpiar EXIT INT TERM HUP

# --- 1. La casa desechable ----------------------------------------------------
export HOME="$TMP/casa"
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_CACHE_HOME="$HOME/.cache"
export XDG_DATA_HOME="$HOME/.local/share"
export XDG_STATE_HOME="$HOME/.local/state"
export XDG_RUNTIME_DIR="$TMP/run"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_DATA_HOME" \
         "$XDG_STATE_HOME" "$XDG_RUNTIME_DIR" "$HOME/.local/bin"
chmod 700 "$XDG_RUNTIME_DIR"

# El socket de Wayland de FUERA, enlazado dentro: es lo unico que el anidado
# necesita de la sesion de verdad (dibujarse en ella). Un enlace vale, porque
# conectarse a un socket unix atraviesa los enlaces.
#
# Se le pone un nombre que NO se parezca a los de libwayland, y no es un capricho:
# con el nombre de fuera («wayland-1») el compositor anidado se apropia de el.
# libwayland da por libre un socket que no tenga su `.lock` al lado, lo BORRA y
# se pone en su sitio — o sea que el enlace al padre desaparece y ademas el
# display de dentro acaba llamandose igual que el de fuera, que es la mejor
# manera de creer que apuntas a un sitio mientras apuntas al otro. Medido.
ENLACE_PADRE="wayland-padre"
case "$PADRE_WL" in
    /*) ENLACE_PADRE="$PADRE_WL" ;;   # ruta absoluta: se usa tal cual
    *)  ln -sfn "$PADRE_RUNTIME/$PADRE_WL" "$XDG_RUNTIME_DIR/$ENLACE_PADRE" ;;
esac

# --- 2. La copia del repo, enlazada como la enlaza instalar.sh ----------------
mkdir -p "$TMP/repo"
tar -C "$REPO" --exclude=.git --exclude='hypr/wallpapers/*' -cf - . \
    | tar -C "$TMP/repo" -xf - 2>/dev/null
for pieza in hypr waybar fuzzel mako mpvpaper; do
    [ -d "$TMP/repo/$pieza" ] && ln -sfn "$TMP/repo/$pieza" "$XDG_CONFIG_HOME/$pieza"
done
ln -sfn "$TMP/repo/hypr/scripts/terminal.sh" "$HOME/.local/bin/celiuz-terminal"

# --- 3. Nada arranca solo -----------------------------------------------------
cat > "$TMP/repo/hypr/conf/autostart.conf" <<'EOF'
# autostart.conf — VACIADO POR tests/anidado.sh. No es el del repo.
#
# En un anidado los exec-once del de verdad muerden la sesion de fuera:
# wallpaper.sh mata mpvpaper y su demonio POR NOMBRE, y los `systemctl --user`
# de hypridle y mako tocan las unidades del usuario, que son las mismas.
#
# Lo que necesites aqui dentro, lanzalo a mano con el WAYLAND_DISPLAY que
# imprime el script.
EOF

# Si esta caja nunca paso el instalador no hay local.conf, y aunque un `source`
# que falta solo deja un aviso, `$conf_maquina` sin definir dejaria el ultimo
# source apuntando a la nada.
if [ ! -f "$TMP/repo/hypr/conf/local.conf" ]; then
    cat > "$TMP/repo/hypr/conf/local.conf" <<'EOF'
# GENERADO por tests/anidado.sh porque esta caja no tiene uno propio.
$terminal = kitty
$conf_maquina = $HOME/.config/hypr/conf/nada.conf
EOF
fi

# --- 4. Arriba ----------------------------------------------------------------
# WAYLAND_DISPLAY apunta al enlace al padre: es donde se dibuja la ventana del
# anidado. El display de DENTRO lo crea el compositor y se averigua despues.
# AQ_NO_MODIFIERS=1 lo pide esta NVIDIA, o se queda en `bo null` sin monitor.
env -u HYPRLAND_INSTANCE_SIGNATURE AQ_NO_MODIFIERS=1 \
    WAYLAND_DISPLAY="$ENLACE_PADRE" \
    Hyprland > "$TMP/hyprland.log" 2>&1 &
HYPR_PID=$!

for _ in $(seq 1 100); do
    INST="$(ls "$XDG_RUNTIME_DIR/hypr" 2>/dev/null | head -1)"
    [ -n "$INST" ] && [ -S "$XDG_RUNTIME_DIR/hypr/$INST/.socket.sock" ] && break
    kill -0 "$HYPR_PID" 2>/dev/null || break
    INST=""
    sleep 0.2
done

if [ -z "$INST" ]; then
    _rojo "El anidado no llego a levantar. Ultimas lineas de su log:"
    tail -15 "$TMP/hyprland.log" >&2
    exit 1
fi

# El display de DENTRO: el unico socket del runtime desechable que no es el
# enlace al padre. Como el enlace se llama aparte, aqui no hay ambigüedad.
NESTED_WL="$(cd "$XDG_RUNTIME_DIR" && ls -d wayland-* 2>/dev/null \
             | grep -v '\.lock$' | grep -vx "$ENLACE_PADRE" | head -1)"

# La punteria, comprobada por el script y no a ojo: si esto contesta, `-i $INST`
# habla con el anidado y no con tu sesion.
if ! hyprctl -i "$INST" version >/dev/null 2>&1; then
    _rojo "Levanto, pero no contesta por su socket de control."
    exit 1
fi

_verde "Anidado en pie."
_gris  "  casa desechable : $HOME"
_gris  "  instancia       : $INST"
_gris  "  display de dentro: ${NESTED_WL:-(no lo encontre)}"
_gris  "  su log          : $TMP/hyprland.log  (se borra al salir)"

# --- 5. O corre lo que te pidieron, o se queda esperando -----------------------
if [ "$#" -gt 0 ]; then
    _negrita ""
    _negrita "Dentro del anidado: $*"
    WAYLAND_DISPLAY="${NESTED_WL:-$PADRE_WL}" HYPRLAND_INSTANCE_SIGNATURE="$INST" "$@"
    exit $?
fi

cat <<EOF

Para lanzar algo DENTRO, en otra terminal:

    export XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR
    export WAYLAND_DISPLAY=$NESTED_WL
    export HYPRLAND_INSTANCE_SIGNATURE=$INST

WAYLAND_DISPLAY es lo que mete un programa grafico en el anidado;
HYPRLAND_INSTANCE_SIGNATURE solo le dice a hyprctl con quien hablar. Poner
solo la segunda es creer que apuntas aqui mientras apuntas a tu sesion.

Ctrl+C para tumbarlo y borrar la casa desechable.
EOF

wait "$HYPR_PID"
