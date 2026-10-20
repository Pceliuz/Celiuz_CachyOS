"""
remoto/servidor/celiuz_remoto/estado.py — el estado en tiempo real.

Fase 1. Pendiente: aqui solo esta lo que tiene que hacer (ver remoto/DISEÑO.md
y remoto/PROTOCOLO.md).

- Pregunta a lib/hardware.py y lib/sensores.py que tiene ESTE equipo, y solo
  manda eso (sin GPU dedicada no hay VRAM; sin bateria, bateria = null).
- CPU, RAM, disco y red con psutil. Cada segundo por el WebSocket /v0/vivo.
"""
