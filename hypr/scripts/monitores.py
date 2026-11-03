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
de lua/monitors.lua: solo sube el refresco donde se pueda. Tampoco cambia la
resolucion: sube el refresco DENTRO de la que ya tiene.

Y NO PISA LO TUYO. Si nombras una salida en lua/personal.lua o lua/local.lua
(personal.conf/local.conf con la config vieja), este script se la salta entera.
Es la regla de capas del repo: gana el ultimo, y personal se carga el ultimo.

NO ESTA SOLO. lua/monitors.lua hace la MISMA eleccion al cargarse, con
`hl.get_monitors()`, para cada pantalla ya encendida: por eso una recarga no
pasa por los 60 Hz. Este script cubre lo que la config no ve —la primera carga
de la sesion, sin salidas aun, y lo que se enchufa despues— y hace de red si
algo se escapa.

USO
---
    monitores.py            aplica lo que haga falta y calla si no hace falta
    monitores.py --ver      ensayo en seco: la tabla de lo que haria
    monitores.py --demonio  ademas se queda escuchando y reacciona al enchufar

El modo --demonio es el que va en lua/autostart.lua. Enchufar una pantalla
dispara `monitoradded`, y el modo nuevo se le pone sola; recargar la config
dispara `configreloaded`, que devolveria la pantalla a `preferred`, y lo mismo.
Y cuando una pantalla vuelve (apagarla con su boton cuenta como desenchufarla)
relanza el fondo, que mpvpaper deja sin dibujar en ella: ver relanzar_fondo().
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

# Los eventos tras los que hay que volver a mirar (ver demonio()).
EVENTOS = (b"monitoradded", b"monitoraddedv2", b"monitorremoved",
           b"configreloaded")

# Los que ademas obligan a relanzar el fondo (ver relanzar_fondo()).
PANTALLA_NUEVA = (b"monitoradded", b"monitoraddedv2")

# monitoradded y monitoraddedv2 llegan por separado a veces: sin esto el fondo
# se relanzaria dos veces seguidas, y cada mpvpaper son ~430 MB al arrancar.
PAUSA_FONDO = 5.0

FONDO = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wallpaper.sh")


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


def mejor_refresco_a(modos, ancho, alto):
    """El refresco mas alto A ESA resolucion, como (ancho, alto, refresco).

    Es lo que se aplica: la resolucion no se toca nunca —la pone la regla de
    lua/monitors.lua, que ya elige la del modo preferido, o la pones tu—, solo
    se sube el refresco dentro de ella. Es la misma eleccion que hace
    monitors.lua al cargarse, para que los dos no se contradigan.
    """
    refrescos = [r for a, b, r in modos if (a, b) == (ancho, alto)]
    return (ancho, alto, max(refrescos)) if refrescos else None


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
        modos = parsear_modos(mon.get("availableModes"))
        # Se sube el refresco A LA RESOLUCION QUE YA TIENE. Cambiar de
        # resolucion no es lo que se vino a hacer aqui, y a ciegas es
        # peligroso: si la que hay puesta no es la mas grande, es la del modo
        # preferido de la pantalla o la eligio alguien (personal.lua, un
        # `hyprctl` a mano). Antes, en ese caso, no se subia ni el refresco.
        mejor = mejor_refresco_a(modos, actual[0], actual[1])
        mayor = mejor_modo(modos)
        if nombre in fijadas:
            motivo = "la fijas tu en tu personal.lua (o personal.conf)"
        elif mejor is None:
            motivo = "no anuncia ningun modo que se pueda leer a su resolucion"
        elif abs(mejor[2] - actual[2]) < MISMO_REFRESCO:
            motivo = "ya esta en su mejor modo"
            if mayor and mayor[:2] != actual[:2]:
                motivo += (" a %dx%d (su resolucion mayor es %dx%d; esa no la "
                           "cambio)" % (actual[0], actual[1], mayor[0], mayor[1]))
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


def fondo_vivo(firma):
    """¿Hay un mpvpaper de ESTA sesion? Se le reconoce por su socket IPC.

    Mismo criterio que wallpaper.sh (`pids_con_marca`): la ruta del socket lleva
    la firma de la instancia de Hyprland, asi que no se confunde con el de otra
    sesion viva ni con el de un Hyprland anidado de pruebas.
    """
    if not firma:
        return False
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open("/proc/%s/cmdline" % pid, "rb") as fh:
                partes = fh.read().split(b"\0")
        except OSError:
            continue
        if (partes and os.path.basename(partes[0]) == b"mpvpaper"
                and any(firma.encode() in p for p in partes)):
            return True
    return False


def relanzar_fondo(firma, lanzar=None):
    """Tras volver una pantalla, relanza el fondo para que se vuelva a dibujar.

    mpvpaper (1.8) sabe estrenar una pantalla NUEVA, pero no recuperar una que
    se fue y volvio: apagar el monitor con su boton es, para el PC, desenchufar
    el cable, y al volver su capa queda creada pero sin dibujar (`a: 0` en
    `hyprctl layers`, mientras la de la pantalla recien llegada sale `a: 1`).
    Visto el 2026-11-01 en un Gigabyte GS27QCA por DisplayPort, tres veces.

    Solo si el fondo estaba vivo. Si no lo esta es que lo quito a proposito
    wallpaper-pause.py porque estas jugando, y relanzarlo ahora le devolveria
    sus ~430 MB al juego; ese demonio ya lo levanta el solo al salir.
    """
    if not fondo_vivo(firma):
        return False
    if lanzar is None:
        import subprocess
        lanzar = lambda orden: subprocess.Popen(  # noqa: E731
            orden, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
    lanzar([FONDO, "--only-mpv"])
    return True


def demonio(raiz=RAIZ):
    """Aplica al arrancar, al aparecer o desaparecer una pantalla y al recargar.

    Se escucha el socket de eventos en vez de sondear, igual que hace
    wallpaper-pause.py. Los eventos que importan son `monitoradded`,
    `monitoraddedv2`, `monitorremoved` y `configreloaded`; el resto del trafico
    (workspaces, ventanas) se ignora sin leerlo dos veces.

    `configreloaded` porque una recarga vuelve a aplicar `preferred` —el modo
    del EDID— y le quita a la pantalla el refresco que se le habia subido. Sin
    escucharlo, la PC se quedaba a 60 Hz tras cada `hyprctl reload` hasta el
    siguiente enchufe (2026-10-20, al recargar `instalar.sh` la sesion). Volver
    a aplicar no hace bucle: si no hay nada que mejorar no manda ni una orden.
    """
    aplicar(raiz)
    ruta = os.path.join(os.path.dirname(_socket_control()), ".socket2.sock")
    firma = os.path.basename(os.path.dirname(ruta))
    ultimo_fondo = 0.0
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
                nombres = {l.split(b">>")[0] for l in lineas.split(b"\n")}
                if nombres & set(EVENTOS):
                    # Que amaine la rafaga de eventos antes de preguntar: si se
                    # mira en el primero, la pantalla nueva aun no tiene ni
                    # posicion ni modos que leer.
                    time.sleep(REPOSO)
                    aplicar(raiz)
                    # Despues de aplicar, para que el fondo nazca ya con el
                    # modo y la posicion buenos de la pantalla que volvio.
                    if (nombres & set(PANTALLA_NUEVA)
                            and time.monotonic() - ultimo_fondo > PAUSA_FONDO):
                        if relanzar_fondo(firma):
                            ultimo_fondo = time.monotonic()
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
