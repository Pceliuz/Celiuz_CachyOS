#!/usr/bin/env python3
"""
hypr/scripts/modo-programador.py — entrar y salir del modo programador.

Uso:
    modo-programador.py toggle            entra o sale, preguntando antes (SUPER+P)
    modo-programador.py on  [--sin-preguntar]
    modo-programador.py off [--sin-preguntar]
    modo-programador.py estado [--json]   sale con 0 si esta puesto y 1 si no
    modo-programador.py inicio            abre (o cierra) el inicio
    modo-programador.py menu              abre (o cierra) el menu rapido
    modo-programador.py lanzar ID [--pantalla NOMBRE]
                                          abre una app del modo (en esa pantalla)
    modo-programador.py ir N              ir al escritorio N
    modo-programador.py anadir-app        elegir con fuzzel una app para fijarla en el menu
    modo-programador.py quitar-app [ID]   desfijarla (sin ID, lista las fijadas)

LA IDEA
-------
El primo de trabajo del modo gaming (lo pidio asi el usuario, que estudia
software con IA, sistemas y ciberseguridad): casi las mismas restricciones, con
algo mas de libertad. Lo que cambia respecto al gaming esta escrito al lado de
cada cosa; en corto:

  - NO se cierra nada. Lo que no es de trabajo (juegos, Steam, lo que no sea
    una app del modo ni una terminal) se GUARDA en un escritorio oculto y al
    salir vuelve a su numero. Lo de trabajo se queda donde estaba.
  - Los escritorios son libres: nada de «una app por escritorio». Un editor y
    dos terminales en el mismo es como se programa.
  - La barra de arriba se queda (reloj, red, escritorios); el dock se va, que
    lleva juegos. Fondo en video fuera (la VRAM es para los modelos de IA y lo
    que compiles), avisos en «no molestar», y el borde de las ventanas y el
    fondo con el tema del modo. Las animaciones se quedan.
  - Con varias pantallas, SOLO se toca la de trabajo (la enfocada al entrar):
    en la otra puede seguir el anime, como pidio el usuario. El inicio deja
    abrir una app en la otra pantalla (Shift+Enter).
  - Mientras dura, un juego que se abra va al escritorio oculto con un aviso.
    Todo lo demas que abras se queda: si lo abriste tu, es que lo querias.

Al entrar sale el INICIO (programador-inicio.py), un lanzador a pantalla
completa con las apps de trabajo por secciones; dentro del modo vuelve con
SUPER+B (que fuera es fuzzel). El MENU RAPIDO (programador-menu.py) va con la
misma tecla que el del modo gaming, SUPER + la de al lado del 1: lo abierto con
su volumen, la musica, tus apps y añadir otras.

Los dos modos no se juntan: con uno puesto, el otro no entra (lo dice).

LOS GANCHOS (~/.config/celiuz/modo-programador.d/)
--------------------------------------------------
Como los del modo gaming: cada ejecutable se corre con `on` al entrar y `off`
al salir, en segundo plano. Vacia para quien clona.

LO QUE NO AGUANTA
-----------------
Una recarga de la config devuelve el borde, el fondo y SUPER+B de siempre (los
lee de cero). Salir y volver a entrar lo arregla.
"""

import glob
import importlib.util
import json
import os
import shlex
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(AQUI, "lib"))

import canales  # noqa: E402
import hypr  # noqa: E402
import programador  # noqa: E402

_spec = importlib.util.spec_from_file_location("modo_gaming", os.path.join(AQUI, "modo-gaming.py"))
mg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mg)

LANZAR = os.path.join(AQUI, "lanzar.sh")
TERMINAL = os.path.join(AQUI, "terminal.sh")
TARJETA = os.path.join(AQUI, "modo-gaming-tarjeta.py")
INICIO = os.path.join(AQUI, "programador-inicio.py")
MENU = os.path.join(AQUI, "programador-menu.py")

