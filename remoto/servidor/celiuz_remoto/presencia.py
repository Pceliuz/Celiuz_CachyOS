"""
remoto/servidor/celiuz_remoto/presencia.py — ¿hay una PERSONA delante de la PC?

Fase 4. Pendiente: aqui solo esta lo que tiene que hacer (ver remoto/DISEÑO.md
y remoto/PROTOCOLO.md).

- Si: teclado o raton recientes (ext-idle-notify, lo mismo que mide hypridle),
  o un inhibidor de inactividad activo (un video reproduciendose: viendo anime
  no se toca el raton).
- No: una descarga o un render. Eso no es una persona.
- Tres salidas, como hyprctl locked en lock.sh: si / no / no lo se. «No lo se»
  NO es «no hay nadie».
"""
