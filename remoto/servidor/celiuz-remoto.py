#!/usr/bin/env python3
"""
remoto/servidor/celiuz-remoto.py — el servicio de Celiuz Remoto.

    celiuz-remoto.py revisar            que le falta a este equipo para el remoto
    celiuz-remoto.py paquetes           TODOS los paquetes de Arch que usa (los lee instalar.sh --remoto-todo)
    celiuz-remoto.py rutas              donde guarda cada cosa (fuera del repo)
    celiuz-remoto.py servir             el servicio (escucha solo por Tailscale)
    celiuz-remoto.py estado             que dice el servicio que esta corriendo
    celiuz-remoto.py dispositivos       los telefonos emparejados
    celiuz-remoto.py celulares          los que hay conectados por cable (adb)
    celiuz-remoto.py emparejar          empareja el celular del cable (--celular SERIE)
    celiuz-remoto.py renovar            abre el canal USB para renovar un pase
    celiuz-remoto.py revocar <id>       quita un telefono (no vuelve a entrar)
    celiuz-remoto.py desbloquear <id>   tras 5 contraseñas mal
    celiuz-remoto.py quitar-pase <id>   le quita el pase (sigue emparejado)
    celiuz-remoto.py permisos <id> +terminal -archivos
    celiuz-remoto.py registro [-n N]    lo ultimo que paso
    celiuz-remoto.py cancelar           cancela un apagado/reinicio/suspension en marcha
    celiuz-remoto.py vigilancia [si|no] arma o desarma la vigilancia, o dice como esta
    celiuz-remoto.py presencia [ausente|presente]   lo apunta hypridle; sin nada, lo dice
    celiuz-remoto.py barra              el icono de waybar (JSON; vacio con el servicio apagado)
    celiuz-remoto.py inicio             ¿sesion abierta o pantalla de inicio? ¿se puede entrar?
    celiuz-remoto.py entrar             con la PC en SDDM: entra y la sesion arranca bloqueada
    celiuz-remoto.py al-entrar          lo pregunta lua/autostart.lua: sale 0 si hay que bloquear
    celiuz-remoto.py despertar [MAC]    sin MAC: la de este equipo y si puede despertarse; con MAC: despierta a ese
    celiuz-remoto.py invitar [--horas 2] [--permisos estado,ventanas,pantalla] [--cancelar]
                                        ayudar a un amigo: una invitación sin cable, de un solo uso
    celiuz-remoto.py anclaje [--vigilar]  el internet del celular por USB: que vuelva al reiniciar

Un <id> vale entero, por su principio o por el nombre del telefono. El diseño,
en remoto/DISEÑO.md; lo que se dicen la app y el servidor, en PROTOCOLO.md.
"""

import argparse
import importlib.util
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import celiuz_remoto  # noqa: E402,F401  (pone hypr/scripts/lib en el path)
from celiuz_remoto import rutas  # noqa: E402

# (que, como se mira, para que, paquete de Arch). Solo se mira si EXISTE: nada
# de esto arranca, conecta ni toca la red.
NECESIDADES = [
    ("tailscale", "programa", "la red entre el celular y la PC", "tailscale"),
    ("aiohttp", "modulo", "el servidor (HTTP y WebSocket)", "python-aiohttp"),
    ("psutil", "modulo", "CPU, RAM, disco y red", "python-psutil"),
    ("cryptography", "modulo", "comprobar la firma de cada celular", "python-cryptography"),
    ("adb", "programa", "instalar la app y emparejar por cable", "android-tools"),
]
# Lo que no hace falta para lo basico: sin esto, solo se pierde esa parte (y se
# dice), pero no es un aviso.
OPCIONALES = [
    ("ffmpeg", "programa", "las miniaturas de fotos y vídeos en el explorador", "ffmpeg"),
    ("wayvnc", "programa", "ver y manejar la pantalla desde el celular", "wayvnc"),
]
# Lo que pide remoto/app/compilar.sh para hacer la app del celular en esta PC.
# El SDK de Android no esta: no es un paquete de los repos (Android Studio).
PARA_COMPILAR = ["jdk17-openjdk", "nodejs", "npm"]

