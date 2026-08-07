#!/usr/bin/env python3
"""
hypr/scripts/lib/canales.py

Donde vive el FIFO de ordenes de cada demonio, y de QUE SESION es.

POR QUE EXISTE
--------------
Los dos demonios del escritorio reciben ordenes por un FIFO en
`$XDG_RUNTIME_DIR`, y esa carpeta es **del usuario, no de la sesion**. O sea que
dos sesiones de Hyprland vivas a la vez —dos TTY, o un cambio rapido de usuario—
compartian el mismo fichero:

    $XDG_RUNTIME_DIR/waybar-autohide.fifo
    $XDG_RUNTIME_DIR/wallpaper-pause.fifo

Y compartir ese fichero no es «se molestan un poco»: es que **el escritorio deja
de responder a lo que le pides**. Cada demonio comprueba una vez por segundo que
el FIFO de la ruta sigue siendo el suyo y lo rehace si no, asi que los dos se lo
robaban en bucle; y un `SUPER+C` acababa donde le tocara. Lo mismo con las dos
lineas-tirador, el panel de calendario, el gestor del dock y —peor— las ordenes
`lock` y `unlock` de la pantalla de bloqueo, que son las que evitan que la barra
se lea por encima del bloqueo.

Con la firma de la instancia en el nombre, cada sesion tiene el suyo:

    $XDG_RUNTIME_DIR/waybar-autohide.<firma>.fifo

LA REGLA
--------
**Todo lo que sea de una SESION y viva en `$XDG_RUNTIME_DIR` lleva la firma en el
nombre.** Esa carpeta dura lo que dura la sesion del USUARIO, que puede ser mas
de una sesion grafica y sobrevive a cerrar sesion — que es justo como un demonio
huerfano acaba con el escritorio de otro (ver `waybar-autohide.py`).

QUE PASA SI NO HAY FIRMA
------------------------
`HYPRLAND_INSTANCE_SIGNATURE` la pone Hyprland a todo lo que lanza, asi que los
seis que escriben la tienen. Pero a mano desde un TTY o por ssh no esta, y ahi
hay que elegir: si solo hay UN canal de ese demonio, se usa ese —es lo que
cualquiera querria— y si hay varios NO se adivina, porque acertar la sesion
equivocada es peor que no hacer nada (mandarias `unlock` a la pantalla de bloqueo
de otra sesion). Sin firma y con varios, se devuelve una ruta que no existe: los
que escriben comprueban con `test -p` y fallan en silencio, que es lo correcto.

ESTO TIENE UN GEMELO EN SHELL
-----------------------------
`canales.sh` hace lo mismo para `lock.sh` y `barras.sh`. La convencion del nombre
esta escrita en dos idiomas a la fuerza, asi que `tests/unidad/canales.sh`
compara las dos implementaciones caso por caso y falla si se separan.
"""

import glob
import os
import stat

RUNTIME = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"


def firma():
    """La firma de la instancia de Hyprland en curso, o "" si no se sabe."""
    return os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or ""


def _del_tipo(ruta, ext):
    """Que el fichero sea de verdad lo que su extension promete."""
    try:
        modo = os.stat(ruta).st_mode
    except OSError:
        return False   # se lo llevaron entre el glob y el stat
    return stat.S_ISSOCK(modo) if ext == "sock" else stat.S_ISFIFO(modo)


def canal(nombre, ext="fifo"):
    """Ruta del canal de `nombre` para ESTA sesion.

    `nombre` es el del demonio ("waybar-autohide", "wallpaper-pause") o el de la
    pieza ("mpvpaper"). `ext` distingue un FIFO de ordenes de un socket de mpv;
    la regla del nombre es la misma para los dos, que es justo lo que se quiere:
    **nada de una sesion se llama igual en dos sesiones.**
    """
    sig = firma()
    if sig:
        return os.path.join(RUNTIME, f"{nombre}.{sig}.{ext}")

    # Sin firma. Si solo hay un canal de ese demonio, es ese; si hay varios, no
    # se adivina (ver la cabecera). Se exige que sea del TIPO que toca, no solo
    # que se llame asi: `echo x > ruta-sin-fifo` deja un fichero normal y sale
    # con 0, asi que la basura de esa trampa no debe contar como candidata.
    sueltos = sorted(f for f in glob.glob(os.path.join(RUNTIME, f"{nombre}.*.{ext}"))
                     if _del_tipo(f, ext))
    if len(sueltos) == 1:
        return sueltos[0]
    return os.path.join(RUNTIME, f"{nombre}.sin-sesion.{ext}")


def canal_barras():
    return canal("waybar-autohide")


def canal_fondo():
    return canal("wallpaper-pause")


def socket_mpv():
    """El socket IPC de mpvpaper de ESTA sesion.

    Lo abre mpvpaper con `--input-ipc-server` (ver wallpaper.sh) y por ahi le
    hablan el demonio de ahorro, la pantalla de bloqueo y CeliuzPaper. Tambien
    es lo que identifica a NUESTRO mpvpaper entre los de otras sesiones: su
    ruta sale en la linea de comandos del proceso, asi que sirve para matarlo
    sin recurrir a un `pkill -x mpvpaper` que se lleva por delante los ajenos.
    """
    return canal("mpvpaper", "sock")


if __name__ == "__main__":
    import sys

    verbos = {"barras": canal_barras, "fondo": canal_fondo, "mpv": socket_mpv}
    if len(sys.argv) != 2 or sys.argv[1] not in verbos:
        sys.exit(f"uso: {os.path.basename(sys.argv[0])} {{{'|'.join(verbos)}}}")
    print(verbos[sys.argv[1]]())
