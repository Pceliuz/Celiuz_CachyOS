#!/usr/bin/env bash
# tests/unidad/wifi-panel.sh — el panel de red de la barra: que lea bien nmcli,
# que ENSEÑE bien lo que hay y que cada boton mande la orden que toca. Sin
# ventana, sin NetworkManager y sin tocar la red: nmcli, rfkill y qrencode son
# de mentira.
#
# QUE VIGILA
# ----------
#   - El modo terso de nmcli escapa «:» y «\» (un SSID puede llevarlos).
#   - Un router de doble banda son dos puntos de acceso: una sola red.
#   - Conectado arriba con sus IP (las dos, la secundaria de la oficina
#     tambien); las guardadas al alcance con boton, y «mejor señal» si se oye
#     bastante mejor que la actual; las de fuera de alcance, sin boton; el cable
#     sin enchufar, a la vista. Las otras: las 4 mejores y el resto plegado.
#   - Una red de empresa (802.1X) o WEP va a «Ajustes avanzados».
#   - En un equipo sin wifi (la PC con cable) el panel enseña el cable.
#   - Cada boton: la orden de nmcli exacta, y su error explicado.
#   - La contraseña para el QR entra a qrencode por la entrada estandar, nunca
#     como argumento.
#   - El estilo sale entero de la paleta (es el mismo que el del Bluetooth).
#
# Conectar a una red NUEVA va por D-Bus y lo prueba tests/e2e/wifi-panel.sh.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

RES="$TMP/resultados"
binario_falso nmcli 0 'case "$*" in
    *"connection up uuid u-mala"*) echo "Error: Connection activation failed: Secrets were required, but not provided." >&2; exit 4 ;;
esac'
binario_falso rfkill 0
binario_falso qrencode 0 'cat > "'"$REGISTRO"'/qrencode.stdin"; printf "PNG"'

PATH="$FALSOS:$PATH" python3 - "$REPO/hypr/scripts/wifi-panel.py" > "$RES" 2>"$TMP/py.err" <<'PYEOF'
import importlib.util
import re
import sys

spec = importlib.util.spec_from_file_location("panel", sys.argv[1])
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def ver(nombre, valor):
    print("%s=%s" % (nombre, valor))


# --- 1. Leer nmcli -----------------------------------------------------------------
ver("partir", p.partir(r"*:Casa\:5G:64:WPA2:2412 MHz"))
ver("partir_barra", p.partir(r"a\\b:c"))
REDES = "\n".join([
    "*:TP-LINK_181C:64:WPA2:2412 MHz",
    " :[ ]:100:WPA2:5745 MHz",
    " :HUAWEI-9KgC:64:WPA1 WPA2:2422 MHz",
    " :HUAWEI-9KgC:14:WPA1 WPA2:5180 MHz",
    " :SBINFRAESTRUCTURA:50:WPA2:2462 MHz",
    " :Redmi 14C:40:WPA2:2412 MHz",
    " :Yuli:40:WPA1 WPA2:2412 MHz",
    " :Aula_TIC:27:WPA1 WPA2:2412 MHz",
    " :IRENE:24:WPA1 WPA2:2412 MHz",
    " :Cafe libre:30::2412 MHz",
    " :Oficina:70:WPA2 802.1X:5180 MHz",
    " ::90:WPA2:2412 MHz",
])
redes = p.leer_redes(REDES)
ver("huawei", "%d %s" % (redes["HUAWEI-9KgC"]["senal"], sorted(redes["HUAWEI-9KgC"]["bandas"])))
ver("oculta", "" in redes)
ver("en_uso", [s for s, r in redes.items() if r["en_uso"]])
ver("ssids", p.leer_ssids("connection.uuid:u1\n802-11-wireless.ssid:A:B\n\n"
                          "connection.uuid:u2\n802-11-wireless.ssid:[ ]\n"))

DISP = p.leer_dispositivos("wlan0:wifi:connected:TP-LINK_181C\nenp1s0:ethernet:unavailable:\n"
                           "lo:loopback:connected (externally):lo\n")
