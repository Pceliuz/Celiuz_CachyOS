#!/usr/bin/env python3
"""gen-colores.py — pasa la paleta de hyprlang a CSS de GTK.

POR QUE EXISTE. La paleta vive en hypr/conf/colores.conf como variables de
hyprlang. Hyprland y hyprlock las leen directamente (los dos hablan el mismo
idioma y hyprlock admite `source`), pero waybar se estiliza con CSS de GTK, que
no tiene forma de leer un .conf. Sin esto, el violeta estaria escrito a mano en
dos sitios y tarde o temprano dejarian de coincidir.

Genera waybar/colores.css con un `@define-color` por variable. style.css lo
carga con @import y no vuelve a escribir un color literal nunca.

Los alfas NO se generan: el CSS de GTK sabe derivarlos solo con
`alpha(@amatista, 0.35)`, asi que no hace falta una variable por transparencia.

Uso:
    gen-colores.py            genera waybar/colores.css
    gen-colores.py --check    no escribe; sale con 1 si el archivo esta viejo
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
ORIGEN = RAIZ / "hypr" / "conf" / "colores.conf"
DESTINO = RAIZ / "waybar" / "colores.css"
DESTINO_MAKO = RAIZ / "mako" / "colores"

# Que tono le toca a cada parte de una notificacion.
#
# Esta tabla existe porque mako, al contrario que el CSS, NO TIENE VARIABLES:
# no se le puede decir "el borde es $amatista", hay que escribirle el color ya
# resuelto. Asi que el reparto de papeles, que en waybar vive en style.css,
# aqui tiene que vivir en el generador. Es el unico sitio del proyecto donde
# una decision de diseno esta en codigo y no en un archivo de config.
#
# Formato: (seccion, [(clave, variable, alfa_o_None)])
#
# El alfa opcional pisa el de la paleta. Se usa para el fondo: $superficie es
# opaco, pero la notificacion tiene que dejar entrever lo que hay detras, igual
# que las pastillas de la barra. El desenfoque que lo hace legible lo pone
# Hyprland con un `layerrule = blur` sobre la capa de mako (windowrules.conf).
MAKO = [
    (None, [                              # globales: la notificacion normal
        ("background-color", "superficie", 0.92),
        ("text-color",       "luz",        None),
        ("border-color",     "amatista",   None),
        ("progress-color",   "violeta",    0.45),
    ]),
    ("urgency=low", [                     # lo que solo informa: se apaga
        ("border-color", "apagado", None),
        ("text-color",   "tenue",   None),
    ]),
    ("urgency=critical", [                # lo unico que puede salirse del violeta
        ("border-color", "alerta", None),
        ("text-color",   "alerta", None),
    ]),
]

# $nombre = rgba(RRGGBBAA)   [# comentario opcional al lado]
# El comentario final es opcional PERO tiene que estar contemplado: sin el
# `(?:#.*)?` las dos variables que lo llevan ($alerta y $atencion) no casaban y
# desaparecian del CSS sin decir nada.
PATRON = re.compile(r"^\s*\$(\w+)\s*=\s*rgba\(([0-9a-fA-F]{8})\)\s*(?:#.*)?$")


def leer_paleta(ruta: Path) -> list[tuple[str, str, str, str]]:
    """Devuelve [(nombre, css, hexadecimal_crudo, nota)].

    El crudo se guarda ademas del css porque mako quiere el color en
    #RRGGBBAA y el CSS de GTK en rgba(r,g,b,a): son el mismo dato en dos
    formatos, y reconvertir de uno a otro seria dar una vuelta de mas.
    """
    salida = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        m = PATRON.match(linea)
        if not m:
            continue
        nombre, hexa = m.group(1), m.group(2).lower()

        # OJO CON EL ORDEN, que tiene trampa. En el ARCHIVO de config el orden
        # es RRGGBBAA (el alfa al final), pero `hyprctl getoption` los DEVUELVE
        # como AARRGGBB (el alfa delante). Son dos ordenes distintos para el
        # mismo color. Aqui se lee del archivo, asi que es RRGGBBAA.
        #
        # Leerlo al reves no rompe nada de forma visible: da colores parecidos
        # con el alfa cambiado, que es el tipo de fallo que se tarda una tarde
        # en ver. Ya paso una vez escribiendo este script.
        r, g, b, a = (int(hexa[j:j + 2], 16) for j in (0, 2, 4, 6))
        css = f"#{r:02x}{g:02x}{b:02x}" if a == 255 else \
              f"rgba({r}, {g}, {b}, {a / 255:.3f}".rstrip("0").rstrip(".") + ")"

        # Solo se copia el comentario que va en la MISMA linea, detras del
        # valor. Los parrafos de encima explican el papel de cada tono en
        # prosa: recortarlos automaticamente daba frases cortadas sin sentido.
        # Quien quiera el porque, va a colores.conf, que para eso es la fuente.
        trozos = linea.split("#", 1)
        nota = trozos[1].strip() if len(trozos) > 1 else ""
        salida.append((nombre, css, hexa, nota))
    return salida


def render(paleta) -> str:
    ancho = max(len(n) for n, _, _, _ in paleta)
    filas = []
    for nombre, css, _, nota in paleta:
        fila = f"@define-color {nombre:<{ancho}} {css};"
        if nota:
            fila = f"{fila:<46}/* {nota[:70]} */"
        filas.append(fila)
    return (
        "/* GENERADO POR hypr/scripts/gen-colores.py — NO EDITAR A MANO.\n"
        " *\n"
        " * La fuente de verdad es hypr/conf/colores.conf. Si cambias un color\n"
        " * ahi y no vuelves a lanzar el generador, la barra se queda con el\n"
        " * viejo. Lo mas comodo: gen-colores.py y luego recargar las barras.\n"
        " *\n"
        " * Para transparencias no hagas variables nuevas: el CSS de GTK las\n"
        " * deriva solo, con alpha(@amatista, 0.35).\n"
        " */\n\n" + "\n".join(filas) + "\n"
    )


def render_mako(paleta) -> str:
    """Config de color de mako. Se incluye desde mako/config con `include=`.

    OJO CON EL ORDEN, que en mako no es libre: las opciones globales tienen que
    ir ANTES de la primera seccion `[criterio]`. Como este archivo trae las dos
    cosas, el `include=` va AL FINAL de mako/config. Si se pusiera antes, todo
    lo que viniera detras en config se leeria como parte de la ultima seccion
    de aqui, en vez de como opciones globales — y sin dar ningun error.
    """
    # mako acepta #RRGGBB y #RRGGBBAA, que es el mismo orden que usa hyprlang
    # en los archivos: basta con cambiar rgba( ) por #. El unico cuidado es el
    # alfa, y por eso se guarda el hexadecimal crudo y no el css ya convertido.
    crudo = {n: h for n, _, h, _ in paleta}

    filas = [
        "# GENERADO POR hypr/scripts/gen-colores.py — NO EDITAR A MANO.",
        "#",
        "# Los colores de las notificaciones, sacados de hypr/conf/colores.conf,",
        "# que es la misma fuente que usan Hyprland, hyprlock y la barra.",
        "#",
        "# mako NO tiene variables, asi que el reparto de papeles (que tono va en",
        "# el borde, cual en el texto) esta en la tabla MAKO del generador.",
        "#",
        "# Este archivo se incluye AL FINAL de mako/config, porque trae secciones",
        "# y en mako las opciones globales tienen que ir antes de la primera.",
        "",
    ]
    for seccion, pares in MAKO:
        if seccion:
            filas.append("")
            filas.append(f"[{seccion}]")
        for clave, var, alfa in pares:
            hexa = crudo[var]
            if alfa is not None:
                hexa = hexa[:6] + f"{round(alfa * 255):02x}"
            valor = f"#{hexa}"
            # progress-color necesita decir COMO se mezcla con el fondo.
            if clave == "progress-color":
                valor = f"over {valor}"
            filas.append(f"{clave}={valor}")
    return "\n".join(filas) + "\n"


def main() -> int:
    if not ORIGEN.exists():
        print(f"no encuentro la paleta: {ORIGEN}", file=sys.stderr)
        return 1

    paleta = leer_paleta(ORIGEN)
    if not paleta:
        print(f"{ORIGEN} no tiene ninguna variable de color", file=sys.stderr)
        return 1

    salidas = [(DESTINO, render(paleta)), (DESTINO_MAKO, render_mako(paleta))]

    if "--check" in sys.argv:
        viejos = [d for d, nuevo in salidas
                  if (d.read_text(encoding="utf-8") if d.exists() else "") != nuevo]
        if viejos:
            for d in viejos:
                print(f"{d.relative_to(RAIZ)} esta desactualizado respecto a "
                      f"colores.conf", file=sys.stderr)
            return 1
        print(f"al dia ({len(paleta)} colores en {len(salidas)} destinos)")
        return 0

    for destino, nuevo in salidas:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(nuevo, encoding="utf-8")
        print(f"{destino.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
