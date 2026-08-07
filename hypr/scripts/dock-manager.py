#!/usr/bin/env python3
"""
~/dotfiles/hypr/scripts/dock-manager.py

El gestor del dock: la ventanita que sale al hacer CLIC DERECHO en cualquier
icono del dock. Dos cosas, las que se piden a un dock:

    +  Anadir aplicacion   -> busca entre las apps instaladas y la pega al dock
    -  Quitar aplicacion   -> lista lo que hay puesto y lo saca

Igual que el panel del calendario, no es una ventana normal sino una capa de
Wayland (gtk-layer-shell) anclada al borde de abajo, encima del dock: Hyprland no
la cuenta como ventana, asi que no rompe el mosaico ni roba sitio.

Quien manda de verdad es waybar/dock-apps.json; aqui solo se edita esa lista y se
llama a gen-dock.py, que regenera dock.jsonc y le pide al demonio que reinicie el
dock. Asi el mismo camino sirve para el clic derecho, para la terminal y para un
asistente.

Cada app entra al dock con SU PROPIO icono, el mismo que le ves en el lanzador
(SUPER+D): se guarda el campo `Icon=` de su .desktop y gen-dock.py lo resuelve a
un fichero. Solo si una app no trae icono utilizable se pide elegir un glifo de la
Nerd Font, buscandolo por nombre entre los ~10.000 que trae (lib/nf_icons.py).

Uso:  dock-manager.py [appN] [--anadir|--quitar]
      appN es el boton sobre el que se hizo el clic derecho; sirve para ofrecer
      "quitar justo esta" sin tener que buscarla en la lista. Las banderas abren
      directamente en una pantalla, para colgarlo de un atajo de teclado.
"""

import json
import os
import re
import signal
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import canales  # noqa: E402

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, Gdk, GLib, GtkLayerShell, Pango  # noqa: E402

import nf_icons  # noqa: E402

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(SCRIPTS, "gen-dock.py")
TERMINAL = os.path.join(SCRIPTS, "terminal.sh")
# La raiz del repo, resolviendo el enlace simbolico: a este script se le puede
# llamar por ~/.config/hypr/... o por ~/.local/bin/..., y realpath() lleva
# hasta el fichero de verdad dentro del repo, se haya clonado donde se haya
# clonado. Antes ponia "~/dotfiles/...", que obligaba a clonar justo ahi.
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
DATOS_DOCK = os.path.join(RAIZ, "waybar/dock-apps.json")

ANCHO = 460
# Hueco por debajo del panel para que quede apoyado justo encima del dock sin
# taparlo. Se pregunta el alto real de la capa del dock a Hyprland (cambia si se
# toca ALTO en gen-dock.py); esto es solo el valor de reserva.
MARGEN_ABAJO = 88
# Aire entre el panel y el dock: ahora que el panel lleva borde completo, pegarlo
# al dock haria que se leyeran como una sola pieza cortada.
SEPARACION = 10
# Segundos con el puntero lejos antes de cerrarse solo. Solo aplica en el menu:
# en cuanto entras a anadir o quitar, se queda hasta que decidas.
CIERRE_DELAY = 3.0
# Cuantos iconos se ofrecen por busqueda y cuantos caben por fila.
ICONOS_MAX = 40
ICONOS_FILA = 8

RUNTIME = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
PID_PATH = os.path.join(RUNTIME, "dock-manager.pid")
# Con la firma de la sesion; ver lib/canales.py.
FIFO_BARRA = canales.canal_barras()

# Glifos de la interfaz, por codigo y no por el caracter en si: los de la zona de
# uso privado se corrompen al pasar por editores y herramientas de texto.
GLIFO_MAS = chr(0xF0419)     # md-plus_circle_outline
GLIFO_MENOS = chr(0xF0377)   # md-minus_circle_outline

# Directorios donde CUALQUIER instalador deja .desktop, mas alla de los que
# marque la sesion. Van como red de seguridad, no como lista principal: los de
# Flatpak y Snap NO existen hasta que se instala el primer paquete de cada uno,
# y si el usuario instala su primer flatpak sin volver a iniciar sesion, la
# sesion sigue con el $XDG_DATA_DIRS viejo, sin ellos. El caso de un usuario
# instalando su primera app es justo el que tiene que funcionar.
DIRS_EXTRA = [
    "/var/lib/flatpak/exports/share/applications",
    "/var/lib/snapd/desktop/applications",
]

