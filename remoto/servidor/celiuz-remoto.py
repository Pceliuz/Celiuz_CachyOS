#!/usr/bin/env python3
"""
remoto/servidor/celiuz-remoto.py — el servicio de Celiuz Remoto.

    celiuz-remoto.py revisar          que le falta a este equipo para el remoto
    celiuz-remoto.py rutas            donde guarda cada cosa (fuera del repo)
    celiuz-remoto.py servir           el servicio                   (fase 1, pendiente)
    celiuz-remoto.py dispositivos     telefonos emparejados         (fase 1, pendiente)
    celiuz-remoto.py revocar <id>     quitar un telefono            (fase 1, pendiente)

En construccion. El diseño, en remoto/DISEÑO.md.
"""

import argparse
import importlib.util
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import celiuz_remoto  # noqa: E402,F401  (pone hypr/scripts/lib en el path)
from celiuz_remoto import rutas  # noqa: E402

# (que, como se mira, para que, paquete de Arch). Solo se mira si EXISTE: nada
# de esto arranca, conecta ni toca la red.
NECESIDADES = [
    ("tailscale", "programa", "la red entre el celular y la PC", "tailscale"),
    ("aiohttp", "modulo", "el servidor (HTTP y WebSocket)", "python-aiohttp"),
    ("psutil", "modulo", "CPU, RAM, disco y red", "python-psutil"),
    ("adb", "programa", "instalar la app y emparejar por cable", "android-tools"),
]


def _hay(nombre, clase):
    if clase == "programa":
        return shutil.which(nombre) is not None
    return importlib.util.find_spec(nombre) is not None


def revisar():
    faltan = []
    filas = []
    for nombre, clase, para, paquete in NECESIDADES:
        ok = _hay(nombre, clase)
        filas.append({"que": nombre, "para": para, "paquete": paquete, "hay": ok})
        if not ok:
            faltan.append(paquete)
    return filas, faltan


def cmd_revisar(args):
    filas, faltan = revisar()
    if args.json:
        print(json.dumps({"necesidades": filas, "faltan": faltan}, ensure_ascii=False, indent=2))
    else:
        for f in filas:
            marca = "ok   " if f["hay"] else "FALTA"
            print(f"  {marca} {f['que']:<10} {f['para']}")
        if faltan:
            print(f"\n  Para instalarlo: sudo pacman -S {' '.join(faltan)}")
        else:
            print("\n  No falta nada.")
    # Que falte algo no es un error de este programa: es la respuesta.
    return 0


def cmd_rutas(args):
    todas = rutas.todas()
    if args.json:
        print(json.dumps(todas, ensure_ascii=False, indent=2))
    else:
        for clave, ruta in todas.items():
            print(f"  {clave:<13} {ruta}")
    return 0


def cmd_pendiente(args):
    print(f"«{args.orden}» todavia no existe: es de la fase 1 (ver remoto/DISEÑO.md).",
          file=sys.stderr)
    return 2


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="celiuz-remoto.py",
        description="El servicio de Celiuz Remoto (en construccion).")
    sub = p.add_subparsers(dest="orden", required=True)

    s = sub.add_parser("revisar", help="que le falta a este equipo")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_revisar)

    s = sub.add_parser("rutas", help="donde guarda cada cosa")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_rutas)

    for orden in ("servir", "dispositivos"):
        sub.add_parser(orden, help="(fase 1, pendiente)").set_defaults(func=cmd_pendiente)
    s = sub.add_parser("revocar", help="(fase 1, pendiente)")
    s.add_argument("id")
    s.set_defaults(func=cmd_pendiente)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