CONEX = p.leer_conexiones("TP-LINK_181C:u-tplink:802-11-wireless:yes:wlan0\n"
                          "[ ]:u-corchetes:802-11-wireless:yes:\n"
                          "TITITO 5G:u-titito:802-11-wireless:no:\n"
                          "Conexión cableada 1:u-cable:802-3-ethernet:yes:\n")
datos = {"dispositivos": DISP, "wifi_hw": True, "wifi_on": True, "redes": redes,
         "conexiones": CONEX, "ssids": {"u-tplink": "TP-LINK_181C", "u-corchetes": "[ ]",
                                        "u-titito": "TITITO 5G"},
         "ips": {"wlan0": ["192.168.0.113", "192.168.57.113"]}, "conectividad": "full"}

# --- 2. Lo que se ve ------------------------------------------------------------------
m = p.construir(datos)
c = m.conectados[0]
ver("conectado", "%s|%s|%s|%s" % (c.nombre, c.detalle, c.accion, ",".join(c.ips)))
ver("conectado_editable", c.editable)
ver("guardadas", ",".join(f.nombre for f in m.guardadas))
g = {f.nombre: f for f in m.guardadas}
ver("corchetes", "%s|%s|%s" % (g["[ ]"].detalle, g["[ ]"].marca, g["[ ]"].accion))
ver("titito", "%s|%s" % (g["TITITO 5G"].detalle, g["TITITO 5G"].accion))
ver("cable", "%s|%s" % (g["Cable (enp1s0)"].detalle, g["Cable (enp1s0)"].accion))
ver("otras", ",".join(f.nombre for f in m.otras))
ver("otras_huawei", next(f for f in m.otras if f.nombre == "HUAWEI-9KgC").detalle)
ver("oficina", "%s|%s" % (next(f for f in m.otras if f.nombre == "Oficina").accion,
                          next(f for f in m.otras if f.nombre == "Oficina").detalle))
ver("mas_otras", m.mas_otras)
cafe = next(f for f in m.resto if f.nombre == "Cafe libre")
ver("cafe", "%s|%s|%s" % (cafe.seguridad, cafe.candado, cafe.accion))
ver("portal", c.portal)

datos_portal = dict(datos, conectividad="portal")
ver("portal_si", p.construir(datos_portal).conectados[0].portal)

apagado = p.construir(dict(datos, wifi_on=False,
                           dispositivos=p.leer_dispositivos("wlan0:wifi:unavailable:\n")))
ver("apagado", "%s|%d|%s" % (apagado.wifi_on, len(apagado.otras),
                             ",".join(f.detalle for f in apagado.guardadas)))

# Sin wifi y con cable (la PC del autor).
pc = p.construir({"dispositivos": p.leer_dispositivos("enp3s0:ethernet:connected:Cable 1\n"),
                  "conexiones": p.leer_conexiones("Cable 1:u-c:802-3-ethernet:yes:enp3s0\n"),
                  "ips": {"enp3s0": ["192.168.1.20"]}, "redes": {}})
ver("pc", "%s|%s|%s" % (pc.hay_wifi, pc.conectados[0].nombre, pc.conectados[0].accion))
enchufado = p.construir({"dispositivos": p.leer_dispositivos("enp3s0:ethernet:disconnected:\n"),
                         "conexiones": [], "redes": {}})
ver("enchufado", "%s|%s" % (enchufado.guardadas[0].detalle, enchufado.guardadas[0].accion))

# --- 3. Pequeñas piezas ---------------------------------------------------------
ver("seguridad", ",".join(p.tipo_seguridad(x) for x in
                          ("", "--", "WPA2", "WPA1 WPA2", "WPA3", "WPA2 WPA3", "WPA2 802.1X", "WEP")))
ver("rayas", ",".join(str(p.G_SENAL.index(p.glifo_senal(x))) for x in (0, 10, 30, 55, 80, 100)))
ver("qr", p.texto_qr('Ca;sa:"5G"', "a,b\\c"))
ver("qr_abierta", p.texto_qr("Cafe", "", "abierta"))
ver("vel", p.velocidad((0, 0), (1_500_000, 48_000), 1.0))
ver("vel_bajo", p.velocidad((0, 0), (300, 12_000), 1.0))
ver("err_clave", p.explicar("Error: Connection activation failed: Secrets were required, but not provided."))
ver("err_tiempo", p.explicar("Error: Timeout expired (90 seconds)"))
ver("err_raro", p.explicar("Error: algo nuevo\n"))

