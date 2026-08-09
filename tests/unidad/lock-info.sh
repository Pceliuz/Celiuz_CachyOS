#!/usr/bin/env bash
# tests/unidad/lock-info.sh — la fila de datos del bloqueo dice la verdad en
# cualquier equipo, y cuando no tiene nada que decir se calla.
#
# POR QUE EXISTE ESTA PRUEBA
# --------------------------
# `lock-info.sh` es lo unico de la pantalla de bloqueo que depende del HARDWARE:
# bateria, teclado y red. Este repo se usa en un portatil y en un sobremesa, y se
# clona en equipos que no conocemos. Los tres modos de fallo que vigila:
#
#   1. Escribir "bateria --" en un sobremesa. Lo que no aplica no se imprime.
#   2. Devolver una linea en blanco cuando no aplica NADA: hyprlock dibujaria una
#      etiqueta vacia que sigue ocupando su hueco en la columna.
#   3. Sacar el violeta del autor en un equipo que se puso otra paleta. Los
#      colores se leen de hypr/conf/colores.conf, que es la fuente de verdad del
#      escritorio entero; copiarlos al script seria una cuarta copia que se
#      separa sola.
#
# El equipo donde corren las pruebas no se puede elegir, asi que no se comprueba
# "sale la bateria": se comprueba que lo que sale es COHERENTE con lo que hay.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

INFO="$REPO/hypr/scripts/lock-info.sh"

titulo "1. Se puede ejecutar y no se va por la tangente"
if [ -x "$INFO" ]; then
    ok "el script es ejecutable"
else
    fallo "el script es ejecutable" "le falta el bit +x, y hyprlock lo llama por ruta"
fi

salida="$("$INFO" 2>"$TMP/err.txt")"
codigo=$?
afirmar_igual "0" "$codigo" "termina bien"
if [ -s "$TMP/err.txt" ]; then
    fallo "no ensucia stderr" "escribio: $(head -2 "$TMP/err.txt")"
else
    ok "no ensucia stderr"
fi

titulo "2. Lo que dice cuadra con este equipo"
# La bateria: si el equipo tiene uno de estos ficheros, tiene que salir un
# porcentaje; y si no tiene ninguno, no puede salir.
hay_bateria=0
for b in /sys/class/power_supply/BAT*; do
    [ -r "$b/capacity" ] && hay_bateria=1 && break
done
if [ "$hay_bateria" -eq 1 ]; then
    case "$salida" in
        *%*) ok "hay bateria y sale su porcentaje" ;;
        *)   fallo "hay bateria y sale su porcentaje" "no vi ningun % en: $salida" ;;
    esac
else
    # En un sobremesa lo que se comprueba es que NO se invento el dato.
    case "$salida" in
        *bateria*|*"--"*) fallo "sin bateria no se escribe nada de bateria" "salio: $salida" ;;
        *)                ok "sin bateria no se escribe nada de bateria" ;;
    esac
fi

titulo "3. Nunca devuelve una linea en blanco"
# Con todo capado —sin hyprctl, sin ip y con un /sys sin baterias— el script no
# tiene nada que contar. Lo correcto es no imprimir NADA: una linea vacia le
# dejaria a hyprlock una etiqueta que ocupa sitio sin decir nada.
# El PATH se capa SOLO para la llamada al script, no para la prueba: vaciarlo
# de verdad deja al propio bash sin `mkdir` ni `rm` y lo que falla es el andamio.
mkdir -p "$TMP/vacio"
mudo="$(PATH="$TMP/vacio" HOME="$TMP/sin-nada" "$INFO" 2>/dev/null)"
if [ -z "$mudo" ]; then
    ok "sin nada que decir, no imprime ni una linea"
else
    # No es fatal si el equipo de pruebas tiene bateria: el /sys no se puede
    # capar. Solo se exige que, si imprime, sea una linea con contenido.
    case "$mudo" in
        *"<span"*) ok "imprime solo lo que si pudo leer" ;;
        *)         fallo "sin nada que decir, no imprime ni una linea" "salio: «$mudo»" ;;
    esac
fi

titulo "4. Los colores salen de la paleta, no del script"
# Se le da una paleta de mentira con colores imposibles de confundir. Si el
# script los ignora, es que los lleva escritos dentro.
casa="$TMP/casa-paleta"
mkdir -p "$casa/.config/hypr/conf"
printf '$amatista       = rgba(00ff00ff)\n$luz            = rgba(ff0000ff)\n' \
    > "$casa/.config/hypr/conf/colores.conf"
pintado="$(HOME="$casa" "$INFO" 2>/dev/null)"
case "$pintado" in
    *"#00ff00"*) ok "usa el acento de la paleta del equipo" ;;
    *)           fallo "usa el acento de la paleta del equipo" "no vi #00ff00 en: $pintado" ;;
esac
case "$pintado" in
    *b16cff*) fallo "no cuela el violeta del autor" "aparecio b16cff con otra paleta puesta" ;;
    *)        ok "no cuela el violeta del autor" ;;
esac

titulo "5. Sin paleta legible sigue saliendo algo"
# Un equipo a medio instalar no puede quedarse sin fila de datos.
sin="$(HOME="$TMP/no-existe-esta-casa" "$INFO" 2>/dev/null)"
if [ -z "$sin" ]; then
    ok "sin paleta no falla (y aqui no habia nada que decir)"
else
    case "$sin" in
        *"<span foreground=\"#"*) ok "sin paleta cae a los tonos de fabrica" ;;
        *) fallo "sin paleta cae a los tonos de fabrica" "salio: $sin" ;;
    esac
fi

afirmar_intacta_la_casa_real
resumen
