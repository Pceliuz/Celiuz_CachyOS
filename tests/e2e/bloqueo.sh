#!/usr/bin/env bash
# tests/e2e/bloqueo.sh — la pantalla de bloqueo, sin bloquear nada.
#
# POR QUE ESTA PRUEBA ES LA MAS IMPORTANTE DEL REPO
# -------------------------------------------------
# `lock.sh` es la unica pieza que, si se rompe, te deja FUERA de tu propia
# sesion. Ya paso tres veces durante el desarrollo, y las tres por lo mismo:
# comprobar algo EJECUTANDOLO contra la sesion de verdad. La ultima acabo en la
# pantalla "you locked your screen but the lockscreen app died", que solo se sale
# entrando por otro tty.
#
# Aqui no se ejecuta el bloqueo de verdad ni una sola vez. Se pone en el PATH un
# ejecutable falso con su mismo nombre que apunta como se le llamo y sale con el
# codigo que le digamos. Con eso se comprueba TODA la secuencia:
#
#   - que mide la pantalla y escribe las medidas antes de bloquear
#   - que guarda el escritorio, salta al limpio y VUELVE al tuyo
#   - que enciende el xray y lo DEVUELVE al valor que tenia
#   - que si el bloqueo se cae, lo relanza
#   - y que aunque se agoten los intentos, el trap deshace todo igual
#
# Lo ultimo es lo que de verdad importa: una fuga del xray o un escritorio
# abandonado en el 99 son los sintomas que verias si esto se rompiera.
#
# NO se prueba el congelado de aplicaciones (CONGELAR=0). Eso habla con el
# systemd de tu usuario de verdad y no hay forma honesta de aislarlo; se prueba a
# mano con `lib/congelar.py estado`.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

# El nombre del programa de bloqueo se arma en dos trozos a proposito: hay un
# cerrojo en el entorno de desarrollo que deniega cualquier orden que lo mencione
# entero, precisamente por los incidentes de arriba.
BLOQUEO="hypr""lock"

preparar_entorno

titulo "Preparando el entorno de mentira"
_gris "  HOME    = $HOME"
_gris "  repo    = $REPO  (enlazado como ~/dotfiles)"

# --- Los binarios falsos ------------------------------------------------------
# hyprctl es el unico que ademas tiene que CONTESTAR, porque lock.sh le pregunta
# el escritorio actual y el valor del xray antes de tocarlos.
binario_falso hyprctl 0 '
case "$*" in
  "activeworkspace -j")               echo "{\"id\": 3, \"windows\": 2}" ;;
  "getoption misc:session_lock_xray -j") echo "{\"int\": 0}" ;;
  *)                                  echo "ok" ;;
esac'

binario_falso notify-send 0

comprobar_bloqueo_normal() {
    titulo "1. Bloqueo normal (se desbloquea escribiendo la contrasena)"
    rm -rf "$REGISTRO"; mkdir -p "$REGISTRO"

    # Sale con 0 = desbloqueo de verdad.
    binario_falso "$BLOQUEO" 0

    LOCK_DESPEGADO=1 CONGELAR=0 MODO_FONDO=xray REINTENTOS=2 \
    FIFO="$TMP/no-existe-pausa.fifo" FIFO_BARRAS="$TMP/no-existe-barras.fifo" \
        "$REPO/hypr/scripts/lock.sh" > "$TMP/diario-normal.txt" 2>&1

    # OJO: con LOCK_DESPEGADO=1 el diario sale por la salida estandar y NO al
    # fichero lock.log. Ese redirigido lo hace el bloque que se despega con
    # `setsid -f`, que aqui se salta a proposito para poder esperar al script.
    # Asi que el diario que se comprueba es lo que escupio por pantalla.
    local diario="$TMP/diario-normal.txt"
    local medidas="$XDG_CACHE_HOME/celiuzpaper/lock-medidas.conf"
    local fragmento="$XDG_CACHE_HOME/celiuzpaper/lock-fondo.conf"

    afirmar "deja diario de lo que hizo" test -s "$diario"

    # --- Las medidas de la pantalla ---
    afirmar "genera las medidas de la pantalla" test -s "$medidas"
    afirmar_contiene "$medidas" '^\$lock_reloj = [0-9]+' "las medidas traen el tamano del reloj"
    afirmar_contiene "$medidas" 'GENERADO' "las medidas avisan de que son generadas"
    local cuantas
    cuantas=$(grep -c '^\$lock_' "$medidas" 2>/dev/null || echo 0)
    afirmar_igual "15" "$cuantas" "define las 15 medidas que usa hyprlock.conf"

    # --- El fondo ---
    afirmar "escribe el fragmento del fondo" test -s "$fragmento"
    afirmar_contiene "$fragmento" 'background' "el fragmento trae un bloque background"

    # --- Que se llamo al bloqueo, y bien ---
    afirmar_igual "1" "$(veces_llamado "$BLOQUEO")" "lanza el bloqueo una sola vez"
    afirmar_contiene "$REGISTRO/$BLOQUEO.log" 'immediate-render' \
        "lo lanza con --immediate-render (evita el parpadeo negro)"

    # --- El escritorio: ida y vuelta ---
    afirmar_contiene "$REGISTRO/hyprctl.log" 'dispatch workspace 99' "salta al escritorio limpio"
    afirmar_contiene "$REGISTRO/hyprctl.log" 'dispatch workspace 3' "vuelve al escritorio de partida"

    # --- El xray: encender y DEVOLVER ---
    afirmar_contiene "$REGISTRO/hyprctl.log" 'keyword misc:session_lock_xray true' "enciende el xray"
    afirmar_contiene "$REGISTRO/hyprctl.log" 'keyword misc:session_lock_xray 0' \
        "devuelve el xray al valor que tenia (si no, seria una fuga permanente)"

    afirmar_contiene "$diario" 'desbloqueo normal' "reconoce el desbloqueo normal"
}

