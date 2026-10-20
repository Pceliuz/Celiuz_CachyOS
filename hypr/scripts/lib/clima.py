#!/usr/bin/env python3
"""
hypr/scripts/lib/clima.py — el tiempo del panel del reloj, y donde estas, con la
menor cantidad posible de preguntas a nadie.

EL TIEMPO
---------
De Open-Meteo (open-meteo.com): gratis, sin cuenta y sin clave. Se pide SOLO
cuando se abre el panel del reloj, y como mucho una vez cada 15 minutos (lo de
en medio sale de la cache). No hay ningun demonio preguntando en segundo plano.

DONDE ESTAS: LAS REGLAS
-----------------------
Lo pidio el usuario y es una decision de diseño, no un detalle:

  1. Se pregunta UNA VEZ POR RED. Al cambiar de red (otro wifi, el cable de la
     oficina) se pide la ciudad aproximada por la IP a ipinfo.io, por HTTPS; en
     la misma red no se vuelve a preguntar (salvo que pasen 30 dias).
  2. Solo la CIUDAD: las coordenadas se redondean a una decima de grado
     (~10 km) antes de guardarlas y antes de mandarselas a Open-Meteo.
  3. SIN HISTORIAL: se guarda la ultima ubicacion y nada mas, en un fichero que
     solo puede leer tu usuario (0600). De la red se guarda un resumen (sha256)
     de su identificador, no su nombre.
  4. Se puede no preguntar nunca: `ubicacion = zona` la saca de la zona horaria
     del sistema (la tabla zone1970.tab trae las coordenadas de cada zona), o
     una fija.

LOS AJUSTES (~/.config/celiuz/clima.conf, no se versiona)
---------------------------------------------------------
    ubicacion = auto          lo de arriba (de fabrica)
    ubicacion = zona          de la zona horaria: cero preguntas
    ubicacion = -12.05,-77.04 Lima   fija (lo de despues de las coordenadas es
                                     el nombre que se enseña)
    clima = no                ni tiempo ni preguntas: el panel solo enseña la
                              hora, el calendario, la luna y el zodiaco
    signo = acuario           el tuyo, para el contador del zodiaco (opcional)

USO
---
    clima.py --ver            lo que hay, sin preguntar a nadie (solo la cache)
    clima.py --actualizar     pregunta si toca, y lo enseña
"""

import datetime as dt
import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request

FRESCO = 15 * 60            # el tiempo vale 15 minutos
UBICACION_VALE = 30 * 86400  # en la misma red, la ciudad vale 30 dias
PLAZO_RED = 8
HORAS = 12                  # las que giran alrededor del reloj

URL_IP = "https://ipinfo.io/json"
URL_TIEMPO = "https://api.open-meteo.com/v1/forecast"
URL_LUGAR = "https://geocoding-api.open-meteo.com/v1/search"

# Codigos WMO de Open-Meteo -> (texto, glifo de dia, glifo de noche).
NUBE, SOL, LUNA_G, CLARO_D, CLARO_N = "\U000F0590", "\U000F0599", "\U000F0594", "\U000F0595", "\U000F0F31"
NIEBLA, LLOVIZNA, LLUVIA, FUERTE, NIEVE, TORMENTA = (
    "\U000F0591", "\U000F0597", "\U000F0597", "\U000F0596", "\U000F0598", "\U000F0593")
CODIGOS = {
    0: ("Despejado", SOL, LUNA_G),
    1: ("Casi despejado", CLARO_D, CLARO_N),
    2: ("Parcialmente nublado", CLARO_D, CLARO_N),
    3: ("Nublado", NUBE, NUBE),
    45: ("Niebla", NIEBLA, NIEBLA), 48: ("Niebla", NIEBLA, NIEBLA),
    51: ("Llovizna", LLOVIZNA, LLOVIZNA), 53: ("Llovizna", LLOVIZNA, LLOVIZNA),
    55: ("Llovizna", LLOVIZNA, LLOVIZNA), 56: ("Llovizna helada", LLOVIZNA, LLOVIZNA),
    57: ("Llovizna helada", LLOVIZNA, LLOVIZNA),
    61: ("Lluvia ligera", LLUVIA, LLUVIA), 63: ("Lluvia", LLUVIA, LLUVIA),
    65: ("Lluvia fuerte", FUERTE, FUERTE), 66: ("Lluvia helada", LLUVIA, LLUVIA),
    67: ("Lluvia helada", FUERTE, FUERTE),
    71: ("Nieve", NIEVE, NIEVE), 73: ("Nieve", NIEVE, NIEVE), 75: ("Nieve", NIEVE, NIEVE),
    77: ("Nieve", NIEVE, NIEVE),
    80: ("Chubascos", LLUVIA, LLUVIA), 81: ("Chubascos", LLUVIA, LLUVIA),
    82: ("Chubascos fuertes", FUERTE, FUERTE),
    85: ("Chubascos de nieve", NIEVE, NIEVE), 86: ("Chubascos de nieve", NIEVE, NIEVE),
    95: ("Tormenta", TORMENTA, TORMENTA), 96: ("Tormenta", TORMENTA, TORMENTA),
    99: ("Tormenta", TORMENTA, TORMENTA),
}


