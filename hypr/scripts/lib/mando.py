#!/usr/bin/env python3
"""
hypr/scripts/lib/mando.py — leer el mando desde GTK, sin dependencias.

GTK 3 no sabe nada de mandos, y python-evdev no viene instalado. Pero el kernel
los expone en /dev/input/event* y leerlos es sencillo: eventos de 24 bytes
(tiempo, tipo, codigo, valor). Hace falta estar en el grupo `input`, igual que
`lib/teclas.py`; sin permiso no hay mando y todo sigue funcionando con teclado.

QUE ES UN MANDO
---------------
El que declara los botones A (BTN_SOUTH) y Start (BTN_START). No vale con
«tiene ejes» ni con «se llama joystick»: el teclado X820UItra de la PC del
autor se anuncia como joystick (CLAUDE.md, la trampa del mando fantasma), y el
microfono y el raton traen ejes. Medido el 2026-09-25: con esta regla, de todos
los dispositivos de la PC solo pasa el «Microsoft X-Box 360 pad».

LAS ACCIONES
------------
Se traducen a palabras que entiende quien lo use:
    izquierda derecha arriba abajo   cruceta o palanca izquierda
    aceptar (A)  atras (B)  x (X)  y (Y)
    anterior (LB)  siguiente (RB)  select  start  guia
La palanca repite al mantenerla, como una tecla.

CON `exclusivo=True` el mando es SOLO de quien lo lee (EVIOCGRAB): lo usa el
menu rapido, que se abre encima de un juego y sin esto cada A del menu seria
tambien una A en la partida. El kernel lo suelta solo al cerrar el
descriptor, asi que si el menu se cae el juego recupera el mando. Si el mismo mando aparece dos
veces (Steam puede crear uno virtual encima del de verdad), la misma accion en
menos de REBOTE segundos se cuenta una vez.
"""

import array
import fcntl
import glob
import os
import struct
import time

EV_KEY, EV_ABS = 1, 3
BTN_SOUTH, BTN_EAST, BTN_START = 0x130, 0x131, 0x13B
BOTONES = {
    0x130: "aceptar", 0x131: "atras",
    # Norte y oeste: xpad los ha llamado de dos formas segun la version del
    # kernel, asi que cuentan como X / Y sin prometer cual es cual.
    0x133: "x", 0x134: "y",
    0x136: "anterior", 0x137: "siguiente",
    0x13A: "select", 0x13B: "start", 0x13C: "guia",
    0x220: "arriba", 0x221: "abajo", 0x222: "izquierda", 0x223: "derecha",
}
ABS_X, ABS_Y, ABS_HAT0X, ABS_HAT0Y = 0, 1, 16, 17
UMBRAL = 0.55        # fraccion del recorrido de la palanca que cuenta como pulsar
REBOTE = 0.08
REPETIR_TRAS, REPETIR_CADA = 0.35, 0.14
EVENTO = struct.Struct("llHHi")


def _ioc(numero, tam):
    return (2 << 30) | (tam << 16) | (ord("E") << 8) | numero


