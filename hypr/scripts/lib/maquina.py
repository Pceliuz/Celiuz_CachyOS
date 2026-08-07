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
    maquina.py teclado          imprime `completo` o `sin-altgr`
    maquina.py layout           imprime lo que debe valer `kb_layout` aqui
    maquina.py variante         imprime lo que debe valer `kb_variant` aqui
    maquina.py --json           todo, para otro script
    maquina.py --es-laptop      sin imprimir nada; sale 0 si es portatil

USO DESDE PYTHON
    import maquina
    maquina.es_laptop()         True / False
    maquina.detalle()           {'tipo', 'motivo', 'chasis', 'bateria', 'tapa'}
    maquina.perfil_teclado()    {'perfil', 'motivo', 'kb_options', 'conf'}
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
# La distribucion que se eligio al instalar el sistema. La escribe el instalador
# de la distro y la mantiene `localectl`; se lee el fichero y no `localectl`
# porque es un dato quieto y no merece lanzar un proceso.
VCONSOLE = "/etc/vconsole.conf"


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


# --- Que trato necesita el teclado -------------------------------------------
#
# El perfil «completo» es el de un teclado que trae TODAS sus teclas: AltGr y la
# `<>` de la izquierda. Con eso no hay que inventarse un tercer nivel en ningun
# sitio, y el Ctrl derecho se queda siendo Ctrl.
#
# El perfil «sin-altgr» es el del teclado del autor (Attack Shark X820, ANSI de
# 75%): no tiene AltGr, asi que el tercer nivel hay que sacarlo de donde se
# pueda, y de ahi `kb_options = lv3:switch` en conf/input.conf. El coste es real
# —el Ctrl derecho deja de ser Ctrl— y solo compensa si te falta la tecla.
PERFIL_COMPLETO = "completo"
PERFIL_SIN_ALTGR = "sin-altgr"

# La distribucion del autor, que es la del sobremesa y la de siempre: us con la
# variante internacional delante y latam detras para escribir en espanol con la
# memoria muscular de siempre. Ver conf/input.conf.
LAYOUT_AUTOR = "us,latam"
VARIANTE_AUTOR = "altgr-intl,"


