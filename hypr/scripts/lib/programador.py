#!/usr/bin/env python3
"""
hypr/scripts/lib/programador.py — lo que sabe el modo programador: QUE apps de
trabajo hay instaladas, en que seccion va cada una, el tema de sus pantallas y
los ajustes del usuario.

Es el primo de `catalogo.py` (el del modo gaming) y se apoya en el: lee los
mismos .desktop (`catalogo._entradas_desktop()`, el orden XDG ya resuelto) y
usa su clasificacion para dejar FUERA los juegos y los lanzadores.

LAS SECCIONES (las tres carreras del usuario, y lo que se usa al lado)
---------------------------------------------------------------------
Cada app va a la PRIMERA seccion que la reclame, por las `Categories=` de su
.desktop (el estandar de freedesktop) y, para lo que se declara mal, por su id:
    codigo      Development, IDE, TextEditor, Science... (software e IA)
    sistemas    System, TerminalEmulator, Monitor, FileManager, Emulator...
    seguridad   Security, y los conocidos por id (wireshark, burp, ghidra...)
    documentos  Office, WordProcessor, Spreadsheet, Presentation, Viewer
    web         el navegador predeterminado, reproductores de musica y video
                (el anime de la otra pantalla) y el chat
    mias        las que añada el usuario desde el menu rapido
    terminal    herramientas de terminal instaladas (nvim, lazygit, btop...),
                que se abren dentro de una terminal
Nada cableado a un equipo: lo que no este instalado no sale, y una seccion
vacia lo dice en vez de esconderse (la de seguridad, en un equipo recien
instalado, enseña que herramientas apareceran).

LOS AJUSTES (~/.config/celiuz/modo-programador.json, no se versiona)
-------------------------------------------------------------------
    apps          [{label, cmd, icon_name}] que añadio el usuario
    ocultar       ids que no deben salir ("desktop:vim")
    no_molestar   true: los avisos en «no molestar» mientras dura (de fabrica)
    apagar_fondo  true: el fondo en video fuera (deja la VRAM a los modelos de
                  IA y a lo que compiles; de fabrica)
    tema          {clave: "#rrggbb"} para cambiar colores del tema (abajo)
    menu          ids de las apps fijadas en el menu rapido, en orden. Sin el,
                  las de fabrica (favoritas_de_fabrica()); al fijar o quitar
                  una desde el menu se escribe entero

Uso:
    programador.py               resumen legible
    programador.py --json        todo, para las pantallas
"""

import functools
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import apps  # noqa: E402
import catalogo  # noqa: E402

# El tema de las pantallas del modo: el de un editor oscuro y una terminal, y a
# proposito NADA que ver con el violeta del modo gaming (lo pidio el usuario:
# «completamente diferente»). No es una copia de la paleta del repo —esa sigue
# en colores.conf y la usa todo lo demas—: es la de este modo, y vive solo aqui.
# Cada uno puede cambiar cualquier color en su modo-programador.json («tema»).
TEMA_FABRICA = {
    "fondo": "#0b0e14",      # el del editor
    "panel": "#11151c",      # barras laterales y tarjetas
    "linea": "#161b24",      # la linea seleccionada
    "borde": "#252b37",
    "texto": "#c9d1d9",
    "tenue": "#6e7681",      # numeros de linea, ayudas
    "comentario": "#5c6773",
    "verde": "#7ee787",      # el acento: el prompt, el foco
    "cian": "#56d4dd",
    "azul": "#79c0ff",
    "amarillo": "#e3b341",
    "naranja": "#ffa657",
    "rojo": "#ff7b72",
    "morado": "#d2a8ff",
}

CODIGO, SISTEMAS, SEGURIDAD, DOCUMENTOS, WEB, MIAS, TERMINAL = (
    "codigo", "sistemas", "seguridad", "documentos", "web", "mias", "terminal")

# (clave, carpeta que enseña el explorador, titulo, color del tema)
SECCIONES = [
    (CODIGO, "codigo/", "Código e IA", "verde"),
    (SISTEMAS, "sistemas/", "Sistemas", "azul"),
    (SEGURIDAD, "seguridad/", "Ciberseguridad", "rojo"),
    (DOCUMENTOS, "documentos/", "Documentos", "amarillo"),
    (WEB, "web/", "Web, música y anime", "morado"),
    (TERMINAL, "terminal/", "En la terminal", "cian"),
    (MIAS, "mias/", "Mis apps", "naranja"),
]