def _bits(fd, tipo, cuantos):
    buf = array.array("B", [0] * ((cuantos + 7) // 8))
    fcntl.ioctl(fd, _ioc(0x20 + tipo, len(buf)), buf, True)
    return {i for i in range(cuantos) if buf[i // 8] >> (i % 8) & 1}


def _rango(fd, eje):
    buf = array.array("i", [0] * 6)
    fcntl.ioctl(fd, _ioc(0x40 + eje, 24), buf, True)
    return buf[1], buf[2]


def nombre(fd):
    buf = array.array("B", [0] * 256)
    try:
        fcntl.ioctl(fd, _ioc(0x06, 256), buf, True)
    except OSError:
        return ""
    return bytes(buf).split(b"\0")[0].decode("utf-8", "replace")


def es_mando(fd):
    try:
        teclas = _bits(fd, EV_KEY, 0x300)
    except OSError:
        return False
    return BTN_SOUTH in teclas and BTN_START in teclas


def buscar():
    """[(ruta, fd, nombre)] de los mandos conectados, abiertos sin bloquear."""
    hallados = []
    for ruta in sorted(glob.glob("/dev/input/event*")):
        try:
            fd = os.open(ruta, os.O_RDONLY | os.O_NONBLOCK)
        except OSError:
            continue
        if es_mando(fd):
            hallados.append((ruta, fd, nombre(fd)))
        else:
            os.close(fd)
    return hallados


class Mando:
    """Lee todos los mandos y llama a `al_pulsar(accion)`.

    Se engancha al bucle de GLib: `Mando(al_pulsar).empezar()`. `conectado`
    dice si hay alguno (para el aviso de la barra de arriba).
    """

    def __init__(self, al_pulsar, exclusivo=False):
        self.al_pulsar = al_pulsar
        self.exclusivo = exclusivo
        self.dispositivos = {}      # fd -> {"ruta", "rangos", "palanca": {eje: dir}}
        self.ultimo = {}            # accion -> momento (rebote)
        self.sostenida = None       # (accion, momento de la siguiente repeticion)
        self._vigias = {}

    @property
    def conectado(self):
        return bool(self.dispositivos)

    def empezar(self):
        from gi.repository import GLib
        self._GLib = GLib
        self._abrir()
        GLib.timeout_add_seconds(3, self._rebuscar)
        GLib.timeout_add(40, self._repetir)
        return self

    def _abrir(self):
        abiertas = {d["ruta"] for d in self.dispositivos.values()}
        for ruta, fd, _ in buscar():
            if ruta in abiertas:
                os.close(fd)
                continue
            rangos = {}
            for eje in (ABS_X, ABS_Y):
                try:
                    rangos[eje] = _rango(fd, eje)
                except OSError:
                    pass
            if self.exclusivo:
                try:
                    fcntl.ioctl(fd, (1 << 30) | (4 << 16) | (ord("E") << 8) | 0x90, 1)
                except OSError:
                    pass                # otro lo tiene cogido: se lee igual
            self.dispositivos[fd] = {"ruta": ruta, "rangos": rangos, "palanca": {}}
            self._vigias[fd] = self._GLib.io_add_watch(
                fd, self._GLib.IO_IN | self._GLib.IO_ERR | self._GLib.IO_HUP, self._leer)

    def _rebuscar(self):
        # Solo si no hay ninguno: abrir cada /dev/input cuesta (CLAUDE.md,
        # 4-11 ms los que no son teclados), y con un mando ya puesto sobra.
        if not self.dispositivos:
            self._abrir()
        return True

    def _cerrar(self, fd):
        self._GLib.source_remove(self._vigias.pop(fd, 0)) if fd in self._vigias else None
        self.dispositivos.pop(fd, None)
        try:
            os.close(fd)
        except OSError:
            pass

    def _emitir(self, accion):
        ahora = time.monotonic()
        if ahora - self.ultimo.get(accion, 0) < REBOTE:
            return
        self.ultimo[accion] = ahora
        self.al_pulsar(accion)

    def _leer(self, fd, condicion):
        if condicion & (self._GLib.IO_ERR | self._GLib.IO_HUP):
            self._cerrar(fd)
            return False
        try:
            datos = os.read(fd, EVENTO.size * 64)
        except BlockingIOError:
            return True
        except OSError:
            self._cerrar(fd)          # desenchufado
            return False
        disp = self.dispositivos.get(fd)
        if disp is None:
            return False
        for i in range(0, len(datos) - EVENTO.size + 1, EVENTO.size):
            _, _, tipo, codigo, valor = EVENTO.unpack_from(datos, i)
            if tipo == EV_KEY and valor == 1 and codigo in BOTONES:
                self._emitir(BOTONES[codigo])
            elif tipo == EV_ABS and codigo in (ABS_HAT0X, ABS_HAT0Y):
                if valor:
                    eje = ("izquierda", "derecha") if codigo == ABS_HAT0X else ("arriba", "abajo")
                    accion = eje[0] if valor < 0 else eje[1]
                    self._emitir(accion)
                    self.sostenida = (accion, time.monotonic() + REPETIR_TRAS)
                else:
                    self.sostenida = None
            elif tipo == EV_ABS and codigo in disp["rangos"]:
                self._palanca(disp, codigo, valor)
        return True

    def _palanca(self, disp, eje, valor):
        minimo, maximo = disp["rangos"][eje]
        centro, medio = (minimo + maximo) / 2.0, max(1.0, (maximo - minimo) / 2.0)
        fraccion = (valor - centro) / medio
        nombres = ("izquierda", "derecha") if eje == ABS_X else ("arriba", "abajo")
        ahora = None
        if fraccion <= -UMBRAL:
            ahora = nombres[0]
        elif fraccion >= UMBRAL:
            ahora = nombres[1]
        antes = disp["palanca"].get(eje)
        if ahora == antes:
            return
        disp["palanca"][eje] = ahora
        if ahora:
            self._emitir(ahora)
            self.sostenida = (ahora, time.monotonic() + REPETIR_TRAS)
        elif self.sostenida and self.sostenida[0] in nombres:
            self.sostenida = None

    def _repetir(self):
        if self.sostenida and time.monotonic() >= self.sostenida[1]:
            accion = self.sostenida[0]
            self.sostenida = (accion, time.monotonic() + REPETIR_CADA)
            self.ultimo.pop(accion, None)
            self._emitir(accion)
        return True


if __name__ == "__main__":
    for ruta, fd, n in buscar():
        print(ruta, n)
        os.close(fd)
