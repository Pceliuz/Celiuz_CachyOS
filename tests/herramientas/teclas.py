#!/usr/bin/env python3
"""
tests/herramientas/teclas.py <espera> <combo>... — pulsa teclas DE VERDAD con un
teclado virtual (uinput), para probar atajos y menus sin tocar el teclado.

    python3 tests/herramientas/teclas.py 1.0 super+shift+v sleep0.5 ctrl+f esc

OJO: las teclas van a la sesion de VERDAD (a la ventana con el foco), no a un
anidado. Hace falta poder escribir en /dev/uinput (en CachyOS el usuario de la
sesion tiene ACL). Se uso el 2026-09-25 para probar el menu del portapapeles
(Ctrl+F sale de fuzzel con 10, Ctrl+G con 11, Ctrl+D con 12).
"""
import fcntl, os, struct, sys, time

K = {"esc": 1, "enter": 28, "ctrl": 29, "shift": 42, "alt": 56, "down": 108,
     "up": 103, "delete": 111, "f": 33, "g": 34, "d": 32, "a": 30, "b": 48,
     "c": 46, "super": 125, "p": 25, "v": 47, "1": 2, "2": 3, "x": 45}
fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
fcntl.ioctl(fd, 0x40045564, 1)          # EV_KEY
for c in range(1, 200):
    fcntl.ioctl(fd, 0x40045565, c)
dev = struct.pack("80sHHHHi", b"teclas-prueba", 3, 1, 1, 1, 0) + b"\0" * (64 * 4 * 4)
os.write(fd, dev)
fcntl.ioctl(fd, 0x5501)
time.sleep(float(sys.argv[1]))

def ev(t, c, v):
    os.write(fd, struct.pack("llHHi", 0, 0, t, c, v))

for combo in sys.argv[2:]:
    if combo.startswith("sleep"):
        time.sleep(float(combo[5:])); continue
    ks = [K[x] for x in combo.split("+")]
    for k in ks:
        ev(1, k, 1); ev(0, 0, 0); time.sleep(0.02)
    for k in reversed(ks):
        ev(1, k, 0); ev(0, 0, 0); time.sleep(0.02)
    time.sleep(0.25)
time.sleep(0.2)
fcntl.ioctl(fd, 0x5502)
