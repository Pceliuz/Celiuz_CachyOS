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

# canal <nombre> — imprime la ruta del FIFO de ordenes de ese demonio.
canal() {
    local nombre="$1"
    local runtime="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    local sig="${HYPRLAND_INSTANCE_SIGNATURE:-}"

    if [ -n "$sig" ]; then
        printf '%s/%s.%s.fifo\n' "$runtime" "$nombre" "$sig"
        return
    fi

    # Sin firma: si solo hay UNO, ese; si hay varios no se adivina, porque
    # acertar la sesion equivocada es peor que no hacer nada.
    local encontrados=() f
    for f in "$runtime/$nombre".*.fifo; do
        [ -p "$f" ] && encontrados+=("$f")
    done
    if [ "${#encontrados[@]}" -eq 1 ]; then
        printf '%s\n' "${encontrados[0]}"
        return
    fi
    printf '%s/%s.sin-sesion.fifo\n' "$runtime" "$nombre"
}

canal_barras() { canal waybar-autohide; }
canal_fondo()  { canal wallpaper-pause; }
