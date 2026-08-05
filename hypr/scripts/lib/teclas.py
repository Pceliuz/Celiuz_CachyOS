#!/usr/bin/env python3
"""teclas.py — preguntarle AL KERNEL que teclas estan pulsadas ahora mismo.

POR QUE EXISTE ESTO. El cambiador de escritorios (SUPER+TAB) tiene que saber si
sigues aguantando SUPER para decidir si ya has elegido. Suena a que deberia
bastar con escuchar el evento de soltar, y no basta: MEDIDO el 2026-08-04, en un
toque rapido ese evento NO LLEGA POR NINGUN LADO.

    - GTK no lo ve, porque la capa todavia no tenia el teclado: la ventana tarda
      ~185 ms en estar en pantalla y el toque se acaba antes.
    - El `bindr` de Hyprland tampoco lo ve. En el diario de la sesion real
      disparo 2 de 10 veces, y las dos fueron pulsando SUPER SOLA: cuando SUPER
      va en combo con TAB, que es el gesto de verdad, no dispara.

O sea que el evento de soltar se pierde entre dos sillas justo en el caso que
hay que arreglar. La unica fuente que no depende de quien tenga el foco es el
propio kernel: `EVIOCGKEY` devuelve el mapa de teclas pulsadas del dispositivo,
no una cola de eventos. Da igual que el teclado lo tenga otra ventana, el
compositor, o nadie.

Coste MEDIDO: 0,11-0,16 ms por consulta mirando solo los teclados de verdad.
Mirando todos los `/dev/input/event*` son 170 ms, porque los que no son teclados
(HDMI, audio) tardan entre 4 y 11 ms cada uno en abrirse. De ahi el filtro.

NO DEVUELVE UN BOOLEANO A SECAS, Y ES A PROPOSITO: devuelve None cuando no ha
podido mirar. Leer /dev/input pide estar en el grupo `input`, y este repo se usa
en mas de un equipo (ver la regla de oro del CLAUDE.md). Si en una maquina no se
puede leer y esto devolviera False, quien lo llama entenderia "ya la solto" y el
gesto se romperia entero. Con None, el que llama sabe que tiene que tirar del
camino de siempre.
"""

import fcntl
import glob
import os

KEY_LEFTMETA = 125
KEY_RIGHTMETA = 126

# El mapa se pide por bytes y la tecla mas alta que miramos es la 126, que cae en
# el byte 15. Con 16 basta y no se copia de mas.
_TAM = 16

# EVIOCGKEY(len) = _IOR('E', 0x18, len). Se arma a mano porque no hay ioctl.h en
# Python: direccion de lectura (2) << 30 | tamano << 16 | 'E' << 8 | numero.
_EVIOCGKEY = (2 << 30) | (_TAM << 16) | (ord("E") << 8) | 0x18

# EVIOCGBIT(EV_KEY, len): que teclas SABE mandar un dispositivo. Sirve para
# reconocer un teclado sin fiarse de como se llame. EV_KEY es 1.
_EVIOCGBIT_KEY = (2 << 30) | (_TAM << 16) | (ord("E") << 8) | (0x20 + 1)

_teclados = None


def bit(mapa, codigo):
    """¿Esta puesto el bit de esa tecla en el mapa que devuelve el kernel?

    El mapa viene por bytes y en cada uno los bits van del menos significativo al
    mas: la tecla 125 es el bit 5 del byte 15. Esta suelto en su propia funcion
    porque es lo mas facil de equivocar de todo el modulo y asi se puede probar
    sin necesidad de un teclado de verdad (ver tests/unidad/teclas.sh).
    """
    indice = codigo // 8
    if indice >= len(mapa):
        return False
    return bool(mapa[indice] >> (codigo % 8) & 1)


def _tiene_meta(fd):
    """True si este dispositivo sabe mandar la tecla SUPER (o sea, es un teclado)."""
    try:
        caps = bytearray(_TAM)
        fcntl.ioctl(fd, _EVIOCGBIT_KEY, caps)
        return bit(caps, KEY_LEFTMETA)
    except OSError:
        return False


def teclados():
    """Los dispositivos de teclado legibles, sin repetir.

    Primero por `by-path/*-kbd`, que es instantaneo (son enlaces, no hay que
    abrir nada) y en esta maquina da exactamente los tres teclados buenos.

    El rastreo completo es el respaldo para cuando no existan esos enlaces, y va
    detras a proposito: cuesta ~170 ms porque hay que abrir todos los
    dispositivos para preguntarles que teclas tienen. Se calcula UNA vez por
    proceso; estos scripts viven unos cientos de milisegundos, asi que no da
    tiempo a que la lista envejezca.
    """
    global _teclados
    if _teclados is not None:
        return _teclados

    vistos = []
    for enlace in glob.glob("/dev/input/by-path/*-kbd"):
        # Un mismo teclado suele traer varios enlaces by-path (el X820 anuncia
        # ademas dispositivos -consumer-control y -system-control aparte), asi
        # que se resuelve a su ruta real y se quitan los repetidos.
        real = os.path.realpath(enlace)
        if real not in vistos and os.access(real, os.R_OK):
            vistos.append(real)

    if not vistos:
        for ruta in glob.glob("/dev/input/event*"):
            try:
                fd = os.open(ruta, os.O_RDONLY | os.O_NONBLOCK)
            except OSError:
                continue
            try:
                if _tiene_meta(fd):
                    vistos.append(ruta)
            finally:
                os.close(fd)

    _teclados = vistos
    return _teclados


def pulsada(*codigos):
    """True / False / None — si alguna de esas teclas esta pulsada ahora mismo.

    None significa "no he podido mirar" (sin permiso sobre /dev/input, o sin
    ningun teclado a la vista), y NO es lo mismo que False. Ver la cabecera.
    """
    mirado = False
    for ruta in teclados():
        try:
            fd = os.open(ruta, os.O_RDONLY | os.O_NONBLOCK)
        except OSError:
            continue
        try:
            mapa = bytearray(_TAM)
            fcntl.ioctl(fd, _EVIOCGKEY, mapa)
        except OSError:
            continue
        finally:
            os.close(fd)
        mirado = True
        for codigo in codigos:
            if bit(mapa, codigo):
                return True
    return False if mirado else None


def super_pulsada():
    """True / False / None — si SUPER (cualquiera de las dos) sigue pulsada."""
    return pulsada(KEY_LEFTMETA, KEY_RIGHTMETA)


if __name__ == "__main__":
    import sys
    estado = super_pulsada()
    print({True: "pulsada", False: "suelta",
           None: "no se puede saber (sin acceso a /dev/input)"}[estado])
    print("teclados:", ", ".join(teclados()) or "ninguno")
    sys.exit(0 if estado is not None else 1)
