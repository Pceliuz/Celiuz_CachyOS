#!/usr/bin/env bash
#
# notificaciones.sh — el modulo de notificaciones de la barra.
#
# Devuelve JSON para waybar (formato `return-type: json`): texto, clase CSS y
# tooltip. La clase es lo que style.css usa para pintarlo, asi que el color de
# cada estado se decide alli y no aqui.
#
# Estados:
#   normal     nada pendiente
#   pendiente  hay notificaciones sin descartar
#   dnd        "no molestar" puesto
#
# OJO: `makoctl list` NO devuelve JSON pese a lo que sugiere el nombre — es
# texto para leer, con una linea "Notification N: titulo" por cada una. Por eso
# se cuenta con grep y no se parsea como estructura.

set -uo pipefail

if ! command -v makoctl >/dev/null 2>&1; then
    printf '{"text":"","tooltip":"mako no esta instalado","class":"apagado"}\n'
    exit 0
fi

# Si mako no esta corriendo, makoctl falla. No es un error que haya que gritar:
# se ensena el icono apagado y ya.
if ! modo="$(makoctl mode 2>/dev/null)"; then
    printf '{"text":"","tooltip":"mako no esta corriendo","class":"apagado"}\n'
    exit 0
fi

pendientes="$(makoctl list 2>/dev/null | grep -c '^Notification ')" || pendientes=0

# Glifos Nerd Font. SE ESCRIBEN CON chr() DESDE PYTHON, no a mano: estan en
# el rango de Uso Privado (U+F0xx) y las herramientas de texto los aplastan
# — la primera version dejo la campana normal y la de pendientes con EL MISMO
# codepoint, asi que los dos estados se veian identicos.
# Comprobar con:  python3 -c "print(hex(ord(open('...').read()[n])))"
CAMPANA=$''        # campana de contorno: todo tranquilo
CAMPANA_PUNTO=$''  # campana rellena: hay algo esperando
CAMPANA_MUDA=$''   # campana tachada: no molestar

if grep -qx 'no-molestar' <<<"$modo"; then
    texto="$CAMPANA_MUDA"
    clase="dnd"
    if (( pendientes > 0 )); then
        tooltip="No molestar · $pendientes esperando"
    else
        tooltip="No molestar"
    fi
elif (( pendientes > 0 )); then
    texto="$CAMPANA_PUNTO $pendientes"
    clase="pendiente"
    tooltip="$pendientes sin leer"
else
    texto="$CAMPANA"
    clase="normal"
    tooltip="Sin notificaciones"
fi

tooltip="$tooltip
SUPER+N descartar · SUPER+CTRL+N recuperar
SUPER+ALT+N no molestar"

# El tooltip lleva saltos de linea, que en JSON tienen que ir escapados.
tooltip="${tooltip//$'\n'/\\n}"

printf '{"text":"%s","tooltip":"%s","class":"%s"}\n' "$texto" "$tooltip" "$clase"
