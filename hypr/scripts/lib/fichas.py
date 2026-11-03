#!/usr/bin/env python3
"""
hypr/scripts/lib/fichas.py

Las FICHAS de las apps del catalogo (`celiuz-app.json`) y la lista de las que
se ofrecen. No confundir con `catalogo.py`, que es el de los JUEGOS del modo
gaming: aquel mira lo instalado para jugar; este, las apps opcionales que cada
uno elige al instalar los dotfiles (ver CATALOGO.md).

    fichas.py validar <carpeta-de-la-app>   comprueba su celiuz-app.json
    fichas.py lista [--json]                 las apps de fuera que se ofrecen
    fichas.py instaladas [--json]            las que se anunciaron en este equipo

LA FICHA
--------
Vive en la raiz del repo de cada app, y las rutas que lleva son RELATIVAS a esa
raiz (el icono y las capturas se quedan en el repo de la app: los dotfiles no
engordan). Version 1:

    ficha        1 (el formato; sube si cambia de forma incompatible)
    id           minusculas, numeros y guiones: «cell-cast»
    nombre       como se ensena: «Cell-Cast»
    resumen      una linea
    descripcion  un parrafo
    categoria    una de CATEGORIAS
    icono        ruta relativa a un .svg o .png del repo
    capturas     lista de rutas relativas (puede ir vacia)
    necesita     lista de NECESIDADES (puede ir vacia)
    pide_sudo    null, o una frase que dice PARA QUE se pide
    ordenes      instalar, revisar, quitar (obligatorias) y sistema +
                 sistema_quitar (las dos o ninguna): ordenes que se lanzan
                 DESDE la raiz del repo. `revisar` contesta con su codigo de
                 salida: 0 es «todo listo».
    abrir        opcional: la orden que la abre una vez instalada

La regla de la contrasena es la de todo el repo: instalar, revisar y quitar NO
la piden nunca. Lo que necesite root va en `sistema`, y entonces `pide_sudo`
dice para que, para que la ventana lo avise ANTES de instalar.

COMO SE SABE QUE UNA APP ESTA INSTALADA
---------------------------------------
No se busca por el disco (la pudieron clonar en cualquier carpeta): la app SE
ANUNCIA. Su instalador deja un enlace `apps.d/<id>` -> la raiz de su repo en
`$XDG_DATA_HOME/celiuz/` (o `~/.local/share/celiuz/`), y lo quita al
desinstalarse. Da igual si se instalo desde el catalogo o clonandola a mano.
"""

import json
import os
import re
import sys

FICHERO = "celiuz-app.json"
VERSION = 1
CATEGORIAS = ("sistemas", "gaming", "stream", "escritorio")
NECESIDADES = ("android", "portatil", "nvidia", "bluetooth")
ORDENES_OBLIGATORIAS = ("instalar", "revisar", "quitar")
ORDENES_SISTEMA = ("sistema", "sistema_quitar")
ID_VALIDO = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
REPO_VALIDO = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?(\.git)?$")
SUDO = re.compile(r"(^|[\s;&|(`$])(sudo|pkexec|doas)(\s|$)")

RAIZ_DOTFILES = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.realpath(__file__)))))
LISTA = os.path.join(RAIZ_DOTFILES, "apps", "lista.json")


def dir_datos():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "celiuz")


def dir_anuncios():
    return os.path.join(dir_datos(), "apps.d")


def _ruta_relativa_buena(raiz, ruta):
    """Relativa, sin salirse del repo, y que exista."""
    if not isinstance(ruta, str) or not ruta or os.path.isabs(ruta):
        return False
    real = os.path.realpath(os.path.join(raiz, ruta))
    dentro = os.path.realpath(raiz) + os.sep
    return real.startswith(dentro) and os.path.isfile(real)


