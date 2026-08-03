#!/usr/bin/env python3
"""
~/dotfiles/hypr/scripts/gen-dock.py

Genera waybar/dock.jsonc a partir de waybar/dock-apps.json.

Por que un generador y no editar dock.jsonc a mano: cada app del dock son cuatro
lineas repetidas mas su nombre en "modules-center", y el ancho de la barra tiene
que cuadrar con el numero de botones. Hecho a mano se desincroniza en cuanto
anades una app; asi la lista de apps es un dato y el resto sale de una cuenta.

Tambien es la puerta que usa el gestor de clic derecho (dock-manager.py) y la que
usaria un asistente para tocar el dock: escribe el JSON de datos y llama aqui.

Uso:
    gen-dock.py                       regenera dock.jsonc y recarga el dock
    gen-dock.py seed                  crea el dock de partida: tu terminal y tu
                                      navegador, averiguados en la maquina
    gen-dock.py list                  lista las apps con su indice
    gen-dock.py icons <texto>         busca glifos en la Nerd Font
    gen-dock.py add --icon md-discord --label Discord --cmd discord
    gen-dock.py remove <indice>
    gen-dock.py --no-reload           genera sin tocar el dock que esta corriendo

Los tamanos (GEOMETRIA, abajo) van de la mano del bloque del dock en
waybar/style.css: si cambias uno hay que mirar el otro.
"""

import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import apps  # noqa: E402
import nf_icons  # noqa: E402

# La raiz del repo, sacada de DONDE ESTA ESTE FICHERO (hypr/scripts/gen-dock.py
# -> dos carpetas arriba). Antes ponia "~/dotfiles/waybar" y eso obligaba a
# clonar el repo justo ahi: en ~/.dotfiles o ~/repos/dotfiles generaba en una
# ruta que no era la suya, o directamente en el repo de otro. Lo destapo una
# prueba, que con un HOME de mentira acabo escribiendo en el repo de verdad.
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WAYBAR = os.path.join(RAIZ, "waybar")
# NINGUNO DE LOS TRES SE VERSIONA, y es a proposito: son el dock de ESTA maquina.
# Cuando si estaban en git, clonar el repo te traia las apps del autor —incluidos
# dos juegos suyos por steam://rungameid— y un dock-icons.css con rutas absolutas
# a /home/celiuz que en otro equipo no existen. Los crea instalar.sh.
DATOS = os.path.join(WAYBAR, "dock-apps.json")
SALIDA = os.path.join(WAYBAR, "dock.jsonc")
# Hoja de estilo generada con la imagen de fondo de cada boton (el icono propio
# de la app). style.css la carga con @import y no hay que tocarla a mano.
SALIDA_CSS = os.path.join(WAYBAR, "dock-icons.css")
# Rutas absolutas de ESTE repo. Van absolutas a proposito: dock.jsonc es
# generado y no se versiona, asi que puede contener rutas de la maquina.
GESTOR = os.path.join(RAIZ, "hypr/scripts/dock-manager.py")

# Las apps NO se lanzan directamente: pasan por lanzar.sh, que las arranca con
# `uwsm app --` y avisa con una notificacion si el comando no existe.
#
# Lo de uwsm es para que cada app viva en su PROPIO scope de systemd
# (app.slice/app-graphical.slice/app-*.scope). Sin esto caen todas en
# `session.slice/wayland-wm@hyprland.desktop.service`, el mismo cgroup que
# Hyprland, waybar y mpvpaper — comprobado el 2026-07-27. Y eso rompe el
# congelado selectivo al bloquear la pantalla (ver scripts/lib/congelar.py): no
# hay forma de parar una app sin parar de paso el compositor.
#
# Lo del aviso es para que se entienda: uwsm ya notifica si el comando no existe,
# pero con un "Error: Command not found" generico que no dice de que icono viene
# ni que se puede quitar. Ver la cabecera de lanzar.sh.
#
# El comando que guarda dock-apps.json sigue siendo el limpio ("brave", "steam
# steam://rungameid/..."); el prefijo se pone aqui, al generar.
PREFIJO_LANZAMIENTO = os.path.join(RAIZ, "hypr/scripts/lanzar.sh")
# El prefijo de antes. Se sigue reconociendo para no acabar con un comando
# doblemente prefijado si dock-apps.json viene de una version anterior.
PREFIJO_VIEJO = "uwsm app --"

RUNTIME = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
FIFO = os.path.join(RUNTIME, "waybar-autohide.fifo")

