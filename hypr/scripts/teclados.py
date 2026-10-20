#!/usr/bin/env python3
"""
hypr/scripts/teclados.py — que distribucion tiene cada teclado, preguntando UNA
vez por teclado.

    teclados.py --demonio    vigila los teclados y pregunta por los nuevos
                             (lo arranca lua/autostart.lua)
    teclados.py ver          lo que ve ahora: cada teclado, y que hara con el
    teclados.py olvidar ID   borra la respuesta de ese aparato (o «todos»), para
                             que vuelva a preguntar la proxima vez que lo vea
    teclados.py tarjeta DESCRIPCION
                             solo la pregunta; imprime latam / es / us / no, o
                             nada si se cerro sin contestar

POR QUE PREGUNTAR. Lo honesto seria que el teclado lo dijera, y hay donde: el
campo `bCountryCode` del descriptor HID. Se le pregunto a los teclados de las
dos maquinas y contestan «Not supported», como casi todos. /etc/vconsole.conf
tampoco vale: dice con que teclado se INSTALO (en la PC del autor pone latam y
su teclado es un ANSI us). Asi que se pregunta, y se pregunta por algo que se
puede mirar sin saber de distribuciones: que teclas tiene. «Ñ» y «Ç» es español
de España; «Ñ» sin «Ç» es latinoamericano; ni una ni otra («; :» a la derecha
de la L) es ingles.

CADA TECLADO CON LA SUYA, A LA VEZ. La distribucion va por teclado (`hl.device`),
no por equipo: con un teclado US enchufado a la laptop, el US escribe en ingles
y el interno sigue en latinoamericano, y se puede ir de uno a otro sin tocar
nada. Al conectar uno ya conocido sale un aviso diciendo cual se le puso.

QUE ES «UN TECLADO». Un aparato fisico se presenta como varios dispositivos
(«X820UItra», «X820UItra Keyboard», «… Consumer Control»), asi que se pregunta
por APARATO (bus:fabricante:producto) y la respuesta vale para todos sus
nombres. Y no todo lo que Hyprland lista como teclado lo es:
  - el boton de encendido, «Video Bus», los botones extra del portatil: no
    tienen letras. Solo cuenta un aparato con la fila Q..P, A..L y Z..M.
  - un RATON con interfaz de teclado: el «USB OPTICAL MOUSE» de la laptop
    anuncia TODAS las letras (medido en /proc/bus/input/devices). Si ademas
    mueve un puntero y se llama raton, no se pregunta. Si se cuela otro, la
    tarjeta tiene «No es un teclado».
  - el teclado interno de un PORTATIL (bus i8042) tampoco: para ese si vale lo
    que se eligio al instalar, porque se contesto tecleando en el (ver
    lib/maquina.perfil_teclado). En un sobremesa un i8042 es un teclado PS/2
    enchufado, y ese si se pregunta.
  - los virtuales (uinput, el teclado del Hyprland anidado) no se preguntan.

DONDE SE APUNTA: ~/.config/celiuz/teclados.conf, que es de cada equipo (ver
«La regla de oro» del CLAUDE.md). Una linea por nombre de Hyprland, con la
distribucion entera ya resuelta, para que lua/teclados.lua solo tenga que
leerla en cada recarga. Al contestar se aplica tambien en caliente con
`hl.device` (por `hyprctl eval`), que solo cambia ESE teclado.
"""

import fcntl
import os
import socket
import struct
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(AQUI, "lib"))

import canales  # noqa: E402
import hypr  # noqa: E402
import maquina  # noqa: E402

PROC = "/proc/bus/input/devices"
SONDEO = 1.5        # segundos entre vistazos a /proc (leerlo cuesta nada)
ABANDONO = 30       # segundos sin Hyprland antes de irse (ver CLAUDE.md)

BUS_USB, BUS_BLUETOOTH, BUS_I8042 = 0x03, 0x05, 0x11
EV_REL = 2
# KEY_Q..KEY_P, KEY_A..KEY_L, KEY_Z..KEY_M (linux/input-event-codes.h)
LETRAS = list(range(16, 26)) + list(range(30, 39)) + list(range(44, 51))
PALABRA = struct.calcsize("l") * 8     # los bitmaps de /proc van en `long`
RATON = ("mouse", "raton", "ratón", "mice", "trackball")