# --- 4. Lo que manda cada boton --------------------------------------------------
import threading  # noqa: E402
hecho = threading.Event()
respuestas = []


def esperar(orden, *args):
    hecho.clear()
    orden(*args, lambda e, *_: (respuestas.append(e), hecho.set()))
    hecho.wait(10)
    return respuestas[-1]


ctl = p.Control()
ver("r_conectar", esperar(ctl.conectar, "u-corchetes"))
ver("r_mala", esperar(ctl.conectar, "u-mala"))
esperar(ctl.desconectar, "u-tplink")
esperar(ctl.olvidar, "u-titito")
esperar(ctl.autoconectar, "u-tplink", False)
esperar(ctl.cable, "enp1s0")
esperar(ctl.wifi, False)
esperar(ctl.avion, True)
esperar(ctl.buscar)

from types import SimpleNamespace  # noqa: E402
paleta = {k: (0.0, (i + 1) / 20.0, 0.0) for i, k in enumerate(
    ["abismo", "superficie", "apagado", "violeta", "amatista", "neon", "luz",
     "tenue", "atencion", "alerta"])}
ver("qr_png", p.qr_png(p.texto_qr("Casa", "secreto-de-prueba"), paleta).decode())

estilo = p.css(paleta, "Fuente")
permitidos = {p._hex(x) for x in paleta.values()}
ver("css_hex_ajenos", ",".join(sorted(set(re.findall(r"#[0-9a-fA-F]{6}\b", estilo)) - permitidos)) or "-")
PYEOF
codigo=$?

valor() { sed -n "s/^$1=//p" "$RES"; }

titulo "El script carga sin abrir nada"
afirmar_igual "0" "$codigo" "corre sin pantalla ni NetworkManager"
if [ -s "$TMP/py.err" ]; then fallo "y sin nada por stderr" "$(cat "$TMP/py.err")"; else ok "y sin nada por stderr"; fi

titulo "1. Leer nmcli"
afirmar_igual "['*', 'Casa:5G', '64', 'WPA2', '2412 MHz']" "$(valor partir)" "los dos puntos escapados del SSID se respetan"
afirmar_igual "['a\\\\b', 'c']" "$(valor partir_barra)" "y la barra escapada"
afirmar_igual "64 ['2.4 GHz', '5 GHz']" "$(valor huawei)" "doble banda: una red, con la mejor señal y las dos bandas"
afirmar_igual "False" "$(valor oculta)" "una red oculta (sin nombre) no sale"
afirmar_igual "['TP-LINK_181C']" "$(valor en_uso)" "se sabe cual esta en uso"
afirmar_igual "{'u1': 'A:B', 'u2': '[ ]'}" "$(valor ssids)" "los SSID de cada perfil, por bloques"

titulo "2. Lo que enseña"
afirmar_igual "TP-LINK_181C|64% · 2.4 GHz · WPA2|desconectar|192.168.0.113,192.168.57.113" \
    "$(valor conectado)" "conectado: señal, banda, seguridad y las dos IP, con «Desconectar»"
afirmar_igual "True" "$(valor conectado_editable)" "y con «⋯» (para compartirla)"
afirmar_igual "[ ],TITITO 5G,Cable (enp1s0)" "$(valor guardadas)" \
    "mis redes: las de alcance primero, las de fuera despues, y el cable al final"
afirmar_igual "100% · 5 GHz · se conecta sola|mejor señal|conectar" "$(valor corchetes)" \
    "una guardada que se oye mucho mejor lleva «mejor señal»"
afirmar_igual "Fuera de alcance|None" "$(valor titito)" "la de fuera de alcance, sin boton"
afirmar_igual "Sin cable enchufado|None" "$(valor cable)" "el cable sin enchufar, a la vista"
afirmar_igual "Oficina,HUAWEI-9KgC,SBINFRAESTRUCTURA,Redmi 14C" "$(valor otras)" \
    "otras: las 4 de mas señal (empates por nombre)"
