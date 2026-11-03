#!/usr/bin/env python3
"""
~/dotfiles/hypr/scripts/gen-kvantum.py — el tema de Kvantum «Celiuz» para las
apps Qt/KDE (Dolphin y compania): fondo translucido con la paleta del repo.

    gen-kvantum.py                      escribe ~/.config/Kvantum/Celiuz/
    gen-kvantum.py --check              1 si el escrito no es el que saldria
    gen-kvantum.py --base DIR --destino DIR    (las pruebas)

POR QUE UN GENERADOR Y NO UN TEMA EN EL REPO
--------------------------------------------
El tema se hizo a mano el 2026-11-02 sobre KvGnomeDark, mirando Dolphin en
vivo. Copiarlo al repo seria versionar ~300 KB de SVG ajeno con la paleta
del autor escrita dentro: otra copia de colores.conf, de las que se separan
solas (ver tests/unidad/paleta-bloqueo.sh). Aqui solo esta la RECETA: se
parte del KvGnomeDark que trae el paquete `kvantum` y se le cambia lo
mismo que se cambio a mano, con los colores sacados de colores.conf.

Lo que se le cambia, y por que:
  - translucent_windows + reduce_window_opacity: el fondo de las ventanas
    deja ver el wallpaper. transparent_dolphin_view: la vista de archivos de
    Dolphin tambien (Kvantum la pinta aparte).
  - la barra de herramientas (elemento `menubar` del SVG) era un degradado
    gris: pasa a $apagado translucido con una linea $amatista abajo.
  - el azul de acento del tema (#15539e, la seleccion) pasa a $violeta, y el
    azul claro de algunos textos con foco (#3a90eb) a $neon.
  - el boton con el raton encima (`button-focused`, que usan tambien los de la
    barra) era gris: $violeta translucido con borde $amatista, como los
    botones de gtk/celiuz-transparente.css.
  - el campo de texto (la busqueda de Dolphin), la barrita del scroll y la
    cabecera de columnas eran grises (la cabecera, como la barra de arriba): el campo como los de GTK ($abismo con borde $amatista, $neon al
    escribir) y la barrita en $amatista, mas viva con el raton y al arrastrar.

El desenfoque de Hyprland detras se quita en lua/windowrules.lua (no_blur):
con el blur el fondo salia lechoso.

Lo escrito vive FUERA del repo (es de cada equipo, como lock-medidas.conf) y
lo rehace instalar.sh. Sin el paquete kvantum no hay base y no hace nada.
"""

import argparse
import importlib.util
import os
import re
import sys
from pathlib import Path

AQUI = Path(os.path.realpath(__file__)).parent
RAIZ = AQUI.parent.parent
PALETA = RAIZ / "hypr" / "conf" / "colores.conf"

BASE = Path("/usr/share/Kvantum/KvGnomeDark")
NOMBRE = "Celiuz"

# Los tonos de la paleta que usa el tema. Si colores.conf pierde alguno, se
# para con un error en vez de dejar un color a medias.
NECESARIOS = ("negro", "abismo", "superficie", "apagado", "violeta",
              "amatista", "neon", "luz", "tenue")

# Cuanto se ve el fondo. Medido a ojo con Dolphin al lado del Control de
# volumen (GTK4), que fue la referencia que eligio el usuario.
OPACIDAD_VENTANA = 45   # reduce_window_opacity: % que se QUITA a la ventana
OPACIDAD_MENU = 6       # los menus casi opacos: transparentes no se leen


