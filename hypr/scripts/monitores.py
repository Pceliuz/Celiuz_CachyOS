#!/usr/bin/env python3
"""
~/dotfiles/hypr/scripts/monitores.py

A cada pantalla, el refresco MAS ALTO que admita a su resolucion nativa.

POR QUE HACE FALTA UN SCRIPT PARA ESTO
--------------------------------------
Hyprland tiene cuatro palabras para el modo de un monitor, y NINGUNA pide lo
que uno quiere de verdad. El wiki lo dice tal cual: «Predefined modes cannot be
combined; only one can be selected».

    preferred   el modo que declara el EDID. Es el que hay puesto en
                conf/monitors.conf, y es lo unico portable... pero un monitor de
                100 Hz suele declarar 60 como preferido: los refrescos altos
                viven en los modos extendidos.
    highrr      el refresco mas alto, MIRANDO SOLO EL REFRESCO. Se probo el
                2026-08-13 y es una trampa: el televisor de las pruebas anuncia
                800x600@60.32, que le gana en refresco a su 1920x1080@60.00, asi
                que lo dejaba en 800x600.
    highres     la resolucion mas alta, y el refresco queda SIN especificar.
    maxwidth    la mas ancha. Lo mismo.

O sea que «la resolucion nativa Y el refresco mas alto a esa resolucion» no se
puede pedir. Lo pidieron en hyprwm/Hyprland#8758 y se cerro como «not planned».

Pero el dato SI esta: `hyprctl monitors -j` trae `availableModes` con la lista
entera. Elegir bien es aritmetica sobre esa lista —agrupar por resolucion,
quedarse con la de mas pixeles y dentro de ella con el refresco mayor—, y eso es
todo lo que hace este fichero.

LO QUE NO HACE, Y ES A PROPOSITO
--------------------------------
NO toca la escala. La escala buena no se deduce del EDID porque depende de la
DISTANCIA a la que miras: el televisor de esta casa son 1390 mm para 1920
pixeles (~35 DPI, escala 1.5 a distancia de sofa) y un monitor de 24" son ~92
DPI a escala 1, y ningun dato del EDID sabe cual de los dos estas mirando. Eso
sigue en conf/personal.conf, donde se pone a mano una vez y se acierta siempre.

NO mueve nada. Se conserva la posicion y la escala que la pantalla ya tenga, asi
que esto no reordena un escritorio de dos pantallas ni deshace el `auto-right`
de conf/monitors.conf: solo sube el refresco donde se pueda.

Y NO PISA LO TUYO. Si nombras una salida en conf/personal.conf o en
conf/local.conf, este script se la salta entera. Es la regla de capas del repo:
en hyprlang gana el ultimo, y personal.conf se carga el ultimo de todos.

USO
---
    monitores.py            aplica lo que haga falta y calla si no hace falta
    monitores.py --ver      ensayo en seco: la tabla de lo que haria
    monitores.py --demonio  ademas se queda escuchando y reacciona al enchufar

El modo --demonio es el que va en conf/autostart.conf. Enchufar una pantalla
dispara `monitoradded`, y el modo nuevo se le pone sola.
"""

import json
import os
import re
import socket
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib"))
import hypr  # noqa: E402  (hablarle en Lua o en hyprlang: ver lib/hypr.py)

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
RUNTIME = os.environ.get("XDG_RUNTIME_DIR") or "/run/user/%d" % os.getuid()

# Los ficheros de esta maquina y de nadie mas. No se versionan, y lo que digan
# manda sobre lo que decida este script.
# Donde se nombran salidas a mano, segun el idioma de la config que este
# corriendo. Con la de Lua, lo tuyo esta en lua/personal.lua; conf/personal.conf
# queda de la config vieja (y lo sigue leyendo una sesion que arranco con ella).
# Mirar solo el del modo en curso importa: si quitas una pantalla de tu
# personal.lua, la copia vieja de personal.conf no debe seguir «fijandola».
FICHEROS_TUYOS = {
    "lua": ("hypr/lua/personal.lua", "hypr/lua/local.lua"),
    "conf": ("hypr/conf/personal.conf", "hypr/conf/local.conf"),
}

