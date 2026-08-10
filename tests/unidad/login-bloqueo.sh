#!/usr/bin/env bash
# tests/unidad/login-bloqueo.sh — que la pantalla de inicio de sesion y la de
# bloqueo sigan siendo la misma pantalla.
#
# POR QUE EXISTE ESTO. El tema de SDDM se escribio como «la hermana de
# hyprlock.conf», con las mismas medidas y los mismos colores. Cuando el bloqueo
# paso de tarjeta centrada a columna izquierda, el tema NO se entero: se quedo
# una semana enseñando el diseño anterior, con su propia cabecera diciendo
# «misma tarjeta violeta» sobre una tarjeta que ya no existia en ningun sitio.
#
# Y no fallaba nada. Las dos pantallas se dibujaban perfectamente; solo que ya no
# se parecian. Es el mismo modo de fallo que los colores copiados a mano que
# vigila `paleta-bloqueo.sh`: **una copia no avisa cuando se separa de su
# original**, porque sigue siendo valida por su cuenta.
#
# Aqui no se compara el aspecto —eso necesita un compositor y una captura— sino
# los NUMEROS de los que sale el aspecto: si las dos pantallas parten de las
# mismas medidas base y de las mismas transparencias, se ven igual.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

PANTALLA_PY="$REPO/hypr/scripts/lib/pantalla.py"
HYPRLOCK="$REPO/hypr/hyprlock.conf"
MAIN_QML="$REPO/sddm/celiuz/Main.qml"
THEME="$REPO/sddm/celiuz/theme.conf"

titulo "1. Las dos pantallas parten de las mismas medidas"
# Las medidas del bloqueo viven en pantalla.py como px(N) —numeros pensados para
# 1080p—. El tema de SDDM no puede leer ese fichero (el greeter corre como otro
# usuario y ni siquiera hay Python por medio), asi que los repite en QML. Repetir
# es justo lo que hay que vigilar: se comprueba que el NUMERO BASE de cada medida
# aparezca en el QML con el papel que le toca —px() si es un tamaño, centro() si
# es un desplazamiento vertical—.
python3 - "$PANTALLA_PY" "$MAIN_QML" > "$TMP/medidas.txt" <<'PY'
import re, sys

py  = open(sys.argv[1], encoding="utf-8").read()
qml = open(sys.argv[2], encoding="utf-8").read()

# El numero base de cada medida del bloqueo, tal y como lo escribe pantalla.py.
base = {}
for nombre, expr in re.findall(r'"(lock_\w+)":\s*([^\n]+)', py):
    m = re.search(r'px\(\s*(-?\d+)', expr)
    if m:
        base[nombre] = int(m.group(1))
# La banda se calcula antes del diccionario, asi que no la coge el patron de
# arriba: lleva el tope contra el ancho real y por eso vive aparte.
m = re.search(r'lock_banda_w\s*=\s*min\(px\(\s*(-?\d+)', py)
if m:
    base["lock_banda_w"] = int(m.group(1))

# Que papel juega cada una en el QML. Las `_y` son desplazamientos desde el
# centro vertical y alli pasan por centro(); el resto son tamaños y pasan por px().
tamanos = ["lock_banda_w", "lock_col_x", "lock_rounding", "lock_titulo",
           "lock_usuario", "lock_reloj", "lock_fecha", "lock_campo_w",
           "lock_campo_h", "lock_info"]
despl   = ["lock_titulo_y", "lock_usuario_y", "lock_reloj_y", "lock_fecha_y",
           "lock_campo_y", "lock_info_y"]

# lock_col_centro y lock_banda_borde_x no salen aqui a proposito: son derivadas
# que existen porque hyprlang no sabe restar ni centrar dentro de un elemento.
# QML si sabe, asi que el tema no las necesita y no tiene que repetirlas.

faltan = []
for nombre in tamanos + despl:
    if nombre not in base:
        faltan.append(f"{nombre}: ya no sale de un px() en pantalla.py")
        continue
    n = base[nombre]
    patron = rf'px\(\s*{n}\s*\)' if nombre in tamanos else rf'centro\(\s*{n}\s*,'
    if not re.search(patron, qml):
        papel = "px(%d)" % n if nombre in tamanos else "centro(%d, ...)" % n
        faltan.append(f"{nombre}: el bloqueo usa {n} y en Main.qml no hay {papel}")

print("comprobadas", len(tamanos) + len(despl))
for f in faltan:
    print("DESPAREJA", f)
