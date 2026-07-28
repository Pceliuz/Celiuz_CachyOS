#!/usr/bin/env python3
"""
~/dotfiles/hypr/scripts/lib/congelar.py

Congela y descongela aplicaciones al bloquear la pantalla.

COMO
----
Con el *freezer* de cgroup v2, via `systemctl --user freeze|thaw <scope>`. Es
atomico y reversible: el kernel para todos los hilos del cgroup a la vez, no hay
carrera con procesos que estén creando hijos, y al descongelar siguen justo donde
estaban. Muy superior a repartir SIGSTOP por un arbol de procesos.

QUE se congela lo decide juegos.py (cuatro capas + excepciones a mano).

LA RED DE SEGURIDAD (lo importante de este archivo)
---------------------------------------------------
Dejar una aplicacion congelada para siempre es peor que no congelar nada: parece
que se colgo, no responde, y no hay ninguna pista de por que. Asi que:

1. Cada congelado deja un PARTE en $XDG_RUNTIME_DIR/congelado.json con la lista
   de unidades y la hora. Vive en /run, o sea que un reinicio lo borra solo.
2. `descongelar()` no se fia del parte: ademas de las unidades apuntadas,
   recorre TODOS los scopes del usuario y descongela cualquiera que encuentre
   con FreezerState != running. Aunque el parte se pierda o se quede corto, nada
   se queda helado.
3. Las terminales nunca se congelan (decision del usuario, para no tirar sus
   sesiones SSH), asi que si algo va mal SIEMPRE queda una terminal viva desde la
   que ejecutar:  hypr/scripts/lib/congelar.py descongelar

Uso directo (util tambien para el asistente):
    congelar.py estado        que hay congelado ahora
    congelar.py congelar      congela lo que toque (sin bloquear la pantalla)
    congelar.py descongelar   descongela todo, pase lo que pase
"""

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import juegos  # noqa: E402

RUNTIME = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
PARTE = os.path.join(RUNTIME, "congelado.json")


def _systemctl(*args, timeout=10):
    """Devuelve (codigo, salida). Nunca lanza: aqui fallar en silencio es peor."""
    try:
        r = subprocess.run(["systemctl", "--user", *args],
                           capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.SubprocessError) as e:
        return 1, str(e)


def _estado_freezer(unidad):
    _, s = _systemctl("show", "-p", "FreezerState", "--value", unidad)
    return s or "?"


def _scopes_de_usuario():
    _, salida = _systemctl("list-units", "--type=scope", "--all",
                           "--no-legend", "--no-pager", "--plain")
    unidades = []
    for linea in salida.splitlines():
        piezas = linea.split()
        if piezas and piezas[0].endswith(".scope"):
            unidades.append(piezas[0])
    return unidades


def congelar():
    """Congela las apps que toque. Devuelve (congeladas, salvadas)."""
    inventario = juegos.inventario()
    congeladas, salvadas = [], []

    for x in inventario:
        if not x["congelar"]:
            salvadas.append((x["unidad"], x["motivo"]))
            continue
        codigo, mensaje = _systemctl("freeze", x["unidad"])
        if codigo == 0:
            congeladas.append(x["unidad"])
        else:
            # No es fatal: seguimos con las demas. Un scope puede haberse ido
            # entre que lo listamos y lo congelamos.
            print(f"congelar: no se pudo con {x['unidad']}: {mensaje}",
                  file=sys.stderr)

    try:
        with open(PARTE, "w", encoding="utf-8") as fh:
            json.dump({"cuando": time.time(), "unidades": congeladas}, fh)
    except OSError as e:
        # Si no se puede escribir el parte, descongelar sigue funcionando por el
        # barrido del punto 3. Se avisa, pero no se aborta.
        print(f"congelar: aviso, no pude escribir el parte: {e}", file=sys.stderr)

    return congeladas, salvadas


def descongelar():
    """Descongela TODO. Devuelve la lista de unidades que estaban congeladas.

    No se fia del parte: barre todos los scopes. Es la funcion que tiene que
    funcionar siempre, incluso si lo que la llamo antes murio a medias.
    """
    apuntadas = []
    try:
        with open(PARTE, encoding="utf-8") as fh:
            apuntadas = json.load(fh).get("unidades", [])
    except (OSError, ValueError):
        pass

    candidatas = list(dict.fromkeys(apuntadas + _scopes_de_usuario()))
    descongeladas = []
    for unidad in candidatas:
        if _estado_freezer(unidad) in ("running", "?", ""):
            continue
        codigo, mensaje = _systemctl("thaw", unidad)
        if codigo == 0:
            descongeladas.append(unidad)
        else:
            print(f"descongelar: no se pudo con {unidad}: {mensaje}",
                  file=sys.stderr)

    try:
        os.unlink(PARTE)
    except OSError:
        pass
    return descongeladas


def estado():
    """[(unidad, estado_freezer)] de todo lo que no este corriendo normal."""
    return [(u, e) for u in _scopes_de_usuario()
            if (e := _estado_freezer(u)) not in ("running", "?", "")]


def _cli():
    orden = sys.argv[1] if len(sys.argv) > 1 else "estado"

    if orden == "congelar":
        congeladas, salvadas = congelar()
        print(f"congeladas ({len(congeladas)}):")
        for u in congeladas:
            print("   ", u)
        print(f"salvadas ({len(salvadas)}):")
        for u, motivo in salvadas:
            print(f"    {u}  <- {motivo}")
        return 0

    if orden == "descongelar":
        d = descongelar()
        print(f"descongeladas ({len(d)}):" if d else "no habia nada congelado")
        for u in d:
            print("   ", u)
        return 0

    if orden == "estado":
        e = estado()
        if not e:
            print("nada congelado")
        for u, s in e:
            print(f"    {u}  {s}")
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(_cli())
