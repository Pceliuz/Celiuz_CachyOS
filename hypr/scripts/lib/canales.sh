# hypr/scripts/lib/canales.sh — gemelo en shell de lib/canales.py.
#
# Se hace con `source`, no se ejecuta. Lo usan `barras.sh` y `lock.sh`.
#
# El porque de todo esto —que dos sesiones de Hyprland vivas compartian el FIFO
# de ordenes y se lo robaban en bucle— esta contado en `canales.py`, que es donde
# hay que leerlo. Aqui solo esta la misma convencion de nombre, en shell, porque
# `lock.sh` corre en cada bloqueo y arrancar un python para preguntar la ruta
# seria pagarlo en el peor momento.
#
# Que la convencion este escrita dos veces es una deuda a la fuerza (no hay
# manera de compartir codigo entre bash y python), y por eso
# `tests/unidad/canales.sh` compara las dos implementaciones caso por caso.
# Si tocas una, toca la otra.

# canal <nombre> [ext] — imprime la ruta del canal de esa pieza para esta sesion.
# `ext` es "fifo" (un canal de ordenes) o "sock" (el IPC de mpv).
canal() {
    local nombre="$1" ext="${2:-fifo}"
    local runtime="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    local sig="${HYPRLAND_INSTANCE_SIGNATURE:-}"

    if [ -n "$sig" ]; then
        printf '%s/%s.%s.%s\n' "$runtime" "$nombre" "$sig" "$ext"
        return
    fi

    # Sin firma: si solo hay UNO, ese; si hay varios no se adivina, porque
    # acertar la sesion equivocada es peor que no hacer nada. Y se exige que sea
    # del tipo que toca, no solo que se llame asi.
    local prueba="-p"
    [ "$ext" = "sock" ] && prueba="-S"
    local encontrados=() f
    for f in "$runtime/$nombre".*."$ext"; do
        [ "$prueba" "$f" ] && encontrados+=("$f")
    done
    if [ "${#encontrados[@]}" -eq 1 ]; then
        printf '%s\n' "${encontrados[0]}"
        return
    fi
    printf '%s/%s.sin-sesion.%s\n' "$runtime" "$nombre" "$ext"
}

canal_barras() { canal waybar-autohide; }
canal_fondo()  { canal wallpaper-pause; }
socket_mpv()   { canal mpvpaper sock; }

# --- Procesos de ESTA sesion --------------------------------------------------
#
# `pkill -x mpvpaper` y `pgrep -x hyprlock` matan y cuentan POR NOMBRE, y eso no
# distingue de que sesion es cada proceso: con dos sesiones vivas del mismo
# usuario, una se lleva por delante el fondo de la otra, o cree que ya hay un
# bloqueo puesto porque lo tiene la de al lado. Es la trampa que ya mordio de
# verdad el 2026-08-04 con el Hyprland anidado.
#
# El discriminante es la firma de la instancia, que Hyprland le pone en el
# entorno a todo lo que lanza. Se lee de /proc y no hace falta nada instalado.

# pids_de_esta_sesion <nombre-exacto> — PIDs de ese programa lanzados por NUESTRO
# Hyprland.
#
# SIN FIRMA NO DEVUELVE NADA, y eso es a proposito. La tentacion es «si no se
# sabe, no filtres», y eso es exactamente el `pkill -x` que se venia a quitar:
# cualquier sitio sin la variable —un TTY, un script, una prueba— pasaria a matar
# los procesos de TODAS tus sesiones. Mejor no reclamar nada como propio que
# reclamarlo todo. Y para quien llama, el lado seguro cae solo: lock.sh acaba
# bloqueando (en vez de no bloquear por ver el hyprlock de otra sesion) y
# wallpaper.sh acaba lanzando un demonio (en vez de quedarse sin ninguno).
pids_de_esta_sesion() {
    local nombre="$1" sig="${HYPRLAND_INSTANCE_SIGNATURE:-}" pid comm
    [ -n "$sig" ] || return 0
    for d in /proc/[0-9]*; do
        pid="${d##*/}"
        read -r comm 2>/dev/null < "$d/comm" || continue
        [ "$comm" = "$nombre" ] || continue
        tr '\0' '\n' 2>/dev/null < "$d/environ" \
            | grep -qxF "HYPRLAND_INSTANCE_SIGNATURE=$sig" || continue
        printf '%s\n' "$pid"
    done
}

# pids_con_marca <nombre-exacto> <marca> — PIDs de ese programa que lleven `marca`
# en su linea de comandos.
#
# Es la forma buena de dar con NUESTRO mpvpaper: la marca es la ruta de su socket
# IPC, que ya lleva la firma dentro, asi que la propia linea de comandos dice de
# que sesion es. Mas exacto que mirar el entorno, y sin el modo de fallo de
# arriba: sin firma la marca es la ruta "sin-sesion", que no la lleva nadie.
pids_con_marca() {
    local nombre="$1" marca="$2" pid comm linea
    [ -n "$marca" ] || return 0
    for d in /proc/[0-9]*; do
        pid="${d##*/}"
        read -r comm 2>/dev/null < "$d/comm" || continue
        [ "$comm" = "$nombre" ] || continue
        linea="$(tr '\0' ' ' 2>/dev/null < "$d/cmdline")" || continue
        case "$linea" in *"$marca"*) printf '%s\n' "$pid" ;; esac
    done
}

# pids_de_esta_sesion_cmd <trozo-de-la-linea-de-comandos> — igual, pero mirando
# la linea entera. Hace falta para los scripts: el `comm` de
# `python3 wallpaper-pause.py` es "python3", no el nombre del script.
#
# Ojo, la trampa clasica: un `pgrep -f` normal SE ENCUENTRA A SI MISMO y al
# shell que lo lanza, porque el patron aparece en su propia linea de comandos.
# Aqui se descartan el propio proceso y su padre por PID, que es lo unico que no
# se puede confundir.
pids_de_esta_sesion_cmd() {
    local patron="$1" sig="${HYPRLAND_INSTANCE_SIGNATURE:-}" pid linea
    [ -n "$sig" ] || return 0   # sin firma no se reclama nada; ver arriba
    for d in /proc/[0-9]*; do
        pid="${d##*/}"
        [ "$pid" = "$$" ] && continue
        [ "$pid" = "$PPID" ] && continue
        linea="$(tr '\0' ' ' 2>/dev/null < "$d/cmdline")" || continue
        case "$linea" in *"$patron"*) ;; *) continue ;; esac
        tr '\0' '\n' 2>/dev/null < "$d/environ" \
            | grep -qxF "HYPRLAND_INSTANCE_SIGNATURE=$sig" || continue
        printf '%s\n' "$pid"
    done
}
