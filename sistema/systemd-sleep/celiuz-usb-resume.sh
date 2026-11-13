#!/usr/bin/env bash
# /etc/systemd/system-sleep/celiuz-usb-resume.sh
#
# Tras volver de suspender o hibernar, mira si el kernel dejo el rastro del
# fallo conocido del controlador USB xHCI del chipset AMD 500 (0000:02:00.0):
#
#   xhci_hcd 0000:02:00.0: xHC error in resume, USBSTS 0x401, Reinit
#   usb usb1: root hub lost power or was reset
#
# Ese controlador es el de los puertos de atras, donde esta el receptor del
# teclado inalambrico 2.4G. Cuando el resume lo reinicia, el receptor no vuelve
# solo y Parzival tiene que desenchufarlo y volverlo a enchufar (2026-11-13).
# Aqui se hace solo: unbind y bind de ESE controlador y de ninguno mas. En
# 0000:09:00.x van el microfono fifine y el teclado del bus 5; tocarlos seria
# cambiar un fallo por dos.
#
# Se llama desde systemd-sleep, que pasa "pre" o "post" como $1 y la accion
# (suspend/hibernate) como $2. Solo se actua en "post": en "pre" el
# controlador esta bien.
#
# Lo instala instalar.sh en /etc/systemd/system-sleep/. Para las pruebas,
# SYSFS_DIR y DIARIO_KERNEL se pueden apuntar a un sysfs y un diario de mentira
# (tests/unidad/systemd-sleep.sh): NUNCA se desenlaza un controlador real desde
# el laboratorio (§ E-43).

set -uo pipefail

ACCION="${1:-}"
[ "$ACCION" = "post" ] || exit 0

DISPOSITIVO="0000:02:00.0"
SYSFS_DIR="${SYSFS_DIR:-/sys/bus/pci/devices/$DISPOSITIVO}"
DIARIO_KERNEL="${DIARIO_KERNEL:-}"

# Sin el controlador en sysfs no hay nada que reenlazar.
[ -d "$SYSFS_DIR" ] || exit 0

# El rastro del fallo: del diario de mentira si se dio (pruebas), del diario
# del kernel de este arranque si no.
rastro_kernel() {
    if [ -n "$DIARIO_KERNEL" ]; then
        cat "$DIARIO_KERNEL" 2>/dev/null
    else
        journalctl -b 0 -k --no-pager 2>/dev/null
    fi | awk '/PM: (suspend|hibernation) exit|PM: restore/ { buf = ""; next }
              { buf = buf $0 "\n" }
              END { printf "%s", buf }'
}

# Solo se toca si el kernel dijo que ESTE controlador tuvo el Reinit
# EN ESTE DESPERTAR (después de la última salida de suspensión/hibernación).
rastro_kernel | grep -Fq "xhci_hcd $DISPOSITIVO: xHC error in resume" || exit 0

# El driver es el enlace `driver` del dispositivo, como en el sysfs de verdad.
DRIVER="$(readlink -f "$SYSFS_DIR/driver" 2>/dev/null)"
if [ -z "$DRIVER" ] || [ ! -w "$DRIVER/unbind" ] || [ ! -w "$DRIVER/bind" ];
 then
    logger -t celiuz-usb-resume \
        "el kernel reinicio $DISPOSITIVO pero no encuentro su driver" 2>/dev/null
    exit 0
fi

logger -t celiuz-usb-resume \
    "el kernel reinicio $DISPOSITIVO al despertar; lo vuelvo a enlazar" 2>/dev/null

printf '%s' "$DISPOSITIVO" > "$DRIVER/unbind" 2>/dev/null
sleep 1
printf '%s' "$DISPOSITIVO" > "$DRIVER/bind" 2>/dev/null

exit 0
