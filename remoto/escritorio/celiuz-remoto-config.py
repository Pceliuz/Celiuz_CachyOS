#!/usr/bin/env python3
"""
remoto/escritorio/celiuz-remoto-config.py — la app de la PC de Celiuz Remoto.

Fase 1. Pendiente. Es la pantalla 9 de las maquetas: una ventana GTK, como
CeliuzPaper, con el CSS de lib/panel_estilo.py (la paleta del escritorio).

Lo que hara:
  - detectar el celular conectado por cable (servidor/celiuz_remoto/adb.py) y
    guiar la «Depuracion USB» si no esta;
  - instalarle la app y emparejarlo: crear AQUI su contraseña (nunca en el
    celular) y elegir que puede hacer (estado y apagar, apps, archivos,
    terminal);
  - renovar el pase de 24 h (cable + contraseña);
  - listar los telefonos con su pase y su ultimo latido, y revocarlos;
  - el interruptor general del servicio, y el aviso «¿te robaron el celular?»
    con el camino a la consola de Tailscale.
"""

import sys

if __name__ == "__main__":
    print("La app de la PC de Celiuz Remoto todavia no existe (fase 1).", file=sys.stderr)
    sys.exit(2)