def errores_de(ficha, raiz):
    """Lista de problemas de una ficha ya leida (vacia si esta bien)."""
    mal = []
    if not isinstance(ficha, dict):
        return ["la ficha no es un objeto JSON"]
    if ficha.get("ficha") != VERSION:
        mal.append("«ficha» tiene que ser %d (es %r)" % (VERSION, ficha.get("ficha")))
    if not (isinstance(ficha.get("id"), str) and ID_VALIDO.match(ficha["id"])):
        mal.append("«id» tiene que ser minusculas, numeros y guiones (es %r)" % ficha.get("id"))
    for campo in ("nombre", "resumen", "descripcion"):
        v = ficha.get(campo)
        if not (isinstance(v, str) and v.strip()):
            mal.append("falta «%s»" % campo)
    if ficha.get("categoria") not in CATEGORIAS:
        mal.append("«categoria» tiene que ser una de %s (es %r)"
                   % (", ".join(CATEGORIAS), ficha.get("categoria")))
    icono = ficha.get("icono")
    if not _ruta_relativa_buena(raiz, icono):
        mal.append("«icono» no es un fichero del repo: %r" % icono)
    elif not icono.lower().endswith((".svg", ".png")):
        mal.append("«icono» tiene que ser .svg o .png: %r" % icono)
    capturas = ficha.get("capturas", [])
    if not isinstance(capturas, list):
        mal.append("«capturas» tiene que ser una lista")
    else:
        for c in capturas:
            if not _ruta_relativa_buena(raiz, c):
                mal.append("captura que no es un fichero del repo: %r" % c)
    necesita = ficha.get("necesita", [])
    if not isinstance(necesita, list):
        mal.append("«necesita» tiene que ser una lista")
    else:
        for n in necesita:
            if n not in NECESIDADES:
                mal.append("«necesita» no conoce %r (se conocen: %s)" % (n, ", ".join(NECESIDADES)))
    ordenes = ficha.get("ordenes")
    if not isinstance(ordenes, dict):
        mal.append("faltan las «ordenes»")
        ordenes = {}
    for o in ORDENES_OBLIGATORIAS:
        if not (isinstance(ordenes.get(o), str) and ordenes[o].strip()):
            mal.append("falta la orden «%s»" % o)
        elif SUDO.search(ordenes[o]):
            mal.append("la orden «%s» pide contrasena: eso va en «sistema»" % o)
    con_sistema = [o for o in ORDENES_SISTEMA if ordenes.get(o)]
    if len(con_sistema) == 1:
        mal.append("«sistema» y «sistema_quitar» van juntas (solo esta «%s»)" % con_sistema[0])
    pide = ficha.get("pide_sudo")
    if con_sistema and not (isinstance(pide, str) and pide.strip()):
        mal.append("tiene orden «sistema» pero «pide_sudo» no dice para que")
    if not con_sistema and pide is not None:
        mal.append("«pide_sudo» dice algo pero no hay orden «sistema»")
    desconocidas = set(ordenes) - set(ORDENES_OBLIGATORIAS) - set(ORDENES_SISTEMA)
    for o in sorted(desconocidas):
        mal.append("orden desconocida: «%s»" % o)
    if "abrir" in ficha and not (isinstance(ficha["abrir"], str) and ficha["abrir"].strip()):
        mal.append("«abrir» esta vacia")
    return mal


def leer(raiz):
    """(ficha, errores) de la app cuya raiz es `raiz`."""
    ruta = os.path.join(raiz, FICHERO)
    try:
        with open(ruta, encoding="utf-8") as fh:
            ficha = json.load(fh)
    except FileNotFoundError:
        return None, ["no hay %s en %s" % (FICHERO, raiz)]
    except (OSError, ValueError) as e:
        return None, ["%s no se puede leer: %s" % (ruta, e)]
    return ficha, errores_de(ficha, raiz)


def lista(ruta=None):
    """Las apps de fuera que se ofrecen: [{"id", "repo"}]. Lanza ValueError si
    la lista esta mal (es del repo: mejor que lo cante una prueba)."""
    with open(ruta or LISTA, encoding="utf-8") as fh:
        datos = json.load(fh)
    apps = datos.get("apps") if isinstance(datos, dict) else None
    if not isinstance(apps, list):
        raise ValueError("la lista no tiene «apps»")
    vistos = set()
    for a in apps:
        if not (isinstance(a, dict) and isinstance(a.get("id"), str) and ID_VALIDO.match(a["id"])):
            raise ValueError("app sin id valido: %r" % (a,))
        if a["id"] in vistos:
            raise ValueError("id repetido: %s" % a["id"])
        vistos.add(a["id"])
        if not (isinstance(a.get("repo"), str) and REPO_VALIDO.match(a["repo"])):
            raise ValueError("%s: «repo» tiene que ser https://github.com/<dueno>/<repo>" % a["id"])
    return apps


def instaladas():
    """{id: raiz} de las apps que se anunciaron y siguen ahi."""
    d = dir_anuncios()
    hay = {}
    try:
        nombres = sorted(os.listdir(d))
    except OSError:
        return hay
    for n in nombres:
        if not ID_VALIDO.match(n):
            continue
        raiz = os.path.realpath(os.path.join(d, n))
        if os.path.isfile(os.path.join(raiz, FICHERO)):
            hay[n] = raiz
    return hay


def _cli(argv):
    if len(argv) >= 2 and argv[0] == "validar":
        ficha, mal = leer(argv[1])
        if mal:
            for m in mal:
                print("  mal: " + m)
            return 1
        print("bien: %s (%s)" % (ficha["nombre"], ficha["id"]))
        return 0
    if argv and argv[0] == "lista":
        apps = lista()
        if "--json" in argv:
            print(json.dumps(apps, ensure_ascii=False))
        else:
            for a in apps:
                print("%s\t%s" % (a["id"], a["repo"]))
        return 0
    if argv and argv[0] == "instaladas":
        hay = instaladas()
        if "--json" in argv:
            print(json.dumps(hay, ensure_ascii=False))
        else:
            for i, r in hay.items():
                print("%s\t%s" % (i, r))
        return 0
    print(__doc__.strip().split("\n\n")[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
