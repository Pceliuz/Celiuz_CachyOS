#!/usr/bin/env bash
# tests/unidad/canales.sh — los FIFO de ordenes son de UNA sesion, y las dos
# implementaciones de la convencion dicen lo mismo.
#
# POR QUE EXISTE ESTA PRUEBA
# --------------------------
# `$XDG_RUNTIME_DIR` es del USUARIO, no de la sesion. Mientras los dos demonios
# pusieron ahi un `waybar-autohide.fifo` y un `wallpaper-pause.fifo` a secas, dos
# sesiones de Hyprland vivas a la vez —dos TTY, un cambio rapido de usuario—
# compartian el fichero: se lo robaban en bucle (cada demonio rehace el suyo si
# ve que no es el suyo) y las ordenes acababan donde les tocara. Lo peor no era
# el `SUPER+C`, era el `lock`/`unlock` de la pantalla de bloqueo.
#
# Y hay una segunda razon, mas sutil: la convencion del nombre esta escrita DOS
# VECES —`lib/canales.py` y `lib/canales.sh`— porque bash y python no comparten
# codigo, y `lock.sh` corre en cada bloqueo y no puede pagar un arranque de
# python. Dos copias de una regla se separan solas. Esta prueba las compara caso
# por caso: si alguien toca una y no la otra, falla aqui y no en el escritorio.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

PY="$REPO/hypr/scripts/lib/canales.py"
SH="$REPO/hypr/scripts/lib/canales.sh"

# via_py / via_sh — la ruta que da cada implementacion, con el entorno de ahora.
via_py() { python3 "$PY" "$1"; }
via_sh() {
    # El verbo de la CLI no siempre se llama igual que la funcion de shell: el de
    # mpv no es un canal de ordenes sino un socket, y las dos implementaciones lo
    # llaman `socket_mpv`.
    local fn="canal_$1"
    [ "$1" = "mpv" ] && fn="socket_mpv"
    bash -c ". '$SH'; $fn"
}

# afirmar_gemelos — las dos dicen lo mismo, y ademas lo esperado.
afirmar_gemelos() {
    local verbo="$1" esperado="$2" titulo="$3"
    local p s
    p="$(via_py "$verbo")"
    s="$(via_sh "$verbo")"
    afirmar_igual "$esperado" "$p" "$titulo (python)"
    afirmar_igual "$p" "$s" "$titulo: shell dice lo mismo"
}

export XDG_RUNTIME_DIR="$TMP/run"
mkdir -p "$XDG_RUNTIME_DIR"

titulo "1. Con firma de sesion, el canal lleva la firma"
export HYPRLAND_INSTANCE_SIGNATURE="firma_de_prueba_1"
afirmar_gemelos barras "$XDG_RUNTIME_DIR/waybar-autohide.firma_de_prueba_1.fifo" \
    "el canal de las barras"
afirmar_gemelos fondo "$XDG_RUNTIME_DIR/wallpaper-pause.firma_de_prueba_1.fifo" \
    "el canal del fondo"

titulo "2. Dos sesiones distintas NO comparten canal"
# Es el fallo entero en una linea: si estas dos rutas coinciden, dos sesiones
# vivas se pisan las ordenes.
primero="$(via_py barras)"
export HYPRLAND_INSTANCE_SIGNATURE="firma_de_prueba_2"
segundo="$(via_py barras)"
if [ "$primero" != "$segundo" ]; then
    ok "cada sesion tiene el suyo"
else
    fallo "dos sesiones no comparten canal" "las dos dan $primero"
fi

titulo "3. Sin firma y con UN solo canal, se usa ese"
# El caso de llamar a mano desde un TTY o por ssh: no hay variable, pero solo hay
# un escritorio, y adivinarlo ahi es lo que cualquiera querria.
unset HYPRLAND_INSTANCE_SIGNATURE
mkfifo "$XDG_RUNTIME_DIR/waybar-autohide.la-unica.fifo"
afirmar_gemelos barras "$XDG_RUNTIME_DIR/waybar-autohide.la-unica.fifo" \
    "sin firma y con uno solo"

titulo "4. Sin firma y con VARIOS, no se adivina"
# Acertar la sesion equivocada es peor que no hacer nada: mandarias el `unlock` a
# la pantalla de bloqueo de otra sesion. Se devuelve una ruta que no existe, y
# quien escribe lo comprueba con `test -p`.
mkfifo "$XDG_RUNTIME_DIR/waybar-autohide.la-otra.fifo"
ruta="$(via_py barras)"
afirmar_igual "$XDG_RUNTIME_DIR/waybar-autohide.sin-sesion.fifo" "$ruta" \
    "con varios no elige ninguno"
afirmar_igual "$ruta" "$(via_sh barras)" "y el shell tampoco"
if [ ! -p "$ruta" ]; then
    ok 'y esa ruta no existe, asi que el "test -p" de quien escribe lo para'
else
    fallo "la ruta de rendicion no debe existir" "existe: $ruta"
fi