# --- GEOMETRIA ---------------------------------------------------------------
# Todo esto tiene que cuadrar con el bloque "El dock" de style.css:
#
#   glifo 330% de 14px = 46px  ->  caja de linea de 59 px de alto (medido con
#                                  Pango; no es el tamano de la fuente)
#   ancho de la pastilla = min-width 46 + padding 12*2 + borde 1*2 = 72
#   celda                = pastilla 72 + margin 5*2 = 82  = CELDA
#   alto de la pastilla  = ALTO - margin 8*2 = 72, porque el boton se estira a lo
#                          alto para llenar la barra (esta en una caja horizontal
#                          de GTK). O sea: el alto de la barra es lo que decide lo
#                          cuadrada que sale la pastilla.
#
# Ese alto tiene que ser MAYOR que la caja de linea mas el relleno (59+4+2 = 65
# mas los margenes: 81): si no cabe, GTK recorta la pastilla por abajo y el icono
# queda descentrado dentro de un rectangulo cortado. Era exactamente el sintoma
# del dock de 78 px de alto. Medido: con ALTO = 88 la pastilla sale de 72x72 y el
# icono cae centrado con 0 px de desfase.
SPAN = 330      # tamano del glifo en % sobre los 14px base de style.css
CELDA = 82      # ancho reservado por boton
ALTO = 88       # alto de la barra del dock
# Mas botones que esto y hay que alargar la lista de #custom-appN de style.css.
MAX_BOTONES = 20

# La cabecera que lleva dock-apps.json. Vive aqui y no en el fichero porque el
# fichero ya no se versiona: lo escribe `gen-dock.py seed` en cada instalacion.
CABECERA_DATOS = [
    "LAS APPS DEL DOCK — de ESTA maquina. Este fichero NO esta en git: lo crea",
    "instalar.sh con tu terminal y tu navegador, y a partir de ahi es tuyo.",
    "waybar/dock.jsonc y waybar/dock-icons.css se generan de aqui con",
    "hypr/scripts/gen-dock.py y tampoco hay que tocarlos.",
    "",
    "Lo normal es no editar esto a mano: clic derecho en cualquier icono del",
    "dock abre el gestor, que anade y quita apps por ti. Desde la terminal:",
    "  gen-dock.py list",
    "  gen-dock.py add --icon md-discord --label Discord --cmd discord",
    "  gen-dock.py remove 3",
    "  gen-dock.py seed --forzar     vuelve al dock de partida (terminal + navegador)",
    "",
    "Campos de cada app:",
    "  icon      - codigo del glifo en la Nerd Font, en hexadecimal. Se guarda como",
    "              texto y no como el caracter en si a proposito: los glifos de la",
    "              zona de uso privado se corrompen al pasar por editores y",
    "              herramientas de texto. Para buscar uno: gen-dock.py icons <algo>",
    "  icon_name - icono propio de la app (su campo Icon=). Manda sobre el glifo.",
    "  label     - lo que sale en el tooltip al posar el puntero.",
    "  cmd       - lo que se ejecuta al hacer clic izquierdo.",
]


def cargar():
    # Si no hay fichero de datos es que nadie ha pasado instalar.sh todavia: se
    # siembra al vuelo en vez de reventar. Importa porque a esto se llega tambien
    # desde el clic derecho del dock, y ahi un rastreo de Python no se ve.
    if not os.path.exists(DATOS):
        sembrar()
    with open(DATOS) as fh:
        datos = json.load(fh)
    datos.setdefault("apps", [])
    return datos


def guardar(datos):
    with open(DATOS, "w") as fh:
        json.dump(datos, fh, indent=4, ensure_ascii=False)
        fh.write("\n")


# Glifo de respaldo para las apps que van con su icono propio: solo se ve si algun
# dia ese icono desaparece del tema (app desinstalada, cambio de tema). Es
# md-application_outline, a proposito generico y no una adivinanza del tipo de app:
# un icono equivocado despista mas que uno neutro.
GLIFO_GENERICO = 0xF0614


def glifo(app):
    """El caracter del glifo de respaldo, del codigo hexadecimal guardado."""
    try:
        return chr(int(str(app.get("icon", "")), 16))
    except (ValueError, TypeError):
        return chr(GLIFO_GENERICO)


