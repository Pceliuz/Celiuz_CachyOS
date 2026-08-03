#!/usr/bin/env bash
# tests/unidad/generados.sh — los ficheros que escribe un script y nadie edita.
#
# Se prueban sobre una COPIA del repo, no sobre el tuyo. Los generadores sacan su
# destino de la ruta de su propio .py, asi que ejecutarlos aqui reescribiria tus
# ficheros de verdad; con la copia, la prueba no puede tocar nada.
#
# Lo que se busca es el fallo silencioso: estos generadores nunca dan error, solo
# producen algo distinto de lo que esperabas. Un color que falta, un dock con un
# ancho que no cuadra, un icono perdido.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
# Huella de los ficheros del repo de verdad ANTES de nada. Si un generador se
# escapara de la copia, esto lo canta.
HUELLA_REPO="$(find "$REPO/waybar" "$REPO/mako" -type f -exec sha256sum {} + 2>/dev/null | sort | sha256sum)"
COPIA="$(copiar_repo)"

titulo "1. La paleta llega a waybar y a mako"
"$COPIA/hypr/scripts/gen-colores.py" >/dev/null 2>&1
afirmar "genera el CSS de waybar" test -s "$COPIA/waybar/colores.css"
afirmar "genera los colores de mako" test -s "$COPIA/mako/colores"

# Que no se quede ninguna variable por el camino. Es el fallo tipico: anades un
# color a colores.conf, se te olvida el generador, y el CSS lo usa sin existir.
python3 - "$COPIA" > "$TMP/colores.txt" <<'PY'
import re, sys, pathlib
raiz = pathlib.Path(sys.argv[1])
conf = (raiz / "hypr/conf/colores.conf").read_text(encoding="utf-8")
css = (raiz / "waybar/colores.css").read_text(encoding="utf-8")
definidas = set(re.findall(r'^\$(\w+)\s*=', conf, re.M))
en_css = set(re.findall(r'@define-color\s+(\w+)', css))
print("faltan_en_css", ",".join(sorted(definidas - en_css)) or "-")
# Y al reves: que style.css no use un color que nadie define.
style = (raiz / "waybar/style.css").read_text(encoding="utf-8")
# Fuera los comentarios: style.css explica en uno de ellos que se usa
# alpha(@color, 0.35), y eso no es un color, es prosa.
style = re.sub(r'/\*.*?\*/', '', style, flags=re.S)
# Se cogen los nombres con guion incluido (@define-color, no "define" y "color")
# y se descartan las reglas propias de CSS: lo que queda son colores de verdad.
AT_RULES = {"define-color", "import", "media", "keyframes", "supports", "charset"}
usados = set(re.findall(r'@([A-Za-z][\w-]*)', style)) - AT_RULES
print("usados_sin_definir", ",".join(sorted(usados - en_css)) or "-")
PY
afirmar_igual "-" "$(grep '^faltan_en_css ' "$TMP/colores.txt" | cut -d' ' -f2)" \
    "todos los colores de colores.conf llegan al CSS"
afirmar_igual "-" "$(grep '^usados_sin_definir ' "$TMP/colores.txt" | cut -d' ' -f2)" \
    "style.css no usa ningun color que no exista"

titulo "2. Es idempotente (generar dos veces da lo mismo)"
sha1="$(sha256sum "$COPIA/waybar/colores.css" | cut -d' ' -f1)"
"$COPIA/hypr/scripts/gen-colores.py" >/dev/null 2>&1
sha2="$(sha256sum "$COPIA/waybar/colores.css" | cut -d' ' -f1)"
afirmar_igual "$sha1" "$sha2" "regenerar no cambia ni un byte"

titulo "3. El dock se genera de su lista de apps"
# Una lista de mentira: tres apps, con comandos que existen en cualquier sistema
# para que ninguna salga marcada como no instalada.
cat > "$COPIA/waybar/dock-apps.json" <<'JSON'
{
  "apps": [
    {"label": "Uno",  "cmd": "sh",   "icon": "f0a9e"},
    {"label": "Dos",  "cmd": "true", "icon": "f0a9e"},
    {"label": "Tres", "cmd": "ls",   "icon": "f0a9e"}
  ]
}
JSON
"$COPIA/hypr/scripts/gen-dock.py" gen --no-reload >/dev/null 2>&1
afirmar "genera dock.jsonc" test -s "$COPIA/waybar/dock.jsonc"
afirmar_contiene "$COPIA/waybar/dock.jsonc" 'NO EDITAR' "avisa de que no se edita a mano"

python3 - "$COPIA/waybar/dock.jsonc" > "$TMP/dock.txt" <<'PY'
import json, re, sys
crudo = open(sys.argv[1], encoding="utf-8").read()
# El .jsonc lleva comentarios de cabecera; waybar los admite, json.loads no.
limpio = re.sub(r'^\s*//.*$', '', crudo, flags=re.M)
d = json.loads(limpio)
botones = [k for k in d if k.startswith("custom/app")]
print("botones", len(botones))
print("ancho", d.get("width", 0))
print("modulos", len(d.get("modules-center", [])))
PY
leer() { grep "^$1 " "$TMP/dock.txt" | cut -d' ' -f2; }
afirmar_igual "3" "$(leer botones)" "un boton por app"
afirmar_igual "3" "$(leer modulos)" "y los tres colocados en la barra"
# 82 px por app: pastilla de 72 mas 5 de margen a cada lado.
afirmar_igual "246" "$(leer ancho)" "el ancho es 82 por app (3 x 82 = 246)"

titulo "4. Ninguna app se pierde por el camino"
lista="$("$COPIA/hypr/scripts/gen-dock.py" list 2>&1)"
printf '%s' "$lista" > "$TMP/lista.txt"
afirmar_igual "3" "$(grep -c 'Uno\|Dos\|Tres' "$TMP/lista.txt")" "las tres salen al listarlas"
afirmar_no_contiene "$TMP/lista.txt" 'NO INSTALADA' "ninguna sale como no instalada"

titulo "5. No toco tu repo ni tu equipo"
HUELLA_AHORA="$(find "$REPO/waybar" "$REPO/mako" -type f -exec sha256sum {} + 2>/dev/null | sort | sha256sum)"
afirmar_igual "$HUELLA_REPO" "$HUELLA_AHORA" \
    "los ficheros de TU repo no han cambiado (los generadores solo tocaron la copia)"
afirmar_intacta_la_casa_real

resumen
