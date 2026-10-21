"""
remoto/servidor/celiuz_remoto/adb.py — hablar con el celular por el cable.

- Ver que celulares hay enchufados (`adb devices -l`) y, de cada uno, lo que
  necesita la app de la PC para guiar: si autorizo la depuracion USB, su
  nombre, su Android, si tiene Tailscale y si tiene ya nuestra app.
- Abrir el canal USB (`adb reverse tcp:47111 tcp:47111`) y cerrarlo al acabar.
- Pasarle el codigo a la app con un intent EXPLICITO (`am start -n`): solo lo
  recibe nuestra app, no cualquiera que diga entender `celiuzremoto://`
  (PROTOCOLO.md, «USB»).
- Instalar el APK.

Todo con un `-s <serie>`: con dos celulares enchufados (pasa: la PC del autor
tenia un HONOR y un Redmi a la vez el 2026-10-20), un adb sin serie se planta
con «more than one device».

EL NOMBRE: no hay una propiedad que lo diga en todos. Se prueba, en orden, el
que puso el usuario en Ajustes (`settings get global device_name`), el
comercial de Xiaomi (`ro.product.marketname`: «Redmi Note 10S») y el de Honor
y Huawei (`ro.config.marketing_name`: «HONOR X7b»); si no, marca + modelo. El
HONOR contesta «[ ]» al primero, y eso no es un nombre.
"""

import re
import shutil
import subprocess

PAQUETE = "com.celiuz.remoto"
ACTIVIDAD = PAQUETE + "/.MainActivity"
TAILSCALE = "com.tailscale.ipn"
ESQUEMA = "celiuzremoto"
TIEMPO = 15

ESTADOS = {
    "device": "listo",
    "unauthorized": "sin_autorizar",   # falta tocar «Permitir» en el celular
    "offline": "desconectado",
    "no permissions": "sin_permisos",  # reglas udev: el usuario no puede abrir el USB
}


class ErrorAdb(Exception):
    pass


def hay_adb():
    return shutil.which("adb") is not None


def _adb(*args, serie=None, timeout=TIEMPO, entrada=None):
    orden = ["adb"] + (["-s", serie] if serie else []) + list(args)
    try:
        # stdin cerrada si no hay entrada: `adb shell` se come la de quien lo
        # llama, y se tragaba la contraseña que la CLI leia despues por stdin
        # (medido emparejando el HONOR, 2026-10-20).
        r = subprocess.run(orden, capture_output=True, text=True, timeout=timeout,
                           input=entrada, stdin=None if entrada is not None else subprocess.DEVNULL,
                           check=False)
    except FileNotFoundError:
        raise ErrorAdb("no está instalado adb (sudo pacman -S android-tools)") from None
    except subprocess.TimeoutExpired:
        raise ErrorAdb("el celular no contesta por el cable") from None
    return r


def _ok(r, que):
    if r.returncode != 0:
        detalle = (r.stderr or r.stdout).strip().splitlines()
        raise ErrorAdb(f"{que}: {detalle[-1] if detalle else 'adb falló'}")
    return r.stdout


def leer_lista(texto):
    """La salida de `adb devices -l` -> [{serie, estado, modelo}]."""
    salida = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith(("List of devices", "*")):
            continue
        m = re.match(r"(\S+)\s+(no permissions|\S+)(.*)$", linea)
        if not m:
            continue
        serie, estado, resto = m.groups()
        campos = dict(re.findall(r"(\w+):(\S+)", resto))
        salida.append({"serie": serie, "estado": ESTADOS.get(estado, estado),
                       "modelo": campos.get("model", "").replace("_", " ")})
    return salida


_SONDA = ("echo \"nombre=$(settings get global device_name)\"; "
          "echo \"comercial=$(getprop ro.product.marketname)\"; "
          "echo \"honor=$(getprop ro.config.marketing_name)\"; "
          "echo \"marca=$(getprop ro.product.brand)\"; "
          "echo \"modelo=$(getprop ro.product.model)\"; "
          "echo \"android=$(getprop ro.build.version.release)\"; "
          f"echo \"tailscale=$(pm path {TAILSCALE})\"; "
          f"echo \"app=$(dumpsys package {PAQUETE} | grep -m1 versionName)\"")


def _nombre(p):
    for clave in ("nombre", "comercial", "honor"):
        v = p.get(clave, "").strip().strip("[]").strip()
        if v and v != "null":
            return v
    marca, modelo = p.get("marca", "").strip(), p.get("modelo", "").strip()
    if modelo.lower().startswith(marca.lower()):
        return modelo or "Celular"
    return f"{marca.capitalize()} {modelo}".strip() or "Celular"


def leer_sonda(texto):
    p = dict(linea.split("=", 1) for linea in texto.splitlines() if "=" in linea)
    version = re.search(r"versionName=(\S+)", p.get("app", ""))
    return {
        "nombre": _nombre(p),
        "android": p.get("android", "").strip() or None,
        "tailscale": p.get("tailscale", "").strip().startswith("package:"),
        "app": version.group(1) if version else None,
    }


def celulares():
    """Los celulares enchufados, con lo que se sabe de cada uno. Los que no
    estan listos (sin autorizar, sin permisos) salen igual: la app de la PC
    tiene que poder decir que hacer con ellos."""
    lista = leer_lista(_ok(_adb("devices", "-l"), "no puedo listar los celulares"))
    for c in lista:
        c.update({"nombre": c["modelo"] or c["serie"], "android": None,
                  "tailscale": None, "app": None})
        if c["estado"] != "listo":
            continue
        r = _adb("shell", _SONDA, serie=c["serie"])
        if r.returncode == 0:
            c.update(leer_sonda(r.stdout))
    return lista


def abrir_canal(serie, puerto):
    """adb reverse: el 127.0.0.1:<puerto> del celular llega al de la PC."""
    _ok(_adb("reverse", f"tcp:{puerto}", f"tcp:{puerto}", serie=serie),
        "no pude abrir el canal USB")


def cerrar_canal(serie, puerto):
    # De mejor esfuerzo: si el cable ya se quito, no hay nada que cerrar.
    try:
        _adb("reverse", "--remove", f"tcp:{puerto}", serie=serie)
    except ErrorAdb:
        pass


def abrir_app(serie, modo, codigo, puerto):
    """Abre nuestra app con el codigo y el puerto USB (que en la PC se puede
    cambiar en remoto.conf), por intent explicito. El codigo es
    base64url (letras, numeros, - y _): no hace falta escaparlo para el shell
    del celular, y se comprueba por si acaso."""
    if modo not in ("emparejar", "renovar") or not re.fullmatch(r"[A-Za-z0-9_-]+", codigo) \
            or not 1024 <= int(puerto) <= 65535:
        raise ErrorAdb("código o modo no válidos")
    r = _adb("shell", "am", "start", "-n", ACTIVIDAD, "-a", "android.intent.action.VIEW",
             "-d", f"{ESQUEMA}://{modo}/{codigo}?p={int(puerto)}", serie=serie)
    salida = _ok(r, "no pude abrir la app en el celular")
    if "Error" in salida:
        raise ErrorAdb("no pude abrir la app en el celular: "
                       + salida.strip().splitlines()[-1])


def instalar(serie, apk):
    """-r: actualiza conservando los datos (la clave del celular vive ahi)."""
    _ok(_adb("install", "-r", apk, serie=serie, timeout=180), "no pude instalar la app")
