#!/usr/bin/env python3
"""
hypr/scripts/lib/apps_catalogo.py — lo que HACE el catalogo de apps, sin GTK.

La ventana es catalogo-apps.py; esto es lo que hay debajo, para que las pruebas
lo ejerzan sin pantalla. No confundir con `catalogo.py` (los JUEGOS del modo
gaming). El porque de todo, en CATALOGO.md; el formato de la ficha, en
fichas.py.

    apps_catalogo.py estado [--json] [--red]   como esta cada app (--red: baja
                                               las fichas y mira si hay version nueva)
    apps_catalogo.py instalar ID [--sin-sistema]
    apps_catalogo.py actualizar ID
    apps_catalogo.py quitar ID [--sin-sistema]

QUE ES CADA COSA
----------------
- Una app de FUERA sin instalar se ensena con su ficha, su icono y sus
  capturas bajados de GitHub (`raw.githubusercontent.com`, solo esos ficheros,
  no el repo) a `~/.cache/celiuz/catalogo/<id>/`. Al instalarla se CLONA en
  `~/.local/share/celiuz/apps/<id>` y se lanzan sus ordenes desde ahi.
- Una de DENTRO ya esta en los dotfiles: elegirla es lanzar sus ordenes.
- Instalada = anunciada (`apps.d/<id>`, fichas.instaladas): lo deja su propio
  instalador, asi que vale igual si se clono a mano en otra carpeta.

LA CONTRASEÑA
-------------
Las ordenes `sistema` y `sistema_quitar` piden root, y el catalogo no tiene
terminal. Se lanzan con un `sudo` propio delante en el PATH que llama al de
verdad con `-A` y la tarjeta del repo (pedir-clave.py) como askpass. Asi el
instalador de cada app no tiene que saber nada del catalogo: escribe `sudo`
como siempre. Sin terminal, sudo recuerda la contraseña por PROCESO PADRE: con
el `exec` del envoltorio, el padre de cada sudo es el instalador, y la tarjeta
sale una vez por orden (lo vigila tests/unidad/catalogo-apps.sh).

LA UNICA PUERTA A INTERNET
--------------------------
`bajar()`. Todo lo que sale a la red desde aqui pasa por ella (y `git`, que
clona y mira si hay version nueva). Para las pruebas, CELIUZ_CATALOGO_GITHUB
apunta a una carpeta con `<dueno>/<repo>/` que hace de GitHub: de ahi se leen
las fichas y de ahi se clona.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

AQUI = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, AQUI)
import fichas  # noqa: E402

SCRIPTS = os.path.dirname(AQUI)
PEDIR_CLAVE = os.path.join(SCRIPTS, "pedir-clave.py")
LIMITE = 4 * 1024 * 1024      # por fichero bajado: una ficha o una captura
ESPERA_RED = 10               # segundos por peticion
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
GITHUB = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(\.git)?$")


# --- donde vive cada cosa -----------------------------------------------------

def dir_apps():
    """Donde se clonan las apps de fuera."""
    return os.path.join(fichas.dir_datos(), "apps")


def dir_cache():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "celiuz", "catalogo")


def dueno_repo(repo):
    m = GITHUB.match(repo or "")
    return (m.group(1), m.group(2)) if m else (None, None)


def url_fichero(repo, ruta):
    """La URL de un fichero del repo de una app, sin clonarlo."""
    dueno, nombre = dueno_repo(repo)
    falso = os.environ.get("CELIUZ_CATALOGO_GITHUB")
    if falso:
        return "file://" + urllib.parse.quote(os.path.join(falso, dueno, nombre, ruta))
    return "https://raw.githubusercontent.com/%s/%s/HEAD/%s" % (
        dueno, nombre, urllib.parse.quote(ruta))


def url_clonar(repo):
    falso = os.environ.get("CELIUZ_CATALOGO_GITHUB")
    if falso:
        dueno, nombre = dueno_repo(repo)
        return os.path.join(falso, dueno, nombre)
    return repo


# --- la red -------------------------------------------------------------------

def bajar(url, limite=LIMITE):
    """Los bytes de `url`, o None si no se pudo. La UNICA puerta a internet."""
    try:
        with urllib.request.urlopen(url, timeout=ESPERA_RED) as r:
            datos = r.read(limite + 1)
    except (OSError, ValueError):
        return None
    return None if len(datos) > limite else datos


def _ruta_segura(ruta):
    """Una ruta de la ficha (que llega de la red) que no puede salirse de la
    carpeta donde se guarda."""
    if not isinstance(ruta, str) or not ruta or os.path.isabs(ruta):
        return None
    limpia = os.path.normpath(ruta)
    if limpia.startswith("..") or limpia.startswith("/"):
        return None
    return limpia


def traer_ficha(app):
    """Baja la ficha de una app de fuera, con su icono y sus capturas, a la
    cache. Devuelve (ficha, errores). Si algo falla, la cache vieja se queda."""
    datos = bajar(url_fichero(app["repo"], fichas.FICHERO))
    if datos is None:
        return None, ["no se pudo bajar la ficha (¿sin internet?)"]
    try:
        ficha = json.loads(datos.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        return None, ["la ficha no es JSON: %s" % e]
    if not isinstance(ficha, dict):
        return None, ["la ficha no es un objeto JSON"]
    os.makedirs(dir_cache(), exist_ok=True)
    nueva = tempfile.mkdtemp(prefix=app["id"] + ".", dir=dir_cache())
    try:
        with open(os.path.join(nueva, fichas.FICHERO), "wb") as fh:
            fh.write(datos)
        rutas = [ficha.get("icono")] + list(ficha.get("capturas") or [])
        for ruta in rutas:
            limpia = _ruta_segura(ruta)
            if limpia is None:
                continue                      # errores_de lo dira
            contenido = bajar(url_fichero(app["repo"], limpia))
            if contenido is None:
                continue
            destino = os.path.join(nueva, limpia)
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            with open(destino, "wb") as fh:
                fh.write(contenido)
        errores = fichas.errores_de(ficha, nueva)
        if ficha.get("id") != app["id"]:
            errores.append("la ficha dice ser «%s» y en la lista es «%s»" % (ficha.get("id"), app["id"]))
        if errores:
            shutil.rmtree(nueva, ignore_errors=True)
            return None, errores
        final = os.path.join(dir_cache(), app["id"])
        vieja = final + ".vieja"
        shutil.rmtree(vieja, ignore_errors=True)
        if os.path.isdir(final):
            os.rename(final, vieja)
        os.rename(nueva, final)
        shutil.rmtree(vieja, ignore_errors=True)
        return ficha, []
    except OSError as e:
        shutil.rmtree(nueva, ignore_errors=True)
        return None, ["no se pudo guardar la ficha: %s" % e]


# --- lo que este equipo tiene ---------------------------------------------------

def _sys():
    return os.environ.get("CELIUZ_CATALOGO_SYS", "/sys")


def tiene(necesidad):
    """True / False / None (no se puede saber desde aqui, como un celular)."""
    if necesidad == "bluetooth":
        try:
            return bool(os.listdir(os.path.join(_sys(), "class", "bluetooth")))
        except OSError:
            return False
    if necesidad == "nvidia":
        base = os.path.join(_sys(), "bus", "pci", "devices")
        try:
            for d in os.listdir(base):
                try:
                    with open(os.path.join(base, d, "vendor")) as v, \
                         open(os.path.join(base, d, "class")) as c:
                        if v.read().strip() == "0x10de" and c.read().strip().startswith("0x03"):
                            return True
                except OSError:
                    continue
        except OSError:
            return None
        return False
    if necesidad == "portatil":
        try:
            r = subprocess.run([os.path.join(AQUI, "maquina.py"), "--es-laptop"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return None
        return r.returncode == 0
    return None


# --- el estado de cada app ------------------------------------------------------

def apps(con_red=False):
    """Una entrada por app de la lista, con lo que se sabe sin lanzar ordenes:

    id, origen («fuera»/«dentro»), repo, raiz (la carpeta de su ficha),
    ficha, errores, instalada, nuestra (la clonamos nosotros), necesita
    [(necesidad, True/False/None)].

    Con `con_red`, las de fuera sin instalar bajan su ficha antes; sin red, se
    usa la de la cache (si la hay)."""
    anunciadas = fichas.instaladas()
    salida = []
    for app in fichas.lista():
        e = {"id": app["id"], "repo": app.get("repo"), "origen": "dentro" if app.get("dentro") else "fuera",
             "instalada": app["id"] in anunciadas, "ficha": None, "errores": [], "raiz": None,
             "nuestra": False}
        if e["origen"] == "dentro":
            e["raiz"] = fichas.raiz_dentro(app)
        elif e["instalada"]:
            e["raiz"] = anunciadas[app["id"]]
            e["nuestra"] = os.path.realpath(e["raiz"]) == os.path.realpath(os.path.join(dir_apps(), app["id"]))
        else:
            if con_red:
                _, errores = traer_ficha(app)
                e["errores"] = errores
            cache = os.path.join(dir_cache(), app["id"])
            if os.path.isfile(os.path.join(cache, fichas.FICHERO)):
                e["raiz"] = cache
        if e["raiz"]:
            ficha, errores = fichas.leer(e["raiz"])
            if ficha is not None and not errores:
                e["ficha"] = ficha
            else:
                e["errores"] = e["errores"] + errores
        elif not e["errores"]:
            e["errores"] = ["su ficha aun no se ha bajado"]
        e["necesita"] = [(n, tiene(n)) for n in (e["ficha"] or {}).get("necesita", [])]
        salida.append(e)
    return salida


def buscar(app_id, con_red=False):
    for e in apps(con_red=con_red):
        if e["id"] == app_id:
            return e
    return None


def _orden(e, nombre):
    return ((e.get("ficha") or {}).get("ordenes") or {}).get(nombre)


def pide_sudo(e):
    """La frase de para que pide contraseña, o None."""
    return (e.get("ficha") or {}).get("pide_sudo") if _orden(e, "sistema") else None


def revisar(e):
    """(True/False/None, lineas): si esta lista para usarse, y que le falta.
    None si no se pudo preguntar."""
    orden = _orden(e, "revisar")
    if not orden or not e["instalada"]:
        return None, []
    lineas = []
    codigo = correr(orden, e["raiz"], lineas.append, plazo=60)
    if codigo is None:
        return None, lineas
    return codigo == 0, [l for l in lineas if l.strip()]


def aplica(e):
    """(True/False, motivo): si la app tiene sentido en este equipo. Sin orden
    `aplica`, siempre."""
    orden = _orden(e, "aplica")
    # Desde la cache no: sus rutas son las del repo de la app, que aun no esta.
    if not orden or not (e["origen"] == "dentro" or e["instalada"]):
        return True, ""
    lineas = []
    codigo = correr(orden, e["raiz"], lineas.append, plazo=30)
    motivo = " ".join(l.strip() for l in lineas if l.strip())
    return codigo == 0, motivo


def _git(raiz, *args, plazo=60):
    try:
        r = subprocess.run(["git", "-C", raiz] + list(args), stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                           timeout=plazo, env=_entorno_git())
    except (OSError, subprocess.SubprocessError):
        return None
    return r


def _entorno_git():
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"     # sin terminal, que no se quede esperando usuario
    env["LC_ALL"] = "C"
    return env


def hay_nueva(e):
    """True si su repo tiene commits nuevos en GitHub; None si no se sabe (no
    es de fuera, no es un repo de git, sin red)."""
    if e["origen"] != "fuera" or not e["instalada"] or not e["raiz"]:
        return None
    if _git(e["raiz"], "fetch", "--quiet") is None:
        return None
    local = _git(e["raiz"], "rev-parse", "HEAD")
    arriba = _git(e["raiz"], "rev-parse", "@{u}")
    if not (local and arriba) or local.returncode or arriba.returncode:
        return None
    return local.stdout.strip() != arriba.stdout.strip()


# --- lanzar ordenes ---------------------------------------------------------------

def _envoltorio_sudo(dentro):
    """Una carpeta con un `sudo` que llama al de verdad con -A. None si no hay sudo."""
    real = shutil.which("sudo")
    if not real:
        return None
    ruta = os.path.join(dentro, "sudo")
    with open(ruta, "w") as fh:
        fh.write('#!/bin/sh\nexec "%s" -A "$@"\n' % real.replace('"', '\\"'))
    os.chmod(ruta, 0o700)
    return dentro


def correr(orden, raiz, salida, motivo_sudo=None, plazo=None):
    """Lanza `orden` con bash desde `raiz`, sin terminal, y pasa cada linea de
    lo que imprima (sin colores) a `salida`. Devuelve el codigo, o None si no
    se pudo lanzar o se paso del plazo.

    Con `motivo_sudo`, un sudo pide la contraseña en la tarjeta del repo y la
    tarjeta dice ese motivo."""
    env = dict(os.environ)
    env["CELIUZ_CATALOGO"] = "1"
    temporal = None
    if motivo_sudo:
        temporal = tempfile.mkdtemp(prefix="celiuz-catalogo-",
                                    dir=os.environ.get("XDG_RUNTIME_DIR") or None)
        if _envoltorio_sudo(temporal):
            env["PATH"] = temporal + os.pathsep + env.get("PATH", "")
            env["SUDO_ASKPASS"] = PEDIR_CLAVE
            env["CELIUZ_CLAVE_MOTIVO"] = motivo_sudo
    try:
        try:
            proc = subprocess.Popen(["bash", "-c", orden], cwd=raiz, env=env,
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, errors="replace",
                                    start_new_session=True)
        except OSError as ex:
            salida("no se pudo lanzar «%s»: %s" % (orden, ex))
            return None
        try:
            for linea in proc.stdout:
                salida(ANSI.sub("", linea.rstrip("\n")))
            return proc.wait(timeout=plazo)
        except subprocess.TimeoutExpired:
            proc.kill()
            salida("«%s» tardo demasiado y se paro" % orden)
            return None
    finally:
        if temporal:
            shutil.rmtree(temporal, ignore_errors=True)


def _motivo(e):
    return "Para %s: %s. Se pide una vez." % (e["ficha"]["nombre"], pide_sudo(e))


def clonar(e, salida):
    """Clona una app de fuera en dir_apps(). Devuelve la raiz o None."""
    destino = os.path.join(dir_apps(), e["id"])
    if os.path.isdir(os.path.join(destino, ".git")):
        salida("ya estaba descargada en %s" % destino)
        return destino
    if os.path.exists(destino):
        salida("%s existe y no es un repo de git: no lo piso" % destino)
        return None
    os.makedirs(dir_apps(), exist_ok=True)
    salida("descargando %s ..." % e["repo"])
    try:
        r = subprocess.run(["git", "clone", "--depth", "1", url_clonar(e["repo"]), destino],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True, timeout=600, env=_entorno_git())
    except (OSError, subprocess.SubprocessError) as ex:
        salida("git no pudo descargarla: %s" % ex)
        shutil.rmtree(destino, ignore_errors=True)
        return None
    for l in r.stdout.splitlines():
        salida(l)
    if r.returncode != 0:
        shutil.rmtree(destino, ignore_errors=True)
        return None
    return destino


def instalar(e, salida, con_sistema=True):
    """Descarga (si es de fuera), instala y, si se quiere y la tiene, pone la
    parte del sistema. Devuelve True si todo fue bien."""
    raiz = e["raiz"]
    if e["origen"] == "fuera" and not e["instalada"]:
        raiz = clonar(e, salida)
        if raiz is None:
            return False
    ficha, errores = fichas.leer(raiz)
    if errores:
        for m in errores:
            salida("la ficha descargada esta mal: " + m)
        return False
    if ficha["id"] != e["id"]:
        salida("la app descargada dice ser «%s», no «%s»" % (ficha["id"], e["id"]))
        return False
    e = dict(e, ficha=ficha, raiz=raiz)
    salida("== instalando %s" % ficha["nombre"])
    if correr(ficha["ordenes"]["instalar"], raiz, salida) != 0:
        salida("la instalacion fallo")
        return False
    if con_sistema and _orden(e, "sistema"):
        salida("== la parte del sistema (pide tu contraseña)")
        if correr(ficha["ordenes"]["sistema"], raiz, salida, motivo_sudo=_motivo(e)) != 0:
            salida("la parte del sistema no se pudo poner")
            return False
    return True


def actualizar(e, salida):
    """git pull de una app de fuera y vuelve a pasar su instalador."""
    if e["origen"] != "fuera" or not e["instalada"]:
        salida("solo se actualizan las apps de fuera instaladas")
        return False
    salida("== actualizando %s" % e["ficha"]["nombre"])
    r = _git(e["raiz"], "pull", "--ff-only", plazo=600)
    if r is None or r.returncode != 0:
        for l in ((r.stdout + r.stderr) if r else "git no respondio").splitlines():
            salida(l)
        salida("no se pudo actualizar (¿cambios tuyos en %s?)" % e["raiz"])
        return False
    for l in r.stdout.splitlines():
        salida(l)
    return instalar(dict(e, instalada=True), salida, con_sistema=False)


def quitar(e, salida, con_sistema=True):
    """Quita la parte del sistema (si se quiere), la de usuario y, si la
    clonamos nosotros, la carpeta. Devuelve True si todo fue bien."""
    if not e["instalada"] and e["origen"] == "fuera":
        salida("no esta instalada")
        return False
    raiz = e["raiz"]
    salida("== quitando %s" % e["ficha"]["nombre"])
    if con_sistema and _orden(e, "sistema_quitar"):
        salida("== la parte del sistema (pide tu contraseña)")
        if correr(e["ficha"]["ordenes"]["sistema_quitar"], raiz, salida, motivo_sudo=_motivo(e)) != 0:
            salida("la parte del sistema no se pudo quitar")
            return False
    if correr(e["ficha"]["ordenes"]["quitar"], raiz, salida) != 0:
        salida("no se pudo quitar")
        return False
    anuncio = os.path.join(fichas.dir_anuncios(), e["id"])
    if os.path.islink(anuncio):
        os.unlink(anuncio)                 # por si su instalador se lo dejo
    if e["origen"] == "fuera" and e["nuestra"]:
        shutil.rmtree(raiz, ignore_errors=True)
        salida("borrada la descarga: %s" % raiz)
    return True


# --- lo que se ensena ---------------------------------------------------------------

def estado_texto(e, lista=None, aplica_=True, nueva=None):
    """La palabra de estado de una app, la misma en la ventana y en la CLI."""
    if not e["instalada"]:
        return "no hace falta aquí" if aplica_ is False else "sin instalar"
    if nueva:
        return "hay versión nueva"
    if lista is False:
        return "le falta algo"
    return "instalada"


def _cli(argv):
    if argv[:1] == ["estado"]:
        todas = apps(con_red="--red" in argv)
        filas = []
        for e in todas:
            lista, faltas = revisar(e)
            ap, motivo = aplica(e)
            nueva = hay_nueva(e) if "--red" in argv else None
            filas.append({"id": e["id"], "origen": e["origen"], "instalada": e["instalada"],
                          "lista": lista, "faltas": faltas, "aplica": ap, "motivo": motivo,
                          "nueva": nueva, "errores": e["errores"], "raiz": e["raiz"],
                          "necesita": e.get("necesita", []),
                          "estado": estado_texto(e, lista, ap, nueva)})
        if "--json" in argv:
            print(json.dumps(filas, ensure_ascii=False, indent=1))
        else:
            for f in filas:
                print("%-16s %-7s %s" % (f["id"], f["origen"], f["estado"]))
                for m in f["errores"] + f["faltas"]:
                    print("    " + m)
        return 0
    if len(argv) >= 2 and argv[0] in ("instalar", "actualizar", "quitar"):
        e = buscar(argv[1], con_red=argv[0] == "instalar")
        if e is None or e["ficha"] is None:
            print("no conozco «%s» o no tengo su ficha" % argv[1], file=sys.stderr)
            return 2
        imprimir = lambda l: print(l, flush=True)  # noqa: E731
        sistema = "--sin-sistema" not in argv
        if argv[0] == "instalar":
            ok = instalar(e, imprimir, con_sistema=sistema)
        elif argv[0] == "actualizar":
            ok = actualizar(e, imprimir)
        else:
            ok = quitar(e, imprimir, con_sistema=sistema)
        return 0 if ok else 1
    print(__doc__.strip().split("\n\n")[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
