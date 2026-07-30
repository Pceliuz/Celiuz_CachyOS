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

# $nombre = rgba(RRGGBBAA)   [# comentario opcional al lado]
# El comentario final es opcional PERO tiene que estar contemplado: sin el
# `(?:#.*)?` las dos variables que lo llevan ($alerta y $atencion) no casaban y
# desaparecian del CSS sin decir nada.
PATRON = re.compile(r"^\s*\$(\w+)\s*=\s*rgba\(([0-9a-fA-F]{8})\)\s*(?:#.*)?$")


def leer_paleta(ruta: Path) -> list[tuple[str, str, str]]:
    """Devuelve [(nombre, css, nota)]."""
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
        salida.append((nombre, css, nota))
    return salida


def render(paleta) -> str:
    ancho = max(len(n) for n, _, _ in paleta)
    filas = []
    for nombre, css, nota in paleta:
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


def main() -> int:
    if not ORIGEN.exists():
        print(f"no encuentro la paleta: {ORIGEN}", file=sys.stderr)
        return 1

    paleta = leer_paleta(ORIGEN)
    if not paleta:
        print(f"{ORIGEN} no tiene ninguna variable de color", file=sys.stderr)
        return 1

    nuevo = render(paleta)

    if "--check" in sys.argv:
        actual = DESTINO.read_text(encoding="utf-8") if DESTINO.exists() else ""
        if actual != nuevo:
            print(f"{DESTINO.name} esta desactualizado respecto a colores.conf",
                  file=sys.stderr)
            return 1
        print(f"{DESTINO.name} al dia ({len(paleta)} colores)")
        return 0

    DESTINO.write_text(nuevo, encoding="utf-8")
    print(f"{DESTINO.relative_to(RAIZ)}: {len(paleta)} colores")
    return 0


if __name__ == "__main__":
    sys.exit(main())
