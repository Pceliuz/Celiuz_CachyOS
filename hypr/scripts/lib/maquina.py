#!/usr/bin/env python3
"""
hypr/scripts/lib/maquina.py

En que clase de equipo estamos: portatil o sobremesa.

POR QUE EXISTE
--------------
Este repo se escribio en un sobremesa con un teclado Attack Shark X820 (ANSI de
75%, sin AltGr y sin la tecla `<>`), y de ahi salieron decisiones que ese teclado
NECESITA pero que en un portatil sobran. La mas cara es `kb_options = lv3:switch`
en conf/input.conf, que convierte el Ctrl DERECHO en AltGr.

El bloque `input {}` de Hyprland es global: se lo come TODO teclado conectado.
Asi que ese apano viajaba tambien al teclado interno del portatil, que si tiene
AltGr y si tiene la tecla `<>` — o sea que perdia el Ctrl derecho a cambio de
nada. Y lo mismo le pasa a cualquiera que clone este repo: se queda sin Ctrl
derecho por un teclado que no ha visto en su vida.

Aqui se pregunta UNA vez que clase de equipo hay, y el instalador carga (o no)
conf/teclado-laptop.conf con lo que solo tiene sentido en un portatil. Nadie
vuelve a escribir ajustes de portatil en un fichero que lee el sobremesa.

POR QUE ESTO SI SE GENERA AL INSTALAR, y pantalla.py no
------------------------------------------------------
pantalla.py se mide en caliente a proposito: los monitores cambian: conectas un
proyector, giras la pantalla, enchufas la tele. La CAJA no cambia. Un portatil no
amanece siendo un sobremesa, asi que preguntarlo en cada arranque no compra nada.

Y hay una razon tecnica encima: hyprlang no tiene condicionales. No existe forma
de escribir «carga esto solo si...» dentro de un .conf. La decision tiene que
tomarla alguien de fuera, y ese alguien es instalar.sh, que ya genera
conf/local.conf justamente para lo que es de esta maquina y de ninguna otra.

Consecuencia que conviene saber: si mueves el disco de un equipo a otro, hay que
volver a pasar `./instalar.sh`. Es el mismo trato que ya tiene el dock.

DE DONDE SALEN LOS DATOS, en este orden:
  1. /sys/class/dmi/id/chassis_type. Es lo que el fabricante grabo en la BIOS y
     es la respuesta buena cuando existe. Los codigos estan en las dos tablas de
     mas abajo: 8, 9, 10, 11, 14, 30, 31 y 32 son portatiles de una u otra forma;
     3, 4, 5, 6, 7, 13, 15, 16, 17, 23 y 24 son maquinas de las que no se mueven.
  2. Bateria y tapa (/sys/class/power_supply/BAT*, /proc/acpi/button/lid). Sirven
     cuando el DMI dice «Other» o «Unknown» —maquinas virtuales y placas que no
     rellenan el campo— y para corroborar el punto 1.
  3. Sobremesa. El ultimo recurso, y a proposito: da la config de HOY. Si nos
     equivocamos por ahi, no cambia nada de lo que ya funcionaba.

UNA BATERIA NO BASTA POR SI SOLA. Un sobremesa con un SAI conectado por USB
enseña un `/sys/class/power_supply/` con bateria dentro. Por eso la bateria solo
decide cuando el DMI no sabe, y aun asi se pide que haya TAPA tambien: un SAI no
tiene tapa.

USO DESDE LA TERMINAL
    maquina.py                  resumen de lo que hay
    maquina.py tipo             imprime `laptop` o `escritorio`
    maquina.py --json           todo, para otro script
    maquina.py --es-laptop      sin imprimir nada; sale 0 si es portatil

USO DESDE PYTHON
    import maquina
    maquina.es_laptop()         True / False
    maquina.detalle()           {'tipo', 'motivo', 'chasis', 'bateria', 'tapa'}
"""

import glob
import json
import os
import sys

# Los codigos de /sys/class/dmi/id/chassis_type, tal y como los define la
# especificacion SMBIOS (tabla 7.4.1). Solo se listan los que se han visto de
# verdad; cualquier otro cae en «no se sabe» y lo deciden bateria y tapa.
CHASIS_PORTATIL = {
    8: "Portable",
    9: "Laptop",
    10: "Notebook",
    11: "Hand Held",
    14: "Sub Notebook",
    30: "Tablet",
    31: "Convertible",
    32: "Detachable",
}

CHASIS_SOBREMESA = {
    3: "Desktop",
    4: "Low Profile Desktop",
    5: "Pizza Box",
    6: "Mini Tower",
    7: "Tower",
    13: "All in One",
    15: "Space-saving",
    16: "Lunch Box",
    17: "Main Server Chassis",
    23: "Rack Mount Chassis",
    24: "Sealed-case PC",
}

