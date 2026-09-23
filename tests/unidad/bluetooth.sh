#!/usr/bin/env bash
# tests/unidad/bluetooth.sh — que el demonio de los auriculares decida bien: a
# quien llamar primero, a quien bloquear, a quien echar y a quien no tocar nunca.
#
# QUE VIGILA
# ----------
# Todo lo que decide hypr/scripts/bluetooth.py vive en `decidir()`, que recibe la
# foto de BlueZ y lo que se recuerda, y devuelve un plan SIN HACER NADA. Aqui se
# le pasan fotos inventadas. Las reglas que no se pueden romper:
#
#   - El orden es el del ultimo uso: con dos encendidos, gana el de la ultima vez.
#   - Con uno en uso, los demas auriculares se bloquean, y uno de sobra que se
#     haya colado se echa. El que ya estaba en uso no se cambia por otro «mejor».
#   - Un aparato que bloqueaste TU no se desbloquea ni se llama nunca.
#   - Uno soltado a mano no se llama (hasta apagar y encender).
#   - Un raton, un teclado o un movil no se tocan: el movil habla A2DP y manos
#     libres, pero desde el otro lado (Audio Source, Handsfree AG).
#   - Con el Bluetooth apagado no se llama a nadie y se suelta todo lo bloqueado
#     por el cerrojo.
#
# Lo que pasa por D-Bus —las senales, los tiempos, el echar de verdad— lo prueba
# tests/e2e/bluetooth.sh contra un BlueZ falso.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

RES="$TMP/resultados"

python3 - "$REPO/hypr/scripts/bluetooth.py" > "$RES" 2>"$TMP/py.err" <<'PYEOF'
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("bluetooth", sys.argv[1])
bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bt)

SINK = "0000110b-0000-1000-8000-00805f9b34fb"
HFP = "0000111e-0000-1000-8000-00805f9b34fb"
FUENTE = "0000110a-0000-1000-8000-00805f9b34fb"   # el movil: manda audio
AG = "0000111f-0000-1000-8000-00805f9b34fb"       # el movil: la otra punta del manos libres
HID = "00001124-0000-1000-8000-00805f9b34fb"


def dispositivo(mac, nombre, uuids=(SINK, HFP), icono="audio-headset",
                emparejado=True, conectado=False, bloqueado=False,
                adaptador="/org/bluez/hci0"):
    return ("/org/bluez/hci0/dev_" + mac.replace(":", "_"), {bt.DISPOSITIVO: {
        "Address": mac, "Alias": nombre, "Icon": icono, "UUIDs": list(uuids),
        "Paired": emparejado, "Connected": conectado, "Blocked": bloqueado,
        "Adapter": adaptador}})


def foto(*aparatos, encendido=True):
    objetos = {"/org/bluez/hci0": {bt.ADAPTADOR: {"Powered": encendido}}}
    objetos.update(dict(aparatos))
    return bt.leer_aparatos(objetos)


A, B, C = "AA:00:00:00:00:0A", "BB:00:00:00:00:0B", "CC:00:00:00:00:0C"
# B se uso lo ultimo, luego A; C nunca.
USOS = {A: 100.0, B: 200.0}


def recuerdo(**kw):
    kw.setdefault("ultimo_uso", dict(USOS))
    return bt.Recuerdo(**kw)


def sal(clave, valor):
    print("%s=%s" % (clave, valor))


# --- Nadie en uso: a quien se llama y en que orden ---------------------------
p = bt.decidir(foto(dispositivo(A, "Auris A"), dispositivo(B, "Auris B"),
                    dispositivo(C, "Auris C")), recuerdo())
sal("orden", ",".join(p.candidatos))
sal("orden_activo", p.activo)
sal("orden_bloquea", len(p.bloquear))

# Los soltados a mano y los bloqueados por ti se saltan; los del cerrojo no.
# A esta bloqueado y NO esta en la lista del cerrojo: lo bloqueaste tu.
r = recuerdo(soltados={B}, bloqueados={C})
p = bt.decidir(foto(dispositivo(A, "Auris A", bloqueado=True),
                    dispositivo(B, "Auris B"),
                    dispositivo(C, "Auris C", bloqueado=True)), r)
