#!/usr/bin/env bash
# tests/unidad/remoto.sh — Celiuz Remoto (remoto/), las piezas del servicio
# por separado: su CLI, que todo lo suyo vive FUERA del repo, y lo que no se
# puede probar por la red (la sesion que caduca, con un reloj de mentira; el
# estado en un portatil hibrido). Lo de punta a punta, en tests/e2e/remoto.sh.
#
# POR QUE: el remoto guarda claves, telefonos y un historial. Eso es de cada
# equipo (la regla de oro del CLAUDE.md), y con un $HOME de mentira tiene que
# caer dentro de esa casa, no en la de verdad ni en el repo.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
CLI="$REPO/remoto/servidor/celiuz-remoto.py"

titulo "1. revisar dice que falta, sin fallar"
salida="$("$CLI" revisar --json 2>"$TMP/err")"; codigo=$?
afirmar_igual "0" "$codigo" "sale con 0 aunque falten cosas (que falte es la respuesta)"
afirmar "   sin nada por stderr" test ! -s "$TMP/err"
afirmar "   es json con necesidades y faltan" python3 -c '
import json, sys
d = json.loads(sys.argv[1])
assert {n["que"] for n in d["necesidades"]} >= {"tailscale", "aiohttp", "adb"}
assert all(n["paquete"] in d["faltan"] for n in d["necesidades"] if not n["hay"])
' "$salida"

# Sin tailscale ni adb en el PATH, los dos tienen que salir como que faltan
mkdir -p "$TMP/vacio"
salida="$(PATH="$TMP/vacio" /usr/bin/python3 "$CLI" revisar --json 2>/dev/null)"
afirmar "   sin tailscale ni adb en el PATH, salen en «faltan»" python3 -c '
import json, sys
f = json.loads(sys.argv[1])["faltan"]
assert "tailscale" in f and "android-tools" in f, f
' "$salida"

titulo "2. Lo suyo vive fuera del repo, en la casa de quien lo corre"
salida="$("$CLI" rutas --json 2>"$TMP/err")"; codigo=$?
afirmar_igual "0" "$codigo" "rutas sale con 0"
afirmar "   todas dentro del \$HOME de mentira (el socket, en su XDG_RUNTIME_DIR)" python3 -c '
import json, os, sys
casa, repo, run = (os.path.realpath(x) for x in sys.argv[2:5])
for clave, ruta in json.loads(sys.argv[1]).items():
    r = os.path.realpath(ruta)
    dentro = run if clave == "control" else casa
    assert r.startswith(dentro + os.sep), (clave, r)
    assert not r.startswith(repo + os.sep), (clave, r)
' "$salida" "$HOME" "$REPO" "$XDG_RUNTIME_DIR"

titulo "3. Leer no crea nada"
"$CLI" dispositivos >/dev/null 2>"$TMP/err"; codigo=$?
afirmar_igual "0" "$codigo" "dispositivos sin ningun telefono sale con 0"
afirmar "   sin crear carpetas en la casa" test ! -e "$HOME/.local/state/celiuz/remoto"

titulo "4. Las piezas, una a una"
SERV="$REPO/remoto/servidor"
python3 - "$SERV" "$TMP" > "$TMP/piezas.txt" 2>"$TMP/piezas.err" <<'FINPY'
import base64, datetime as dt, json, os, sys
sys.path.insert(0, sys.argv[1])
TMP = sys.argv[2]
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from celiuz_remoto import ajustes, dispositivos as dsp, estado, pase, red, registro, sesion

def comprobar(desc, cond):
    print(("ok|" if cond else "fallo|") + desc)

# --- la sesion caduca SIN USO, no desde que se abrio
class Reloj:
    t = 1000.0
    def __call__(self): return self.t
