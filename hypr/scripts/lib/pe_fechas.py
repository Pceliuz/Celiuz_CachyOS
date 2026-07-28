"""
~/dotfiles/hypr/scripts/lib/pe_fechas.py

Calendario peruano: feriados nacionales y fechas que se celebran aunque no den
descanso. Se calcula para cualquier ano, no es una tabla de un ano suelto.

Dos categorias:
  - FERIADO: descanso obligatorio por ley, sector publico y privado. Son 16.
  - CELEBRACION: se celebra pero se trabaja (Dia de la Madre, Halloween...).

Las fechas de Semana Santa y Carnaval se mueven cada ano porque cuelgan de la
Pascua, asi que se calculan desde ella en vez de escribirse a mano.

Fuente de los 16 feriados: calendario oficial peruano vigente en 2026, que
incluye los cuatro que se anadieron en anos recientes (7 de junio, 23 de julio,
6 de agosto y 9 de diciembre).
"""

import datetime as dt

FERIADO = "feriado"
CELEBRACION = "celebracion"


def pascua(ano):
    """Domingo de Pascua del ano dado (algoritmo de Meeus/Jones/Butcher)."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes, dia = divmod(h + l - 7 * m + 114, 31)
    return dt.date(ano, mes, dia + 1)


def _domingo_n(ano, mes, n):
    """El n-esimo domingo de un mes (n=1 es el primero)."""
    d = dt.date(ano, mes, 1)
    # weekday(): lunes=0 ... domingo=6
    primer_domingo = 1 + (6 - d.weekday()) % 7
    return dt.date(ano, mes, primer_domingo + 7 * (n - 1))


# Feriados de fecha fija. Son 14; con Jueves y Viernes Santo suman los 16.
_FIJOS = [
    ((1, 1),   "Ano Nuevo"),
    ((5, 1),   "Dia del Trabajo"),
    ((6, 7),   "Batalla de Arica y Dia de la Bandera"),
    ((6, 29),  "San Pedro y San Pablo"),
    ((7, 23),  "Dia de la Fuerza Aerea del Peru"),
    ((7, 28),  "Fiestas Patrias — Independencia del Peru"),
    ((7, 29),  "Fiestas Patrias — Gran Parada Militar"),
    ((8, 6),   "Batalla de Junin"),
    ((8, 30),  "Santa Rosa de Lima"),
    ((10, 8),  "Combate de Angamos"),
    ((11, 1),  "Dia de Todos los Santos"),
    ((12, 8),  "Inmaculada Concepcion"),
    ((12, 9),  "Batalla de Ayacucho"),
    ((12, 25), "Navidad"),
]

# Fechas que se celebran pero son dias laborables normales.
_CELEBRACIONES_FIJAS = [
    ((1, 6),   "Bajada de Reyes"),
    ((2, 14),  "Dia de San Valentin y de la Amistad"),
    ((3, 8),   "Dia Internacional de la Mujer"),
    ((4, 23),  "Dia del Idioma Espanol"),
    ((6, 24),  "Dia del Campesino e Inti Raymi"),
    ((7, 6),   "Dia del Maestro"),
    ((8, 22),  "Dia Mundial del Folklore"),
    ((9, 23),  "Dia de la Primavera y de la Juventud"),
    ((9, 24),  "Dia de las Fuerzas Armadas"),
    ((10, 18), "Senor de los Milagros"),
    ((10, 31), "Dia de la Cancion Criolla y Halloween"),
    ((11, 2),  "Dia de los Difuntos"),
    ((12, 24), "Nochebuena"),
    ((12, 31), "Fin de Ano"),
]

_cache = {}


def fechas_del_ano(ano):
    """{date: [(tipo, nombre), ...]} con todo lo del ano. Se cachea por ano."""
    if ano in _cache:
        return _cache[ano]

    res = {}

    def add(fecha, tipo, nombre):
        res.setdefault(fecha, []).append((tipo, nombre))

    for (mes, dia), nombre in _FIJOS:
        add(dt.date(ano, mes, dia), FERIADO, nombre)
    for (mes, dia), nombre in _CELEBRACIONES_FIJAS:
        add(dt.date(ano, mes, dia), CELEBRACION, nombre)

    p = pascua(ano)
    add(p - dt.timedelta(days=3), FERIADO, "Jueves Santo")
    add(p - dt.timedelta(days=2), FERIADO, "Viernes Santo")
    add(p - dt.timedelta(days=7), CELEBRACION, "Domingo de Ramos")
    add(p, CELEBRACION, "Domingo de Pascua")
    add(p - dt.timedelta(days=46), CELEBRACION, "Miercoles de Ceniza")
    add(p - dt.timedelta(days=48), CELEBRACION, "Carnaval")

    # Dia de la Madre: segundo domingo de mayo. Dia del Padre: tercero de junio.
    # Dia del Nino: tercer domingo de agosto.
    add(_domingo_n(ano, 5, 2), CELEBRACION, "Dia de la Madre")
    add(_domingo_n(ano, 6, 3), CELEBRACION, "Dia del Padre")
    add(_domingo_n(ano, 8, 3), CELEBRACION, "Dia del Nino")

    _cache[ano] = res
    return res


def del_dia(fecha):
    """Lista [(tipo, nombre), ...] de una fecha concreta. Vacia si no hay nada."""
    return fechas_del_ano(fecha.year).get(fecha, [])


def es_feriado(fecha):
    return any(t == FERIADO for t, _ in del_dia(fecha))


if __name__ == "__main__":
    # Comprobacion rapida: python3 pe_fechas.py [ano]
    import sys
    ano = int(sys.argv[1]) if len(sys.argv) > 1 else dt.date.today().year
    todo = fechas_del_ano(ano)
    feriados = sorted(f for f, v in todo.items() if any(t == FERIADO for t, _ in v))
    print(f"Pascua {ano}: {pascua(ano)}")
    print(f"Feriados nacionales: {len(feriados)}")
    for f in feriados:
        nombres = ", ".join(n for t, n in todo[f] if t == FERIADO)
        print(f"  {f:%d/%m %a}  {nombres}")
    print("\nCelebraciones (no feriado):")
    for f in sorted(todo):
        for t, n in todo[f]:
            if t == CELEBRACION:
                print(f"  {f:%d/%m %a}  {n}")
