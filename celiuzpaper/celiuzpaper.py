#!/usr/bin/env python3
"""
CeliuzPaper — el selector de fondos de pantalla.

    celiuzpaper                 abre el selector
    celiuzpaper --list          lista los fondos en la terminal
    celiuzpaper --set <texto>   pone el fondo que coincida con ese texto
    celiuzpaper --random        pone uno al azar (distinto del actual)
    celiuzpaper --current       dice cual esta puesto

LA IDEA
-------
Un selector de fondos normal te ensena miniaturas y te hace adivinar. Este no:
mientras te mueves por la tira de abajo, **cambia el fondo de verdad**, a pantalla
completa, detras de la propia ventana. Lo que estas juzgando es el fondo, no una
foto pequena de el. Se puede porque mpv acepta `loadfile` por su socket IPC: el
video se cambia en marcha, sin reiniciar mpvpaper y sin parpadeo (~0.3 s).

Enter (o clic) lo deja puesto de forma permanente; Escape devuelve el que tenias.

EL DISENO, Y POR QUE
--------------------
- La ventana **se aparta de lo que estas eligiendo**: es una capa transparente a
  pantalla completa, pero solo se oscurece la franja de abajo, con un degradado.
  Cuatro quintos de la pantalla son el fondo, limpio.
- La tira son tarjetas **16:9**, la forma que tiene un fondo de pantalla. Las
  vistas previas que trae Wallpaper Engine son cuadradas, asi que las miniaturas
  se sacan del propio video con ffmpeg (a 3 s) y se guardan en cache.
- Las tarjetas se dibujan con Cairo y no con imagenes de GTK: hace falta para
  recortar con esquinas redondeadas, oscurecer las no elegidas y encender la
  elegida con un halo. La profundidad la da el contraste, no los bordes.
- Nada de botones, ni "Aplicar", ni "Cancelar". Flechas, Enter y Escape.

Para que lo maneje el asistente esta la parte de terminal (--set, --random), que
usa el mismo camino: lib/wallpapers.py.
"""

import os
import random
import signal
import sys

sys.path.insert(0, os.path.expanduser("~/dotfiles/hypr/scripts/lib"))

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, GtkLayerShell, Pango  # noqa: E402

import wallpapers as wp  # noqa: E402

# --- Medidas ------------------------------------------------------------------
# Tarjeta 16:9. 220 de ancho deja ver ~7 de golpe en 1920 y sigue siendo
# reconocible de un vistazo.
TARJETA_W = 220
TARJETA_H = 124
SEPARACION = 14
# Cuanto se encoge una tarjeta no elegida. Es el "efecto de levantar" sin cambiar
# el tamano de la casilla: si cambiara, la tira daria saltos al moverse.
ENCOGIDO = 5
RADIO = 14

# Franja oscura de abajo. El degradado sube hasta ALTO_VELO y ahi ya es
# transparente del todo.
ALTO_VELO = 380
MARGEN = 46
# Alto FIJO del bloque de abajo (cabecera + tira + pie). Fijarlo no es cosmetico:
# si el bloque crece o se encoge —al llegar los datos de un video, o al pasar de
# un titulo latino a uno chino, que es mas alto— GTK recoloca todo y, al ser una
# ventana transparente, no limpia lo que habia antes: quedan tarjetas fantasma
# pegadas en la pantalla. Con el alto fijo nada se mueve y no hay restos.
ALTO_BLOQUE = 272

# Espera antes de cambiar el fondo de verdad al pasar por una tarjeta. Sin esto,
# barrer la tira con el raton dispararia diez cambios seguidos.
RETARDO_VISTA = 180
# Duracion de la animacion con la que la tira se recoloca.
DESLIZADO = 260

COLOR_TEXTO = "#e0def4"
COLOR_TENUE = "#8b86a3"
COLOR_AMATISTA = "#b16cff"

