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
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import nf_icons  # noqa: E402

WAYBAR = os.path.expanduser("~/dotfiles/waybar")
DATOS = os.path.join(WAYBAR, "dock-apps.json")
SALIDA = os.path.join(WAYBAR, "dock.jsonc")
# Hoja de estilo generada con la imagen de fondo de cada boton (el icono propio
# de la app). style.css la carga con @import y no hay que tocarla a mano.
SALIDA_CSS = os.path.join(WAYBAR, "dock-icons.css")
GESTOR = "$HOME/dotfiles/hypr/scripts/dock-manager.py"

# Las apps se lanzan a traves de uwsm para que cada una viva en su PROPIO scope
# de systemd (app.slice/app-graphical.slice/app-*.scope). Sin esto caen todas en
# `session.slice/wayland-wm@hyprland.desktop.service`, el mismo cgroup que
# Hyprland, waybar y mpvpaper — comprobado el 2026-07-27. Y eso rompe el
# congelado selectivo al bloquear la pantalla (ver scripts/lib/congelar.py): no
# hay forma de parar una app sin parar de paso el compositor.
#
# El comando que guarda dock-apps.json sigue siendo el limpio ("brave", "steam
# steam://rungameid/..."); el prefijo se pone aqui, al generar.
PREFIJO_LANZAMIENTO = "uwsm app --"

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


def cargar():
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
    """Antepone el prefijo de uwsm al comando de una app (ver PREFIJO_LANZAMIENTO).

    Si el comando ya lo lleva, se deja como esta: asi regenerar el dock dos veces
    no acaba con `uwsm app -- uwsm app -- brave`.
    """
    cmd = str(cmd).strip()
    if not cmd or cmd.startswith(PREFIJO_LANZAMIENTO):
        return cmd
    return f"{PREFIJO_LANZAMIENTO} {cmd}"


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
                    choices=["gen", "list", "add", "remove", "icons"])
    ap.add_argument("resto", nargs="*")
    ap.add_argument("--icon", help="glifo de la Nerd Font (nombre o hex), de respaldo")
    ap.add_argument("--icon-name", help="icono propio de la app (campo Icon= de su .desktop)")
    ap.add_argument("--label"), ap.add_argument("--cmd")
    ap.add_argument("--no-reload", action="store_true")
    args = ap.parse_args()

    if args.accion == "list":
        for i, app in enumerate(cargar()["apps"], 1):
            ruta = ruta_icono(app.get("icon_name"))
            if ruta:
                icono = f"icono propio: {os.path.basename(ruta)}"
            elif app.get("icon"):
                icono = f"glifo U+{app['icon'].upper()}"
            else:
                icono = "glifo generico (no encuentro su icono)"
            print(f"{i:2}. {glifo(app)}  {app.get('label', ''):32} "
                  f"{app.get('cmd', ''):34} {icono}")
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
