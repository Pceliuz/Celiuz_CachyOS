#!/usr/bin/env python3
"""
tests/herramientas/volcar.py <salida.json> — el estado ENTERO del Hyprland de
esta sesion, a un JSON: todas las opciones (la lista sale de los tipos de la API,
/usr/share/hypr/stubs/hl.meta.lua), los atajos con sus banderas y descripcion,
el teclado de cada dispositivo, los monitores, las animaciones y curvas, y las
reglas de ventana MEDIDAS (abre una kitty con cada clase y mira si flota y su
tamano).

Se hizo para verificar el paso de hyprlang a Lua (2026-09-25) y sirve para
cualquier cambio grande: una version nueva de Hyprland, reordenar modulos...
Se corre DENTRO de un anidado, nunca en la sesion de verdad (abre ventanas):

    ./tests/anidado.sh python3 tests/herramientas/volcar.py /tmp/antes.json
    # ... cambio ...
    ./tests/anidado.sh python3 tests/herramientas/volcar.py /tmp/despues.json
    python3 tests/herramientas/comparar.py /tmp/antes.json /tmp/despues.json
"""
import json, re, subprocess, sys, time, os

def hc(*a, j=True):
    r = subprocess.run(["hyprctl"] + (["-j"] if j else []) + list(a), capture_output=True, text=True)
    if not j:
        return r.stdout
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {"_crudo": r.stdout.strip()}

claves = re.findall(r'^---\| "([^"]+)"', open("/usr/share/hypr/stubs/hl.meta.lua").read(), re.M)
claves = [c for c in claves if "." in c and not c.startswith(("config.", "hyprland.", "input.keyboard.key", "keybinds.", "layer.", "monitor.", "screenshare.", "window.", "workspace."))
          or c.startswith(("input.", "misc.", "general.", "decoration.", "animations.", "binds.", "cursor.", "debug.", "dwindle.", "ecosystem.", "experimental.", "gestures.", "group.", "layout.", "master.", "opengl.", "quirks.", "render.", "scrolling.", "xwayland.", "input_capture."))]
claves = sorted(set(c for c in claves if not c.startswith(("window.", "workspace.", "monitor.", "layer."))))

def a_getoption(c):
    trozos = c.split(".")
    out = []
    i = 0
    while i < len(trozos):
        if trozos[i] == "col" and i + 1 < len(trozos):
            out.append("col." + trozos[i + 1]); i += 2
        else:
            out.append(trozos[i]); i += 1
    return ":".join(out)

opciones = {}
for c in claves:
    v = hc("getoption", a_getoption(c))
    if isinstance(v, dict):
        v.pop("option", None)
    opciones[c] = v

binds = []
for b in hc("binds"):
    binds.append({k: b.get(k) for k in ("modmask", "key", "keycode", "locked", "mouse", "release", "repeat", "longPress", "non_consuming", "catch_all", "submap", "dispatcher", "arg", "description")})

teclados = [{k: d.get(k) for k in ("name", "layout", "variant", "options", "rules", "model")} for d in hc("devices").get("keyboards", [])]
monitores = [{k: m.get(k) for k in ("name", "width", "height", "refreshRate", "x", "y", "scale")} for m in hc("monitors")]
animaciones = hc("animations")

# Reglas de ventana: abrir una kitty con cada clase y mirar como sale.
reglas = {}
for clase in ("monitor-tui", "config-reload", "aviso-detalle", "sin-regla"):
    p = subprocess.Popen(["kitty", "--class", clase, "-o", "confirm_os_window_close=0", "sleep", "20"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    c = None
    for _ in range(60):
        time.sleep(0.2)
        c = next((x for x in hc("clients") if x.get("class") == clase), None)
        if c:
            break
    time.sleep(0.8)
    c = next((x for x in hc("clients") if x.get("class") == clase), None)
    reglas[clase] = {k: c.get(k) for k in ("floating", "size", "at")} if c else None
    p.kill(); p.wait()
    time.sleep(0.5)

json.dump({"opciones": opciones, "binds": binds, "teclados": teclados, "monitores": monitores,
           "animaciones": animaciones, "reglas": reglas, "errores": hc("configerrors", j=False).strip(),
           "modo": hc("eval", "return 1", j=False).strip()},
          open(sys.argv[1], "w"), indent=1, ensure_ascii=False, sort_keys=True)
print("volcado:", len(opciones), "opciones,", len(binds), "atajos")
