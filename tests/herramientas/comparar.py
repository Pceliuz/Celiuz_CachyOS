#!/usr/bin/env python3
"""
tests/herramientas/comparar.py <a.json> <b.json> — lo que difiere entre dos
volcados de volcar.py, normalizando lo que es solo formato: `"int": 1` frente a
`"bool": true`, `"custom"` frente a `"css"`/`"gradient"` (hyprlang y Lua dicen
lo mismo con campos distintos), y las rutas que hyprlang expande al leer la
config y Lua deja para el shell.

LEGADO traduce la accion de un atajo de hyprlang a la descripcion que lleva en
Lua (alli `hyprctl binds` solo dice `__lua`). Si comparas dos volcados Lua, no
hace falta.

Ruido conocido en la comparacion hyprlang/Lua del 2026-09-25 (no son fallos):
`tap-to-click`/`tap-and-drag` se llaman con guion en hyprlang, `input_capture.*`
solo existe en Lua, y `group.groupbar.font_weight_*` da «internal error» en el
getoption de Lua.
"""
import json, sys, re

a = json.load(open(sys.argv[1])); b = json.load(open(sys.argv[2]))
fallos = 0

def norm_valor(d):
    """El valor de un getoption, sin depender del modo."""
    if not isinstance(d, dict):
        return d
    d = dict(d)
    d.pop("set", None)
    if "_crudo" in d:
        return ("crudo", d["_crudo"])
    for k in ("bool", "int", "float", "str", "custom", "css", "vec2", "data", "gradient", "color"):
        pass
    vals = {k: v for k, v in d.items()}
    if len(vals) != 1:
        return tuple(sorted(vals.items()))
    k, v = next(iter(vals.items()))
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return round(float(v), 4)
    if isinstance(v, str):
        s = v.strip()
        # "4 4 4 4" (css) == "4" / custom "4 4 4 4"
        nums = s.split()
        if nums and all(re.fullmatch(r"-?\d+(\.\d+)?", n) for n in nums):
            if len(set(nums)) == 1:
                return round(float(nums[0]), 4)
            return tuple(round(float(n), 4) for n in nums)
        return s.lower()
    if isinstance(v, list):
        return tuple(v)
    return v

def set_de(d):
    return d.get("set") if isinstance(d, dict) else None

print("== OPCIONES")
for c in sorted(set(a["opciones"]) | set(b["opciones"])):
    va, vb = a["opciones"].get(c), b["opciones"].get(c)
    na, nb = norm_valor(va), norm_valor(vb)
    if na != nb or set_de(va) != set_de(vb):
        fallos += 1
        print(f"  {c}:\n     conf: {json.dumps(va)}\n     lua : {json.dumps(vb)}")

print("== ATAJOS")
def clave_bind(x):
    return (x["modmask"], x["key"], x["keycode"])
def banderas(x):
    return {k: x.get(k) for k in ("locked", "mouse", "release", "repeat", "longPress", "non_consuming", "catch_all", "submap")}
LEGADO = {  # dispatcher de hyprlang -> descripcion que lleva en Lua
    ("killactive", ""): "cerrar la ventana",
    ("togglefloating", ""): "flotante o en mosaico",
    ("dpms", "on"): "encender la pantalla",
    ("movefocus", "l"): "foco a la izquierda", ("movefocus", "r"): "foco a la derecha",
    ("movefocus", "u"): "foco arriba", ("movefocus", "d"): "foco abajo",
    ("movewindow", ""): "arrastrar la ventana", ("resizewindow", ""): "redimensionar la ventana",
}
for i in range(1, 8):
    LEGADO[("workspace", str(i))] = f"ir al escritorio {i}"
    LEGADO[("movetoworkspace", str(i))] = f"mover la ventana al escritorio {i}"
ba = {clave_bind(x): x for x in a["binds"]}
bb = {clave_bind(x): x for x in b["binds"]}
for k in sorted(set(ba) | set(bb), key=str):
    xa, xb = ba.get(k), bb.get(k)
    if not xa or not xb:
        fallos += 1; print(f"  {k}: solo en {'conf' if xa else 'lua'}"); continue
    fa, fb = banderas(xa), banderas(xb)
    if xa["dispatcher"] == "mouse":
        fb = dict(fb, mouse=True)   # medido: en Lua el arrastre no depende de la bandera
    if fa != fb:
        fallos += 1; print(f"  {k}: banderas\n     conf: {fa}\n     lua : {fb}")
    if xa["dispatcher"] == "exec":
        # hyprlang expande las variables de entorno al LEER la config; Lua las
        # deja en la orden y las expande el shell al ejecutarla. Equivalente.
        esperado = re.sub(r"/tmp/anidado-\w+/casa", "$HOME", xa["arg"])
        esperado = re.sub(r"/tmp/anidado-\w+/run", "$XDG_RUNTIME_DIR", esperado)
        if esperado == "hyprctl dispatch dpms on":
            esperado = "encender la pantalla"   # la tapa: en Lua va con hl.dsp.dpms
    elif xa["dispatcher"] == "mouse":
        esperado = LEGADO.get((xa["arg"].strip(), ""), "??")
    else:
        esperado = LEGADO.get((xa["dispatcher"], xa["arg"].strip()), f"?? {xa['dispatcher']} {xa['arg']}")
    if xb.get("description") != esperado or xb["dispatcher"] != "__lua":
        fallos += 1; print(f"  {k}: accion\n     conf: {xa['dispatcher']} {xa['arg']!r}\n     lua : {xb.get('description')!r}")

for seccion in ("teclados", "monitores", "reglas"):
    print("==", seccion.upper())
    if a[seccion] != b[seccion]:
        fallos += 1
        print(f"  conf: {json.dumps(a[seccion], ensure_ascii=False)}\n  lua : {json.dumps(b[seccion], ensure_ascii=False)}")

print("== ANIMACIONES")
if a["animaciones"] != b["animaciones"]:
    fallos += 1
    ja = json.dumps(a["animaciones"], sort_keys=True); jb = json.dumps(b["animaciones"], sort_keys=True)
    print("  difieren (detalle abajo)")
    print("  conf:", ja[:3000]); print("  lua :", jb[:3000])

print("== ERRORES   conf:", repr(a["errores"]), " lua:", repr(b["errores"]))
print("== MODO      conf:", a["modo"][:40], " lua:", b["modo"])
print(f"\n{fallos} diferencias")