CSS = f"""
window {{
    /* Transparente arriba y oscuro abajo: la franja de abajo es la unica parte
     * que tapa el fondo, y aun asi deja verlo.
     *
     * El `background-color: transparent` es obligatorio, no cosmetico: el tema
     * (Adwaita) pone un color opaco en `window` que queda DEBAJO del degradado y
     * tapa la pantalla entera, con lo que se pierde la idea de la app. Y hace
     * falta ademas el visual RGBA de _montar_capa: sin el, el alfa se compone
     * contra negro. Las dos cosas, o no hay velo. */
    background-color: transparent;
    /* El velo degradado NO se pone aqui: lo pinta Selector._pintar_fondo con
     * Cairo. Motivo: con el fondo por CSS, GTK solo repinta lo que cree danado y
     * en una ventana transparente los pixeles que quedan libres al recolocarse
     * algo no se limpian nunca — quedaban tarjetas fantasma pegadas en pantalla.
     * Pintandolo a mano se borra la superficie entera en cada fotograma. */
    color: {COLOR_TEXTO};
    font-family: "MesloLGS Nerd Font";
}}

/* La firma de la app. Pequena, espaciada y apagada: esta para decirte donde
 * estas, no para llamar la atencion. */
#marca {{
    font-size: 11px;
    color: {COLOR_AMATISTA};
    letter-spacing: 3px;
}}
/* Sombra en el texto que puede caer sobre imagen: el velo cubre el caso normal,
 * pero un fondo muy claro se come un texto claro. Con la sombra se lee siempre,
 * sin tener que oscurecer mas el velo y tapar el fondo. */
#titulo {{
    font-size: 27px;
    font-weight: bold;
    color: {COLOR_TEXTO};
    text-shadow: 0 2px 10px rgba(0, 0, 0, 0.95);
}}
#datos {{
    font-size: 12px;
    color: {COLOR_TENUE};
    text-shadow: 0 1px 6px rgba(0, 0, 0, 0.9);
}}
#contador {{
    text-shadow: 0 1px 6px rgba(0, 0, 0, 0.9);
    font-size: 22px;
    color: {COLOR_TENUE};
}}
#contador-total {{
    font-size: 13px;
    color: {COLOR_TENUE};
}}
#teclas {{
    text-shadow: 0 1px 6px rgba(0, 0, 0, 0.9);
    font-size: 11px;
    color: {COLOR_TENUE};
    letter-spacing: 1px;
}}
#nota {{
    text-shadow: 0 1px 6px rgba(0, 0, 0, 0.9);
    font-size: 11px;
    color: {COLOR_TENUE};
}}
#aviso {{
    font-size: 12px;
    color: #eb6f92;
}}

#difuminado-izq {{
    background-image: linear-gradient(to right,
        rgba(9, 3, 18, 0.92) 0%, rgba(9, 3, 18, 0.0) 100%);
}}
#difuminado-der {{
    background-image: linear-gradient(to left,
        rgba(9, 3, 18, 0.92) 0%, rgba(9, 3, 18, 0.0) 100%);
}}

scrolledwindow, scrolledwindow viewport {{ background-color: transparent; }}
/* La barra de desplazamiento se esconde: la tira se mueve sola con las flechas y
 * con la rueda, y una barra ahi solo seria ruido. */
scrollbar {{ opacity: 0; min-height: 0; }}
"""


def redondeado(cr, x, y, w, h, r):
    """Camino de un rectangulo con las esquinas redondeadas."""
    import math
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