GUARDADAS = "special:modo-programador"
CLASE_TERMINAL = "prog-term"          # las herramientas de terminal del modo

# Lo que cambia al entrar y se devuelve al salir (se lee antes con getoption).
# Sin el fondo en video, detras de las ventanas se veria el logo de Hyprland:
# en su lugar, el color de fondo del tema.
EFECTOS_FONDO = {
    "misc:disable_hyprland_logo": "true",
    "misc:force_default_wallpaper": "0",
}
BORDES = ("general:col.active_border", "general:col.inactive_border")

# SUPER+B: fuera, fuzzel; dentro, el inicio del modo.
ATAJO_INICIO = ("SUPER", "B", 64)


# --- El estado ------------------------------------------------------------------
def ruta_estado():
    """La de ESTA sesion, con su firma (como el modo gaming y los FIFO)."""
    sig = canales.firma()
    if sig:
        return os.path.join(canales.RUNTIME, "modo-programador.%s.json" % sig)
    sueltos = glob.glob(os.path.join(canales.RUNTIME, "modo-programador.*.json"))
    if len(sueltos) == 1:
        return sueltos[0]
    return os.path.join(canales.RUNTIME, "modo-programador.sin-sesion.json")


def leer_estado():
    try:
        with open(ruta_estado(), encoding="utf-8") as fh:
            datos = json.load(fh)
        return datos if isinstance(datos, dict) and datos.get("activo") else None
    except (OSError, ValueError):
        return None


