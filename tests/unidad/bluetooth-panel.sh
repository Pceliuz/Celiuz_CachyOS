#!/usr/bin/env bash
# tests/unidad/bluetooth-panel.sh — que el panel de Bluetooth de la barra ENSEÑE
# bien lo que hay, sin abrir ninguna ventana ni hablar con BlueZ.
#
# QUE VIGILA
# ----------
# Lo que se ve sale de `construir()` (hypr/scripts/bluetooth-panel.py), que recibe
# la foto de BlueZ y devuelve las secciones. Aqui se le dan fotos inventadas:
#
#   - En uso, el activo primero y con su bateria (org.bluez.Battery1).
#   - Mis aparatos en el orden del demonio (ultimo uso), con el estado que el
#     demonio les da: en espera por el cerrojo, bloqueado por ti (sin boton),
#     soltado a mano. Con unos puestos y el cerrojo, el boton es «Usar este»
#     (cambiar), no «Conectar».
#   - Cerca: solo los sin emparejar que dicen su nombre (un LE sin nombre son
#     docenas de MAC al azar), los auriculares primero, y como mucho MAX_CERCA.
#   - Varios con el mismo nombre (los TWS) se distinguen por el final de la MAC;
#     uno solo no lleva etiqueta.
#   - Con el Bluetooth apagado, ni botones ni busqueda.
#   - Ajustes.guardar() (bluetooth.py) cambia solo sus dos claves y respeta lo
#     que hubiera escrito a mano en bluetooth.conf.
#   - El estilo sale ENTERO de la paleta que se le da: ni un color del autor
#     escrito a mano (la trampa de los colores copiados del CLAUDE.md).
#
# Lo que pasa por D-Bus (emparejar, cambiar de auricular con el demonio delante,
# el agente) lo prueba tests/e2e/bluetooth-panel.sh.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

RES="$TMP/resultados"

python3 - "$REPO/hypr/scripts/bluetooth-panel.py" > "$RES" 2>"$TMP/py.err" <<'PYEOF'
import importlib.util
import os
import sys
import time

spec = importlib.util.spec_from_file_location("panel", sys.argv[1])
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
bt = p.bt

SINK = "0000110b-0000-1000-8000-00805f9b34fb"
HID = "00001124-0000-1000-8000-00805f9b34fb"
AHORA = time.mktime((2026, 10, 19, 15, 0, 0, 0, 0, -1))


def aparato(mac, nombre, uuids=(SINK,), icono="audio-headset", emparejado=True,
            conectado=False, bloqueado=False, rssi=None, con_nombre=True, bateria=None):
    props = {"Address": mac, "Alias": nombre if con_nombre else mac.replace(":", "-"),
             "Icon": icono, "UUIDs": list(uuids), "Paired": emparejado,
             "Connected": conectado, "Blocked": bloqueado, "Adapter": "/org/bluez/hci0"}
    if con_nombre:
        props["Name"] = nombre
    if rssi is not None:
        props["RSSI"] = rssi
    ifaces = {bt.DISPOSITIVO: props}
    if bateria is not None:
        ifaces[p.BATERIA] = {"Percentage": bateria}
    return ("/org/bluez/hci0/dev_" + mac.replace(":", "_"), ifaces)


def foto(*aparatos, encendido=True, buscando=True):
    objetos = {"/org/bluez/hci0": {bt.ADAPTADOR: {"Powered": encendido,
                                                  "Discovering": buscando,
                                                  "Alias": "Equipo"}}}
    objetos.update(dict(aparatos))
    return objetos


def recuerdo(usos=None, bloqueados=(), soltados=(), activo=None):
    r = bt.Recuerdo()
    r.ultimo_uso = dict(usos or {})
    r.bloqueados = set(bloqueados)
    r.soltados = set(soltados)
    r.activo = activo
    return r


def ver(nombre, valor):
    print("%s=%s" % (nombre, valor))


A, B, C, D = "41:42:11:C6:EF:93", "41:42:47:57:27:25", "41:42:39:70:4D:0C", "AA:00:00:00:00:04"
usos = {A: AHORA - 60, B: AHORA - 86400 * 19, C: AHORA - 86400 * 28}