class Tarjeta(Gtk.DrawingArea):
    """Una tarjeta de la tira: la miniatura recortada, y su estado."""

    def __init__(self, fondo, selector):
        super().__init__()
        self.fondo = fondo
        self.selector = selector
        self.pixbuf = None
        self.escalado = None      # la miniatura ya recortada al tamano exacto
        self.seleccionada = False
        self.en_uso = False

        self.set_size_request(TARJETA_W, TARJETA_H)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK
                        | Gdk.EventMask.ENTER_NOTIFY_MASK)
        self.connect("draw", self._dibujar)
        self.connect("button-press-event", self._clic)
        self.connect("enter-notify-event", self._entrar)

    # --- Imagen ---

    def poner_imagen(self, ruta):
        if not ruta or not os.path.exists(ruta):
            return
        try:
            self.pixbuf = GdkPixbuf.Pixbuf.new_from_file(ruta)
        except GLib.Error:
            return
        self.escalado = None
        self.queue_draw()

    def _recortar(self, w, h):
        """Escala la miniatura para LLENAR la tarjeta y recorta lo que sobra.

        Es el equivalente de background-size: cover. Importa porque las
        miniaturas no siempre traen la misma proporcion, y una tira con imagenes
        deformadas se ve mal a la primera.
        """
        if not self.pixbuf:
            return None
        if self.escalado and self.escalado.get_width() == w and self.escalado.get_height() == h:
            return self.escalado
        pw, ph = self.pixbuf.get_width(), self.pixbuf.get_height()
        if not pw or not ph:
            return None
        escala = max(w / pw, h / ph)
        nw, nh = max(1, int(pw * escala + 0.5)), max(1, int(ph * escala + 0.5))
        grande = self.pixbuf.scale_simple(nw, nh, GdkPixbuf.InterpType.BILINEAR)
        if grande is None:
            return None
        self.escalado = GdkPixbuf.Pixbuf.new_subpixbuf(
            grande, (nw - w) // 2, (nh - h) // 2, w, h)
        return self.escalado

    # --- Pintado ---

    def _dibujar(self, _widget, cr):
        ancho = self.get_allocated_width()
        alto = self.get_allocated_height()
        dentro = 0 if self.seleccionada else ENCOGIDO
        x, y = dentro, dentro
        w, h = ancho - dentro * 2, alto - dentro * 2

        if self.seleccionada:
            # Halo: tres rectangulos concentricos cada vez mas tenues. Da la
            # sensacion de que la tarjeta esta levantada y encendida.
            for i, alfa in ((7, 0.05), (4, 0.10), (2, 0.20)):
                redondeado(cr, x - i, y - i, w + i * 2, h + i * 2, RADIO + i)
                cr.set_source_rgba(0.69, 0.42, 1.0, alfa)
                cr.fill()

        redondeado(cr, x, y, w, h, RADIO)
        cr.clip()

        imagen = self._recortar(int(w), int(h))
        if imagen:
            Gdk.cairo_set_source_pixbuf(cr, imagen, x, y)
            cr.paint()
        else:
            # Sin miniatura todavia: un hueco liso, no un boquete negro.
            cr.set_source_rgba(0.10, 0.06, 0.18, 0.9)
            cr.rectangle(x, y, w, h)
            cr.fill()

        if not self.seleccionada:
            # Las no elegidas se apagan. Es lo que hace que la elegida resalte
            # sin necesidad de marcos ni flechas.
            cr.set_source_rgba(0.03, 0.01, 0.07, 0.52)
            cr.rectangle(x, y, w, h)
            cr.fill()

        cr.reset_clip()

        # El anillo de la elegida, por dentro del borde para que no se recorte.
        if self.seleccionada:
            redondeado(cr, x + 1, y + 1, w - 2, h - 2, RADIO - 1)
            cr.set_source_rgb(0.69, 0.42, 1.0)
            cr.set_line_width(2)
            cr.stroke()

        if self.en_uso:
            self._marca_en_uso(cr, x, y, w)

    def _marca_en_uso(self, cr, x, y, w):
        """Punto amatista arriba a la derecha: el fondo que esta puesto ahora."""
        cx, cy, r = x + w - 14, y + 14, 4.5
        cr.set_source_rgba(0.03, 0.01, 0.07, 0.75)
        cr.arc(cx, cy, r + 3.5, 0, 6.2832)
        cr.fill()
        cr.set_source_rgb(0.69, 0.42, 1.0)
        cr.arc(cx, cy, r, 0, 6.2832)
        cr.fill()

    # --- Interaccion ---

    def _clic(self, _widget, evento):
        if evento.button == 1:
            self.selector.elegir(self.fondo, aplicar=True)
        return True

    def _entrar(self, _widget, evento):
        """Pasar el puntero por encima ya cambia el fondo: es el gesto principal.

        Pero solo si el puntero se ha MOVIDO de verdad. Al navegar con las flechas
        la tira se desliza, y la tarjeta que pasa por debajo de un puntero quieto
        recibe tambien un enter-notify: sin esta comprobacion, el raton parado le
        robaba la seleccion al teclado y saltaba a otro fondo.
        """
        posicion = (round(evento.x_root), round(evento.y_root))
        if posicion == self.selector.ultimo_puntero:
            return False
        self.selector.ultimo_puntero = posicion
        self.selector.seleccionar(self.fondo, motivo="puntero")
        return False


class Selector(Gtk.Window):
    def __init__(self, fondos, no_usables=0):
        super().__init__()
        self.fondos = fondos
        self.no_usables = no_usables
        self.tarjetas = []
        self.indice = 0
        self.pendiente = None          # temporizador del retardo de la vista
        self.anim_desliz = None
        self.aplicado = False
        # Ultima posicion conocida del puntero: sirve para distinguir "el raton se
        # ha movido encima de una tarjeta" de "la tira se ha deslizado bajo un
        # raton quieto". Ver Tarjeta._entrar.
        self.ultimo_puntero = None

        self.hay_mpv = wp.mpv_vivo()
        self.original = wp.reproduciendo() or wp.actual()
        self.puesto = wp.actual()

        self._montar_capa()
        self._estilo()
        self._construir()

        # Mientras se elige, el demonio de ahorro no debe pausar el video: un
        # fotograma congelado no se puede juzgar.
        wp.avisar_pausa("hold")
        if self.hay_mpv:
            wp.mpv("set_property", "pause", False)
        # Y hay que poder ver el fondo: con ventanas abiertas esta tapado del
        # todo, asi que se aparta a un workspace vacio y se vuelve al cerrar.
        self.origen = wp.despejar_escritorio()

        self.connect("key-press-event", self._tecla)
        self.connect("button-press-event", self._clic_fuera)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.SCROLL_MASK)
        self.connect("scroll-event", self._rueda)
        self.connect("destroy", lambda *_: self._salir())

        self.show_all()

        # Arranca en el que esta puesto, sin previsualizar nada (ya se esta
        # viendo) y sin animar el deslizado: tiene que aparecer ya centrado.
        inicial = next((i for i, f in enumerate(self.fondos)
                        if os.path.realpath(f["video"]) == self.puesto), 0)
        self.indice = inicial
        self._pintar_seleccion()
        GLib.idle_add(self._centrar, inicial, False)
        GLib.idle_add(self._cargar_datos)

    # --- Montaje ---

    def _montar_capa(self):
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        for borde in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM,
                      GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
            GtkLayerShell.set_anchor(self, borde, True)
        # EXCLUSIVE y no ON_DEMAND: es un selector modal, las flechas y Escape
        # tienen que funcionar en cuanto aparece, sin clickar primero.
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        # Sin visual RGBA, GTK compone el alfa contra negro opaco y la ventana tapa
        # la pantalla entera. Con el, el velo es de verdad un velo.
        visual = Gdk.Screen.get_default().get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)
        # El fondo lo pintamos nosotros (ver _pintar_fondo).
        self.set_app_paintable(True)
        self.connect("draw", self._pintar_fondo)

    def _pintar_fondo(self, _widget, cr):
        """Borra la superficie entera y pinta el velo degradado de abajo.

        Dos cosas en una, y las dos hacen falta:

        1. El borrado va con OPERATOR_SOURCE y alfa 0, o sea que ESCRIBE
           transparencia en vez de mezclarse encima. Es lo que garantiza que no
           queden restos del fotograma anterior en una ventana transparente.
        2. El degradado sube desde el borde de abajo. Sus paradas estan puestas
           contra el texto: la zona del titulo y de la tira tiene que quedar lo
           bastante oscura para leerse sobre un fondo claro (hay fondos casi
           blancos), y de ahi para arriba el velo desaparece en ~100 px.

        Devuelve False para que los hijos (texto y tarjetas) se pinten encima.
        """
        import cairo

        ancho = self.get_allocated_width()
        alto = self.get_allocated_height()

        cr.save()
        cr.set_operator(cairo.Operator.SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.restore()

        # La franja de mas abajo va OPACA del todo, no al 96%: por debajo esta el
        # dock de waybar, que en un workspace vacio se queda fijo, y con el velo
        # translucido se le veian los iconos por detras de la tira. Opaco, el dock
        # desaparece mientras eliges y no hace falta pedirle nada a su demonio.
        velo = cairo.LinearGradient(0, alto, 0, alto - ALTO_VELO)
        for parada, alfa in ((0.00, 1.0), (0.58, 0.97), (0.78, 0.74), (1.00, 0.0)):
            velo.add_color_stop_rgba(parada, 0.035, 0.012, 0.07, alfa)
        cr.set_source(velo)
        cr.rectangle(0, alto - ALTO_VELO, ancho, ALTO_VELO)
        cr.fill()
        return False

    def _estilo(self):
        prov = Gtk.CssProvider()
        prov.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def _construir(self):
        raiz = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        raiz.set_valign(Gtk.Align.END)
        raiz.set_size_request(-1, ALTO_BLOQUE)
        self.add(raiz)
        self.raiz = raiz

        # --- Cabecera: nombre del fondo y sus datos ---
        cabecera = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        cabecera.set_margin_start(MARGEN)
        cabecera.set_margin_end(MARGEN)
        cabecera.set_margin_bottom(20)

        textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.marca = Gtk.Label(label="C E L I U Z P A P E R", xalign=0)
        self.marca.set_name("marca")
        self.titulo = Gtk.Label(label="", xalign=0)
        self.titulo.set_name("titulo")
        self.titulo.set_ellipsize(Pango.EllipsizeMode.END)
        self.datos = Gtk.Label(label="", xalign=0)
        self.datos.set_name("datos")
        textos.pack_start(self.marca, False, False, 0)
        textos.pack_start(self.titulo, False, False, 2)
        textos.pack_start(self.datos, False, False, 0)
        cabecera.pack_start(textos, True, True, 0)

        # Contador a la derecha, alineado con el titulo.
        cuenta = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        cuenta.set_valign(Gtk.Align.END)
        self.contador = Gtk.Label(label="", xalign=1)
        self.contador.set_name("contador")
        self.total = Gtk.Label(label=f"de {len(self.fondos)} fondos", xalign=1)
        self.total.set_name("contador-total")
        cuenta.pack_start(self.contador, False, False, 0)
        cuenta.pack_start(self.total, False, False, 0)
        cabecera.pack_start(cuenta, False, False, 0)

        raiz.pack_start(cabecera, False, False, 0)

        # --- La tira ---
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.NEVER)
        self.scroll.set_size_request(-1, TARJETA_H + 16)
        tira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=SEPARACION)
        # Media pantalla de aire a los lados: asi el primero y el ultimo tambien
        # pueden quedarse centrados.
        tira.set_margin_start(MARGEN)
        tira.set_margin_end(MARGEN)
        for fondo in self.fondos:
            tarjeta = Tarjeta(fondo, self)
            tarjeta.poner_imagen(wp.miniatura(fondo, generar=False))
            self.tarjetas.append(tarjeta)
            tira.pack_start(tarjeta, False, False, 0)
        self.scroll.add(tira)

        # La tira es mas ancha que la pantalla, asi que por los lados siempre hay
        # tarjetas cortadas. Dos velos degradados en los bordes las disuelven en la
        # oscuridad: se entiende que hay mas sin que el corte se vea como un error.
        capas = Gtk.Overlay()
        capas.add(self.scroll)
        for lado, clase in ((Gtk.Align.START, "difuminado-izq"),
                            (Gtk.Align.END, "difuminado-der")):
            velo = Gtk.Box()
            velo.set_name(clase)
            velo.set_halign(lado)
            velo.set_valign(Gtk.Align.FILL)
            velo.set_size_request(MARGEN + 26, -1)
            # El velo no debe comerse los clics ni el paso del puntero por las
            # tarjetas que tapa a medias.
            velo.set_can_focus(False)
            capas.add_overlay(velo)
            capas.set_overlay_pass_through(velo, True)
        raiz.pack_start(capas, False, False, 0)

        # --- Pie: las teclas y las notas ---
        pie = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        pie.set_margin_start(MARGEN)
        pie.set_margin_end(MARGEN)
        pie.set_margin_top(12)
        pie.set_margin_bottom(MARGEN - 18)
        teclas = Gtk.Label(
            label="←  →   elegir       ENTER / clic   poner       ESC   cancelar",
            xalign=0)
        teclas.set_name("teclas")
        pie.pack_start(teclas, True, True, 0)

        self.nota = Gtk.Label(label=self._texto_nota(), xalign=1)
        self.nota.set_name("aviso" if not self.hay_mpv else "nota")
        pie.pack_start(self.nota, False, False, 0)
        raiz.pack_start(pie, False, False, 0)

    def _texto_nota(self):
        if not self.hay_mpv:
            return "mpvpaper no esta corriendo: sin vista previa en vivo"
        escenas = self.no_usables
        if escenas:
            return f"{escenas} fondos de escena o web, que mpvpaper no puede usar"
        return ""

    # --- Seleccion y vista previa ---

    def seleccionar(self, fondo, motivo="teclado"):
        indice = self.fondos.index(fondo)
        if indice == self.indice and motivo == "puntero":
            return
        self.indice = indice
        self._pintar_seleccion()
        self._centrar(indice, True)
        self._programar_vista()

    def mover(self, delta):
        self.indice = max(0, min(len(self.fondos) - 1, self.indice + delta))
        self._pintar_seleccion()
        self._centrar(self.indice, True)
        self._programar_vista()

    def _pintar_seleccion(self):
        fondo = self.fondos[self.indice]
        for i, tarjeta in enumerate(self.tarjetas):
            elegida = i == self.indice
            en_uso = os.path.realpath(tarjeta.fondo["video"]) == self.puesto
            if elegida != tarjeta.seleccionada or en_uso != tarjeta.en_uso:
                tarjeta.seleccionada = elegida
                tarjeta.en_uso = en_uso
                tarjeta.queue_draw()

        self.titulo.set_text(fondo["titulo"])
        self.contador.set_text(f"{self.indice + 1}")
        marca = "  ·  EN USO" if os.path.realpath(fondo["video"]) == self.puesto else ""
        # Los datos se leen del cache si estan; si no, se rellenan luego para no
        # frenar el movimiento por la tira.
        self.datos.set_text(wp.describir(fondo, fondo.get("_info") or {}) + marca)
        # El texto cambia de ancho y la ventana es transparente: se repinta todo.
        self.queue_draw()

    def _programar_vista(self):
        if not self.hay_mpv:
            return
        if self.pendiente:
            GLib.source_remove(self.pendiente)
        self.pendiente = GLib.timeout_add(RETARDO_VISTA, self._aplicar_vista)

    def _aplicar_vista(self):
        self.pendiente = None
        wp.previsualizar(self.fondos[self.indice]["video"])
        return False

    # --- Deslizado de la tira ---

    def _centrar(self, indice, animar):
        """Deja la tarjeta elegida en el centro de la pantalla."""
        ajuste = self.scroll.get_hadjustment()
        if not ajuste:
            return False
        paso = TARJETA_W + SEPARACION
        objetivo = MARGEN + indice * paso + TARJETA_W / 2 - ajuste.get_page_size() / 2
        objetivo = max(0, min(objetivo, max(0, ajuste.get_upper() - ajuste.get_page_size())))

        if not animar:
            ajuste.set_value(objetivo)
            self.queue_draw()
            return False

        if self.anim_desliz:
            GLib.source_remove(self.anim_desliz)
        inicio = ajuste.get_value()
        reloj = GLib.get_monotonic_time()

        def paso_anim():
            t = (GLib.get_monotonic_time() - reloj) / 1000 / DESLIZADO
            if t >= 1:
                ajuste.set_value(objetivo)
                self.anim_desliz = None
                self.queue_draw()
                return False
            # easeOutCubic: sale rapido y frena al final, que es lo que hace que
            # el movimiento se sienta fluido y no mecanico.
            suave = 1 - (1 - t) ** 3
            ajuste.set_value(inicio + (objetivo - inicio) * suave)
            # Sin esto quedan restos del fotograma anterior: en una ventana
            # transparente GTK solo repinta la zona que cree danada.
            self.queue_draw()
            return True

        self.anim_desliz = GLib.timeout_add(16, paso_anim)
        return False

    # --- Carga en segundo plano ---

    def _cargar_miniaturas(self):
        """Genera las miniaturas que falten, de una en una y sin bloquear.

        La primera vez cuesta ~0.27 s por fondo. Hacerlo de golpe congelaria la
        ventana al abrirse, asi que se hace en ratos libres y cada tarjeta se
        refresca cuando le toca: la app abre al instante y se va rellenando.
        """
        for tarjeta in self.tarjetas:
            ruta = wp.miniatura(tarjeta.fondo, generar=False)
            if ruta and ruta.endswith(".jpg") and os.path.dirname(ruta) == wp.CACHE_MINIATURAS:
                continue
            GLib.idle_add(self._generar_una, tarjeta)
            return False
        return False

    def _generar_una(self, tarjeta):
        ruta = wp.miniatura(tarjeta.fondo, generar=True)
        tarjeta.poner_imagen(ruta)
        GLib.timeout_add(10, self._cargar_miniaturas)
        return False

    def _cargar_datos(self):
        for fondo in self.fondos:
            if "_info" not in fondo:
                fondo["_info"] = wp.datos(fondo)
                if fondo is self.fondos[self.indice]:
                    self._pintar_seleccion()
                GLib.timeout_add(10, self._cargar_datos)
                return False
        self._pintar_seleccion()
        # Los datos ya estan; ahora las miniaturas de verdad, que son lo caro.
        GLib.timeout_add(10, self._cargar_miniaturas)
        return False

    # --- Poner, cancelar, salir ---

    def elegir(self, fondo, aplicar=False):
        self.seleccionar(fondo)
        if aplicar:
            self.aplicar()

    def aplicar(self):
        fondo = self.fondos[self.indice]
        try:
            wp.aplicar(fondo["video"])
        except OSError as error:
            self.titulo.set_text(f"no se pudo poner: {error}")
            return
        self.puesto = os.path.realpath(fondo["video"])
        self.aplicado = True
        self._pintar_seleccion()
        # Un instante para que se vea la marca de "en uso" moverse a la tarjeta
        # antes de que la ventana desaparezca: el cambio queda confirmado a la
        # vista, no solo de palabra.
        GLib.timeout_add(220, lambda: (self.close(), False)[1])

    def cancelar(self):
        if self.hay_mpv and self.original and not self.aplicado:
            wp.previsualizar(self.original)
        self.close()

    def _salir(self):
        if self.pendiente:
            GLib.source_remove(self.pendiente)
            self.pendiente = None
        # Te deja donde estabas, con tus ventanas.
        wp.volver_al_escritorio(getattr(self, "origen", None))
        # El demonio de ahorro vuelve a mandar: si hay ventanas abiertas, pausara
        # el fondo el mismo en cuanto lea esto.
        wp.avisar_pausa("release")
        Gtk.main_quit()

    # --- Entrada ---

    def _tecla(self, _w, evento):
        nombre = Gdk.keyval_name(evento.keyval)
        if nombre in ("Escape", "q"):
            self.cancelar()
        elif nombre in ("Right", "l", "Down", "Tab"):
            self.mover(1)
        elif nombre in ("Left", "h", "Up", "ISO_Left_Tab"):
            self.mover(-1)
        elif nombre in ("Return", "KP_Enter", "space"):
            self.aplicar()
        elif nombre == "Home":
            self.mover(-len(self.fondos))
        elif nombre == "End":
            self.mover(len(self.fondos))
        elif nombre == "r":
            self.mover(random.randint(1, max(1, len(self.fondos) - 1)))
        return True

    def _rueda(self, _w, evento):
        direccion = evento.direction
        if direccion == Gdk.ScrollDirection.SMOOTH:
            _, dx, dy = evento.get_scroll_deltas()
            delta = dx or dy
            if abs(delta) < 0.1:
                return True
            self.mover(1 if delta > 0 else -1)
        elif direccion in (Gdk.ScrollDirection.DOWN, Gdk.ScrollDirection.RIGHT):
            self.mover(1)
        elif direccion in (Gdk.ScrollDirection.UP, Gdk.ScrollDirection.LEFT):
            self.mover(-1)
        return True

    def _clic_fuera(self, _w, evento):
        # Clic en la zona de arriba (el fondo, no la tira): cancelar. Es lo que
        # espera cualquiera de un selector que se abre encima de todo.
        altura = self.get_allocated_height()
        if evento.y < altura - self.raiz.get_allocated_height():
            self.cancelar()
        return False