# Por categoria de freedesktop, en orden: gana la primera seccion que case.
CATEGORIAS = [
    (SEGURIDAD, {"security"}),
    (CODIGO, {"development", "ide", "science", "math", "datavisualization",
              "artificialintelligence", "database", "revisioncontrol", "debugger",
              "guidesigner", "webdevelopment", "translation"}),
    (DOCUMENTOS, {"office", "wordprocessor", "spreadsheet", "presentation",
                  "viewer", "calculator", "dictionary", "calendar", "projectmanagement"}),
    (WEB, {"webbrowser", "player", "chat", "instantmessaging", "email", "music"}),
    (SISTEMAS, {"system", "terminalemulator", "monitor", "filemanager", "filetools",
                "emulator", "remoteaccess", "network", "packagemanager"}),
    (CODIGO, {"texteditor"}),
]

# Lo que se declara mal (o con categorias genericas), por id del .desktop en
# minusculas o una subcadena de el. Herramientas de seguridad que suelen venir
# como `Network` o `Utility`, y editores que se dicen `Utility`.
POR_ID = {
    SEGURIDAD: ("wireshark", "burp", "zaproxy", "ghidra", "zenmap", "keepass",
                "veracrypt", "metasploit", "armitage", "maltego", "cutter", "iaito",
                "bettercap", "hashcat", "autopsy", "torbrowser", "tor-browser", "kleopatra",
                "gtkhash", "seahorse", "imhex", "bless", "okteta", "hydra"),
    CODIGO: ("jupyter", "spyder", "rstudio", "dbeaver", "postman", "insomnia", "bruno",
             "zed", "neovide", "lapce", "cursor", "windsurf", "pycharm", "intellij", "clion",
             "webstorm", "goland", "rider", "datagrip", "codium", "vscodium", "sublime",
             "kate", "gitg", "gitkraken", "github-desktop", "lmstudio", "ollama", "alpaca",
             "anythingllm", "jshell", "jconsole", "meld", "kdevelop", "qtcreator", "geany", "emacs",
             "obsidian"),
    SISTEMAS: ("virt-manager", "gnome-boxes", "virtualbox", "remmina", "gparted",
               "docker", "podman", "pods", "cockpit", "putty", "filezilla", "missioncenter",
               "kernelmanager", "scx-manager", "btrfs-assistant"),
    WEB: ("discord", "vesktop", "telegram", "signal", "whatsapp", "slack", "spotify",
          "glassy", "zapzap", "element"),
}

# Ni de trabajo ni de nada: ajustes del escritorio y bienvenida del sistema. Se
# pueden añadir igual a mano.
NO_ES_TRABAJO = {"cachyos-hello", "nwg-look", "qt6ct", "qt5ct", "celiuzpaper",
                 "nvidia-settings", "uuctl", "lstopo", "xgps", "xgpsspeed", "qv4l2",
                 "qvidcap", "celiuz-remoto", "limine-snapper-restore",
                 "org.pulseaudio.pavucontrol", "dev.noctalia.noctalia"}

# Herramientas de terminal, si estan instaladas (shutil.which): (orden, nombre,
# seccion, icono del tema). Solo las INTERACTIVAS: un `nmap` a secas imprime la
# ayuda y la terminal se cerraria. Las que ya traen su .desktop con
# Terminal=true (btop, nvtop, vim) salen por ahi y no se repiten.
HERRAMIENTAS_TERMINAL = [
    ("nvim", "Neovim", CODIGO, "nvim"),
    ("hx", "Helix", CODIGO, "helix"),
    ("lazygit", "lazygit", CODIGO, "git"),
    ("ipython", "IPython", CODIGO, "python"),
    ("python3", "Python", CODIGO, "python"),
    ("node", "Node.js", CODIGO, "nodejs"),
    ("gdb", "GDB", CODIGO, "utilities-terminal"),
    ("r2", "radare2", SEGURIDAD, "utilities-terminal"),
    ("msfconsole", "Metasploit", SEGURIDAD, "utilities-terminal"),
    ("tmux", "tmux", SISTEMAS, "utilities-terminal"),
    ("htop", "htop", SISTEMAS, "htop"),
    ("lazydocker", "lazydocker", SISTEMAS, "docker"),
]

# Lo que la seccion de seguridad enseña cuando no hay nada: para que no parezca
# un fallo, y para saber por donde empezar.
SUGERENCIAS_SEGURIDAD = "wireshark-qt · nmap · ghidra · burpsuite · metasploit · hashcat"