reloj = Reloj()
alm = dsp.Almacen(os.path.join(TMP, "s", "dispositivos.json"))
priv = Ed25519PrivateKey.generate()
pub = base64.b64encode(priv.public_key().public_bytes(
    serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
d = alm.crear("Prueba", pub, dsp.hash_contrasena("abcd"), ["estado"], pase.iso(pase.ahora()))
s = sesion.Sesiones(alm, reloj=reloj, caducidad=300)
def firmar(texto): return base64.b64encode(priv.sign(texto)).decode()
r = s.reto(d["id"])
token, _ = s.entrar(d["id"], r, firmar(sesion.texto_firmado("sesion", r)), "abcd")
reloj.t += 299; comprobar("a los 299 s sin uso la sesion sigue", s.quien(token) is not None)
reloj.t += 299; comprobar("usarla la estira otros 300 s", s.quien(token) is not None)
reloj.t += 301; comprobar("a los 301 s sin uso caduca", s.quien(token) is None)
r = s.reto(d["id"]); reloj.t += 31
try:
    s.entrar(d["id"], r, firmar(sesion.texto_firmado("sesion", r)), "abcd"); comprobar("un reto de hace 31 s ya no vale", False)
except sesion.Rechazo as e:
    comprobar("un reto de hace 31 s ya no vale", e.error == "firma")
for _ in range(sesion.MAX_RETOS + 50):
    s.reto("x")
comprobar("pedir retos a lo loco no llena la memoria", len(s.retos) <= sesion.MAX_RETOS)

# --- el pase: 24 h exactas, con zona
ahora = pase.ahora()
hasta = pase.renovado(ahora)
comprobar("el pase dura 24 h exactas", pase.leer(hasta) - ahora.replace(microsecond=0) == dt.timedelta(hours=24))
comprobar("vigente un segundo antes", pase.vigente({"pase_hasta": hasta}, pase.leer(hasta) - dt.timedelta(seconds=1)))
comprobar("vencido justo a su hora", not pase.vigente({"pase_hasta": hasta}, pase.leer(hasta)))
comprobar("una fecha SIN zona no vale como pase", not pase.vigente({"pase_hasta": "2099-01-01T00:00:00"}))

# --- donde se puede escuchar
for ip, bien in (("100.113.246.39", True), ("100.64.0.1", True), ("127.0.0.1", True),
                 ("0.0.0.0", False), ("192.168.1.40", False), ("100.128.0.1", False), ("::1", False)):
    comprobar(f"escuchar en {ip}: {'si' if bien else 'no'}", red.direccion_segura(ip) == bien)

# --- remoto.conf: lo raro se ignora, no tumba
conf = os.path.join(TMP, "remoto.conf")
open(conf, "w").write("puerto_red = 5000\npuerto_usb = 80\nsesion = nada\nclave_rara = 1\n")
v = ajustes.leer(conf)
comprobar("remoto.conf: un puerto bueno se coge", v["puerto_red"] == 5000)
comprobar("remoto.conf: uno privilegiado (80) se ignora", v["puerto_usb"] == ajustes.DE_FABRICA["puerto_usb"])
comprobar("remoto.conf: un valor que no es numero se ignora", v["sesion"] == 300)

# --- un dispositivos.json roto NO se pisa (se perderian todos los telefonos)
roto = os.path.join(TMP, "roto", "dispositivos.json")
os.makedirs(os.path.dirname(roto)); open(roto, "w").write("{esto no es json")
try:
    dsp.Almacen(roto).crear("x", pub, dsp.hash_contrasena("abcd"), [], "")
    comprobar("un dispositivos.json roto no se sobrescribe", False)
except dsp.ErrorDispositivo:
    comprobar("un dispositivos.json roto no se sobrescribe", open(roto).read() == "{esto no es json")
comprobar("una clave publica que no mide 32 bytes no se acepta", not dsp.publica_valida(base64.b64encode(b"x" * 31).decode()))

# --- el registro tacha los secretos aunque alguien se los pase
registro.apuntar("prueba", "id", contrasena="secreta", token="otro")
linea = registro.ultimas(1)[0]
comprobar("el registro tacha contraseña y token", linea["contrasena"] == "***" and linea["token"] == "***")

# --- el estado de un portatil HIBRIDO: la dedicada no se toca
pci = os.path.join(TMP, "pci")
for dev, control, status in (("0000:00:02.0", "auto", "active"), ("0000:01:00.0", "auto", "suspended")):
    os.makedirs(os.path.join(pci, dev, "power"))
    open(os.path.join(pci, dev, "power", "control"), "w").write(control)
    open(os.path.join(pci, dev, "power", "runtime_status"), "w").write(status)
hw = {"tipo": "portatil", "bateria": False, "cpu": {"nombre": "CPU", "sensor": None},
      "gpus": [{"nombre": "Intel UHD 620", "fabricante": "Intel", "pci": "0000:00:02.0", "dedicada": False, "temp": False, "vram": False},
               {"nombre": "NVIDIA GeForce MX150", "fabricante": "NVIDIA", "pci": "0000:01:00.0", "dedicada": True, "temp": True, "vram": True}]}
class NvmlQueNoSeDebeUsar:
    def medir(self, pci): raise AssertionError("se desperto la NVIDIA dormida")
    def cerrar(self): pass
m = estado.Muestreador(hw=hw, nvml=NvmlQueNoSeDebeUsar(), pci_raiz=pci, casa=TMP)
try:
    g = m.tomar()["gpu"]
    comprobar("hibrido: la NVIDIA dormida sale «dormida» sin despertarla", g[1] == {"nombre": "MX150", "dormida": True})
    comprobar("hibrido: la integrada sale solo con su nombre", g[0] == {"nombre": "Intel UHD 620"})
except AssertionError as e:
    comprobar(str(e), False)
m2 = estado.Muestreador(hw=dict(hw, gpus=[]), nvml=None, pci_raiz=pci, casa=TMP)
comprobar("sin bateria, bateria es null", m2.tomar()["bateria"] is None)
comprobar("en un hibrido no se arranca NVML nunca",
          estado.Muestreador(hw=hw, pci_raiz=pci, casa=TMP).nvml is None)
FINPY
while IFS='|' read -r res desc; do
    case "$res" in
        ok) ok "$desc" ;;
        fallo) fallo "$desc" ;;
        *) fallo "salida inesperada de las piezas" "$res $desc" ;;
    esac
done < "$TMP/piezas.txt"
afirmar "   las piezas dijeron algo (no reventaron antes de empezar)" test "$(grep -c '^ok|' "$TMP/piezas.txt")" -ge 20
afirmar_no_contiene "$TMP/piezas.err" "Traceback" "   sin ningun traceback"
afirmar_contiene "$TMP/piezas.err" "no conozco «clave_rara»" "   y lo raro del remoto.conf se avisa con su linea"

afirmar_intacta_la_casa_real
resumen