# Como viene cada modo en `availableModes`: "1920x1080@100.00Hz".
MODO_RE = re.compile(r"^(\d+)x(\d+)@([\d.]+)Hz$")

# Una linea `monitor = NOMBRE, ...` con nombre de verdad. La generica de
# monitors.conf (`monitor = , preferred, ...`) NO casa aqui a proposito: no fija
# ninguna salida concreta, asi que no bloquea nada.
FIJADA_RE = re.compile(r"^[ \t]*monitor[ \t]*=[ \t]*([^,\s]+)[ \t]*,", re.MULTILINE)
# En Lua: `hl.monitor({ output = "HDMI-A-1", ... })`, fuera de comentarios. La
# salida vacia (`output = ""`, la regla generica) no nombra ninguna.
FIJADA_LUA_RE = re.compile(r'^[^\n-]*hl\.monitor\s*\(\s*\{[^}]*?output\s*=\s*"([^"]+)"',
                           re.MULTILINE)

# Dos modos con el mismo refresco de verdad pueden diferir en la tercera
# decimal segun de donde salga el numero. Por debajo de esto son el mismo y no
# hay nada que cambiar — si no, se reaplicaria el mismo modo en cada evento.
MISMO_REFRESCO = 0.5

# Al enchufar una pantalla Hyprland manda varios eventos casi a la vez
# (monitoradded, monitoraddedv2, y los de workspaces que la siguen). Se espera a
# que amaine antes de mirar, o se aplicaria el modo tres veces.
REPOSO = 0.5


def _socket_control():
    """Ruta del socket de control de la instancia de Hyprland en curso."""
    base = os.path.join(RUNTIME, "hypr")
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not sig:
        # Sin la variable (lanzado a mano desde otra terminal) se cae en la
        # unica instancia viva, que es lo que hace waybar-autohide.py.
        try:
            vivas = [d for d in os.listdir(base)
                     if os.path.isdir(os.path.join(base, d))]
        except OSError:
            vivas = []
        if not vivas:
            return ""
        sig = vivas[0]
    return os.path.join(base, sig, ".socket.sock")


def query(cmd):
    """Manda un comando al socket de Hyprland y devuelve la respuesta cruda.

    Es la UNICA puerta al compositor de todo el fichero, y por eso la prueba
    puede sustituirla entera y comprobar la aritmetica sin sesion ni pantallas.
    """
    ruta = _socket_control()
    if not ruta:
        return ""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            s.connect(ruta)
            s.sendall(cmd.encode())
            trozos = []
            while True:
                trozo = s.recv(8192)
                if not trozo:
                    break
                trozos.append(trozo)
        return b"".join(trozos).decode(errors="replace")
    except OSError:
        return ""


# --- Elegir el modo -----------------------------------------------------------

def parsear_modos(lista):
    """[(ancho, alto, refresco)] de los modos que anuncia una salida.

    Lo que no case se tira en silencio: `availableModes` es texto libre y un
    modo raro no puede tumbar la eleccion de los demas.
    """
    modos = []
    for texto in lista or ():
        casa = MODO_RE.match(str(texto).strip())
        if not casa:
            continue
        try:
            modos.append((int(casa.group(1)), int(casa.group(2)),
                          float(casa.group(3))))
        except ValueError:
            continue
    return modos


def mejor_modo(modos):
    """La resolucion mas grande y, DENTRO DE ELLA, el refresco mas alto.

    El orden de los dos criterios es todo el asunto. Al reves —refresco primero,
    que es lo que hace `highrr`— el televisor se va a 800x600, porque su
    800x600@60.32 tiene mas refresco que su 1920x1080@60.00.
    """
    if not modos:
        return None
    ancho, alto = max((a * b, a, b) for a, b, _ in modos)[1:]
    refresco = max(r for a, b, r in modos if (a, b) == (ancho, alto))
    return ancho, alto, refresco