def ruta_icono(nombre):
    """Fichero del icono de una app a partir de su nombre en el tema de iconos.

    Es el valor del campo `Icon=` de su .desktop: puede ser un nombre a buscar en
    el tema ("firefox", "steam_icon_2407270") o ya una ruta absoluta. Se resuelve
    AQUI, al generar, y no se guarda en dock-apps.json, para que el dock siga
    funcionando si cambias de tema de iconos o la app se actualiza y cambia de
    fichero.

    Se pide 128 px porque el icono se dibuja a 46: por debajo de eso los PNG se
    ven blandos al escalarlos.
    """
    if not nombre:
        return None
    if os.path.isabs(nombre) and os.path.exists(nombre):
        return nombre
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
        Gtk.init_check([])
        icono = Gtk.IconTheme.get_default().lookup_icon(nombre, 128, 0)
        return icono.get_filename() if icono else None
    except (ImportError, ValueError):
        return None


def escapar(texto):
    """Escapa para meter el texto dentro de una cadena JSON."""
    return json.dumps(str(texto), ensure_ascii=False)[1:-1]


def lanzar(cmd):
    """Antepone el lanzador al comando de una app (ver PREFIJO_LANZAMIENTO).

    Si el comando ya lo lleva, se deja como esta: asi regenerar el dock dos veces
    no acaba con `lanzar.sh lanzar.sh brave`.
    """
    cmd = str(cmd).strip()
    if not cmd or cmd.startswith(PREFIJO_LANZAMIENTO) or cmd.startswith(PREFIJO_VIEJO):
        return cmd
    return f"{PREFIJO_LANZAMIENTO} {cmd}"


def instalada(cmd):
    """Si el comando de una app se puede ejecutar de verdad en esta maquina."""
    cmd = str(cmd).strip()
    if not cmd:
        return False
    primero = cmd.split()[0]
    return bool(shutil.which(primero)) or os.access(primero, os.X_OK)


def generar(datos=None):
    """Escribe dock.jsonc. Devuelve (numero de apps, ancho de la barra)."""
    datos = cargar() if datos is None else datos
    apps = datos["apps"]
    if len(apps) > MAX_BOTONES:
        raise SystemExit(
            f"gen-dock: {len(apps)} apps es mas de lo que cubre style.css "
            f"({MAX_BOTONES}). Alarga la lista de #custom-appN antes de seguir.")

    ancho = max(CELDA, CELDA * len(apps))
    ids = [f"app{i + 1}" for i in range(len(apps))]

    # Cada app usa su propio icono si se puede resolver; si no, cae al glifo de la
    # Nerd Font. Se resuelve antes de escribir nada porque decide las dos cosas:
    # el contenido del boton en dock.jsonc y la regla de dock-icons.css.
    rutas = [ruta_icono(app.get("icon_name")) for app in apps]

    lineas = [
        "// ~/dotfiles/waybar/dock.jsonc",
        "//",
        "// GENERADO por ~/dotfiles/hypr/scripts/gen-dock.py — NO EDITAR A MANO:",
        "// cualquier cambio se pierde la proxima vez que se anada o quite una app.",
        "//",
        "// Las apps se editan en ~/dotfiles/waybar/dock-apps.json, o con el clic",
        "// derecho sobre cualquier icono del dock, que abre el gestor.",
        "//",
        "// El aspecto (colores, tamano de la pastilla, redondeo) esta en el bloque",
        "// \"El dock\" de style.css, que si es de escritura a mano.",
        "{",
        '    // "name" define tambien el namespace Wayland de la capa. El demonio de',
        "    // auto-ocultado y los layerrules distinguen las cuatro barras por aqui.",
        '    "name": "waybar-dock",',
        '    "layer": "top",',
        '    "position": "bottom",',
        "",
        f"    // Alto y ancho salen de la cuenta de GEOMETRIA en gen-dock.py:",
        f"    // {len(apps)} apps x {CELDA} px de celda. Fijar el ancho es lo que hace que",
        "    // waybar centre la barra; el resto del borde inferior queda libre para",
        "    // clickar en tus ventanas.",
        f'    "height": {ALTO},',
        f'    "width": {ancho},',
        '    "spacing": 0,',
        "",
        "    // Sin zona exclusiva: el dock nunca le quita sitio a las ventanas, sube",
        "    // por encima de ellas.",
        '    "exclusive": false,',
        "",
        "    // SIGUSR1 se queda con su valor por defecto (toggle), como en las otras",
        "    // barras: la accion hide de waybar no desmapea la superficie.",
        '    "on-sigusr2": "noop",',
        "",
        '    "modules-center": [',
    ]
    for i, mid in enumerate(ids):
        coma = "," if i < len(ids) - 1 else ""
        lineas.append(f'        "custom/{mid}"{coma}')
    lineas += ["    ],", ""]

    for mid, app, ruta in zip(ids, apps, rutas):
        if ruta:
            # Con icono propio el boton no lleva texto: solo un espacio para que
            # el modulo exista. El dibujo entra por CSS (background-image), que es
            # el unico camino que aguanta varios iconos distintos en una barra
            # (ver el comentario de dock-icons.css).
            contenido = " "
        else:
            contenido = f"<span size='{SPAN}%'>{glifo(app)}</span>"
        lineas += [
            f'    // {app.get("label", "")}',
            f'    "custom/{mid}": {{',
            f'        "format": "{contenido}",',
            f'        "tooltip-format": "{escapar(app.get("label", ""))}",',
            f'        "on-click": "{escapar(lanzar(app.get("cmd", "")))}",',
            f'        "on-click-right": "{GESTOR} {mid}"',
            "    },",
        ]
    # La ultima app no lleva coma: se le quita al cierre de su bloque.
    if apps:
        lineas[-1] = "    }"
    lineas += ["}", ""]

    with open(SALIDA, "w") as fh:
        fh.write("\n".join(lineas))

    generar_css(ids, apps, rutas)

    # Un comando que no existe no da error al pulsarlo: lanzar.sh avisa por
    # notificacion, pero mas vale decirlo tambien AQUI, que es cuando todavia se
    # puede arreglar. Es el fallo que dejaba "iconos que no abren nada".
    faltan = [a.get("label") or a.get("cmd") for a in apps if not instalada(a.get("cmd"))]
    for nombre in faltan:
        print(f"aviso: «{nombre}» no esta instalado en esta maquina; su icono no "
              f"abrira nada (quitalo con el clic derecho en el dock)", file=sys.stderr)

    return len(apps), ancho


