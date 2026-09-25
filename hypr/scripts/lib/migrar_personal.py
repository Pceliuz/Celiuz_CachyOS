#!/usr/bin/env python3
"""
hypr/scripts/lib/migrar_personal.py
Traduce tu `conf/personal.conf` (hyprlang) a `lua/personal.lua`.

    migrar_personal.py <personal.conf>     imprime el Lua por la salida
                                           estandar y los avisos por stderr

POR QUE EXISTE. Al pasar la config a Lua (2026-09-25), lo tuyo se queda en un
fichero que Hyprland ya no lee: `personal.conf` no se versiona, asi que el repo
no puede traerte la version nueva. Sin esto, al volver a entrar perderias en
silencio lo que tuvieras ahi — en la laptop del autor, las dos lineas que le
ponen al televisor su escala 1.5 y a la pantalla interna su sitio.

Lo usa `instalar.sh` UNA vez: solo si no hay `lua/personal.lua` y tu
`personal.conf` tiene algo que no sean comentarios. No toca `personal.conf`: una
sesion que arranco con la config vieja lo sigue leyendo hasta cerrar sesion.

QUE SABE TRADUCIR, que es lo que se suele poner ahi:

    monitor = SALIDA, MODO, POSICION, ESCALA   ->  hl.monitor({ ... })
    exec-once = orden                          ->  al arrancar la sesion
    exec = orden                               ->  en cada carga
    env = NOMBRE,valor                         ->  hl.env(...)
    bind[elr...] = MODS, tecla, exec, orden    ->  hl.bind(...)
    # comentario                               ->  -- comentario

Todo lo demas —secciones `input { ... }`, un bind a otro dispatcher, una linea
con `$variables` de hyprlang— NO se adivina: se copia COMENTADO con una marca
«SIN TRADUCIR» y se avisa, para que lo pases tu. Una traduccion que acierta a
medias es peor que un aviso: te deja algo que parece funcionar.
"""
import re
import sys

MARCA = "-- SIN TRADUCIR (pasalo a mano; ver lua/*.lua de ejemplo): "


def cadena(texto):
    t = texto.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + t + '"'


def escala(texto):
    t = texto.strip()
    return t if re.fullmatch(r"\d+(\.\d+)?", t) else cadena(t)


BANDERAS = {"l": "locked", "e": "repeating", "r": "release", "n": "non_consuming",
            "t": "transparent", "i": "ignore_mods", "o": "long_press"}


def traducir(texto):
    """(lua, avisos) de un personal.conf entero."""
    salida, avisos = [], []
    for n, linea in enumerate(texto.splitlines(), 1):
        cruda = linea.rstrip()
        s = cruda.strip()
        if not s:
            salida.append("")
            continue
        if s.startswith("#"):
            salida.append("--" + s[1:])
            continue
        # Un comentario al final de la linea se conserva aparte.
        codigo, _, coment = s.partition(" #")
        codigo = codigo.strip()
        cola = (" --" + coment) if coment else ""
        m = re.fullmatch(r"([\w-]+)\s*=\s*(.*)", codigo)
        lua = None
        # Una variable de hyprlang (`$terminal`, `$mainMod`: en minuscula por
        # costumbre) no existe en Lua, y dejarla escrita llegaria al shell
        # vacia. Las de entorno (`$HOME`, `$XDG_RUNTIME_DIR`) si valen: las
        # expande el shell al ejecutar, igual que antes.
        if m and not re.search(r"\$\{?[a-z]", m.group(2)):
            clave, valor = m.group(1), m.group(2).strip()
            if clave == "monitor":
                p = [x.strip() for x in valor.split(",")]
                if len(p) == 4:
                    lua = ("hl.monitor({ output = %s, mode = %s, position = %s, scale = %s })"
                           % (cadena(p[0]), cadena(p[1]), cadena(p[2]), escala(p[3])))
                elif len(p) == 2 and p[1] == "disable":
                    lua = "hl.monitor({ output = %s, disabled = true })" % cadena(p[0])
            elif clave == "exec-once" and valor:
                lua = ('hl.on("hyprland.start", function() hl.exec_cmd(%s) end)'
                       % cadena(valor))
            elif clave == "exec" and valor:
                lua = "hl.exec_cmd(%s)" % cadena(valor)
            elif clave == "env" and "," in valor:
                k, v = valor.split(",", 1)
                lua = "hl.env(%s, %s)" % (cadena(k.strip()), cadena(v.strip()))
            elif re.fullmatch(r"bind[lernatio]*", clave):
                p = [x.strip() for x in valor.split(",", 3)]
                flags = clave[4:]
                if len(p) == 4 and p[2] == "exec":
                    mods = " + ".join(p[0].split())
                    tecla = (mods + " + " + p[1]) if mods else p[1]
                    opciones = ", ".join("%s = true" % BANDERAS[f] for f in flags)
                    lua = "hl.bind(%s, hl.dsp.exec_cmd(%s)%s)" % (
                        cadena(tecla), cadena(p[3]),
                        (", { " + opciones + " }") if opciones else "")
        if lua is None:
            salida.append(MARCA + cruda)
            avisos.append("linea %d sin traducir: %s" % (n, s))
        else:
            salida.append(lua + cola)
    return "\n".join(salida).rstrip() + "\n", avisos


CABECERA = """\
-- hypr/lua/personal.lua — TUYO. No se versiona, y el repo no lo pisa nunca.
--
-- TRADUCIDO de tu conf/personal.conf al pasar la config a Lua. Revisa lo
-- marcado «SIN TRADUCIR»: eso no se adivino, y esta comentado.
--
-- Se carga el ULTIMO de todos, asi que aqui puedes anadir lo que quieras y
-- tambien pisar cualquier ajuste o atajo del repo. Ejemplos en lua/*.lua.

"""


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("uso: migrar_personal.py <personal.conf>")
    with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
        lua, avisos = traducir(f.read())
    sys.stdout.write(CABECERA + lua)
    for a in avisos:
        print(a, file=sys.stderr)
