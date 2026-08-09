#!/usr/bin/env bash
# hypr/scripts/lock-info.sh — la fila de datos de la pantalla de bloqueo.
#
# Imprime UNA linea con marcado Pango: bateria, teclado y red, cada cosa con su
# glifo en amatista y su valor en claro. hyprlock la pinta con un solo `label`
# que la vuelve a pedir cada pocos segundos (cmd[update:...]).
#
#   󰁹 98%    󰌌 latam    󰤨 wifi
#
# POR QUE UNA SOLA LINEA Y NO TRES ETIQUETAS
# ------------------------------------------
# Tres etiquetas necesitarian tres posiciones en x, y hyprlang no sabe sumar:
# habria que generar `$lock_info_x1`, `x2`, `x3` desde pantalla.py y mantener a
# mano la separacion entre ellas. Con una sola etiqueta la separacion son
# espacios, y ademas las piezas que no aplican DESAPARECEN sin dejar un hueco.
#
# LO QUE NO APLICA NO SE IMPRIME, y eso es el motivo de la mitad de este script:
# el repo se usa en un sobremesa y en un portatil. Sin bateria no se escribe
# "bateria: --", no se escribe nada. Igual con la red si no hay ruta por defecto.
#
# Se prueba a mano con:  hypr/scripts/lock-info.sh

set -u

# LOS COLORES SE LEEN DE LA PALETA, no se escriben aqui.
#
# Este script emite marcado Pango, que no entiende los `$amatista` de hyprlang,
# asi que hay que resolverlos. Pero copiarlos a mano seria una cuarta copia de la
# paleta que se separa sola en cuanto alguien cambie un tono en colores.conf —el
# repo ya tiene un generador (gen-colores.py) justo para no hacer eso—, y quien
# clone el repo y se ponga su color se encontraria la fila de datos con el
# violeta del autor.
#
# El formato de la paleta es `$amatista = rgba(b16cffff)`: hyprlang lo escribe en
# RRGGBBAA, y Pango quiere #RRGGBB, asi que se recortan los dos ultimos digitos.
#
# Si la paleta no se puede leer se usan los tonos de fabrica: la fila de datos
# saldra con el color de siempre, que es mejor que no salir.
PALETA="$HOME/.config/hypr/conf/colores.conf"

color_de() {
    local nombre="$1" respaldo="$2" v=""
    if [ -r "$PALETA" ]; then
        v="$(sed -n "s/^\\\$$nombre[[:space:]]*=[[:space:]]*rgba(\([0-9a-fA-F]\{6\}\)[0-9a-fA-F]\{0,2\}).*/\1/p" \
             "$PALETA" | head -1)"
    fi
    printf '#%s\n' "${v:-$respaldo}"
}

AMATISTA="$(color_de amatista b16cff)"
CLARO="$(color_de luz e4c7ff)"

piezas=()

# --- Bateria -----------------------------------------------------------------
# Solo si hay alguna. `BAT*` y no `BAT0` porque el numero cambia de equipo a
# equipo, y hay portatiles con dos.
for bat in /sys/class/power_supply/BAT*; do
    [ -r "$bat/capacity" ] || continue
    read -r nivel 2>/dev/null < "$bat/capacity" || continue
    estado=""
    [ -r "$bat/status" ] && read -r estado 2>/dev/null < "$bat/status"
    # El glifo dice si esta cargando; el numero, cuanto queda.
    if [ "$estado" = "Charging" ]; then
        glifo="󰂄"
    elif [ "$nivel" -ge 80 ]; then glifo="󰂁"
    elif [ "$nivel" -ge 50 ]; then glifo="󰁿"
    elif [ "$nivel" -ge 20 ]; then glifo="󰁽"
    else                            glifo="󰁺"
    fi
    piezas+=("$glifo ${nivel}%")
    break
done

# --- Teclado -----------------------------------------------------------------
# La distribucion ACTIVA, que no tiene por que ser la primera de la lista: en
# este repo SUPER+DEL alterna entre latam y us. Se le pregunta a Hyprland, que
# durante el bloqueo sigue vivo. Si no contesta, no se escribe nada.
if command -v hyprctl >/dev/null 2>&1; then
    mapa="$(hyprctl -j devices 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    raise SystemExit
for t in d.get("keyboards", []):
    if t.get("main"):
        # "Spanish (Latin American)" no cabe en la franja: se queda la primera
        # palabra, que es lo que distingue una distribucion de otra de un vistazo.
        print((t.get("active_keymap") or "").split("(")[0].strip()[:14])
        break
' 2>/dev/null)"
    [ -n "$mapa" ] && piezas+=("󰌌 $mapa")
fi

# --- Red ---------------------------------------------------------------------
# Se mira la interfaz de la RUTA POR DEFECTO y no una lista de nombres: los
# nombres los pone systemd segun el bus (enp1s0, wlan0, enp22s0f0u1...) y
# adivinarlos es como no mirar. Que sea inalambrica lo dice el propio kernel.
if command -v ip >/dev/null 2>&1; then
    iface="$(ip route show default 2>/dev/null | awk '/^default/{print $5; exit}')"
    if [ -n "${iface:-}" ]; then
        if [ -d "/sys/class/net/$iface/wireless" ]; then
            piezas+=("󰤨 wifi")
        else
            piezas+=("󰈀 cable")
        fi
    fi
fi

# Sin nada que decir, no se imprime ni una linea en blanco: hyprlock dibujaria
# una etiqueta vacia que sigue ocupando su hueco.
[ "${#piezas[@]}" -gt 0 ] || exit 0

salida=""
for p in "${piezas[@]}"; do
    glifo="${p%% *}"
    valor="${p#* }"
    [ -n "$salida" ] && salida+="    "
    salida+="<span foreground=\"$AMATISTA\">$glifo</span> <span foreground=\"$CLARO\">$valor</span>"
done
printf '%s\n' "$salida"
