#!/usr/bin/env python3
# kitty/celiuz-iconos.py — iconos de Nerd Font a su tamaño en kitty.
#
# Lo pidio el usuario (2026-10-22): los iconos de colores del saludo de la
# terminal (fastfetch/plantilla.jsonc) salian diminutos. Kitty los cogia de
# la variante «Mono» de la Nerd Font instalada, que los ENCOGE a una celda.
# La variante normal de la misma fuente los dibuja casi el doble, y kitty les
# deja ocupar dos celdas cuando detras va un espacio (lo que hace el saludo).
#
# kitty.conf no es del repo, asi que instalar.sh le añade una linea marcada:
#     geninclude celiuz-iconos.py
# y enlaza este fichero en ~/.config/kitty. `geninclude` lo EJECUTA cada vez
# que arranca kitty y usa lo que imprime como config: la fuente se pregunta en
# caliente (regla del CLAUDE.md), no se apunta al instalar. Cuesta un fc-match
# (~15 ms). Sin Nerd Font normal no imprime nada y todo queda como estaba.
#
# Que fuente: «Symbols Nerd Font» si esta (solo trae iconos); si no, la normal
# de la familia cuya Mono esta dibujando hoy los iconos (asi no cambia el
# estilo); si no, cualquier Nerd Font normal.
#
# Rangos: la zona privada de Unicode donde viven los iconos, MENOS los
# separadores de powerline (U+E0A0-E0D7): esos van pegados al texto de un
# prompt y, mas anchos, lo descuadrarian.

import subprocess

RANGOS = "U+E000-U+E09F,U+E0D8-U+F8FF,U+F0000-U+FFFFF"


def fc(*args):
    try:
        r = subprocess.run(["fc-match" if args[0] == "match" else "fc-list", *args[1:]],
                           capture_output=True, text=True, timeout=2)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def familias():
    """Las Nerd Font normales (ni Mono ni Propo) instaladas."""
    todas = set()
    for linea in fc("list", ":", "family").splitlines():
        for f in linea.split(","):
            f = f.strip()
            if f.endswith("Nerd Font"):
                todas.add(f)
    return todas


def elegir():
    normales = familias()
    if not normales:
        return None
    if "Symbols Nerd Font" in normales:
        return "Symbols Nerd Font"
    # La que pinta hoy un icono cualquiera (U+F303, el de Arch).
    hoy = fc("match", "-f", "%{family}", "monospace:charset=f303").split(",")[0].strip()
    for sufijo in (" Mono", " Propo"):
        if hoy.endswith(sufijo) and hoy[: -len(sufijo)] in normales:
            return hoy[: -len(sufijo)]
    if hoy in normales:
        return hoy
    return sorted(normales)[0]


def config():
    fuente = elegir()
    return f"symbol_map {RANGOS} {fuente}\n" if fuente else ""


if __name__ == "__main__":
    print(config(), end="")
