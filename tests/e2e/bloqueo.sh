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
    afirmar_igual "18" "$cuantas" "define las 18 medidas que usa hyprlock.conf"

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

comprobar_aviso_no_responde() {
    titulo "3. Congelar sin que el compositor acuse a las apps de colgadas"
    # Congelar una app es dejarla muda a proposito, y Hyprland vigila que cada
    # ventana conteste a su ping: a los `anr_missed_pings` fallos dibuja «no
    # responde» con «Esperar» y «Forzar cierre». Lo pinta EL COMPOSITOR, asi que
    # no se tapa cerrando ventanas, y con el xray encendido se ve por debajo del
    # bloqueo. Le paso al autor: la pantalla de bloqueo con un dialogo detras
    # acusando a Obsidian de colgada... cuando la habia congelado el propio
    # bloqueo dos lineas antes.
    rm -rf "$REGISTRO"; mkdir -p "$REGISTRO"
    binario_falso hyprctl 0 '
case "$*" in
  "activeworkspace -j")                    echo "{\"id\": 7, \"windows\": 4}" ;;
  "getoption misc:session_lock_xray -j")   echo "{\"int\": 0}" ;;
  "getoption misc:enable_anr_dialog -j")   echo "{\"int\": 1}" ;;
  *)                                       echo "ok" ;;
esac'
    # systemctl SE SUSTITUYE, y no es opcional: congelar.py lo llama de verdad y
    # con el bus del usuario delante congelaria las apps de la sesion real.
    binario_falso systemctl 0
    binario_falso "$BLOQUEO" 0

    LOCK_DESPEGADO=1 CONGELAR=1 MODO_FONDO=xray REINTENTOS=1 \
    FIFO="$TMP/no-existe-pausa.fifo" FIFO_BARRAS="$TMP/no-existe-barras.fifo" \
        "$REPO/hypr/scripts/lock.sh" > "$TMP/diario-anr.txt" 2>&1

    local diario="$TMP/diario-anr.txt"

    afirmar_contiene "$REGISTRO/hyprctl.log" 'keyword misc:enable_anr_dialog false' \
        "apaga el aviso de «no responde» al congelar"
    afirmar_contiene "$REGISTRO/hyprctl.log" 'keyword misc:enable_anr_dialog 1' \
        "y lo devuelve al valor que tenia (dejarlo apagado seria una fuga)"

    # El ORDEN importa tanto como que ocurra. Si se apagara despues de congelar,
    # el aviso ya habria salido; si se devolviera antes de descongelar, el
    # compositor encontraria las apps mudas y lo sacaria justo al final.
    local n_apaga n_congela n_descongela n_devuelve
    n_apaga=$(grep -n 'no responde» apagado' "$diario" | head -1 | cut -d: -f1)
    n_congela=$(grep -n 'congelando aplicaciones' "$diario" | head -1 | cut -d: -f1)
    n_descongela=$(grep -n 'descongel' "$diario" | head -1 | cut -d: -f1)
    n_devuelve=$(grep -n 'no responde» devuelto' "$diario" | head -1 | cut -d: -f1)

    afirmar "lo apaga ANTES de congelar" \
        test -n "$n_apaga" -a -n "$n_congela" -a "${n_apaga:-99}" -lt "${n_congela:-0}"
    afirmar "lo devuelve DESPUES de descongelar" \
        test -n "$n_devuelve" -a -n "$n_descongela" -a "${n_devuelve:-0}" -gt "${n_descongela:-99}"
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
    afirmar_contiene "$XDG_CACHE_HOME/celiuzpaper/lock-medidas.conf" '^\$lock_banda_w = [0-9]+' \
        "las medidas salen del respaldo, no vacias"
}

comprobar_dos_a_la_vez() {
    titulo "5. Dos SUPER+L en el mismo segundo (la averia del 2026-09-14)"
    rm -rf "$REGISTRO"; mkdir -p "$REGISTRO"

    # El fallo de verdad: dos lock.sh entraron a la vez, los dos miraron «¿hay
    # algun hyprlock?» ANTES de que ninguno hubiera lanzado el suyo, y los dos
    # siguieron adelante. Como el bloqueo de sesion de Wayland solo lo puede
    # tener uno, el segundo hyprlock se quedo vivo para siempre sin pintar nada,
    # y a partir de ahi SUPER+L no volvio a hacer nada en cinco horas.
    #
    # Por eso el falso TARDA: sin una ventana abierta de verdad, el segundo
    # lock.sh llegaria cuando el primero ya ha terminado y no habria carrera que
    # medir. La prueba pasaria sin comprobar nada.
    binario_falso hyprctl 0 '
case "$*" in
  "locked")                              echo "false" ;;
  "activeworkspace -j")                  echo "{\"id\": 7, \"windows\": 0}" ;;
  "getoption misc:session_lock_xray -j") echo "{\"int\": 0}" ;;
  *)                                     echo "ok" ;;
