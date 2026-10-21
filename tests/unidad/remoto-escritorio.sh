#!/usr/bin/env bash
# tests/unidad/remoto-escritorio.sh — la parte de la PC de Celiuz Remoto que no
# es el servidor: la app de la PC (sus textos y su CSS, sin pantalla), como se
# lee adb, y como se instala (la unidad de systemd que viene APAGADA).
#
# POR QUE: la ventana se mira en un anidado (el aspecto no se prueba aqui),
# pero lo que dice —«vence mañana a las 09:48», «hace 2 h 05 min»— y lo que
# decide —si un celular esta autorizado, como se llama— son cuentas, y las
# cuentas se prueban. Los nombres de adb salen de los dos celulares reales del
# 2026-10-20: un HONOR que contesta «[ ]» como nombre, y un Redmi.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
ESC="$REPO/remoto/escritorio"
SERV="$REPO/remoto/servidor"

titulo "1. Textos, adb y CSS, pieza a pieza"
python3 - "$ESC" "$SERV" "$REPO/hypr/scripts/lib" > "$TMP/piezas.txt" 2>"$TMP/piezas.err" <<'FINPY'
import datetime as dt, re, sys
sys.path[:0] = sys.argv[1:4]
import textos, estilo
from celiuz_remoto import adb

def comprobar(desc, cond):
    print(("ok|" if cond else "fallo|") + desc)

zona = dt.timezone(dt.timedelta(hours=-5))
ahora = dt.datetime(2026, 10, 20, 22, 0, 0, tzinfo=zona)
hace = lambda **k: ahora - dt.timedelta(**k)
comprobar("hace 12 s", textos.hace(hace(seconds=12), ahora) == "hace 12 s")
comprobar("hace 5 min", textos.hace(hace(minutes=5, seconds=30), ahora) == "hace 5 min")
comprobar("hace 2 h 05 min", textos.hace(hace(hours=2, minutes=5), ahora) == "hace 2 h 05 min")
comprobar("de hace dias, la fecha", textos.hace(hace(days=3), ahora) == "el 17/10")
comprobar("un reloj adelantado no da tiempos negativos", textos.hace(ahora + dt.timedelta(seconds=30), ahora) == "hace 0 s")

texto, queda = textos.pase({"pase_hasta": (ahora + dt.timedelta(hours=12)).isoformat()}, ahora)
comprobar("pase que vence mañana: «vence mañana a las 10:00»", texto == "Pase: vence mañana a las 10:00")
comprobar("   y la barra marca la mitad", abs(queda - 0.5) < 0.001)
texto, queda = textos.pase({"pase_hasta": hace(minutes=1).isoformat()}, ahora)
comprobar("pase vencido: lo dice y sin barra", texto.startswith("Pase vencido hoy") and queda is None)
texto, queda = textos.pase({"pase_hasta": None}, ahora)
comprobar("sin pase: dice como se saca", "por cable" in texto and queda is None)

comprobar("las casillas dan los permisos del protocolo",
          textos.permisos_de([0, 2]) == ["estado", "energia", "archivos"])
comprobar("de fabrica, la terminal NO viene marcada",
          [c[2] for c in textos.CASILLAS] == [True, True, True, False])
comprobar("el resumen solo nombra casillas enteras",
          textos.resumen_permisos(["estado"]) == "ningún permiso")
comprobar("contraseña corta", textos.contrasena_valida("abc", "abc") is not None)
comprobar("contraseñas distintas", "no coinciden" in textos.contrasena_valida("abcd", "abce"))
comprobar("contraseña buena", textos.contrasena_valida("abcd", "abcd") is None)

hora, linea = textos.linea_registro({"cuando": hace(minutes=3).isoformat(), "accion": "entrar_mal",
                                     "dispositivo": "abc123", "motivo": "contrasena"},
                                    {"abc123": "HONOR X7b"}, ahora)
comprobar("el registro en castellano, con el nombre del telefono",
          hora == "21:57:00" and linea == "Intento de entrada fallido · HONOR X7b (contraseña incorrecta)")
hora, _ = textos.linea_registro({"cuando": hace(days=2).isoformat(), "accion": "entrar"}, {}, ahora)
comprobar("   de otro dia, con la fecha", hora == "18/10 22:00")
comprobar("   una accion desconocida no revienta",
          textos.linea_registro({"accion": "rara"}, {}, ahora) == ("", "rara"))

lista = adb.leer_lista("""* daemon started successfully
List of devices attached
A8RD9X4406G02366       unauthorized usb:3-2 transport_id:1
GMAUAITONBEAPVTW       device usb:1-1 product:maltose_global model:M2101K7BL device:maltose transport_id:2
0123456789ABCDEF       no permissions (missing udev rules?); see [http://...] usb:1-2
""")
comprobar("adb: tres celulares, cada uno con su estado",
          [(c["serie"], c["estado"]) for c in lista] ==
          [("A8RD9X4406G02366", "sin_autorizar"), ("GMAUAITONBEAPVTW", "listo"),
           ("0123456789ABCDEF", "sin_permisos")])
comprobar("adb: el modelo sin guiones bajos", lista[1]["modelo"] == "M2101K7BL")
honor = adb.leer_sonda("nombre=[ ]\ncomercial=\nhonor=HONOR X7b\nmarca=HONOR\nmodelo=CLK-LX3\n"
                       "android=14\ntailscale=package:/data/app/x/base.apk\napp=\n")
