#!/usr/bin/env bash
# tests/run.sh — lanza todas las pruebas del repo.
#
#   ./tests/run.sh            todas
#   ./tests/run.sh bloqueo    solo las que lleven ese texto en el nombre
#
# QUE SE PRUEBA Y QUE NO
# ----------------------
# Se prueba todo lo que es logica: de donde salen los fondos, que medidas toca
# usar en cada pantalla, que generan los generadores, y la secuencia entera de la
# pantalla de bloqueo (con un binario falso, sin bloquear nunca).
#
# NO se prueba el ASPECTO. Que una capa de GTK se dibuje donde toca, que el velo
# tape lo que debe o que un icono salga centrado no lo puede comprobar un script:
# eso se mira con un Hyprland anidado y una captura. Estas pruebas cubren la
# mitad que sí se puede automatizar, que es la que se rompe en silencio.
#
# SE PUEDE LANZAR EN CUALQUIER SITIO. No hace falta Hyprland corriendo, ni Steam,
# ni Wallpaper Engine, ni un monitor concreto: cada prueba se monta un HOME de
# mentira. Vale desde un TTY, por SSH o en integracion continua.
#
# Lo unico que necesita es bash, python3 y las herramientas que ya pide el
# escritorio (ffmpeg para los fondos). Si falta algo, la prueba lo dice.

set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FILTRO="${1:-}"

verde() { printf '\033[32m%s\033[0m\n' "$*"; }
rojo()  { printf '\033[31m%s\033[0m\n' "$*"; }
gris()  { printf '\033[90m%s\033[0m\n' "$*"; }

# Requisitos minimos: mejor decirlo claro que fallar en la comprobacion 14.
faltan=()
for prog in bash python3 grep sed find tar sha256sum; do
    command -v "$prog" >/dev/null 2>&1 || faltan+=("$prog")
done
if [ "${#faltan[@]}" -gt 0 ]; then
    rojo "Faltan herramientas basicas: ${faltan[*]}"
    exit 2
fi

PRUEBAS=()
while IFS= read -r p; do PRUEBAS+=("$p"); done < <(
    find "$DIR/unidad" "$DIR/e2e" -maxdepth 1 -name '*.sh' -type f 2>/dev/null | sort
)

if [ "${#PRUEBAS[@]}" -eq 0 ]; then
    rojo "No encontre ninguna prueba en $DIR"
    exit 2
fi

BIEN=0
MAL=0
FALLIDAS=()

for prueba in "${PRUEBAS[@]}"; do
    nombre="$(basename "$prueba" .sh)"
    grupo="$(basename "$(dirname "$prueba")")"
    if [ -n "$FILTRO" ] && [[ "$nombre" != *"$FILTRO"* ]]; then
        continue
    fi
    printf '\n\033[1m═══ %s/%s ═══\033[0m\n' "$grupo" "$nombre"
    if bash "$prueba"; then
        BIEN=$((BIEN + 1))
    else
        MAL=$((MAL + 1))
        FALLIDAS+=("$grupo/$nombre")
    fi
done

printf '\n\033[1m%s\033[0m\n' "════════════════════════════════════"
if [ "$MAL" -eq 0 ]; then
    verde "  $BIEN pruebas, todas bien"
    gris  "  (el aspecto no se prueba aqui: eso va con un Hyprland anidado)"
    exit 0
fi
rojo "  $MAL de $((BIEN + MAL)) pruebas fallaron:"
for f in "${FALLIDAS[@]}"; do rojo "    - $f"; done
exit 1