# --- Rutas ----------------------------------------------------------------------
def _config():
    return os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")


def config_usuario():
    return os.path.join(_config(), "celiuz", "modo-programador.json")


def carpeta_ganchos():
    return os.path.join(_config(), "celiuz", "modo-programador.d")


def ajustes():
    datos = catalogo._leer_json(config_usuario())
    apps_ = [a for a in datos.get("apps", []) if isinstance(a, dict) and a.get("cmd")]
    tema = dict(TEMA_FABRICA)
    for k, v in (datos.get("tema") or {}).items():
        if k in tema and isinstance(v, str) and len(v) == 7 and v.startswith("#"):
            tema[k] = v
    return {"apps": apps_, "ocultar": {str(x) for x in datos.get("ocultar", [])},
            "no_molestar": datos.get("no_molestar", True) is not False,
            "apagar_fondo": datos.get("apagar_fondo", True) is not False,
            "tema": tema}


def tema_rgb(tema=None):
    """El tema en tuplas (r, g, b) de 0 a 1, para Cairo."""
    tema = tema or ajustes()["tema"]
    return {k: tuple(int(v[i:i + 2], 16) / 255 for i in (1, 3, 5)) for k, v in tema.items()}


# --- Clasificar -------------------------------------------------------------------
def seccion_de(ident, campos):
    """La seccion de un .desktop, o None si no es de trabajo."""
    bajo = ident.lower()
    if bajo in NO_ES_TRABAJO:
        return None
    if catalogo.clase_de_desktop(ident, campos) in (catalogo.JUEGO, catalogo.LANZADOR):
        return None
    for seccion, pistas in POR_ID.items():
        if any(p in bajo for p in pistas):
            return seccion
    categorias = {c.strip().lower() for c in campos.get("Categories", "").split(";") if c.strip()}
    if not categorias & {"audio", "video", "audiovideo"} and categorias & {"settings", "desktopsettings"} \
            and not categorias & {"development", "system"}:
        return None
    for seccion, cats in CATEGORIAS:
        if categorias & cats:
            return seccion
    return None


def _entrada(ident, ruta, campos, seccion):
    terminal = campos.get("Terminal", "").lower() == "true"
    return {
        "id": ("flatpak:" if "flatpak/exports" in ruta else "desktop:") + ident,
        "nombre": campos.get("Name") or ident,
        "descripcion": campos.get("Comment") or campos.get("GenericName") or "",
        "cmd": apps.limpiar_exec(campos.get("Exec", "")),
        "icono": campos.get("Icon", ""),
        "seccion": seccion,
        "terminal": terminal,
        # Lo que sirve para reconocer su ventana (ver es_de_trabajo()).
        "pistas": [p for p in (ident, campos.get("StartupWMClass", ""), campos.get("Icon", "")) if p],
    }


@functools.lru_cache(maxsize=1)
def _del_sistema():
    salida = []
    for ident, (ruta, campos) in catalogo._entradas_desktop().items():
        if not catalogo._visible(campos):
            continue
        seccion = seccion_de(ident, campos)
        if seccion:
            salida.append(_entrada(ident, ruta, campos, seccion))
    return salida


def herramientas_terminal(ya):
    """Las herramientas de terminal instaladas que no salgan ya por un .desktop."""
    salida = []
    for orden, nombre, seccion, icono in HERRAMIENTAS_TERMINAL:
        if orden in ya or not shutil.which(orden):
            continue
        salida.append({"id": "terminal:" + orden, "nombre": nombre, "descripcion": "$ " + orden,
                       "cmd": orden, "icono": icono, "seccion": TERMINAL, "terminal": True,
                       "pistas": [], "de": seccion})
    return salida