PY
cuantas=$(grep '^comprobadas ' "$TMP/medidas.txt" | cut -d' ' -f2)
afirmar_igual "16" "$cuantas" "se comparan las 16 medidas de la columna"
if grep -q '^DESPAREJA' "$TMP/medidas.txt"; then
    fallo "el login usa las mismas medidas que el bloqueo" \
          "$(grep '^DESPAREJA' "$TMP/medidas.txt" | sed 's/^DESPAREJA //')"
else
    ok "el login usa las mismas medidas que el bloqueo"
fi

titulo "2. Y de la misma escala"
# El factor y sus topes tienen que ser los mismos, o las medidas base coincidiran
# y aun asi las dos pantallas se veran de distinto tamaño en el mismo monitor.
for valor in 1920 1080 0.62 2.20 0.42; do
    if grep -q -- "$valor" "$MAIN_QML"; then
        ok "el QML usa la misma constante de escala ($valor)"
    else
        fallo "el QML usa la misma constante de escala ($valor)" \
              "pantalla.py la usa y Main.qml no"
    fi
done

titulo "3. Y de las mismas transparencias"
# Los literales del bloqueo llevan el alfa en la parte de atras (RRGGBBAA) y el
# QML lo escribe como un float. Se comparan los CONJUNTOS y no cada uno en su
# sitio: asi la prueba no se rompe por reordenar los bloques del .conf, pero si
# alguien sube la banda al 70% en una de las dos, salta.
python3 - "$HYPRLOCK" "$MAIN_QML" "$THEME" > "$TMP/alfas.txt" <<'PY'
import re, sys

lock  = open(sys.argv[1], encoding="utf-8").read()
qml   = open(sys.argv[2], encoding="utf-8").read()
theme = open(sys.argv[3], encoding="utf-8").read()

# Del bloqueo: todo rgba(RRGGBBAA) de 8 hex que NO sea opaco (ff). Los opacos son
# colores de la paleta sin mas y no dicen nada de la transparencia del diseño.
alfas_lock = set()
for hexa in re.findall(r'rgba\(([0-9a-fA-F]{8})\)', lock):
    a = int(hexa[6:], 16) / 255
    if a < 0.999:
        alfas_lock.add(round(a, 2))

# Del tema: los Qt.rgba(...) y la opacidad del velo de theme.conf.
alfas_qml = set()
for a in re.findall(r'Qt\.rgba\([^)]*?,\s*([01]?\.\d+)\s*\)', qml, re.S):
    alfas_qml.add(round(float(a), 2))
m = re.search(r'^veloOpacidad\s*=\s*([01]?\.\d+)', theme, re.M)
if m:
    alfas_qml.add(round(float(m.group(1)), 2))

print("lock", sorted(alfas_lock))
print("qml ", sorted(alfas_qml))
# Las sombras del bloqueo (shadow_color) no tienen equivalente en QML sin
# QtQuick.Effects, asi que no se exige que el tema las tenga. Lo que si se exige
# es lo contrario: que el tema no se invente una transparencia que el bloqueo no
# use, porque eso es exactamente separarse del original.
for a in sorted(alfas_qml - alfas_lock):
    print("SOBRA", a)
PY
if grep -q '^SOBRA' "$TMP/alfas.txt"; then
    fallo "el login no usa transparencias que el bloqueo no tenga" \
          "$(grep '^SOBRA' "$TMP/alfas.txt" | sed 's/^SOBRA /alfa /'); \
del bloqueo salen $(grep '^lock ' "$TMP/alfas.txt" | cut -d' ' -f2-)"
else
    ok "el login no usa transparencias que el bloqueo no tenga"
fi

titulo "4. El tema no se ha quedado hablando del diseño viejo"
# La tarjeta centrada se fue en 4ade398. Si su nombre vuelve a aparecer por aqui
# es que alguien copio de una version anterior — o que el rediseño se deshizo a
# medias, que es como empezo todo esto.
afirmar_no_contiene "$MAIN_QML" 'tarjeta violeta' "la cabecera no describe la tarjeta de antes"
afirmar_contiene "$MAIN_QML" 'banda' "el QML habla de la banda, que es lo que hay ahora"
afirmar_contiene "$THEME" 'columna' "theme.conf tambien describe la columna"

titulo "5. No toco nada de tu equipo"
afirmar_intacta_la_casa_real

resumen