comprobar("HONOR: «[ ]» no es un nombre, se usa el comercial", honor["nombre"] == "HONOR X7b")
comprobar("   con Tailscale y sin la app", honor["tailscale"] and honor["app"] is None)
redmi = adb.leer_sonda("nombre=Redmi Note 10S\ncomercial=Redmi Note 10S\nhonor=\nandroid=13\n"
                       "tailscale=\napp=    versionName=0.1.0\n")
comprobar("Redmi: su nombre, sin Tailscale, con la app 0.1.0",
          redmi == {"nombre": "Redmi Note 10S", "android": "13", "tailscale": False, "app": "0.1.0"})
comprobar("sin ningun nombre: marca + modelo",
          adb.leer_sonda("nombre=null\nmarca=samsung\nmodelo=SM-A546B\n")["nombre"] == "Samsung SM-A546B")
try:
    adb.abrir_app("X", "emparejar", "codigo; rm -rf /", 47111)
    comprobar("un codigo con caracteres raros no llega al shell del celular", False)
except adb.ErrorAdb:
    comprobar("un codigo con caracteres raros no llega al shell del celular", True)

# El CSS: entero de la paleta que se le da. Con una paleta de mentira, cada
# color que salga tiene que ser uno de ella (o la sombra negra).
C = {k: (i / 20, 0.5, 1 - i / 20) for i, k in enumerate(
    ["abismo", "superficie", "apagado", "violeta", "amatista", "neon", "luz", "tenue",
     "atencion", "alerta"])}
verde = (0.1, 0.9, 0.2)
css = estilo.css(C, "Fuente", verde)
dados = {estilo._hex(c) for c in list(C.values()) + [verde]}
hexes = set(re.findall(r"#[0-9a-f]{6}", css))
comprobar("el CSS no lleva ni un color que no sea de la paleta", hexes <= dados)
rgbs = {tuple(map(int, m)) for m in re.findall(r"rgba\((\d+), (\d+), (\d+),", css)}
dados_rgb = {tuple(int(round(x * 255)) for x in c) for c in list(C.values()) + [verde]}
comprobar("   ni en sus transparencias", rgbs <= dados_rgb)
FINPY
while IFS='|' read -r res desc; do
    case "$res" in
        ok) ok "$desc" ;;
        fallo) fallo "$desc" ;;
        *) fallo "salida inesperada" "$res $desc" ;;
    esac
done < "$TMP/piezas.txt"
afirmar "   las piezas dijeron algo" test "$(grep -c '^ok|' "$TMP/piezas.txt")" -ge 25
afirmar "   sin nada por stderr" test ! -s "$TMP/piezas.err"

titulo "2. Viene apagado"
UNIDAD="$REPO/remoto/servidor/celiuz-remoto.service"
afirmar_contiene "$UNIDAD" '^ExecStart=%h/\.local/bin/celiuz-remoto servir$' \
    "la unidad arranca por el enlace de ~/.local/bin (vale se clone donde se clone)"
afirmar_contiene "$UNIDAD" '^Restart=on-failure$' "   y se reintenta si Tailscale aun no tiene IP"
# «is-enabled» solo mira: lo que no puede aparecer es un enable o un start
afirmar_no_contiene "$REPO/instalar.sh" 'systemctl --user (enable|start|restart) .*celiuz-remoto' \
    "instalar.sh NO la enciende (se enciende a mano desde la app de la PC)"
# Enlazada, `systemctl --user disable` (el boton de apagar) BORRA el enlace y ya
# no se puede volver a encender: tiene que ir copiada (medido el 2026-10-20).
afirmar_no_contiene "$REPO/instalar.sh" 'enlazar .*celiuz-remoto\.service' \
    "la unidad se COPIA, no se enlaza (el disable borraría el enlace)"
afirmar_contiene "$REPO/instalar.sh" 'install -m 0644 .*celiuz-remoto\.service' "   con install -m 0644"
afirmar_contiene "$ESC/celiuz-remoto.desktop" '^Exec=celiuz-remoto-config$' \
    "el .desktop la lanza por el PATH, sin rutas absolutas"
afirmar_contiene "$ESC/celiuz-remoto.desktop" '^StartupWMClass=celiuz-remoto$' \
    "   y su clase es la que pone la app (GLib.set_prgname)"
afirmar_contiene "$ESC/celiuz-remoto-config.py" 'GLib.set_prgname\("celiuz-remoto"\)' \
    "   (la misma que casa con la regla de lua/windowrules.lua)"
afirmar_contiene "$REPO/hypr/lua/windowrules.lua" 'class = "\^\(celiuz-remoto\)\$"' \
    "   que la deja flotante"
afirmar_igual "<svg" "$(head -c 4 "$ESC/celiuz-remoto.svg")" "el icono empieza por <svg (gdk-pixbuf no lee uno que empiece por comentario)"

titulo "3. Sin Wayland no se dibuja en ningun sitio"
DISPLAY=:0 "$ESC/celiuz-remoto-config.py" > "$TMP/sin-wayland" 2>&1; codigo=$?
afirmar_igual "1" "$codigo" "sin WAYLAND_DISPLAY sale con 1 (aunque haya DISPLAY: no cae a XWayland)"
afirmar_contiene "$TMP/sin-wayland" "hace falta una sesión Wayland" "   y dice por qué"

afirmar_intacta_la_casa_real
resumen