def guardar_estado(datos):
    ruta = ruta_estado()
    with open(ruta + ".nuevo", "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=2)
    os.replace(ruta + ".nuevo", ruta)


# --- Avisos ---------------------------------------------------------------------
def avisar(titulo, texto=""):
    """Un aviso «de paso» (mako/config): se ve tambien en «no molestar», que el
    modo pone, sin sonar y se va solo."""
    try:
        subprocess.Popen(["notify-send", "-a", "Modo programador", "-c", "de-paso",
                          "-i", "utilities-terminal", titulo, texto],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass


# --- Pantallas y escritorios -------------------------------------------------------
def monitores():
    try:
        return json.loads(mg._hyprctl("monitors", "-j") or "[]")
    except ValueError:
        return []


def monitor_enfocado():
    for m in monitores():
        if m.get("focused"):
            return m.get("name")
    return None


def escritorios_de(nombre):
    """Los ids de escritorio que estan en la pantalla `nombre`."""
    try:
        ws = json.loads(mg._hyprctl("workspaces", "-j") or "[]")
    except ValueError:
        return set()
    return {w.get("id") for w in ws if w.get("monitor") == nombre}


def _en_pantalla(ventana, ids_trabajo, monitor_id):
    """Si una ventana es de la pantalla de trabajo. Por el escritorio y, si no
    se sabe, por el id de monitor de la propia ventana."""
    n = mg.num_ws(ventana)
    if n is not None and ids_trabajo:
        return n in ids_trabajo
    return ventana.get("monitor") == monitor_id


def guardar_ajenas(modo, estado, lista):
    """Lo que no es de trabajo de la pantalla de trabajo, al escritorio oculto,
    apuntando donde estaba. Devuelve los nombres de lo guardado."""
    pantalla = estado.get("pantalla")
    ids = escritorios_de(pantalla) if pantalla else set()
    monitor_id = next((m.get("id") for m in monitores() if m.get("name") == pantalla), None)
    guardadas = []
    for v in mg.clientes():
        if not v.get("address") or not v.get("mapped", True) or mg.num_ws(v) is None:
            continue
        if not _en_pantalla(v, ids, monitor_id) or programador.es_de_trabajo(v, lista):
            continue
        estado["guardadas"][v["address"]] = mg.num_ws(v)
        mg.mover(modo, v["address"], GUARDADAS, False)
        guardadas.append(v.get("class") or v.get("title") or v["address"])
    return guardadas


# --- Bordes, fondo y atajos ----------------------------------------------------------
def leer_gradiente(clave):
    """El valor crudo de un color de borde («ff7ee787 ff56d4dd 45deg»), o None."""
    try:
        datos = json.loads(mg._hyprctl("getoption", clave, "-j") or "{}")
    except ValueError:
        return None
    for campo in ("gradient", "custom", "css"):
        if isinstance(datos.get(campo), str) and datos[campo].strip():
            return datos[campo].strip()
    if isinstance(datos.get("int"), int):
        return "%08x" % (datos["int"] & 0xFFFFFFFF)
    return None


def _rgba(aarrggbb):
    """«ff7ee787» (como lo da getoption) -> «rgba(7ee787ff)» (como se escribe)."""
    t = aarrggbb.strip().lower().lstrip("#")
    if t.startswith("0x"):
        t = t[2:]
    if len(t) == 6:
        t = "ff" + t
    if len(t) != 8 or any(c not in "0123456789abcdef" for c in t):
        raise ValueError("color raro: %r" % aarrggbb)
    return "rgba(%s%s)" % (t[2:], t[:2])


def peticion_gradiente(modo, clave, crudo):
    """(verbo, resto) de hyprctl para poner un borde. `crudo` en el formato de
    getoption: colores AARRGGBB separados por espacios y un angulo «Ndeg»
    opcional. En Lua va como tabla (lua/general.lua lo escribe asi); en
    hyprlang, en una linea."""
    colores, angulo = [], None
    for trozo in crudo.split():
        if trozo.endswith("deg"):
            angulo = int(float(trozo[:-3]))
        else:
            colores.append(_rgba(trozo))
    if not colores:
        raise ValueError("borde sin colores: %r" % crudo)
    if modo == hypr.LUA:
        seccion, _, resto = clave.partition(":")
        _, _, nombre = resto.partition(".")
        lua = "{ colors = { %s }, angle = %d }" % (", ".join(hypr.cadena_lua(c) for c in colores),
                                                 angulo or 0)
        return "eval", "hl.config({ %s = { col = { %s = %s } } })" % (seccion, nombre, lua)
    return "keyword", "%s %s%s" % (clave, " ".join(colores), " %ddeg" % angulo if angulo is not None else "")


def poner_gradiente(modo, clave, crudo):
    try:
        verbo, resto = peticion_gradiente(modo, clave, crudo)
    except ValueError:
        return
    if verbo == "keyword":
        clave_, _, valor = resto.partition(" ")
        mg._hyprctl("keyword", clave_, valor)
    else:
        mg._hyprctl("eval", resto)


def bordes_del_tema(tema):
    """Los bordes del modo: verde a cian el activo, el del tema el inactivo."""
    hexa = lambda k: "ff" + tema[k].lstrip("#")  # noqa: E731
    return {"general:col.active_border": "%s %s 45deg" % (hexa("verde"), hexa("cian")),
            "general:col.inactive_border": hexa("borde")}


def atajo_actual(mods, tecla, mascara):
    """La orden del atajo de siempre (para devolverlo al salir): en Lua es su
    `description` (lua/keybinds.lua la pone igual que la orden en los exec)."""
    try:
        binds = json.loads(mg._hyprctl("binds", "-j") or "[]")
    except ValueError:
        return None
    for b in binds:
        if b.get("modmask") == mascara and (b.get("key") or "").upper() == tecla and not b.get("submap"):
            if b.get("dispatcher") == "exec" and b.get("arg"):
                return b["arg"]
            return b.get("description") or None
    return None


def peticion_atajo(modo, mods, tecla, orden, descripcion):
    """(verbo, argumentos) para cambiar un atajo de exec en caliente."""
    if modo == hypr.LUA:
        combo = "%s + %s" % (mods, tecla)
        return "eval", ['hl.unbind(%s); hl.bind(%s, hl.dsp.exec_cmd(%s), { description = %s })'
                        % (hypr.cadena_lua(combo), hypr.cadena_lua(combo), hypr.cadena_lua(orden),
                           hypr.cadena_lua(descripcion))]
    return "keyword", ["unbind %s,%s" % (mods, tecla), "bind %s,%s,exec,%s" % (mods, tecla, orden)]


def cambiar_atajo(modo, mods, tecla, orden, descripcion):
    verbo, args = peticion_atajo(modo, mods, tecla, orden, descripcion)
    for a in args:
        if verbo == "eval":
            mg._hyprctl("eval", a)
        else:
            palabra, _, resto = a.partition(" ")
            mg._hyprctl("keyword", palabra, resto)


# --- Abrir cosas -----------------------------------------------------------------
def _lanzar_proceso(orden):
    try:
        subprocess.Popen(orden, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except OSError:
        return False


def orden_de(app):
    """La linea de ordenes con que se abre una app del modo: por lanzar.sh (su
    scope de systemd, y aviso si no esta), y las de terminal dentro de una
    terminal con su clase (terminal.sh ya pone el uwsm)."""
    try:
        partes = shlex.split(app["cmd"])
    except ValueError:
        partes = app["cmd"].split()
    if app.get("terminal"):
        return [TERMINAL, CLASE_TERMINAL] + partes
    return [LANZAR] + partes


def lanzar(ident, pantalla=None):
    lista = programador.apps_de_trabajo()
    app = next((a for a in lista if a["id"] == ident), None)
    if app is None:
        print("modo programador: no hay ninguna app «%s»" % ident, file=sys.stderr)
        return 1
    if pantalla:
        # La ventana nueva sale en la pantalla con el foco: se le da a esa
        # primero (`hl.dsp.focus({ monitor = ... })`, comprobado en vivo).
        modo = hypr.modo()
        if modo == hypr.LUA:
            mg._hyprctl("dispatch", "hl.dsp.focus({ monitor = %s })" % hypr.cadena_lua(pantalla))
        elif modo:
            mg._hyprctl("dispatch", "focusmonitor", pantalla)
    return 0 if _lanzar_proceso(orden_de(app)) else 1


def abrir_pantalla(script):
    """El inicio o el menu (cada uno se cierra solo si ya estaba abierto)."""
    if not os.path.exists(script) or not os.environ.get("WAYLAND_DISPLAY"):
        return False
    return _lanzar_proceso([sys.executable, script])


# --- Preguntar --------------------------------------------------------------------
def preguntar(accion):
    """La tarjeta, con el tema del modo. Sin tarjeta no se hace nada (como en el
    modo gaming: un atajo rozado no puede mover tus ventanas sin preguntarte)."""
    if not os.path.exists(TARJETA):
        return False
    try:
        return subprocess.run([sys.executable, TARJETA, "--programador", accion],
                              check=False, timeout=60).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


# --- El vigilante ------------------------------------------------------------------
def arrancar_vigilante():
    try:
        return subprocess.Popen([sys.executable, os.path.realpath(__file__), "vigilar"],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True).pid
    except OSError:
        return None


def parar_vigilante(pid):
    """Solo si ese PID sigue siendo NUESTRO vigilante (un PID se recicla)."""
    if not pid:
        return
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as fh:
            orden = fh.read().decode("utf-8", "replace")
    except OSError:
        return
    if "modo-programador.py" in orden and "vigilar" in orden:
        try:
            os.kill(pid, 15)
        except OSError:
            pass


def es_juego_o_tienda(ventana):
    """Lo unico que el modo no deja a la vista: un juego, o la ventana principal
    de un lanzador (Steam, Heroic...). Sus dialogos («Launching…») tampoco."""
    if mg._clase(ventana).startswith("steam_app_"):
        return True
    return bool(mg.es_de_juego(ventana)) or mg.es_ventana_de_lanzador(ventana) or mg.es_dialogo_steam(ventana)


def apartar_si_juego(modo, ventana):
    """Un juego (o una tienda) que se abre en la pantalla de trabajo, al oculto,
    con un aviso. True si se aparto."""
    estado = leer_estado()
    if not estado or not es_juego_o_tienda(ventana) or mg.num_ws(ventana) is None:
        return False
    pantalla = estado.get("pantalla")
    ids = escritorios_de(pantalla) if pantalla else set()
    if ids and mg.num_ws(ventana) not in ids:
        return False                    # en la otra pantalla: libre
    estado.setdefault("guardadas", {})[ventana["address"]] = mg.num_ws(ventana)
    guardar_estado(estado)
    mg.mover(modo, ventana["address"], GUARDADAS, False)
    avisar("Guardado hasta que salgas", "«%s» espera en el escritorio oculto: estás en modo programador."
           % (ventana.get("title") or ventana.get("class") or "?"))
    return True


def vigilar():
    import socket
    modo = hypr.modo()
    ruta = os.path.join(canales.RUNTIME, "hypr", canales.firma(), ".socket2.sock")
    try:
        eventos = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        eventos.connect(ruta)
        eventos.settimeout(2.0)
    except OSError:
        return 1
    buffer = b""
    while True:
        try:
            trozo = eventos.recv(8192)
        except socket.timeout:
            if not leer_estado():
                return 0
            continue
        except OSError:
            return 0
        if not trozo:
            return 0                    # Hyprland se fue
        if not leer_estado():
            return 0                    # el modo se quito
        buffer += trozo
        *lineas, buffer = buffer.split(b"\n")
        for linea in lineas:
            evento, _, datos = linea.decode("utf-8", "replace").partition(">>")
            if evento != "openwindow":
                continue
            # Los juegos tardan en decir quienes son (Proton): se mira un
            # momento despues, con su ventana ya puesta.
            time.sleep(0.3)
            direccion = "0x" + datos.split(",")[0]
            v = next((x for x in mg.clientes() if x.get("address") == direccion), None)
            if v:
                apartar_si_juego(modo, v)


# --- Entrar y salir -------------------------------------------------------------------
def entrar(sin_preguntar=False):
    if leer_estado():
        print("modo programador: ya estaba puesto")
        return 0
    if mg.leer_estado():
        print("modo programador: estás en el modo gaming; sal de él primero (SUPER+G)", file=sys.stderr)
        avisar("Estás en el modo gaming", "Sal de él primero (SUPER+G) para entrar al modo programador.")
        return 1
    modo = hypr.modo()
    if not modo:
        print("modo programador: no hay una sesion de Hyprland con la que hablar", file=sys.stderr)
        return 1
    if not sin_preguntar and not preguntar("entrar"):
        print("modo programador: cancelado")
        return 1

    aj = programador.ajustes()
    estado = {"activo": True, "desde": int(time.time()), "firma": canales.firma(),
              "pantalla": monitor_enfocado(), "efectos": {}, "bordes": {},
              "no_molestar_puesto": False, "fondo_apagado": False, "guardadas": {},
              "atajo_inicio": None, "vigilante": None}
    # El estado PRIMERO: si algo de abajo falla a medias, salir sabe que deshacer.
    guardar_estado(estado)

    lista = programador.apps_de_trabajo(aj)
    guardadas = guardar_ajenas(modo, estado, lista)
    guardar_estado(estado)

    for clave, crudo in bordes_del_tema(aj["tema"]).items():
        antes = leer_gradiente(clave)
        if antes:
            estado["bordes"][clave] = antes
            poner_gradiente(modo, clave, crudo)
    if aj["apagar_fondo"]:
        efectos = dict(EFECTOS_FONDO)
        efectos["misc:background_color"] = "rgba(%sff)" % aj["tema"]["fondo"].lstrip("#")
        for clave, valor in efectos.items():
            antes = mg.leer_opcion(clave)
            if antes is not None:
                estado["efectos"][clave] = antes
                mg.poner_opcion(modo, clave, valor)
        estado["fondo_apagado"] = mg.mandar_fifo(canales.canal_fondo(), "gaming-on")
    if aj["no_molestar"]:
        modos = mg.makoctl("mode")
        if modos is not None and "no-molestar" not in modos.split():
            if mg.makoctl("mode", "-a", "no-molestar") is not None:
                estado["no_molestar_puesto"] = True
    # Solo el dock: la barra de arriba se queda (el reloj, la red, los escritorios).
    mg.mandar_fifo(canales.canal_barras(), "dock:gaming-on")
    guardar_estado(estado)

    estado["atajo_inicio"] = atajo_actual(*ATAJO_INICIO)
    cambiar_atajo(modo, ATAJO_INICIO[0], ATAJO_INICIO[1], "%s inicio" % os.path.realpath(__file__),
                  "modo programador: inicio")
    estado["vigilante"] = arrancar_vigilante()
    guardar_estado(estado)
    ganchos = correr_ganchos("on")
    abrir_pantalla(INICIO)

    print("modo programador: puesto")
    if guardadas:
        print("  guardadas hasta salir: " + ", ".join(guardadas))
    if ganchos:
        print("  ganchos: " + ", ".join(ganchos))
    return 0


def correr_ganchos(fase):
    """Los de ~/.config/celiuz/modo-programador.d/ (el mismo reparto que el
    modo gaming, con su carpeta)."""
    original = mg.carpeta_ganchos
    mg.carpeta_ganchos = programador.carpeta_ganchos
    try:
        return mg.correr_ganchos(fase)
    finally:
        mg.carpeta_ganchos = original


def cerrar_pantallas():
    """El inicio y el menu, si estan abiertos (cada uno guarda su PID)."""
    for nombre, marca in (("programador-inicio", b"programador-inicio.py"),
                          ("programador-menu", b"programador-menu.py")):
        ruta = os.path.join(canales.RUNTIME, "%s.%s.pid" % (nombre, canales.firma() or "sin-sesion"))
        try:
            with open(ruta) as fh:
                pid = int(fh.read().strip())
            with open("/proc/%d/cmdline" % pid, "rb") as fh:
                if marca in fh.read():
                    os.kill(pid, 15)
        except (OSError, ValueError):
            pass


def salir(sin_preguntar=False):
    estado = leer_estado()
    if not estado:
        print("modo programador: no estaba puesto")
        return 0
    if not sin_preguntar and not preguntar("salir"):
        print("modo programador: cancelado")
        return 1
    parar_vigilante(estado.get("vigilante"))
    cerrar_pantallas()
    modo = hypr.modo()
    if modo:
        # Lo guardado vuelve a su numero, sin llevarte.
        guardadas = estado.get("guardadas") or {}
        for v in mg.clientes():
            if v.get("address") in guardadas and mg._en(v) == GUARDADAS:
                mg.mover(modo, v["address"], guardadas[v["address"]], False)
        # Y lo que se quedara en el oculto por otro camino, a donde estas.
        activo = mg.escritorio_activo().get("id") or 1
        for v in mg.clientes():
            if mg._en(v) == GUARDADAS:
                mg.mover(modo, v["address"], activo, False)
        for clave, crudo in (estado.get("bordes") or {}).items():
            poner_gradiente(modo, clave, crudo)
        for clave, valor in (estado.get("efectos") or {}).items():
            mg.poner_opcion(modo, clave, valor)
        orden = estado.get("atajo_inicio") or "pkill fuzzel || fuzzel"
        cambiar_atajo(modo, ATAJO_INICIO[0], ATAJO_INICIO[1], orden, orden)
    if estado.get("no_molestar_puesto"):
        mg.makoctl("mode", "-r", "no-molestar")
    if estado.get("fondo_apagado"):
        mg.mandar_fifo(canales.canal_fondo(), "gaming-off")
    mg.mandar_fifo(canales.canal_barras(), "dock:gaming-off")
    correr_ganchos("off")
    try:
        os.remove(ruta_estado())
    except OSError:
        pass
    print("modo programador: quitado")
    return 0


# --- El resto de la CLI ------------------------------------------------------------
def ir_cli(sitio):
    if not sitio.isdigit():
        print("uso: modo-programador.py ir <numero de escritorio>", file=sys.stderr)
        return 2
    mg.ir(hypr.modo(), int(sitio))
    return 0


def anadir_app():
    """Elegir con fuzzel una app para fijarla en el menu rapido: las del modo
    que aun no estan fijadas y, detras, cualquier otra instalada (esa entra
    ademas en «mias/» del inicio)."""
    import shutil
    if not shutil.which("fuzzel"):
        print("modo programador: hace falta fuzzel para elegir la app", file=sys.stderr)
        return 1
    fijadas = {a["id"] for a in programador.favoritas()}
    candidatas = [{"label": a["nombre"], "icon_name": a["icono"], "id": a["id"]}
                  for a in programador.apps_de_trabajo() if a["id"] not in fijadas]
    candidatas += programador.candidatas_para_anadir()
    if not candidatas:
        return 1
    lineas = ["%s\0icon\x1f%s" % (" ".join(c["label"].split()),
                                 ",".join(filter(None, (c["icon_name"], "application-x-executable"))))
              for c in candidatas]
    try:
        r = subprocess.run(["fuzzel", "--dmenu", "--index", "--prompt", "\uf120  Fijar en el menú  ",
                            "--placeholder", "Busca una app…"],
                           input="\n".join(lineas), capture_output=True, text=True, timeout=300)
        indice = int(r.stdout.strip())
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return 1                        # cancelado
    if not 0 <= indice < len(candidatas):
        return 1
    elegida = candidatas[indice]
    if "id" not in elegida:
        programador.anadir_app({k: elegida[k] for k in ("label", "cmd", "icon_name", "terminal")})
        elegida = dict(elegida, id="mia:" + elegida["cmd"])
    programador.fijar(elegida["id"])
    print("modo programador: fijada «%s»" % elegida["label"])
    return 0


def quitar_app_cli(ident):
    """Desfijar una app del menu rapido (sigue en el inicio)."""
    if not ident:
        for a in programador.favoritas():
            print("%s\t%s" % (a["id"], a["nombre"]))
        return 2
    if not programador.desfijar(ident):
        print("modo programador: «%s» no esta fijada en el menu" % ident, file=sys.stderr)
        return 1
    print("modo programador: quitada «%s» del menu" % ident)
    return 0


def estado_cli(como_json):
    estado = leer_estado()
    if como_json:
        print(json.dumps({"activo": bool(estado), "desde": (estado or {}).get("desde"),
                          "pantalla": (estado or {}).get("pantalla")}))
    else:
        print("puesto desde %s" % time.strftime("%H:%M", time.localtime(estado["desde"]))
              if estado else "quitado")
    return 0 if estado else 1


def main(argv):
    orden = argv[0] if argv else ""
    sin = "--sin-preguntar" in argv
    if orden == "on":
        return entrar(sin)
    if orden == "off":
        return salir(sin)
    if orden == "toggle":
        return salir(sin) if leer_estado() else entrar(sin)
    if orden == "estado":
        return estado_cli("--json" in argv)
    if orden == "vigilar":
        return vigilar()
    if orden in ("inicio", "menu"):
        if not leer_estado():
            print("modo programador: no esta puesto", file=sys.stderr)
            return 1
        return 0 if abrir_pantalla(INICIO if orden == "inicio" else MENU) else 1
    if orden == "lanzar" and len(argv) >= 2:
        pantalla = argv[argv.index("--pantalla") + 1] if "--pantalla" in argv[:-1] else None
        return lanzar(argv[1], pantalla)
    if orden == "ir":
        return ir_cli(argv[1] if len(argv) > 1 else "")
    if orden == "anadir-app":
        return anadir_app()
    if orden == "quitar-app":
        return quitar_app_cli(" ".join(argv[1:]))
    print(__doc__.split("LA IDEA")[0].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
