#!/usr/bin/env python3
"""
remoto/escritorio/celiuz-remoto-config.py — la app de la PC de Celiuz Remoto.

    celiuz-remoto-config        abre la ventana

Es la pantalla 9 de las maquetas (https://claude.ai/artifact/BGqHdnHe5W2Xu7LNuVwYUd):
una ventana normal, con la paleta del escritorio (estilo.py, de colores.conf).

    Teléfonos   el celular del cable, paso a paso (depuración USB, Tailscale,
                la app, la contraseña, los permisos), y los ya emparejados con
                su pase, para renovar, desbloquear o revocar
    Registro    lo que ha pasado (registro.jsonl), en castellano
    Ajustes     dónde escucha y dónde guarda cada cosa

Abajo a la izquierda, el interruptor del servicio: viene APAGADO (DISEÑO.md, «Se
activa desde la PC, y a mano») y se enciende aquí, con systemctl --user.

Nada de lo que hace se queda solo en esta ventana: emparejar y renovar pasan por
servidor/celiuz_remoto/cable.py, lo mismo que usa la CLI, y lo demás escribe en
el mismo dispositivos.json y el mismo registro que el servicio.

Lo que tarda (adb, emparejar) va en un hilo y vuelve con GLib.idle_add: GTK
solo se toca desde el hilo principal.
"""

import os
import subprocess
import sys
import threading

AQUI = os.path.dirname(os.path.realpath(__file__))
REMOTO = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(REMOTO, "servidor"))

import celiuz_remoto  # noqa: E402  (pone hypr/scripts/lib en el path)
from celiuz_remoto import adb, ajustes, cable, control, dispositivos, pase, registro, rutas  # noqa: E402

import estilo  # noqa: E402
import textos  # noqa: E402

UNIDAD = "celiuz-remoto.service"
TAILSCALE_CONSOLA = "https://login.tailscale.com/admin/machines"
CADA_ESTADO = 2      # segundos: servicio y teléfonos emparejados
CADA_CABLE = 3       # segundos: lo que hay enchufado (adb tarda ~0,5 s)
AVISO_SERVICIO = "Enciende el servicio (abajo a la izquierda) para emparejar."


# --- el servicio (systemd --user) ---------------------------------------------

def _systemctl(*args):
    try:
        r = subprocess.run(["systemctl", "--user", *args], capture_output=True,
                           text=True, timeout=15, check=False)
        return r.returncode, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


def estado_servicio():
    """{"instalado", "activo", "red", "detalle"}: lo que se enseña abajo a la izquierda."""
    codigo, salida = _systemctl("show", UNIDAD, "-p", "LoadState,ActiveState,SubState")
    props = dict(linea.split("=", 1) for linea in salida.splitlines() if "=" in linea)
    instalado = props.get("LoadState") == "loaded"
    activo = props.get("ActiveState") == "active"
    red = None
    if activo:
        try:
            c, d = control.pedir("GET", "/control/estado", timeout=2)
            red = d.get("red") if c == 200 else None
        except (control.SinServicio, OSError):
            red = None
    detalle = props.get("SubState", "")
    return {"instalado": instalado, "activo": activo, "red": red,
            "reintentando": props.get("ActiveState") == "activating" or detalle == "auto-restart"}


# --- GTK ----------------------------------------------------------------------

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("PangoCairo", "1.0")   # la usa dibujo.py, y sin esto avisa
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

import dibujo  # noqa: E402


def tamano_inicial():
    """El de la maqueta (1200x760), o el 92 % de la pantalla si no cabe: en la
    laptop (1366x768) la maqueta entera se saldria por abajo."""
    pantalla = Gdk.Display.get_default()
    monitor = pantalla.get_primary_monitor() or pantalla.get_monitor(0) if pantalla else None
    if monitor is None:
        return 1200, 760
    area = monitor.get_workarea()
    return min(1200, int(area.width * 0.92)), min(760, int(area.height * 0.92))


def etiqueta(texto="", clases=(), xalign=0.0, envolver=False, seleccionable=False, ancho=60):
    l = Gtk.Label(label=texto, xalign=xalign)
    for c in clases:
        l.get_style_context().add_class(c)
    if envolver:
        l.set_line_wrap(True)
        l.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        # Sin tope, GTK3 pide para un texto con ajuste de linea el ancho de la
        # frase ENTERA: la barra de 230 px salia de 420 y la columna de la
        # derecha se comia media pantalla.
        l.set_max_width_chars(ancho)
    l.set_selectable(seleccionable)
    return l