def generar_css(ids, apps, rutas):
    """Escribe dock-icons.css: la imagen de fondo de cada boton con icono propio.

    Va en un fichero aparte y no en style.css porque esto cambia cada vez que se
    anade o quita una app, y style.css es de escritura a mano. Las propiedades
    comunes (tamano, centrado, no repetir) estan alli; aqui solo la ruta.
    """
    lineas = [
        "/* ~/dotfiles/waybar/dock-icons.css",
        " *",
        " * GENERADO por ~/dotfiles/hypr/scripts/gen-dock.py — NO EDITAR A MANO.",
        " * Lo carga style.css con @import.",
        " *",
        " * Los iconos propios de las apps van como background-image y no con el",
        " * modulo `image` de waybar porque en la 0.15 una barra con DOS modulos",
        " * image se queda invisible entera (alpha 0, sin ningun aviso en el log).",
        " * Con un solo modulo image funciona; con dos, no. Comprobado.",
        " */",
        "",
    ]
    con_icono = 0
    for mid, app, ruta in zip(ids, apps, rutas):
        if not ruta:
            lineas += [f"/* {app.get('label', '')}: sin icono propio, usa el glifo */"]
            continue
        con_icono += 1
        lineas += [
            f"/* {app.get('label', '')} */",
            f'#custom-{mid} {{ background-image: url("{ruta}"); }}',
        ]
    lineas.append("")
    with open(SALIDA_CSS, "w") as fh:
        fh.write("\n".join(lineas))
    return con_icono


def semilla():
    """El dock de partida de una instalacion nueva: terminal y navegador.

    Solo esas dos, y averiguadas en la maquina (ver lib/apps.py). El repo no
    puede traer apps concretas: es publico, y las del autor son iconos muertos en
    cualquier otro equipo. Dos que funcionen valen mas que ocho que no; el resto
    las pone cada uno con el clic derecho.
    """
    entradas = []
    term = apps.terminal()
    if term:
        # El .desktop de la mayoria de terminales se llama a si mismo en
        # minusculas y a secas ("kitty"), que en un tooltip no dice gran cosa.
        term["label"] = f"Terminal — {term['label']}"
        entradas.append(term)
    nav = apps.navegador()
    if nav:
        entradas.append(nav)
    return entradas


def sembrar(forzar=False):
    """Escribe dock-apps.json de cero. Devuelve las apps que dejo puestas."""
    if os.path.exists(DATOS) and not forzar:
        raise SystemExit(f"gen-dock seed: {DATOS} ya existe. "
                         f"Usa --forzar si de verdad quieres reemplazarlo.")
    entradas = semilla()
    datos = {"//": CABECERA_DATOS, "apps": entradas}
    guardar(datos)
    return entradas


def recargar():
    """Le pide al demonio que reinicie el dock para que lea el nuevo config."""
    try:
        fd = os.open(FIFO, os.O_WRONLY | os.O_NONBLOCK)
        try:
            os.write(fd, b"dock:reload\n")
        finally:
            os.close(fd)
        return True
    except OSError:
        return False


