#!/usr/bin/env bash
# tests/unidad/remoto-vigilancia.sh — la vigilancia de Celiuz Remoto y la
# presencia, sin esperar la hora: reloj, Tailscale y presencia de mentira.
#
# POR QUE: es lo unico del remoto que APAGA LA PC SOLO. Los dos fallos posibles
# son malos a su manera: apagar con alguien delante (o sin saberlo), y no
# apagar con el celular robado. Cada caso de aqui es una de las reglas que se
# cerraron con el usuario (remoto/DISEÑO.md, «La vigilancia»).

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
SERV="$REPO/remoto/servidor"
# hypridle «corriendo» (lo pregunta presencia() con systemctl) y nada mas
binario_falso systemctl 0
binario_falso pgrep 0

titulo "1. Las reglas, una a una"
python3 - "$SERV" "$TMP" > "$TMP/piezas.txt" 2>"$TMP/piezas.err" <<'FINPY'
import base64, json, os, socket, sys, threading
sys.path.insert(0, sys.argv[1])
TMP = sys.argv[2]
from celiuz_remoto import dispositivos as dsp, escritorio, pase, vigilancia as vg

def comprobar(desc, cond, detalle=None):
    print(("ok|" if cond else "fallo|") + desc + ("" if cond or detalle is None else f" -> {detalle}"))

H = 3600
T0 = 1_800_000_000.0
tel = lambda **k: dict({"id": "a", "nombre": "HONOR", "ip_tailscale": "100.1.1.1",
                        "ultima_senal": None, "apagando_en": None}, **k)
en_linea = {"100.1.1.1": {"online": True, "visto": None, "nombre": "x"}}
fuera = lambda visto: {"100.1.1.1": {"online": False, "visto": visto, "nombre": "x"}}

s, c, todos = vg.decidir([tel(ultima_senal=T0 - 5 * H)], en_linea, T0)
comprobar("en línea en Tailscale: su señal es ahora, aunque llevara 5 h callado", s["a"] == T0 and not c)
comprobar("el margen es 1 h (el usuario lo bajó de 2 el 2026-10-21)", vg.MARGEN == H and vg.TEXTO_MARGEN == "1 h")
s, c, todos = vg.decidir([tel(ultima_senal=T0 - 30)], fuera(T0 - H + 60), T0)
comprobar("59 min sin señal: todavía no", not c)
s, c, todos = vg.decidir([tel(ultima_senal=T0 - 30)], fuera(T0 - H - 60), T0)
comprobar("   pero la última señal guardada (hace 30 s) manda sobre un LastSeen viejo", not c and s["a"] == T0 - 30)
s, c, todos = vg.decidir([tel(ultima_senal=T0 - H - 60)], fuera(T0 - 3 * H), T0)
comprobar("1 h 01 min sin señal: callado, y si es el único, callan todos", c == ["a"] and todos)
s, c, todos = vg.decidir([tel(ultima_senal=T0 - 59 * 60, apagando_en=T0 - 59 * 60)], fuera(None), T0)
comprobar("un «me están apagando» ya no acorta nada: es la misma hora", not c)
s, c, todos = vg.decidir([tel(ultima_senal=None)], {}, T0)
comprobar("nunca oído desde que se vigila: se cuenta desde ahora, no desde 1970", s["a"] == T0 and not c)
s, c, todos = vg.decidir([tel(ultima_senal=T0 - 3 * H)], None, T0)
comprobar("tailscale no contesta (se fue el internet): no se oye a nadie y cuenta igual", c == ["a"])
dos = [tel(), tel(id="b", ip_tailscale="100.2.2.2", ultima_senal=T0 - 3 * H)]
s, c, todos = vg.decidir(dos, dict(en_linea, **{"100.2.2.2": {"online": False, "visto": None, "nombre": "y"}}), T0)
comprobar("con dos: calla uno, el otro sigue → solo ese, no todos", c == ["b"] and not todos)
comprobar("sin teléfonos que vigilar, «todos callados» es falso (no apaga por nada)",
          vg.decidir([], {}, T0)[2] is False)

aparatos = vg.leer_tailscale(json.dumps({"Peer": {"k": {"HostName": "[ ]", "Online": True,
    "LastSeen": "0001-01-01T00:00:00Z", "TailscaleIPs": ["100.113.85.57", "fd7a::1"]}}}))
comprobar("lee `tailscale status --json` (el LastSeen 0001 es «sin dato»)",
          aparatos["100.113.85.57"] == {"online": True, "visto": None, "nombre": "[ ]"})

aparatos = vg.leer_tailscale(json.dumps({"Peer": {"k": {"HostName": "x", "Online": False,
    "LastSeen": "2026-10-21T01:10:00.1Z", "LastHandshake": "2026-10-20T20:28:02.9-05:00",
    "TailscaleIPs": ["100.113.85.57"]}}}))