def salidas_fijadas(raiz=RAIZ, modo=""):
    """Nombres de salida que ya configuraste tu; este script no las toca.

    `modo` es el de la config que corre ("lua" o "conf"). Si no se sabe, se
    miran los dos: saltarse de mas una pantalla es inofensivo, pisar una que
    fijaste tu no lo es.
    """
    fijadas = set()
    ficheros = FICHEROS_TUYOS.get(modo) or FICHEROS_TUYOS["lua"] + FICHEROS_TUYOS["conf"]
    for relativa in ficheros:
        try:
            with open(os.path.join(raiz, relativa), encoding="utf-8",
                      errors="replace") as fh:
                texto = fh.read()
        except OSError:
            continue
        patron = FIJADA_LUA_RE if relativa.endswith(".lua") else FIJADA_RE
        fijadas.update(patron.findall(texto))
    return fijadas


def formatear_refresco(valor):
    """El refresco como lo escribe un humano: 100 y no 100.0, 59.97 y no 59.97003."""
    texto = "%.2f" % valor
    return texto.rstrip("0").rstrip(".")


def linea_monitor(mon, modo):
    """La linea `monitor=` que le corresponde, conservando sitio y escala."""
    ancho, alto, refresco = modo
    escala = mon.get("scale") or 1.0
    # La escala se escribe con los decimales justos: Hyprland RECHAZA la linea
    # si el tamano logico no sale entero, asi que 1.5 tiene que llegar como 1.5.
    esc = ("%.6f" % float(escala)).rstrip("0").rstrip(".")
    return "%s,%dx%d@%s,%dx%d,%s" % (
        mon["name"], ancho, alto, formatear_refresco(refresco),
        int(mon.get("x", 0)), int(mon.get("y", 0)), esc)


def revisar(raiz=RAIZ):
    """[(monitor, modo_actual, modo_mejor, motivo)] de cada pantalla.

    `motivo` dice por que NO se va a tocar, o None si si hay que tocarla. Se
    devuelve todo —tambien lo que se deja igual— porque --ver lo enseña entero:
    una tabla que solo lista los cambios no deja comprobar los aciertos.
    """
    try:
        monitores = json.loads(query("j/monitors"))
    except ValueError:
        return []
    fijadas = salidas_fijadas(raiz, hypr.modo_por_respuesta(query("eval return 1")))
    salida = []
    for mon in monitores:
        nombre = mon.get("name")
        if not nombre:
            continue
        try:
            actual = (int(mon["width"]), int(mon["height"]),
                      float(mon["refreshRate"]))
        except (KeyError, TypeError, ValueError):
            continue
        mejor = mejor_modo(parsear_modos(mon.get("availableModes")))
        if nombre in fijadas:
            motivo = "la fijas tu en tu personal.lua (o personal.conf)"
        elif mejor is None:
            motivo = "no anuncia ningun modo que se pueda leer"
        elif mejor[:2] != actual[:2]:
            # Cambiar de RESOLUCION no es lo que se vino a hacer aqui, y a
            # ciegas es peligroso: si la que hay puesta no es la mas grande, es
            # que alguien la eligio (una linea en personal.conf que nombra otra
            # salida, un `hyprctl keyword` a mano, o el propio EDID mintiendo).
            # Se avisa y se deja como esta.
            motivo = "su resolucion no es la mayor que anuncia (%dx%d); no la cambio" % (
                mejor[0], mejor[1])
        elif abs(mejor[2] - actual[2]) < MISMO_REFRESCO:
            motivo = "ya esta en su mejor modo"
        else:
            motivo = None
        salida.append((mon, actual, mejor, motivo))
    return salida