esac'
    binario_falso "$BLOQUEO" 0 'sleep 2'

    local comun=(LOCK_DESPEGADO=1 CONGELAR=0 MODO_FONDO=xray REINTENTOS=1
                 CERROJO_BLOQUEO="$XDG_RUNTIME_DIR/bloqueo-prueba.lock"
                 FIFO="$TMP/no-existe-pausa.fifo" FIFO_BARRAS="$TMP/no-existe-barras.fifo")

    env "${comun[@]}" "$REPO/hypr/scripts/lock.sh" > "$TMP/diario-carrera-a.txt" 2>&1 &
    local a=$!
    env "${comun[@]}" "$REPO/hypr/scripts/lock.sh" > "$TMP/diario-carrera-b.txt" 2>&1 &
    local b=$!
    wait "$a"; wait "$b"

    # LO QUE IMPORTA: uno solo. Dos aqui es la averia entera reproducida.
    afirmar_igual "1" "$(veces_llamado "$BLOQUEO")" \
        "de dos pulsaciones a la vez sale UN solo bloqueo, no dos"

    afirmar "el que pierde el turno lo dice y se aparta" \
        grep -qs 'se me adelanto' "$TMP/diario-carrera-a.txt" "$TMP/diario-carrera-b.txt"

    # La segunda averia de aquel dia: el que llego tarde leyo el xray que acababa
    # de encender el primero, lo tomo por «el valor de antes» y al desbloquear lo
    # dejo encendido. Si el que pierde ni siquiera llega a mirarlo, no puede
    # confundirse, y el xray se devuelve al 0 que tenia.
    afirmar_contiene "$REGISTRO/hyprctl.log" 'keyword misc:session_lock_xray 0' \
        "el xray vuelve a 0 y no se queda encendido para siempre"
}

comprobar_bloqueada_sin_hyprlock() {
    titulo "6. Bloqueada pero sin hyprlock (la pantalla del «lockscreen app died»)"
    rm -rf "$REGISTRO"; mkdir -p "$REGISTRO"

    # El compositor dice que el bloqueo esta puesto, pero no queda nadie
    # dibujandolo. Es la pantalla de la que solo se sale por otro tty, y la
    # respuesta buena NO es «ya esta bloqueada, no hago nada»: es relanzar, que
    # el hyprlock nuevo RETOMA el bloqueo que ya habia (misc:allow_session_lock_restore).
    #
    # Se prueba porque es justo lo que estuvo a punto de romperse al arreglar lo
    # del 2026-09-14: preguntar solo «¿esta bloqueada?» y salir cerraba la unica
    # puerta de salida que le queda a esta pantalla.
    binario_falso hyprctl 0 '
case "$*" in
  "locked")                              echo "true" ;;
  "activeworkspace -j")                  echo "{\"id\": 7, \"windows\": 0}" ;;
  "getoption misc:session_lock_xray -j") echo "{\"int\": 0}" ;;
  *)                                     echo "ok" ;;
esac'
    binario_falso "$BLOQUEO" 0

    LOCK_DESPEGADO=1 CONGELAR=0 MODO_FONDO=xray REINTENTOS=1 \
    CERROJO_BLOQUEO="$XDG_RUNTIME_DIR/bloqueo-prueba2.lock" \
    FIFO="$TMP/no-existe-pausa.fifo" FIFO_BARRAS="$TMP/no-existe-barras.fifo" \
        "$REPO/hypr/scripts/lock.sh" > "$TMP/diario-ya.txt" 2>&1

    afirmar_igual "1" "$(veces_llamado "$BLOQUEO")" \
        "relanza el bloqueo en vez de dejar la pantalla muerta"
    afirmar_contiene "$TMP/diario-ya.txt" 'RETOMAR' "y deja dicho que lo hace para retomar"

    # El atajo de «ya esta bloqueada Y su hyprlock en pie» no se puede provocar
    # aqui: pide un proceso cuyo `comm` sea exactamente «hyprlock» y que lleve la
    # firma de la sesion en su entorno, y un falso con almohadilla-bang tiene por
    # `comm` su interprete («bash»), no su nombre. Esa rama se comprobo a mano en
    # el anidado, que es donde hay un hyprlock de verdad.
}

comprobar_hyprctl_sin_locked() {
    titulo "7. Un Hyprland que no conoce «locked» (otra maquina, otra version)"
    rm -rf "$REGISTRO"; mkdir -p "$REGISTRO"

    # `hyprctl locked` funciona en 0.56.1 pero NO sale en `hyprctl --help`: es
    # superficie no documentada, y este repo se clona en otras cajas. Un Hyprland
    # que no la conozca contesta «unknown request».
    #
    # Lo que se comprueba es que eso se lee como «NO LO SE» y no como «no esta
    # bloqueada». Si se leyera como «no», el script daria por huerfano a un
    # hyprlock legitimo y lo mataria: la pantalla se desbloquearia sola, que es
    # exactamente lo contrario de para lo que existe este fichero.
    binario_falso hyprctl 0 '
case "$*" in
  "locked")                              echo "unknown request" ;;
  "activeworkspace -j")                  echo "{\"id\": 4, \"windows\": 1}" ;;
  "getoption misc:session_lock_xray -j") echo "{\"int\": 0}" ;;
  *)                                     echo "ok" ;;