CSS = b"""
window {
    /* Translucido como la terminal (kitty va a background_opacity 0.6): al estar
     * el dock invisible en reposo, una ventana opaca colgando de la nada se veia
     * pegote. Asi se ve el wallpaper por detras y se lee como parte del conjunto.
     * El borde va COMPLETO y con las cuatro esquinas redondeadas: antes le
     * faltaba el de abajo, dando por hecho que se apoyaba en un dock visible. */
    background-color: rgba(20, 8, 38, 0.68);
    border: 1px solid #b16cff;
    border-radius: 12px;
    color: #e0def4;
    font-family: "MesloLGS Nerd Font";
    font-size: 13px;
}
#titulo { font-size: 15px; font-weight: bold; padding: 2px 2px 8px 2px; }
#pista  { color: #6e6a86; font-size: 11px; padding-top: 6px; }

/* Las dos opciones del menu y las filas de las listas: mismo aspecto de fila
 * clickable, apagada en reposo y encendida en amatista al pasar por encima. */
#fila {
    background-color: rgba(177, 108, 255, 0.06);
    border: 1px solid rgba(177, 108, 255, 0.20);
    border-radius: 9px;
    padding: 9px 12px;
    margin: 3px 0;
    color: #e0def4;
    transition: background-color 150ms ease-in-out, border-color 150ms ease-in-out;
}
#fila:hover { background-color: rgba(177, 108, 255, 0.22); border-color: #b16cff; }
/* Propo tambien aqui: es la variante de la Nerd Font que centra los iconos
 * dentro de su caja (ver el bloque del dock en waybar/style.css). */
#fila-glifo {
    font-family: "MesloLGS Nerd Font Propo";
    font-size: 22px; padding-right: 12px; color: #b16cff;
    min-width: 26px;
}
#fila-titulo  { font-weight: bold; }
#fila-sub     { color: #6e6a86; font-size: 11px; }
#fila-marca   { color: #b16cff; font-size: 11px; }

#volver {
    background: transparent; border: none; color: #b16cff;
    padding: 0 8px 0 0; margin: 0; font-size: 15px;
}
#volver:hover { color: #e0def4; }

entry {
    background-color: rgba(0, 0, 0, 0.35);
    border: 1px solid rgba(177, 108, 255, 0.35);
    border-radius: 8px;
    padding: 6px 8px;
    color: #e0def4;
    caret-color: #b16cff;
}
entry:focus { border-color: #b16cff; }

scrolledwindow { border: none; }
scrollbar { background: transparent; }
scrollbar slider {
    background-color: rgba(177, 108, 255, 0.35);
    border-radius: 6px; min-width: 6px; min-height: 24px;
}
scrollbar slider:hover { background-color: #b16cff; }

/* Rejilla de iconos del paso "elige un icono". */
#icono {
    background-color: rgba(177, 108, 255, 0.06);
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 4px;
    margin: 2px;
    min-width: 40px; min-height: 40px;
    color: #e0def4;
    font-family: "MesloLGS Nerd Font Propo";
    font-size: 24px;
}
#icono:hover { background-color: rgba(177, 108, 255, 0.26); border-color: #b16cff; }
#icono.sugerido { border-color: rgba(177, 108, 255, 0.55); }

#aviso { color: #eb6f92; font-size: 11px; padding-top: 4px; }
"""


def avisar_barra(mensaje):
    """Escribe una orden en el FIFO del demonio de las barras, si esta vivo."""
    try:
        fd = os.open(FIFO_BARRA, os.O_WRONLY | os.O_NONBLOCK)
        try:
            os.write(fd, (mensaje + "\n").encode())
        finally:
            os.close(fd)
    except OSError:
        pass