def resolver_icono(valor):
    """Acepta el nombre de un glifo (md-discord) o su codigo hexadecimal."""
    valor = valor.strip()
    tabla = nf_icons.iconos()
    if valor in tabla:
        return f"{tabla[valor]:x}"
    try:
        cp = int(valor, 16)
        if 0x20 <= cp <= 0x10FFFF:
            return f"{cp:x}"
    except ValueError:
        pass
    res = nf_icons.buscar(valor, limite=1)
    if res:
        return f"{res[0][1]:x}"
    raise SystemExit(f"gen-dock: no encuentro ningun glifo para «{valor}». "
                     f"Prueba: gen-dock.py icons {valor}")


def main():
    ap = argparse.ArgumentParser(add_help=True, description="Genera el dock de waybar")
    ap.add_argument("accion", nargs="?", default="gen",
                    choices=["gen", "list", "add", "remove", "icons", "seed"])
    ap.add_argument("resto", nargs="*")
    ap.add_argument("--forzar", action="store_true",
                    help="seed: reemplaza dock-apps.json aunque ya exista")
    ap.add_argument("--icon", help="glifo de la Nerd Font (nombre o hex), de respaldo")
    ap.add_argument("--icon-name", help="icono propio de la app (campo Icon= de su .desktop)")
    ap.add_argument("--label"), ap.add_argument("--cmd")
    ap.add_argument("--no-reload", action="store_true")
    args = ap.parse_args()

    if args.accion == "seed":
        puestas = sembrar(forzar=args.forzar)
        if not puestas:
            print("gen-dock seed: no encuentro ni terminal ni navegador en esta "
                  "maquina; el dock queda vacio (anade apps con el clic derecho)",
                  file=sys.stderr)
        for entrada in puestas:
            print(f"puesta: {entrada['label']:28} {entrada['cmd']}")
        n, ancho = generar()
        print(f"dock.jsonc generado: {n} apps, {ancho} px de ancho, {ALTO} de alto")
        if not args.no_reload:
            recargar()
        return

    if args.accion == "list":
        for i, app in enumerate(cargar()["apps"], 1):
            ruta = ruta_icono(app.get("icon_name"))
            if ruta:
                icono = f"icono propio: {os.path.basename(ruta)}"
            elif app.get("icon"):
                icono = f"glifo U+{app['icon'].upper()}"
            else:
                icono = "glifo generico (no encuentro su icono)"
            falta = "" if instalada(app.get("cmd")) else "  [NO INSTALADA]"
            print(f"{i:2}. {glifo(app)}  {app.get('label', ''):32} "
                  f"{app.get('cmd', ''):34} {icono}{falta}")
        return

    if args.accion == "icons":
        termino = " ".join(args.resto) or (args.icon or "")
        for nombre, cp in nf_icons.buscar(termino, limite=40):
            print(f"{chr(cp)}  U+{cp:X}  {nombre}")
        return

    datos = cargar()

    if args.accion == "add":
        if not args.cmd or not (args.icon or args.icon_name):
            raise SystemExit("gen-dock add: hace falta --cmd y uno de "
                             "--icon-name (icono propio) o --icon (glifo)")
        nueva = {"label": args.label or args.cmd, "cmd": args.cmd}
        if args.icon_name:
            nueva["icon_name"] = args.icon_name
            if not ruta_icono(args.icon_name):
                print(f"aviso: no encuentro el icono «{args.icon_name}» en el tema; "
                      f"se usara el glifo de respaldo si lo hay")
        if args.icon:
            nueva["icon"] = resolver_icono(args.icon)
        datos["apps"].append(nueva)
        guardar(datos)

    elif args.accion == "remove":
        try:
            idx = int(args.resto[0])
        except (IndexError, ValueError):
            raise SystemExit("gen-dock remove: dame el indice que sale en «list»")
        if not 1 <= idx <= len(datos["apps"]):
            raise SystemExit(f"gen-dock remove: el indice {idx} no existe")
        fuera = datos["apps"].pop(idx - 1)
        guardar(datos)
        print(f"quitada: {fuera.get('label', '')}")

    n, ancho = generar(datos)
    print(f"dock.jsonc generado: {n} apps, {ancho} px de ancho, {ALTO} de alto")
    if not args.no_reload:
        print("dock recargado" if recargar() else "el demonio del dock no responde "
              "(no pasa nada: al arrancar leera el nuevo config)")


if __name__ == "__main__":
    main()