def distribucion_del_sistema():
    """(layout, variante) que se eligio al instalar el sistema, o (None, None).

    Sale de /etc/vconsole.conf (XKBLAYOUT y XKBVARIANT), que es lo que contesto
    el usuario cuando el instalador de la distro le pregunto por su teclado.
    """
    datos = {}
    try:
        with open(VCONSOLE, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if linea.startswith("#") or "=" not in linea:
                    continue
                clave, valor = linea.split("=", 1)
                datos[clave.strip()] = valor.strip().strip('"').strip("'")
    except OSError:
        return None, None
    return datos.get("XKBLAYOUT") or None, datos.get("XKBVARIANT") or ""


def perfil_teclado():
    """Que perfil de teclado le toca a esta caja, y por que.

    POR QUE SE DECIDE POR LA CAJA Y NO MIRANDO EL TECLADO. Lo honesto seria
    preguntar si hay alguna tecla AltGr conectada; se puede, leyendo las
    capacidades en /sys/class/input. Pero `kb_options` vive en el bloque
    `input {}` de hyprlang, que es texto en un fichero y se lee al arrancar: un
    dato que cambia al enchufar o desenchufar un teclado NO se puede cablear
    ahi, y es justo lo que prohibe la regla del CLAUDE.md. La caja, en cambio,
    no cambia. Asi que se decide por el chasis, igual que el resto de este
    modulo, y quien enchufe un teclado raro tiene la linea a mano y comentada.

    EL LIMITE, dicho claro: un SOBREMESA con un teclado normal de 105 teclas
    tampoco necesita el apaño, y aun asi se lo lleva, porque el sobremesa es el
    caso por defecto y ahi el repo conserva la config del autor. Si te pasa,
    la solucion es una linea: `kb_options =` en conf/input.conf.

    Y LO MISMO CON LA DISTRIBUCION, que es lo que decide si las teclas dan lo
    que tienen escrito encima. El repo trae `us,latam` porque el teclado del
    autor esta serigrafiado en us; en un portatil eso es casi siempre falso, y
    entonces la `ñ`, los acentos y los simbolos salen donde no toca.

    En un portatil SI se puede saber cual es, y la fuente es /etc/vconsole.conf:
    lo que el usuario contesto cuando el instalador de la distro le pregunto por
    su teclado. En un portatil eso es de fiar porque **estaba tecleando en el
    teclado interno mientras respondia**.

    OJO, Y ES LA TRAMPA DE TODO ESTO: en un SOBREMESA esa misma fuente miente.
    La del autor dice `XKBLAYOUT=latam` y su teclado es un ANSI us — eligio
    latam al instalar y luego cambio de teclado, que es lo normal en una torre.
    Por eso el sobremesa NO mira vconsole y se queda con la del autor: deducirlo
    de ahi arreglaria el portatil y romperia la PC.

    Devuelve un diccionario con:
      perfil      «completo» o «sin-altgr»
      motivo      por que se ha decidido eso (para diagnosticar sin adivinar)
      kb_options  lo que deberia valer `kb_options` en esta caja
      kb_layout   lo que deberia valer `kb_layout`, con la de esta caja delante
      kb_variant  la variante de cada una, en el mismo orden
      conf        el fichero que lo aplica, o None si no hace falta ninguno
    """
    d = detalle()
    if d["tipo"] == "laptop":
        sistema, variante = distribucion_del_sistema()
        # La segunda distribucion es la del autor, para poder alternar con
        # SUPER+DEL: hay atajos y juegos que dan por hecho un teclado us. Si el
        # sistema ya dice us, esto queda igual que estaba y no se toca nada.
        if sistema and sistema != "us":
            layout = f"{sistema},us"
            varian = f"{variante},altgr-intl"
            porque = (f"el sistema se instalo con el teclado «{sistema}», y en "
                      f"un portatil eso es de fiar porque se respondio tecleando "
                      f"en el teclado interno")
        else:
            layout, varian = LAYOUT_AUTOR, VARIANTE_AUTOR
            porque = ("no hay ninguna distribucion apuntada en /etc/vconsole.conf, "
                      "o ya es «us»: se deja la de siempre"
                      if not sistema else
                      "el sistema ya se instalo con «us»: se deja la de siempre")
        return {
            "perfil": PERFIL_COMPLETO,
            "motivo": ("es un portatil (" + d["motivo"] + "), y el teclado "
                       "interno de un portatil tiene AltGr y tecla «<>»"),
            "kb_options": "",
            "kb_layout": layout,
            "kb_variant": varian,
            "motivo_layout": porque,
            "conf": "conf/teclado-laptop.conf",
        }
    return {
        "perfil": PERFIL_SIN_ALTGR,
        "motivo": ("es un sobremesa (" + d["motivo"] + "), asi que se deja la "
                   "config del autor: teclado ANSI de 75% sin AltGr"),
        "kb_options": "lv3:switch",
        "kb_layout": LAYOUT_AUTOR,
        "kb_variant": VARIANTE_AUTOR,
        "motivo_layout": ("es un sobremesa: /etc/vconsole.conf no dice cual es "
                          "el teclado que hay enchufado AHORA, asi que no se usa"),
        "conf": None,
    }


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
    t = perfil_teclado()
    print(f"    TECLADO  ·  perfil «{t['perfil']}»")
    print(f"      kb_options = {t['kb_options'] or '(vacio: el Ctrl derecho sigue siendo Ctrl)'}")
    print(f"      {t['motivo']}")
    print()
    print(f"      kb_layout  = {t['kb_layout']}   (la primera es la que arranca activa)")
    print(f"      kb_variant = {t['kb_variant']}")
    print(f"      {t['motivo_layout']}")
    print()


def main():
    args = sys.argv[1:]
    orden = args[0] if args else ""

    if orden in ("-h", "--help"):
        return print(__doc__.strip())
    if orden == "--json":
        todo = dict(detalle(), teclado=perfil_teclado())
        return print(json.dumps(todo, indent=2, ensure_ascii=False))
    if orden == "--es-laptop":
        sys.exit(0 if es_laptop() else 1)
    if orden == "tipo":
        return print(detalle()["tipo"])
    if orden == "motivo":
        return print(detalle()["motivo"])
    if orden == "teclado":
        return print(perfil_teclado()["perfil"])
    if orden == "layout":
        return print(perfil_teclado()["kb_layout"])
    if orden == "variante":
        return print(perfil_teclado()["kb_variant"])
    if orden:
        sys.exit(f"maquina: no entiendo «{orden}». Prueba --help")
    _resumen()


if __name__ == "__main__":
    main()
