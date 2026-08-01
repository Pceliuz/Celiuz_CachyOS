#!/usr/bin/env python3
"""teclado.py — en que distribucion de teclado estas, y como cambiarla.

POR QUE EXISTE. Desde el teclado Attack Shark X820 (ANSI de 75%) la sesion lleva
DOS distribuciones a la vez, declaradas en conf/input.conf:

    #0  us(altgr-intl)  — lo impreso en la tecla es lo que sale
    #1  latam           — la `ñ` y las tildes donde las tenias siempre

El problema de tener dos no es cambiar de una a otra: es no saber en cual estas
hasta que escribes mal. Por eso todo cambio AVISA por notificacion, y por eso al
arrancar la sesion se manda un aviso de cortesia diciendo con cual empiezas.

Uso:
    teclado.py estado     imprime la activa en una linea (para la barra o el
                          asistente); sin tocar nada
    teclado.py cambiar    pasa a la siguiente y avisa      (bind SUPER+DEL)
    teclado.py avisar     solo avisa de la que hay puesta  (exec-once al inicio)

Las notificaciones se mandan con la etiqueta `x-canonical-private-synchronous`,
que mako entiende como "sustituye a la anterior de esta etiqueta": si pulsas
SUPER+DEL cuatro veces seguidas no se te apilan cuatro avisos, se reescribe uno.
"""
import json
import subprocess
import sys
import time

# Nombre bonito y frase de recordatorio, buscados por trozo del nombre que
# reporta Hyprland en `active_keymap`, que es el nombre largo de xkb.
#
# OJO con los trozos: el nombre real que devuelve esta version es
# "English (intl., with AltGr dead keys)" — SIN el "US" que uno esperaria de la
# variante `us(altgr-intl)`. Buscar "English (US" no casaba con nada y el aviso
# habria salido con el nombre crudo de xkb. Comprobado con `hyprctl devices`.
#
# La frase no es decorativa: es lo unico que hay que recordar de cada una.
DISTRIBUCIONES = [
    ("Latin American", "Latinoamericano",
     "La <b>ñ</b> y las tildes, donde estan impresas.\n"
     "Sin <b>&lt;</b> ni <b>&gt;</b>: no existen en este teclado."),
    ("English", "Ingles US",
     "Lo que dice la tecla es lo que sale.\n"
     "<b>ñ</b> y tildes con <b>Ctrl derecho</b> (AltGr)."),
]

DESCONOCIDA = ("Teclado", "Distribucion no reconocida")
ETIQUETA = "teclado"          # para que un aviso sustituya al anterior
ESPERA_MAKO = 15              # segundos como mucho esperando al demonio


def _hyprctl(*args, json_=False):
    orden = ["hyprctl"] + (["-j"] if json_ else []) + list(args)
    salida = subprocess.run(orden, capture_output=True, text=True).stdout
    return json.loads(salida) if json_ else salida.strip()


def activa():
    """(nombre_bonito, recordatorio) de la distribucion puesta ahora mismo.

    Se pregunta por el teclado MAIN y no por el primero de la lista: en esta
    sesion hay siete teclados a ojos de Hyprland (el raton, el microfono, el
    boton de encendido... todos anuncian teclas), y solo uno es el de verdad.
    """
    teclados = _hyprctl("devices", json_=True)["keyboards"]
    principal = next((t for t in teclados if t.get("main")), None) or teclados[0]
    nombre_xkb = principal.get("active_keymap", "")
    for trozo, bonito, recordatorio in DISTRIBUCIONES:
        if trozo in nombre_xkb:
            return bonito, recordatorio
    return nombre_xkb or DESCONOCIDA[0], DESCONOCIDA[1]


def avisar(titulo, cuerpo, milisegundos):
    subprocess.run([
        "notify-send",
        "--app-name=Teclado",
        "--icon=input-keyboard",
        f"--expire-time={milisegundos}",
        f"--hint=string:x-canonical-private-synchronous:{ETIQUETA}",
        titulo, cuerpo,
    ])


def esperar_a_mako():
    """No mandar el aviso de arranque antes de que haya quien lo reciba.

    `exec-once` no garantiza orden: esta linea y el `systemctl --user start
    mako` de autostart.conf se lanzan a la vez. Si mako aun no ha cogido
    org.freedesktop.Notifications, notify-send se queda esperando a un servicio
    que no esta y el aviso se pierde en silencio — que es justo el fallo que
    este script existe para no tener.
    """
    limite = time.monotonic() + ESPERA_MAKO
    while time.monotonic() < limite:
        listo = subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet", "mako"]
        ).returncode == 0
        if listo:
            return True
        time.sleep(0.3)
    return False


def main():
    orden = sys.argv[1] if len(sys.argv) > 1 else "estado"

    if orden == "estado":
        nombre, _ = activa()
        print(nombre)

    elif orden == "cambiar":
        # `all` y no el teclado principal a secas: el raton tambien manda teclas
        # (sus botones laterales), y si se quedara en otra distribucion serian
        # dos verdades distintas en la misma sesion.
        _hyprctl("switchxkblayout", "all", "next")
        nombre, recordatorio = activa()
        avisar(f"Teclado: {nombre}", recordatorio, 2500)

    elif orden == "avisar":
        esperar_a_mako()
        nombre, recordatorio = activa()
        avisar(f"Teclado: {nombre}",
               f"{recordatorio}\n<i>SUPER+DEL para cambiar.</i>", 6000)

    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
