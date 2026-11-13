#!/usr/bin/env bash
# tests/unidad/systemd-sleep.sh — que el gancho de volver de suspender o
# hibernar recupere SOLO el controlador USB 0000:02:00.0 y solo cuando el
# kernel dejo el rastro del Reinit.
#
# QUE VIGILA, Y POR QUE
# ---------------------
# Al despertar el 2026-11-13 el kernel dijo
#   xhci_hcd 0000:02:00.0: xHC error in resume, USBSTS 0x401, Reinit
#   usb usb1: root hub lost power or was reset
# y el receptor del teclado inalambrico 2.4G (en los puertos de atras, que son
# de ese controlador) no volvio hasta desenchufarlo y volverlo a enchufar.
# El gancho lo vuelve a enlazar solo. Aqui se prueba con un sysfs DE MENTIRA:
# nunca se desenlaza un controlador de verdad desde el laboratorio (§ E-43).

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

# El repo guarda el gancho con extension (el banco de trabajo no acepta rutas
# sin ella); instalar.sh lo copia a /etc/systemd/system-sleep/celiuz-usb-resume,
# que es donde systemd-sleep busca los ganchos.
GANCHO="$REPO/sistema/systemd-sleep/celiuz-usb-resume.sh"
SYSFS="$TMP/sysfs/0000:02:00.0"
DRIVER="$TMP/driver"
TRAZA="$TMP/kernel.log"

# sysfs falso: el dispositivo, su driver (al que apunta el enlace `driver`, como
# en el sysfs de verdad) y los dos ficheros donde se escribe el unbind/bind.
preparar_sysfs() {
    rm -rf "$TMP/sysfs" "$DRIVER"
    mkdir -p "$SYSFS" "$DRIVER"
    ln -s "$DRIVER" "$SYSFS/driver"
    : > "$DRIVER/unbind"
    : > "$DRIVER/bind"
}

correr() {
    SYSFS_DIR="$SYSFS" DIARIO_KERNEL="$TRAZA" bash "$GANCHO" "$@"
}

REINIT='xhci_hcd 0000:02:00.0: xHC error in resume, USBSTS 0x401, Reinit'
# Las marcas del kernel tal como las escribe en el diario real (2026-11-13).
ENTRADA_SUSPEND='PM: suspend entry (deep)'
ENTRADA_HIBERNAR='PM: hibernation: hibernation entry'
SALIDA_SUSPEND='PM: suspend exit'

# --- 1. Con el rastro del Reinit, recupera el controlador del teclado ---------

titulo "1. Con el rastro del Reinit, vuelve a enlazar el controlador del teclado"
preparar_sysfs
binario_falso logger
{
    printf '%s\n' "$ENTRADA_SUSPEND"
    printf '%s\n' "$REINIT"
} > "$TRAZA"
correr post suspend
codigo=$?
afirmar_igual "0" "$codigo" "termina bien"
afirmar_contiene "$DRIVER/unbind" "0000:02:00.0" "desenlaza el 0000:02:00.0"
afirmar_contiene "$DRIVER/bind" "0000:02:00.0" "lo vuelve a enlazar"
afirmar_contiene "$REGISTRO/logger.log" "0000:02:00.0" "deja rastro en el diario"

# --- 2. Lo mismo al volver de hibernar ---------------------------------------

titulo "2. Al volver de hibernar hace lo mismo"
preparar_sysfs
{
    printf '%s\n' "$ENTRADA_HIBERNAR"
    printf '%s\n' "$REINIT"
} > "$TRAZA"
correr post hibernate
afirmar_contiene "$DRIVER/bind" "0000:02:00.0" "hibernar: lo vuelve a enlazar"

# --- 3. Sin el rastro del fallo no toca nada ---------------------------------
# Un unbind/bind a ciegas en cada resume remataria un teclado que estaba bien.