# --- 1. El caso del usuario: tres TWS, uno puesto, dos en espera ---------------
m = p.construir(foto(aparato(A, "TWS", conectado=True, bateria=80),
                     aparato(B, "TWS", bloqueado=True),
                     aparato(C, "TWS", bloqueado=True),
                     aparato(D, "Teclado", uuids=(HID,), icono="input-keyboard")),
                recuerdo(usos, bloqueados={B, C}, activo=A), bt.Ajustes(), ahora=AHORA)
ver("uso", ",".join(f.mac for f in m.en_uso))
ver("uso_bateria", m.en_uso[0].bateria)
ver("uso_accion", m.en_uso[0].accion)
ver("guardados", ",".join(f.mac for f in m.guardados))
ver("guardado_B_detalle", m.guardados[0].detalle)
ver("guardado_B_accion", m.guardados[0].accion)
ver("teclado_accion", m.guardados[2].accion)
ver("teclado_detalle", m.guardados[2].detalle)
ver("etiquetas", ",".join(f.etiqueta for f in m.en_uso + m.guardados))
ver("equipo", m.equipo)

# --- 2. Sin cerrojo, conectar es conectar ----------------------------------------
m = p.construir(foto(aparato(A, "TWS", conectado=True), aparato(B, "Otros")),
                recuerdo(usos, activo=A), bt.Ajustes(cerrojo=False), ahora=AHORA)
ver("sin_cerrojo_accion", m.guardados[0].accion)
ver("sin_cerrojo_etiquetas", ",".join(f.etiqueta for f in m.en_uso + m.guardados if f.etiqueta) or "-")

# --- 3. Bloqueado por ti, soltado a mano, y nada puesto ------------------------
m = p.construir(foto(aparato(A, "Auris A", bloqueado=True), aparato(B, "Auris B"),
                     aparato(C, "Auris C")),
                recuerdo(usos, soltados={B}), bt.Ajustes(), ahora=AHORA)
porm = {f.mac: f for f in m.guardados}
ver("por_ti_accion", porm[A].accion)
ver("por_ti_detalle", porm[A].detalle)
ver("soltado_detalle", porm[B].detalle)
ver("libre_detalle", porm[C].detalle)
ver("libre_accion", porm[C].accion)
ver("vacio_en_uso", len(m.en_uso))

# --- 4. Cerca ---------------------------------------------------------------------
cerca = [aparato("CC:00:00:00:00:%02X" % i, "Movil %d" % i, uuids=(), icono="phone",
                 emparejado=False, rssi=-50 - i) for i in range(8)]
m = p.construir(foto(aparato(A, "TWS", conectado=True),
                     aparato("BB:00:00:00:00:01", "x", emparejado=False, rssi=-40,
                             con_nombre=False),
                     aparato("BB:00:00:00:00:02", "Soundcore", emparejado=False, rssi=-80),
                     *cerca),
                recuerdo(usos, activo=A), bt.Ajustes(), ahora=AHORA)
ver("cerca_primero", m.cerca[0].nombre)
ver("cerca_marca", m.cerca[0].marca)
ver("cerca_cuantos", len(m.cerca))
ver("cerca_sin_nombre", any(f.mac == "BB:00:00:00:00:01" for f in m.cerca))
ver("cerca_accion", m.cerca[1].accion)
ver("cerca_detalle", m.cerca[1].detalle)
ver("cerca_emparejado_dentro", any(f.mac == A for f in m.cerca))

# --- 5. Apagado ------------------------------------------------------------------
m = p.construir(foto(aparato(B, "Auris B"),
                     aparato("BB:00:00:00:00:02", "Soundcore", emparejado=False),
                     encendido=False),
                recuerdo(usos), bt.Ajustes(), ahora=AHORA)
ver("apagado_acciones", ",".join(str(f.accion) for f in m.guardados))
ver("apagado_cerca", len(m.cerca))
ver("apagado_buscando", m.buscando)
m = p.construir({}, recuerdo(), bt.Ajustes(), rfkill=(True, False), ahora=AHORA)
ver("sin_adaptador", "%s %s" % (m.hay_adaptador, m.rfkill_blando))

