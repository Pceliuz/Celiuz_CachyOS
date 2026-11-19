#!/usr/bin/env python3
"""
hypr/scripts/catalogo-apps.py — el CATALOGO de apps opcionales.

    celiuz-catalogo                    la ventana
    celiuz-catalogo --app ID           la ventana, con esa app abierta
    celiuz-catalogo --png RUTA [ID]    la ventana dibujada a un fichero, sin
                                       crearla (para mirar su aspecto con la
                                       sesion ocupada; no sale a la red)

Quien instala los dotfiles se lleva la base; lo opcional (Celiuz Remoto, el
arreglo del wifi y el Bluetooth, y las apps de fuera como Cell-Cast) se elige
aqui. El porque, en CATALOGO.md. Lo que hace cada boton vive en
lib/apps_catalogo.py, sin GTK: esta ventana solo lo ensena y lo lanza.

COMO SE PORTA
-------------
- Se dibuja enseguida con lo que hay en el equipo (las fichas de dentro y las
  de fuera que ya se bajaron), y despues, en un hilo, mira si cada app instalada
  esta lista (`revisar`), baja las fichas de GitHub y busca versiones nuevas.
  Sin internet se queda con lo que tenia y lo dice.
- Una cosa a la vez: mientras instala o quita, los botones se apagan y la
  ventana no se deja cerrar (dejaria la app a medias).
- Lo que pide contraseña lo dice ANTES, con la frase de su ficha
  (`pide_sudo`), y deja elegir instalarla sin esa parte. La contraseña la
  pide la tarjeta del repo (pedir-clave.py), nunca esta ventana.
- Lo que imprime cada orden sale en el registro de abajo. Un enlace ahi
  (el de iniciar sesion en Tailscale, por ejemplo) se abre con un clic.
"""

import os
import subprocess
import sys
import threading

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("PangoCairo", "1.0")   # la usa dibujo.py, y sin esto avisa
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango  # noqa: E402

AQUI = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(AQUI, "lib"))
import apps_catalogo as cat  # noqa: E402
import dibujo  # noqa: E402
import panel_estilo  # noqa: E402

LANZAR = os.path.join(AQUI, "lanzar.sh")
CATEGORIAS = {"sistemas": "Sistemas", "gaming": "Gaming", "stream": "Stream",
              "escritorio": "Escritorio"}
NECESIDADES = {"android": "un celular Android", "portatil": "un portátil",
               "nvidia": "una gráfica NVIDIA", "bluetooth": "Bluetooth"}


def css(C, fuente):
    v = {k: panel_estilo._hex(c) for k, c in C.items()}
    r = panel_estilo._rgba
    return panel_estilo.css_base(C, fuente) + f"""
    /* Translucido como las demas apps (gtk/celiuz-transparente.css), un poco
     * mas tapado para que se lea la letra pequeña; nitido por windowrules.lua. */
    window, window.background {{ background-color: {r(C['abismo'], .82)}; }}
    #fondo {{ padding: 18px; }}
    #fondo.png {{ background-color: {v['abismo']}; }}
    #titulo {{ font-size: 20px; }}
    #lista {{ background: none; }}
    #lista row {{ border-radius: 12px; padding: 0; margin: 0 0 6px 0; outline: none; }}
    #lista row:hover {{ background-color: {r(C['amatista'], .10)}; }}
    #lista row:selected {{ background-color: {r(C['violeta'], .30)};
                           box-shadow: inset 0 0 0 1px {v['amatista']}; }}
    #lista row:selected label {{ color: {v['luz']}; }}
    #lista row:selected .detalle {{ color: {v['tenue']}; }}
    .fila {{ padding: 10px; }}
    #detalle {{ background-color: {r(C['superficie'], .7)}; border-radius: 16px;
                border: 1px solid {v['apagado']}; padding: 18px; }}
    #nombre-app {{ font-size: 20px; font-weight: bold; }}
    .descripcion {{ font-size: 13px; }}
    .estado {{ font-size: 12px; font-weight: bold; }}
    .estado.bien {{ color: {v['neon']}; }}
    .estado.falta {{ color: {v['atencion']}; }}
    .estado.nada {{ color: {v['tenue']}; }}
    .ok {{ color: {v['neon']}; }}
    .no {{ color: {v['alerta']}; }}
    .sudo {{ border-radius: 10px; padding: 8px 10px; color: {v['atencion']};
             background-color: {r(C['atencion'], .10)}; border: 1px solid {r(C['atencion'], .35)}; }}
    .confirma {{ border-radius: 12px; padding: 12px; border: 1px solid {v['amatista']};
                 background-color: {r(C['violeta'], .18)}; }}
    button {{ padding: 6px 14px; font-size: 13px; }}
    button.chip {{ border-radius: 14px; padding: 3px 12px; border-color: {v['apagado']}; }}
    button.chip label {{ color: {v['tenue']}; }}
    button.chip.activo {{ background-color: {v['violeta']}; border-color: {v['neon']}; }}
    button.chip.activo label {{ color: {v['luz']}; }}
    .captura {{ border-radius: 8px; border: 1px solid {v['apagado']}; padding: 0; }}
    #registro {{ border-radius: 10px; border: 1px solid {v['apagado']}; }}
    #registro text {{ background-color: {v['abismo']}; color: {v['tenue']}; }}
    #registro textview {{ font-family: "MesloLGS Nerd Font Mono", monospace; font-size: 11px;
                          padding: 8px; }}
    #red {{ font-size: 11px; color: {v['tenue']}; }}
    """