CABECERA = """\
# La distribucion de cada teclado de este equipo. La escribe
# hypr/scripts/teclados.py cuando contestas su pregunta, y la lee
# hypr/lua/teclados.lua en cada recarga. Para que vuelva a preguntar por uno:
#     teclados.py olvidar <id>        (o borra sus lineas)
# nombre en Hyprland<TAB>kb_layout<TAB>kb_variant<TAB>id del aparato<TAB>descripcion
# (kb_layout «-»: dijiste que no es un teclado)
"""


# --- Lo que hay enchufado --------------------------------------------------------
def nombre_hypr(nombre):
    """El nombre con que Hyprland llama a un dispositivo: el del kernel en
    minusculas y con los espacios hechos guiones. Comprobado en la laptop:
    «USB OPTICAL MOUSE  Keyboard» es usb-optical-mouse--keyboard."""
    return nombre.replace(" ", "-").replace("\n", "-").lower()


def _bitmap(texto):
    valor = 0
    for palabra in texto.split():
        valor = (valor << PALABRA) | int(palabra, 16)
    return valor


def leer_proc(texto):
    """Los dispositivos de /proc/bus/input/devices, como diccionarios."""
    dispositivos = []
    for bloque in texto.split("\n\n"):
        d = {"bus": None, "id": "", "nombre": "", "ev": 0, "teclas": 0}
        for linea in bloque.splitlines():
            if linea.startswith("I:"):
                campos = dict(c.split("=", 1) for c in linea[2:].split() if "=" in c)
                try:
                    d["bus"] = int(campos.get("Bus", ""), 16)
                except ValueError:
                    continue
                d["id"] = "%s:%s:%s" % (campos.get("Bus", "").lower(),
                                        campos.get("Vendor", "").lower(),
                                        campos.get("Product", "").lower())
            elif linea.startswith("N: Name="):
                d["nombre"] = linea[len("N: Name="):].strip().strip('"')
            elif linea.startswith("B: EV="):
                d["ev"] = _bitmap(linea[len("B: EV="):])
            elif linea.startswith("B: KEY="):
                d["teclas"] = _bitmap(linea[len("B: KEY="):])
        if d["bus"] is not None and d["nombre"]:
            d["hypr"] = nombre_hypr(d["nombre"])
            dispositivos.append(d)
    return dispositivos


def tiene_letras(d):
    return all(d["teclas"] >> n & 1 for n in LETRAS)


def aparatos(dispositivos, portatil, nombres_hypr=None):
    """Los teclados de verdad, agrupados por aparato fisico.

    Devuelve [{id, descripcion, nombres, motivo}] donde `motivo` es None si hay
    que preguntar por el, o por que no. `nombres_hypr` es la lista de teclados
    de `hyprctl devices`; con ella se apuntan solo nombres que Hyprland conoce.
    """
    grupos = {}
    for d in dispositivos:
        grupos.setdefault(d["id"], []).append(d)
    resultado = []
    for ident, ds in grupos.items():
        if not any(tiene_letras(d) for d in ds):
            continue
        bus = ds[0]["bus"]
        descripcion = min((d["nombre"] for d in ds), key=len).strip()
        nombres = sorted({d["hypr"] for d in ds
                          if nombres_hypr is None or d["hypr"] in nombres_hypr})
        if not nombres:
            continue
        motivo = None
        if bus == BUS_I8042 and portatil:
            motivo = "el teclado interno del portatil: usa lo que elegiste al instalar"
        elif bus not in (BUS_USB, BUS_BLUETOOTH, BUS_I8042):
            motivo = "no es USB ni Bluetooth (virtual o del sistema)"
        elif (any(d["ev"] >> EV_REL & 1 for d in ds)
              and any(p in descripcion.lower() for p in RATON)):
            motivo = "es un raton que se anuncia tambien como teclado"
        resultado.append({"id": ident, "descripcion": descripcion,
                          "nombres": nombres, "motivo": motivo})
    return sorted(resultado, key=lambda a: a["id"])


# --- Lo que ya se contesto -----------------------------------------------------------
def ruta_conf():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "celiuz", "teclados.conf")


def leer_conf():
    """{nombre: {layout, variant, id, descripcion}}"""
    datos = {}
    try:
        with open(ruta_conf(), encoding="utf-8") as fh:
            for linea in fh:
                if linea.startswith("#") or not linea.strip():
                    continue
                campos = linea.rstrip("\n").split("\t")
                if len(campos) >= 4:
                    datos[campos[0]] = {"layout": campos[1], "variant": campos[2],
                                        "id": campos[3],
                                        "descripcion": campos[4] if len(campos) > 4 else ""}
    except OSError:
        pass
    return datos


