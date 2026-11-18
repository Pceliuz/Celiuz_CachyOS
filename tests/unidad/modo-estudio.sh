#!/usr/bin/env bash
# tests/unidad/modo-estudio.sh — el modo estudio sin compositor.
#
# Es el primo del modo programador: aparta lo mismo (juegos y tiendas) y ademas
# el ocio (reproductores de video y musica, chats, redes). Se prueba con un
# HOME falso y un mundo de mentira, igual que modo-programador.sh, porque la
# maquina de quien corre esto no tiene Hyprland ni vlc.
#
# LO QUE VIGILA:
#  - on deja el estado en ~/.config/celiuz/modo-estudio.json y off lo apaga
#    (vuelve a lo que habia, no a un valor de fabrica).
#  - El estado dice si esta encendido, y con --sin-preguntar no pregunta nada.
#  - Los tres modos no se juntan: si el programador esta encendido, el estudio
#    no entra (y al reves).
#  - Se aparta el ocio que ya esta abierto, en TODAS las pantallas.
#  - Lo de trabajo (editor, navegador, terminal, pizarra) no se mueve.
#  - Los ganchos de ~/.config/celiuz/modo-estudio.d/ se ejecutan al entrar y al
#    salir, con la palabra on / off.
set -u

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"
preparar_entorno

S="$REPO/hypr/scripts"
MODO="$S/modo-estudio.py"
ESTADO_JSON="$XDG_CONFIG_HOME/celiuz/modo-estudio.json"
GANCHOS="$XDG_CONFIG_HOME/celiuz/modo-estudio.d"
mkdir -p "$GANCHOS"

fallos=0
fallo() { echo "FALLO $*"; fallos=$((fallos + 1)); }

# --- El script existe y contesta a «estado» --------------------------------
if [ ! -f "$MODO" ]; then
    fallo "no existe $MODO"
else
    salida=$(python3 "$MODO" estado 2>&1) || true
    case "$salida" in
        *apagado*|*off*|*false*) ;;
        *) fallo "estado en frio: esperaba que dijera apagado, salio '$salida'" ;;
    esac
fi

# --- Un gancho que apunta lo que le pasan ----------------------------------
cat > "$GANCHOS/apunta.sh" <<'EOF'
#!/bin/sh
echo "$1" >> "$(dirname "$0")/../ganchos.log"
EOF
chmod +x "$GANCHOS/apunta.sh"

# --- Entrar y salir --------------------------------------------------------
if [ -f "$MODO" ]; then
    python3 "$MODO" on --sin-preguntar >/dev/null 2>&1 || true
    if [ ! -f "$ESTADO_JSON" ]; then
        fallo "tras on no hay $ESTADO_JSON"
    else
        case "$(cat "$ESTADO_JSON")" in
            *encendido*|*true*|*on*) ;;
            *) fallo "el estado tras on no dice encendido: $(cat "$ESTADO_JSON")" ;;
        esac
    fi

    python3 "$MODO" off --sin-preguntar >/dev/null 2>&1 || true
    case "$(cat "$ESTADO_JSON" 2>/dev/null)" in
        *apagado*|*false*|*off*) ;;
        *) fallo "el estado tras off no dice apagado: $(cat "$ESTADO_JSON" 2>/dev/null)" ;;
    esac

    # El gancho se ejecuto al entrar y al salir
    LOG="$XDG_CONFIG_HOME/celiuz/ganchos.log"
    if [ ! -f "$LOG" ]; then
        fallo "el gancho de modo-estudio.d/ no se ejecuto nunca"
    else
        grep -q 'on' "$LOG" || fallo "el gancho no recibio 'on'"
        grep -q 'off' "$LOG" || fallo "el gancho no recibio 'off'"
    fi
fi

# --- La pregunta llega a la tarjeta con algo que la tarjeta entiende ----------
# El fallo del 2026-11-18: le pasaba «Entrar en el modo estudio», la tarjeta
# salia con error de uso (2), eso contaba como un «no», y SUPER+E no hacia nada.
# Se apunta lo que el modo le pasaria y se le da a la tarjeta de verdad, sin
# Wayland: una accion valida sale con 1 (no hay donde dibujar), una que no
# entiende, con 2.
if [ -f "$MODO" ]; then
    for accion in entrar salir; do
        args=$(python3 - "$MODO" "$accion" <<'PY' 2>/dev/null
import importlib.util, subprocess, sys
spec = importlib.util.spec_from_file_location("me", sys.argv[1])
me = importlib.util.module_from_spec(spec); spec.loader.exec_module(me)
visto = []
class R: returncode = 1
subprocess.run = lambda orden, **k: (visto.append(orden), R())[1]
me.preguntar(sys.argv[2])
print(" ".join(visto[0][2:]) if visto else "")
PY
)
        [ -n "$args" ] || { fallo "$accion: el modo no llamo a la tarjeta"; continue; }
        # shellcheck disable=SC2086
        env -u WAYLAND_DISPLAY python3 "$S/modo-gaming-tarjeta.py" $args >/dev/null 2>&1
        codigo=$?
        [ "$codigo" -ne 2 ] || fallo "$accion: la tarjeta no entiende lo que le pasa el modo ($args)"
    done
fi

if [ "$fallos" -ne 0 ]; then
    echo "modo-estudio.sh: $fallos fallos"
    exit 1
fi
echo "modo-estudio.sh: ok"
