#!/usr/bin/env bash
# tests/unidad/paleta-bloqueo.sh — en la pantalla de bloqueo no queda ningun
# color que se haya separado de la paleta.
#
# POR QUE EXISTE
# --------------
# `hyprlock.conf` es el fichero del repo con MAS colores escritos a mano, y no
# por descuido: hyprlang no sabe derivar un alfa de una variable, asi que una
# sombra al 55% de $amatista hay que escribirla `rgba(b16cff8c)` y no hay otra.
# El CSS de la barra si puede (`alpha(@amatista, .55)`), y por eso alli no queda
# ni un literal; aqui son inevitables.
#
# Inevitables, pero no invisibles. Una copia de un color no falla NUNCA: se
# dibuja igual, solo que del tono de otro. Y ya habia pasado dos veces cuando se
# escribio esta prueba, las dos sin que nada se quejara:
#
#   1. `placeholder_text` ponia #8b86a3 cuando $tenue es #8a7aa8. Un gris que no
#      esta en la paleta y del que no queda constancia de haber sido elegido:
#      simplemente se quedo atras cuando la paleta cambio.
#   2. El velo y dos sombras usaban 090312, que tampoco es de la paleta —lo mas
#      parecido es $abismo, 0d0418—. Cuatro sitios con un negro de nadie.
#
# Para quien clone el repo esto es lo que duele: cambia $amatista en
# colores.conf, se le pone todo el escritorio de su color... y la pantalla de
# bloqueo se queda a medias, con el violeta del autor en los trozos copiados.
#
# LO QUE SE EXIGE, y es lo unico que se puede exigir sin prohibir los literales:
# que la parte RGB de cada literal sea la de ALGUN color de la paleta. El alfa
# es libre —para eso existen—, pero el tono tiene que salir de colores.conf.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

CONF="$REPO/hypr/hyprlock.conf"
PALETA="$REPO/hypr/conf/colores.conf"
PANGO="$REPO/hypr/conf/colores-pango.conf"

titulo "1. Todo literal de hyprlock.conf sale de la paleta"
python3 - "$CONF" "$PALETA" > "$TMP/sueltos.txt" <<'PY'
import re, sys

conf = open(sys.argv[1], encoding="utf-8").read()
paleta_txt = open(sys.argv[2], encoding="utf-8").read()

# Los RGB que la paleta autoriza.
buenos = {m.lower() for m in re.findall(r'^\s*\$\w+\s*=\s*rgba\(([0-9a-fA-F]{6})[0-9a-fA-F]{2}\)',
                                        paleta_txt, re.M)}

# Solo se miran las lineas de AJUSTE, no los comentarios: la cabecera explica en
# prosa cuales son los literales y por que, y eso no es un color, es
# documentacion. Una linea de hyprlang es comentario si empieza por # (tras los
# espacios); dentro de una linea de ajuste, el ## es un escape, no un comentario.
sueltos = []
for n, linea in enumerate(conf.splitlines(), 1):
    if re.match(r'\s*#', linea):
        continue
    for rgb in re.findall(r'rgba\(([0-9a-fA-F]{6})[0-9a-fA-F]{2}\)', linea):
        if rgb.lower() not in buenos:
            sueltos.append(f"{n}:rgba:{rgb}")
    for rgb in re.findall(r'##([0-9a-fA-F]{6})\b', linea):
        if rgb.lower() not in buenos:
            sueltos.append(f"{n}:pango:{rgb}")

print("paleta", len(buenos))
print("sueltos", ";".join(sueltos) or "-")
PY
leer() { grep "^$1 " "$TMP/sueltos.txt" | cut -d' ' -f2-; }

if [ "$(leer paleta)" -ge 10 ]; then
    ok "la paleta se leyo entera ($(leer paleta) colores)"
else
    fallo "la paleta se leyo entera" "solo vi $(leer paleta) colores; ¿cambio el formato?"
fi

sueltos="$(leer sueltos)"
if [ "$sueltos" = "-" ]; then
    ok "ningun color de hyprlock.conf se ha salido de la paleta"
else
    fallo "ningun color de hyprlock.conf se ha salido de la paleta" \
          "linea:donde:color -> ${sueltos//;/ }"
fi

titulo "2. El marcado Pango usa variables, no hexadecimales"
# Es la mitad que de verdad evita que vuelva a pasar: mientras el color del
# placeholder sea una variable, no puede quedarse atras.
for campo in placeholder_text fail_text; do
    linea="$(grep -E "^\s*$campo\s*=" "$CONF" || true)"
    if [ -z "$linea" ]; then
        fallo "$campo existe" "no lo encuentro en hyprlock.conf"
    elif printf '%s' "$linea" | grep -qP 'foreground="\$pango_\w+"'; then
        ok "$campo tira de la paleta por variable"
    else
        fallo "$campo tira de la paleta por variable" "pone: $(printf '%s' "$linea" | tr -s ' ')"
    fi
done

titulo "3. Las variables \$pango_ que se usan estan definidas"
# Sin esto, un nombre mal escrito no da error: hyprlang deja el texto tal cual y
# Pango se encuentra un color invalido. Se veria el campo sin color, no un fallo.
usadas="$(grep -oP '\$pango_\w+' "$CONF" | sort -u)"
faltan=""
for v in $usadas; do
    grep -qF "$v " "$PANGO" || faltan="$faltan $v"
done
if [ -n "$usadas" ] && [ -z "$faltan" ]; then
    ok "las $(printf '%s\n' $usadas | wc -l) variables Pango que usa existen en el generado"
else
    fallo "las variables Pango que usa existen en el generado" "faltan:${faltan:- (no usa ninguna)}"
fi

titulo "4. El generado lleva el escape de hyprlang (##), no una # sola"
# Con una sola almohadilla, hyprlang se come el resto de la linea como
# comentario y la variable queda VACIA. No da error: el span sale sin color.
malas="$(grep -cP '^\$pango_\w+\s*=\s*#[0-9a-fA-F]' "$PANGO" || true)"
buenas="$(grep -cP '^\$pango_\w+\s*=\s*##[0-9a-fA-F]{6}\s*$' "$PANGO" || true)"
afirmar_igual "0" "$malas" "ninguna variable con una sola almohadilla"
if [ "$buenas" -ge 10 ]; then
    ok "las $buenas variables llevan ##RRGGBB"
else
    fallo "las variables llevan ##RRGGBB" "solo $buenas bien formadas"
fi

titulo "5. El generado esta al dia con colores.conf"
# Se regenera sobre una COPIA: el generador saca su destino de la ruta de su
# propio .py, asi que lanzarlo aqui reescribiria el repo de verdad.
COPIA="$(copiar_repo)"
antes="$(sha256sum "$COPIA/hypr/conf/colores-pango.conf" 2>/dev/null | cut -d' ' -f1)"
"$COPIA/hypr/scripts/gen-colores.py" >/dev/null 2>&1
despues="$(sha256sum "$COPIA/hypr/conf/colores-pango.conf" | cut -d' ' -f1)"
afirmar_igual "$antes" "$despues" "colores-pango.conf no se ha quedado viejo"

titulo "6. No toco nada de tu equipo"
afirmar_intacta_la_casa_real

resumen
