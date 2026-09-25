#!/usr/bin/env python3
"""
tests/herramientas/raton.py <espera> <dx> <dy> [boton] — ALT + clic + arrastre
con un raton virtual (uinput). boton 272 = izquierdo (defecto), 273 = derecho.

Se uso el 2026-09-25 para comprobar que en Lua los atajos de raton arrastran y
redimensionan aunque `hyprctl binds` diga `"mouse": false`: dentro de un
anidado se ata ALT + clic a hl.dsp.window.drag() (en la sesion de fuera SUPER +
clic ya lo coge la tuya), se enfoca la ventana del anidado, se pone el puntero
en su centro con `hyprctl dispatch movecursor` de la sesion de fuera, y esto
arrastra. Igual que teclas.py, los eventos van a la sesion de VERDAD.
"""
import fcntl, os, struct, sys, time
EV_SYN, EV_KEY, EV_REL = 0, 1, 2
fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
fcntl.ioctl(fd, 0x40045564, EV_KEY)
fcntl.ioctl(fd, 0x40045564, EV_REL)
for c in (56, 272, 273):              # KEY_LEFTALT, BTN_LEFT, BTN_RIGHT
    fcntl.ioctl(fd, 0x40045565, c)
for c in (0, 1):                      # REL_X, REL_Y
    fcntl.ioctl(fd, 0x40045566, c)
os.write(fd, struct.pack("80sHHHHi", b"raton-prueba", 3, 1, 2, 1, 0) + b"\0" * (64 * 4 * 4))
fcntl.ioctl(fd, 0x5501)
time.sleep(float(sys.argv[1]))
def ev(t, c, v): os.write(fd, struct.pack("llHHi", 0, 0, t, c, v))
def syn(): ev(EV_SYN, 0, 0)
dx, dy = int(sys.argv[2]), int(sys.argv[3])
BTN = int(sys.argv[4]) if len(sys.argv) > 4 else 272
ev(EV_KEY, 56, 1); syn(); time.sleep(0.15)
ev(EV_KEY, BTN, 1); syn(); time.sleep(0.15)
for _ in range(20):
    ev(EV_REL, 0, dx // 20); ev(EV_REL, 1, dy // 20); syn(); time.sleep(0.02)
time.sleep(0.2)
ev(EV_KEY, BTN, 0); syn(); time.sleep(0.1)
ev(EV_KEY, 56, 0); syn(); time.sleep(0.3)
fcntl.ioctl(fd, 0x5502)
