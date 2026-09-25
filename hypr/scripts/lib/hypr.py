#!/usr/bin/env python3
"""
hypr/scripts/lib/hypr.py
Hablarle a Hyprland en el idioma que entienda: el de la config en Lua, o el
viejo de hyprlang.

POR QUE EXISTE
--------------
Desde Hyprland 0.56 la config puede ser Lua (`hyprland.lua`), y la 0.57 retira
la de hyprlang (`hyprland.conf`). Lo que no dice el cartel de aviso, y se midio
el 2026-09-25 en dos anidados, uno de cada: **el modo de la config cambia
tambien lo que acepta `hyprctl`**.

    orden                               con .conf          con .lua
    hyprctl dispatch workspace 3        ok                 error de sintaxis Lua
    hyprctl dispatch 'hl.dsp.focus(..)' Invalid dispatcher ok
    hyprctl keyword misc:x false        ok                 «keyword can't work with
                                                           non-legacy parsers. Use eval.»
    hyprctl eval 'return 1'             «eval is only      ok
                                        supported with the lua config manager»
    hyprctl getoption ...               igual              igual

O sea que un script que diga `dispatch workspace 3` se rompe EN SILENCIO al
pasar la config a Lua: el bloqueo no vaciaria el escritorio, hypridle no
apagaria la pantalla, la rueda de la barra no cambiaria de escritorio...

Y no vale con escribirlo todo en Lua: el MODO lo decide el Hyprland que esta
corriendo, no el repo. La sesion que ya estaba abierta al traer los cambios
sigue en hyprlang hasta cerrar sesion, y la otra maquina lo esta hasta que haga
`git pull`. Por eso se pregunta en caliente (`modo`) y se traduce.

Lo que se sabe traducir es SOLO lo que el repo usa, a proposito: una tabla
corta y medida vale mas que un traductor general que acierte a medias.

    dispatch workspace X        hl.dsp.focus({ workspace = X })
    dispatch dpms on|off|toggle hl.dsp.dpms({ action = "on" })
    dispatch exit               hl.dsp.exit()
    dispatch exec CMD           hl.dsp.exec_cmd("CMD")
    keyword a:b:c V             hl.config({ a = { b = { c = V } } })
    keyword monitor N,M,P,E     hl.monitor({ output = N, mode = M, position = P, scale = E })

ESTO TIENE UN GEMELO EN SHELL
-----------------------------
`hypr.sh` hace lo mismo para lock.sh y los binds (que no pueden pagar el
arranque de python). `tests/unidad/hypr-compat.sh` compara las dos caso por
caso y falla si se separan.
"""
import os
import re
import subprocess

LUA, CONF = "lua", "conf"


def modo_por_respuesta(respuesta):
    """Lo que contesta `eval return 1`: "lua", "conf" o "" si no se sabe.

    Tres salidas y no dos, a proposito (la misma regla que `hyprctl locked` en
    el CLAUDE.md): un Hyprland que no contesta NO es un Hyprland con .conf.
    """
    r = (respuesta or "").strip()
    if r == "ok":
        return LUA
    if "only supported with the lua config manager" in r or "unknown request" in r.lower():
        return CONF
    return ""


