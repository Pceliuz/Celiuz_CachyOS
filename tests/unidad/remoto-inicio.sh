#!/usr/bin/env bash
# tests/unidad/remoto-inicio.sh — Celiuz Remoto, fase 5: tras un reinicio, con
# la PC en la pantalla de inicio (SDDM).
#
# POR QUE: aqui hay lo unico del remoto que corre como ROOT
# (remoto/sistema/entrar.py) y reinicia SDDM. Reiniciar SDDM con una sesion
# abierta la cierra entera, asi que lo primero que se mira es que se NIEGA si
# hay alguien dentro, y que «no se a quien hay» tambien es un no. Despues: que
# el autologin de un solo uso no se queda puesto pase lo que pase, que la regla
# de polkit deja justo lo que dice y nada mas, y que la sesion abierta asi
# arranca bloqueada (la marca de inicio.py y el orden de lua/autostart.lua).
#
# loginctl y systemctl son de mentira: nada de esto toca SDDM ni logind.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
# Con la descripcion delante (como afirmar) y sobre TEXTO, no sobre ficheros.
igual() { afirmar_igual "$2" "$3" "$1"; }
contiene() { if printf '%s' "$3" | grep -qF -- "$2"; then ok "$1"; else fallo "$1" "no encontre «$2» en: $3"; fi; }
no_contiene() { if printf '%s' "$3" | grep -qF -- "$2"; then fallo "$1" "aparecio «$2»"; else ok "$1"; fi; }
ENTRAR="$REPO/remoto/sistema/entrar.py"
YO="$(id -un)"
MI_UID="$(id -u)"

# loginctl: lo que haya en $TMP/sesiones.json; tras el «reinicio» de SDDM, y si
# existe $TMP/entra, aparece la sesion del usuario.
binario_falso loginctl 0 '
case "$1" in
  list-sessions)
    if [ -e "'"$TMP"'/logind-roto" ]; then exit 1; fi
    if [ -e "'"$TMP"'/reiniciado" ] && [ -e "'"$TMP"'/entra" ]; then
        echo "[{\"session\":\"5\",\"uid\":'"$MI_UID"',\"user\":\"'"$YO"'\",\"seat\":\"seat0\",\"class\":\"user\"}]"
    else
        cat "'"$TMP"'/sesiones.json"
    fi ;;
  enable-linger)  mkdir -p "'"$TMP"'/raiz/var/lib/systemd/linger"; touch "'"$TMP"'/raiz/var/lib/systemd/linger/'"$YO"'" ;;
  disable-linger) rm -f "'"$TMP"'/raiz/var/lib/systemd/linger/'"$YO"'" ;;
esac'
binario_falso systemctl 0 '
case "$*" in
  "show -p Id --value display-manager.service") cat "'"$TMP"'/gestor" ;;
  "restart display-manager.service")
      cp "$CELIUZ_ENTRAR_DROPIN" "'"$TMP"'/dropin-al-reiniciar" 2>/dev/null
      touch "'"$TMP"'/reiniciado" ;;
  start*) if [ -e "'"$TMP"'/polkit-no" ]; then echo "Failed to start x: Access denied" >&2; exit 1; fi ;;
esac'

GREETER='{"session":"c1","uid":968,"user":"sddm","seat":"seat0","class":"greeter"}'
MANAGER='{"session":"3","uid":'"$MI_UID"',"user":"'"$YO"'","seat":null,"class":"manager"}'
PERSONA='{"session":"2","uid":'"$MI_UID"',"user":"'"$YO"'","seat":"seat0","class":"user"}'
sesiones() { printf '[%s]\n' "$(IFS=,; echo "$*")" > "$TMP/sesiones.json"; }
echo sddm.service > "$TMP/gestor"

