#!/usr/bin/env bash
# tests/lib/comun.sh — lo que comparten todas las pruebas.
#
# LAS TRES REGLAS DE ESTAS PRUEBAS
# --------------------------------
# 1. NUNCA tocan tu sesion ni tu configuracion. Cada prueba corre con un $HOME
#    de mentira y con XDG_CONFIG_HOME, XDG_CACHE_HOME y XDG_RUNTIME_DIR dentro de
#    una carpeta temporal que se borra al terminar. Si una prueba escribiera en
#    ~/.config de verdad, seria un fallo de la prueba.
#
# 2. Lo peligroso se sustituye por un BINARIO FALSO. En vez de ejecutar el
#    bloqueo de pantalla de verdad —que ya dejo al autor fuera de su sesion tres
#    veces— se pone en el PATH un ejecutable con el mismo nombre que solo APUNTA
#    los argumentos con los que se le llamo. Despues se comprueba que se le llamo
#    bien. Se prueba la logica entera sin correr el riesgo ni una vez.
#
# 3. No se aborta al primer fallo. Se apuntan todos y se resumen al final, para
#    arreglar de una tanda en vez de ir descubriendolos de uno en uno.
#
# NADA DE ESTO DEPENDE DE LA MAQUINA DEL AUTOR. No hace falta Hyprland
# corriendo, ni Steam, ni mpvpaper, ni un monitor concreto: se puede lanzar desde
# un TTY o en un servidor de integracion continua. Clonas el repo y ejecutas
# ./tests/run.sh.

set -uo pipefail

# La raiz del repo, sacada de donde esta ESTE fichero. Nada de rutas absolutas:
# el repo tiene que valer clonado en cualquier sitio.
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export REPO

PASADAS=0
FALLADAS=0
FALLOS=()

_verde()  { printf '\033[32m%s\033[0m\n' "$*"; }
_rojo()   { printf '\033[31m%s\033[0m\n' "$*"; }
_gris()   { printf '\033[90m%s\033[0m\n' "$*"; }
titulo()  { printf '\n\033[1m%s\033[0m\n' "$*"; }

# --- Afirmaciones -------------------------------------------------------------

ok()   { PASADAS=$((PASADAS + 1)); _verde "  ✓ $1"; }
fallo() {
    FALLADAS=$((FALLADAS + 1))
    FALLOS+=("$1")
    _rojo "  ✗ $1"
    [ -n "${2:-}" ] && _gris "      $2"
    return 0
}

# afirmar "lo que deberia pasar" <comando...>
afirmar() {
    local desc="$1"; shift
    if "$@" >/dev/null 2>&1; then ok "$desc"; else fallo "$desc" "fallo: $*"; fi
}

# afirmar_contiene <fichero> <patron> "descripcion"
afirmar_contiene() {
    local fichero="$1" patron="$2" desc="$3"
    if [ -f "$fichero" ] && grep -qE -- "$patron" "$fichero" 2>/dev/null; then
        ok "$desc"
    else
        fallo "$desc" "no encontre «$patron» en $(basename "$fichero")"
    fi
}

# afirmar_no_contiene <fichero> <patron> "descripcion"
afirmar_no_contiene() {
    local fichero="$1" patron="$2" desc="$3"
    if [ -f "$fichero" ] && grep -qE -- "$patron" "$fichero" 2>/dev/null; then
        fallo "$desc" "aparecio «$patron», y no deberia"
    else
        ok "$desc"
    fi
}

# afirmar_igual <esperado> <obtenido> "descripcion"
afirmar_igual() {
    if [ "$1" = "$2" ]; then ok "$3"; else fallo "$3" "esperaba «$1», obtuve «$2»"; fi
}

resumen() {
    titulo "Resumen"
    if [ "$FALLADAS" -eq 0 ]; then
        _verde "  $PASADAS comprobaciones, todas bien"
        return 0
    fi
    _rojo "  $FALLADAS de $((PASADAS + FALLADAS)) fallaron:"
    for f in "${FALLOS[@]}"; do _rojo "    - $f"; done
    return 1
}

# --- El entorno de mentira ----------------------------------------------------

# Listado de la cache real del usuario: nombre y fecha de cada fichero. Si al
# terminar una prueba esto ha cambiado, es que algo se escapo del corralito.
_listado_cache_real() {
    local dir="${XDG_CACHE_HOME:-$HOME/.cache}/celiuzpaper"
    [ -d "$dir" ] || { echo "(no hay)"; return; }
    ls -la --time-style=+%s "$dir" 2>/dev/null
}

_huella_cache_real() {
    _listado_cache_real | sha256sum | cut -c1-16
}