# El comando que lo deja todo de una vez (instalar.sh). Lo dicen la CLI y la
# ventana cuando falta algo, para no ir de paquete en paquete.
INSTALAR_TODO = "./instalar.sh --remoto-todo"


def paquetes():
    """Todo lo de Arch que usa el remoto, sin repetir y en orden."""
    todos = [p for *_, p in NECESIDADES + OPCIONALES] + PARA_COMPILAR
    return list(dict.fromkeys(todos))


def tailscale():
    """¿Esta conectado Tailscale? (`tailscale ip -4`: pregunta al demonio de
    este equipo, no sale a la red). Devuelve (bool, por que)."""
    from celiuz_remoto import red
    try:
        return True, red.ip_tailscale()
    except red.SinRed as e:
        return False, str(e)


def _hay(nombre, clase):
    if clase == "programa":
        return shutil.which(nombre) is not None
    return importlib.util.find_spec(nombre) is not None


def revisar():
    faltan = []
    filas = []
    for nombre, clase, para, paquete in NECESIDADES:
        ok = _hay(nombre, clase)
        filas.append({"que": nombre, "para": para, "paquete": paquete, "hay": ok})
        if not ok:
            faltan.append(paquete)
    return filas, faltan


def revisar_opcionales():
    filas = []
    for nombre, clase, para, paquete in OPCIONALES:
        filas.append({"que": nombre, "para": para, "paquete": paquete, "hay": _hay(nombre, clase)})
    return filas


def arranque():
    """Lo de la fase 5, que no son paquetes: ¿arranca con el equipo? ¿se puede
    entrar desde la pantalla de inicio? (remoto/DISEÑO.md, «Tras reiniciar»)."""
    from celiuz_remoto import despertar, inicio
    estado = inicio.sistema_estado()
    return {"linger": inicio.linger(), "sistema": estado == "ok", "sistema_estado": estado,
            "despertar": despertar.info()}


def cmd_revisar(args):
    filas, faltan = revisar()
    opcionales = revisar_opcionales()
    tras = arranque()
    ts_ok, ts_info = tailscale() if shutil.which("tailscale") else (False, "no está instalado")
    if args.json:
        print(json.dumps({"necesidades": filas, "faltan": faltan, "arranque": tras,
                          "tailscale": {"conectado": ts_ok, "info": ts_info},
                          "instalar_todo": INSTALAR_TODO,
                          "opcionales": opcionales,
                          "opcionales_faltan": [o["paquete"] for o in opcionales if not o["hay"]]},
                         ensure_ascii=False, indent=2))
    else:
        for f in filas:
            marca = "ok   " if f["hay"] else "FALTA"
            print(f"  {marca} {f['que']:<10} {f['para']}")
        print(f"  {'ok   ' if ts_ok else 'NO   '} {'conectado':<10} Tailscale: {ts_info}")
        if faltan or not ts_ok:
            print(f"\n  Para dejarlo todo de una vez (pide sudo): {INSTALAR_TODO}")
        else:
            print("\n  No falta nada.")
        print("\n  Opcionales:")
        for o in opcionales:
            marca = "ok   " if o["hay"] else "no   "
            print(f"  {marca} {o['que']:<10} {o['para']}" + ("" if o["hay"] else f"  (sudo pacman -S {o['paquete']})"))
        print("\n  Tras reiniciar:")
        print("    arranca con el equipo       " + (
            "sí (linger)" if tras["linger"] else "no: se enciende con el servicio, desde la ventana"))
        print("    entrar desde SDDM           " + {
            "ok": "sí",
            "falta": "no: ./instalar.sh --remoto-sistema (pide sudo)",
            "vieja": "la copia de root es VIEJA (trajiste un arreglo): ./instalar.sh --remoto-sistema",
            "sddm_conf": "no: /etc/sddm.conf entraría SIN uwsm: ./instalar.sh --remoto-sistema",
        }[tras["sistema_estado"]])
        w = tras["despertar"]
        print("    despertarlo desde otro      " + {"si": "sí", "no": "no", "no_lo_se": "no lo sé"}[w["wol"]]
              + f" — {w['motivo']}")
    # Que falte algo no es un error de este programa: es la respuesta.
    return 0


def cmd_paquetes(_args):
    print(" ".join(paquetes()))
    return 0