titulo "5. Un fichero normal con ese nombre no cuenta como canal"
# `echo x > ruta-sin-fifo` CREA un fichero normal y sale con 0: es la trampa
# clasica de este repo. Esa basura no debe pasar por un canal valido.
rm -f "$XDG_RUNTIME_DIR"/waybar-autohide.*.fifo
: > "$XDG_RUNTIME_DIR/waybar-autohide.basura.fifo"
ruta="$(via_py barras)"
afirmar_igual "$XDG_RUNTIME_DIR/waybar-autohide.sin-sesion.fifo" "$ruta" \
    "un fichero normal no es un canal (python)"
afirmar_igual "$ruta" "$(via_sh barras)" "un fichero normal no es un canal (shell)"

titulo "6. barras.sh no escribe a ciegas"
# Sin canal tiene que fallar RUIDOSAMENTE. Antes, un `echo` a una ruta sin FIFO
# creaba un fichero normal, salia con 0, y el atajo parecia funcionar.
binario_falso notify-send
rm -f "$XDG_RUNTIME_DIR"/waybar-autohide.*
export HYPRLAND_INSTANCE_SIGNATURE="firma_sin_demonio"
if BARRAS_CALLADO=1 "$REPO/hypr/scripts/barras.sh" show 2>"$TMP/barras.err"; then
    fallo "barras.sh falla si no hay canal" "salio con 0 sin haber demonio"
else
    ok "barras.sh falla si no hay canal, en vez de fingir que funciona"
fi
if [ -e "$XDG_RUNTIME_DIR/waybar-autohide.firma_sin_demonio.fifo" ]; then
    fallo "no deja basura con el nombre del canal" \
          "creo un fichero donde deberia haber un FIFO"
else
    ok "y no deja un fichero normal con el nombre del canal"
fi

titulo "7. Con canal, la orden llega entera"
mkfifo "$XDG_RUNTIME_DIR/waybar-autohide.firma_sin_demonio.fifo"
( timeout 5 cat "$XDG_RUNTIME_DIR/waybar-autohide.firma_sin_demonio.fifo" \
    > "$TMP/recibido.txt" ) &
LECTOR=$!
sleep 0.3
BARRAS_CALLADO=1 "$REPO/hypr/scripts/barras.sh" show dock:show
wait "$LECTOR" 2>/dev/null
afirmar_contiene "$TMP/recibido.txt" "show" "la orden llega"
afirmar_contiene "$TMP/recibido.txt" "dock:show" "y las dos ordenes viajan juntas"

titulo "8. El socket de mpvpaper tambien es de una sola sesion"
export HYPRLAND_INSTANCE_SIGNATURE="firma_de_prueba_1"
afirmar_gemelos mpv "$XDG_RUNTIME_DIR/mpvpaper.firma_de_prueba_1.sock" \
    "el socket de mpv"

titulo "9. Sin firma NO se reclama nada como propio"
# Esta es la parte que mas cerca estuvo de salir mal, y por eso tiene prueba.
#
# La tentacion al escribir `pids_de_esta_sesion` es «si no hay firma, no
# filtres». Eso es EXACTAMENTE el `pkill -x` que se venia a quitar: cualquier
# sitio sin la variable —un TTY, un script, esta misma prueba— pasaria a matar
# los procesos de TODAS tus sesiones. Y no es hipotetico: con esa version,
# `pids_de_esta_sesion mpvpaper` desde el entorno de pruebas devolvia el
# mpvpaper REAL del usuario, que es el fondo de su escritorio.
#
# La regla es al reves: sin firma no se reclama nada. Para quien llama, el lado
# seguro cae solo (lock.sh acaba bloqueando, wallpaper.sh acaba lanzando).
unset HYPRLAND_INSTANCE_SIGNATURE
# `sleep` sirve de cobaya: existe seguro y no es de nadie.
sleep 30 & COBAYA=$!
sleep 0.3
salida="$(bash -c ". '$SH'; pids_de_esta_sesion sleep")"
if [ -z "$salida" ]; then
    ok "sin firma no devuelve NINGUN proceso (ni los ajenos)"
else
    fallo "sin firma no se reclama nada" \
          "devolvio PIDs con el entorno sin firma: $salida"
fi
salida="$(bash -c ". '$SH'; pids_de_esta_sesion_cmd sleep")"
if [ -z "$salida" ]; then
    ok "y la variante que mira la linea de comandos, igual"
else
    fallo "sin firma no se reclama nada (por linea de comandos)" \
          "devolvio: $salida"
fi

titulo "10. Se reconoce a los propios por una marca en su linea de comandos"
# Es como wallpaper.sh distingue SU mpvpaper: por la ruta de su socket, que ya
# lleva la firma dentro. Aqui la cobaya es un sleep con un argumento marcado.
salida="$(bash -c ". '$SH'; pids_con_marca sleep 30")"
afirmar_igual "$COBAYA" "$salida" "encuentra al que lleva la marca"
salida="$(bash -c ". '$SH'; pids_con_marca sleep marca-que-no-lleva-nadie")"
if [ -z "$salida" ]; then
    ok "y no devuelve nada si la marca no aparece"
else
    fallo "una marca ausente no debe encontrar a nadie" "devolvio: $salida"
fi
kill "$COBAYA" 2>/dev/null; wait "$COBAYA" 2>/dev/null

titulo "11. No toco nada de tu equipo"
afirmar_intacta_la_casa_real

resumen