def _hyprctl(comando):
    import socket as sk
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not sig:
        return ""
    ruta = os.path.join(RUNTIME, "hypr", sig, ".socket.sock")
    try:
        with sk.socket(sk.AF_UNIX, sk.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect(ruta)
            s.sendall(comando.encode())
            trozos = []
            while True:
                trozo = s.recv(8192)
                if not trozo:
                    break
                trozos.append(trozo)
        return b"".join(trozos).decode(errors="replace")
    except OSError:
        return ""


def alto_dock():
    """Alto real de la capa del dock, para apoyar el panel justo encima.

    Se le pregunta al compositor en vez de repetir aqui el numero de
    gen-dock.py: asi cambiar el tamano del dock no deja el panel flotando.
    """
    try:
        data = json.loads(_hyprctl("j/layers"))
    except ValueError:
        return MARGEN_ABAJO
    for monitor in data.values():
        for capas in monitor.get("levels", {}).values():
            for capa in capas:
                if capa.get("namespace") == "waybar-dock":
                    return capa["h"]
    return MARGEN_ABAJO


def cursor_pos():
    """(x, y) del puntero segun Hyprland; None si no se puede saber.

    Se pregunta al compositor y no a GTK porque en Wayland una app no puede
    consultar el puntero cuando no esta encima de ella, que es justo el caso que
    hay que detectar para cerrarse."""
    import socket as sk
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not sig:
        return None
    ruta = os.path.join(RUNTIME, "hypr", sig, ".socket.sock")
    try:
        with sk.socket(sk.AF_UNIX, sk.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect(ruta)
            s.sendall(b"cursorpos")
            datos = s.recv(256).decode(errors="replace").strip()
        x, y = datos.split(",")
        return int(x), int(y)
    except (OSError, ValueError):
        return None


# --- Las apps instaladas -----------------------------------------------------

CAMPOS_EXEC = re.compile(r"%[fFuUdDnNickvm]")
MARCAS_FLATPAK = re.compile(r"(?<!\S)@@u?(?!\S)")


def dirs_apps():
    """Los directorios de .desktop, de mas prioridad a menos.

    Se calcula en cada escaneo en vez de fijarlo en una constante al arrancar:
    una lista escrita a mano se queda corta en cuanto el usuario instala por una
    via que no estaba prevista. Manda $XDG_DATA_DIRS, que es donde la sesion
    declara de verdad de donde salen las apps (ahi es donde Flatpak se anade
    solo via /etc/profile.d), y detras se anaden los DIRS_EXTRA que no estuvieran
    ya. El orden importa porque decide quien gana al deduplicar.
    """
    inicio = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    # Los valores por defecto de la spec, para cuando la variable no viene puesta.
    resto = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    candidatos = [os.path.join(inicio, "applications")]
    candidatos += [os.path.join(d, "applications") for d in resto.split(":") if d]
    # El Flatpak de usuario cuelga del mismo sitio que el resto de datos del
    # usuario, asi que se saca de `inicio` y no de una ruta escrita a mano.
    candidatos.append(os.path.join(inicio, "flatpak/exports/share/applications"))
    candidatos += DIRS_EXTRA

    dirs, vistos = [], set()
    for carpeta in candidatos:
        # Por ruta real: en esta maquina $XDG_DATA_DIRS trae los exports de
        # Flatpak repetidos, y sin normalizar se escanearia dos veces cada uno.
        try:
            clave = os.path.realpath(carpeta)
        except OSError:
            continue
        if clave in vistos or not os.path.isdir(carpeta):
            continue
        vistos.add(clave)
        dirs.append(carpeta)
    return dirs


def firma_apps():
    """Estado de los directorios de .desktop, para saber si hay que reescanear.

    Basta con la fecha de los directorios: al instalar o desinstalar algo cambia
    la del directorio que gana o pierde el fichero, y los que aparecen de cero
    (el primer flatpak, el primer snap) cambian la lista de directorios en si.
    No se guarda nada en disco a proposito: un cache en ~/.cache que hubiera que
    borrar a mano es exactamente el fallo que se esta arreglando.
    """
    firma = []
    for carpeta in dirs_apps():
        for raiz, _, _ in os.walk(carpeta):
            try:
                firma.append((raiz, os.stat(raiz).st_mtime_ns))
            except OSError:
                continue
    return tuple(firma)


def apps_instaladas():
    """Lista de (nombre, comando, comentario, id, icono) leyendo los .desktop.

    `icono` es el campo Icon= tal cual: el nombre del icono PROPIO de la app en el
    tema de iconos. Es lo que se guarda en el dock, y lo que hace que la app
    aparezca ahi con su icono de verdad y no con un glifo elegido a mano.

    Se deduplica por Desktop File ID y no por nombre de fichero, que es lo que
    manda la spec XDG: el id es la ruta relativa al directorio de aplicaciones
    con las barras cambiadas por guiones, asi que hay que recorrer tambien los
    subdirectorios (hay paquetes que meten sus .desktop en uno). Si el mismo id
    sale en varios directorios gana el primero, o sea el de mas prioridad: es lo
    que permite que un .desktop en ~/.local/share/applications pise al del
    sistema, que es para lo que existe ese directorio.
    """
    apps, ids = {}, set()
    for carpeta in dirs_apps():
        for raiz, _, ficheros in os.walk(carpeta):
            for nombre in sorted(ficheros):
                if not nombre.endswith(".desktop"):
                    continue
                ruta = os.path.join(raiz, nombre)
                ident = os.path.relpath(ruta, carpeta)[:-8].replace(os.sep, "-")
                # El id se marca como visto aunque el .desktop acabe descartado:
                # un fichero con NoDisplay=true en ~/.local/share/applications es
                # precisamente como se oculta una app del sistema, y si el de
                # abajo pudiera colarse en su lugar no serviria de nada.
                if ident in ids:
                    continue
                ids.add(ident)
                datos = _leer_desktop(ruta, ident)
                if datos:
                    apps[ident] = datos
    return sorted(apps.values(), key=lambda a: a[0].lower())


def _leer_desktop(ruta, ident):
    seccion = None
    campos = {}
    try:
        with open(ruta, encoding="utf-8", errors="replace") as fh:
            for linea in fh:
                linea = linea.strip()
                if linea.startswith("["):
                    # Solo interesa la entrada principal: las secciones
                    # [Desktop Action ...] son los submenus del clic derecho.
                    if seccion == "Desktop Entry":
                        break
                    seccion = linea.strip("[]")
                    continue
                if seccion != "Desktop Entry" or "=" not in linea:
                    continue
                clave, valor = linea.split("=", 1)
                campos[clave.strip()] = valor.strip()
    except OSError:
        return None

    # Se descarta SOLO lo que no es una app lanzable o lo que su propio autor
    # marco como no mostrable, y nada mas:
    #   Type != Application  -> son Link o Directory, no hay nada que ejecutar.
    #   NoDisplay=true       -> el .desktop existe solo para asociar tipos de
    #                           fichero o para ser lanzado por otra app.
    #   Hidden=true           -> equivale a borrado, la spec obliga a ignorarlo.
    #   sin Exec              -> no habria comando que poner en el dock.
    # A proposito NO se filtra por OnlyShowIn/NotShowIn: eso es para que GNOME y
    # KDE se escondan mutuamente sus paneles de ajustes, y como Hyprland no es
    # ninguno de los dos, aplicarlo tiraria la mitad del menu del sistema. Ni por
    # Terminal=true: una app de consola es perfectamente valida en el dock, y mas
    # abajo se le da su terminal.
    if campos.get("Type", "Application") != "Application":
        return None
    if campos.get("NoDisplay", "").lower() == "true":
        return None
    if campos.get("Hidden", "").lower() == "true":
        return None
    ejecutar = campos.get("Exec", "").strip()
    if not ejecutar:
        return None

    # Nombre en espanol si el .desktop lo trae.
    nombre = (campos.get("Name[es]") or campos.get("Name")
              or os.path.basename(ruta)[:-8])
    comentario = campos.get("Comment[es]") or campos.get("Comment") or ""
    comando = CAMPOS_EXEC.sub("", ejecutar).replace('"%c"', "")
    # Flatpak envuelve los ficheros a abrir entre marcas `@@u ... @@` para
    # pasarlos por el portal. Quitados los codigos de campo esas marcas se
    # quedan sueltas en la linea y flatpak aborta con un error de sintaxis.
    comando = MARCAS_FLATPAK.sub("", comando)
    comando = " ".join(comando.split())
    if campos.get("Terminal", "").lower() == "true":
        # Una app de consola sin terminal no se ve: se le pone la del sistema.
        # NO se nombra ninguna terminal aqui. Antes ponia `kitty -e` y en un
        # equipo sin kitty el icono no abria nada. Quien sabe cual hay instalada
        # es terminal.sh, y de paso le pone clase propia a la ventana.
        #
        # --sin-uwsm porque este comando lo lanza lanzar.sh, que ya mete la app
        # en su scope de systemd: anidar un uwsm dentro de otro no vale de nada.
        comando = f"{TERMINAL} --sin-uwsm dock-term {comando}"
    return (nombre, comando, comentario, ident, campos.get("Icon", "").strip())


def icono_existe(nombre):
    """True si el icono de la app se puede resolver a un fichero de verdad.

    Hace falta saberlo ANTES de anadir: si la app no tiene icono utilizable, el
    boton saldria vacio, y en ese caso se cae al paso de elegir un glifo.
    """
    if not nombre:
        return False
    if os.path.isabs(nombre):
        return os.path.exists(nombre)
    return Gtk.IconTheme.get_default().lookup_icon(nombre, 128, 0) is not None


# --- El panel ----------------------------------------------------------------

class Gestor(Gtk.Window):
    def __init__(self, pulsado=None, pantalla=None):
        super().__init__()
        self.pulsado = pulsado          # "appN" del icono con el que se abrio
        self.iconos = nf_icons.iconos()
        self.apps_cache = None          # se lee al entrar en "anadir"
        self.apps_firma = None          # estado de los directorios al leerlo
        self.auto_cierre = True         # solo mientras se este en el menu
        self.margen_abajo = alto_dock() + SEPARACION

        self._montar_capa()
        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.caja.set_border_width(12)
        self.add(self.caja)

        self.connect("destroy", Gtk.main_quit)
        self.connect("key-press-event", self._tecla)

        if pantalla == "anadir":
            self._pantalla_anadir()
        elif pantalla == "quitar":
            self._pantalla_quitar()
        else:
            self._menu()

        # El cierre no va por foco: con focus_follows_mouse basta rozar una
        # ventana para perderlo, y el panel se cerraria antes de llegar a el.
        self._fuera_desde = None
        GLib.timeout_add(200, self._vigilar_puntero)
        self.show_all()

    def _montar_capa(self):
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, self.margen_abajo)
        # ON_DEMAND: coge el teclado al clickarlo (hace falta para escribir en la
        # busqueda y para Escape) pero no se lo roba a la app que estabas usando
        # solo por aparecer.
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)
        self.set_size_request(ANCHO, -1)

    # --- Utilidades de construccion ---

    def _limpiar(self):
        for hijo in self.caja.get_children():
            self.caja.remove(hijo)

    def _cabecera(self, texto, volver=None):
        caja = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        if volver:
            boton = Gtk.Button(label="‹")
            boton.set_name("volver")
            boton.connect("clicked", lambda *_: volver())
            caja.pack_start(boton, False, False, 0)
        etiqueta = Gtk.Label(label=texto, xalign=0)
        etiqueta.set_name("titulo")
        caja.pack_start(etiqueta, True, True, 0)
        self.caja.pack_start(caja, False, False, 0)

    def _fila(self, glifo, titulo, sub="", marca="", accion=None, icono=None):
        boton = Gtk.Button()
        boton.set_name("fila")
        caja = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        if icono:
            # El icono propio de la app, el mismo que se vera en el dock. Se pinta
            # aqui para que la lista se lea como el lanzador (SUPER+D) y sepas de
            # antemano con que icono va a quedar.
            img = Gtk.Image()
            if os.path.isabs(icono):
                img.set_from_file(icono)
            else:
                img.set_from_icon_name(icono, Gtk.IconSize.LARGE_TOOLBAR)
            img.set_pixel_size(26)
            img.set_margin_end(12)
            caja.pack_start(img, False, False, 0)
        elif glifo:
            g = Gtk.Label(label=glifo)
            g.set_name("fila-glifo")
            caja.pack_start(g, False, False, 0)

        textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        t = Gtk.Label(label=titulo, xalign=0)
        t.set_name("fila-titulo")
        t.set_ellipsize(Pango.EllipsizeMode.END)
        textos.pack_start(t, False, False, 0)
        if sub:
            s = Gtk.Label(label=sub, xalign=0)
            s.set_name("fila-sub")
            s.set_ellipsize(Pango.EllipsizeMode.END)
            textos.pack_start(s, False, False, 0)
        caja.pack_start(textos, True, True, 0)

        if marca:
            m = Gtk.Label(label=marca)
            m.set_name("fila-marca")
            caja.pack_start(m, False, False, 0)

        boton.add(caja)
        if accion:
            boton.connect("clicked", lambda *_: accion())
        return boton

    def _lista_scroll(self, alto=300):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(alto)
        scroll.set_max_content_height(alto)
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scroll.add(caja)
        self.caja.pack_start(scroll, True, True, 0)
        return caja

    def _pista(self, texto):
        etiqueta = Gtk.Label(label=texto, xalign=0)
        etiqueta.set_name("pista")
        etiqueta.set_line_wrap(True)
        self.caja.pack_start(etiqueta, False, False, 0)

    # --- Pantalla 1: el menu ---

    def _menu(self):
        self.auto_cierre = True
        self._limpiar()
        self._cabecera("Dock")

        apps = self._apps_dock()
        self.caja.pack_start(
            self._fila(GLIFO_MAS, "Anadir aplicacion",
                       "busca entre las apps instaladas",
                       accion=self._pantalla_anadir), False, False, 0)

        sub = "no hay ninguna puesta" if not apps else f"{len(apps)} en el dock ahora"
        self.caja.pack_start(
            self._fila(GLIFO_MENOS, "Quitar aplicacion", sub,
                       accion=self._pantalla_quitar), False, False, 0)

        self._pista("Escape cierra. El orden de los iconos es el de la lista, "
                    "y se edita en waybar/dock-apps.json.")
        self.show_all()

    # --- Pantalla 2: anadir ---

    def _pantalla_anadir(self):
        self.auto_cierre = False
        self._limpiar()
        self._cabecera("Anadir aplicacion", volver=self._menu)

        self.busqueda = Gtk.Entry()
        self.busqueda.set_placeholder_text("escribe para filtrar…")
        self.busqueda.connect("changed", lambda *_: self._pintar_apps())
        self.caja.pack_start(self.busqueda, False, False, 0)

        self.lista_apps = self._lista_scroll(320)
        # El escaneo se repite si algun directorio de .desktop ha cambiado desde
        # la ultima vez, para que instalar una app con el gestor abierto y volver
        # a entrar en "anadir" la encuentre sin tener que cerrar nada.
        firma = firma_apps()
        if self.apps_cache is None or self.apps_firma != firma:
            self.apps_cache = apps_instaladas()
            self.apps_firma = firma
        self._pintar_apps()
        self._pista(f"{len(self.apps_cache)} aplicaciones instaladas.")
        self.show_all()
        self.busqueda.grab_focus()

    def _pintar_apps(self):
        for hijo in self.lista_apps.get_children():
            self.lista_apps.remove(hijo)
        filtro = self.busqueda.get_text().strip().lower()
        puestas = {a.get("cmd", "") for a in self._apps_dock()}

        mostradas = 0
        for nombre, comando, comentario, ident, icono in self.apps_cache:
            if filtro and filtro not in nombre.lower() and filtro not in ident.lower():
                continue
            ya = comando in puestas
            self.lista_apps.pack_start(
                self._fila("", nombre, comentario or comando,
                           marca="ya esta" if ya else "",
                           icono=icono if icono_existe(icono) else None,
                           accion=lambda n=nombre, c=comando, i=ident, ic=icono:
                               self._anadir_app(n, c, i, ic)),
                False, False, 0)
            mostradas += 1
            if mostradas >= 200:   # la lista completa son cientos: se corta
                break
        if not mostradas:
            vacio = Gtk.Label(label="nada encontrado", xalign=0)
            vacio.set_name("fila-sub")
            self.lista_apps.pack_start(vacio, False, False, 0)
        self.lista_apps.show_all()

    # --- Anadir: el camino normal ---

    def _anadir_app(self, nombre, comando, ident, icono):
        """Anade la app con SU PROPIO icono, sin preguntar nada mas.

        Solo si la app no tiene un icono utilizable se pasa al selector de glifos:
        antes ese paso era obligatorio y no tenia sentido, porque la app ya trae su
        icono y es el que se espera ver en el dock.
        """
        if icono_existe(icono):
            self._gen(["add", "--icon-name", icono, "--label", nombre, "--cmd", comando])
            self.close()
        else:
            self._pantalla_icono(nombre, comando, ident)

    # --- Pantalla de respaldo: elegir un glifo ---

    def _pantalla_icono(self, nombre, comando, ident):
        self.auto_cierre = False
        self._limpiar()
        self._cabecera(f"Icono para {nombre}", volver=self._pantalla_anadir)
        aviso = Gtk.Label(
            label=f"{nombre} no trae un icono propio utilizable, "
                  f"asi que elige un glifo:", xalign=0)
        aviso.set_name("fila-sub")
        aviso.set_line_wrap(True)
        self.caja.pack_start(aviso, False, False, 0)

        sugerido = nf_icons.sugerir(nombre, ident, comando.split()[0] if comando else "",
                                    tabla=self.iconos)
        self.icono_busqueda = Gtk.Entry()
        self.icono_busqueda.set_placeholder_text("busca un icono: firefox, folder, gamepad…")
        # Se arranca con el nombre de la app como busqueda: casi siempre acierta.
        primera = re.split(r"[\s\-_.]+", nombre.strip())[0].lower()
        self.icono_busqueda.set_text(primera)
        self.icono_busqueda.connect("changed", lambda *_: self._pintar_iconos())
        self.caja.pack_start(self.icono_busqueda, False, False, 0)

        self.rejilla_caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.caja.pack_start(self.rejilla_caja, True, True, 0)

        self.destino = (nombre, comando)
        self.sugerido = sugerido
        self._pintar_iconos()
        self._pista("Clic en un icono para anadir la app al dock. "
                    "El icono se puede cambiar luego quitando y volviendo a anadir.")
        self.show_all()
        self.icono_busqueda.grab_focus()

    def _pintar_iconos(self):
        for hijo in self.rejilla_caja.get_children():
            self.rejilla_caja.remove(hijo)

        termino = self.icono_busqueda.get_text()
        aciertos = nf_icons.buscar(termino, limite=ICONOS_MAX, tabla=self.iconos)
        if not aciertos and self.sugerido:
            aciertos = [self.sugerido]

        if not aciertos:
            aviso = Gtk.Label(label="ningun icono con ese nombre — prueba otra palabra "
                                    "(en ingles: folder, game, music, shield…)", xalign=0)
            aviso.set_name("aviso")
            aviso.set_line_wrap(True)
            self.rejilla_caja.pack_start(aviso, False, False, 0)
            self.rejilla_caja.show_all()
            return

        fila = None
        for i, (nombre_icono, cp) in enumerate(aciertos):
            if i % ICONOS_FILA == 0:
                fila = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
                self.rejilla_caja.pack_start(fila, False, False, 0)
            boton = Gtk.Button(label=chr(cp))
            boton.set_name("icono")
            boton.set_tooltip_text(nombre_icono)
            if self.sugerido and nombre_icono == self.sugerido[0]:
                boton.get_style_context().add_class("sugerido")
            boton.connect("clicked", lambda _b, c=cp: self._anadir(c))
            fila.pack_start(boton, False, False, 0)
        self.rejilla_caja.show_all()

    # --- Pantalla 4: quitar ---

    def _pantalla_quitar(self):
        self.auto_cierre = False
        self._limpiar()
        self._cabecera("Quitar del dock", volver=self._menu)

        apps = self._apps_dock()
        caja = self._lista_scroll(min(320, max(80, 58 * len(apps))))
        # El indice del boton con el que se abrio el gestor: se marca para poder
        # quitar "esta misma" sin buscarla.
        pulsado_idx = None
        if self.pulsado and self.pulsado.startswith("app"):
            try:
                pulsado_idx = int(self.pulsado[3:]) - 1
            except ValueError:
                pass

        for i, app in enumerate(apps):
            try:
                glifo = chr(int(str(app.get("icon", "")), 16))
            except ValueError:
                glifo = "?"
            icono = app.get("icon_name")
            caja.pack_start(
                self._fila(glifo, app.get("label", ""), app.get("cmd", ""),
                           marca="← clickaste esta" if i == pulsado_idx else "quitar",
                           icono=icono if icono_existe(icono) else None,
                           accion=lambda n=i + 1: self._quitar(n)),
                False, False, 0)
        if not apps:
            vacio = Gtk.Label(label="el dock esta vacio", xalign=0)
            vacio.set_name("fila-sub")
            caja.pack_start(vacio, False, False, 0)
        self._pista("Se quita al primer clic, sin confirmar: volver a anadirla son "
                    "dos clics.")
        self.show_all()

    # --- Acciones sobre los datos ---

    def _apps_dock(self):
        """Las apps que hay puestas ahora. Se lee el JSON de datos directamente:
        para LEER no hace falta pasar por gen-dock.py, que es quien ESCRIBE."""
        try:
            with open(DATOS_DOCK) as fh:
                return json.load(fh).get("apps", [])
        except (OSError, ValueError):
            return []

    def _anadir(self, cp):
        nombre, comando = self.destino
        self._gen(["add", "--icon", f"{cp:x}", "--label", nombre, "--cmd", comando])
        self.close()

    def _quitar(self, indice):
        self._gen(["remove", str(indice)])
        # No se cierra: quitar dos seguidas es lo normal.
        self.pulsado = None
        self._pantalla_quitar()

    def _gen(self, argumentos):
        salida = subprocess.run([GEN] + argumentos, capture_output=True, text=True)
        # gen-dock.py reinicia el dock, y una barra recien nacida vuelve a su
        # cuenta atras de auto-ocultado. Se le repite la orden de quedarse quieta:
        # mientras este gestor siga abierto, el dock no se esconde.
        avisar_barra("dock:hold")
        if salida.returncode != 0:
            aviso = Gtk.Label(label=(salida.stderr or "gen-dock fallo").strip(), xalign=0)
            aviso.set_name("aviso")
            aviso.set_line_wrap(True)
            self.caja.pack_start(aviso, False, False, 0)
            self.caja.show_all()

    # --- Ciclo de vida ---

    def _vigilar_puntero(self):
        """Cierra el panel cuando el puntero lleva un rato lejos.

        Solo mientras se este en el menu: si estas escribiendo en la busqueda,
        que se cierre porque el raton esta en otro sitio seria absurdo."""
        if not self.auto_cierre:
            self._fuera_desde = None
            return True
        pos = cursor_pos()
        if pos is None:
            return True
        x, y = pos
        alto = self.get_allocated_height()
        ancho = self.get_allocated_width()
        monitor = Gdk.Display.get_default().get_monitor(0)
        geo = monitor.get_geometry() if monitor else None
        pantalla_w = geo.width if geo else 1920
        pantalla_h = geo.height if geo else 1080
        izq = (pantalla_w - ancho) / 2
        arriba = pantalla_h - self.margen_abajo - alto

        dentro_panel = izq <= x <= izq + ancho and arriba <= y <= arriba + alto
        # La franja del dock cuenta como dentro: bajar del panel al dock no debe
        # disparar el cierre por el camino.
        dentro_dock = y >= pantalla_h - self.margen_abajo

        if dentro_panel or dentro_dock:
            self._fuera_desde = None
        else:
            ahora = GLib.get_monotonic_time() / 1_000_000
            if self._fuera_desde is None:
                self._fuera_desde = ahora
            elif ahora - self._fuera_desde >= CIERRE_DELAY:
                self.close()
                return False
        return True

    def _tecla(self, _w, ev):
        if Gdk.keyval_name(ev.keyval) == "Escape":
            self.close()
            return True
        return False