def etiqueta(texto="", clases=(), xalign=0.0, envolver=False, ancho=50):
    l = Gtk.Label(label=texto, xalign=xalign)
    for c in clases:
        l.get_style_context().add_class(c)
    if envolver:
        l.set_line_wrap(True)
        l.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        # Sin tope, GTK3 pide el ancho de la frase ENTERA (CLAUDE.md, trampas).
        l.set_max_width_chars(ancho)
    return l


def boton(texto, clases=(), al_pulsar=None):
    b = Gtk.Button(label=texto)
    for c in clases:
        b.get_style_context().add_class(c)
    if al_pulsar:
        b.connect("clicked", lambda *_: al_pulsar())
    return b


def imagen(ruta, tam, alto=None):
    """Un Gtk.Image de un fichero de la app, o un hueco si no carga."""
    try:
        if alto:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(ruta, -1, alto, True)
        else:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(ruta, tam, tam)
        return Gtk.Image.new_from_pixbuf(pb)
    except (GLib.Error, TypeError):
        img = Gtk.Image.new_from_icon_name("application-x-executable", Gtk.IconSize.DIALOG)
        img.set_pixel_size(tam)
        return img


def estado_de(e, x):
    """(texto, clase) del estado de una app."""
    if x.get("comprobando") and e["instalada"] and x.get("lista") is None:
        return "comprobando…", "nada"
    texto = cat.estado_texto(e, x.get("lista"), x.get("aplica", True), x.get("nueva"))
    clase = {"instalada": "bien", "hay versión nueva": "falta", "le falta algo": "falta"}.get(texto, "nada")
    return texto, clase