def aplicar(raiz=RAIZ, seco=False):
    """Pone el mejor modo donde haga falta. Devuelve cuantas pantallas cambio."""
    cambiadas = 0
    # Con la config en Lua, `keyword monitor` da error: va como `eval
    # hl.monitor({...})`. Se pregunta el modo una vez, y solo si hay algo que
    # cambiar (--ver no le habla al compositor mas de lo imprescindible).
    modo = None
    for mon, actual, mejor, motivo in revisar(raiz):
        if motivo is not None:
            continue
        linea = linea_monitor(mon, mejor)
        if seco:
            print("  (haria) hyprctl keyword monitor %s" % linea)
        else:
            if modo is None:
                modo = hypr.modo_por_respuesta(query("eval return 1"))
            verbo, resto = hypr.peticion_keyword(modo, "monitor", linea)
            query("%s %s" % (verbo, resto))
            print("monitores: %s pasa de %s Hz a %s Hz a %dx%d" % (
                mon["name"], formatear_refresco(actual[2]),
                formatear_refresco(mejor[2]), mejor[0], mejor[1]))
        cambiadas += 1
    return cambiadas


# --- Las dos formas de llamarlo -----------------------------------------------

def ver(raiz=RAIZ):
    """La tabla de --ver: que hay, que se podria poner, y que se va a hacer."""
    filas = revisar(raiz)
    if not filas:
        print("monitores: no hay sesion de Hyprland con la que hablar")
        return 1
    for mon, actual, mejor, motivo in filas:
        print("%s  %dx%d@%s Hz" % (mon["name"], actual[0], actual[1],
                                   formatear_refresco(actual[2])))
        if mejor:
            print("  el mejor modo a su resolucion: %dx%d@%s Hz" % (
                mejor[0], mejor[1], formatear_refresco(mejor[2])))
        print("  %s" % (motivo if motivo else "SE LE VA A PONER"))
    aplicar(raiz, seco=True)
    return 0


def demonio(raiz=RAIZ):
    """Aplica al arrancar y cada vez que aparece o desaparece una pantalla.

    Se escucha el socket de eventos en vez de sondear, igual que hace
    wallpaper-pause.py. Los eventos que importan son `monitoradded`,
    `monitoraddedv2` y `monitorremoved`; el resto del trafico (workspaces,
    ventanas) se ignora sin leerlo dos veces.
    """
    aplicar(raiz)
    ruta = os.path.join(os.path.dirname(_socket_control()), ".socket2.sock")
    while True:
        try:
            eventos = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            eventos.connect(ruta)
        except OSError:
            # Aun no hay compositor al otro lado, o ya no lo hay. Se reintenta:
            # este demonio lo arranca Hyprland, asi que muere con la sesion.
            time.sleep(2)
            continue
        buffer = b""
        try:
            while True:
                trozo = eventos.recv(4096)
                if not trozo:
                    break            # se cayo el socket: fuera y a reconectar
                buffer += trozo
                lineas, _, buffer = buffer.rpartition(b"\n")
                if not lineas:
                    continue
                if any(l.split(b">>")[0] in (b"monitoradded", b"monitoraddedv2",
                                             b"monitorremoved")
                       for l in lineas.split(b"\n")):
                    # Que amaine la rafaga de eventos antes de preguntar: si se
                    # mira en el primero, la pantalla nueva aun no tiene ni
                    # posicion ni modos que leer.
                    time.sleep(REPOSO)
                    aplicar(raiz)
        except OSError:
            pass
        finally:
            eventos.close()


def main():
    argumentos = sys.argv[1:]
    if "--ver" in argumentos:
        return ver()
    if "--demonio" in argumentos:
        return demonio()
    if argumentos:
        sys.exit("monitores.py: solo entiendo --ver y --demonio (me diste "
                 "«%s»)" % " ".join(argumentos))
    aplicar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