def boton(texto, clases=(), al_pulsar=None):
    b = Gtk.Button(label=texto)
    for c in clases:
        b.get_style_context().add_class(c)
    if al_pulsar:
        b.connect("clicked", lambda *_: al_pulsar())
    return b


def caja(vertical=True, espacio=0, clases=()):
    b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL,
                spacing=espacio)
    for c in clases:
        b.get_style_context().add_class(c)
    return b


def vaciar(contenedor):
    for hijo in contenedor.get_children():
        contenedor.remove(hijo)


class Paso(Gtk.Box):
    """Una fila de la lista de pasos: el circulo (numero, ✓ o !) y el texto."""

    def __init__(self, numero):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.numero = numero
        self.circulo = etiqueta(str(numero), ("paso",), xalign=0.5)
        self.circulo.set_valign(Gtk.Align.CENTER)
        self.texto = etiqueta("", ("paso-texto",))
        self.ayuda = etiqueta("", ("tenue", "chico"), envolver=True)
        col = caja(espacio=2)
        col.pack_start(self.texto, False, False, 0)
        col.pack_start(self.ayuda, False, False, 0)
        self.pack_start(self.circulo, False, False, 0)
        self.pack_start(col, True, True, 0)
        self.extra = caja(vertical=False)
        self.extra.set_valign(Gtk.Align.CENTER)
        self.pack_end(self.extra, False, False, 0)

    def poner(self, estado, texto, ayuda=""):
        """estado: hecho / falta / actual / pendiente."""
        ctx = self.circulo.get_style_context()
        for c in ("hecho", "falta"):
            ctx.remove_class(c)
        if estado == "hecho":
            ctx.add_class("hecho")
            self.circulo.set_text("✓")
        elif estado == "falta":
            ctx.add_class("falta")
            self.circulo.set_text("!")
        else:
            self.circulo.set_text(str(self.numero))
        t = self.texto.get_style_context()
        (t.add_class if estado in ("actual", "falta") else t.remove_class)("actual")
        self.texto.set_text(texto)
        self.ayuda.set_text(ayuda)
        self.ayuda.set_visible(bool(ayuda))


