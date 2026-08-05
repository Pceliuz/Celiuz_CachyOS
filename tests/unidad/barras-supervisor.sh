#!/usr/bin/env bash
# tests/unidad/barras-supervisor.sh — el demonio de las barras NO puede apagarse
# porque se le caiga una waybar.
#
# EL FALLO QUE VIGILA. Durante un tiempo el bucle de waybar-autohide.py acababa
# en `if not all(bar.alive()): cleanup()`: si UNA de las cuatro instancias moria,
# el demonio mataba a las otras tres y se apagaba. Y no quedaba nadie que las
# levantara —el propio atajo de reinicio empieza hablando con el demonio—, asi
# que el escritorio se quedaba sin barra y sin dock hasta CERRAR SESION, que es
# cuando `exec-once` vuelve a correr. Medido el 2026-08-05: matando una sola de
# las cuatro, a los 4 s no quedaba ninguna capa waybar viva.
#
# COMO SE PRUEBA SIN HYPRLAND. El demonio pregunta al compositor por un socket
# de UNIX; si no contesta, `query()` devuelve cadena vacia y `visible_real()`
# devuelve None, o sea que update() se abstiene de tocar nada. La supervision,
# que es lo que se prueba aqui, no depende del compositor: es mirar si el
# proceso hijo sigue vivo. Basta con un `waybar` de mentira.
#
# NUNCA se cuentan procesos por NOMBRE. El waybar falso se llama `waybar` igual
# que el de verdad, asi que un `pgrep waybar` cogeria las cuatro instancias de la
# sesion del autor y un `pkill` se las llevaria por delante. Se cuentan y se
# matan por PID, y solo los hijos del demonio de la prueba.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

COPIA="$(copiar_repo)"
DEMONIO="$COPIA/hypr/scripts/waybar-autohide.py"

# hypr_socket() se va a la unica instancia que encuentre cuando no hay
# HYPRLAND_INSTANCE_SIGNATURE (preparar_entorno la quita). Sin ninguna carpeta
# el demonio saldria con un mensaje antes de empezar. El socket no existe y no
# hace falta: lo que se prueba es la supervision, no el dialogo.
mkdir -p "$XDG_RUNTIME_DIR/hypr/prueba-supervisor"

binario_falso notify-send

# Un waybar que se queda quieto hasta que lo maten. `exec` para que el PID que
# ve el demonio sea el del proceso que de verdad sigue vivo.
cat > "$FALSOS/waybar" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$REGISTRO/waybar.log"
exec sleep 600
EOF
chmod +x "$FALSOS/waybar"

# hijos <pid> — PIDs de los hijos directos, uno por linea. Por PPID, no por
# nombre (ver la cabecera).
hijos() { ps -o pid= --ppid "$1" 2>/dev/null | tr -d ' '; }
cuantos_hijos() { hijos "$1" | grep -c . || true; }

matar_demonio() {
    [ -n "${PID_DEMONIO:-}" ] || return 0
    for h in $(hijos "$PID_DEMONIO"); do kill "$h" 2>/dev/null; done
    kill "$PID_DEMONIO" 2>/dev/null
    wait "$PID_DEMONIO" 2>/dev/null
    PID_DEMONIO=""
}
trap 'matar_demonio; limpiar_entorno' EXIT INT TERM


titulo "1. Una waybar caida se relanza, y el demonio sigue en pie"

python3 "$DEMONIO" >"$TMP/demonio.log" 2>&1 &
PID_DEMONIO=$!
sleep 3

afirmar "el demonio arranca" kill -0 "$PID_DEMONIO"
afirmar_igual "4" "$(cuantos_hijos "$PID_DEMONIO")" "levanta las cuatro instancias"

antes="$(hijos "$PID_DEMONIO" | sort | tr '\n' ' ')"
victima="$(hijos "$PID_DEMONIO" | head -1)"
kill "$victima"
sleep 3

afirmar "el demonio NO se apaga al morir una" kill -0 "$PID_DEMONIO"
afirmar_igual "4" "$(cuantos_hijos "$PID_DEMONIO")" "vuelve a haber cuatro instancias"

despues="$(hijos "$PID_DEMONIO" | sort | tr '\n' ' ')"
afirmar "la muerta ya no esta en la lista" test ! -d "/proc/$victima"
afirmar "y la lista de hijos ha cambiado" test "$antes" != "$despues"

matar_demonio


titulo "2. Una que se cae SIEMPRE no deja al demonio en bucle"

# Ahora el waybar falso se muere nada mas arrancar. Sin freno, el demonio
# lanzaria procesos para siempre, diez veces por segundo.
cat > "$FALSOS/waybar" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$REGISTRO/waybar.log"
exit 1
EOF
chmod +x "$FALSOS/waybar"
: > "$REGISTRO/waybar.log"

python3 "$DEMONIO" >"$TMP/demonio2.log" 2>&1 &
PID_DEMONIO=$!
sleep 6

afirmar "el demonio sigue vivo aunque no consiga ninguna barra" \
        kill -0 "$PID_DEMONIO"

# REINTENTOS_MAX es 5 por barra y hay dos barras, con dos instancias cada una:
# el techo son 4 arranques iniciales + 2 barras x 5 reintentos x 2 instancias.
# Lo que importa no es el numero exacto, sino que PARE.
intentos="$(veces_llamado waybar)"
afirmar "deja de reintentar (no es un bucle infinito)" test "$intentos" -le 30
_gris "    arranques de waybar contados: $intentos"

sleep 3
afirmar_igual "$intentos" "$(veces_llamado waybar)" \
        "y una vez rendido ya no lanza mas"
afirmar "avisa por notificacion de que se rinde" test "$(veces_llamado notify-send)" -ge 1

matar_demonio


titulo "3. No toco nada de tu equipo"
afirmar_intacta_la_casa_real

resumen
