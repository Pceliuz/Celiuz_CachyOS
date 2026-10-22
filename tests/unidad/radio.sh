#!/usr/bin/env bash
# tests/unidad/radio.sh — `./instalar.sh --radio`: el wifi rtw88 y el Bluetooth
# USB sin ahorro de energia (sistema/radio/).
#
# QUE VIGILA
# ----------
# - Que solo pone lo que el equipo tiene: con wifi rtw88, lo del wifi; con un
#   Bluetooth USB, lo del Bluetooth; sin ninguno, nada.
# - Que despierta el adaptador Bluetooth en el acto (power/control = on).
# - Que la instalacion normal avisa si falta, y deja de avisar al ponerlo.
# - Que --radio-quitar lo quita.
# /etc y /sys son carpetas de mentira (CELIUZ_RADIO_RAIZ, CELIUZ_RADIO_SYS), y
# sudo e install, binarios falsos: no se toca el sistema.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
binario_falso sudo 0 '"$@"; exit $?'
binario_falso install 0 'mkdir -p "$(dirname "${@: -1}")" && cp "${@: -2:1}" "${@: -1}"; exit $?'
binario_falso nmcli 0

# Las funciones de la seccion, sin correr el instalador entero.
cargar() {
    {
        sed -n '/^raiz() {/,/^}/p' "$REPO/instalar.sh"
        sed -n '/^# --- 9d\. /,/^# --- Adelante/p' "$REPO/instalar.sh"
    } > "$TMP/radio_fn.sh"
    SOLO_REVISAR=0; REPO="$REPO"; AVISOS=()
    titulo() { :; }; gris() { :; }; hecho() { :; }
    aviso() { echo "AVISO: $1"; }
    . "$TMP/radio_fn.sh"
}

# un_sys <con-rtw88 0|1> <con-btusb 0|1> → un /sys de mentira
un_sys() {
    local s="$TMP/sys-$1$2"
    rm -rf "$s"
    mkdir -p "$s/bus/pci/drivers/rtw88_8821ce" "$s/bus/usb/drivers/btusb" \
             "$s/devices/pci0000:00/usb1/1-7/1-7:1.0" "$s/devices/pci0000:00/usb1/1-7/power"
    echo auto > "$s/devices/pci0000:00/usb1/1-7/power/control"
    [ "$1" = 1 ] && mkdir -p "$s/bus/pci/drivers/rtw88_8821ce/0000:02:00.0"
    [ "$2" = 1 ] && ln -s "$s/devices/pci0000:00/usb1/1-7/1-7:1.0" "$s/bus/usb/drivers/btusb/1-7:1.0"
    echo "$s"
}

ETC="$TMP/raiz"
export CELIUZ_RADIO_RAIZ="$ETC"

titulo "1. La laptop: wifi rtw88 y Bluetooth USB"
export CELIUZ_RADIO_SYS="$(un_sys 1 1)"
afirmar_igual "rtw88 btusb" "$( (cargar; radio_necesita) | paste -sd' ')" "ve las dos cosas"
avisos="$( (cargar; radio_estado) )"
afirmar_igual "2" "$(grep -c '^AVISO:' <<< "$avisos")" "sin poner, la instalacion normal avisa de las dos"
( cargar; radio_instalar ) >/dev/null 2>&1
for f in etc/modprobe.d/rtw88-sin-ahorro.conf etc/NetworkManager/conf.d/wifi-sin-ahorro.conf etc/modprobe.d/btusb-sin-ahorro.conf; do
    afirmar "puesto /$f, igual que el del repo" cmp -s "$REPO/sistema/radio/$(basename "$f")" "$ETC/$f"
done
afirmar_igual "on" "$(cat "$CELIUZ_RADIO_SYS/devices/pci0000:00/usb1/1-7/power/control")" \
    "el Bluetooth despierto en el acto"
afirmar_igual "" "$( (cargar; radio_estado) )" "puesto, ya no avisa"
echo "# tocado a mano" >> "$ETC/etc/modprobe.d/btusb-sin-ahorro.conf"
afirmar "una copia que se separo del repo vuelve a avisar" \
    grep -q "AVISO: el Bluetooth" <<< "$( (cargar; radio_estado) )"
( cargar; radio_quitar ) >/dev/null 2>&1
afirmar_igual "" "$(find "$ETC" -type f)" "--radio-quitar lo quita todo"

titulo "2. Solo lo que hay"
rm -rf "$ETC"
export CELIUZ_RADIO_SYS="$(un_sys 0 1)"
( cargar; radio_instalar ) >/dev/null 2>&1
afirmar_igual "btusb-sin-ahorro.conf" "$(find "$ETC" -type f -printf '%f\n')" \
    "con Bluetooth USB y otro wifi: solo lo del Bluetooth (el ahorro del wifi se queda)"
rm -rf "$ETC"
export CELIUZ_RADIO_SYS="$(un_sys 0 0)"
afirmar_igual "" "$( (cargar; radio_estado) | grep AVISO)" "sin nada de eso: ni un aviso"
( cargar; radio_instalar ) >/dev/null 2>&1
afirmar_igual "" "$(find "$ETC" -type f 2>/dev/null)" "y no pone nada"

titulo "3. Los ficheros del repo"
afirmar "rtw88: sin ahorro profundo ni ASPM" grep -qx 'options rtw88_core disable_lps_deep=1' "$REPO/sistema/radio/rtw88-sin-ahorro.conf"
afirmar "NetworkManager: powersave = 2 (apagado)" grep -qx 'wifi.powersave = 2' "$REPO/sistema/radio/wifi-sin-ahorro.conf"
afirmar "btusb: sin suspension" grep -qx 'options btusb enable_autosuspend=0' "$REPO/sistema/radio/btusb-sin-ahorro.conf"

afirmar_intacta_la_casa_real
resumen
