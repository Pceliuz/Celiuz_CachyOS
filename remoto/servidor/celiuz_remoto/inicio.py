"""
remoto/servidor/celiuz_remoto/inicio.py — tras un reinicio: la PC en la pantalla de inicio (SDDM).

Fase 5 (remoto/DISEÑO.md, «Tras reiniciar»). Tres piezas, y solo la tercera
pide root:

1. ARRANCAR SIN SESION. El servicio sigue siendo de `systemd --user`, pero con
   *linger* (`loginctl enable-linger`): el systemd del usuario arranca con el
   equipo y no espera a que alguien entre. Lo enciende la ventana de la PC junto
   con el servicio, y no pide contraseña (polkit deja a cada uno cambiar el
   suyo). El diseño decia «servicio de sistema que corre como el usuario»: es
   esto mismo, sin que lo que escucha por la red tenga que nacer de root.

2. SABER DONDE ESTA LA PC: estado() dice «abierta» (hay un Hyprland vivo),
   «pantalla_inicio» (SDDM esperando y nadie dentro) o «no_lo_se». Lo pregunta
   a logind en caliente, nunca lo recuerda.

3. ENTRAR: entrar() deja la marca de «arranca bloqueada» y pide a systemd la
   unidad de sistema celiuz-remoto-entrar@<usuario>.service, que es la que
   escribe el autologin de un solo uso (remoto/sistema/entrar.py, con la regla
   de polkit que solo deja arrancar ESA). La contraseña de Linux nunca viaja: la
   sesion arranca y lua/autostart.lua la bloquea al ver la marca (al_entrar()).

Lo de root lo instala aparte `./instalar.sh --remoto-sistema`, como el tema de
SDDM: sin eso, todo lo demas funciona y la app dice que falta.
"""

import json
import os
import pwd
import subprocess
import time

from . import escritorio, rutas

UNIDAD = "celiuz-remoto-entrar@{}.service"
MARCA_VALE = 180     # segundos: una marca mas vieja no bloquea (la entrada fallo)
_CACHE_S = 3.0
_cache = (0.0, None)


def usuario():
    return pwd.getpwuid(os.getuid()).pw_name


def _raiz():
    # Solo para las pruebas: donde mirar /etc, /usr/local y /var/lib.
    return os.environ.get("CELIUZ_REMOTO_RAIZ_SISTEMA", "/")


def sistema_instalado():
    """¿Paso alguien `./instalar.sh --remoto-sistema`? Se mira la unidad y el
    programa; la regla de polkit no se puede leer sin root (rules.d es 700)."""
    r = _raiz()
    return (os.path.isfile(os.path.join(r, "etc/systemd/system/celiuz-remoto-entrar@.service"))
            and os.access(os.path.join(r, "usr/local/lib/celiuz-remoto/entrar"), os.X_OK))


def linger():
    """¿Arranca el systemd del usuario con el equipo? logind lo apunta asi."""
    return os.path.exists(os.path.join(_raiz(), "var/lib/systemd/linger", usuario()))


def _sesiones():
    try:
        r = subprocess.run(["loginctl", "list-sessions", "-j"], capture_output=True,
                           text=True, timeout=5, check=False, stdin=subprocess.DEVNULL)
        datos = json.loads(r.stdout) if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    return datos if isinstance(datos, list) else None


def _calcular():
    if escritorio.instancia():
        return {"sesion": "abierta", "puede_entrar": False, "motivo": "la sesión está abierta"}
    lista = _sesiones()
    if lista is None:
        return {"sesion": "no_lo_se", "puede_entrar": False,
                "motivo": "no pude preguntarle a logind"}
    # Las mismas dos reglas que remoto/sistema/entrar.py (que vuelve a mirarlas
    # como root: no se fia de esto).
    personas = [s for s in lista
                if str(s.get("class", "")).startswith("user") and s.get("seat") == "seat0"]
    greeter = any(s.get("class") == "greeter" and s.get("seat") == "seat0" for s in lista)
    if personas:
        return {"sesion": "no_lo_se", "puede_entrar": False,
                "motivo": "hay una sesión abierta que no es de Hyprland"}
    if not greeter:
        return {"sesion": "no_lo_se", "puede_entrar": False,
                "motivo": "no hay sesión ni pantalla de inicio (¿una consola?)"}
    if not sistema_instalado():
        return {"sesion": "pantalla_inicio", "puede_entrar": False,
                "motivo": "falta pasar en la PC: ./instalar.sh --remoto-sistema"}
    return {"sesion": "pantalla_inicio", "puede_entrar": True,
            "motivo": "en la pantalla de inicio de sesión"}


