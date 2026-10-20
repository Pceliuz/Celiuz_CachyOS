#!/usr/bin/env bash
# tests/unidad/reloj-panel.sh — el panel del reloj (calendar-panel.py) y lo que
# lo alimenta: la luna y el zodiaco (lib/cielo.py) y el tiempo y la ubicacion
# (lib/clima.py). Sin ventana y SIN INTERNET: la unica puerta a la red de
# clima.py (`pedir`) se sustituye por una que apunta a quien se pregunta.
#
# QUE VIGILA, sobre todo la privacidad (lo pidio el usuario):
#   - En la MISMA red no se pregunta donde estas; en una nueva, UNA vez.
#   - Lo que se guarda y lo que se manda: la ciudad, redondeada a 0,1° (~10 km),
#     y solo la ULTIMA (sin historial), en un fichero 0600; de la red, un
#     resumen, no su nombre.
#   - «ubicacion = zona», una fija o «clima = no»: CERO preguntas.
#   - El tiempo se pide como mucho cada 15 minutos, y sin conexion se enseña el
#     guardado diciendo de cuando es.
#   - La luna cae en fechas conocidas, y el zodiaco cambia en sus cortes.
#   - La orbita: una sola hora delante, y en t=0 es la primera.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

RES="$TMP/resultados"
export TMP
# nmcli de mentira: la conexion activa es lo que diga $TMP/red.txt.
binario_falso nmcli 0 'cat "'"$TMP"'/red.txt"'
export PATH="$FALSOS:$PATH"

python3 - "$REPO/hypr/scripts" > "$RES" 2>"$TMP/py.err" <<'PYEOF'
import datetime as dt
import importlib.util
import json
import os
import stat
import sys

sys.path.insert(0, os.path.join(sys.argv[1], "lib"))
import cielo  # noqa: E402
import clima  # noqa: E402

spec = importlib.util.spec_from_file_location("panel", os.path.join(sys.argv[1], "calendar-panel.py"))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def ver(nombre, valor):
    print("%s=%s" % (nombre, valor))


# --- La luna y el zodiaco ------------------------------------------------------------
def fase(d):
    return cielo.luna(dt.datetime.fromisoformat(d + "T12:00+00:00"))


ver("llena_ene", fase("2026-01-03")["nombre"])
ver("nueva_ene", fase("2026-01-18")["nombre"])
ver("gibosa", "%s %d" % (fase("2026-10-19")["nombre"], round(fase("2026-10-19")["iluminada"] * 100)))
ver("menguante", fase("2026-11-01")["nombre"])
ver("cortes", ",".join(cielo.zodiaco(dt.date.fromisoformat(d))["nombre"] for d in
                       ("2026-01-19", "2026-01-20", "2026-02-18", "2026-02-19", "2026-12-21",
                        "2026-12-22", "2027-01-05")))
ver("libra_hasta", cielo.zodiaco(dt.date(2026, 10, 19))["hasta"])
ver("acuario_en", cielo.dias_para("ACUARIO", dt.date(2026, 10, 19)))
ver("acuario_hoy", cielo.dias_para("acuario", dt.date(2027, 2, 1)))
ver("signo_raro", cielo.buscar_signo("ofiuco"))
ver("zod_tu", p.texto_zodiaco(dt.date(2026, 10, 19), "acuario")[2].split("  ", 1)[1])

# --- El panel: piezas -----------------------------------------------------------
ver("feriado", "%s|%s|%d" % p.proximo_feriado(dt.date(2026, 10, 19)))
ver("sol_tarde", round(p.arco_sol(12 * 60, "06:00", "18:00"), 2))
ver("sol_noche", p.arco_sol(20 * 60, "06:00", "18:00"))
pos = p.orbita(12, 0.0, 100, 100, 80, 30)
ver("orbita_delante", [q[0] for q in pos if q[4]])
pos2 = p.orbita(12, 0.04, 100, 100, 80, 30)
ver("orbita_una", sum(1 for q in pos2 if q[4]))
ver("orbita_gira", round(pos2[0][1] - pos[0][1], 1) != 0)
ver("medidores", [m[1] for m in p.medidores({"viento": 3.14, "humedad": 82, "lluvia": 0,
                                               "sensacion": 25.4})])