def ya_abierto_lo_cierro():
    """Si hay otra instancia viva la mata y devuelve True (efecto interruptor)."""
    try:
        with open(PID_PATH) as fh:
            pid = int(fh.read().strip())
        os.kill(pid, signal.SIGTERM)
        return True
    except (OSError, ValueError):
        return False


def main():
    if ya_abierto_lo_cierro():
        return

    with open(PID_PATH, "w") as fh:
        fh.write(str(os.getpid()))

    # Mientras el gestor este abierto el dock no se esconde: el panel esta
    # apoyado sobre el y quedaria flotando en el aire.
    avisar_barra("dock:hold")

    def salir(*_):
        avisar_barra("dock:release")
        try:
            os.remove(PID_PATH)
        except OSError:
            pass
        Gtk.main_quit()

    signal.signal(signal.SIGTERM, lambda *_: salir())
    signal.signal(signal.SIGINT, lambda *_: salir())
    # GLib necesita despertar de vez en cuando para atender las senales de Unix.
    GLib.timeout_add(200, lambda: True)

    # Argumentos: el boton pulsado (appN) y, opcionalmente, la pantalla en la que
    # abrir directamente. Lo segundo sirve para colgarlo de un atajo de teclado.
    argumentos = sys.argv[1:]
    pantalla = None
    for bandera, nombre in (("--anadir", "anadir"), ("--quitar", "quitar")):
        if bandera in argumentos:
            argumentos.remove(bandera)
            pantalla = nombre
    pulsado = argumentos[0] if argumentos else None
    gestor = Gestor(pulsado, pantalla)
    gestor.connect("destroy", lambda *_: salir())
    Gtk.main()

    avisar_barra("dock:release")
    try:
        os.remove(PID_PATH)
    except OSError:
        pass


if __name__ == "__main__":
    main()