def cmd_rutas(args):
    todas = rutas.todas()
    if args.json:
        print(json.dumps(todas, ensure_ascii=False, indent=2))
    else:
        for clave, ruta in todas.items():
            print(f"  {clave:<13} {ruta}")
    return 0


def _almacen():
    from celiuz_remoto import dispositivos
    return dispositivos.Almacen()


def _buscar(almacen, texto):
    disp = almacen.buscar(texto)
    if disp is None:
        print(f"No encuentro un único teléfono «{texto}» (mira «dispositivos»).",
              file=sys.stderr)
    return disp


def _hora(iso):
    from celiuz_remoto import pase
    m = pase.leer(iso)
    return m.strftime("%d/%m %H:%M") if m else "—"


def cmd_servir(args):
    import asyncio
    from celiuz_remoto import estado, red, servidor
    try:
        ip = red.ip_tailscale()
    except red.SinRed as e:
        # Sale con error para que systemd lo reintente: al arrancar la PC,
        # tailscaled puede tardar en tener IP.
        print(f"celiuz-remoto: no arranco: {e}", file=sys.stderr)
        return 1
    try:
        return asyncio.run(servidor.servir(ip, estado.Muestreador()))
    except OSError as e:
        print(f"celiuz-remoto: no puedo escuchar en {ip}: {e}", file=sys.stderr)
        return 1


