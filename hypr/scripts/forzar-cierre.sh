#!/usr/bin/env bash
# hypr/scripts/forzar-cierre.sh — SUPER+SHIFT+Q: cerrar la app de la ventana
# activa aunque no haga caso.
#
# POR QUE EXISTE
# --------------
# SUPER+Q (`hl.dsp.window.close`) solo PIDE a la ventana que se cierre, y la
# app puede no contestar: ONLYOFFICE, el 2026-10-24, con un .pptx abierto, no
# se cerraba por mas veces que se pulsara (sin ningun dialogo a la vista).
# Pedir por las buenas tiene que seguir siendo lo normal —es lo que deja salir
# el «¿guardar cambios?»—, asi que esto va en un atajo aparte.
#
# QUE HACE
# --------
# 1. SIGTERM al proceso de la ventana: «termina», que casi todas atienden (a
#    ONLYOFFICE le basto, en 1 s). Ojo: se lleva TODAS las ventanas de ese
#    proceso, no solo la activa.
# 2. Si a los ESPERA segundos sigue vivo, SIGKILL.
# 3. Avisa de lo que hizo.
#
# Se niega con Hyprland (una ventana mal identificada no puede llevarse la
# sesion), con un pid de otro usuario y si no sabe que ventana es: «no lo se»
# no es una ventana que matar.

set -u

ESPERA="${CELIUZ_FORZAR_ESPERA:-3}"

avisar() {
    notify-send -a "Forzar cierre" -i process-stop "$1" "${2:-}" 2>/dev/null || true
}

ventana="$(hyprctl activewindow -j 2>/dev/null)"
leido="$(python3 -c '
import json, sys
try:
    v = json.loads(sys.stdin.read())
    print(int(v.get("pid", 0)), (v.get("class") or v.get("title") or "la ventana").replace("\n", " "))
except Exception:
    print(0, "")
' <<< "$ventana")"
pid="${leido%% *}"
nombre="${leido#* }"

if ! [ "$pid" -gt 1 ] 2>/dev/null; then
    avisar "No hay ninguna ventana activa que cerrar"
    exit 1
fi
comm=""
read -r comm 2>/dev/null < "/proc/$pid/comm"
case "$comm" in
    Hyprland|hyprland|"")
        avisar "No cierro eso" "El proceso $pid es ${comm:-desconocido}"
        exit 1 ;;
esac
dueno="$(stat -c %u "/proc/$pid" 2>/dev/null)"
if [ "$dueno" != "$(id -u)" ]; then
    avisar "No cierro eso" "$nombre ($pid) no es tuyo"
    exit 1
fi

kill -TERM "$pid" 2>/dev/null
limite=$(( ESPERA * 10 ))
for ((i = 0; i < limite; i++)); do
    kill -0 "$pid" 2>/dev/null || { avisar "Cerrado: $nombre" "No hacía caso a SUPER+Q"; exit 0; }
    sleep 0.1
done
kill -KILL "$pid" 2>/dev/null
avisar "Cerrado a la fuerza: $nombre" "No contestó en ${ESPERA} s; lo que no hubiera guardado se perdió"
exit 0
