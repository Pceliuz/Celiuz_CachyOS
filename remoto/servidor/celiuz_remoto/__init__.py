"""
remoto/servidor/celiuz_remoto — el servicio de Celiuz Remoto.

Un modulo por cosa que hace, y cada uno cuenta en su cabecera que le toca. El
porque de todo, en remoto/DISEÑO.md; lo que se dicen la app y el servidor, en
remoto/PROTOCOLO.md.
"""

import os
import sys

# La raiz del repo se saca de donde esta este fichero, nunca de ~/dotfiles (la
# regla del CLAUDE.md). realpath, y no abspath: se nos puede llamar por un enlace.
PAQUETE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.normpath(os.path.join(PAQUETE, "..", "..", ".."))
LIB = os.path.join(REPO, "hypr", "scripts", "lib")

# Para reutilizar lo que ya sabe el escritorio (hardware, sensores, hypr...).
if LIB not in sys.path:
    sys.path.insert(0, LIB)

VERSION_PROTOCOLO = 0
PUERTO_RED = 47110
PUERTO_USB = 47111