export CELIUZ_ENTRAR_DROPIN="$TMP/sddm.conf.d/zz-celiuz-remoto-entrar.conf"
export CELIUZ_ENTRAR_ESPERA=3
export CELIUZ_ENTRAR_ESTADO="$TMP/sddm-state.conf"
export CELIUZ_ENTRAR_SESIONES="$TMP/wayland-sessions:$TMP/xsessions"
mkdir -p "$TMP/sddm.conf.d" "$TMP/wayland-sessions" "$TMP/xsessions"
: > "$TMP/wayland-sessions/hyprland.desktop"
: > "$TMP/wayland-sessions/hyprland-uwsm.desktop"
: > "$TMP/xsessions/plasmax11.desktop"
entrar() { rm -f "$TMP/reiniciado" "$TMP/dropin-al-reiniciar" "$REGISTRO/systemctl.log"
           "$ENTRAR" "$@" 2>"$TMP/entrar.err"; echo $?; }
reinicio() { grep -c '^restart display-manager' "$REGISTRO/systemctl.log" 2>/dev/null || echo 0; }

titulo "1. entrar.py (lo que corre como root): se niega si hay alguien"
sesiones "$GREETER" "$PERSONA"
igual "con una sesion en el asiento: no (3)" "3" "$(entrar "$YO")"
igual "  y NO reinicia SDDM" "0" "$(reinicio)"
afirmar "  ni deja autologin" test ! -e "$CELIUZ_ENTRAR_DROPIN"
contiene "  y dice por que" "reiniciar SDDM la cerraría" "$(cat "$TMP/entrar.err")"
sesiones "$GREETER" '{"session":"7","uid":1001,"user":"otra","seat":"seat0","class":"user-early"}'
igual "con la de OTRA persona (user-early) tampoco" "3" "$(entrar "$YO")"
touch "$TMP/logind-roto"
igual "sin poder preguntar a logind: no (no lo se no es nadie)" "3" "$(entrar "$YO")"
igual "  y NO reinicia SDDM" "0" "$(reinicio)"
rm -f "$TMP/logind-roto"
sesiones "$MANAGER"
igual "sin pantalla de inicio (una consola): no (4)" "4" "$(entrar "$YO")"
sesiones "$GREETER" "$MANAGER"
echo gdm.service > "$TMP/gestor"
igual "si el gestor no es SDDM: no (5)" "5" "$(entrar "$YO")"
echo sddm.service > "$TMP/gestor"
igual "sin usuario: mal llamado (2)" "2" "$(entrar)"
igual "un usuario que no existe: 2" "2" "$(entrar nadie-se-llama-asi-xyz)"
igual "una cuenta del sistema (root): 2" "2" "$(entrar root)"
igual "  y en ninguno de estos reinicia SDDM" "0" "$(reinicio)"

titulo "2. entrar.py: el autologin es de un solo uso"
if [ "$MI_UID" -lt 1000 ]; then
    _gris "  (se salta: quien corre las pruebas no es una cuenta de persona)"
else
    sesiones "$GREETER" "$MANAGER"
    touch "$TMP/entra"
    igual "con la PC en SDDM y el linger del usuario (manager): entra (0)" "0" "$(entrar "$YO")"
    igual "  reinicia SDDM una vez" "1" "$(reinicio)"
    afirmar "  con el autologin de ESTE usuario puesto en ese momento" \
        grep -qx "User=$YO" "$TMP/dropin-al-reiniciar"
    afirmar "  que no vuelve a entrar solo al salir" grep -qx "Relogin=false" "$TMP/dropin-al-reiniciar"
    afirmar "  sin saber la ultima: la de Hyprland CON uwsm (sin ella fallan los lanzadores)" \
        grep -qx "Session=hyprland-uwsm.desktop" "$TMP/dropin-al-reiniciar"
    afirmar "  y al entrar lo BORRA" test ! -e "$CELIUZ_ENTRAR_DROPIN"
    printf '[Last]\nSession=/usr/share/xsessions/plasmax11.desktop\nUser=%s\n' "$YO" > "$CELIUZ_ENTRAR_ESTADO"
    igual "otra vez, con SDDM recordando otra sesion" "0" "$(entrar "$YO")"
    afirmar "  entra en la que usaste la ultima vez (de state.conf, aunque traiga la ruta)" \
        grep -qx "Session=plasmax11.desktop" "$TMP/dropin-al-reiniciar"
    printf '[Last]\nSession=borrada.desktop\n' > "$CELIUZ_ENTRAR_ESTADO"
    entrar "$YO" >/dev/null
    afirmar "  una ultima que ya no existe no vale: la de uwsm" \
        grep -qx "Session=hyprland-uwsm.desktop" "$TMP/dropin-al-reiniciar"
    rm -f "$TMP/entra" "$CELIUZ_ENTRAR_ESTADO"
    igual "si la sesion no aparece: se rinde (6)" "6" "$(entrar "$YO")"
    afirmar "  y lo borra igual" test ! -e "$CELIUZ_ENTRAR_DROPIN"