class Ventana(Gtk.Window):
    def __init__(self):
        super().__init__(title="Celiuz Remoto")
        self.set_default_size(*tamano_inicial())
        self.set_icon_name("celiuz-remoto")
        self.almacen = dispositivos.Almacen()
        self.celulares = []          # lo ultimo que dijo adb
        self.error_adb = None
        self.serie = None            # el celular elegido del cable
        self.ocupado = False         # emparejando o renovando
        self.servicio = {"instalado": False, "activo": False, "red": None}
        self._mirando_cable = False

        raiz = caja(vertical=False)
        raiz.set_name("fondo")
        self.add(raiz)
        raiz.pack_start(self._nav(), False, False, 0)
        self.paginas = Gtk.Stack()
        self.paginas.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.paginas.add_named(self._pagina_telefonos(), "telefonos")
        self.paginas.add_named(self._pagina_registro(), "registro")
        self.paginas.add_named(self._pagina_ajustes(), "ajustes")
        raiz.pack_start(self.paginas, True, True, 0)

        self.connect("destroy", self._al_cerrar)
        self.connect("key-press-event", self._tecla)
        self.ir("telefonos")
        self.refrescar()
        self.mirar_cable()
        GLib.timeout_add_seconds(CADA_ESTADO, self._tic_estado)
        GLib.timeout_add_seconds(CADA_CABLE, self._tic_cable)

    # --- la barra de la izquierda ---

    def _nav(self):
        nav = caja(espacio=6)
        nav.set_name("nav")
        nav.set_size_request(230, -1)
        nav.pack_start(etiqueta("Celiuz Remoto", ("fuerte",)), False, False, 0)
        nav.get_children()[0].set_name("marca")
        self.pestanas = {}
        for clave, nombre in (("telefonos", "Teléfonos"), ("registro", "Registro"),
                              ("ajustes", "Ajustes")):
            b = boton(nombre, ("pestana",), lambda c=clave: self.ir(c))
            b.get_child().set_xalign(0.0)
            self.pestanas[clave] = b
            nav.pack_start(b, False, False, 0)

        tarjeta = caja(espacio=8, clases=("tarjeta", "chica"))
        tarjeta.set_name("servicio")
        tarjeta.pack_start(etiqueta("Servicio", ("tenue", "chico")), False, False, 0)
        self.servicio_txt = etiqueta("", ("fuerte",), envolver=True, ancho=22)
        self.servicio_det = etiqueta("", ("tenue", "chico"), envolver=True, ancho=26)
        self.servicio_btn = boton("", ("discreto",), self.alternar_servicio)
        for w in (self.servicio_txt, self.servicio_det, self.servicio_btn):
            tarjeta.pack_start(w, False, False, 0)
        nav.pack_end(tarjeta, False, False, 0)
        return nav

    def ir(self, clave):
        self.paginas.set_visible_child_name(clave)
        for c, b in self.pestanas.items():
            ctx = b.get_style_context()
            (ctx.add_class if c == clave else ctx.remove_class)("activa")
        if clave == "registro":
            self.pintar_registro()

    def _tecla(self, _w, ev):
        if ev.keyval == Gdk.KEY_Escape and not self.ocupado:
            self.destroy()
            return True
        return False

    # --- Teléfonos ---

    def _pagina_telefonos(self):
        pagina = caja(vertical=False, espacio=28)
        pagina.set_border_width(28)

        izq = caja(espacio=18)
        cab = caja(espacio=4)
        fila = caja(vertical=False, espacio=12)
        self.cable_titulo = etiqueta("Teléfono conectado por cable", ("h1",))
        fila.pack_start(self.cable_titulo, True, True, 0)
        self.selector = Gtk.ComboBoxText()
        self.selector.connect("changed", self._al_elegir)
        self.selector.set_no_show_all(True)
        fila.pack_end(self.selector, False, False, 0)
        cab.pack_start(fila, False, False, 0)
        self.cable_sub = etiqueta("", ("tenue",), envolver=True)
        cab.pack_start(self.cable_sub, False, False, 0)
        izq.pack_start(cab, False, False, 0)

        t = caja(espacio=14, clases=("tarjeta",))
        self.p_usb, self.p_tail, self.p_app, self.p_clave, self.p_perm = (Paso(n) for n in range(1, 6))
        self.boton_instalar = boton("Instalar la app", ("discreto",), self.instalar_app)
        self.boton_instalar.set_no_show_all(True)
        self.p_app.extra.pack_start(self.boton_instalar, False, False, 0)
        for p in (self.p_usb, self.p_tail, self.p_app, self.p_clave):
            t.pack_start(p, False, False, 0)

        claves = Gtk.Grid(column_spacing=12, row_spacing=6, column_homogeneous=True)
        claves.set_margin_start(38)
        self.clave1, self.clave2 = Gtk.Entry(), Gtk.Entry()
        for i, (e, nombre) in enumerate(((self.clave1, "Contraseña"), (self.clave2, "Repítela"))):
            e.set_visibility(False)
            e.set_input_purpose(Gtk.InputPurpose.PASSWORD)
            e.connect("changed", lambda *_: self.pintar_cable())
            lab = etiqueta(nombre, ("etiqueta",))
            lab.set_mnemonic_widget(e)
            claves.attach(lab, i, 0, 1, 1)
            claves.attach(e, i, 1, 1, 1)
        self.clave2.connect("activate", lambda *_: self.emparejar())
        t.pack_start(claves, False, False, 0)
        aviso = etiqueta("No uses la de tu usuario de Linux: esta es solo para la app.",
                         ("tenue", "chico"))
        aviso.set_margin_start(38)
        t.pack_start(aviso, False, False, 0)

        t.pack_start(self.p_perm, False, False, 0)
        casillas = Gtk.Grid(column_spacing=20, row_spacing=10, column_homogeneous=True)
        casillas.set_margin_start(38)
        self.casillas = []
        for i, (nombre, _, marcada) in enumerate(textos.CASILLAS):
            c = Gtk.CheckButton(label=nombre)
            c.set_active(marcada)
            self.casillas.append(c)
            casillas.attach(c, i % 2, i // 2, 1, 1)
        t.pack_start(casillas, False, False, 0)
        izq.pack_start(t, False, False, 0)

        botones = caja(vertical=False, espacio=12)
        self.boton_emparejar = boton("Emparejar y dar pase de 24 h", ("grande", "lleno"), self.emparejar)
        self.boton_renovar = boton("Solo renovar el pase", ("grande",), self.renovar)
        self.boton_cancelar = boton("Cancelar", ("grande",), cable.cancelar)
        self.boton_cancelar.set_no_show_all(True)
        for b in (self.boton_emparejar, self.boton_renovar, self.boton_cancelar):
            botones.pack_start(b, False, False, 0)
        izq.pack_start(botones, False, False, 0)
        self.estado_op = etiqueta("", (), envolver=True)
        self.estado_op.set_name("estado-op")
        izq.pack_start(self.estado_op, False, False, 0)
        # Con scroll: en una pantalla baja (la laptop, 768 px) la lista de pasos
        # no cabe entera y sin esto la ventana se haria mas alta que la pantalla.
        desliza_izq = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        desliza_izq.add(izq)
        pagina.pack_start(desliza_izq, True, True, 0)

        der = caja(espacio=14)
        der.set_size_request(340, -1)
        der.set_hexpand(False)
        der.pack_start(etiqueta("Teléfonos emparejados", ("h2",)), False, False, 0)
        desliza = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.lista = caja(espacio=12)
        desliza.add(self.lista)
        der.pack_start(desliza, True, True, 0)
        robo = caja(espacio=6, clases=("tarjeta", "chica", "robo"))
        robo.pack_start(etiqueta("¿Te robaron el celular?", ("alerta-titulo",)), False, False, 0)
        robo.pack_start(etiqueta("Desde cualquier navegador, entra en la consola de Tailscale y "
                                 "quita ese aparato. Se corta al instante, sin venir a la PC. "
                                 "Luego revócalo aquí.", ("tenue", "chico"), envolver=True,
                                 ancho=36),
                        False, False, 0)
        enlace = Gtk.LinkButton.new_with_label(TAILSCALE_CONSOLA, "Abrir la consola de Tailscale")
        enlace.set_halign(Gtk.Align.START)
        robo.pack_start(enlace, False, False, 0)
        der.pack_end(robo, False, False, 0)
        pagina.pack_start(der, False, False, 0)
        return pagina

    def _al_elegir(self, combo):
        serie = combo.get_active_id()
        if serie and serie != self.serie:
            self.serie = serie
            self.pintar_cable()

    def mirar_cable(self):
        """adb en un hilo: tarda medio segundo y no puede congelar la ventana."""
        if self._mirando_cable or self.ocupado:
            return

        def trabajo():
            try:
                lista, error = adb.celulares(), None
            except adb.ErrorAdb as e:
                lista, error = [], str(e)
            GLib.idle_add(self._cable_leido, lista, error)

        self._mirando_cable = True
        threading.Thread(target=trabajo, daemon=True).start()

    def _cable_leido(self, lista, error):
        self._mirando_cable = False
        cambio = lista != self.celulares or error != self.error_adb
        self.celulares, self.error_adb = lista, error
        series = [c["serie"] for c in lista]
        if self.serie not in series:
            listos = [c["serie"] for c in lista if c["estado"] == "listo"]
            self.serie = (listos or series or [None])[0]
            cambio = True
        if cambio:
            self.selector.handler_block_by_func(self._al_elegir)
            self.selector.remove_all()
            for c in lista:
                self.selector.append(c["serie"], f"{c['nombre']} ({c['serie'][-4:]})")
            if self.serie:
                self.selector.set_active_id(self.serie)
            self.selector.set_visible(len(lista) > 1)
            self.selector.handler_unblock_by_func(self._al_elegir)
            self.pintar_cable()
        return False

    def celular(self):
        return next((c for c in self.celulares if c["serie"] == self.serie), None)

    def pintar_cable(self):
        c = self.celular()
        emparejado = self.almacen.por_serie(self.serie) if c else None
        if self.error_adb:
            self.cable_titulo.set_text("No puedo mirar el cable")
            self.cable_sub.set_text(self.error_adb)
        elif c is None:
            self.cable_titulo.set_text("Conecta el celular por cable")
            self.cable_sub.set_text("Con la «Depuración USB» activada: Ajustes → Información del "
                                    "teléfono → toca 7 veces «Número de compilación», y luego "
                                    "Opciones de desarrollador → Depuración USB.")
        else:
            self.cable_titulo.set_text("Teléfono conectado por cable")
            partes = [c["nombre"]] + ([f"Android {c['android']}"] if c.get("android") else [])
            partes.append(c["serie"])
            if emparejado:
                partes.append(f"ya emparejado como «{emparejado['nombre']}»")
            self.cable_sub.set_text(" · ".join(partes))

        listo = c is not None and c["estado"] == "listo"
        if c is None:
            self.p_usb.poner("actual", "Depuración USB autorizada")
        elif c["estado"] == "sin_autorizar":
            self.p_usb.poner("falta", "Depuración USB sin autorizar",
                             "Mira la pantalla del celular y toca «Permitir» (marca «Permitir "
                             "siempre desde este ordenador»).")
        elif c["estado"] == "sin_permisos":
            self.p_usb.poner("falta", "Linux no deja abrir el USB del celular",
                             "Faltan las reglas udev de Android: sudo pacman -S android-udev")
        elif not listo:
            self.p_usb.poner("falta", f"El celular está «{c['estado']}»",
                             "Desconéctalo y vuelve a conectarlo.")
        else:
            self.p_usb.poner("hecho", "Depuración USB autorizada")

        if not listo:
            self.p_tail.poner("pendiente", "Tailscale en el celular")
        elif c.get("tailscale"):
            self.p_tail.poner("hecho", "Tailscale en el celular")
        else:
            self.p_tail.poner("falta", "Falta Tailscale en el celular",
                              "Instálalo desde Play Store y entra con la misma cuenta que esta "
                              "PC: sin él, la app no llega a la PC.")

        hay_apk = os.path.exists(rutas.apk())
        if not listo:
            self.p_app.poner("pendiente", "La app de Celiuz Remoto")
            self.boton_instalar.hide()
        elif c.get("app"):
            self.p_app.poner("hecho", f"App instalada (v{c['app']})")
            self.boton_instalar.set_label("Actualizar")
            self.boton_instalar.set_visible(hay_apk)
        else:
            self.p_app.poner("falta", "Falta la app de Celiuz Remoto",
                             "" if hay_apk else "Todavía no está compilada en esta PC.")
            self.boton_instalar.set_label("Instalar la app")
            self.boton_instalar.set_visible(hay_apk)

        uno, dos = self.clave1.get_text(), self.clave2.get_text()
        fallo = textos.contrasena_valida(uno, dos) if (uno or dos) else "vacía"
        for e in (self.clave1, self.clave2):
            e.get_style_context().remove_class("error")
        if fallo is None:
            self.p_clave.poner("hecho", "Contraseña de la app")
        elif fallo == "vacía":
            self.p_clave.poner("actual", "Crea la contraseña de la app")
        else:
            self.p_clave.poner("actual", "Crea la contraseña de la app", fallo)
            if dos:
                self.clave2.get_style_context().add_class("error")
        self.p_perm.poner("actual" if fallo is None else "pendiente",
                          "Qué puede hacer este teléfono")

        servicio = self.servicio.get("activo") and self.servicio.get("red")
        puede = listo and bool(c.get("app")) and servicio and not self.ocupado
        self.boton_emparejar.set_sensitive(bool(puede and fallo is None))
        self.boton_renovar.set_sensitive(bool(puede and emparejado))
        for w in [self.clave1, self.clave2] + self.casillas:
            w.set_sensitive(not self.ocupado)
        # El aviso del servicio solo pisa la linea de estado si esta libre (o si
        # es el mismo aviso): no se come el «Emparejado» ni un error.
        if not self.ocupado:
            libre = self.estado_op.get_text() in ("", AVISO_SERVICIO)
            if not servicio and libre:
                self.op(AVISO_SERVICIO, "")
            elif servicio and self.estado_op.get_text() == AVISO_SERVICIO:
                self.op("", "")

    def op(self, texto, clase):
        self.estado_op.set_text(texto)
        ctx = self.estado_op.get_style_context()
        for c in ("error", "ok"):
            ctx.remove_class(c)
        if clase:
            ctx.add_class(clase)

    def _por_cable(self, trabajo, al_acabar):
        self.ocupado = True
        self.boton_cancelar.show()
        self.pintar_cable()

        def hilo():
            try:
                fin, error = trabajo(lambda t: GLib.idle_add(self.op, t, "")), None
            except (cable.ErrorCable, adb.ErrorAdb) as e:
                fin, error = None, str(e)
            GLib.idle_add(listo, fin, error)

        def listo(fin, error):
            self.ocupado = False
            self.boton_cancelar.hide()
            if error:
                self.op(f"No se pudo: {error}", "error")
            else:
                al_acabar(fin)
            self.refrescar()
            return False

        threading.Thread(target=hilo, daemon=True).start()

    def emparejar(self):
        if not self.boton_emparejar.get_sensitive():
            return
        c = self.celular()
        contrasena = self.clave1.get_text()
        permisos = textos.permisos_de([i for i, x in enumerate(self.casillas) if x.get_active()])
        serie, nombre = c["serie"], c["nombre"]

        def hecho(_fin):
            self.clave1.set_text("")
            self.clave2.set_text("")
            self.op(f"Emparejado «{nombre}», con pase de 24 h. Ya puedes entrar desde el celular.",
                    "ok")

        self._por_cable(lambda aviso: cable.emparejar(serie, contrasena, permisos, nombre, aviso),
                        hecho)

    def renovar(self):
        serie = self.serie
        self.op("En el celular, escribe la contraseña de la app.", "")
        self._por_cable(lambda aviso: cable.renovar(serie, aviso),
                        lambda _fin: self.op("Pase renovado: 24 h desde ahora.", "ok"))

    def instalar_app(self):
        serie, apk = self.serie, rutas.apk()
        self.op("Instalando la app en el celular…", "")
        self.ocupado = True
        self.pintar_cable()

        def hilo():
            try:
                adb.instalar(serie, apk)
                GLib.idle_add(self.op, "App instalada.", "ok")
            except adb.ErrorAdb as e:
                GLib.idle_add(self.op, f"No se pudo: {e}", "error")
            GLib.idle_add(fin)

        def fin():
            self.ocupado = False
            self.celulares = []      # que se vuelva a mirar todo
            self.mirar_cable()
            return False

        threading.Thread(target=hilo, daemon=True).start()

    # --- los emparejados ---

    def pintar_emparejados(self):
        try:
            todos = self.almacen.todos()
        except dispositivos.ErrorDispositivo as e:
            vaciar(self.lista)
            self.lista.pack_start(etiqueta(str(e), ("rojo",), envolver=True), False, False, 0)
            self.lista.show_all()
            return
        firma = [(d["id"], d.get("pase_hasta"), d.get("bloqueado"), d.get("ultima_sesion"),
                  tuple(d["permisos"]), d["nombre"]) for d in todos]
        ahora = pase.ahora()
        minuto = ahora.strftime("%H:%M")
        if firma == getattr(self, "_firma_lista", None) and minuto == getattr(self, "_minuto", None):
            return
        self._firma_lista, self._minuto = firma, minuto
        vaciar(self.lista)
        if not todos:
            self.lista.pack_start(etiqueta("Todavía ninguno. Conecta el celular por cable y "
                                           "empieza por la izquierda.", ("tenue", "chico"),
                                           envolver=True, ancho=36), False, False, 0)
        for d in todos:
            self.lista.pack_start(self._tarjeta(d, ahora), False, False, 0)
        self.lista.show_all()

    def _tarjeta(self, d, ahora):
        t = caja(espacio=8, clases=("tarjeta", "chica"))
        fila = caja(vertical=False, espacio=8)
        fila.pack_start(etiqueta(d["nombre"], ("fuerte",)), True, True, 0)
        ultima = textos.leer_fecha(d.get("ultima_sesion"))
        estado = etiqueta("BLOQUEADO" if d.get("bloqueado") else
                          (f"entró {textos.hace(ultima, ahora)}" if ultima else "aún no ha entrado"),
                          ("chico", "rojo" if d.get("bloqueado") else "tenue"))
        fila.pack_end(estado, False, False, 0)
        t.pack_start(fila, False, False, 0)
        texto, queda = textos.pase(d, ahora)
        t.pack_start(etiqueta(texto, ("tenue", "chico")), False, False, 0)
        if queda is not None:
            barra = Gtk.LevelBar(min_value=0, max_value=1, value=queda)
            barra.remove_offset_value(Gtk.LEVEL_BAR_OFFSET_LOW)
            barra.remove_offset_value(Gtk.LEVEL_BAR_OFFSET_HIGH)
            barra.remove_offset_value(Gtk.LEVEL_BAR_OFFSET_FULL)
            t.pack_start(barra, False, False, 0)
        t.pack_start(etiqueta(textos.resumen_permisos(d["permisos"]), ("tenue", "chico"),
                              envolver=True, ancho=36), False, False, 0)
        botones = caja(vertical=False, espacio=8)
        if d.get("bloqueado"):
            botones.pack_start(boton("Desbloquear", ("discreto",),
                                     lambda i=d["id"]: self.desbloquear(i)), False, False, 0)
        if pase.vigente(d):
            botones.pack_start(boton("Quitar el pase", ("discreto",),
                                     lambda i=d["id"]: self.quitar_pase(i)), False, False, 0)
        botones.pack_start(boton("Revocar", ("peligro",), lambda x=d: self.revocar(x)),
                           False, False, 0)
        t.pack_start(botones, False, False, 0)
        return t

    def _cambio(self, ident, accion, **campos):
        self.almacen.cambiar(ident, **campos)
        registro.apuntar(accion, ident)
        self.refrescar()

    def desbloquear(self, ident):
        self._cambio(ident, "desbloqueado", bloqueado=False, fallos=0)

    def quitar_pase(self, ident):
        self._cambio(ident, "pase_quitado", pase_hasta=None)

    def revocar(self, d):
        dialogo = Gtk.MessageDialog(transient_for=self, modal=True,
                                    message_type=Gtk.MessageType.WARNING,
                                    buttons=Gtk.ButtonsType.NONE,
                                    text=f"¿Revocar «{d['nombre']}»?")
        dialogo.format_secondary_text(
            "Ya no podrá entrar, ni con la contraseña. Para volver a usarlo habrá que "
            "emparejarlo otra vez por cable.")
        dialogo.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        dialogo.add_button("Revocar", Gtk.ResponseType.OK)
        respuesta = dialogo.run()
        dialogo.destroy()
        if respuesta == Gtk.ResponseType.OK:
            self.almacen.revocar(d["id"])
            registro.apuntar("revocado", d["id"], nombre=d["nombre"])
            self.op(f"Revocado «{d['nombre']}».", "ok")
            self.refrescar()

    # --- el servicio ---

    def pintar_servicio(self):
        s = self.servicio
        ctx = self.servicio_txt.get_style_context()
        for c in ("ok", "atencion", "rojo"):
            ctx.remove_class(c)
        if not s["instalado"]:
            self.servicio_txt.set_text("Sin instalar")
            ctx.add_class("atencion")
            self.servicio_det.set_text("Pasa ./instalar.sh para que esté la unidad de systemd.")
            self.servicio_btn.set_label("Encender el servicio")
            self.servicio_btn.set_sensitive(False)
        elif s["activo"] and s["red"]:
            self.servicio_txt.set_text("Activo · solo Tailscale")
            ctx.add_class("ok")
            self.servicio_det.set_text(s["red"])
            self.servicio_btn.set_label("Apagar el servicio")
            self.servicio_btn.get_style_context().add_class("peligro")
            self.servicio_btn.set_sensitive(True)
        elif s["activo"] or s.get("reintentando"):
            self.servicio_txt.set_text("Esperando a Tailscale")
            ctx.add_class("atencion")
            self.servicio_det.set_text("Sin Tailscale conectado no escucha en ningún sitio. "
                                       "Lo reintenta solo.")
            self.servicio_btn.set_label("Apagar el servicio")
            self.servicio_btn.get_style_context().add_class("peligro")
            self.servicio_btn.set_sensitive(True)
        else:
            self.servicio_txt.set_text("Apagado")
            ctx.add_class("rojo")
            self.servicio_det.set_text("Viene apagado: nadie puede entrar desde fuera.")
            self.servicio_btn.set_label("Encender el servicio")
            self.servicio_btn.get_style_context().remove_class("peligro")
            self.servicio_btn.set_sensitive(True)

    def alternar_servicio(self):
        encender = not (self.servicio["activo"] or self.servicio.get("reintentando"))
        self.servicio_btn.set_sensitive(False)

        def hilo():
            codigo, salida = _systemctl("enable" if encender else "disable", "--now", UNIDAD)
            GLib.idle_add(fin, codigo, salida)

        def fin(codigo, salida):
            if codigo != 0:
                self.op(f"systemctl no pudo: {salida.splitlines()[-1] if salida else codigo}",
                        "error")
            else:
                registro.apuntar("servicio_encendido" if encender else "servicio_apagado")
            # Al encender, tarda un momento en tener el socket: se mira en un rato.
            GLib.timeout_add(800, lambda: (self.refrescar(), False)[1])
            return False

        threading.Thread(target=hilo, daemon=True).start()

    # --- Registro y Ajustes ---

    def _pagina_registro(self):
        pagina = caja(espacio=14)
        pagina.set_border_width(28)
        pagina.pack_start(etiqueta("Registro", ("h1",)), False, False, 0)
        pagina.pack_start(etiqueta("Lo que ha hecho cada teléfono y cuándo. Nunca guarda "
                                   "contraseñas ni lo que se escribe en la terminal.",
                                   ("tenue",), envolver=True), False, False, 0)
        desliza = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.registro = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        desliza.add(self.registro)
        pagina.pack_start(desliza, True, True, 0)
        return pagina

    def pintar_registro(self):
        vaciar(self.registro)
        try:
            nombres = {d["id"]: d["nombre"] for d in self.almacen.todos()}
        except dispositivos.ErrorDispositivo:
            nombres = {}
        ahora = pase.ahora()
        lineas = list(reversed(registro.ultimas(200)))
        if not lineas:
            self.registro.add(etiqueta("Nada todavía.", ("tenue",)))
        for linea in lineas:
            hora, texto = textos.linea_registro(linea, nombres, ahora)
            fila = caja(vertical=False, espacio=16)
            h = etiqueta(hora, ("registro-hora",))
            h.set_size_request(110, -1)
            fila.pack_start(h, False, False, 0)
            fila.pack_start(etiqueta(texto, ("registro-texto",), envolver=True), True, True, 0)
            self.registro.add(fila)
        self.registro.show_all()

    def _pagina_ajustes(self):
        pagina = caja(espacio=14)
        pagina.set_border_width(28)
        pagina.pack_start(etiqueta("Ajustes", ("h1",)), False, False, 0)
        v = ajustes.leer()
        filas = [
            ("Escucha en", "la IP de Tailscale de esta PC, puerto %d (y nunca en la red de casa)"
             % v["puerto_red"]),
            ("Canal USB", "127.0.0.1:%d, solo mientras se empareja o se renueva" % v["puerto_usb"]),
            ("La sesión caduca", "tras %d s sin usarla" % v["sesion"]),
            ("Se cambia en", rutas.ajustes()),
            ("Teléfonos", rutas.dispositivos()),
            ("Registro", rutas.registro()),
            ("La app compilada", rutas.apk()),
        ]
        t = caja(espacio=12, clases=("tarjeta",))
        for k, valor in filas:
            fila = caja(vertical=False, espacio=16)
            e = etiqueta(k, ("tenue",))
            e.set_size_request(170, -1)
            fila.pack_start(e, False, False, 0)
            fila.pack_start(etiqueta(valor, ("mono",) if valor.startswith("/") else (),
                                     envolver=True, seleccionable=True), True, True, 0)
            t.pack_start(fila, False, False, 0)
        pagina.pack_start(t, False, False, 0)
        pagina.pack_start(etiqueta("Los cambios de remoto.conf valen al reiniciar el servicio.",
                                   ("tenue", "chico")), False, False, 0)
        return pagina

    # --- el ritmo ---

    def refrescar(self):
        threading.Thread(target=self._leer_servicio, daemon=True).start()
        self.pintar_emparejados()
        if self.paginas.get_visible_child_name() == "registro":
            self.pintar_registro()

    def _leer_servicio(self):
        s = estado_servicio()
        GLib.idle_add(self._servicio_leido, s)

    def _servicio_leido(self, s):
        self.servicio = s
        self.pintar_servicio()
        self.pintar_cable()
        return False

    def _tic_estado(self):
        if not self.ocupado:
            self.refrescar()
        return True

    def _tic_cable(self):
        self.mirar_cable()
        return True

    def _al_cerrar(self, *_):
        if self.ocupado:
            cable.cancelar()
        Gtk.main_quit()


def main():
    # La clase de la ventana en Wayland (app_id): sale del nombre del programa,
    # no de set_wmclass, que en Wayland no hace nada. Es la que casa con
    # StartupWMClass del .desktop.
    GLib.set_prgname("celiuz-remoto")
    if not dibujo.solo_wayland():
        print("celiuz-remoto-config: hace falta una sesión Wayland.", file=sys.stderr)
        return 1
    proveedor = Gtk.CssProvider()
    proveedor.load_from_data(estilo.css(dibujo.C, dibujo.FUENTE, dibujo.VERDE).encode())
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), proveedor,
                                             Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    Ventana().show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