# --- Ubicacion y tiempo, sin internet -----------------------------------------------
preguntas = []
RESPUESTAS = {
    "ipinfo": {"city": "Lima", "loc": "-12.0464,-77.0428", "region": "Lima"},
    "forecast": {
        "current": {"time": "2026-10-19T18:15", "temperature_2m": 22.8,
                    "apparent_temperature": 25.4, "relative_humidity_2m": 82,
                    "wind_speed_10m": 3.1, "weather_code": 3,
                    "precipitation_probability": 0, "is_day": 0},
        "hourly": {"time": ["2026-10-%02dT%02d:00" % (19 + h // 24, h % 24) for h in range(48)],
                   "temperature_2m": [20 + h / 10 for h in range(48)],
                   "weather_code": [3] * 48, "precipitation_probability": [0] * 48,
                   "is_day": [1 if 6 <= h % 24 < 18 else 0 for h in range(48)]},
        "daily": {"sunrise": ["2026-10-19T05:41"], "sunset": ["2026-10-19T18:05"]},
    },
    "search": {"results": [{"name": "Arequipa", "latitude": -16.39889, "longitude": -71.535}]},
}
sin_red = {"activo": False}


def pedir(url, plazo=None):
    preguntas.append(url)
    if sin_red["activo"]:
        raise OSError("sin red")
    for clave, r in RESPUESTAS.items():
        if clave in url:
            return json.loads(json.dumps(r))
    raise OSError(url)


clima.pedir = pedir
# La red sale del nmcli de mentira (ver abajo): lo que imprima $TMP/red.txt.
red_txt = os.path.join(os.environ["TMP"], "red.txt")


class Red:
    def __setitem__(self, _k, uuid):
        with open(red_txt, "w") as f:
            f.write("%s:802-11-wireless\n" % uuid)


red = Red()
red["actual"] = "uuid-de-casa"
conf = clima.fichero_ajustes()
os.makedirs(os.path.dirname(conf), exist_ok=True)


def poner_conf(texto):
    with open(conf, "w") as f:
        f.write(texto)


poner_conf("ubicacion = auto\n")
r = clima.obtener(ahora=1000.0)
ver("primera", "%s|%s|%d" % (r["ciudad"], r["tiempo"]["temp"], len(preguntas)))
ver("pide_ip", sum("ipinfo" in u for u in preguntas))
ver("url_redondeada", next(u for u in preguntas if "forecast" in u).split("?")[1].split("&current")[0])
guardada = json.load(open(clima.fichero_ubicacion()))
ver("guardado", "%s %s %s" % (guardada["lat"], guardada["lon"], sorted(guardada)))
import hashlib  # noqa: E402
ver("red_resumen", "%s|%s" % ("uuid-de-casa" in json.dumps(guardada),
                              guardada["red"] == hashlib.sha256(b"uuid-de-casa").hexdigest()[:16]))
ver("modo_ubicacion", oct(stat.S_IMODE(os.stat(clima.fichero_ubicacion()).st_mode)))
ver("modo_tiempo", oct(stat.S_IMODE(os.stat(clima.fichero_tiempo()).st_mode)))

antes = len(preguntas)
r = clima.obtener(ahora=1000.0 + 600)          # 10 min despues, misma red
ver("a_los_10min", len(preguntas) - antes)
r = clima.obtener(ahora=1000.0 + 16 * 60)      # pasados los 15 min
ver("a_los_16min", ",".join("ip" if "ipinfo" in u else "tiempo" for u in preguntas[antes:]))

antes = len(preguntas)
red["actual"] = "uuid-de-la-oficina"                  # otra red: una pregunta de ubicacion
RESPUESTAS["ipinfo"] = {"city": "Callao", "loc": "-12.0566,-77.1181"}
clima.obtener(ahora=5000.0, forzar=True)
ver("red_nueva", sum("ipinfo" in u for u in preguntas[antes:]))
guardada = json.load(open(clima.fichero_ubicacion()))
ver("sin_historial", "%s|%s" % (guardada["ciudad"], "Lima" in json.dumps(guardada)))

antes = len(preguntas)
sin_red["activo"] = True
r = clima.obtener(ahora=5000.0 + 20 * 60)
ver("sin_conexion", "%s|%s" % (r["tiempo"] is not None, r.get("error", "")[:13]))
sin_red["activo"] = False

for modo, texto in (("zona", "ubicacion = zona\n"),
                    ("fija", "ubicacion = -12.123,-77.456 Mi casa\n"),
                    ("apagado", "clima = no\n")):
    poner_conf(texto)
    antes = len(preguntas)
    if modo == "apagado":
        ver("apagado", clima.obtener(ahora=9e9).get("apagado"))
        ver("apagado_preguntas", len(preguntas) - antes)
    else:
        u = clima.ubicacion(clima.ajustes())
        ver(modo, "%s|%s|%s|%d" % (u and u["lat"], u and u["lon"], u and u["ciudad"],
                                    len(preguntas) - antes))

poner_conf("ubicacion = Arequipa\n")
antes = len(preguntas)
u1 = clima.ubicacion(clima.ajustes())
u2 = clima.ubicacion(clima.ajustes())
ver("por_nombre", "%s|%s|%d" % (u1["ciudad"], u1["lat"], len(preguntas) - antes))

ver("zona_iso", clima._iso6709("-1203-07703"))
ver("zona_iso_seg", clima._iso6709("+404251-0740023"))
ver("describir", "%s|%s" % (clima.describir(0, True)[0], clima.describir(61, False)[0]))
t = clima.interpretar(RESPUESTAS["forecast"])
ver("horas", "%d %s %s" % (len(t["horas"]), t["horas"][0]["hora"], t["horas"][0]["dia"]))
ver("hace", ",".join(clima.hace(s) for s in (30, 600, 7200, 200000)))
PYEOF
codigo=$?

valor() { sed -n "s/^$1=//p" "$RES"; }

titulo "Carga sin abrir nada ni salir a internet"
afirmar_igual "0" "$codigo" "corre sin pantalla"
if [ -s "$TMP/py.err" ]; then fallo "y sin nada por stderr" "$(cat "$TMP/py.err")"; else ok "y sin nada por stderr"; fi

titulo "1. La luna y el zodiaco"
afirmar_igual "Luna llena" "$(valor llena_ene)" "el 3 de enero de 2026 es luna llena"
afirmar_igual "Luna nueva" "$(valor nueva_ene)" "el 18, nueva"
afirmar_igual "Creciente gibosa 58" "$(valor gibosa)" "el 19 de octubre a mediodia UTC, creciente gibosa al 58% (por lo iluminado; por dias salia «cuarto»)"
afirmar_igual "Menguante gibosa" "$(valor menguante)" "y despues de la llena, menguante"
afirmar_igual "Capricornio,Acuario,Acuario,Piscis,Sagitario,Capricornio,Capricornio" "$(valor cortes)" \
    "el zodiaco cambia en sus cortes, tambien al cruzar el año"
afirmar_igual "2026-10-22" "$(valor libra_hasta)" "Libra acaba el 22 de octubre"
afirmar_igual "93" "$(valor acuario_en)" "faltan 93 dias para Acuario (sin importar mayusculas)"
afirmar_igual "0" "$(valor acuario_hoy)" "y dentro de su temporada, 0"
afirmar_igual "None" "$(valor signo_raro)" "un signo que no existe no rompe nada"
afirmar_igual "Acuario (tú) · en 93 días" "$(valor zod_tu)" "el tuyo, si lo pones en clima.conf"

titulo "2. El panel"
afirmar_igual "2026-11-01|Dia de Todos los Santos|13" "$(valor feriado)" "el proximo feriado"
afirmar_igual "0.5" "$(valor sol_tarde)" "el sol a mediodia, a la mitad del arco"
afirmar_igual "None" "$(valor sol_noche)" "de noche, sin sol"
afirmar_igual "[0]" "$(valor orbita_delante)" "en t=0 delante va la primera hora"
afirmar_igual "1" "$(valor orbita_una)" "y nunca hay dos delante"
afirmar_igual "True" "$(valor orbita_gira)" "y se mueve con el tiempo"
afirmar_igual "['3.1 m/s', '82%', '0%', '25°C']" "$(valor medidores)" "los medidores"

titulo "3. Privacidad: cuando se pregunta donde estas"
afirmar_igual "Lima|22.8|2" "$(valor primera)" "la primera vez: ubicacion y tiempo, dos preguntas"
afirmar_igual "1" "$(valor pide_ip)" "una sola de ubicacion"
afirmar_igual "latitude=-12.0&longitude=-77.0" "$(valor url_redondeada)" \
    "a Open-Meteo le llega la ciudad redondeada, no las coordenadas exactas"
afirmar_igual "-12.0 -77.0 ['ciudad', 'cuando', 'lat', 'lon', 'red']" "$(valor guardado)" \
    "se guarda redondeado, y solo eso"
afirmar_igual "False|True" "$(valor red_resumen)" "de la red, un resumen (sha256) y no su identificador"
afirmar_igual "0o600" "$(valor modo_ubicacion)" "el fichero de la ubicacion solo es tuyo"
afirmar_igual "0o600" "$(valor modo_tiempo)" "y el del tiempo tambien"
afirmar_igual "0" "$(valor a_los_10min)" "a los 10 minutos y en la misma red: cero preguntas"
afirmar_igual "tiempo" "$(valor a_los_16min)" "pasados 15: solo el tiempo, la ubicacion no se vuelve a pedir"
afirmar_igual "1" "$(valor red_nueva)" "en una red nueva, una pregunta de ubicacion"
afirmar_igual "Callao|False" "$(valor sin_historial)" "y se guarda la nueva SIN la anterior"
afirmar_igual "True|Sin conexión:" "$(valor sin_conexion)" "sin conexion, lo guardado y diciendo de cuando es"

titulo "4. Privacidad: los modos sin preguntas"
afirmar_igual "-12.1|-77.0|Lima|0" "$(valor zona)" "«zona»: de la zona horaria, cero preguntas"
afirmar_igual "-12.1|-77.5|Mi casa|0" "$(valor fija)" "una fija: cero preguntas, y redondeada igual"
afirmar_igual "True" "$(valor apagado)" "«clima = no» apaga el tiempo"
afirmar_igual "0" "$(valor apagado_preguntas)" "y no pregunta nada"
afirmar_igual "Arequipa|-16.4|1" "$(valor por_nombre)" "por nombre de ciudad: una pregunta, y se recuerda"

titulo "5. Piezas del tiempo"
afirmar_igual "(-12.05, -77.05)" "$(valor zona_iso)" "las coordenadas de zone1970.tab"
afirmar_contiene "$RES" "^zona_iso_seg=.40\.714" "tambien con segundos"
afirmar_igual "Despejado|Lluvia ligera" "$(valor describir)" "los codigos del tiempo, en español"
afirmar_igual "12 18:00 False" "$(valor horas)" "doce horas desde la actual, sabiendo si es de noche"
afirmar_igual "un momento,10 min,2 h,2 días" "$(valor hace)" "el «hace cuanto»"

afirmar_intacta_la_casa_real
resumen
