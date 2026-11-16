#!/usr/bin/env python3
"""
hypr/scripts/grabar-portal.py — el selector que lanza el portal de Hyprland
(xdph) cuando un programa pide grabar o compartir la pantalla.

Lo pone hypr/xdph.conf (`custom_picker_binary`). Hace UNA cosa propia: si
grabar.sh acaba de encargar una ventana (lib/grabacion.py preseleccionar),
contesta con esa ventana sin preguntar nada. En cualquier otro caso —compartir
pantalla en una videollamada, OBS...— le pasa la pregunta, con los mismos
argumentos, al selector de siempre (hyprland-share-picker): para todo lo demas
el portal se comporta como si este fichero no existiera.

Por que no se puede fallar aqui: si este programa revienta, el portal no
recibe respuesta y la videollamada se queda sin poder compartir. Por eso todo
lo propio va dentro de un try, y lo que no sea el recado acaba SIEMPRE en el
selector de siempre.
"""

import os
import sys

AQUI = os.path.dirname(os.path.realpath(__file__))
SELECTOR_DE_SIEMPRE = "hyprland-share-picker"


def respuesta_encargada():
    try:
        sys.path.insert(0, os.path.join(AQUI, "lib"))
        import grabacion
        direccion = grabacion.tomar_recado()
        if not direccion:
            return None
        ident = grabacion.id_en_lista_del_portal(
            direccion, os.environ.get("XDPH_WINDOW_SHARING_LIST", ""))
        if ident is None:
            # La ventana se cerro entre elegirla y empezar: mejor preguntar
            # que grabar otra cosa.
            return None
        # Sin la «r» detras de [SELECTION]: esta respuesta es para ESTA
        # grabacion y no se guarda para restaurar la sesion despues.
        return "[SELECTION]/window:%s" % ident
    except Exception as e:  # noqa: BLE001 — aqui no se puede reventar
        print("grabar-portal: %s" % e, file=sys.stderr)
        return None


def main():
    respuesta = respuesta_encargada()
    if respuesta:
        print(respuesta, flush=True)
        return 0
    try:
        os.execvp(SELECTOR_DE_SIEMPRE, [SELECTOR_DE_SIEMPRE] + sys.argv[1:])
    except OSError as e:
        print("grabar-portal: no puedo lanzar %s: %s" % (SELECTOR_DE_SIEMPRE, e),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