sal("filtro_candidatos", ",".join(p.candidatos))
sal("filtro_desbloquea", ",".join(p.desbloquear))

# --- Uno en uso: el cerrojo ------------------------------------------------------
p = bt.decidir(foto(dispositivo(A, "Auris A", conectado=True),
                    dispositivo(B, "Auris B"), dispositivo(C, "Auris C")), recuerdo())
sal("uso_activo", p.activo)
sal("uso_bloquea", ",".join(sorted(p.bloquear)))
sal("uso_candidatos", len(p.candidatos))
sal("uso_echa", len(p.echar))

# Uno bloqueado por ti no se vuelve a bloquear (ya lo esta) ni pasa a ser nuestro.
p = bt.decidir(foto(dispositivo(A, "Auris A", conectado=True),
                    dispositivo(B, "Auris B", bloqueado=True)), recuerdo())
sal("tuyo_bloquea", len(p.bloquear))

# Entran dos a la vez sin que hubiera ninguno: gana el de la ultima vez (B).
p = bt.decidir(foto(dispositivo(A, "Auris A", conectado=True),
                    dispositivo(B, "Auris B", conectado=True)), recuerdo())
sal("dos_activo", p.activo)
sal("dos_echa", ",".join(p.echar))

# Pero si A ya estaba en uso, se queda A aunque B sea «mejor»: eso es el cerrojo.
p = bt.decidir(foto(dispositivo(A, "Auris A", conectado=True),
                    dispositivo(B, "Auris B", conectado=True)), recuerdo(activo=A))
sal("pegado_activo", p.activo)
sal("pegado_echa", ",".join(p.echar))

# Conectado con nuestro bloqueo aun encima: se le quita.
p = bt.decidir(foto(dispositivo(A, "Auris A", conectado=True, bloqueado=True)),
               recuerdo(bloqueados={A}))
sal("encima_desbloquea", ",".join(p.desbloquear))

# --- Lo que no se toca nunca -----------------------------------------------------
movil = dispositivo("DD:00:00:00:00:0D", "Movil", uuids=(FUENTE, AG), icono="phone")
raton = dispositivo("EE:00:00:00:00:0E", "Raton", uuids=(HID,), icono="input-mouse",
                    conectado=True)
nuevo = dispositivo("FF:00:00:00:00:0F", "Sin emparejar", emparejado=False)
p = bt.decidir(foto(dispositivo(A, "Auris A", conectado=True), movil, raton, nuevo),
               recuerdo())
sal("ajenos_bloquea", ",".join(p.bloquear) or "nadie")
sal("ajenos_echa", ",".join(p.echar) or "nadie")
p = bt.decidir(foto(movil, raton, nuevo), recuerdo())
sal("ajenos_candidatos", ",".join(p.candidatos) or "nadie")

# Recien emparejado, aun sin UUIDs: el icono basta para reconocerlo.
p = bt.decidir(foto(dispositivo(C, "Auris C", uuids=())), recuerdo())
sal("icono_candidatos", ",".join(p.candidatos))

# --- Bluetooth apagado -----------------------------------------------------------
p = bt.decidir(foto(dispositivo(A, "Auris A"), dispositivo(B, "Auris B", bloqueado=True),
                    encendido=False), recuerdo(bloqueados={B}))
sal("apagado_candidatos", len(p.candidatos))
sal("apagado_desbloquea", ",".join(p.desbloquear))

# --- Lo que se guarda --------------------------------------------------------------
r = recuerdo(bloqueados={B}, soltados={A})
r.guardar()
leido = bt.Recuerdo.cargar()
sal("guardado_bloqueados", ",".join(sorted(leido.bloqueados)))
sal("guardado_soltados", ",".join(sorted(leido.soltados)))
sal("guardado_uso", leido.ultimo_uso.get(B))
sal("fichero_estado", bt.fichero_recuerdo())
sal("fichero_soltados", bt.fichero_soltados())
PYEOF

