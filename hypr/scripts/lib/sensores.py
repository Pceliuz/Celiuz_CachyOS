#!/usr/bin/env python3
"""
hypr/scripts/lib/sensores.py

Que sensor mide la temperatura de la CPU en ESTA caja.

POR QUE EXISTE
--------------
El modulo `temperature` de la barra llevaba escrita a mano la ruta del sensor del
sobremesa del autor:

    "hwmon-path-abs": "/sys/devices/pci0000:00/0000:00:18.3/hwmon"

Eso es el k10temp de un Ryzen 5 5500, colgado de su bus PCI. En cualquier otra
maquina esa ruta NO EXISTE: en el portatil del propio autor (Intel i5-8250U) el
sensor bueno es `coretemp` y cuelga de otro sitio del arbol, asi que la barra se
quedaba sin poder leer la temperatura. Y lo mismo le pasa a quien clone el repo:
el numero que sale en su barra no es de su procesador, o directamente no sale.

No es un caso raro ni exotico — es que **cada familia de CPU nombra su sensor de
otra manera** (k10temp en AMD, coretemp en Intel, cpu_thermal en las ARM) y
cuelga de un sitio distinto del /sys. Escribir una ruta a mano solo puede valer
para una maquina.

POR QUE NO SIRVE EL NUMERO DE /sys/class/hwmon/hwmonN
----------------------------------------------------
Es lo primero que apetece usar, y esta mal: **ese numero se reparte por orden de
arranque de los modulos del kernel y cambia entre reinicios**. Hoy el coretemp es
hwmon3 y manana puede ser hwmon1, con lo que la barra pasaria a ensenar la
temperatura de la bateria sin avisar de nada.

Lo estable es la ruta del DISPOSITIVO, que es a donde apunta ese enlace:

    /sys/class/hwmon/hwmon3  ->  /sys/devices/platform/coretemp.0/hwmon/hwmon3

De ahi se devuelve la carpeta padre (`.../coretemp.0/hwmon`), que es justo lo que
waybar quiere en `hwmon-path-abs`: el la abre y entra en el primer `hwmonN` que
encuentra dentro. Esa ruta va por el bus o por el nombre de la plataforma, y esos
no dependen del orden de arranque.

POR QUE SE GENERA AL INSTALAR Y NO SE PREGUNTA EN CALIENTE
----------------------------------------------------------
Es la misma excepcion que lib/maquina.py, y por el mismo motivo: waybar lee su
JSON al arrancar y no sabe ejecutar un script para rellenar una clave. O sea que
el dato tiene que estar escrito en un fichero antes de que la barra exista.

Y se sostiene porque **el dato no cambia**: la CPU de una caja es la que es. No
se enchufa un procesador nuevo sin apagar el equipo, y si se cambia la placa hay
que volver a pasar `./instalar.sh`, que es el mismo trato que ya tienen el dock y
el perfil de teclado. Lo que NO se hace es dejarlo cableado en un fichero
versionado, que era justo el fallo.

DE DONDE SALE, en este orden:
  1. El `name` de cada /sys/class/hwmon/hwmonN, comparado con SENSORES_CPU. Es
     el nombre que el propio driver del kernel se pone, y es la respuesta buena.
  2. Dentro del elegido, la entrada `tempN_input` cuya etiqueta sea la del
     conjunto del encapsulado (`Tctl`, `Tdie`, `Package id 0`). Es la que
     representa «la CPU» y no un nucleo suelto, que sube y baja a saltos.
  3. Si no hay etiquetas, `temp1_input`, que es lo que traen los drivers que
     solo publican una.

Si no se reconoce ningun sensor, devuelve None a proposito y NO se inventa una
ruta: el instalador se calla la clave y waybar cae a su valor por defecto
(/sys/class/thermal/thermal_zone0). Un numero de procedencia desconocida en la
barra es peor que el valor por defecto, porque parece bueno.

USO DESDE LA TERMINAL
    sensores.py                 resumen de lo que hay
    sensores.py ruta            imprime lo que va en "hwmon-path-abs"
    sensores.py entrada         imprime lo que va en "input-filename"
    sensores.py --json          todo, para otro script

USO DESDE PYTHON
    import sensores
    sensores.cpu()              {'nombre', 'ruta', 'entrada', 'etiqueta',
                                 'grados', 'motivo'}  o None
"""

import glob
import json
import os
import sys

# Se mira por aqui, y no por /sys/devices, porque es el indice que el kernel
# mantiene de todos los sensores esten donde esten en el arbol.
HWMON = "/sys/class/hwmon"

# Los drivers que publican la temperatura del PROCESADOR, a proposito en orden
# de preferencia y no como un conjunto: en un AMD conviven k10temp y (si esta
# instalado) zenpower, y en algunos portatiles coretemp convive con sensores de
# la placa que tambien parecen de CPU.
#
#   k10temp     AMD, de Family 10h en adelante. Es el del sobremesa del autor.
#   zenpower    sustituto de k10temp en Ryzen; da lo mismo y algo mas.
#   coretemp    Intel. Es el del portatil del autor.
#   cpu_thermal / soc_thermal   placas ARM (Raspberry y similares).
SENSORES_CPU = ("k10temp", "zenpower", "coretemp", "cpu_thermal", "soc_thermal")