def cargar_paleta(ruta=PALETA):
    """{nombre: '#rrggbb'} desde colores.conf, con el lector de gen-colores."""
    spec = importlib.util.spec_from_file_location("gen_colores", AQUI / "gen-colores.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {nombre: "#" + crudo[:6] for nombre, _, crudo, _ in mod.leer_paleta(ruta)}


def poner_claves(texto, claves):
    """Cambia `clave=valor` en un .kvconfig; la que no este, no se inventa."""
    for clave, valor in claves.items():
        texto = re.sub(r"(?m)^%s=.*$" % re.escape(clave), f"{clave}={valor}", texto)
    return texto


def render_kvconfig(base, p):
    t = poner_claves(base, {
        "translucent_windows": "true",
        "reduce_window_opacity": OPACIDAD_VENTANA,
        "reduce_menu_opacity": OPACIDAD_MENU,
        "window.color": p["abismo"],
        "base.color": p["abismo"],
        "alt.base.color": p["superficie"],
        "button.color": p["superficie"],
        "light.color": p["tenue"],
        "mid.light.color": p["apagado"],
        "dark.color": p["negro"],
        "mid.color": p["apagado"],
        "highlight.color": p["violeta"],
        "inactive.highlight.color": p["apagado"],
        "text.color": p["luz"],
        "window.text.color": p["luz"],
        "button.text.color": p["luz"],
    })
    if re.search(r"(?m)^transparent_dolphin_view=", t):
        t = poner_claves(t, {"transparent_dolphin_view": "true"})
    else:
        t = re.sub(r"(?m)^\[Hacks\]$", "[Hacks]\ntransparent_dolphin_view=true", t, count=1)
    return re.sub(r"#3a90eb", p["neon"], t, flags=re.I)


def _rellenar(etiqueta, color, alfa):
    """Pone fill + fill-opacity en UNA etiqueta que ya tenga fill."""
    if "fill:" not in etiqueta or "fill:none" in etiqueta:
        return etiqueta
    etiqueta = re.sub(r"fill:(#[0-9a-fA-F]{6}|url\(#[^)]*\))", "fill:" + color, etiqueta)
    etiqueta = re.sub(r";?fill-opacity:[\d.]+", "", etiqueta)
    return etiqueta.replace("fill:" + color, f"fill:{color};fill-opacity:{alfa}", 1)


def _fin_grupo(t, inicio):
    """Indice justo detras del </g> que cierra el <g> que empieza en `inicio`."""
    prof = 0
    for m in re.finditer(r"<g\b[^>]*?>|</g>", t[inicio:]):
        s = m.group(0)
        if s.startswith("</"):
            prof -= 1
        elif not s.endswith("/>"):
            prof += 1
        if prof == 0:
            return inicio + m.end()
    return None


# Las piezas del borde de un elemento de Kvantum llevan el lado al final.
BORDE_RE = re.compile(r"-(top|bottom|left|right|topleft|topright|bottomleft|bottomright)$")


def recolorear_familia(t, familia, interior, borde):
    """Todo lo de `familia` (el id exacto y los que empiezan por `familia-`):
    el interior (sin lado al final) con `interior`, cada trozo del borde con
    `borde`. Cada uno es (color, alfa), o None para no tocarlo. Si la pieza es
    un <g>, se recolorea lo que hay DENTRO, que es donde estan los colores."""
    piezas = [(m.start(), m.group(1)) for m in re.finditer(r'<[a-z]+\b[^>]*\bid="([^"]+)"', t)
              if m.group(1) == familia or m.group(1).startswith(familia + "-")]
    for inicio, ident in reversed(piezas):   # de atras adelante: no mueve indices
        color = borde if BORDE_RE.search(ident) else interior
        if not color:
            continue
        if t.startswith("<g", inicio):
            fin = _fin_grupo(t, inicio)
            if fin is None:
                continue
        else:
            fin = t.index(">", inicio) + 1
        trozo = re.sub(r"<(?!/)[^>]+>", lambda m: _rellenar(m.group(0), *color), t[inicio:fin])
        t = t[:inicio] + trozo + t[fin:]
    return t


def render_svg(t, p):
    # La barra de herramientas: el interior y su linea de abajo.
    def barra(m):
        etiqueta, ident = m.group(0), m.group(1)
        if ident in ("menubar-normal", "menubar-normal-inactive"):
            return _rellenar(etiqueta, p["apagado"], "0.55")
        if "bottom" in ident:
            return _rellenar(etiqueta, p["amatista"], "0.55")
        return etiqueta
    t = re.sub(r'<[^>]*\bid="(menubar-[^"]*)"[^>]*>', barra, t)

    # Los botones: el interior es una etiqueta suelta con el id exacto, y cada
    # trozo del borde un <g> con las piezas dentro (por eso no basta con
    # cambiar la etiqueta del grupo: el color esta en sus hijos).
    interiores = {
        "button-focused": (p["violeta"], "0.35"),
        "button-focused-inactive": (p["violeta"], "0.35"),
        "tbutton-toggled": (p["violeta"], "0.55"),
        "button-toggled-inactive": (p["apagado"], "0.55"),
    }
    t = re.sub(r'<[^>]*\bid="([^"]+)"[^>]*>',
               lambda m: _rellenar(m.group(0), *interiores[m.group(1)])
               if m.group(1) in interiores else m.group(0), t)
    # Ojo, que hay DOS juegos de bordes: `button-*` (botones normales) y
    # `btn-*` / `tbtn-*`, que es el `frame.element=tbtn` de [ToolbarButton],
    # o sea el borde de los botones de la BARRA. Faltando el segundo, el
    # interior salia violeta y el borde gris (lo cazo tests/unidad/
    # transparencia.sh contra el KvGnomeDark de verdad). Las «-inactive»
    # delante: next() se quedaria con la familia corta.
    bordes = {"button-toggled-inactive": (p["tenue"], "0.50"),
              "btn-toggled-inactive": (p["tenue"], "0.50"),
              "button-focused": (p["amatista"], "0.60"),
              "btn-focused": (p["amatista"], "0.60"),
              "tbutton-toggled": (p["amatista"], "0.60"),
              "tbtn-toggled": (p["amatista"], "0.60"),
              "btn-toggled": (p["amatista"], "0.60")}
    grupos = [(m.start(), m.group(1)) for m in re.finditer(r'<g\b[^>]*\bid="([^"]+)"', t)]
    for inicio, ident in reversed(grupos):     # de atras adelante: no mueve indices
        familia = next((f for f in bordes if ident.startswith(f + "-")), None)
        if not familia:
            continue
        fin = _fin_grupo(t, inicio)
        if fin is None:
            continue
        trozo = re.sub(r"<(?!/)[^>]+>", lambda m: _rellenar(m.group(0), *bordes[familia]),
                       t[inicio:fin])
        t = t[:inicio] + trozo + t[fin:]

    # El campo de texto: `lineedit` (interior y borde ancho) y `le` (el borde
    # que usa [LineEdit] como frame.element). Y la barrita del scroll, que
    # en este tema es solo borde (interior=false en [ScrollbarSlider]).
    campo = (p["abismo"], "0.55")
    for familia, interior, borde in (
            ("lineedit-normal", campo, (p["amatista"], "0.55")),
            ("lineedit-focused", (p["abismo"], "0.70"), (p["neon"], "0.85")),
            ("le-normal", campo, (p["amatista"], "0.55")),
            ("le-focused", (p["abismo"], "0.70"), (p["neon"], "0.85")),
            ("scrollbarslider-normal", (p["amatista"], "0.45"), (p["amatista"], "0.45")),
            ("scrollbarslider-focused", (p["amatista"], "0.75"), (p["amatista"], "0.75")),
            ("scrollbarslider-pressed", (p["neon"], "0.90"), (p["neon"], "0.90")),
            # La cabecera de columnas de la vista detallada («Nombre», «Ruta»).
            ("header-normal", (p["apagado"], "0.55"), (p["amatista"], "0.45"))):
        t = recolorear_familia(t, familia, interior, borde)

    # El azul de acento (seleccion) y el azul claro de foco.
    t = re.sub(r"#15539e", p["violeta"], t, flags=re.I)
    return re.sub(r"#3a90eb", p["neon"], t, flags=re.I)


def generar(base_dir, paleta):
    nombre_base = base_dir.name
    kv = (base_dir / f"{nombre_base}.kvconfig").read_text(encoding="utf-8")
    svg = (base_dir / f"{nombre_base}.svg").read_text(encoding="utf-8")
    return {f"{NOMBRE}.kvconfig": render_kvconfig(kv, paleta),
            f"{NOMBRE}.svg": render_svg(svg, paleta)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", type=Path, default=BASE)
    ap.add_argument("--destino", type=Path,
                    default=Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
                    / "Kvantum" / NOMBRE)
    ap.add_argument("--paleta", type=Path, default=PALETA)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if not (args.base / f"{args.base.name}.kvconfig").is_file():
        print(f"no esta el tema base {args.base} (¿falta el paquete kvantum?)", file=sys.stderr)
        return 2
    paleta = cargar_paleta(args.paleta)
    faltan = [n for n in NECESARIOS if n not in paleta]
    if faltan:
        print(f"a {args.paleta} le faltan colores: {', '.join(faltan)}", file=sys.stderr)
        return 1

    ficheros = generar(args.base, paleta)
    if args.check:
        viejos = [n for n, c in ficheros.items()
                  if not (args.destino / n).is_file()
                  or (args.destino / n).read_text(encoding="utf-8") != c]
        for n in viejos:
            print(f"{args.destino / n} no esta al dia", file=sys.stderr)
        return 1 if viejos else 0
    args.destino.mkdir(parents=True, exist_ok=True)
    for n, c in ficheros.items():
        (args.destino / n).write_text(c, encoding="utf-8")
    print(args.destino)
    return 0


if __name__ == "__main__":
    sys.exit(main())
