#!/usr/bin/env python3
"""
hypr/scripts/calendar-panel.py

El panel que cuelga del reloj de la barra: calendario, la hora con el tiempo de
las proximas horas girando alrededor, la luna y el zodiaco. Es la misma capa que
los paneles del Bluetooth y de la red (lib/panel_capa.py), en ancho.

A LA IZQUIERDA, el calendario de siempre:
  - los feriados y celebraciones del Peru (lib/pe_fechas.py, sin red) y tus
    eventos de Google Calendar (lib/gcal.py, desde la cache local);
  - el detalle del dia que elijas, y el proximo feriado;
  - la fase de la luna (lib/cielo.py: aritmetica, sin red);
  - el signo del zodiaco en curso, y si pones el tuyo en clima.conf, cuanto
    falta para que llegue. Es un extra por diversion.

A LA DERECHA, el tiempo (lib/clima.py, de Open-Meteo):
  - la temperatura y como esta el cielo, arriba;
  - la hora grande, con las PROXIMAS HORAS GIRANDO a su alrededor en una
    elipse, despacio (una vuelta cada GIRO segundos). La que pasa por delante se
    resalta; las de detras se ven mas pequeñas y apagadas, como en perspectiva;
  - el arco del sol (salida y puesta) y cuatro medidores: viento, humedad,
    probabilidad de lluvia y sensacion termica.

El tiempo se pide SOLO al abrir el panel, y como mucho cada 15 minutos; la
ubicacion, una vez por red y a nivel de ciudad. Las reglas, y como no preguntar
nunca, estan en la cabecera de lib/clima.py.

La animacion solo corre con el panel abierto: cerrado no gasta nada.

Se comporta como un boton: correrlo otra vez mientras esta abierto lo cierra.

    calendar-panel.py           abre el panel (o lo cierra)
    calendar-panel.py --ver     lo que enseñaria, en texto
"""

import datetime as dt
import math
import os
import subprocess
import sys
import threading
import time

RAIZ = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(RAIZ, "lib"))

import cielo  # noqa: E402
import clima  # noqa: E402
import gcal  # noqa: E402
import pe_fechas  # noqa: E402

# Unos 640x340: el tamaño del de referencia que trajo el usuario, en la
# pantalla de la laptop (1366x768). Antes medía 760x523 y tapaba media pantalla.
ANCHO_PANEL = 640
ANCHO_IZQ = 228
ALTO_CIELO = 300
GIRO = 240           # segundos por vuelta: «continuo pero lento»
FPS = 15
CACHE_GCAL_VIEJO = 300

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "setiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
DIAS_CORTOS = ["L", "M", "M", "J", "V", "S", "D"]

G_FERIADO = "\U000F00ED"
G_SALE = "\U000F059C"
G_PONE = "\U000F059B"
G_VIENTO = "\U000F059D"
G_HUMEDAD = "\U000F058E"
G_LLUVIA = "\U000F0597"
G_TERMO = "\U000F050F"


# ─────────────────────────────────────────────────────────────────────────────
# Lo que se calcula (sin GTK: lo prueba tests/unidad/reloj-panel.sh)
# ─────────────────────────────────────────────────────────────────────────────

def proximo_feriado(desde):
    """(fecha, nombre, dias) del siguiente feriado desde mañana; None si nada
    en un año (no pasa, pero no se cuelga)."""
    for n in range(1, 370):
        f = desde + dt.timedelta(days=n)
        for tipo, nombre in pe_fechas.del_dia(f):
            if tipo == pe_fechas.FERIADO:
                return f, nombre, n
    return None