def escribir_conf(datos):
    ruta = ruta_conf()
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    temporal = ruta + ".nuevo"
    with open(temporal, "w", encoding="utf-8") as fh:
        fh.write(CABECERA)
        for nombre in sorted(datos, key=lambda n: (datos[n]["id"], n)):
            e = datos[nombre]
            fh.write("\t".join((nombre, e["layout"], e["variant"], e["id"],
                                e["descripcion"].replace("\t", " "))) + "\n")
    os.replace(temporal, ruta)


def distribucion(respuesta):
    """(kb_layout, kb_variant) para una respuesta de la tarjeta. Siempre con
    las dos distribuciones, la del teclado delante, para que SUPER+Supr
    (teclado.py) siga alternando en este teclado igual que en los demas."""
    if respuesta == "no":
        return "-", ""
    if respuesta in ("latam", "es"):
        return "%s,us" % respuesta, ",altgr-intl"
    return maquina.LAYOUT_AUTOR, maquina.VARIANTE_AUTOR


NOMBRES = {"latam": "latinoamericano", "es": "español (España)", "us": "inglés (US)"}


def nombre_distribucion(layout):
    """«latam,us» → «latinoamericano». La primera es la que manda."""
    primera = layout.split(",")[0]
    return NOMBRES.get(primera, primera)