def estado(fresco=False):
    """{sesion, puede_entrar, motivo}. Con unos segundos de cache: lo pide cada
    /v0/vivo cada segundo, y con la PC en SDDM cada vez seria un loginctl."""
    global _cache
    ahora = time.monotonic()
    hora, valor = _cache
    if fresco or valor is None or ahora - hora > _CACHE_S:
        valor = _calcular()
        _cache = (ahora, valor)
    return dict(valor)


def entrar():
    """(ok, mensaje). Comprueba otra vez que toca (el estado cacheado puede
    tener 3 s) y pide la unidad sin esperarla: tarda lo que tarde SDDM."""
    e = estado(fresco=True)
    if not e["puede_entrar"]:
        return False, e["motivo"]
    marca = rutas.entrar_bloqueada()
    os.makedirs(os.path.dirname(marca), mode=0o700, exist_ok=True)
    with open(marca, "w", encoding="utf-8") as fh:
        fh.write(str(time.time()))
    try:
        r = subprocess.run(["systemctl", "start", "--no-block", UNIDAD.format(usuario())],
                           capture_output=True, text=True, timeout=20, check=False,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as ex:
        _quitar_marca()
        return False, f"systemctl no pudo: {ex}"
    if r.returncode != 0:
        _quitar_marca()
        ultima = (r.stderr.strip().splitlines() or ["?"])[-1]
        if "auth" in ultima.lower() or "access denied" in ultima.lower():
            return False, ("polkit no me deja: vuelve a pasar en la PC "
                           "./instalar.sh --remoto-sistema")
        return False, f"systemctl no pudo: {ultima}"
    return True, "Entrando: la sesión arranca bloqueada."


def _quitar_marca():
    try:
        os.unlink(rutas.entrar_bloqueada())
    except FileNotFoundError:
        pass


def al_entrar(ahora=None):
    """Lo pregunta lua/autostart.lua al arrancar la sesion: True si esta
    sesion la abrio el celular (y entonces hay que bloquearla YA). La marca se
    gasta al mirarla, y una vieja no cuenta: si la entrada fallo, la siguiente
    vez que entres a mano no te la bloquea."""
    marca = rutas.entrar_bloqueada()
    try:
        edad = (ahora or time.time()) - os.stat(marca).st_mtime
    except OSError:
        return False
    _quitar_marca()
    return 0 <= edad <= MARCA_VALE


def _marca_linger():
    # Para no quitarle a nadie un linger que ya tuviera por otra cosa: solo se
    # apaga el que encendimos nosotros.
    return os.path.join(rutas.estado(), "linger-nuestro")


def poner_linger(encender):
    """(ok, mensaje). Lo llama la ventana al encender y apagar el servicio. Sin
    contraseña: polkit deja a cada uno cambiar SU linger (set-self-linger)."""
    if encender == linger():
        return True, ""
    if not encender and not os.path.exists(_marca_linger()):
        return True, ""    # lo tenia de antes: no es nuestro
    try:
        r = subprocess.run(["loginctl", "enable-linger" if encender else "disable-linger"],
                           capture_output=True, text=True, timeout=15, check=False,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as ex:
        return False, str(ex)
    if r.returncode != 0:
        return False, (r.stderr.strip().splitlines() or ["?"])[-1]
    if encender:
        os.makedirs(rutas.estado(), mode=0o700, exist_ok=True)
        with open(_marca_linger(), "w", encoding="utf-8") as fh:
            fh.write("encendido por celiuz-remoto-config\n")
    else:
        try:
            os.unlink(_marca_linger())
        except FileNotFoundError:
            pass
    return True, ""