def describir(codigo, es_dia=True):
    texto, dia, noche = CODIGOS.get(int(codigo or 0), ("—", NUBE, NUBE))
    return texto, (dia if es_dia else noche)


# ─────────────────────────────────────────────────────────────────────────────
# Ficheros
# ─────────────────────────────────────────────────────────────────────────────

def _dir(var, defecto):
    return os.path.join(os.environ.get(var) or os.path.expanduser(defecto), "celiuz")


def fichero_ajustes():
    return os.path.join(_dir("XDG_CONFIG_HOME", "~/.config"), "clima.conf")


def fichero_ubicacion():
    return os.path.join(_dir("XDG_CACHE_HOME", "~/.cache"), "ubicacion.json")


def fichero_tiempo():
    return os.path.join(_dir("XDG_CACHE_HOME", "~/.cache"), "clima.json")


def _leer(ruta):
    try:
        with open(ruta, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _escribir(ruta, datos):
    """Solo para tu usuario (0600), y con un temporal: un corte a medias no
    deja un fichero roto."""
    os.makedirs(os.path.dirname(ruta), mode=0o700, exist_ok=True)
    temporal = ruta + ".tmp"
    fd = os.open(temporal, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)
    os.chmod(temporal, 0o600)
    os.replace(temporal, ruta)


def ajustes():
    a = {"ubicacion": "auto", "clima": True, "signo": ""}
    try:
        with open(fichero_ajustes(), encoding="utf-8") as f:
            texto = f.read()
    except OSError:
        return a
    for linea in texto.splitlines():
        linea = linea.split("#", 1)[0].strip()
        if "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        clave, valor = clave.strip().lower(), valor.strip()
        if clave == "ubicacion":
            a["ubicacion"] = valor or "auto"
        elif clave == "clima":
            a["clima"] = valor.lower() not in ("no", "false", "0", "off")
        elif clave == "signo":
            a["signo"] = valor
    return a


# ─────────────────────────────────────────────────────────────────────────────
# Donde estas
# ─────────────────────────────────────────────────────────────────────────────

def redondear(lat, lon):
    """A una decima de grado: ~10 km. La ciudad, no tu calle."""
    return round(float(lat), 1), round(float(lon), 1)


def pedir(url, plazo=PLAZO_RED):
    """GET de un JSON por HTTPS. Las pruebas lo sustituyen: es la UNICA puerta
    de este modulo a internet."""
    req = urllib.request.Request(url, headers={"User-Agent": "celiuz-reloj/1",
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=plazo) as r:
        return json.loads(r.read().decode())


def red_actual():
    """Un resumen (sha256) de la red en uso, o "" sin red. Del identificador de
    la conexion de NetworkManager, no del nombre: en el fichero no queda «Wifi
    de la oficina»."""
    try:
        r = subprocess.run(["nmcli", "-t", "-f", "UUID,TYPE", "connection", "show", "--active"],
                           capture_output=True, text=True, timeout=5,
                           env=dict(os.environ, LC_ALL="C"))
    except (OSError, subprocess.TimeoutExpired):
        return ""
    for linea in r.stdout.splitlines():
        uuid, _, tipo = linea.partition(":")
        if tipo in ("802-11-wireless", "802-3-ethernet") and uuid:
            return hashlib.sha256(uuid.encode()).hexdigest()[:16]
    return ""


def zona_horaria():
    """El nombre de la zona del sistema (America/Lima), o ""."""
    tz = os.environ.get("TZ", "").lstrip(":")
    if tz:
        return tz
    try:
        destino = os.path.realpath("/etc/localtime")
    except OSError:
        return ""
    marca = "/zoneinfo/"
    return destino.split(marca, 1)[1] if marca in destino else ""


def _iso6709(texto):
    """«-1203-07703» (o con segundos) -> (-12.05, -77.05)."""
    import re
    m = re.match(r"([+-])(\d{2})(\d{2})(\d{2})?([+-])(\d{3})(\d{2})(\d{2})?$", texto)
    if not m:
        return None
    s1, d1, m1, x1, s2, d2, m2, x2 = m.groups()
    lat = int(d1) + int(m1) / 60 + int(x1 or 0) / 3600
    lon = int(d2) + int(m2) / 60 + int(x2 or 0) / 3600
    return (-lat if s1 == "-" else lat), (-lon if s2 == "-" else lon)


def por_zona(tabla="/usr/share/zoneinfo/zone1970.tab"):
    """La ubicacion de la ciudad de la zona horaria, sin preguntar a nadie."""
    zona = zona_horaria()
    if not zona:
        return None
    try:
        with open(tabla, encoding="utf-8") as f:
            for linea in f:
                if linea.startswith("#"):
                    continue
                campos = linea.rstrip("\n").split("\t")
                if len(campos) >= 3 and campos[2] == zona:
                    coords = _iso6709(campos[1])
                    if coords:
                        lat, lon = redondear(*coords)
                        return {"lat": lat, "lon": lon, "fuente": "zona",
                                "ciudad": zona.rsplit("/", 1)[-1].replace("_", " ")}
    except OSError:
        pass
    return None


def ubicacion(aj=None, red=None, ahora=None):
    """{lat, lon, ciudad, fuente} o None. Ver las reglas de la cabecera."""
    aj = aj or ajustes()
    ahora = time.time() if ahora is None else ahora
    modo = aj["ubicacion"].strip()
    if modo.lower() == "zona":
        return por_zona()
    if modo.lower() != "auto":
        return _fija(modo)

    red = red_actual() if red is None else red
    guardada = _leer(fichero_ubicacion())
    if (guardada.get("red") == red and red and
            ahora - guardada.get("cuando", 0) < UBICACION_VALE and "lat" in guardada):
        return {k: guardada[k] for k in ("lat", "lon", "ciudad")} | {"fuente": "ip"}
    if not red and "lat" in guardada:
        # Sin red no hay a quien preguntar (ni tiempo que pedir): la ultima.
        return {k: guardada[k] for k in ("lat", "lon", "ciudad")} | {"fuente": "ip"}
    try:
        d = pedir(URL_IP)
        lat, lon = redondear(*str(d["loc"]).split(","))
        nueva = {"red": red, "cuando": ahora, "lat": lat, "lon": lon,
                 "ciudad": str(d.get("city") or "")}
        _escribir(fichero_ubicacion(), nueva)   # pisa la anterior: sin historial
        return {"lat": lat, "lon": lon, "ciudad": nueva["ciudad"], "fuente": "ip"}
    except (OSError, ValueError, KeyError, urllib.error.URLError):
        if "lat" in guardada:
            return {k: guardada[k] for k in ("lat", "lon", "ciudad")} | {"fuente": "ip"}
        return por_zona()


def _fija(texto):
    """«-12.05,-77.04 Lima» o «Arequipa» (por nombre: una sola pregunta al
    buscador de Open-Meteo, y se recuerda)."""
    partes = texto.split(None, 1)
    try:
        lat, lon = redondear(*partes[0].split(","))
        return {"lat": lat, "lon": lon, "ciudad": partes[1] if len(partes) > 1 else "",
                "fuente": "fija"}
    except (ValueError, TypeError, IndexError):
        pass
    guardada = _leer(fichero_ubicacion())
    if guardada.get("nombre_pedido") == texto and "lat" in guardada:
        return {k: guardada[k] for k in ("lat", "lon", "ciudad")} | {"fuente": "fija"}
    try:
        d = pedir(URL_LUGAR + "?count=1&language=es&name=" + urllib.request.quote(texto))
        r = d["results"][0]
        lat, lon = redondear(r["latitude"], r["longitude"])
        _escribir(fichero_ubicacion(), {"nombre_pedido": texto, "lat": lat, "lon": lon,
                                        "ciudad": r.get("name") or texto})
        return {"lat": lat, "lon": lon, "ciudad": r.get("name") or texto, "fuente": "fija"}
    except (OSError, ValueError, KeyError, IndexError, urllib.error.URLError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# El tiempo
# ─────────────────────────────────────────────────────────────────────────────

def url_tiempo(lat, lon):
    return (URL_TIEMPO + "?latitude=%.1f&longitude=%.1f" % (lat, lon) +
            "&current=temperature_2m,apparent_temperature,relative_humidity_2m,"
            "wind_speed_10m,weather_code,precipitation_probability,is_day"
            "&hourly=temperature_2m,weather_code,precipitation_probability,is_day"
            "&daily=sunrise,sunset&timezone=auto&forecast_days=2&wind_speed_unit=ms")


def interpretar(d, ahora=None):
    """La respuesta de Open-Meteo -> lo que usa el panel."""
    c = d["current"]
    h = d["hourly"]
    actual = c["time"][:13] + ":00"
    i = h["time"].index(actual) if actual in h["time"] else 0
    horas = []
    for k in range(i, min(i + HORAS, len(h["time"]))):
        horas.append({"hora": h["time"][k][11:16], "temp": h["temperature_2m"][k],
                      "codigo": h["weather_code"][k],
                      "lluvia": (h.get("precipitation_probability") or [0] * len(h["time"]))[k],
                      "dia": bool((h.get("is_day") or [1] * len(h["time"]))[k])})
    texto, glifo = describir(c.get("weather_code"), bool(c.get("is_day", 1)))
    return {
        "temp": c.get("temperature_2m"), "sensacion": c.get("apparent_temperature"),
        "humedad": c.get("relative_humidity_2m"), "viento": c.get("wind_speed_10m"),
        "lluvia": c.get("precipitation_probability") or 0, "codigo": c.get("weather_code"),
        "dia": bool(c.get("is_day", 1)), "texto": texto, "glifo": glifo,
        "salida": d["daily"]["sunrise"][0][11:16], "puesta": d["daily"]["sunset"][0][11:16],
        "horas": horas,
    }


def obtener(forzar=False, ahora=None):
    """{ciudad, fuente, edad, tiempo, error}. Pregunta solo si hace falta (ver
    la cabecera). Pensado para correr en un hilo: puede tardar segundos."""
    ahora = time.time() if ahora is None else ahora
    aj = ajustes()
    if not aj["clima"]:
        return {"apagado": True}
    lugar = ubicacion(aj, ahora=ahora)
    cache = _leer(fichero_tiempo())
    mismo_sitio = lugar and cache.get("lat") == lugar["lat"] and cache.get("lon") == lugar["lon"]
    if mismo_sitio and not forzar and ahora - cache.get("cuando", 0) < FRESCO:
        return _respuesta(cache, lugar, ahora)
    if lugar is None:
        return {"error": "No sé dónde estás. Pon «ubicacion = zona» en "
                         "~/.config/celiuz/clima.conf para no tener que preguntar."}
    try:
        crudo = pedir(url_tiempo(lugar["lat"], lugar["lon"]))
        datos = interpretar(crudo)
    except (OSError, ValueError, KeyError, IndexError, urllib.error.URLError) as e:
        if mismo_sitio and "tiempo" in cache:
            r = _respuesta(cache, lugar, ahora)
            r["error"] = "Sin conexión: datos de hace %s." % hace(ahora - cache["cuando"])
            return r
        return {"error": "No pude pedir el tiempo (%s)." % type(e).__name__,
                "ciudad": lugar.get("ciudad", "")}
    nueva = {"cuando": ahora, "lat": lugar["lat"], "lon": lugar["lon"], "tiempo": datos}
    _escribir(fichero_tiempo(), nueva)
    return _respuesta(nueva, lugar, ahora)


def _respuesta(cache, lugar, ahora):
    return {"ciudad": (lugar or {}).get("ciudad", ""), "fuente": (lugar or {}).get("fuente", ""),
            "edad": ahora - cache.get("cuando", ahora), "tiempo": cache.get("tiempo")}


def hace(segundos):
    if segundos < 90:
        return "un momento"
    if segundos < 3600:
        return "%d min" % (segundos // 60)
    if segundos < 86400:
        return "%d h" % (segundos // 3600)
    return "%d días" % (segundos // 86400)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--ver"]:
        c = _leer(fichero_tiempo())
        u = _leer(fichero_ubicacion())
        print("Ubicación guardada: %s (%s, %s)" % (u.get("ciudad", "ninguna"), u.get("lat"), u.get("lon")))
        if c.get("tiempo"):
            t = c["tiempo"]
            print("Tiempo de hace %s: %s°C, %s, humedad %s%%, viento %s m/s" % (
                hace(time.time() - c["cuando"]), t["temp"], t["texto"], t["humedad"], t["viento"]))
        sys.exit(0)
    if sys.argv[1:] == ["--actualizar"]:
        print(json.dumps(obtener(), ensure_ascii=False, indent=1, default=str)[:1500])
        sys.exit(0)
    print(__doc__.split("USO\n---\n", 1)[-1].rstrip(), file=sys.stderr)
    sys.exit(2)