titulo "El guion corre limpio"
afirmar "no escribe nada en stderr" test ! -s "$TMP/py.err"
[ -s "$TMP/py.err" ] && sed 's/^/      /' "$TMP/py.err"

valor() { sed -n "s/^$1=//p" "$RES"; }
# Los mismos de dentro del guion.
A=AA:00:00:00:00:0A B=BB:00:00:00:00:0B C=CC:00:00:00:00:0C

titulo "Nadie en uso: a quien se llama"
afirmar_igual "$B,$A,$C" "$(valor orden)" \
    "el ultimo que usaste primero, y el que nunca se uso al final"
afirmar_igual "None" "$(valor orden_activo)" "no hay ninguno en uso"
afirmar_igual "0" "$(valor orden_bloquea)" "sin nadie en uso no se bloquea a nadie"
afirmar_igual "$C" "$(valor filtro_candidatos)" \
    "se salta al soltado a mano (B) y al bloqueado por ti (A); el del cerrojo (C) si entra"
afirmar_igual "$C" "$(valor filtro_desbloquea)" \
    "se desbloquea lo del cerrojo, y solo eso"

titulo "Uno en uso: el cerrojo"
afirmar_igual "$A" "$(valor uso_activo)" "el conectado es el que esta en uso"
afirmar_igual "$B,$C" "$(valor uso_bloquea)" "los demas auriculares se bloquean"
afirmar_igual "0" "$(valor uso_candidatos)" "con uno en uso no se llama a nadie"
afirmar_igual "0" "$(valor uso_echa)" "y no se echa a nadie si no sobra nadie"
afirmar_igual "0" "$(valor tuyo_bloquea)" "uno bloqueado por ti no se toca"
afirmar_igual "$B" "$(valor dos_activo)" \
    "si entran dos a la vez, gana el que usaste la ultima vez"
afirmar_igual "$A" "$(valor dos_echa)" "y el otro se echa"
afirmar_igual "$A" "$(valor pegado_activo)" \
    "el que ya estaba en uso no se cambia por otro"
afirmar_igual "$B" "$(valor pegado_echa)" "el que se cuela es el que se echa"
afirmar_igual "$A" "$(valor encima_desbloquea)" \
    "el que esta en uso no se queda con nuestro bloqueo encima"

titulo "Lo que no es un auricular no se toca"
afirmar_igual "nadie" "$(valor ajenos_bloquea)" \
    "ni el movil, ni el raton, ni uno sin emparejar se bloquean"
afirmar_igual "nadie" "$(valor ajenos_echa)" "ni se echan (el raton sigue conectado)"
afirmar_igual "nadie" "$(valor ajenos_candidatos)" "ni se llaman"
afirmar_igual "$C" "$(valor icono_candidatos)" \
    "uno recien emparejado sin UUIDs se reconoce por el icono"

titulo "Bluetooth apagado"
afirmar_igual "0" "$(valor apagado_candidatos)" "no se llama a nadie"
afirmar_igual "$B" "$(valor apagado_desbloquea)" "y se suelta el cerrojo"

titulo "Lo que se guarda"
afirmar_igual "$B" "$(valor guardado_bloqueados)" "la lista del cerrojo vuelve igual"
afirmar_igual "$A" "$(valor guardado_soltados)" "los soltados vuelven igual"
afirmar_igual "200.0" "$(valor guardado_uso)" "y el ultimo uso"
afirmar_igual "$XDG_STATE_HOME/celiuz/bluetooth.json" "$(valor fichero_estado)" \
    "el cerrojo se guarda en XDG_STATE_HOME: sobrevive a un reinicio, como Blocked"
afirmar_igual "$XDG_RUNTIME_DIR/celiuz-bluetooth.json" "$(valor fichero_soltados)" \
    "los soltados en XDG_RUNTIME_DIR: un reinicio los olvida"

afirmar_intacta_la_casa_real

resumen