comprobar("«offline» del coordinador pero saludo de WireGuard reciente: vale el saludo (el caso real del HONOR)",
          aparatos["100.113.85.57"]["visto"] == vg._epoch("2026-10-20T20:28:02.9-05:00"))

# --- la vuelta entera, con su almacen ---
class Reloj:
    t = T0
    def __call__(self): return self.t
reloj = Reloj()
alm = dsp.Almacen(os.path.join(TMP, "s", "dispositivos.json"))
pub = base64.b64encode(os.urandom(32)).decode()
d = alm.crear("HONOR", pub, dsp.hash_contrasena("abcd"), ["estado"], pase.iso(pase.ahora()))
alm.cambiar(d["id"], pase_hasta=pase.renovado(), ip_tailscale="100.1.1.1")
apagados, avisos = [], []
estado_red = {"aparatos": en_linea}
quien = {"v": ("nadie", "nadie delante")}
jugando = {"v": False}
v = vg.Vigilancia(alm, lambda: apagados.append(1), lambda t, c: avisos.append(c),
                  aparatos=lambda: estado_red["aparatos"], presencia=lambda: quien["v"], reloj=reloj,
                  jugando=lambda: jugando["v"])
comprobar("viene desarmada", v.vuelta() == "desarmada" and not apagados)
v.armar(True)
comprobar("armada y el celular en línea: vigila", v.estado == "armada")
estado_red["aparatos"] = fuera(None)
reloj.t += H - 60
comprobar("a los 59 min de silencio no hace nada", v.vuelta() == "armada" and not apagados)
quien["v"] = ("presente", "un vídeo")
reloj.t += 120
comprobar("a la 1 h 01 min CON alguien delante: no apaga, avisa", v.vuelta() == "avisando" and not apagados)
comprobar("   y le quita el pase (se recupera por cable)", not pase.vigente(alm.uno(d["id"])))
comprobar("   el aviso dice por qué no apaga", avisos and "hay alguien delante" in avisos[-1], avisos)
comprobar("   sin pase ya no se le vigila", v.vuelta() == "sin_telefonos")

alm.cambiar(d["id"], pase_hasta=pase.renovado(), ultima_senal=reloj.t - H - 60)
quien["v"] = ("no_lo_se", "hypridle no está corriendo")
comprobar("si no se sabe si hay alguien: tampoco apaga («no lo sé» no es «nadie»)",
          v.vuelta() == "avisando" and not apagados)
alm.cambiar(d["id"], pase_hasta=pase.renovado(), ultima_senal=reloj.t - H - 60)
quien["v"] = ("nadie", "sin teclado ni ratón")
jugando["v"] = True
comprobar("en el MODO GAMING, aunque hypridle diga «nadie» (se juega con mando): no apaga, avisa",
          v.vuelta() == "jugando" and not apagados, (v.estado, apagados))
comprobar("   el aviso dice que es por el modo gaming", "modo gaming" in avisos[-1], avisos[-1])
comprobar("   y le quita el pase igual", not pase.vigente(alm.uno(d["id"])))
alm.cambiar(d["id"], pase_hasta=pase.renovado(), ultima_senal=reloj.t - H - 60)
jugando["v"] = None
comprobar("si no se sabe si hay modo gaming, manda la presencia (sin nadie: apaga)",
          v.vuelta() == "apagando" and apagados == [1], (v.estado, apagados))
jugando["v"] = False
apagados.clear()
alm.cambiar(d["id"], pase_hasta=pase.renovado(), ultima_senal=reloj.t - H - 60)
comprobar("sin nadie delante: APAGA (con su cuenta atrás)", v.vuelta() == "apagando" and apagados == [1])
v.armar(False)
comprobar("desarmada, deja de vigilar", v.estado == "desarmada")
# --- preguntarle directamente al celular (el coordinador se atasca) ---
alm.cambiar(d["id"], pase_hasta=pase.renovado(), ultima_senal=reloj.t - 3 * H)
sondeos = []
contesta = {"v": True}
v2 = vg.Vigilancia(alm, lambda: apagados.append(2), lambda t, c: None,
                   aparatos=lambda: fuera(reloj.t - 3 * H), presencia=lambda: ("nadie", "x"),
                   reloj=reloj, sondear=lambda ip: (sondeos.append(ip), contesta["v"])[1],
                   jugando=lambda: False)
v2.armar(True)
comprobar("coordinador dice «offline 3 h» pero el celular contesta al ping: NO calla, no apaga",
          v2.estado == "armada" and apagados == [1] and sondeos == ["100.1.1.1"], (v2.estado, apagados, sondeos))
reloj.t += 60
v2.vuelta()
comprobar("   y no se le vuelve a preguntar hasta pasados 5 min (un paquete, nada de batería)",
          len(sondeos) == 1, sondeos)
alm.cambiar(d["id"], ultima_senal=reloj.t - 3 * H)
contesta["v"] = False
reloj.t += 301
comprobar("si tampoco contesta al ping: calla (y sin nadie delante, apaga)",
          v2.vuelta() == "apagando" and apagados == [1, 2] and len(sondeos) == 2, (v2.estado, apagados, sondeos))