# --- 6. Fechas y errores --------------------------------------------------------
ver("cuando_hoy", p.cuando(AHORA - 3600, AHORA))
ver("cuando_ayer", p.cuando(AHORA - 86400, AHORA))
ver("cuando_mes", p.cuando(AHORA - 86400 * 19, AHORA))
ver("cuando_anio", p.cuando(AHORA - 86400 * 400, AHORA))
ver("cuando_nunca", p.cuando(None, AHORA))
ver("err_page", p.explicar("GDBus.Error:org.bluez.Error.Failed: br-connection-page-timeout"))
ver("err_auth", p.explicar("GDBus.Error:org.bluez.Error.AuthenticationTimeout: Authentication Timeout"))
ver("err_raro", p.explicar("GDBus.Error:org.bluez.Error.Failed: algo nuevo"))

# --- 7. Ajustes.guardar respeta lo tuyo --------------------------------------------
conf = bt.fichero_ajustes()
os.makedirs(os.path.dirname(conf), exist_ok=True)
with open(conf, "w") as f:
    f.write("# mis notas\nlock = si   # en ingles\notra = cosa\n")
a = bt.Ajustes.cargar()
a.cerrojo, a.auto = False, False
a.guardar()
texto = open(conf).read()
ver("conf_notas", "# mis notas" in texto and "otra = cosa" in texto)
ver("conf_lock", "lock = no" in texto)
ver("conf_auto_anadido", "auto = no" in texto)
ver("conf_sin_duplicar", texto.count("lock") + texto.count("cerrojo"))
b = bt.Ajustes.cargar()
ver("conf_vuelta", "%s %s" % (b.cerrojo, b.auto))
os.remove(conf)
bt.Ajustes(cerrojo=True, auto=False).guardar()
c = bt.Ajustes.cargar()
ver("conf_nuevo", "%s %s" % (c.cerrojo, c.auto))

# --- 8. El estilo es de la paleta que se le da -------------------------------------
import re
verde = {k: (0.0, (i + 1) / 20.0, 0.0) for i, k in enumerate(
    ["abismo", "superficie", "apagado", "violeta", "amatista", "neon", "luz",
     "tenue", "atencion", "alerta"])}
estilo = p.css(verde, "Fuente")
permitidos = {p._hex(c) for c in verde.values()}
hexes = set(re.findall(r"#[0-9a-fA-F]{6}\b", estilo))
ver("css_hex_ajenos", ",".join(sorted(hexes - permitidos)) or "-")
rgbas = set(re.findall(r"rgba\((\d+), (\d+), (\d+)", estilo))
rgb_permitidos = {tuple(str(int(round(x * 255))) for x in c) for c in verde.values()}
rgb_permitidos.add(("0", "0", "0"))   # la sombra negra, que no es de nadie
ver("css_rgba_ajenos", ",".join(",".join(t) for t in sorted(rgbas - rgb_permitidos)) or "-")
PYEOF
codigo=$?

valor() { sed -n "s/^$1=//p" "$RES"; }

titulo "El script carga sin abrir nada"
afirmar_igual "0" "$codigo" "construir() y compañia corren sin pantalla ni bus"
if [ -s "$TMP/py.err" ]; then
    fallo "y sin escribir nada por stderr" "$(cat "$TMP/py.err")"
else
    ok "y sin escribir nada por stderr"
fi

titulo "1. Tres TWS, uno puesto y dos en espera"
afirmar_igual "41:42:11:C6:EF:93" "$(valor uso)" "en uso solo el conectado"
afirmar_igual "80" "$(valor uso_bateria)" "con su bateria"
afirmar_igual "soltar" "$(valor uso_accion)" "y el boton de soltarlo"
afirmar_igual "41:42:47:57:27:25,41:42:39:70:4D:0C,AA:00:00:00:00:04" "$(valor guardados)" \
    "los guardados en el orden del demonio, los que no son de audio al final"
afirmar_igual "Usado el 30 sep · en espera (uno a la vez)" "$(valor guardado_B_detalle)" \
    "dice cuando se uso y que el cerrojo lo tiene esperando"
afirmar_igual "cambiar" "$(valor guardado_B_accion)" "con uno puesto el boton es «Usar este»"
afirmar_igual "conectar" "$(valor teclado_accion)" "un teclado se conecta sin mas"
afirmar_igual "Teclado emparejado" "$(valor teclado_detalle)" "y dice lo que es"
afirmar_igual "…EF:93,…27:25,…4D:0C," "$(valor etiquetas)" \
    "los tres TWS llevan el final de su MAC y el teclado no"