def apps_de_trabajo(aj=None):
    """Todas las apps del modo, cada una con su seccion, en el orden de las
    secciones y por nombre dentro de cada una. El navegador predeterminado va
    siempre (en `web`), aunque su .desktop no se declare navegador."""
    aj = aj or ajustes()
    salida = [dict(a) for a in _del_sistema()]
    nav = apps.navegador()
    if nav:
        for a in salida:
            if catalogo._normal(a["cmd"]) == catalogo._normal(nav["cmd"]):
                a["seccion"], a["navegador"] = WEB, True
                break
        else:
            salida.append({"id": "app:" + nav["cmd"], "nombre": nav.get("label") or nav["cmd"],
                           "descripcion": "navegador predeterminado", "cmd": nav["cmd"],
                           "icono": nav.get("icon_name", ""), "seccion": WEB, "terminal": False,
                           "pistas": [], "navegador": True})
    ordenes = {os.path.basename((a["cmd"] or "").split()[0]) for a in salida if a["cmd"]}
    salida += herramientas_terminal(ordenes)
    vistos = {catalogo._normal(a["cmd"]) for a in salida}
    for a in aj["apps"]:
        mia = {"id": "mia:" + a["cmd"], "nombre": a.get("label") or a["cmd"], "descripcion": "añadida por ti",
               "cmd": a["cmd"], "icono": a.get("icon_name", ""), "seccion": MIAS,
               "terminal": bool(a.get("terminal")), "pistas": [], "mia": True}
        if catalogo._normal(a["cmd"]) in vistos:
            # Ya estaba en otra seccion: se queda alli, pero marcada como tuya
            # (para que se pueda quitar desde el menu).
            for x in salida:
                if catalogo._normal(x["cmd"]) == catalogo._normal(a["cmd"]):
                    x["mia"] = True
            continue
        salida.append(mia)
    salida = [a for a in salida if a["id"] not in aj["ocultar"] and a["cmd"]]
    orden = {s[0]: i for i, s in enumerate(SECCIONES)}
    salida.sort(key=lambda a: (orden.get(a["seccion"], 99), a["nombre"].lower()))
    return salida


def por_seccion(lista=None):
    lista = apps_de_trabajo() if lista is None else lista
    return [(clave, carpeta, titulo, color, [a for a in lista if a["seccion"] == clave])
            for clave, carpeta, titulo, color in SECCIONES]


def buscar(lista, texto):
    """Filtro como el de una paleta de ordenes: todas las letras, en orden, en
    el nombre, la orden o la descripcion. Primero lo que EMPIEZA por el texto."""
    t = "".join(texto.lower().split())
    if not t:
        return list(lista)

    def en_orden(cadena):
        i = 0
        for c in cadena:
            if i < len(t) and c == t[i]:
                i += 1
        return i == len(t)

    puntos = []
    for a in lista:
        nombre = a["nombre"].lower()
        resto = (a["cmd"] + " " + a.get("descripcion", "")).lower()
        if nombre.replace(" ", "").startswith(t):
            p = 0
        elif t in nombre.replace(" ", ""):
            p = 1
        elif t in resto:
            p = 2
        elif en_orden(nombre):
            p = 3
        else:
            continue
        puntos.append((p, a["nombre"].lower(), a))
    return [a for _, _, a in sorted(puntos, key=lambda x: (x[0], x[1]))]


# --- Ventanas -------------------------------------------------------------------
def _sin_signos(texto):
    return "".join(c for c in (texto or "").lower() if c.isalnum())


TERMINALES = {"kitty", "foot", "alacritty", "wezterm", "ghostty", "konsole",
              "org.wezfurlong.wezterm", "com.mitchellh.ghostty", "xterm"}


def es_de_trabajo(ventana, lista):
    """Si una ventana es de alguna app del modo (o una terminal). Se compara sin
    signos, como en el modo gaming: la clase de Brave es «brave-browser» y su
    orden «brave»; la de VS Code, «code»; la de Dolphin, «org.kde.dolphin»."""
    clase = (ventana.get("class") or ventana.get("initialClass") or "").lower()
    if not clase:
        return False
    if clase in TERMINALES or clase.startswith("celiuz-") or clase.startswith("prog-"):
        return True
    limpia = _sin_signos(clase)
    for a in lista:
        candidatos = [_sin_signos(p) for p in a.get("pistas", [])]
        partes = (a["cmd"] or "").split()
        if partes:
            candidatos.append(_sin_signos(os.path.basename(partes[0])))
        for c in candidatos:
            if c and (c == limpia or (len(c) >= 4 and (c in limpia or limpia in c))):
                return True
    return False


# --- Lo del usuario ---------------------------------------------------------------
def _guardar(datos):
    ruta = config_usuario()
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta + ".nuevo", "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=4)
        fh.write("\n")
    os.replace(ruta + ".nuevo", ruta)