v2.armar(False)

r = v.resumen()
comprobar("el resumen para la PC dice qué pasa con cada teléfono",
          r["telefonos"][0]["nombre"] == "HONOR" and "presencia" in r and r["armada"] is False)

# --- la presencia, en tres salidas ---
run = os.path.join(TMP, "run"); os.environ["XDG_RUNTIME_DIR"] = run
comprobar("sin ningún Hyprland vivo: nadie", escritorio.presencia()[0] == "nadie")
firma = "abc_1792449598_1"
carpeta = os.path.join(run, "hypr", firma); os.makedirs(carpeta)
srv = socket.socket(socket.AF_UNIX); srv.bind(os.path.join(carpeta, ".socket.sock")); srv.listen(8)
def atender():
    while True:
        try: srv.accept()[0].close()
        except OSError: return
threading.Thread(target=atender, daemon=True).start()
os.makedirs(os.path.join(run, "hypr", "muerta_1700000000_1"))
comprobar("encuentra el Hyprland vivo (y no la carpeta de uno muerto)", escritorio.instancia() == firma)
comprobar("sesión recién abierta, sin nada apuntado: presente", escritorio.presencia()[0] == "presente")
os.environ["HYPRLAND_INSTANCE_SIGNATURE"] = firma
escritorio.marcar_presencia("ausente")
comprobar("hypridle apunta «ausente»: nadie", escritorio.presencia()[0] == "nadie")
escritorio.marcar_presencia("presente")
comprobar("y al volver, presente", escritorio.presencia()[0] == "presente")
os.environ["HYPRLAND_INSTANCE_SIGNATURE"] = "otra_1600000000_1"
escritorio.marcar_presencia("ausente")
comprobar("un «ausente» de OTRA sesión no cuenta", escritorio.presencia()[0] == "presente")

# --- el modo gaming, preguntado al modo-gaming.py DE VERDAD (no se copia su ruta)
del os.environ["HYPRLAND_INSTANCE_SIGNATURE"]   # el servicio no la trae: la busca
comprobar("sin modo gaming puesto: no", escritorio.modo_gaming() is False, escritorio.modo_gaming())
json.dump({"activo": True, "desde": 1}, open(os.path.join(run, "modo-gaming.%s.json" % firma), "w"))
comprobar("con el modo gaming de ESTA sesión puesto: sí", escritorio.modo_gaming() is True)
os.remove(os.path.join(run, "modo-gaming.%s.json" % firma))
json.dump({"activo": True, "desde": 1}, open(os.path.join(run, "modo-gaming.otra_1600000000_1.json"), "w"))
comprobar("el modo gaming de OTRA sesión no cuenta", escritorio.modo_gaming() is False)
FINPY
while IFS='|' read -r res desc; do
    case "$res" in
        ok) ok "$desc" ;;
        fallo) fallo "$desc" ;;
        *) fallo "salida inesperada" "$res $desc" ;;
    esac
done < "$TMP/piezas.txt"
afirmar "   dijeron algo (no reventó antes de empezar)" test "$(grep -c '^ok|' "$TMP/piezas.txt")" -ge 25
afirmar "   sin nada por stderr" test ! -s "$TMP/piezas.err"

titulo "2. hypridle: sin él, «no lo sé»"
binario_falso systemctl 3
binario_falso pgrep 1
salida="$(python3 - "$SERV" "$TMP" <<'FINPY'
import os, socket, sys, threading
sys.path.insert(0, sys.argv[1])
run = os.path.join(sys.argv[2], "run2"); os.environ["XDG_RUNTIME_DIR"] = run
from celiuz_remoto import escritorio
c = os.path.join(run, "hypr", "x_1792449598_1"); os.makedirs(c)
s = socket.socket(socket.AF_UNIX); s.bind(os.path.join(c, ".socket.sock")); s.listen(8)
threading.Thread(target=lambda: [s.accept()[0].close() for _ in iter(int, 1)], daemon=True).start()
print(escritorio.presencia()[0])
FINPY
)"
afirmar_igual "no_lo_se" "$salida" "con sesión pero sin hypridle: no_lo_se (y eso no apaga)"
afirmar_contiene "$REPO/hypr/hypridle.conf" "on-timeout = \\\$HOME/.local/bin/celiuz-remoto presencia ausente" \
    "hypridle.conf apunta la ausencia"
afirmar_contiene "$REPO/hypr/hypridle.conf" "on-resume = \\\$HOME/.local/bin/celiuz-remoto presencia presente" \
    "   y la vuelta"
afirmar_igual "300" "$(grep -B2 'presencia ausente' "$REPO/hypr/hypridle.conf" | sed -n 's/.*timeout = \([0-9]*\).*/\1/p')" \
    "   a los 300 s, el mismo número que PRESENCIA_S"

afirmar_intacta_la_casa_real
resumen