def _minutos(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def arco_sol(ahora_min, salida, puesta):
    """Lo recorrido del dia (0..1), o None de noche."""
    s, p = _minutos(salida), _minutos(puesta)
    if p <= s or not (s <= ahora_min <= p):
        return None
    return (ahora_min - s) / (p - s)


def medidores(t):
    """[(glifo, valor como texto, fraccion 0..1, nombre)] del tiempo."""
    def tope(x, a, b):
        return max(0.0, min(1.0, (x - a) / (b - a)))
    return [
        (G_VIENTO, "%.1f m/s" % t["viento"], tope(t["viento"], 0, 15), "Viento"),
        (G_HUMEDAD, "%d%%" % round(t["humedad"]), t["humedad"] / 100, "Humedad"),
        (G_LLUVIA, "%d%%" % round(t["lluvia"]), t["lluvia"] / 100, "Lluvia"),
        (G_TERMO, "%d°C" % round(t["sensacion"]), tope(t["sensacion"], -5, 40), "Sensación"),
    ]


def orbita(n, t, cx, cy, rx, ry):
    """Donde va cada una de las `n` horas en el instante `t` (0..1 de vuelta):
    [(i, x, y, profundidad 0..1, delante)]. La 0 esta delante (abajo) en t=0;
    giran en el sentido del reloj visto desde arriba. `delante` lo lleva la
    que este mas cerca del frente, y solo una."""
    paso = 2 * math.pi / n
    puestos = []
    for i in range(n):
        a = math.pi / 2 + (i - t * n) * paso
        puestos.append([i, cx + rx * math.cos(a), cy + ry * math.sin(a), (math.sin(a) + 1) / 2, False])
    frente = max(puestos, key=lambda p: p[3])
    frente[4] = True
    return [tuple(p) for p in puestos]


def texto_zodiaco(hoy, signo_propio=""):
    z = cielo.zodiaco(hoy)
    lineas = ["%s  %s · hasta el %d %s" % (z["glifo"], z["nombre"], z["hasta"].day,
                                          MESES[z["hasta"].month - 1][:3]),
              z["frase"]]
    propio = cielo.buscar_signo(signo_propio) if signo_propio else None
    if propio:
        dias = cielo.dias_para(propio[1], hoy)
        lineas.append("%s  %s (tú) · %s" % (propio[2], propio[0],
                                             "¡es tu temporada!" if dias == 0 else
                                             "mañana" if dias == 1 else "en %d días" % dias))
    return lineas


def ver():
    hoy = dt.date.today()
    print("%s %d de %s" % (DIAS[hoy.weekday()], hoy.day, MESES[hoy.month - 1]))
    pf = proximo_feriado(hoy)
    if pf:
        print("Próximo feriado: %s, en %d días" % (pf[1], pf[2]))
    l = cielo.luna()
    print("Luna: %s, %d%%" % (l["nombre"], round(l["iluminada"] * 100)))
    print("Zodiaco: " + " · ".join(texto_zodiaco(hoy, clima.ajustes()["signo"])))
    c = clima._leer(clima.fichero_tiempo())
    if c.get("tiempo"):
        t = c["tiempo"]
        print("Tiempo (cache de hace %s): %s°C %s" % (clima.hace(time.time() - c["cuando"]),
                                                      t["temp"], t["texto"]))
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# La ventana
# ─────────────────────────────────────────────────────────────────────────────

def abrir_panel():
    try:
        import panel_capa as pc
    except (ImportError, ValueError):
        subprocess.Popen(["notify-send", "-a", "Reloj", "Falta gtk-layer-shell",
                          "Sin él no puede abrirse el panel del reloj.\n"
                          "sudo pacman -S gtk-layer-shell"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return 1
    if not pc.solo_wayland():
        print("calendar-panel: hace falta una sesion Wayland", file=sys.stderr)
        return 1
    import dibujo
    from gi.repository import Pango as P
    GLib, Gtk, Gdk = pc.GLib, pc.Gtk, pc.Gdk
    etiqueta, boton, caja = pc.etiqueta, pc.boton, pc.caja
    C = dibujo.C
    hx = {k: pc_hex(v) for k, v in C.items()}

    CSS_EXTRA = f"""
    #izq {{ border-right: 1px solid {hx['apagado']}; padding: 2px 14px 2px 2px; }}
    #marco {{ padding: 10px 12px; }}
    #mes {{ font-size: 13px; font-weight: bold; }}
    button.nav {{ border: none; padding: 0 8px; }}
    button.nav label {{ color: {hx['amatista']}; font-size: 15px; }}
    .dsem {{ color: {hx['amatista']}; font-weight: bold; font-size: 10px; }}
    button.dia {{ border: 1px solid transparent; border-radius: 7px; padding: 0;
                  min-width: 28px; min-height: 20px; }}
    button.dia label {{ font-size: 12px; }}
    button.dia.otromes label {{ color: {hx['apagado']}; }}
    button.dia.domingo label {{ color: {hx['tenue']}; }}
    button.dia.feriado label {{ color: {hx['alerta']}; font-weight: bold; }}
    button.dia.hoy {{ background-color: {hx['violeta']}; }}
    button.dia.hoy label {{ color: {hx['luz']}; font-weight: bold; }}
    button.dia.sel {{ border-color: {hx['amatista']}; }}
    .bloque {{ border-top: 1px solid {hx['apagado']}; padding-top: 5px; margin-top: 5px; }}
    .fecha {{ color: {hx['amatista']}; font-weight: bold; font-size: 11px; }}
    .linea {{ font-size: 11px; }}
    #izq .tenue {{ font-size: 11px; }}
    .feriado-t {{ color: {hx['alerta']}; font-size: 11px; }}
    .celebra-t {{ color: {hx['atencion']}; font-size: 11px; }}
    .evento-t {{ color: {hx['neon']}; font-size: 11px; }}
    """

    class Panel(pc.PanelCapa):
        def __init__(self):
            super().__init__("calendar-panel", "", "", CSS_EXTRA, ancho=ANCHO_PANEL,
                             esqueleto=False)
            self.hoy = dt.date.today()
            self.seleccion = self.hoy
            self.mes = self.hoy.replace(day=1)
            self.eventos = gcal.cargar_cache()
            self.ajustes = clima.ajustes()
            self.tiempo = None          # lo que devuelve clima.obtener()
            self.leyendo = False
            self.inicio = time.monotonic()
            self.luna = cielo.luna()

            fila = caja(espacio=0)
            self.marco.pack_start(fila, True, True, 0)
            izq = caja(vertical=True, espacio=0)
            izq.set_name("izq")
            izq.set_valign(Gtk.Align.START)
            izq.set_size_request(ANCHO_IZQ, -1)
            fila.pack_start(izq, False, False, 0)
            self._izquierda(izq)

            self.lienzo = Gtk.DrawingArea()
            self.lienzo.set_size_request(ANCHO_PANEL - ANCHO_IZQ - 30, ALTO_CIELO)
            self.lienzo.connect("draw", self._dibujar)
            fila.pack_start(self.lienzo, True, True, 0)

            self.add_events(Gdk.EventMask.SCROLL_MASK)
            self.connect("scroll-event", self._rueda)
            self.connect("key-press-event", self._teclas)

            self._pintar_mes()
            self._pedir_tiempo()
            GLib.timeout_add(int(1000 / FPS), self._animar)
            GLib.timeout_add_seconds(clima.FRESCO, lambda: self._pedir_tiempo() or True)
            self._refrescar_gcal()

        # --- La columna del calendario -------------------------------------

        def _izquierda(self, izq):
            cab = caja()
            cab.pack_start(boton("‹", lambda: self._mover_mes(-1), ("nav",)), False, False, 0)
            self.titulo_mes = etiqueta(nombre="mes", xalign=0.5)
            cab.pack_start(self.titulo_mes, True, True, 0)
            cab.pack_start(boton("›", lambda: self._mover_mes(1), ("nav",)), False, False, 0)
            izq.pack_start(cab, False, False, 0)

            self.rejilla = Gtk.Grid()
            self.rejilla.set_column_homogeneous(True)
            self.rejilla.set_row_spacing(0)
            izq.pack_start(self.rejilla, False, False, 2)

            self.detalle = caja(vertical=True, espacio=2)
            self.detalle.get_style_context().add_class("bloque")
            izq.pack_start(self.detalle, False, False, 0)

            # La luna, en dos lineas: los ocho discos y «fase · % · llena el».
            lunas = caja(vertical=True, espacio=2)
            lunas.get_style_context().add_class("bloque")
            l = self.luna
            dib = Gtk.DrawingArea()
            dib.set_size_request(ANCHO_IZQ - 12, 24)
            dib.connect("draw", self._dibujar_lunas)
            lunas.pack_start(dib, False, False, 0)
            llena = l["proxima_llena"].astimezone()
            pie_l = caja()
            nombre_l = etiqueta(l["nombre"], ("linea",))
            nombre_l.set_ellipsize(P.EllipsizeMode.END)
            pie_l.pack_start(nombre_l, True, True, 0)
            # El porcentaje no cabe al lado: va en el tooltip.
            nombre_l.set_tooltip_text("%d%% iluminada" % round(l["iluminada"] * 100))
            pie_l.pack_end(etiqueta("llena %d %s" % (llena.day, MESES[llena.month - 1][:3]),
                                    ("tenue",)), False, False, 0)
            lunas.pack_start(pie_l, False, False, 0)
            izq.pack_start(lunas, False, False, 0)

            # El zodiaco: el signo en curso con su frase, y el tuyo si lo pusiste.
            zod = caja(vertical=True, espacio=0)
            zod.get_style_context().add_class("bloque")
            lineas = texto_zodiaco(self.hoy, self.ajustes["signo"])
            z = cielo.zodiaco(self.hoy)
            primera = etiqueta("%s  %s · %s" % (z["glifo"], z["nombre"], z["frase"]), ("linea",))
            primera.set_ellipsize(P.EllipsizeMode.END)
            zod.pack_start(primera, False, False, 0)
            segunda = lineas[2] if len(lineas) > 2 else "hasta el %d %s" % (
                z["hasta"].day, MESES[z["hasta"].month - 1][:3])
            zod.pack_start(etiqueta(segunda, ("tenue",)), False, False, 0)
            izq.pack_start(zod, False, False, 0)

        def _pintar_mes(self):
            for h in self.rejilla.get_children():
                self.rejilla.remove(h)
            self.titulo_mes.set_text("%s %d" % (MESES[self.mes.month - 1], self.mes.year))
            for col, n in enumerate(DIAS_CORTOS):
                self.rejilla.attach(etiqueta(n, ("dsem",), xalign=0.5), col, 0, 1, 1)
            inicio = self.mes - dt.timedelta(days=self.mes.weekday())
            for i in range(42):
                f = inicio + dt.timedelta(days=i)
                fila, col = divmod(i, 7)
                self.rejilla.attach(self._dia(f), col, fila + 1, 1, 1)
            self.rejilla.show_all()
            self._pintar_detalle()

        def _eventos_de(self, f):
            marcas = pe_fechas.del_dia(f)
            return [e for e in self.eventos.get(f.isoformat(), [])
                    if not (e.get("festivo") and marcas)]

        def _dia(self, f):
            marcas = pe_fechas.del_dia(f)
            feriado = any(t == pe_fechas.FERIADO for t, _ in marcas)
            celebra = any(t == pe_fechas.CELEBRACION for t, _ in marcas)
            eventos = self._eventos_de(f)
            # Numero y debajo los puntitos: feriado, celebracion, algo tuyo.
            puntos = ""
            if feriado:
                puntos += "<span color='%s'>•</span>" % hx["alerta"]
            elif celebra:
                puntos += "<span color='%s'>•</span>" % hx["atencion"]
            if eventos:
                puntos += "<span color='%s'>•</span>" % hx["neon"]
            e = Gtk.Label()
            e.set_markup("<span size='8500'>%d</span>\n<span size='4000'>%s</span>"
                         % (f.day, puntos or " "))
            e.set_justify(Gtk.Justification.CENTER)
            b = Gtk.Button()
            b.add(e)
            b.set_relief(Gtk.ReliefStyle.NONE)
            b.set_can_focus(False)
            ctx = b.get_style_context()
            ctx.add_class("dia")
            if f.month != self.mes.month:
                ctx.add_class("otromes")
            if feriado:
                ctx.add_class("feriado")
            elif f.weekday() == 6:
                ctx.add_class("domingo")
            if f == self.hoy:
                ctx.add_class("hoy")
            elif f == self.seleccion:
                ctx.add_class("sel")
            b.connect("clicked", lambda *_: self._elegir(f))
            return b

        def _pintar_detalle(self):
            for h in self.detalle.get_children():
                self.detalle.remove(h)
            f = self.seleccion
            cab = "%s %d de %s" % (DIAS[f.weekday()], f.day, MESES[f.month - 1])
            linea = caja(espacio=6)
            linea.pack_start(etiqueta(cab, ("fecha",)), False, False, 0)
            if f == self.hoy:
                linea.pack_start(etiqueta("· hoy", ("tenue",)), False, False, 0)
            self.detalle.pack_start(linea, False, False, 0)
            cosas = 0
            for tipo, nombre in pe_fechas.del_dia(f):
                self.detalle.pack_start(etiqueta(
                    ("%s  %s" % (G_FERIADO, nombre)),
                    ("feriado-t" if tipo == pe_fechas.FERIADO else "celebra-t",)), False, False, 0)
                cosas += 1
            for ev in self._eventos_de(f)[:3]:
                e = etiqueta("%s  %s" % (ev["hora"] or "todo el día", ev["titulo"]), ("evento-t",))
                e.set_ellipsize(P.EllipsizeMode.END)
                e.set_max_width_chars(30)
                self.detalle.pack_start(e, False, False, 0)
                cosas += 1
            if not cosas:
                # Sin nada ese dia, la linea la ocupa el proximo feriado: asi no
                # hace falta un bloque aparte (el panel pasaba de 500 px de alto).
                self.detalle.pack_start(etiqueta("Nada anotado este día", ("tenue",)),
                                        False, False, 0)
                pf = proximo_feriado(f)
                if pf:
                    e = etiqueta("%s  %s · %d %s" % (
                        G_FERIADO, pf[1].replace("Dia de ", "").replace("Día de ", ""),
                        pf[0].day, MESES[pf[0].month - 1][:3]), ("feriado-t",))
                    e.set_ellipsize(P.EllipsizeMode.END)
                    e.set_tooltip_text("Próximo feriado: %s, %s" % (
                        pf[1], "mañana" if pf[2] == 1 else "en %d días" % pf[2]))
                    self.detalle.pack_start(e, False, False, 0)
            self.detalle.show_all()

        def _elegir(self, f):
            self.seleccion = f
            if (f.year, f.month) != (self.mes.year, self.mes.month):
                self.mes = f.replace(day=1)
            self._pintar_mes()

        def _mover_mes(self, delta):
            m = self.mes.month - 1 + delta
            self.mes = dt.date(self.mes.year + m // 12, m % 12 + 1, 1)
            self._pintar_mes()

        def _rueda(self, _w, ev):
            if ev.direction == Gdk.ScrollDirection.UP:
                self._mover_mes(-1)
            elif ev.direction == Gdk.ScrollDirection.DOWN:
                self._mover_mes(1)
            return True

        def _teclas(self, _w, ev):
            n = Gdk.keyval_name(ev.keyval)
            if n in ("Left", "Page_Up"):
                self._mover_mes(-1)
            elif n in ("Right", "Page_Down"):
                self._mover_mes(1)
            elif n in ("Home", "t"):
                self.mes, self.seleccion = self.hoy.replace(day=1), self.hoy
                self._pintar_mes()
            else:
                return False
            return True

        def _refrescar_gcal(self):
            if not gcal.hay_sesion():
                return
            edad = gcal.edad_cache()
            if edad is not None and edad < CACHE_GCAL_VIEJO:
                return
            try:
                proc = subprocess.Popen([sys.executable, os.path.join(RAIZ, "lib", "gcal.py"),
                                         "sync"], stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)
            except OSError:
                return

            def mirar():
                if proc.poll() is None:
                    return True
                self.eventos = gcal.cargar_cache()
                self._pintar_mes()
                return False
            GLib.timeout_add_seconds(3, mirar)

        # --- El tiempo ----------------------------------------------------

        def _pedir_tiempo(self):
            if self.leyendo:
                return
            self.leyendo = True

            def hilo():
                try:
                    r = clima.obtener()
                except Exception as e:  # noqa: BLE001 — el reloj tiene que salir igual
                    r = {"error": str(e)}
                GLib.idle_add(lambda: self._tiempo_listo(r) or False)
            threading.Thread(target=hilo, daemon=True).start()

        def _tiempo_listo(self, r):
            self.leyendo = False
            self.tiempo = r
            self.lienzo.queue_draw()

        def _animar(self):
            self.lienzo.queue_draw()
            # A medianoche cambia el «hoy».
            if dt.date.today() != self.hoy:
                self.hoy = dt.date.today()
                self._pintar_mes()
            return True

        # --- Dibujar ------------------------------------------------------

        def _dibujar_lunas(self, w, cr):
            ancho = w.get_allocated_width()
            n = len(cielo.FASES_DIBUJO)
            r = 9
            paso = (ancho - 2 * r - 4) / (n - 1)
            for i, (k, creciente) in enumerate(cielo.FASES_DIBUJO):
                cx, cy = 2 + r + i * paso, 12
                dibujar_luna(cr, cx, cy, r, k, creciente, C)
                if i == self.luna["fase"]:
                    cr.set_source_rgba(*C["neon"], 1)
                    cr.set_line_width(2)
                    dibujo.circulo(cr, cx, cy, r + 2.5)
                    cr.stroke()
            return False

        def _dibujar(self, w, cr):
            ancho, alto = w.get_allocated_width(), w.get_allocated_height()
            ahora = dt.datetime.now()
            r = self.tiempo or {}
            t = r.get("tiempo")

            # Arriba: donde, y el tiempo de ahora.
            lugar = r.get("ciudad") or ""
            if r.get("apagado"):
                cabecera = ""
            elif t:
                cabecera = "%s · hace %s" % (lugar, clima.hace(r.get("edad", 0))) if lugar else ""
            elif self.leyendo or not r:
                cabecera = "pidiendo el tiempo…"
            else:
                cabecera = r.get("error", "")
            dibujo.texto(cr, cabecera, 10, 4, 11, C["tenue"], ancho=ancho * 0.5, una_linea=True)
            if t:
                dibujo.texto(cr, "%d°C" % round(t["temp"]), ancho - 8, -2, 32, C["neon"],
                             peso=P.Weight.BOLD, derecha=True)
                dibujo.texto(cr, "%s · sensación %d°" % (t["texto"], round(t["sensacion"])),
                             ancho - 8, 40, 11, C["tenue"], derecha=True)
            elif r.get("error") and not r.get("apagado"):
                dibujo.texto(cr, r["error"], 10, 22, 10, C["alerta"], ancho=ancho - 20)

            # La orbita: lo de detras, la hora, y lo de delante encima.
            # Centrada en lo que queda entre la cabecera (~58 px) y el sol y
            # los medidores (~84): el alto lo pone la columna del calendario.
            cx, rx = ancho / 2, ancho / 2 - 30
            ry = max(44, min(64, (alto - 142) * 0.32))
            cy = 58 + (alto - 58 - 84) / 2 + 12
            cr.set_source_rgba(*C["amatista"], 0.45)
            cr.set_line_width(1.4)
            cr.set_dash([5, 5])
            cr.save()
            cr.translate(cx, cy)
            cr.scale(rx, ry)
            cr.arc(0, 0, 1, 0, 2 * math.pi)
            cr.restore()
            cr.stroke()
            cr.set_dash([])

            horas = (t or {}).get("horas") or []
            vuelta = ((time.monotonic() - self.inicio) % GIRO) / GIRO
            puestos = orbita(len(horas), vuelta, cx, cy, rx, ry) if horas else []
            for p in sorted(puestos, key=lambda p: p[3]):
                if p[3] < 0.5:
                    self._hora_orbita(cr, horas[p[0]], p)
            reloj = ahora.strftime("%H:%M")
            tw, th = dibujo.medir(cr, reloj, 42, P.Weight.BOLD)
            sw, _ = dibujo.medir(cr, ahora.strftime(":%S"), 16)
            x0 = cx - (tw + sw) / 2
            arriba = cy - 58
            dibujo.texto(cr, reloj, x0, arriba, 42, C["luz"], peso=P.Weight.BOLD)
            dibujo.texto(cr, ahora.strftime(":%S"), x0 + tw, arriba + th - 25, 16, C["amatista"])
            dibujo.texto(cr, "%s, %d de %s" % (DIAS[ahora.weekday()], ahora.day,
                                               MESES[ahora.month - 1]),
                         cx, arriba + th - 4, 11, C["tenue"], centro=True)
            for p in sorted(puestos, key=lambda p: p[3]):
                if p[3] >= 0.5:
                    self._hora_orbita(cr, horas[p[0]], p)

            # Abajo: el sol y los medidores.
            if t:
                self._sol(cr, 4, alto - 58, t, ahora)
                x = ancho - 6
                for glifo, valor, frac, nombre in reversed(medidores(t)):
                    self._medidor(cr, x - 24, alto - 42, glifo, valor, frac, nombre)
                    x -= 58
            return False

        def _hora_orbita(self, cr, h, p):
            _i, x, y, prof, delante = p
            texto, glifo = clima.describir(h["codigo"], h["dia"])
            if delante:
                w, al = 56, 60
                dibujo.redondo(cr, x - w / 2, y - al / 2, w, al, 12)
                cr.set_source_rgba(*C["violeta"], 0.95)
                cr.fill_preserve()
                cr.set_source_rgba(*C["neon"], 1)
                cr.set_line_width(1.2)
                cr.stroke()
                dibujo.texto(cr, h["hora"], x, y - 26, 10, C["luz"], centro=True)
                dibujo.texto(cr, glifo, x, y - 12, 16, C["luz"], centro=True)
                dibujo.texto(cr, "%d°C" % round(h["temp"]), x, y + 9, 12, C["luz"],
                             peso=P.Weight.BOLD, centro=True)
                return
            alfa = 0.25 + 0.6 * prof
            esc = 0.7 + 0.3 * prof
            dibujo.texto(cr, h["hora"], x, y - 19 * esc, 9 * esc, C["tenue"], alfa=alfa,
                         centro=True)
            dibujo.texto(cr, glifo, x, y - 8 * esc, 12 * esc, C["amatista"], alfa=alfa,
                         centro=True)
            dibujo.texto(cr, "%d°" % round(h["temp"]), x, y + 6 * esc, 9 * esc, C["tenue"],
                         alfa=alfa, centro=True)

        def _sol(self, cr, x, y, t, ahora):
            w, alto_arco = 112, 38
            cx, base = x + w / 2, y + alto_arco + 4
            recorrido = arco_sol(ahora.hour * 60 + ahora.minute, t["salida"], t["puesta"])
            cr.set_line_width(4)
            cr.set_line_cap(1)
            cr.save()
            cr.translate(cx, base)
            cr.scale(w / 2 - 6, alto_arco)
            cr.arc(0, 0, 1, math.pi, 2 * math.pi)
            cr.restore()
            cr.set_source_rgba(*C["apagado"], 1)
            cr.stroke()
            if recorrido is not None:
                cr.save()
                cr.translate(cx, base)
                cr.scale(w / 2 - 6, alto_arco)
                cr.arc(0, 0, 1, math.pi, math.pi + math.pi * recorrido)
                cr.restore()
                cr.set_source_rgba(*C["amatista"], 1)
                cr.stroke()
                a = math.pi + math.pi * recorrido
                sx, sy = cx + (w / 2 - 6) * math.cos(a), base + alto_arco * math.sin(a)
                cr.set_source_rgba(*C["atencion"], 1)
                dibujo.circulo(cr, sx, sy, 6)
                cr.fill()
            else:
                dibujo.texto(cr, clima.LUNA_G, cx, base - 26, 14, C["neon"], centro=True)
            dibujo.texto(cr, "%s %s  %s %s" % (G_SALE, t["salida"], G_PONE, t["puesta"]),
                         cx, base + 3, 10, C["tenue"], centro=True)

        def _medidor(self, cr, cx, cy, glifo, valor, frac, nombre):
            r = 16
            cr.set_line_width(3.5)
            cr.set_source_rgba(*C["apagado"], 1)
            dibujo.circulo(cr, cx, cy, r)
            cr.stroke()
            if frac > 0.005:
                cr.set_source_rgba(*C["neon"], 1)
                cr.new_sub_path()
                cr.arc(cx, cy, r, -math.pi / 2, -math.pi / 2 + 2 * math.pi * frac)
                cr.stroke()
            dibujo.texto(cr, glifo, cx, cy - 8, 12, C["luz"], centro=True)
            dibujo.texto(cr, valor, cx, cy + r + 3, 10, C["luz"], centro=True)
            dibujo.texto(cr, nombre, cx, cy + r + 15, 9, C["tenue"], centro=True)

    return pc.lanzar("calendar-panel", Panel)


def pc_hex(rgb):
    return "#%02x%02x%02x" % tuple(int(round(c * 255)) for c in rgb)


def dibujar_luna(cr, cx, cy, r, iluminada, creciente, C):
    """Un disco de luna con la parte iluminada que toca. La sombra entre la
    parte con luz y la oscura es media elipse de ancho r*(1-2k): con k<0.5
    queda hacia el lado iluminado (una C fina), con k>0.5 hacia el otro (una
    gibosa)."""
    cr.set_source_rgba(*C["apagado"], 1)
    cr.new_sub_path()
    cr.arc(cx, cy, r, 0, 2 * math.pi)
    cr.fill()
    if iluminada <= 0.01:
        return
    cr.save()
    cr.translate(cx, cy)
    if not creciente:
        cr.scale(-1, 1)          # menguante: la luz a la izquierda
    cr.new_path()
    cr.arc(0, 0, r, -math.pi / 2, math.pi / 2)          # la mitad con luz (derecha)
    e = 1 - 2 * iluminada
    if abs(e) < 0.01:
        cr.line_to(0, -r)
    else:
        cr.save()
        cr.scale(e, 1)
        cr.arc_negative(0, 0, r, math.pi / 2, -math.pi / 2)
        cr.restore()
    cr.close_path()
    cr.restore()
    cr.set_source_rgba(*C["luz"], 1)
    cr.fill()


def main(argv):
    if argv == ["--ver"]:
        return ver()
    if argv:
        print(__doc__.strip().split("\n\n")[-1], file=sys.stderr)
        return 2
    return abrir_panel()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
