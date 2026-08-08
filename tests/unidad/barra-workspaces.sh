#!/usr/bin/env bash
# tests/unidad/barra-workspaces.sh — los puntos de los workspaces siguen siendo
# puntos, y el activo sigue siendo una pastilla.
#
# POR QUE EXISTE ESTA PRUEBA
# --------------------------
# Los workspaces de la barra de arriba se dibujan con el FONDO del boton, sin
# texto ("format": "" en config.jsonc). Y en el CSS de GTK el alto de ese fondo
# solo se puede acotar con el MARGEN VERTICAL: los hijos de una caja horizontal
# se estiran a lo alto, `min-height` es un suelo y no existe el techo. Probado
# tambien moviendo la forma a la etiqueta, por si se libraba: se estira igual.
#
# O sea que la forma sale de una RESTA — el alto de la barra menos el margen de
# arriba y el de abajo— y esa resta cruza dos ficheros que no se hablan:
#
#     config.jsonc   "height": 44          el alto de la barra
#     style.css      margin: 17px 5px      el margen de cada punto
#                    min-height: 10px      lo que tiene que quedar en medio
#
# Si alguien mueve el alto de la barra y no el margen, no falla nada, no avisa
# nadie, y los puntos se deforman: medido a 60px de barra salian CAPSULAS
# VERTICALES y el activo un circulo, o sea el diseno exactamente del reves.
#
# Es justo el tipo de fallo que este repo no puede permitirse, porque se clona en
# otras maquinas y ahi nadie va a saber que la culpa era de una resta.
#
# Lo segundo que vigila es el nombre de la clase del workspace vacio. `.occupied`
# estuvo puesto en style.css sin pintar nada: el modulo hyprland/workspaces marca
# los VACIOS (`.empty`), no los llenos. Con numeros casi no se notaba; con puntos,
# un workspace con ventanas se veria igual que uno vacio.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

CONFIG="$REPO/waybar/config.jsonc"
ESTILO="$REPO/waybar/style.css"

titulo "1. La cuenta del punto cuadra con el alto de la barra"

# El alto de la barra, del config.jsonc. Se lee con grep y no con un parser de
# JSON a proposito: el fichero lleva comentarios y aqui solo hace falta un numero.
alto_barra="$(grep -oP '^\s*"height":\s*\K[0-9]+' "$CONFIG" | head -1)"

# El bloque de los puntos: desde `#workspaces button {` hasta su llave de cierre.
# Se acota asi para no confundirse con el `margin` del dock, que tambien vive en
# style.css y ya mordio una vez.
bloque="$(awk '/^#workspaces button \{/{d=1} d{print} d&&/^\}/{exit}' "$ESTILO")"
margen="$(printf '%s\n' "$bloque" | grep -oP 'margin:\s*\K[0-9]+' | head -1)"
punto="$(printf '%s\n' "$bloque" | grep -oP 'min-height:\s*\K[0-9]+' | head -1)"

if [ -z "$alto_barra" ] || [ -z "$margen" ] || [ -z "$punto" ]; then
    fallo "se leen los tres numeros" \
          "alto=[$alto_barra] margen=[$margen] punto=[$punto]"
else
    ok "alto de barra $alto_barra, margen $margen, punto $punto"
    afirmar_igual "$alto_barra" "$((margen * 2 + punto))" \
        "margen x2 + punto = alto de la barra"
fi

titulo "2. El punto es mas ancho que alto, o deja de ser un punto"
# La comprobacion de fondo: da igual como se llegue a los numeros, lo que no
# puede pasar es que la forma salga vertical. Un circulo es tan ancho como alto;
# la pastilla del activo, mas ancha.
ancho="$(printf '%s\n' "$bloque" | grep -oP 'min-width:\s*\K[0-9]+' | head -1)"
activo="$(awk '/^#workspaces button\.active \{/{d=1} d{print} d&&/^\}/{exit}' "$ESTILO" \
          | grep -oP 'min-width:\s*\K[0-9]+' | head -1)"

if [ "$ancho" = "$punto" ]; then
    ok "el punto es redondo ($ancho x $punto)"
else
    fallo "el punto es redondo" "mide $ancho x $punto"
fi

if [ -n "$activo" ] && [ "$activo" -gt "$punto" ]; then
    ok "el activo se estira a pastilla ($activo x $punto)"
else
    fallo "el activo es mas ancho que alto" "mide $activo x $punto"
fi

titulo "3. El workspace vacio se marca con la clase que existe"
afirmar_contiene "$ESTILO" '^#workspaces button\.empty \{' \
    "style.css usa la clase .empty"
afirmar_no_contiene "$ESTILO" '^#workspaces button\.occupied \{' \
    "y no la .occupied, que el modulo de Hyprland no pone nunca"

titulo "4. Los puntos no llevan numero, y el numero no se pierde"
# El "format" vacio es lo que convierte el boton en forma pura. Y con el numero
# fuera, el tooltip es lo unico que queda para saber a cual apuntas. Los dos van
# dentro del bloque de workspaces, asi que se recorta antes de mirar: un
# "tooltip": true suelto de otro modulo no cuenta.
bloque_ws="$TMP/bloque-workspaces.jsonc"
awk '/"hyprland\/workspaces": \{/{d=1} d{print} d&&/^    \},/{exit}' \
    "$CONFIG" > "$bloque_ws"
afirmar_contiene "$bloque_ws" '"format": ""' \
    "los workspaces salen sin texto"
afirmar_contiene "$bloque_ws" '"tooltip": true' \
    "el numero sigue estando en el tooltip"

titulo "5. La etiqueta esta neutralizada"
# Sin esta regla el punto no baja de 18px: el selector `*` del principio de
# style.css le pone 14px a la etiqueta directamente, y una etiqueta vacia no
# ocupa ancho pero si el alto de linea de su fuente.
afirmar_contiene "$ESTILO" '^#workspaces button label \{' \
    "la etiqueta vacia tiene su propia regla"

afirmar_intacta_la_casa_real
resumen