# --- Terminal -----------------------------------------------------------------

def cli_list():
    fondos = wp.escanear()
    puesto = wp.actual()
    us = wp.usables(fondos)
    print(f"\n  CELIUZPAPER  ·  {len(us)} fondos usables de {len(fondos)}\n")
    print("  " + "─" * 66)
    for fondo in us:
        marca = "●" if os.path.realpath(fondo["video"]) == puesto else " "
        print(f"  {marca} {fondo['titulo'][:44]:44}  {wp.describir(fondo)}")
    otros = [f for f in fondos if not f["usable"]]
    if otros:
        tipos = {}
        for f in otros:
            tipos[f["tipo"]] = tipos.get(f["tipo"], 0) + 1
        detalle = ", ".join(f"{n} de {t}" for t, n in sorted(tipos.items()))
        print("  " + "─" * 66)
        print(f"  No usables por mpvpaper: {detalle}")
    print(f"\n  ● = puesto ahora. Para cambiar:  celiuzpaper --set <texto>\n")


def cli_set(texto):
    encontrados = wp.buscar(texto)
    if not encontrados:
        sys.exit(f"celiuzpaper: ningun fondo coincide con «{texto}»")
    if len(encontrados) > 1:
        print(f"«{texto}» coincide con {len(encontrados)}; se usa el primero:")
        for f in encontrados:
            print(f"  - {f['titulo']}")
    fondo = encontrados[0]
    wp.aplicar(fondo["video"])
    print(f"Fondo: {fondo['titulo']}")