titulo "3. Sin el rastro del fallo no toca el controlador"
preparar_sysfs
printf '%s\n' 'usb 1-1: new low-speed USB device number 3 using xhci_hcd' > "$TRAZA"
correr post suspend
codigo=$?
afirmar_igual "0" "$codigo" "termina bien"
afirmar "no desenlaza nada" test ! -s "$DRIVER/unbind"
afirmar "no enlaza nada" test ! -s "$DRIVER/bind"

# --- 4. El rastro de OTRO controlador no vale ---------------------------------
# En 0000:09:00.x van el microfono fifine y el teclado del bus 5: si se
# desenlazara ese, el fallo se convertiria en dos.

titulo "4. El Reinit de otro controlador no se toca"
preparar_sysfs
printf '%s\n' 'xhci_hcd 0000:09:00.3: xHC error in resume, USBSTS 0x401, Reinit' > "$TRAZA"
correr post suspend
afirmar "no desenlaza nada" test ! -s "$DRIVER/unbind"
afirmar "no enlaza nada" test ! -s "$DRIVER/bind"

# --- 5. En `pre` no hace nada ------------------------------------------------

titulo "5. Antes de dormir (pre) no toca nada"
preparar_sysfs
printf '%s\n' "$REINIT" > "$TRAZA"
correr pre suspend
afirmar "pre: no desenlaza" test ! -s "$DRIVER/unbind"

# --- 6. Sin el dispositivo en sysfs no hace nada -----------------------------

titulo "6. Sin el dispositivo en sysfs no hace nada"
preparar_sysfs
printf '%s\n' "$REINIT" > "$TRAZA"
SYSFS_DIR="$TMP/no-existe" DIARIO_KERNEL="$TRAZA" bash "$GANCHO" post suspend
codigo=$?
afirmar_igual "0" "$codigo" "termina bien sin el dispositivo"
afirmar "no enlaza nada" test ! -s "$DRIVER/bind"

# --- 7. Un Reinit de un despertar ANTERIOR no se toca ------------------------
# rastro_kernel mira solo lo posterior a la ultima salida de suspender/hibernar.
# Si mirara todo el arranque, tras el primer despertar con fallo el
# 'xHC error in resume' se queda en el diario y cada despertar siguiente
# reenlazaria el controlador aunque haya vuelto bien: se cortarian la camara,
# el mando y el receptor sin motivo.

titulo "7. Un Reinit de un ciclo viejo no se toca"
preparar_sysfs
{
    printf '%s\n' "$ENTRADA_SUSPEND"
    printf '%s\n' "$REINIT"
    printf '%s\n' "$SALIDA_SUSPEND"
    printf '%s\n' "$ENTRADA_SUSPEND"
    printf '%s\n' 'usb 1-1: new low-speed USB device number 3 using xhci_hcd'
    printf '%s\n' "$SALIDA_SUSPEND"
} > "$TRAZA"
correr post suspend
codigo=$?
afirmar_igual "0" "$codigo" "termina bien"
afirmar "no desenlaza nada" test ! -s "$DRIVER/unbind"
afirmar "no enlaza nada" test ! -s "$DRIVER/bind"

# --- 8. El Reinit de ESTE despertar si se toca -------------------------------
# El orden real del diario del 2026-11-13: la entrada, el error y la salida.

titulo "8. El Reinit de este despertar (entre la entrada y la salida) si se toca"
preparar_sysfs
binario_falso logger
{
    printf '%s\n' "$ENTRADA_SUSPEND"
    printf '%s\n' "$REINIT"
    printf '%s\n' "$SALIDA_SUSPEND"
} > "$TRAZA"
correr post suspend
codigo=$?
afirmar_igual "0" "$codigo" "termina bien"
afirmar_contiene "$DRIVER/unbind" "0000:02:00.0" "desenlaza el 0000:02:00.0"
afirmar_contiene "$DRIVER/bind" "0000:02:00.0" "lo vuelve a enlazar"

afirmar_intacta_la_casa_real
resumen