# afirmar_intacta_la_casa_real — que la prueba no se salio de su corralito.
#
# Si falla, DICE QUE FICHEROS cambiaron, y no solo que la huella es otra. Dos
# hashes no le sirven de nada a nadie, y hay un caso que da falsa alarma y hay
# que poder reconocer de un vistazo: **la suite tarda minutos, asi que si tu
# sesion se bloquea por inactividad mientras corre, lock.sh reescribe
# `lock-bg.jpg`, `lock-fondo.conf`, `lock-medidas.conf` y `lock.log` en la cache
# de verdad**. La prueba no ha tocado nada; ha sido tu escritorio. Paso el
# 2026-08-07 y cuesta un rato entenderlo si solo ves cambiar un hash.
afirmar_intacta_la_casa_real() {
    local antes="$HUELLA_REAL" despues
    despues="$(HOME="$CASA_REAL" XDG_CACHE_HOME="$CASA_REAL/.cache" _huella_cache_real)"
    if [ "$antes" = "$despues" ]; then
        ok "no toco la cache real del usuario ($CASA_REAL)"
        return
    fi

    local ahora cambios
    ahora="$(HOME="$CASA_REAL" XDG_CACHE_HOME="$CASA_REAL/.cache" _listado_cache_real)"
    cambios="$(diff <(printf '%s\n' "$LISTADO_REAL") <(printf '%s\n' "$ahora") \
               | grep -E '^[<>]' | sed 's/^/        /')"
    fallo "no toco la cache real del usuario" \
          "cambio esto (si son ficheros lock-*, probablemente se te bloqueo la
      pantalla mientras corrian las pruebas, y no es culpa de la prueba):
$cambios"
}

# preparar_entorno — crea un HOME desechable y deja todo apuntando ahi.
#
# El repo se ENLAZA dentro como ~/dotfiles porque algunas piezas (hyprlock.conf,
# por ejemplo) todavia lo buscan por esa ruta. Asi la prueba ejerce el codigo de
# verdad, sin copiarlo ni modificarlo.
preparar_entorno() {
    # Se guarda la casa de verdad ANTES de pisarla, para poder comprobar despues
    # que nada escribio ahi. Es la red de seguridad de las propias pruebas.
    CASA_REAL="${HOME}"
    export CASA_REAL
    HUELLA_REAL="$(_huella_cache_real)"
    LISTADO_REAL="$(_listado_cache_real)"   # para poder decir QUE cambio
    export HUELLA_REAL

    TMP="$(mktemp -d "${TMPDIR:-/tmp}/prueba-dotfiles-XXXXXX")"
    export TMP
    export HOME="$TMP/casa"
    export XDG_CONFIG_HOME="$HOME/.config"
    export XDG_CACHE_HOME="$HOME/.cache"
    export XDG_DATA_HOME="$HOME/.local/share"
    export XDG_RUNTIME_DIR="$TMP/run"
    export FALSOS="$TMP/bin"
    export REGISTRO="$TMP/registro"

    mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_DATA_HOME" \
             "$XDG_RUNTIME_DIR" "$FALSOS" "$REGISTRO"
    chmod 700 "$XDG_RUNTIME_DIR"
    ln -sfn "$REPO" "$HOME/dotfiles"

    # Que ningun script se cuele hablando con el Hyprland de verdad: sin esta
    # variable, hyprctl no encuentra a quien preguntar y lib/pantalla.py se va a
    # su respaldo, que es justo lo que queremos probar.
    unset HYPRLAND_INSTANCE_SIGNATURE
    unset WAYLAND_DISPLAY

    export PATH="$FALSOS:$PATH"
    trap 'limpiar_entorno' EXIT INT TERM
}

limpiar_entorno() {
    [ -n "${TMP:-}" ] && [ -d "$TMP" ] && rm -rf "$TMP"
}

# copiar_repo — deja una copia entera del repo en $TMP/repo y la imprime.
#
# Hace falta para probar los GENERADORES (gen-dock.py, gen-colores.py), que
# escriben dentro del propio repo: sacan su destino de la ruta del fichero .py,
# no del HOME. Ejecutarlos tal cual reescribiria los ficheros de verdad del
# usuario, que es justo lo que una prueba no debe hacer nunca.
#
# Se dejan fuera .git y los videos de fondo: pesan y no hacen falta.
copiar_repo() {
    local destino="$TMP/repo"
    [ -d "$destino" ] && { echo "$destino"; return; }
    mkdir -p "$destino"
    tar -C "$REPO" --exclude=.git --exclude='hypr/wallpapers/*' -cf - . \
        | tar -C "$destino" -xf - 2>/dev/null
    echo "$destino"
}

# binario_falso <nombre> [codigo_salida] [cuerpo_extra]
#
# Deja en el PATH un ejecutable que apunta sus argumentos en
# $REGISTRO/<nombre>.log y sale con el codigo que se le diga. El cuerpo extra
# permite que ademas conteste algo por su salida (util para los que se consultan,
# como hyprctl).
binario_falso() {
    local nombre="$1" codigo="${2:-0}" cuerpo="${3:-}"
    cat > "$FALSOS/$nombre" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$REGISTRO/$nombre.log"
$cuerpo
exit $codigo
EOF
    chmod +x "$FALSOS/$nombre"
}

# veces_llamado <nombre> — cuantas veces se llamo a un binario falso.
veces_llamado() {
    local f="$REGISTRO/$1.log"
    [ -f "$f" ] && wc -l < "$f" | tr -d ' ' || echo 0
}
