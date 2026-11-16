#!/usr/bin/env python3
"""
hypr/scripts/lib/grabacion.py — lo que grabar.sh necesita saber de Hyprland y de
PipeWire para grabar UNA VENTANA con SOLO SU SONIDO.

    grabacion.py ventanas            las ventanas que se pueden grabar, en JSON
    grabacion.py audio DIRECCION     las fuentes `app:` del sonido de esa ventana
    grabacion.py preseleccionar DIRECCION
                                     deja el recado para grabar-portal.py

POR QUE UNA VENTANA VA POR EL PORTAL
------------------------------------
gpu-screen-recorder en Wayland graba monitores y zonas por su cuenta, pero una
ventana solo a traves de xdg-desktop-portal: el portal de Hyprland (xdph) le da
la imagen de ESA ventana con hyprland_toplevel_export, aunque este tapada o en
otro escritorio (medido el 2026-11-16: una terminal en el escritorio 9, sin
verse, salio grabada con su reloj corriendo).

El portal pregunta "¿que ventana?" lanzando un selector. Por defecto es
hyprland-share-picker, una ventana suya; xdph.conf lo cambia por
grabar-portal.py, que lee el recado que deja `preseleccionar` y, si no hay
recado, le pasa la pregunta al de siempre. Asi compartir pantalla en una
videollamada sigue funcionando igual que antes.

POR QUE EL SONIDO SE BUSCA POR PROCESO
--------------------------------------
gpu-screen-recorder graba el sonido de una app con `-a app:NOMBRE`, y NOMBRE es
el `application.name` que la app anuncia a PipeWire —«Brave», no «brave-browser»
(medido: `app:brave-browser` grabo silencio con Brave sonando)—. Ese nombre no
se puede deducir de la ventana, hay que preguntarselo a PipeWire: se buscan los
flujos de salida cuyo `application.process.id` sea el proceso de la ventana o
uno de sus hijos (los navegadores suenan desde un proceso hijo).

Si la app no esta sonando al empezar no hay flujo que mirar, y se anaden de
reserva el nombre del ejecutable y la clase de la ventana: gpu-screen-recorder
engancha tambien los flujos que aparecen DESPUES de empezar (medido), y el
nombre no distingue mayusculas.

El limite, y no tiene arreglo aqui: PipeWire separa el sonido por PROGRAMA, no
por ventana. Dos ventanas del mismo navegador comparten proceso y nombre, asi
que grabar una se lleva el sonido de las dos.
"""

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import canales  # noqa: E402

# Lo que dura el recado: el portal pregunta en el primer segundo de la
# grabacion. Uno viejo (una grabacion que no llego a arrancar) no puede
# contestar por su cuenta la siguiente vez que una videollamada pida pantalla.
VIDA_RECADO = 20.0


def _json_de(orden):
    try:
        r = subprocess.run(orden, capture_output=True, text=True, timeout=5)
        return json.loads(r.stdout) if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def ventanas(clientes=None):
    """Las ventanas que se pueden grabar: las mapeadas y en un escritorio de
    verdad (los especiales, como el scratchpad, tambien valen; los negativos
    que no son especiales no existen para el usuario)."""
    if clientes is None:
        clientes = _json_de(["hyprctl", "clients", "-j"]) or []
    salida = []
    for c in clientes:
        if not c.get("mapped", True) or c.get("hidden"):
            continue
        ws = c.get("workspace") or {}
        salida.append({
            "direccion": c.get("address", ""),
            "clase": c.get("class") or c.get("initialClass") or "",
            "titulo": c.get("title") or "",
            "escritorio": ws.get("name", ""),
            "pid": c.get("pid", 0),
            "foco": c.get("focusHistoryID", 99),
        })
    # La que tuviste delante la ultima, primero: es la que mas veces se quiere.
    salida.sort(key=lambda v: v["foco"])
    return salida