fi
UNIDAD="$REPO/remoto/sistema/celiuz-remoto-entrar@.service"
afirmar "la unidad lo borra tambien al acabar (ExecStopPost)" \
    grep -qx 'ExecStopPost=/usr/bin/rm -f /etc/sddm.conf.d/zz-celiuz-remoto-entrar.conf' "$UNIDAD"
afirmar "y tmpfiles al arrancar el equipo" \
    grep -qx 'r /etc/sddm.conf.d/zz-celiuz-remoto-entrar.conf' "$REPO/remoto/sistema/celiuz-remoto.tmpfiles"
afirmar "el mismo nombre que usa entrar.py" \
    grep -q '"/etc/sddm.conf.d/zz-celiuz-remoto-entrar.conf"' "$ENTRAR"
afirmar "la unidad ejecuta la COPIA de root, no el repo" \
    grep -qx 'ExecStart=/usr/local/lib/celiuz-remoto/entrar %i' "$UNIDAD"
afirmar "con freno (no reinicia SDDM en bucle)" grep -q '^StartLimitBurst=' "$UNIDAD"
afirmar "entrar.py arranca aislado (python -I)" sh -c "head -1 '$ENTRAR' | grep -q -- ' -I$'"

titulo "2b. /etc/sddm.conf: el Session= que pisaba la sesion (sddm_conf.py)"
CONF="$REPO/remoto/sistema/sddm_conf.py"
printf '[Autologin]\nSession=hyprland\n\n[Theme]\nCurrent=celiuz\n' > "$TMP/sddm.conf"
nuevo="$(python3 "$CONF" "$TMP/sddm.conf")"; codigo=$?
igual "el de CachyOS (Session= sin User=): hay que tocarlo (0)" "0" "$codigo"
afirmar "  la linea queda COMENTADA, no borrada" grep -qx "# Session=hyprland" <<< "$nuevo"
afirmar "  con quien y por que" grep -q "Celiuz Remoto la comento" <<< "$nuevo"
afirmar "  y lo demas, intacto" grep -qx "Current=celiuz" <<< "$nuevo"
printf '%s\n' "$nuevo" > "$TMP/sddm.conf"
python3 "$CONF" "$TMP/sddm.conf" >/dev/null; codigo=$?
igual "ya comentado: nada que hacer (1)" "1" "$codigo"
printf '[Autologin]\nUser=alguien\nSession=plasma\n' > "$TMP/sddm.conf"
salida="$(python3 "$CONF" "$TMP/sddm.conf")"; codigo=$?
igual "con un autologin DE VERDAD (User=): no se toca (2)" "2|" "$codigo|$salida"
python3 "$CONF" "$TMP/no-existe.conf" >/dev/null; codigo=$?
igual "sin /etc/sddm.conf: nada que hacer (1)" "1" "$codigo"
printf '[Theme]\nSession=otra\n' > "$TMP/sddm.conf"
python3 "$CONF" "$TMP/sddm.conf" >/dev/null; codigo=$?
igual "un Session= fuera de [Autologin] no es asunto suyo (1)" "1" "$codigo"

