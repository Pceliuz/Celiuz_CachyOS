#!/usr/bin/env python3
"""
remoto/sistema/sddm_conf.py — lo que estorba en /etc/sddm.conf para entrar desde el celular.

    sddm_conf.py RUTA      imprime el fichero arreglado (sale con 0), o nada si
                           no hay que tocarlo (1), o nada si NO SE DEBE (2)

NO escribe nada: lo usa `instalar.sh --remoto-sistema`, que guarda antes una
copia (/etc/sddm.conf.antes-celiuz-remoto) y pone el resultado con sudo. Corre
como el usuario: solo lee y transforma texto.

POR QUE (la laptop del usuario, 2026-10-21): el instalador de CachyOS deja en
/etc/sddm.conf

    [Autologin]
    Session=hyprland

sin User=, o sea un autologin APAGADO con la sesion SIN uwsm puesta. SDDM lee
/etc/sddm.conf DESPUES de /etc/sddm.conf.d/, asi que esa linea pisaba la que
escribe entrar.py, y al entrar desde el celular la sesion arrancaba sin uwsm
(sin ella fallan los lanzadores: lanzar.sh usa `uwsm app`). Se COMENTA, no se
borra, con una linea que explica quien y por que.

Lo que NO se toca: si [Autologin] tiene un User= de verdad, alguien tiene un
autologin puesto a proposito, y su Session= es suya (sale con 2, y el
instalador avisa). Tampoco [Theme] ni nada fuera de [Autologin].
"""

import sys

MARCA = "# Celiuz Remoto la comento: pisaba la sesion de entrar desde el celular (remoto/sistema/sddm_conf.py)"


def arreglar(texto):
    """(codigo, texto nuevo o None). 0 cambiado, 1 nada que hacer, 2 no se debe."""
    lineas = texto.splitlines(keepends=True)
    seccion = ""
    usuario = ""
    sesiones = []
    for i, linea in enumerate(lineas):
        limpia = linea.strip()
        if limpia.startswith("["):
            seccion = limpia
        elif seccion == "[Autologin]" and "=" in limpia and not limpia.startswith("#"):
            clave, _, valor = limpia.partition("=")
            clave = clave.strip()
            if clave == "User":
                usuario = valor.strip()
            elif clave == "Session":
                sesiones.append(i)
    if not sesiones:
        return 1, None
    if usuario:
        return 2, None
    for i in sesiones:
        fin = "\n" if lineas[i].endswith("\n") else ""
        lineas[i] = f"{MARCA}\n# {lineas[i].strip()}{fin}"
    return 0, "".join(lineas)


def main(argv):
    if len(argv) != 2:
        print("uso: sddm_conf.py RUTA", file=sys.stderr)
        return 3
    try:
        with open(argv[1], encoding="utf-8") as fh:
            texto = fh.read()
    except FileNotFoundError:
        return 1
    except OSError as e:
        print(f"sddm_conf: {e}", file=sys.stderr)
        return 3
    codigo, nuevo = arreglar(texto)
    if nuevo is not None:
        sys.stdout.write(nuevo)
    return codigo


if __name__ == "__main__":
    sys.exit(main(sys.argv))