def modo():
    """El modo del Hyprland de esta sesion, preguntando con hyprctl."""
    try:
        r = subprocess.run(["hyprctl", "eval", "return 1"], capture_output=True,
                           text=True, timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return modo_por_respuesta(r.stdout)


def cadena_lua(texto):
    """Un literal de cadena de Lua con comillas dobles."""
    t = str(texto).replace("\\", "\\\\").replace('"', '\\"')
    t = t.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return '"' + t + '"'


_NUMERO = re.compile(r"^-?\d+(\.\d+)?$")


def valor_lua(texto):
    """true/false y numeros tal cual; lo demas, cadena."""
    t = str(texto).strip()
    if t in ("true", "false"):
        return t
    if t in ("yes", "on"):
        return "true"
    if t in ("no", "off"):
        return "false"
    if _NUMERO.match(t):
        return t
    return cadena_lua(t)


def dispatch_lua(dispatcher, argumento=""):
    """La expresion de Lua de un dispatcher viejo. ValueError si no se sabe."""
    d = dispatcher.strip()
    a = (argumento or "").strip()
    if d == "workspace":
        if not a:
            raise ValueError("workspace sin escritorio")
        return "hl.dsp.focus({ workspace = %s })" % (a if _NUMERO.match(a) else cadena_lua(a))
    if d == "dpms":
        accion = a.split()[0] if a else "toggle"
        if accion not in ("on", "off", "toggle"):
            raise ValueError("dpms: accion desconocida «%s»" % accion)
        return 'hl.dsp.dpms({ action = "%s" })' % accion
    if d == "exit":
        return "hl.dsp.exit()"
    if d == "exec":
        if not a:
            raise ValueError("exec sin orden")
        return "hl.dsp.exec_cmd(%s)" % cadena_lua(a)
    raise ValueError("no se traducir el dispatcher «%s»" % d)


def keyword_lua(clave, valor):
    """El Lua de un `keyword` viejo. ValueError si no se sabe."""
    c = clave.strip()
    if c == "monitor":
        partes = [p.strip() for p in str(valor).split(",")]
        if len(partes) != 4 or not partes[0]:
            raise ValueError("monitor: se esperaban 4 campos, «%s»" % valor)
        nombre, modo_, posicion, escala = partes
        return ("hl.monitor({ output = %s, mode = %s, position = %s, scale = %s })"
                % (cadena_lua(nombre), cadena_lua(modo_), cadena_lua(posicion),
                   valor_lua(escala)))
    trozos = [t for t in c.split(":") if t]
    if len(trozos) < 2 or not all(re.match(r"^[a-z_][a-z0-9_.]*$", t) for t in trozos):
        raise ValueError("no se traducir la opcion «%s»" % c)
    # `col.active_border` es una clave con punto DENTRO de la seccion; en Lua
    # va como tabla anidada (general = { col = { active_border = ... } }).
    trozos = [p for t in trozos for p in t.split(".")]
    lua = valor_lua(valor)
    for t in reversed(trozos):
        lua = "{ %s = %s }" % (t, lua)
    return "hl.config(%s)" % lua


def peticion_dispatch(modo_, dispatcher, argumento=""):
    """El texto que va DETRAS de `dispatch` (en hyprctl o por el socket)."""
    if modo_ == LUA:
        return dispatch_lua(dispatcher, argumento)
    return ("%s %s" % (dispatcher, argumento)).strip()


def peticion_keyword(modo_, clave, valor):
    """(verbo, resto) para hyprctl o el socket: `keyword` en hyprlang, `eval`
    en Lua."""
    if modo_ == LUA:
        return "eval", keyword_lua(clave, valor)
    return "keyword", "%s %s" % (clave, valor)


if __name__ == "__main__":
    # Para que la prueba compare con el gemelo de shell:
    #   hypr.py dispatch <modo> <dispatcher> [arg]
    #   hypr.py keyword <modo> <clave> <valor>
    #   hypr.py modo-de "<respuesta>"
    import sys
    a = sys.argv[1:]
    try:
        if a[:1] == ["dispatch"] and len(a) >= 3:
            print(peticion_dispatch(a[1], a[2], " ".join(a[3:])))
        elif a[:1] == ["keyword"] and len(a) == 4:
            print(" ".join(peticion_keyword(a[1], a[2], a[3])))
        elif a[:1] == ["modo-de"] and len(a) == 2:
            print(modo_por_respuesta(a[1]))
        elif a == ["modo"]:
            print(modo())
        else:
            sys.exit("uso: hypr.py dispatch|keyword|modo-de|modo ...")
    except ValueError as e:
        sys.exit("hypr.py: %s" % e)
