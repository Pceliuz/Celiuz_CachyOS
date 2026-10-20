#!/usr/bin/env python3
"""
hypr/scripts/lib/cielo.py — la fase de la luna y el signo del zodiaco de una
fecha. Sin red y sin dependencias: es aritmetica.

LA LUNA
-------
Se cuenta desde una luna nueva conocida (6 de enero de 2000, 18:14 UTC) con el
mes sinodico medio (29,530588853 dias). Es la aproximacion de siempre: falla en
unas horas, no en dias, que para ensenar la fase sobra. La iluminada es la
fraccion del disco con luz, (1 - cos(angulo)) / 2.

EL ZODIACO
----------
El tropical, el de los horoscopos: cada signo empieza y acaba en una fecha fija
del calendario. Las fechas de corte varian un dia segun la fuente; aqui van las
mas comunes. Es un extra por diversion, y la frase de cada signo tambien.
"""

import datetime as dt
import math

MES_SINODICO = 29.530588853
NUEVA_REF = dt.datetime(2000, 1, 6, 18, 14, tzinfo=dt.timezone.utc)

FASES = [
    "Luna nueva", "Creciente", "Cuarto creciente", "Creciente gibosa",
    "Luna llena", "Menguante gibosa", "Cuarto menguante", "Menguante",
]
# La fraccion iluminada y el lado de cada una de las 8, para dibujarlas en fila.
FASES_DIBUJO = [(0.0, True), (0.25, True), (0.5, True), (0.75, True),
                (1.0, True), (0.75, False), (0.5, False), (0.25, False)]


def _utc(momento):
    if momento.tzinfo is None:
        momento = momento.astimezone()
    return momento.astimezone(dt.timezone.utc)


def luna(momento=None):
    """{edad (dias), iluminada (0..1), creciente, fase (0..7), nombre,
    proxima_llena, proxima_nueva} para ese momento (por defecto, ahora)."""
    momento = _utc(momento or dt.datetime.now(dt.timezone.utc))
    edad = ((momento - NUEVA_REF).total_seconds() / 86400) % MES_SINODICO
    angulo = 2 * math.pi * edad / MES_SINODICO
    iluminada = (1 - math.cos(angulo)) / 2
    # El nombre va por lo ILUMINADO, no por los dias: los cuartos son el
    # instante del 50%, y una luna al 63% es ya gibosa (por dias, en ocho
    # tramos iguales, salia «cuarto creciente»).
    creciente = edad < MES_SINODICO / 2
    if iluminada < 0.03:
        fase = 0
    elif iluminada > 0.97:
        fase = 4
    elif abs(iluminada - 0.5) <= 0.04:
        fase = 2 if creciente else 6
    elif iluminada < 0.5:
        fase = 1 if creciente else 7
    else:
        fase = 3 if creciente else 5
    hasta_llena = (MES_SINODICO / 2 - edad) % MES_SINODICO
    hasta_nueva = (MES_SINODICO - edad) % MES_SINODICO
    return {
        "edad": edad,
        "iluminada": iluminada,
        "creciente": creciente,
        "fase": fase,
        "nombre": FASES[fase],
        "proxima_llena": momento + dt.timedelta(days=hasta_llena),
        "proxima_nueva": momento + dt.timedelta(days=hasta_nueva),
    }


# (nombre, clave, glifo Nerd Font, (mes, dia) de inicio, frase)
SIGNOS = [
    ("Capricornio", "capricornio", "\U000F0A80", (12, 22), "Paso a paso"),
    ("Acuario", "acuario", "\U000F0A7D", (1, 20), "Piensa distinto"),
    ("Piscis", "piscis", "\U000F0A84", (2, 19), "Escucha tu intuición"),
    ("Aries", "aries", "\U000F0A7E", (3, 21), "Empieza algo nuevo"),
    ("Tauro", "tauro", "\U000F0A87", (4, 20), "Ve a tu ritmo"),
    ("Géminis", "geminis", "\U000F0A81", (5, 21), "Cuenta lo que piensas"),
    ("Cáncer", "cancer", "\U000F0A7F", (6, 21), "Cuida a los tuyos"),
    ("Leo", "leo", "\U000F0A82", (7, 23), "Que se te vea"),
    ("Virgo", "virgo", "\U000F0A88", (8, 23), "Ordena una cosa"),
    ("Libra", "libra", "\U000F0A83", (9, 23), "Busca el equilibrio"),
    ("Escorpio", "escorpio", "\U000F0A86", (10, 23), "Ve al fondo"),
    ("Sagitario", "sagitario", "\U000F0A85", (11, 22), "Sal a explorar"),
]


def _inicio(signo, ano):
    mes, dia = signo[3]
    return dt.date(ano, mes, dia)


def zodiaco(fecha=None):
    """{nombre, clave, glifo, desde, hasta, frase} del signo de esa fecha."""
    fecha = fecha or dt.date.today()
    # El ultimo signo cuyo inicio (de este año o del anterior) no pasa de hoy.
    candidatos = []
    for i, s in enumerate(SIGNOS):
        for ano in (fecha.year - 1, fecha.year):
            inicio = _inicio(s, ano)
            if inicio <= fecha:
                candidatos.append((inicio, i))
    inicio, i = max(candidatos)
    s = SIGNOS[i]
    siguiente = SIGNOS[(i + 1) % len(SIGNOS)]
    fin = _inicio(siguiente, inicio.year if _inicio(siguiente, inicio.year) > inicio
                  else inicio.year + 1) - dt.timedelta(days=1)
    return {"nombre": s[0], "clave": s[1], "glifo": s[2], "desde": inicio,
            "hasta": fin, "frase": s[4]}


def buscar_signo(texto):
    """El signo por su nombre, sin tildes ni mayusculas; None si no es uno."""
    import unicodedata
    limpio = "".join(c for c in unicodedata.normalize("NFD", (texto or "").strip().lower())
                     if unicodedata.category(c) != "Mn")
    for s in SIGNOS:
        if s[1] == limpio:
            return s
    return None


def dias_para(clave, fecha=None):
    """Dias que faltan para que empiece ese signo (0 si es el de hoy)."""
    fecha = fecha or dt.date.today()
    s = buscar_signo(clave)
    if s is None:
        return None
    if zodiaco(fecha)["clave"] == s[1]:
        return 0
    inicio = _inicio(s, fecha.year)
    if inicio <= fecha:
        inicio = _inicio(s, fecha.year + 1)
    return (inicio - fecha).days


if __name__ == "__main__":
    l = luna()
    z = zodiaco()
    print("Luna: %s, %d%% iluminada (llena el %s)" % (
        l["nombre"], round(l["iluminada"] * 100), l["proxima_llena"].astimezone().strftime("%d/%m")))
    print("Zodiaco: %s (%s - %s) · %s" % (z["nombre"], z["desde"].strftime("%d/%m"),
                                          z["hasta"].strftime("%d/%m"), z["frase"]))