def _hijos(raiz, proc="/proc"):
    """El PID raiz y todos sus descendientes, mirando /proc/*/stat."""
    padres = {}
    try:
        entradas = os.listdir(proc)
    except OSError:
        return {raiz}
    for e in entradas:
        if not e.isdigit():
            continue
        try:
            with open(os.path.join(proc, e, "stat")) as f:
                stat = f.read()
            # El nombre va entre parentesis y puede llevar espacios: se corta
            # por el ULTIMO ')'.
            ppid = int(stat.rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            continue
        padres.setdefault(ppid, []).append(int(e))
    todos, pendientes = set(), [raiz]
    while pendientes:
        p = pendientes.pop()
        if p in todos:
            continue
        todos.add(p)
        pendientes.extend(padres.get(p, []))
    return todos


def flujos_de_salida(volcado=None):
    """(application.name, application.process.id) de cada flujo que suena."""
    if volcado is None:
        volcado = _json_de(["pw-dump"]) or []
    flujos = []
    for o in volcado:
        p = ((o.get("info") or {}).get("props")) or {}
        if p.get("media.class") != "Stream/Output/Audio":
            continue
        nombre = p.get("application.name")
        try:
            pid = int(p.get("application.process.id"))
        except (TypeError, ValueError):
            continue
        if nombre:
            flujos.append((nombre, pid))
    return flujos


def _ejecutable(pid, proc="/proc"):
    try:
        return os.path.basename(os.readlink(os.path.join(proc, str(pid), "exe")))
    except OSError:
        return ""


def nombres_audio(ventana, flujos=None, proc="/proc"):
    """Los nombres para `-a app:` del sonido de una ventana: primero los que
    PipeWire dice que suenan desde su arbol de procesos, despues los de
    reserva. Sin repetir (sin mirar mayusculas, como gpu-screen-recorder)."""
    pid = int(ventana.get("pid") or 0)
    nombres = []
    if pid > 0:
        arbol = _hijos(pid, proc)
        for nombre, p in (flujos if flujos is not None else flujos_de_salida()):
            if p in arbol:
                nombres.append(nombre)
        nombres.append(_ejecutable(pid, proc))
    nombres.append(ventana.get("clase", ""))
    vistos, salida = set(), []
    for n in nombres:
        # El `|` separa fuentes en -a: un nombre que lo llevara partiria la
        # orden en dos fuentes que no son.
        n = (n or "").strip().replace("|", "")
        if n and n.lower() not in vistos:
            vistos.add(n.lower())
            salida.append(n)
    return salida


def fuente_audio(ventana, **kw):
    """El argumento entero de -a: `app:A|app:B`. Vacio si no hay nada."""
    return "|".join("app:" + n for n in nombres_audio(ventana, **kw))


def buscar(direccion, lista=None):
    for v in (lista if lista is not None else ventanas()):
        if v["direccion"].lower() == direccion.lower():
            return v
    return None


# --- El recado para grabar-portal.py ----------------------------------------

def ruta_recado():
    return canales.canal("grabar-ventana", "recado")


def preseleccionar(direccion, ruta=None):
    ruta = ruta or ruta_recado()
    tmp = ruta + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"direccion": direccion, "cuando": time.time()}, f)
    os.replace(tmp, ruta)


def tomar_recado(ruta=None, ahora=None):
    """La direccion encargada, si hay un recado fresco. Se BORRA al leerlo: sirve
    para una pregunta del portal, no para todas las que vengan detras."""
    ruta = ruta or ruta_recado()
    try:
        with open(ruta) as f:
            datos = json.load(f)
    except (OSError, ValueError):
        return None
    finally:
        try:
            os.unlink(ruta)
        except OSError:
            pass
    ahora = time.time() if ahora is None else ahora
    if not isinstance(datos, dict) or ahora - float(datos.get("cuando", 0)) > VIDA_RECADO:
        return None
    return datos.get("direccion") or None


def id_en_lista_del_portal(direccion, lista):
    """El identificador que espera xdph para una ventana de Hyprland.

    xdph le pasa al selector XDPH_WINDOW_SHARING_LIST, entradas seguidas de la
    forma  ID[HC>]clase[HT>]titulo[HE>]DIRECCION[HA>]  con la DIRECCION en
    decimal (la de `hyprctl clients`, que va en hexadecimal). El selector
    contesta  [SELECTION]/window:ID .
    """
    try:
        buscada = int(direccion, 16)
    except (TypeError, ValueError):
        return None
    for entrada in lista.split("[HA>]"):
        if "[HE>]" not in entrada or "[HC>]" not in entrada:
            continue
        ident = entrada.split("[HC>]", 1)[0]
        try:
            if int(entrada.rsplit("[HE>]", 1)[1]) == buscada:
                return ident
        except ValueError:
            continue
    return None


def main(argv):
    if argv[:1] == ["ventanas"]:
        print(json.dumps(ventanas(), ensure_ascii=False))
        return 0
    if len(argv) == 2 and argv[0] == "audio":
        v = buscar(argv[1])
        if not v:
            return 1
        print(fuente_audio(v))
        return 0
    if len(argv) == 2 and argv[0] == "preseleccionar":
        preseleccionar(argv[1])
        return 0
    print("uso: grabacion.py ventanas | audio DIRECCION | preseleccionar DIRECCION",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