class Catalogo(Gtk.Box):
    """Todo el contenido. Va aparte de la ventana para poder dibujarlo en un
    Gtk.OffscreenWindow (--png)."""

    def __init__(self, inicial=None, asincrono=True):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.set_name("fondo")
        self.asincrono = asincrono
        self.apps = cat.apps()
        self.extra = {e["id"]: {"comprobando": asincrono} for e in self.apps}
        self.seleccion = inicial if any(e["id"] == inicial for e in self.apps) else None
        if self.seleccion is None and self.apps:
            self.seleccion = self.apps[0]["id"]
        self.categoria = None
        self.ocupado = None           # id de la app que se esta instalando o quitando
        self.confirmando = None       # ("instalar"|"quitar", id)
        if not asincrono:
            self._comprobar_local(self.apps, self.extra)
        self._montar()
        self.pintar()
        if asincrono:
            threading.Thread(target=self._cargar, daemon=True).start()

    # --- la carga en segundo plano ------------------------------------------------

    @staticmethod
    def _comprobar_local(apps, extra):
        for e in apps:
            x = extra.setdefault(e["id"], {})
            x["lista"], x["faltas"] = cat.revisar(e)
            x["aplica"], x["motivo"] = cat.aplica(e)
            x["comprobando"] = False

    def _cargar(self, solo_local=False):
        extra = {e["id"]: {} for e in self.apps}
        apps = cat.apps()
        self._comprobar_local(apps, extra)
        GLib.idle_add(self._recibir, apps, extra, "" if solo_local else "buscando novedades en GitHub…")
        if solo_local:
            return
        apps = cat.apps(con_red=True)
        extra = {e["id"]: {} for e in apps}
        self._comprobar_local(apps, extra)
        sin_red = False
        for e in apps:
            if e["origen"] == "fuera" and e["instalada"]:
                extra[e["id"]]["nueva"] = cat.hay_nueva(e)
            if e["origen"] == "fuera" and not e["instalada"] and e["errores"]:
                sin_red = sin_red or any("internet" in m for m in e["errores"])
        GLib.idle_add(self._recibir, apps, extra,
                      "sin conexión con GitHub: se enseña lo último que se bajó" if sin_red else "")

    def _recibir(self, apps, extra, aviso_red):
        if self.ocupado:
            return False               # lo que llegue a mitad de una instalacion, fuera
        self.apps, self.extra = apps, extra
        self.red.set_text(aviso_red)
        self.pintar()
        return False

    def recargar(self):
        self.red.set_text("comprobando…")
        threading.Thread(target=self._cargar, kwargs={"solo_local": True}, daemon=True).start()

    # --- el esqueleto ---------------------------------------------------------------

    def _montar(self):
        cab = Gtk.Box(spacing=12)
        cab.pack_start(imagen(os.path.join(cat.fichas.RAIZ_DOTFILES, "apps", "celiuz-catalogo.svg"), 44),
                       False, False, 0)
        textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        textos.pack_start(etiqueta("Catálogo Celiuz", ("titulo",)), False, False, 0)
        textos.get_children()[0].set_name("titulo")
        textos.pack_start(etiqueta("Elige lo que quieres en este equipo. Lo que no elijas no se instala.",
                                   ("tenue",)), False, False, 0)
        cab.pack_start(textos, True, True, 0)
        self.red = etiqueta("", xalign=1.0)
        self.red.set_name("red")
        cab.pack_end(self.red, False, False, 0)
        self.pack_start(cab, False, False, 0)

        self.chips = Gtk.Box(spacing=6)
        self.pack_start(self.chips, False, False, 0)

        cuerpo = Gtk.Box(spacing=14)
        izq = Gtk.ScrolledWindow()
        izq.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        izq.set_size_request(340, -1)
        self.lista = Gtk.ListBox()
        self.lista.set_name("lista")
        self.lista.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.lista.set_filter_func(self._filtro)
        self.lista.connect("row-selected", self._al_elegir)
        izq.add(self.lista)
        cuerpo.pack_start(izq, False, False, 0)

        der = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        der.set_name("detalle")
        desliza = Gtk.ScrolledWindow()
        desliza.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.ficha = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        desliza.add(self.ficha)
        der.pack_start(desliza, True, True, 0)

        # El registro vive FUERA de lo que se repinta: si no, cada refresco se
        # llevaria lo que lleva impreso la instalacion en curso.
        self.registro_caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        cab_reg = Gtk.Box(spacing=6)
        cab_reg.pack_start(etiqueta("REGISTRO", ("seccion",)), True, True, 0)
        cab_reg.pack_end(boton("ocultar", ("plano",), self._ocultar_registro), False, False, 0)
        self.registro_caja.pack_start(cab_reg, False, False, 0)
        marco = Gtk.ScrolledWindow()
        marco.set_name("registro")
        marco.set_size_request(-1, 150)
        self.texto = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.buffer = self.texto.get_buffer()
        self.tag_enlace = self.buffer.create_tag("enlace", underline=Pango.Underline.SINGLE,
                                                 foreground=panel_estilo._hex(dibujo.C["neon"]))
        self.texto.connect("event-after", self._clic_registro)
        marco.add(self.texto)
        self.registro_marco = marco
        self.registro_caja.pack_start(marco, True, True, 0)
        self.registro_caja.set_no_show_all(True)
        der.pack_end(self.registro_caja, False, False, 0)

        cuerpo.pack_start(der, True, True, 0)
        self.pack_start(cuerpo, True, True, 0)

    # --- pintar ----------------------------------------------------------------------

    def _app(self, app_id):
        return next((e for e in self.apps if e["id"] == app_id), None)

    def pintar(self):
        self._pintar_chips()
        self._pintar_lista()
        self._pintar_ficha()

    def _pintar_chips(self):
        for h in self.chips.get_children():
            h.destroy()
        presentes = sorted({(e["ficha"] or {}).get("categoria") for e in self.apps} - {None},
                           key=lambda c: list(CATEGORIAS).index(c) if c in CATEGORIAS else 99)
        for cat_id, texto in [(None, "Todas")] + [(c, CATEGORIAS.get(c, c)) for c in presentes]:
            b = boton(texto, ("chip",) + (("activo",) if cat_id == self.categoria else ()),
                      lambda c=cat_id: self._elegir_categoria(c))
            self.chips.pack_start(b, False, False, 0)
        self.chips.show_all()

    def _elegir_categoria(self, c):
        self.categoria = c
        self._pintar_chips()
        self.lista.invalidate_filter()

    def _filtro(self, fila):
        if self.categoria is None:
            return True
        e = self._app(fila.app_id)
        return bool(e and (e["ficha"] or {}).get("categoria") == self.categoria)

    def _pintar_lista(self):
        self._pintando = True
        for h in self.lista.get_children():
            self.lista.remove(h)
        elegir = None
        for e in self.apps:
            fila = Gtk.ListBoxRow()
            fila.app_id = e["id"]
            caja = Gtk.Box(spacing=12)
            caja.get_style_context().add_class("fila")
            ficha = e["ficha"] or {}
            icono = os.path.join(e["raiz"], ficha["icono"]) if e["raiz"] and ficha.get("icono") else ""
            caja.pack_start(imagen(icono, 44), False, False, 0)
            textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            arriba = Gtk.Box(spacing=8)
            arriba.pack_start(etiqueta(ficha.get("nombre", e["id"]), ("nombre",)), False, False, 0)
            arriba.pack_start(etiqueta("incluida" if e["origen"] == "dentro" else "GitHub", ("etiqueta",)),
                              False, False, 0)
            textos.pack_start(arriba, False, False, 0)
            resumen = ficha.get("resumen") or (e["errores"][0] if e["errores"] else "")
            textos.pack_start(etiqueta(resumen, ("detalle",), envolver=True, ancho=34), False, False, 0)
            texto, clase = estado_de(e, self.extra.get(e["id"], {}))
            if self.ocupado == e["id"]:
                texto, clase = "trabajando…", "falta"
            textos.pack_start(etiqueta(texto, ("estado", clase)), False, False, 0)
            caja.pack_start(textos, True, True, 0)
            fila.add(caja)
            self.lista.add(fila)
            if e["id"] == self.seleccion:
                elegir = fila
        self.lista.show_all()
        if elegir is not None:
            self.lista.select_row(elegir)
        self._pintando = False

    def _al_elegir(self, _lista, fila):
        if getattr(self, "_pintando", False) or fila is None:
            return
        if fila.app_id != self.seleccion:
            self.seleccion = fila.app_id
            self.confirmando = None
            self._pintar_ficha()

    def _pintar_ficha(self):
        for h in self.ficha.get_children():
            h.destroy()
        e = self._app(self.seleccion)
        if e is None:
            self.ficha.pack_start(etiqueta("No hay apps en el catálogo.", ("tenue",)), False, False, 0)
            self.ficha.show_all()
            return
        x = self.extra.get(e["id"], {})
        ficha = e["ficha"]
        if ficha is None:
            self.ficha.pack_start(etiqueta(e["id"], ()), False, False, 0)
            self.ficha.get_children()[-1].set_name("nombre-app")
            for m in e["errores"]:
                self.ficha.pack_start(etiqueta(m, ("error-texto",), envolver=True), False, False, 0)
            if e.get("repo"):
                self.ficha.pack_start(self._enlace_github(e), False, False, 0)
            self.ficha.show_all()
            return

        cab = Gtk.Box(spacing=16)
        cab.pack_start(imagen(os.path.join(e["raiz"], ficha["icono"]), 72), False, False, 0)
        t = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        nombre = etiqueta(ficha["nombre"])
        nombre.set_name("nombre-app")
        t.pack_start(nombre, False, False, 0)
        t.pack_start(etiqueta(ficha["resumen"], ("tenue",), envolver=True), False, False, 0)
        marcas = Gtk.Box(spacing=6)
        marcas.pack_start(etiqueta(CATEGORIAS.get(ficha["categoria"], ficha["categoria"]), ("etiqueta",)),
                          False, False, 0)
        marcas.pack_start(etiqueta("incluida en los dotfiles" if e["origen"] == "dentro" else "de GitHub",
                                   ("etiqueta",)), False, False, 0)
        t.pack_start(marcas, False, False, 0)
        cab.pack_start(t, True, True, 0)
        self.ficha.pack_start(cab, False, False, 0)

        texto, clase = estado_de(e, x)
        if self.ocupado == e["id"]:
            texto, clase = "trabajando…", "falta"
        self.ficha.pack_start(etiqueta(texto.upper(), ("estado", clase)), False, False, 0)
        if e["instalada"]:
            for m in x.get("faltas") or []:
                self.ficha.pack_start(etiqueta("· " + m, ("tenue",), envolver=True, ancho=60), False, False, 0)
        if x.get("aplica") is False and x.get("motivo"):
            self.ficha.pack_start(etiqueta(x["motivo"], ("tenue",), envolver=True, ancho=60), False, False, 0)

        self.ficha.pack_start(self._botones(e, x), False, False, 0)
        if self.confirmando and self.confirmando[1] == e["id"]:
            self.ficha.pack_start(self._confirmacion(e), False, False, 0)

        self.ficha.pack_start(etiqueta(ficha["descripcion"], ("descripcion",), envolver=True, ancho=60),
                              False, False, 0)

        if e.get("necesita"):
            self.ficha.pack_start(etiqueta("NECESITA", ("seccion",)), False, False, 0)
            for n, hay in e["necesita"]:
                fila = Gtk.Box(spacing=8)
                marca, clase, nota = {True: ("✓", "ok", ""), False: ("✗", "no", "  (este equipo no lo tiene)"),
                                      None: ("•", "tenue", "")}[hay]
                fila.pack_start(etiqueta(marca, (clase,)), False, False, 0)
                fila.pack_start(etiqueta(NECESIDADES.get(n, n) + nota), False, False, 0)
                self.ficha.pack_start(fila, False, False, 0)

        motivo = cat.pide_sudo(e)
        if motivo:
            self.ficha.pack_start(etiqueta("Pide tu contraseña " + motivo + ".", ("sudo",),
                                           envolver=True, ancho=60), False, False, 0)

        capturas = [c for c in ficha.get("capturas") or [] if os.path.isfile(os.path.join(e["raiz"], c))]
        if capturas:
            self.ficha.pack_start(etiqueta("CAPTURAS", ("seccion",)), False, False, 0)
            fila = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=3)
            for c in capturas:
                ruta = os.path.join(e["raiz"], c)
                b = Gtk.Button()
                b.get_style_context().add_class("captura")
                b.add(imagen(ruta, 0, alto=140))
                b.set_tooltip_text("Ver en grande")
                b.connect("clicked", lambda *_, r=ruta: self._abrir_uri(GLib.filename_to_uri(r)))
                fila.add(b)
            self.ficha.pack_start(fila, False, False, 0)

        if e["origen"] == "fuera":
            self.ficha.pack_start(self._enlace_github(e), False, False, 0)
        else:
            rel = os.path.relpath(e["raiz"], cat.fichas.RAIZ_DOTFILES)
            self.ficha.pack_start(etiqueta("Viene dentro de los dotfiles (%s/): se actualiza con ellos." % rel,
                                           ("tenue",), envolver=True), False, False, 0)
        self.ficha.show_all()

    def _enlace_github(self, e):
        web = e["repo"][:-4] if e["repo"].endswith(".git") else e["repo"]
        b = Gtk.LinkButton.new_with_label(web, "  Ver en GitHub")
        b.set_halign(Gtk.Align.START)
        b.get_style_context().add_class("plano")
        return b

    def _botones(self, e, x):
        caja = Gtk.Box(spacing=8)
        quieto = self.ocupado is None
        ficha = e["ficha"]
        if not e["instalada"]:
            b = boton("Instalar", ("lleno",), lambda: self.pedir("instalar", e["id"]))
            b.set_sensitive(quieto and x.get("aplica", True) is not False)
            caja.pack_start(b, False, False, 0)
        else:
            if ficha.get("abrir"):
                caja.pack_start(boton("Abrir", ("lleno",), lambda: self.abrir(e)), False, False, 0)
            if x.get("nueva"):
                b = boton("Actualizar", (), lambda: self.lanzar("actualizar", e["id"]))
                b.set_sensitive(quieto)
                caja.pack_start(b, False, False, 0)
            if x.get("lista") is False:
                b = boton("Completar", (), lambda: self.pedir("instalar", e["id"]))
                b.set_sensitive(quieto)
                caja.pack_start(b, False, False, 0)
            b = boton("Quitar", ("peligro",), lambda: self.pedir("quitar", e["id"]))
            b.set_sensitive(quieto)
            caja.pack_end(b, False, False, 0)
        return caja

    def _confirmacion(self, e):
        que = self.confirmando[0]
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        caja.get_style_context().add_class("confirma")
        botones = Gtk.Box(spacing=8)
        if que == "instalar":
            caja.pack_start(etiqueta("Para dejarla entera, %s pide tu contraseña %s. Te la pedirá una "
                                     "tarjeta, no esta ventana." % (e["ficha"]["nombre"], cat.pide_sudo(e)),
                                     envolver=True, ancho=60), False, False, 0)
            botones.pack_start(boton("Instalar", ("lleno",), lambda: self.lanzar("instalar", e["id"], True)),
                               False, False, 0)
            botones.pack_start(boton("Sin la parte del sistema", ("suave",),
                                     lambda: self.lanzar("instalar", e["id"], False)), False, False, 0)
        else:
            caja.pack_start(etiqueta("¿Quitar %s de este equipo?" % e["ficha"]["nombre"], ("nombre",)),
                            False, False, 0)
            sistema = None
            if cat._orden(e, "sistema_quitar"):
                sistema = Gtk.CheckButton(label="Quitar también lo del sistema (pide tu contraseña)")
                sistema.set_active(True)
                caja.pack_start(sistema, False, False, 0)
            botones.pack_start(boton("Quitar", ("peligro",),
                                     lambda: self.lanzar("quitar", e["id"],
                                                         bool(sistema and sistema.get_active()))),
                               False, False, 0)
        botones.pack_start(boton("Cancelar", ("suave",), self._cancelar), False, False, 0)
        caja.pack_start(botones, False, False, 0)
        return caja

    # --- acciones --------------------------------------------------------------------

    def pedir(self, que, app_id):
        """Instalar sin contraseña va directo; lo demas pregunta antes."""
        e = self._app(app_id)
        if que == "instalar" and not cat.pide_sudo(e):
            self.lanzar("instalar", app_id, False)
            return
        self.confirmando = (que, app_id)
        self._pintar_ficha()

    def _cancelar(self):
        self.confirmando = None
        self._pintar_ficha()

    def lanzar(self, que, app_id, con_sistema=False):
        e = self._app(app_id)
        if e is None or self.ocupado:
            return
        self.confirmando = None
        self.ocupado = app_id
        self.registro_caja.set_no_show_all(False)
        self.registro_caja.show_all()
        self.buffer.set_text("")
        self.red.set_text("")
        self.pintar()

        def linea(l):
            GLib.idle_add(self._escribir, l)

        def trabajo():
            try:
                if que == "instalar":
                    ok = cat.instalar(e, linea, con_sistema=con_sistema)
                elif que == "actualizar":
                    ok = cat.actualizar(e, linea)
                else:
                    ok = cat.quitar(e, linea, con_sistema=con_sistema)
            except Exception as ex:          # que un fallo no deje la ventana bloqueada
                linea("error inesperado: %r" % (ex,))
                ok = False
            GLib.idle_add(self._terminado, ok)

        threading.Thread(target=trabajo, daemon=True).start()

    def _escribir(self, l):
        fin = self.buffer.get_end_iter()
        inicio_off = fin.get_offset()
        self.buffer.insert(fin, l + "\n")
        for palabra in l.split():
            if palabra.startswith(("https://", "http://")):
                pos = l.find(palabra)
                a = self.buffer.get_iter_at_offset(inicio_off + pos)
                b = self.buffer.get_iter_at_offset(inicio_off + pos + len(palabra))
                self.buffer.apply_tag(self.tag_enlace, a, b)
        self.texto.scroll_to_iter(self.buffer.get_end_iter(), 0, False, 0, 1)
        return False

    def _clic_registro(self, vista, evento):
        if evento.type != Gdk.EventType.BUTTON_RELEASE or evento.button.button != 1:
            return
        if self.buffer.get_has_selection():
            return
        x, y = vista.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, int(evento.x), int(evento.y))
        hay, it = vista.get_iter_at_location(x, y)
        if not hay or not it.has_tag(self.tag_enlace):
            return
        a, b = it.copy(), it.copy()
        a.backward_to_tag_toggle(self.tag_enlace)
        b.forward_to_tag_toggle(self.tag_enlace)
        self._abrir_uri(self.buffer.get_text(a, b, False))

    def _terminado(self, ok):
        self._escribir("✓ listo" if ok else "✗ no se pudo terminar: lo de arriba dice por qué")
        self.ocupado = None
        self.recargar()
        return False

    def _ocultar_registro(self):
        self.registro_caja.hide()

    def abrir(self, e):
        try:
            subprocess.Popen([LANZAR, "bash", "-c", e["ficha"]["abrir"]], cwd=e["raiz"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError as ex:
            self.registro_caja.set_no_show_all(False)
            self.registro_caja.show_all()
            self._escribir("no se pudo abrir: %s" % ex)

    @staticmethod
    def _abrir_uri(uri):
        try:
            Gio.AppInfo.launch_default_for_uri(uri, None)
        except GLib.Error:
            pass


class Ventana(Gtk.Window):
    def __init__(self, inicial=None):
        super().__init__(title="Catálogo Celiuz")
        self.set_icon_name("celiuz-catalogo")
        self.set_default_size(*tamano_inicial())
        self.catalogo = Catalogo(inicial)
        self.add(self.catalogo)
        self.connect("delete-event", self._al_cerrar)
        self.connect("key-press-event", self._tecla)

    def _al_cerrar(self, *_):
        if self.catalogo.ocupado:
            self.catalogo._escribir("espera a que termine: cerrar ahora la dejaría a medias")
            return True
        Gtk.main_quit()
        return False

    def _tecla(self, _w, ev):
        if ev.keyval == Gdk.KEY_Escape:
            if self.catalogo.confirmando:
                self.catalogo._cancelar()
            else:
                self.close()
            return True
        return False


def tamano_inicial():
    """980x680, o el 92 % de la pantalla si no cabe (la laptop es 1366x768)."""
    pantalla = Gdk.Display.get_default()
    monitor = (pantalla.get_primary_monitor() or pantalla.get_monitor(0)) if pantalla else None
    if monitor is None:
        return 980, 680
    area = monitor.get_workarea()
    return min(980, int(area.width * 0.92)), min(680, int(area.height * 0.92))


def estilo():
    proveedor = Gtk.CssProvider()
    proveedor.load_from_data(css(dibujo.C, dibujo.FUENTE).encode())
    # Por ENCIMA del CSS del usuario: el de transparencia (que se carga con
    # prioridad USER) le pone fondo a todos los botones y taparia los suyos.
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), proveedor,
                                             Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)