def cmd_estado(args):
    from celiuz_remoto import control
    try:
        codigo, d = control.pedir("GET", "/control/estado")
    except control.SinServicio as e:
        print(e, file=sys.stderr)
        return 1
    if codigo != 200:
        print(f"  El servicio contestó {codigo}: {d.get('mensaje')}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        print(f"  escuchando en  {d['red']}")
        print(f"  sesiones       {d['sesiones']}")
        print(f"  canal USB      {d['ventana'] or 'cerrado'}")
    return 0


def cmd_dispositivos(args):
    from celiuz_remoto import pase
    todos = _almacen().todos()
    if args.json:
        # Sin hashes: lo que importa saber, no lo que se puede robar.
        limpio = [{k: v for k, v in d.items() if k not in ("contrasena", "publica")}
                  | {"pase_vigente": pase.vigente(d)} for d in todos]
        print(json.dumps(limpio, ensure_ascii=False, indent=2))
        return 0
    if not todos:
        print("  Ningún teléfono emparejado (celiuz-remoto.py emparejar).")
        return 0
    for d in todos:
        estado_pase = f"pase hasta {_hora(d['pase_hasta'])}" if pase.vigente(d) else "sin pase"
        marca = "  BLOQUEADO" if d.get("bloqueado") else ""
        print(f"  {d['id']}  {d['nombre']:<20} {estado_pase:<24} "
              f"{','.join(d['permisos'])}{marca}")
        print(f"  {'':16}  emparejado {_hora(d['creado'])}, "
              f"última sesión {_hora(d.get('ultima_sesion'))}")
    return 0


def _leer_contrasena():
    import getpass
    if not sys.stdin.isatty():
        # Para la app de la PC y las pruebas: una linea por stdin, nunca por
        # argumento (se veria en /proc/<pid>/cmdline, como la del wifi).
        return sys.stdin.readline().rstrip("\n")
    while True:
        uno = getpass.getpass("  Contraseña de la app para este teléfono: ")
        dos = getpass.getpass("  Otra vez: ")
        if uno == dos:
            return uno
        print("  No coinciden. Otra vez.", file=sys.stderr)


def _sin_adb(cuerpo):
    """Abre la ventana y espera, sin tocar el cable: imprime el codigo para que
    lo use otro (las pruebas, con su celular de mentira)."""
    from celiuz_remoto import control
    try:
        codigo, d = control.pedir("POST", "/control/ventana", cuerpo)
    except control.SinServicio as e:
        print(e, file=sys.stderr)
        return 1
    if codigo != 200:
        print(f"  No se pudo abrir el canal USB: {d.get('mensaje')}", file=sys.stderr)
        return 1
    print(f"CODIGO {d['codigo']}", flush=True)
    print(f"PUERTO {d['puerto']}", flush=True)
    print(f"  Canal USB abierto {d['caduca']} s. Esperando al teléfono...", file=sys.stderr)
    _, fin = control.pedir("GET", f"/control/ventana?espera={d['caduca']}",
                           timeout=d["caduca"] + 15)
    if fin.get("estado") == "hecho":
        print(f"  Hecho: {fin.get('dispositivo')}", file=sys.stderr)
        return 0
    print(f"  No llegó nada ({fin.get('estado')}).", file=sys.stderr)
    return 1


def _ventana(args, cuerpo):
    if args.sin_adb:
        return _sin_adb(cuerpo)
    from celiuz_remoto import adb, cable
    try:
        cel = cable.elegir(adb.celulares(), args.celular)
        if cel["estado"] != "listo":
            raise cable.ErrorCable("ese celular no ha autorizado la depuración USB")
        if not cel.get("app"):
            raise cable.ErrorCable(f"«{cel['nombre']}» no tiene la app de Celiuz Remoto")
        print(f"  Con «{cel['nombre']}» ({cel['serie']}).", file=sys.stderr)
        aviso = lambda texto: print("  " + texto, file=sys.stderr)  # noqa: E731
        if cuerpo["modo"] == "emparejar":
            fin = cable.emparejar(cel["serie"], cuerpo["contrasena"], cuerpo["permisos"],
                                  cuerpo.get("nombre") or cel["nombre"], aviso)
        else:
            fin = cable.renovar(cel["serie"], aviso)
    except (adb.ErrorAdb, cable.ErrorCable) as e:
        print(f"  No se pudo: {e}", file=sys.stderr)
        return 1
    print(f"  Hecho: {fin.get('dispositivo')}", file=sys.stderr)
    return 0


def cmd_celulares(args):
    from celiuz_remoto import adb
    try:
        lista = adb.celulares()
    except adb.ErrorAdb as e:
        print(f"  {e}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(lista, ensure_ascii=False, indent=2))
        return 0
    if not lista:
        print("  Ningún celular por cable (y con la «Depuración USB» activada).")
    for c in lista:
        if c["estado"] != "listo":
            print(f"  {c['serie']:<18} {c['nombre']:<18} {c['estado']}")
            continue
        print(f"  {c['serie']:<18} {c['nombre']:<18} Android {c['android'] or '?'} · "
              f"Tailscale {'sí' if c['tailscale'] else 'NO'} · "
              f"app {c['app'] or 'no instalada'}")
    return 0


def cmd_emparejar(args):
    permisos = [p for p in (args.permisos or "").split(",") if p]
    if not args.sin_adb:
        # El celular antes que la contraseña: no hacerla escribir para nada.
        from celiuz_remoto import adb, cable
        try:
            args.celular = cable.elegir(adb.celulares(), args.celular)["serie"]
        except (adb.ErrorAdb, cable.ErrorCable) as e:
            print(f"  No se pudo: {e}", file=sys.stderr)
            return 1
    contrasena = _leer_contrasena()
    return _ventana(args, {"modo": "emparejar", "contrasena": contrasena,
                           "permisos": permisos, "nombre": args.nombre})


def cmd_renovar(args):
    return _ventana(args, {"modo": "renovar"})


def cmd_revocar(args):
    from celiuz_remoto import registro
    almacen = _almacen()
    disp = _buscar(almacen, args.id)
    if disp is None:
        return 1
    almacen.revocar(disp["id"])
    registro.apuntar("revocado", disp["id"], nombre=disp["nombre"])
    print(f"  Revocado «{disp['nombre']}». Si te lo robaron, quítalo también de "
          "https://login.tailscale.com/admin/machines")
    return 0


def cmd_desbloquear(args):
    from celiuz_remoto import registro
    almacen = _almacen()
    disp = _buscar(almacen, args.id)
    if disp is None:
        return 1
    almacen.cambiar(disp["id"], bloqueado=False, fallos=0)
    registro.apuntar("desbloqueado", disp["id"])
    print(f"  «{disp['nombre']}» puede volver a entrar.")
    return 0


def cmd_quitar_pase(args):
    from celiuz_remoto import registro
    almacen = _almacen()
    disp = _buscar(almacen, args.id)
    if disp is None:
        return 1
    almacen.cambiar(disp["id"], pase_hasta=None)
    registro.apuntar("pase_quitado", disp["id"])
    print(f"  «{disp['nombre']}» ya no tiene pase. Se renueva por cable.")
    return 0


def cmd_permisos(args):
    from celiuz_remoto import dispositivos, registro
    almacen = _almacen()
    disp = _buscar(almacen, args.id)
    if disp is None:
        return 1
    permisos = set(disp["permisos"])
    for c in args.cambios:
        signo, nombre = c[:1], c[1:]
        if signo not in "+-" or nombre not in dispositivos.PERMISOS:
            print(f"  «{c}» no vale: +permiso o -permiso, con permiso uno de "
                  f"{', '.join(dispositivos.PERMISOS)}", file=sys.stderr)
            return 2
        (permisos.add if signo == "+" else permisos.discard)(nombre)
    nuevos = [p for p in dispositivos.PERMISOS if p in permisos]
    almacen.cambiar(disp["id"], permisos=nuevos)
    registro.apuntar("permisos", disp["id"], permisos=nuevos)
    print(f"  «{disp['nombre']}»: {', '.join(nuevos) or 'ninguno'}")
    return 0


def cmd_cancelar(args):
    from celiuz_remoto import control
    try:
        codigo, d = control.pedir("DELETE", "/control/energia")
    except control.SinServicio as e:
        print(e, file=sys.stderr)
        return 1
    print("  Cancelado." if d.get("cancelada") else "  No había nada en marcha.")
    return 0


def cmd_vigilancia(args):
    from celiuz_remoto import control
    try:
        if args.armar is None:
            codigo, d = control.pedir("GET", "/control/vigilancia", timeout=20)
        else:
            codigo, d = control.pedir("POST", "/control/vigilancia",
                                      {"armada": args.armar == "si"}, timeout=20)
    except control.SinServicio as e:
        print(e, file=sys.stderr)
        return 1
    if codigo != 200:
        print(f"  El servicio contestó {codigo}: {d.get('mensaje')}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return 0
    print(f"  vigilancia   {'ARMADA' if d['armada'] else 'desarmada'} ({d['estado']})")
    print(f"  delante      {d['presencia']} — {d['presencia_motivo']}")
    for f in d["telefonos"]:
        if f["vigilado"]:
            senal = "en línea" if f["en_linea"] else (
                f"callado {f['callado_s'] // 60} min" if f["callado_s"] is not None else "sin oír aún")
        elif not f["pase"]:
            senal = "no se vigila: sin pase"
        else:
            senal = "no se vigila: aún no ha entrado por Tailscale"
        print(f"  {f['nombre']:<20} {senal}")
    return 0


def cmd_presencia(args):
    from celiuz_remoto import escritorio
    if args.estado:
        escritorio.marcar_presencia(args.estado)
        return 0
    quien, motivo = escritorio.presencia()
    print(f"  {quien} — {motivo}")
    return 0


def barra():
    """{text, tooltip, class} para el modulo custom/remoto de waybar. Barato:
    solo el socket de control (sin red, sin tailscale). Sin servicio, texto
    vacio, y waybar esconde el modulo."""
    from celiuz_remoto import control
    try:
        codigo, d = control.pedir("GET", "/control/estado", timeout=2)
    except (control.SinServicio, OSError):
        return {"text": ""}
    if codigo != 200:
        return {"text": ""}
    e = d.get("energia")
    lineas = [f"Celiuz Remoto: escuchando en {d.get('red')}"]
    if e:
        verbo = {"apagar": "Se apaga", "reiniciar": "Se reinicia", "suspender": "Se suspende"}[e["accion"]]
        lineas.insert(0, f"{verbo} en {e['quedan']} s — clic para cancelar desde la ventana")
        clase = "apagando"
    elif d.get("sesiones"):
        n = d["sesiones"]
        lineas.append(f"{n} celular{'es' if n > 1 else ''} conectado{'s' if n > 1 else ''} ahora")
        clase = "conectado"
    else:
        lineas.append("ningún celular conectado ahora")
        clase = "activo"
    lineas.append(f"vigilancia: {d.get('vigilancia', '?')}")
    return {"text": "\U000f011c", "tooltip": "\n".join(lineas), "class": clase}


def cmd_barra(args):
    print(json.dumps(barra(), ensure_ascii=False), flush=True)
    return 0


def cmd_inicio(args):
    from celiuz_remoto import inicio
    e = inicio.estado(fresco=True)
    if args.json:
        print(json.dumps(e, ensure_ascii=False, indent=2))
    else:
        print(f"  {e['sesion']} — {e['motivo']}")
        print(f"  entrar desde el celular: {'sí' if e['puede_entrar'] else 'no'}")
    return 0


def cmd_entrar(args):
    from celiuz_remoto import inicio, registro
    ok, mensaje = inicio.entrar()
    print(f"  {mensaje}", file=sys.stdout if ok else sys.stderr)
    if ok:
        registro.apuntar("entrar_escritorio", que="cli")
    return 0 if ok else 1


def cmd_al_entrar(args):
    """0 = esta sesion la abrio el celular: bloquear. 1 = no. Barato a proposito
    (corre al arrancar CADA sesion): solo rutas e inicio, sin red."""
    from celiuz_remoto import inicio
    return 0 if inicio.al_entrar() else 1


def cmd_despertar(args):
    from celiuz_remoto import despertar
    if not args.mac:
        i = despertar.info()
        print(f"  tarjeta   {i['tarjeta'] or '—'}")
        print(f"  MAC       {i['mac'] or '—'}")
        print(f"  despertar {i['wol']} — {i['motivo']}")
        if i["wol"] != "si" and i["tarjeta"]:
            print(f"  Para activarlo (una vez, con root): sudo ethtool -s {i['tarjeta']} wol g")
            print("  y en la BIOS: «Wake on LAN» / «Power On By PCI-E». Ver remoto/DISEÑO.md.")
        return 0
    try:
        por = despertar.despertar(args.mac)
    except ValueError as e:
        print(f"  {e}", file=sys.stderr)
        return 2
    print(f"  Paquete mágico enviado a {args.mac} por {', '.join(por) or 'ningún sitio'}.")
    return 0 if por else 1


def cmd_anclaje(args):
    from celiuz_remoto import anclaje
    if args.vigilar:
        return anclaje.vigilar()
    r = anclaje.revisar()
    if not r["recordados"]:
        print("  Ningún celular le ha dado internet por USB a esta PC: no hay nada que vigilar.")
        return 0
    for serie, c in r["recordados"].items():
        print(f"  {c.get('nombre') or serie} ({serie}): se le vuelve a pedir el anclaje ({c.get('funcion')})")
    print(f"  sin sesión abierta  {'sí' if r['permiso_sin_sesion'] else 'no: en la pantalla de inicio adb no puede abrir el USB'}")
    print(f"  arranca con la PC   {'sí (linger)' if r['linger'] else 'no: solo al entrar'}")
    for f in r["falta"]:
        print(f"  Falta: {f}")
    return 0


def cmd_invitar(args):
    from celiuz_remoto import control
    try:
        if args.cancelar:
            control.pedir("DELETE", "/control/invitacion")
            print("  Invitación cancelada.")
            return 0
        cuerpo = {"horas": args.horas}
        if args.permisos:
            cuerpo["permisos"] = [p for p in args.permisos.split(",") if p]
        codigo, d = control.pedir("POST", "/control/invitacion", cuerpo, timeout=20)
    except control.SinServicio as e:
        print(e, file=sys.stderr)
        return 1
    if codigo != 200:
        print(f"  El servicio contestó {codigo}: {d.get('mensaje')}", file=sys.stderr)
        return 1
    print()
    for linea in d["texto"].splitlines():
        print("  " + linea)
    print()
    print("  Mándaselo a quien te va a ayudar. Antes, comparte esta PC con su cuenta")
    print("  de Tailscale (login.tailscale.com -> Machines -> esta PC -> Share).")
    return 0


def cmd_registro(args):
    from celiuz_remoto import registro
    for linea in registro.ultimas(args.n):
        resto = {k: v for k, v in linea.items() if k not in ("cuando", "accion", "dispositivo")}
        print(f"  {linea['cuando']}  {linea['accion']:<18} {linea.get('dispositivo', ''):<16} "
              + " ".join(f"{k}={v}" for k, v in resto.items()))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="celiuz-remoto.py",
        description="El servicio de Celiuz Remoto.")
    sub = p.add_subparsers(dest="orden", required=True)

    s = sub.add_parser("revisar", help="que le falta a este equipo")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_revisar)

    s = sub.add_parser("paquetes", help="todos los paquetes de Arch que usa")
    s.set_defaults(func=cmd_paquetes)

    s = sub.add_parser("rutas", help="donde guarda cada cosa")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_rutas)

    s = sub.add_parser("servir", help="el servicio")
    s.set_defaults(func=cmd_servir)

    s = sub.add_parser("estado", help="lo que dice el servicio")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_estado)

    s = sub.add_parser("dispositivos", help="los telefonos emparejados")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_dispositivos)

    s = sub.add_parser("emparejar", help="abre el canal USB para un telefono nuevo")
    s.add_argument("--nombre")
    s.add_argument("--permisos", help="separados por comas (de fabrica: estado,energia)")
    s.add_argument("--celular", help="la serie de adb, si hay mas de uno enchufado")
    s.add_argument("--sin-adb", action="store_true",
                   help="no tocar el cable: imprime el codigo y espera")
    s.set_defaults(func=cmd_emparejar)

    s = sub.add_parser("renovar", help="abre el canal USB para renovar un pase")
    s.add_argument("--celular")
    s.add_argument("--sin-adb", action="store_true")
    s.set_defaults(func=cmd_renovar)

    s = sub.add_parser("celulares", help="los celulares conectados por cable")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_celulares)

    for orden, func, ayuda in (("revocar", cmd_revocar, "quita un telefono"),
                               ("desbloquear", cmd_desbloquear, "tras 5 contraseñas mal"),
                               ("quitar-pase", cmd_quitar_pase, "le quita el pase")):
        s = sub.add_parser(orden, help=ayuda)
        s.add_argument("id")
        s.set_defaults(func=func)

    s = sub.add_parser("permisos", help="+permiso / -permiso")
    s.add_argument("id")
    s.add_argument("cambios", nargs="+")
    s.set_defaults(func=cmd_permisos)

    s = sub.add_parser("barra", help="el icono de waybar")
    s.set_defaults(func=cmd_barra)

    s = sub.add_parser("cancelar", help="cancela un apagado en marcha")
    s.set_defaults(func=cmd_cancelar)

    s = sub.add_parser("vigilancia", help="arma, desarma o dice como esta")
    s.add_argument("armar", nargs="?", choices=["si", "no"])
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_vigilancia)

    s = sub.add_parser("presencia", help="lo apunta hypridle")
    s.add_argument("estado", nargs="?", choices=["ausente", "presente"])
    s.set_defaults(func=cmd_presencia)

    s = sub.add_parser("inicio", help="¿sesion abierta o pantalla de inicio?")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_inicio)

    s = sub.add_parser("entrar", help="con la PC en SDDM: entra, y la sesion arranca bloqueada")
    s.set_defaults(func=cmd_entrar)

    s = sub.add_parser("al-entrar", help="lo pregunta el arranque de la sesion")
    s.set_defaults(func=cmd_al_entrar)

    s = sub.add_parser("despertar", help="Wake-on-LAN: lo de este equipo, o despertar a otro")
    s.add_argument("mac", nargs="?")
    s.set_defaults(func=cmd_despertar)

    s = sub.add_parser("invitar", help="ayudar a un amigo: invitacion sin cable")
    s.add_argument("--horas", type=int, default=2, choices=[1, 2, 4, 8])
    s.add_argument("--permisos")
    s.add_argument("--cancelar", action="store_true")
    s.set_defaults(func=cmd_invitar)

    s = sub.add_parser("anclaje", help="que vuelva el internet del celular por USB al reiniciar")
    s.add_argument("--vigilar", action="store_true", help="el demonio (lo arranca su unidad)")
    s.set_defaults(func=cmd_anclaje)

    s = sub.add_parser("registro", help="lo ultimo que paso")
    s.add_argument("-n", type=int, default=30)
    s.set_defaults(func=cmd_registro)

    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) >= 3 and argv[0] == "permisos" and argv[2] != "--":
        # «permisos X -estado»: sin esto argparse toma -estado por una opcion.
        argv.insert(2, "--")
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