def avisar_conectado(descripcion, layout, nuevo):
    """El aviso al conectar un teclado. Con la misma etiqueta que teclado.py,
    para que un aviso sustituya al anterior en vez de apilarse."""
    if layout == "-":
        return
    titulo = "Teclado %s conectado" % nombre_distribucion(layout)
    cuerpo = ("«%s»: %s. Los demás teclados conservan la suya." %
              (descripcion, "configuración aplicada" if nuevo else
               "configuración cambiada automáticamente"))
    try:
        subprocess.run(["notify-send", "--app-name=Teclado", "--icon=input-keyboard",
                        "--expire-time=5000",
                        "--hint=string:x-canonical-private-synchronous:teclado",
                        titulo, cuerpo], timeout=5, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        pass


# --- Hablar con Hyprland ---------------------------------------------------------------
def _hyprctl(*args):
    try:
        r = subprocess.run(["hyprctl"] + list(args), capture_output=True, text=True,
                           timeout=5, check=False)
        return r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def teclados_hypr():
    """Los nombres de teclado que lista Hyprland, o None si no contesta."""
    import json
    try:
        return {k["name"] for k in json.loads(_hyprctl("devices", "-j"))["keyboards"]}
    except (ValueError, KeyError, TypeError):
        return None


def aplicar(nombre, layout, variant):
    """Ese teclado, ya, sin recargar nada. Solo con la config en Lua: la vieja
    (el puente) no tiene `eval`, y entonces se avisa y queda para la sesion
    siguiente."""
    if layout == "-":
        return True
    if hypr.modo() != "lua":
        print("teclados: la sesion no usa la config en Lua; %s se ajustara al "
              "volver a entrar" % nombre, file=sys.stderr)
        return False
    orden = "hl.device({ name = %s, kb_layout = %s, kb_variant = %s })" % (
        hypr.cadena_lua(nombre), hypr.cadena_lua(layout), hypr.cadena_lua(variant))
    return _hyprctl("eval", orden).strip() == "ok"


def hypr_vivo():
    """Si se puede CONECTAR con nuestro Hyprland (no si contesta: uno vivo pero
    atareado tambien calla; ver CLAUDE.md)."""
    ruta = os.path.join(canales.RUNTIME, "hypr", canales.firma(), ".socket.sock")
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.settimeout(1)
        s.connect(ruta)
        return True
    except OSError:
        return False
    finally:
        s.close()


# --- La pregunta -------------------------------------------------------------------------
def preguntar(descripcion):
    """«latam», «es», «us», «no», o None si se cerro sin contestar."""
    try:
        r = subprocess.run([sys.executable, os.path.realpath(__file__), "tarjeta", descripcion],
                           capture_output=True, text=True, timeout=600, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    respuesta = r.stdout.strip()
    return respuesta if respuesta in ("latam", "es", "us", "no") else None


def tarjeta(descripcion):
    """La tarjeta, con la misma cara que la del modo gaming. Sin cuenta atras:
    acabas de enchufar un teclado y puede que estes mirando a otro lado."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "tarjeta_base", os.path.join(AQUI, "modo-gaming-tarjeta.py"))
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    Gtk, Gdk, GtkLayerShell = base.Gtk, base.Gdk, base.GtkLayerShell

    if not base.solo_wayland() or not Gtk.init_check(sys.argv)[0]:
        return 1
    base.cargar_estilo("""
        .letra { font-weight: 800; padding: 12px 10px; }
        .letra .grande { font-size: 28px; font-weight: 800; color: white; }
        .letra .pequena { font-size: 12px; font-weight: 700; color: alpha(white, 0.8); }
        .enlace { background: none; border: none; box-shadow: none; color: @tenue;
                  font-size: 12px; padding: 4px 6px; }
        .enlace:hover { color: @luz; }
    """)

    ventana = Gtk.Window()
    respuesta = {"valor": ""}

    def terminar(valor):
        respuesta["valor"] = valor
        ventana.destroy()

    GtkLayerShell.init_for_window(ventana)
    GtkLayerShell.set_namespace(ventana, "teclado-tarjeta")
    GtkLayerShell.set_layer(ventana, GtkLayerShell.Layer.OVERLAY)
    GtkLayerShell.set_keyboard_mode(ventana, GtkLayerShell.KeyboardMode.ON_DEMAND)
    ventana.set_app_paintable(True)
    if ventana.get_screen().get_rgba_visual():
        ventana.set_visual(ventana.get_screen().get_rgba_visual())

    caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    caja.get_style_context().add_class("tarjeta")
    caja.set_size_request(460, -1)
    for texto, clase in (("◆  TECLADO NUEVO", "marca"),
                         ("¿Qué teclas tiene?", "titulo"),
                         ("«%s». Mira la tecla de la derecha de la L, y si hay "
                          "una «Ç» junto al Intro. Lo recuerdo para este teclado, "
                          "y los demás conservan la suya." % descripcion, "texto")):
        etiqueta = Gtk.Label(label=texto, xalign=0)
        etiqueta.set_line_wrap(True)
        etiqueta.set_max_width_chars(44)
        etiqueta.get_style_context().add_class(clase)
        caja.pack_start(etiqueta, False, False, 0)

    botones = Gtk.Box(spacing=12, homogeneous=True)
    botones.set_margin_top(14)
    for letra, pie_, valor in (("Ñ  Ç", "España", "es"), ("Ñ", "Latinoamérica", "latam"),
                               ("; :", "Inglés", "us")):
        b = Gtk.Button()
        dentro = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for texto_, clase_ in ((letra, "grande"), (pie_, "pequena")):
            e = Gtk.Label(label=texto_)
            e.get_style_context().add_class(clase_)
            dentro.pack_start(e, False, False, 0)
        b.add(dentro)
        for clase in ("boton", "si", "letra"):
            b.get_style_context().add_class(clase)
        b.connect("clicked", lambda _b, v=valor: terminar(v))
        botones.pack_start(b, True, True, 0)
    caja.pack_start(botones, False, False, 0)

    pie = Gtk.Box(spacing=6)
    pie.set_margin_top(8)
    for texto, valor in (("No es un teclado", "no"), ("Ahora no", "")):
        b = Gtk.Button(label=texto)
        b.get_style_context().add_class("enlace")
        b.connect("clicked", lambda _b, v=valor: terminar(v))
        pie.pack_end(b, False, False, 0)
    caja.pack_start(pie, False, False, 0)

    ventana.add(caja)
    ventana.connect("key-press-event",
                    lambda _w, e: terminar("") if e.keyval == Gdk.KEY_Escape else False)
    ventana.connect("destroy", Gtk.main_quit)
    ventana.show_all()
    Gtk.main()
    if respuesta["valor"]:
        print(respuesta["valor"])
    return 0


# --- El demonio ----------------------------------------------------------------------------
def revisar(texto, aplazados, preguntar_=preguntar, vistos=None, avisar_=avisar_conectado):
    """Una pasada: apunta y aplica lo que falte. Devuelve los ids aplazados
    («Ahora no») que siguen enchufados, para no volver a preguntar por ellos
    hasta que se desenchufen. Con `vistos` (un set que el demonio guarda entre
    pasadas) avisa de cada teclado ya conocido que ACABA de aparecer; sin el,
    no avisa (la primera pasada del demonio lo arranca con lo que ya habia)."""
    portatil = maquina.detalle()["tipo"] == "laptop"
    lista = aparatos(leer_proc(texto), portatil, teclados_hypr())
    presentes = {a["id"] for a in lista}
    aplazados = aplazados & presentes
    conf = leer_conf()
    por_id = {e["id"]: e for e in conf.values()}
    recien = presentes - vistos if vistos is not None else set()
    if vistos is not None:
        vistos.clear()
        vistos.update(presentes)
    for a in lista:
        if a["motivo"]:
            continue
        sabido = por_id.get(a["id"])
        if sabido is None:
            if a["id"] in aplazados:
                continue
            respuesta = preguntar_(a["descripcion"])
            if respuesta is None:
                aplazados.add(a["id"])
                continue
            layout, variant = distribucion(respuesta)
            avisar_(a["descripcion"], layout, True)
        else:
            layout, variant = sabido["layout"], sabido["variant"]
            if a["id"] in recien:
                avisar_(a["descripcion"], layout, False)
        nuevos = [n for n in a["nombres"] if n not in conf]
        if not nuevos:
            continue
        for n in nuevos:
            conf[n] = {"layout": layout, "variant": variant, "id": a["id"],
                       "descripcion": a["descripcion"]}
        escribir_conf(conf)
        for n in nuevos:
            aplicar(n, layout, variant)
    return aplazados


def demonio():
    if not canales.firma():
        sys.exit("teclados.py: sin HYPRLAND_INSTANCE_SIGNATURE no se a que sesion atender")
    # Uno por sesion: un flock con la firma, que «ya hay una tarjeta» no vale
    # de cerrojo (ver CLAUDE.md, el modo gaming abrio dos bibliotecas asi).
    cerrojo = open(os.path.join(canales.RUNTIME, "teclados.%s.lock" % canales.firma()), "w")
    try:
        fcntl.flock(cerrojo, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0
    ultimo, aplazados, sin_hypr, vistos = None, set(), 0.0, None
    while True:
        if hypr_vivo():
            sin_hypr = 0.0
        else:
            sin_hypr += SONDEO
            if sin_hypr >= ABANDONO:
                return 0     # nuestro Hyprland ya no esta: no sobrevivirle
        try:
            with open(PROC, encoding="utf-8", errors="replace") as fh:
                texto = fh.read()
        except OSError:
            texto = ""
        if texto != ultimo and sin_hypr == 0:
            ultimo = texto
            # Que amaine: un aparato aparece en /proc antes que en Hyprland.
            time.sleep(0.5)
            # La primera vez se apunta lo que ya hay enchufado sin avisar: al
            # entrar en la sesion no hace falta un aviso por teclado.
            if vistos is None:
                vistos = {a["id"] for a in aparatos(leer_proc(texto),
                          maquina.detalle()["tipo"] == "laptop", teclados_hypr())}
            aplazados = revisar(texto, aplazados, vistos=vistos)
        time.sleep(SONDEO)


def ver():
    portatil = maquina.detalle()["tipo"] == "laptop"
    with open(PROC, encoding="utf-8", errors="replace") as fh:
        lista = aparatos(leer_proc(fh.read()), portatil, teclados_hypr())
    conf = leer_conf()
    por_id = {e["id"]: e for e in conf.values()}
    if not lista:
        print("No veo ningun teclado.")
    for a in lista:
        print("%s  %s" % (a["id"], a["descripcion"]))
        print("    nombres: %s" % ", ".join(a["nombres"]))
        sabido = por_id.get(a["id"])
        if a["motivo"]:
            print("    no se pregunta: %s" % a["motivo"])
        elif sabido:
            print("    %s" % ("no es un teclado" if sabido["layout"] == "-" else
                              "%s (%s)" % (sabido["layout"], sabido["variant"])))
        else:
            print("    sin contestar: preguntara el demonio")
    print("\nApuntado en %s" % ruta_conf())
    return 0


def olvidar(ident):
    conf = leer_conf()
    quedan = {} if ident == "todos" else {n: e for n, e in conf.items() if e["id"] != ident}
    if len(quedan) == len(conf):
        print("No tengo nada apuntado de «%s». Mira los ids con: teclados.py ver" % ident)
        return 1
    escribir_conf(quedan)
    print("Olvidado. Al volver a enchufarlo (o al entrar) se vuelve a preguntar.")
    return 0


def main(argv):
    if argv[:1] == ["--demonio"]:
        return demonio()
    if argv[:1] == ["ver"]:
        return ver()
    if argv[:1] == ["olvidar"] and len(argv) == 2:
        return olvidar(argv[1])
    if argv[:1] == ["tarjeta"] and len(argv) == 2:
        return tarjeta(argv[1])
    print(__doc__.split("POR QUE")[0].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