afirmar_igual "64% · 2.4 y 5 GHz" "$(valor otras_huawei)" "con sus bandas"
afirmar_igual "avanzado|70% · 5 GHz · de empresa" "$(valor oficina)" "una de empresa va a ajustes avanzados"
afirmar_igual "4" "$(valor mas_otras)" "el resto, plegado"
afirmar_igual "abierta|False|nueva" "$(valor cafe)" "una abierta: sin candado, conecta sin contraseña"
afirmar_igual "False" "$(valor portal)" "sin portal no hay aviso"
afirmar_igual "True" "$(valor portal_si)" "con portal (hotel, oficina), se avisa"
afirmar_igual "False|0|Fuera de alcance,Fuera de alcance,Fuera de alcance" "$(valor apagado)" \
    "con el wifi apagado: ni otras redes ni botones"
afirmar_igual "False|Cable (enp3s0)|desconectar" "$(valor pc)" "sin wifi (la PC), el cable conectado arriba"
afirmar_igual "Enchufado, sin conectar|cable" "$(valor enchufado)" "un cable enchufado y sin conectar, con boton"

titulo "3. Piezas"
afirmar_igual "abierta,abierta,psk,psk,sae,psk,empresa,wep" "$(valor seguridad)" "el tipo de seguridad"
afirmar_igual "0,1,2,3,4,4" "$(valor rayas)" "las rayas de la señal"
afirmar_igual 'WIFI:T:WPA;S:Ca\;sa\:\"5G\";P:a\,b\\c;;' "$(valor qr)" "el QR escapa lo que el formato pide"
afirmar_igual "WIFI:T:nopass;S:Cafe;;" "$(valor qr_abierta)" "y una abierta va sin contraseña"
afirmar_igual "↓ 1.5 MB/s   ↑ 48 kB/s" "$(valor vel)" "la velocidad"
afirmar_igual "↓ 300 B/s   ↑ 12 kB/s" "$(valor vel_bajo)" "y la de poco trafico"
afirmar_contiene "$RES" "^err_clave=Contraseña incorrecta" "los errores de nmcli se explican"
afirmar_contiene "$RES" "^err_tiempo=No contesta" "el de tiempo tambien"
afirmar_igual "algo nuevo" "$(valor err_raro)" "uno desconocido, con su texto y sin «Error:»"

titulo "4. Cada boton, su orden"
afirmar_igual "None" "$(valor r_conectar)" "conectar una guardada contesta bien"
afirmar_contiene "$RES" "^r_mala=Contraseña incorrecta" "y si falla, el error explicado"
L="$REGISTRO/nmcli.log"
afirmar_contiene "$L" "^connection up uuid u-corchetes$" "conectar: connection up por uuid"
afirmar_contiene "$L" "^connection down uuid u-tplink$" "desconectar: connection down (no «device disconnect», que apaga la tarjeta)"
afirmar_contiene "$L" "^connection delete uuid u-titito$" "olvidar: connection delete"
afirmar_contiene "$L" "^connection modify uuid u-tplink connection.autoconnect no$" "conectar sola: modify"
afirmar_contiene "$L" "^device connect enp1s0$" "el cable: device connect"
afirmar_contiene "$L" "^radio wifi off$" "el interruptor: radio wifi"
afirmar_contiene "$L" "^device wifi rescan$" "buscar: rescan"
afirmar_contiene "$REGISTRO/rfkill.log" "^block all$" "el modo avion: rfkill block all, sin sudo"
afirmar_igual "PNG" "$(valor qr_png)" "el QR sale de qrencode"
afirmar_contiene "$REGISTRO/qrencode.stdin" "secreto-de-prueba" "con la contraseña por la entrada estandar"
afirmar_no_contiene "$REGISTRO/qrencode.log" "secreto-de-prueba" "y no como argumento"
afirmar_igual "-" "$(valor css_hex_ajenos)" "el estilo sale de la paleta"

afirmar_intacta_la_casa_real
resumen
