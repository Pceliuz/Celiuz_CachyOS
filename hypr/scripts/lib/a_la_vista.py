#!/usr/bin/env python3
"""
hypr/scripts/lib/a_la_vista.py — ¿se ve alguna ventana ahora mismo, en
cualquier pantalla?

    a_la_vista.py        sale con 0 si NO se ve ninguna, 1 si se ve alguna (y
                         dice cuales), 2 si no lo puede saber

Lo usa lock.sh. El bloqueo enseña el fondo con `misc:session_lock_xray`, que
deja ver TODO lo que hay debajo; por eso salta antes a un escritorio vacio. Pero
eso no basta siempre, y las tres veces se vio una app a traves del bloqueo:
  - el vigilante del modo gaming te devolvia al escritorio del juego en
    milisegundos («a uno vacio no se va»): Minecraft detras del bloqueo, en la
    laptop de alguien que usa este repo (2026-10-20);
  - con DOS pantallas solo se vacia la que tiene el foco; la otra sigue
    enseñando sus ventanas;
  - una ventana FIJADA (`pin`) sale en todos los escritorios, el vacio incluido.

Se ve una ventana si esta en el escritorio activo de alguna pantalla (o en su
escritorio especial, si esta abierto), o si esta fijada.

TRES SALIDAS, como `hyprctl locked` en lock.sh: «no lo se» (2) NO es «no se ve
nada» (0). Quien llame trata el 2 como un si: mejor el fondo quieto que un
escritorio a la vista.
"""

import json
import subprocess
import sys


def _hyprctl(*args):
    r = subprocess.run(["hyprctl"] + list(args) + ["-j"], capture_output=True,
                       text=True, timeout=3, check=False)
    return json.loads(r.stdout)


def visibles(monitores, clientes):
    """Las ventanas que se ven: [(clase, escritorio)]."""
    activos = set()
    for m in monitores:
        activos.add((m.get("activeWorkspace") or {}).get("id"))
        especial = (m.get("specialWorkspace") or {}).get("id")
        if especial:
            activos.add(especial)
    activos.discard(None)
    salida = []
    for c in clientes:
        if c.get("mapped") is False or c.get("hidden"):
            continue
        ws = (c.get("workspace") or {}).get("id")
        if c.get("pinned") or ws in activos:
            salida.append((c.get("class") or c.get("title") or "?", ws))
    return salida


def main():
    try:
        monitores, clientes = _hyprctl("monitors"), _hyprctl("clients")
        if not isinstance(monitores, list) or not isinstance(clientes, list) or not monitores:
            raise ValueError("respuesta rara")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        print("no lo se: hyprctl no contesto bien")
        return 2
    lista = visibles(monitores, clientes)
    for clase, ws in lista:
        print("%s (escritorio %s)" % (clase, ws))
    return 1 if lista else 0


if __name__ == "__main__":
    sys.exit(main())