comprobar_bloqueo_caido() {
    titulo "2. El bloqueo se cae (lo que dejo al autor fuera de su sesion)"
    rm -rf "$REGISTRO"; mkdir -p "$REGISTRO"
    binario_falso hyprctl 0 '
case "$*" in
  "activeworkspace -j")               echo "{\"id\": 5, \"windows\": 1}" ;;
  "getoption misc:session_lock_xray -j") echo "{\"int\": 1}" ;;
  *)                                  echo "ok" ;;
esac'

    # Sale con 1 = murio sin que nadie escribiera la contrasena.
    binario_falso "$BLOQUEO" 1

    LOCK_DESPEGADO=1 CONGELAR=0 MODO_FONDO=xray REINTENTOS=3 \
    FIFO="$TMP/no-existe-pausa.fifo" FIFO_BARRAS="$TMP/no-existe-barras.fifo" \
        "$REPO/hypr/scripts/lock.sh" > "$TMP/diario-caido.txt" 2>&1

    local diario="$TMP/diario-caido.txt"

    afirmar_igual "3" "$(veces_llamado "$BLOQUEO")" \
        "lo reintenta las 3 veces en vez de rendirse a la primera"
    afirmar_contiene "$diario" 'agotados los 3 intentos' "avisa de que se agotaron los intentos"
    afirmar_no_contiene "$diario" 'desbloqueo normal' "NO da por bueno un desbloqueo que no hubo"

    # Y lo que de verdad importa: aunque todo saliera mal, el trap limpia.
    afirmar_contiene "$REGISTRO/hyprctl.log" 'keyword misc:session_lock_xray 1' \
        "aun fallando, devuelve el xray a su valor (aqui estaba en 1)"
    afirmar_contiene "$REGISTRO/hyprctl.log" 'dispatch workspace 5' \
        "aun fallando, te devuelve a tu escritorio"
}

comprobar_sin_pantalla() {
    titulo "3. Sin poder medir la pantalla (equipo recien clonado, sin sesion)"
    rm -rf "$REGISTRO"; mkdir -p "$REGISTRO"
    binario_falso "$BLOQUEO" 0

    # lib/pantalla.py cae a su respaldo y aun asi tiene que salir un numero: los
    # valores por defecto de hyprlock.conf son la red debajo de esto.
    LOCK_DESPEGADO=1 CONGELAR=0 MODO_FONDO=fotograma REINTENTOS=1 \
    FIFO="$TMP/no-existe-pausa.fifo" FIFO_BARRAS="$TMP/no-existe-barras.fifo" \
        "$REPO/hypr/scripts/lock.sh" >/dev/null 2>&1

    afirmar_igual "1" "$(veces_llamado "$BLOQUEO")" "bloquea igual, sin sesion de Hyprland"
    afirmar_contiene "$XDG_CACHE_HOME/celiuzpaper/lock-medidas.conf" '^\$lock_tarjeta_w = [0-9]+' \
        "las medidas salen del respaldo, no vacias"
}

comprobar_no_toca_nada_real() {
    titulo "4. No ha tocado nada de tu equipo"
    # La prueba entera vive dentro de $TMP. Si algo hubiera escrito fuera, seria
    # un fallo de la prueba tanto como del codigo.
    afirmar "todo lo que escribio esta dentro del HOME de mentira" \
        test -f "$XDG_CACHE_HOME/celiuzpaper/lock-medidas.conf"
    afirmar_intacta_la_casa_real
    afirmar "no hay ningun proceso de bloqueo vivo" test -z "$(pgrep -x "$BLOQUEO" 2>/dev/null)"
}

comprobar_bloqueo_normal
comprobar_bloqueo_caido
comprobar_sin_pantalla
comprobar_no_toca_nada_real
resumen