def anadir_app(app):
    """Guarda {label, cmd, icon_name[, terminal]} entre las tuyas, y la saca de
    `ocultar` si estaba."""
    datos = catalogo._leer_json(config_usuario())
    datos["ocultar"] = [x for x in datos.get("ocultar", []) if x not in ("mia:" + app["cmd"],)]
    if not datos["ocultar"]:
        del datos["ocultar"]
    if not any(isinstance(a, dict) and a.get("cmd") == app["cmd"] for a in datos.get("apps", [])):
        datos.setdefault("apps", []).append(app)
    _guardar(datos)


# --- Las fijadas en el menu rapido ---------------------------------------------------
def favoritas_de_fabrica(lista):
    """Lo que el usuario dijo que usa al programar, si esta instalado: el
    navegador (y la musica en el), los archivos, el editor, la oficina y un
    reproductor de musica. Una de cada, la primera que haya."""
    elegidas = []

    def primera(cond):
        for a in lista:
            if cond(a) and a["id"] not in elegidas:
                elegidas.append(a["id"])
                return

    primera(lambda a: a.get("navegador"))
    primera(lambda a: "dolphin" in a["id"].lower() or "nautilus" in a["id"].lower()
            or "thunar" in a["id"].lower() or "nemo" in a["id"].lower())
    primera(lambda a: a["seccion"] == CODIGO and not a["terminal"]
            and any(p in a["id"].lower() for p in ("code", "zed", "idea", "pycharm", "codium", "kate", "sublime")))
    primera(lambda a: "onlyoffice" in a["id"].lower() or "libreoffice" in a["id"].lower())
    primera(lambda a: a["seccion"] == WEB and not a.get("navegador")
            and any(p in (a["id"] + a["nombre"]).lower() for p in ("music", "spotify", "glassy", "rhythmbox",
                                                                 "elisa", "amberol", "strawberry")))
    return elegidas


def favoritas(lista=None):
    """Las apps fijadas del menu, en su orden (solo las que siguen existiendo)."""
    lista = apps_de_trabajo() if lista is None else lista
    datos = catalogo._leer_json(config_usuario())
    ids = datos.get("menu")
    if not isinstance(ids, list):
        ids = favoritas_de_fabrica(lista)
    por_id = {a["id"]: a for a in lista}
    return [por_id[i] for i in ids if i in por_id]


def fijar(ident):
    """Añade una app (por id) al final de las fijadas."""
    datos = catalogo._leer_json(config_usuario())
    ids = [a["id"] for a in favoritas()]
    if ident not in ids:
        ids.append(ident)
    datos["menu"] = ids
    _guardar(datos)


def desfijar(ident):
    """La quita de las fijadas (la app sigue en el inicio). False si no estaba."""
    ids = [a["id"] for a in favoritas()]
    if ident not in ids:
        return False
    datos = catalogo._leer_json(config_usuario())
    datos["menu"] = [i for i in ids if i != ident]
    _guardar(datos)
    return True


def candidatas_para_anadir():
    """Las apps instaladas que aun no estan en el modo (ni juegos ni ocultas)."""
    ya = {catalogo._normal(a["cmd"]) for a in apps_de_trabajo()}
    salida = []
    for ident, (_, campos) in sorted(catalogo._entradas_desktop().items(),
                                     key=lambda x: (x[1][1].get("Name") or x[0]).lower()):
        if not catalogo._visible(campos) or catalogo.clase_de_desktop(ident, campos) == catalogo.JUEGO:
            continue
        cmd = apps.limpiar_exec(campos.get("Exec", ""))
        if cmd and catalogo._normal(cmd) not in ya:
            salida.append({"label": campos.get("Name") or ident, "cmd": cmd,
                           "icon_name": campos.get("Icon", ""),
                           "terminal": campos.get("Terminal", "").lower() == "true"})
    return salida


def _cli(argv):
    if argv and argv != ["--json"]:
        print("uso: programador.py [--json]", file=sys.stderr)
        return 2
    lista = apps_de_trabajo()
    if argv == ["--json"]:
        print(json.dumps({"secciones": [{"clave": c, "titulo": t, "apps": a}
                                        for c, _, t, _, a in por_seccion(lista)]},
                         ensure_ascii=False, indent=2))
        return 0
    for _, carpeta, titulo, _, lista_ in por_seccion(lista):
        print("%s  %s (%d)" % (carpeta, titulo, len(lista_)))
        for a in lista_:
            print("    %-30s %s%s" % (a["nombre"][:30], a["cmd"][:40], "  [terminal]" if a["terminal"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