afirmar_igual "Equipo" "$(valor equipo)" "el nombre del equipo sale del adaptador"

titulo "2. Sin cerrojo"
afirmar_igual "conectar" "$(valor sin_cerrojo_accion)" "se conecta otro sin soltar el primero"
afirmar_igual "-" "$(valor sin_cerrojo_etiquetas)" "con nombres distintos no hay etiquetas"

titulo "3. Los estados del demonio"
afirmar_igual "None" "$(valor por_ti_accion)" "uno bloqueado por ti no tiene boton"
afirmar_contiene "$RES" "^por_ti_detalle=.*bloqueado por ti" "y lo dice"
afirmar_contiene "$RES" "^soltado_detalle=.*lo soltaste" "el soltado a mano lo dice"
afirmar_contiene "$RES" "^libre_detalle=Usado el 21 sep · entra solo al encenderlo" \
    "y el libre, que entrara solo"
afirmar_igual "conectar" "$(valor libre_accion)" "sin nadie puesto, el boton es «Conectar»"
afirmar_igual "0" "$(valor vacio_en_uso)" "y en uso no hay nada"

titulo "4. Cerca, sin emparejar"
afirmar_igual "Soundcore" "$(valor cerca_primero)" "los auriculares primero, aunque se oigan peor"
afirmar_igual "listo para emparejar" "$(valor cerca_marca)" "con su marca"
afirmar_igual "6" "$(valor cerca_cuantos)" "como mucho seis"
afirmar_igual "False" "$(valor cerca_sin_nombre)" "uno que no dice su nombre no sale"
afirmar_igual "emparejar" "$(valor cerca_accion)" "el boton es emparejar"
afirmar_igual "Teléfono · muy cerca" "$(valor cerca_detalle)" "y dice que es y lo cerca que esta"
afirmar_igual "False" "$(valor cerca_emparejado_dentro)" "lo emparejado no sale en cerca"

titulo "5. Con el Bluetooth apagado"
afirmar_igual "None" "$(valor apagado_acciones)" "no hay botones de conectar"
afirmar_igual "0" "$(valor apagado_cerca)" "ni nada cerca"
afirmar_igual "False" "$(valor apagado_buscando)" "ni busqueda"
afirmar_igual "False True" "$(valor sin_adaptador)" "sin adaptador por rfkill, lo sabe"

titulo "6. Fechas y errores"
afirmar_igual "Usado hoy, 14:00" "$(valor cuando_hoy)" "hoy, con la hora"
afirmar_igual "Usado ayer" "$(valor cuando_ayer)" "ayer"
afirmar_igual "Usado el 30 sep" "$(valor cuando_mes)" "una fecha de este año"
afirmar_igual "Usado el 14 sep 2025" "$(valor cuando_anio)" "otra de otro año, con el año"
afirmar_igual "Nunca usado" "$(valor cuando_nunca)" "nunca"
afirmar_contiene "$RES" "^err_page=No contesta" "un page-timeout se explica"
afirmar_contiene "$RES" "^err_auth=No aceptó a tiempo" "un AuthenticationTimeout tambien"
afirmar_igual "algo nuevo" "$(valor err_raro)" "uno desconocido sale con su texto, sin el prefijo"

titulo "7. Los interruptores escriben bluetooth.conf sin pisar lo tuyo"
afirmar_igual "True" "$(valor conf_notas)" "los comentarios y las claves ajenas se quedan"
afirmar_igual "True" "$(valor conf_lock)" "la clave en ingles se cambia en su sitio"
afirmar_igual "True" "$(valor conf_auto_anadido)" "la que faltaba se añade"
afirmar_igual "1" "$(valor conf_sin_duplicar)" "y el cerrojo no sale dos veces"
afirmar_igual "False False" "$(valor conf_vuelta)" "bluetooth.py lee lo mismo que se escribio"
afirmar_igual "True False" "$(valor conf_nuevo)" "y sin fichero, lo crea"

titulo "8. El estilo sale de la paleta"
afirmar_igual "-" "$(valor css_hex_ajenos)" "ningun color #rrggbb que no sea de la paleta"
afirmar_igual "-" "$(valor css_rgba_ajenos)" "ni ninguna transparencia de otro color"

afirmar_intacta_la_casa_real
resumen