titulo "2c. revisar: lo de root, al dia o no"
R="$TMP/raiz-revisar"
estado_sistema() { CELIUZ_REMOTO_RAIZ_SISTEMA="$R" python3 -c '
import sys; sys.path.insert(0, sys.argv[1])
from celiuz_remoto import inicio; print(inicio.sistema_estado())' "$REPO/remoto/servidor"; }
mkdir -p "$R/etc/systemd/system" "$R/usr/local/lib/celiuz-remoto"
igual "sin pasar --remoto-sistema: falta" "falta" "$(estado_sistema)"
: > "$R/etc/systemd/system/celiuz-remoto-entrar@.service"
printf '#!/usr/bin/python3\n# la de antes\n' > "$R/usr/local/lib/celiuz-remoto/entrar"; chmod +x "$R/usr/local/lib/celiuz-remoto/entrar"
igual "con la copia de root distinta de la del repo (un git pull con arreglo): vieja" "vieja" "$(estado_sistema)"
cp "$REPO/remoto/sistema/entrar.py" "$R/usr/local/lib/celiuz-remoto/entrar"
printf '[Autologin]\nSession=hyprland\n' > "$R/etc/sddm.conf"
igual "al dia, pero /etc/sddm.conf pisa la sesion: sddm_conf" "sddm_conf" "$(estado_sistema)"
python3 "$REPO/remoto/sistema/sddm_conf.py" "$R/etc/sddm.conf" > "$R/nuevo" && mv "$R/nuevo" "$R/etc/sddm.conf"
igual "y arreglado eso: ok" "ok" "$(estado_sistema)"

titulo "3. La regla de polkit: lo justo"
if ! command -v node >/dev/null 2>&1; then
    _gris "  (se salta: sin node no se puede evaluar el JavaScript de polkit)"
else
    sed "s/@USUARIO@/yo/g" "$REPO/remoto/sistema/celiuz-remoto.rules.in" > "$TMP/regla.js"
    afirmar "no queda ningun @USUARIO@ sin cambiar" sh -c "! grep -q @USUARIO@ '$TMP/regla.js'"
    cat > "$TMP/polkit.js" <<'FINJS'
const fs = require('fs');
let regla = null;
const polkit = { Result: { YES: 'si', NO: 'no', NOT_HANDLED: '-' }, addRule: (f) => { regla = f; } };
eval(fs.readFileSync(process.argv[2], 'utf8'));
const accion = (id, d = {}) => ({ id, lookup: (k) => d[k] });
const casos = {
  apagar: [accion('org.freedesktop.login1.power-off'), 'yo'],
  apagar_otro: [accion('org.freedesktop.login1.power-off'), 'otro'],
  reiniciar_varias: [accion('org.freedesktop.login1.reboot-multiple-sessions'), 'yo'],
  suspender: [accion('org.freedesktop.login1.suspend'), 'yo'],
  saltar_inhibidor: [accion('org.freedesktop.login1.power-off-ignore-inhibit'), 'yo'],
  entrar: [accion('org.freedesktop.systemd1.manage-units', { unit: 'celiuz-remoto-entrar@yo.service', verb: 'start' }), 'yo'],
  entrar_como_otro: [accion('org.freedesktop.systemd1.manage-units', { unit: 'celiuz-remoto-entrar@otro.service', verb: 'start' }), 'yo'],
  parar: [accion('org.freedesktop.systemd1.manage-units', { unit: 'celiuz-remoto-entrar@yo.service', verb: 'stop' }), 'yo'],
  otra_unidad: [accion('org.freedesktop.systemd1.manage-units', { unit: 'sshd.service', verb: 'start' }), 'yo'],
  otro_entrar: [accion('org.freedesktop.systemd1.manage-units', { unit: 'celiuz-remoto-entrar@yo.service', verb: 'start' }), 'otro'],
  otra_cosa: [accion('org.freedesktop.udisks2.filesystem-mount'), 'yo'],
};
const r = {};
for (const [k, [a, u]] of Object.entries(casos)) r[k] = regla(a, { user: u });
console.log(JSON.stringify(r));
FINJS
    pk="$(node "$TMP/polkit.js" "$TMP/regla.js" 2>&1)"
    pk_es() { python3 -c 'import json,sys; print(json.loads(sys.argv[1])[sys.argv[2]])' "$pk" "$1" 2>/dev/null; }
    igual "apagar: si" "si" "$(pk_es apagar)"
    igual "reiniciar con otra sesion (el greeter): si" "si" "$(pk_es reiniciar_varias)"
    igual "suspender: si" "si" "$(pk_es suspender)"
    igual "apagar siendo OTRO usuario: no es cosa suya" "-" "$(pk_es apagar_otro)"
    igual "saltarse los inhibidores: no" "-" "$(pk_es saltar_inhibidor)"
    igual "arrancar SU unidad de entrar: si" "si" "$(pk_es entrar)"
    igual "la de entrar como OTRO: no" "-" "$(pk_es entrar_como_otro)"
    igual "pararla (otro verbo): no" "-" "$(pk_es parar)"
    igual "otra unidad: no" "-" "$(pk_es otra_unidad)"
    igual "otro usuario con mi unidad: no" "-" "$(pk_es otro_entrar)"
    igual "cualquier otra accion: no" "-" "$(pk_es otra_cosa)"
fi

titulo "4. inicio.py (el servicio, sin root): donde esta la PC"
export CELIUZ_REMOTO_RAIZ_SISTEMA="$TMP/raiz"
py() { PYTHONPATH="$REPO/remoto/servidor" python3 -c "
import json, sys
from celiuz_remoto import inicio
$1" 2>"$TMP/py.err"; }
sesiones "$GREETER" "$MANAGER"
e="$(py 'print(json.dumps(inicio.estado(fresco=True)))')"
contiene "sin Hyprland y con SDDM esperando: pantalla_inicio" '"sesion": "pantalla_inicio"' "$e"
contiene "  pero sin lo de root no se puede entrar" '"puede_entrar": false' "$e"
contiene "  y dice que pasar" "instalar.sh --remoto-sistema" "$e"
mkdir -p "$TMP/raiz/etc/systemd/system" "$TMP/raiz/usr/local/lib/celiuz-remoto"
cp "$UNIDAD" "$TMP/raiz/etc/systemd/system/"
cp "$ENTRAR" "$TMP/raiz/usr/local/lib/celiuz-remoto/entrar"
e="$(py 'print(json.dumps(inicio.estado(fresco=True)))')"
contiene "con lo de root: se puede entrar" '"puede_entrar": true' "$e"
sesiones "$GREETER" "$PERSONA"
e="$(py 'print(json.dumps(inicio.estado(fresco=True)))')"
contiene "con una sesion que no es Hyprland: no lo se" '"sesion": "no_lo_se"' "$e"
contiene "  y no ofrece entrar" '"puede_entrar": false' "$e"
touch "$TMP/logind-roto"
e="$(py 'print(json.dumps(inicio.estado(fresco=True)))')"
contiene "sin logind: no lo se" '"sesion": "no_lo_se"' "$e"
rm -f "$TMP/logind-roto"
FIRMA="prueba_1792449598_1"
mkdir -p "$XDG_RUNTIME_DIR/hypr/$FIRMA"
python3 - "$XDG_RUNTIME_DIR/hypr/$FIRMA/.socket.sock" <<'FINPY' &
import socket, sys
s = socket.socket(socket.AF_UNIX); s.bind(sys.argv[1]); s.listen(16)
while True:
    s.accept()[0].close()
FINPY
PID_HYPR=$!
trap 'kill $PID_HYPR 2>/dev/null; limpiar_entorno' EXIT INT TERM
esperar_socket() { for _ in $(seq 50); do [ -S "$1" ] && return; sleep 0.1; done; }
esperar_socket "$XDG_RUNTIME_DIR/hypr/$FIRMA/.socket.sock"
e="$(py 'print(json.dumps(inicio.estado(fresco=True)))')"
contiene "con un Hyprland vivo: abierta" '"sesion": "abierta"' "$e"
kill $PID_HYPR 2>/dev/null; wait $PID_HYPR 2>/dev/null
rm -rf "$XDG_RUNTIME_DIR/hypr"

titulo "5. Entrar, y que la sesion arranque bloqueada"
sesiones "$GREETER" "$MANAGER"
rm -f "$REGISTRO/systemctl.log"
r="$(py 'print(inicio.entrar())')"
contiene "entrar() dice que va" "True" "$r"
afirmar "  pide la unidad de ESTE usuario, sin esperarla" \
    grep -qx "start --no-block celiuz-remoto-entrar@$YO.service" "$REGISTRO/systemctl.log"
MARCA="$XDG_RUNTIME_DIR/celiuz-remoto/entrar-bloqueada"
afirmar "  deja la marca de arrancar bloqueada" test -f "$MARCA"
CLI="$REPO/remoto/servidor/celiuz-remoto.py"
"$CLI" al-entrar; codigo=$?
igual "al-entrar con la marca recien puesta: bloquear (0)" "0" "$codigo"
afirmar "  y la gasta" test ! -e "$MARCA"
"$CLI" al-entrar; codigo=$?
igual "la segunda vez: no (1)" "1" "$codigo"
mkdir -p "$(dirname "$MARCA")"; touch -d '-10 minutes' "$MARCA"
"$CLI" al-entrar; codigo=$?
igual "una marca vieja (entrada que fallo) no bloquea" "1" "$codigo"
afirmar "  y tambien se gasta" test ! -e "$MARCA"
touch "$TMP/polkit-no"
r="$(py 'print(inicio.entrar())')"
contiene "si polkit no deja: lo dice, y que pasar" "instalar.sh --remoto-sistema" "$r"
afirmar "  sin dejar la marca" test ! -e "$MARCA"
rm -f "$TMP/polkit-no"
sesiones "$GREETER" "$PERSONA"
rm -f "$REGISTRO/systemctl.log"
r="$(py 'print(inicio.entrar())')"
contiene "con alguien dentro no lo pide" "False" "$r"
igual "  ni llama a systemctl" "0" "$(veces_llamado systemctl)"

AUTO="$REPO/hypr/lua/autostart.lua"
primera="$(awk '/^hl\.on\("hyprland\.start"/{d=1; next} d && /^ *hl\.exec_cmd\(/{print; exit}' "$AUTO")"
contiene "autostart.lua: lo PRIMERO que arranca es mirar la marca" "celiuz-remoto al-entrar" "$primera"
contiene "  y si toca, lock.sh" 'lock.sh' "$primera"

titulo "6. Linger: arrancar con el equipo, sin quitarle a nadie el suyo"
rm -f "$REGISTRO/loginctl.log"
py 'print(inicio.poner_linger(True))' >/dev/null
afirmar "encender: enable-linger" grep -qx "enable-linger" "$REGISTRO/loginctl.log"
afirmar "  y apunta que es nuestro" test -f "$XDG_STATE_HOME/celiuz/remoto/linger-nuestro"
igual "  linger() lo ve" "True" "$(py 'print(inicio.linger())')"
py 'print(inicio.poner_linger(False))' >/dev/null
afirmar "apagar el nuestro: disable-linger" grep -qx "disable-linger" "$REGISTRO/loginctl.log"
afirmar "  y se olvida" test ! -e "$XDG_STATE_HOME/celiuz/remoto/linger-nuestro"
mkdir -p "$TMP/raiz/var/lib/systemd/linger"; touch "$TMP/raiz/var/lib/systemd/linger/$YO"
rm -f "$REGISTRO/loginctl.log"
py 'print(inicio.poner_linger(False))' >/dev/null
afirmar "uno que ya estaba (de otra cosa) NO se apaga" test ! -e "$REGISTRO/loginctl.log"

titulo "7. instalar.sh --remoto-sistema (en --revisar: dice, no toca)"
unset CELIUZ_REMOTO_RAIZ_SISTEMA
salida="$("$REPO/instalar.sh" --remoto-sistema --revisar 2>&1)"; codigo=$?
igual "sale bien" "0" "$codigo"
contiene "copia el programa a /usr/local (no lo ejecuta desde el repo)" \
    "entrar.py /usr/local/lib/celiuz-remoto/entrar" "$salida"
contiene "la regla de polkit" "/etc/polkit-1/rules.d/50-celiuz-remoto.rules" "$salida"
contiene "tmpfiles" "/etc/tmpfiles.d/celiuz-remoto.conf" "$salida"
contiene "todo de root" "-o root -g root" "$salida"
no_contiene "y en --revisar no pide sudo" "[sudo]" "$salida"

afirmar_intacta_la_casa_real
resumen
