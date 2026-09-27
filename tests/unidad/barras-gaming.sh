#!/usr/bin/env bash
# tests/unidad/barras-gaming.sh — el modo gaming quita las barras, y ni el
# supervisor ni DESBLOQUEAR LA PANTALLA las resucitan mientras dure.
#
# EL FALLO QUE VIGILA. El modo gaming mata las barras igual que el bloqueo
# (`lock`), pero son estados distintos: si compartieran el mismo, bloquear la
# pantalla a mitad de partida y desbloquearla (`unlock`, que las relanza) las
# devolveria con el modo puesto. Y al reves: salir del modo con la pantalla
# bloqueada no puede levantarlas por encima del bloqueo.
#
# Mismo montaje que barras-supervisor.sh: el demonio de verdad con un `waybar`
# de mentira, y los procesos se cuentan por PID de padre, nunca por nombre.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

COPIA="$(copiar_repo)"
DEMONIO="$COPIA/hypr/scripts/waybar-autohide.py"
mkdir -p "$XDG_RUNTIME_DIR/hypr/prueba-gaming"
binario_falso notify-send
cat > "$FALSOS/waybar" <<EOF
#!/usr/bin/env bash
exec sleep 600
EOF
chmod +x "$FALSOS/waybar"

# Vivos, no zombis: una waybar terminada sigue siendo hija hasta que la recogen.
hijos() { ps -o pid=,stat= --ppid "$1" 2>/dev/null | awk '$2 !~ /^Z/ {print $1}'; }
vivas() { hijos "$PID_DEMONIO" | grep -c . || true; }
matar_demonio() {
    [ -n "${PID_DEMONIO:-}" ] || return 0
    for h in $(ps -o pid= --ppid "$PID_DEMONIO" 2>/dev/null); do kill "$h" 2>/dev/null; done
    kill "$PID_DEMONIO" 2>/dev/null
    wait "$PID_DEMONIO" 2>/dev/null
    PID_DEMONIO=""
}
trap 'matar_demonio; limpiar_entorno' EXIT INT TERM

FIFO="$XDG_RUNTIME_DIR/waybar-autohide.sin-sesion.fifo"
orden() { printf '%s\n' "$*" > "$FIFO"; sleep 2.5; }

python3 "$DEMONIO" >"$TMP/demonio.log" 2>&1 &
PID_DEMONIO=$!
sleep 3
afirmar "el demonio arranca con su FIFO" test -p "$FIFO"
afirmar_igual "4" "$(vivas)" "cuatro waybar al empezar"

titulo "Entrar al modo"
orden gaming-on dock:gaming-on
afirmar_igual "0" "$(vivas)" "gaming-on las quita todas"
sleep 2
afirmar_igual "0" "$(vivas)" "el supervisor no las resucita"

titulo "Bloquear y desbloquear a mitad de partida"
orden lock dock:lock
orden unlock dock:unlock
afirmar_igual "0" "$(vivas)" "desbloquear NO las devuelve con el modo puesto"

titulo "Salir del modo"
orden gaming-off dock:gaming-off
afirmar_igual "4" "$(vivas)" "gaming-off las levanta"

titulo "Salir del modo con la pantalla bloqueada"
orden gaming-on dock:gaming-on
orden lock dock:lock
orden gaming-off dock:gaming-off
afirmar_igual "0" "$(vivas)" "no salen por encima del bloqueo"
orden unlock dock:unlock
afirmar_igual "4" "$(vivas)" "vuelven al desbloquear"

afirmar "el demonio sigue vivo" kill -0 "$PID_DEMONIO"
matar_demonio
afirmar_intacta_la_casa_real
resumen