esac'
    binario_falso "$BLOQUEO" 0

    LOCK_DESPEGADO=1 CONGELAR=0 MODO_FONDO=xray REINTENTOS=1 \
    CERROJO_BLOQUEO="$XDG_RUNTIME_DIR/bloqueo-p7.lock" \
    FIFO="$TMP/no-existe-pausa.fifo" FIFO_BARRAS="$TMP/no-existe-barras.fifo" \
        "$REPO/hypr/scripts/lock.sh" > "$TMP/diario-p7.txt" 2>&1

    afirmar_igual "1" "$(veces_llamado "$BLOQUEO")" \
        "bloquea igual: de las dos salidas malas, acabar bloqueado es la buena"
    afirmar_contiene "$TMP/diario-p7.txt" 'no puedo preguntar' \
        "y deja dicho que no pudo preguntarlo, en vez de inventarse un «no»"

    # Que ADEMAS no mate a nadie en ese caso pide un proceso cuyo `comm` sea
    # «hyprlock» con la firma de la sesion, y eso no se puede montar con un falso
    # de almohadilla-bang (su `comm` es el interprete). La rama se lee en
    # lock.sh: el kill cuelga de [ "$BLOQUEADA" = no ], nunca de «nose».
}

comprobar_sin_flock() {
    titulo "8. Una caja sin flock (sin util-linux)"
    rm -rf "$REGISTRO"; mkdir -p "$REGISTRO"

    # El cerrojo es lo que arregla la carrera, pero NO tenerlo no puede costar el
    # bloqueo. Si «no hay flock» y «el turno lo tiene otro» se trataran igual, una
    # caja sin util-linux no bloquearia NUNCA, y encima en silencio.
    binario_falso hyprctl 0 '
case "$*" in
  "locked")                              echo "false" ;;
  "activeworkspace -j")                  echo "{\"id\": 2, \"windows\": 3}" ;;
  "getoption misc:session_lock_xray -j") echo "{\"int\": 0}" ;;
  *)                                     echo "ok" ;;
esac'
    binario_falso "$BLOQUEO" 0

    LOCK_DESPEGADO=1 CONGELAR=0 MODO_FONDO=xray REINTENTOS=1 \
    FLOCK_BIN="flock-que-no-existe-en-esta-caja" \
    CERROJO_BLOQUEO="$XDG_RUNTIME_DIR/bloqueo-p8.lock" \
    FIFO="$TMP/no-existe-pausa.fifo" FIFO_BARRAS="$TMP/no-existe-barras.fifo" \
        "$REPO/hypr/scripts/lock.sh" > "$TMP/diario-p8.txt" 2>&1

    afirmar_igual "1" "$(veces_llamado "$BLOQUEO")" \
        "sin cerrojo bloquea igual, en vez de quedarse sin hacer nada"
    afirmar_contiene "$TMP/diario-p8.txt" 'sin flock' "y avisa de que va sin cerrojo"
    afirmar_contiene "$REGISTRO/hyprctl.log" 'dispatch workspace 2' \
        "y el trap sigue devolviendote a tu escritorio"
}

comprobar_no_toca_nada_real() {
    titulo "4. No ha tocado nada de tu equipo"
    # La prueba entera vive dentro de $TMP. Si algo hubiera escrito fuera, seria
    # un fallo de la prueba tanto como del codigo.
    afirmar "todo lo que escribio esta dentro del HOME de mentira" \
        test -f "$XDG_CACHE_HOME/celiuzpaper/lock-medidas.conf"
    afirmar_intacta_la_casa_real
    # Se busca POR RUTA, no por nombre. Con `pgrep -x` a secas esta comprobacion
    # miraba los procesos de TODO el equipo, asi que si bloqueabas tu pantalla de
    # verdad mientras corria la suite, veia TU hyprlock y lo daba por suyo: la
    # prueba fallaba sin que nada estuviera roto. Es el mismo error que
    # lib/canales.sh documenta para el codigo (`pgrep -x` no distingue de que
    # sesion es cada proceso); aqui el discriminante es que el falso vive en
    # $FALSOS, una ruta que solo existe dentro de esta prueba.
    afirmar "no hay ningun proceso de bloqueo vivo" \
        test -z "$(pgrep -f "$FALSOS/$BLOQUEO" 2>/dev/null)"
}

comprobar_bloqueo_normal
comprobar_bloqueo_caido
comprobar_aviso_no_responde
comprobar_sin_pantalla
comprobar_dos_a_la_vez
comprobar_bloqueada_sin_hyprlock
comprobar_hyprctl_sin_locked
comprobar_sin_flock
comprobar_no_toca_nada_real
resumen