# Etiquetas de la entrada que mide el conjunto del encapsulado. Un `Core 0` sube
# y baja a saltos de 20 grados segun que hilo este trabajando; esta no.
ETIQUETAS_PAQUETE = ("tctl", "tdie", "package id 0", "cpu")


def _leer(ruta):
    """El contenido de un fichero de /sys, o None si no se puede leer.

    En /sys hay ficheros que existen y aun asi dan error al leerlos (un sensor
    que el firmware no contesta, permisos), asi que no basta con os.path.exists.
    """
    try:
        with open(ruta, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def _entrada_buena(carpeta):
    """(fichero, etiqueta) de la temperatura que representa a toda la CPU.

    Se prefiere la del encapsulado entero. Si el driver no pone etiquetas —hay
    varios que no—, se cae a temp1_input, que es la que publican todos.
    """
    entradas = sorted(glob.glob(os.path.join(carpeta, "temp*_input")))
    for entrada in entradas:
        etiqueta = _leer(entrada.replace("_input", "_label"))
        if etiqueta and etiqueta.strip().lower() in ETIQUETAS_PAQUETE:
            return os.path.basename(entrada), etiqueta.strip()
    if entradas:
        primera = entradas[0]
        return os.path.basename(primera), _leer(primera.replace("_input", "_label"))
    return None, None


def cpu():
    """El sensor de temperatura de la CPU de esta caja, o None si no se reconoce.

    Devuelve un diccionario con:
      nombre     el `name` del driver (k10temp, coretemp...)
      ruta       lo que va en "hwmon-path-abs": la carpeta ESTABLE del
                 dispositivo, no /sys/class/hwmon/hwmonN
      entrada    lo que va en "input-filename" (temp1_input y compania)
      etiqueta   como llama el driver a esa entrada, o None si no la etiqueta
      grados     la lectura de ahora mismo, para poder comprobarlo de un vistazo
      motivo     por que se ha elegido ese, para diagnosticar sin adivinar
    """
    encontrados = {}
    for enlace in sorted(glob.glob(os.path.join(HWMON, "hwmon*"))):
        nombre = _leer(os.path.join(enlace, "name"))
        if nombre and nombre not in encontrados:
            encontrados[nombre] = enlace

    for nombre in SENSORES_CPU:
        enlace = encontrados.get(nombre)
        if not enlace:
            continue
        entrada, etiqueta = _entrada_buena(enlace)
        if not entrada:
            continue   # el driver esta pero no publica ninguna temperatura

        # La carpeta del dispositivo, atravesando el enlace de /sys/class. El
        # padre y no el propio hwmonN: es lo que espera waybar, que entra sola
        # en el primer hwmonN que haya dentro.
        destino = os.path.realpath(enlace)
        ruta = os.path.dirname(destino)

        crudo = _leer(os.path.join(enlace, entrada))
        grados = round(int(crudo) / 1000) if crudo and crudo.lstrip("-").isdigit() else None

        return {
            "nombre": nombre,
            "ruta": ruta,
            "entrada": entrada,
            "etiqueta": etiqueta,
            "grados": grados,
            "motivo": (f"el driver «{nombre}» es el que publica la temperatura "
                       f"de este procesador" +
                       (f", y «{etiqueta}» es la del encapsulado entero"
                        if etiqueta else "")),
        }
    return None


def _resumen():
    d = cpu()
    print()
    if not d:
        print("    SENSOR DE CPU  ·  NO RECONOCIDO")
        print("      la barra caera al valor por defecto de waybar")
        print("      (/sys/class/thermal/thermal_zone0), que puede no ser la CPU")
        print()
        print("      lo que hay en esta caja:")
        for enlace in sorted(glob.glob(os.path.join(HWMON, "hwmon*"))):
            print(f"        {os.path.basename(enlace):<10} {_leer(os.path.join(enlace, 'name'))}")
        print()
        return
    print("    SENSOR DE CPU  ·  preguntado a /sys/class/hwmon")
    print(f"    ● {d['nombre']}   —   {d['motivo']}")
    print()
    print(f"      hwmon-path-abs = {d['ruta']}")
    print(f"      input-filename = {d['entrada']}"
          + (f"   ({d['etiqueta']})" if d["etiqueta"] else ""))
    if d["grados"] is not None:
        print(f"      ahora mismo marca {d['grados']}°C")
    print()


def main():
    orden = sys.argv[1] if len(sys.argv) > 1 else ""
    if orden in ("-h", "--help"):
        return print(__doc__.strip())
    if orden == "--json":
        return print(json.dumps(cpu(), indent=2, ensure_ascii=False))
    d = cpu()
    if orden == "ruta":
        return print(d["ruta"]) if d else sys.exit(1)
    if orden == "entrada":
        return print(d["entrada"]) if d else sys.exit(1)
    if orden:
        sys.exit(f"sensores: no entiendo «{orden}». Prueba --help")
    _resumen()


if __name__ == "__main__":
    main()