def cli_random():
    us = wp.usables()
    puesto = wp.actual()
    candidatos = [f for f in us if os.path.realpath(f["video"]) != puesto] or us
    if not candidatos:
        sys.exit("celiuzpaper: no hay fondos usables")
    fondo = random.choice(candidatos)
    wp.aplicar(fondo["video"])
    print(f"Fondo: {fondo['titulo']}")


def main():
    args = sys.argv[1:]
    if args:
        orden = args[0]
        if orden in ("-l", "--list"):
            return cli_list()
        if orden in ("-s", "--set"):
            if len(args) < 2:
                sys.exit("celiuzpaper --set <texto o ruta>")
            resto = " ".join(args[1:])
            if os.path.isfile(resto):
                wp.aplicar(resto)
                return print(f"Fondo: {os.path.basename(resto)}")
            return cli_set(resto)
        if orden in ("-r", "--random"):
            return cli_random()
        if orden in ("-c", "--current"):
            puesto = wp.actual()
            return print(puesto or "(ninguno)")
        if orden in ("-h", "--help"):
            return print(__doc__.strip())
        sys.exit(f"celiuzpaper: no entiendo «{orden}». Prueba --help")

    fondos = wp.escanear()
    us = wp.usables(fondos)
    if not us:
        sys.exit("celiuzpaper: no encuentro ningun fondo de video utilizable.\n"
                 "Suscribete a fondos de tipo VIDEO en el Workshop de Wallpaper "
                 "Engine, o pon tus propios videos en ~/dotfiles/hypr/wallpapers/propios/")

    selector = Selector(us, no_usables=len(fondos) - len(us))

    # Si a la app la matan (kill, cierre de sesion, un fallo), tiene que dejar el
    # sistema como estaba: sin el `hold` del demonio de ahorro puesto, con el fondo
    # de antes y en tu workspace. Sin esto, un kill dejaba el video sin pausar y a
    # ti en un escritorio vacio.
    for senal in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, senal,
                             lambda *_: (selector.cancelar(), False)[1])
    Gtk.main()


if __name__ == "__main__":
    main()