def a_png(ruta, inicial=None, ancho=980, alto=680):
    estilo()
    fuera = Gtk.OffscreenWindow()
    fuera.get_style_context().add_class("background")
    contenido = Catalogo(inicial, asincrono=False)
    contenido.get_style_context().add_class("png")
    fuera.add(contenido)
    fuera.set_size_request(ancho, alto)
    fuera.show_all()
    for _ in range(50):
        while Gtk.events_pending():
            Gtk.main_iteration()
    pb = fuera.get_pixbuf()
    if pb is None:
        print("catalogo-apps: no se pudo dibujar", file=sys.stderr)
        return 1
    pb.savev(ruta, "png", [], [])
    print(ruta)
    return 0


def main(argv):
    # La clase de la ventana en Wayland sale del nombre del programa (CLAUDE.md:
    # set_wmclass no hace nada). Es la de StartupWMClass y la de windowrules.lua.
    GLib.set_prgname("celiuz-catalogo")
    if not dibujo.solo_wayland():
        print("celiuz-catalogo: hace falta una sesión Wayland.", file=sys.stderr)
        return 1
    if argv[:1] == ["--png"] and len(argv) >= 2:
        return a_png(argv[1], argv[2] if len(argv) > 2 else None)
    inicial = argv[argv.index("--app") + 1] if "--app" in argv[:-1] else None
    estilo()
    v = Ventana(inicial)
    v.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
