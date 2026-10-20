"""
remoto/servidor/celiuz_remoto/red.py — donde escucha el servicio.

Fase 1. Pendiente: aqui solo esta lo que tiene que hacer (ver remoto/DISEÑO.md
y remoto/PROTOCOLO.md).

- Escucha SOLO en la IP de Tailscale (tailscale ip -4), puerto 47110. Sin
  Tailscale no arranca: nunca cae a 0.0.0.0.
- El canal USB (127.0.0.1:47111) lo abre solo la app de la PC, unos minutos.
"""