# Las rutas van en constantes y no escritas dentro de las funciones para que las
# pruebas puedan apuntarlas a un /sys de mentira y fingir un sobremesa, un
# portatil o una maquina virtual sin DMI. Sin esto, lo unico comprobable seria el
# equipo en el que se lanza la prueba.
DMI = "/sys/class/dmi/id"
POWER = "/sys/class/power_supply"
LID_PROC = "/proc/acpi/button/lid"
INPUT_SYS = "/sys/class/input"


def _leer(ruta):
    """El contenido de un fichero de /sys, o None si no se puede leer.

    Se traga los errores a proposito: en una maquina virtual media
    /sys/class/dmi no existe, y eso es un dato mas, no una averia.
    """
    try:
        with open(ruta) as f:
            return f.read().strip()
    except OSError:
        return None


def chasis():
    """(codigo, nombre) de lo que dice la BIOS, o (None, None) si no lo dice."""
    crudo = _leer(f"{DMI}/chassis_type")
    if crudo is None or not crudo.isdigit():
        return None, None
    codigo = int(crudo)
    nombre = CHASIS_PORTATIL.get(codigo) or CHASIS_SOBREMESA.get(codigo)
    return codigo, nombre


def hay_bateria():
    """True si hay alguna bateria de verdad.

    Se comprueba el `type` de cada fuente de alimentacion en vez de fiarse del
    nombre: el cargador se llama `ADP0` o `AC` segun el equipo, pero su type
    siempre es `Mains`. Asi no hay que adivinar nombres.
    """
    for fuente in glob.glob(f"{POWER}/*"):
        if _leer(f"{fuente}/type") == "Battery":
            return True
    return False


def hay_tapa():
    """True si el equipo declara una tapa que se abre y se cierra."""
    if glob.glob(f"{LID_PROC}/*"):
        return True
    # En kernels sin /proc/acpi, la tapa sale como un interruptor de input.
    for nombre in glob.glob(f"{INPUT_SYS}/input*/name"):
        if (_leer(nombre) or "").lower().startswith("lid switch"):
            return True
    return False


def detalle():
    """Que clase de equipo es esto, y por que lo creemos.

    El `motivo` no es adorno: cuando alguien reporte «me detecto mal», es lo
    primero que hay que mirar y ahorra toda la investigacion.
    """
    codigo, nombre = chasis()
    bateria, tapa = hay_bateria(), hay_tapa()

    if codigo in CHASIS_PORTATIL:
        tipo = "laptop"
        motivo = f"la BIOS dice que el chasis es «{nombre}» ({codigo})"
    elif codigo in CHASIS_SOBREMESA:
        tipo = "escritorio"
        motivo = f"la BIOS dice que el chasis es «{nombre}» ({codigo})"
    elif bateria and tapa:
        tipo = "laptop"
        motivo = ("la BIOS no dice que chasis es, pero hay bateria y tapa"
                  if codigo is None else
                  f"el chasis {codigo} no dice nada util, pero hay bateria y tapa")
    else:
        tipo = "escritorio"
        motivo = ("no hay ni bateria ni tapa" if not bateria else
                  "hay bateria pero no hay tapa: puede ser un SAI, no un portatil")

    return {"tipo": tipo, "motivo": motivo, "chasis": codigo,
            "chasis_nombre": nombre, "bateria": bateria, "tapa": tapa}


def es_laptop():
    return detalle()["tipo"] == "laptop"


def _resumen():
    d = detalle()
    print()
    print("    EQUIPO  ·  preguntado al DMI")
    print(f"    ● {d['tipo']}   —   {d['motivo']}")
    print()
    print(f"      bateria: {'si' if d['bateria'] else 'no'}"
          f"      tapa: {'si' if d['tapa'] else 'no'}")
    if d["tipo"] == "laptop":
        print("      se cargara conf/teclado-laptop.conf")
    else:
        print("      no se cargara nada de portatil")
    print()


def main():
    args = sys.argv[1:]
    orden = args[0] if args else ""

    if orden in ("-h", "--help"):
        return print(__doc__.strip())
    if orden == "--json":
        return print(json.dumps(detalle(), indent=2, ensure_ascii=False))
    if orden == "--es-laptop":
        sys.exit(0 if es_laptop() else 1)
    if orden == "tipo":
        return print(detalle()["tipo"])
    if orden:
        sys.exit(f"maquina: no entiendo «{orden}». Prueba --help")
    _resumen()


if __name__ == "__main__":
    main()
