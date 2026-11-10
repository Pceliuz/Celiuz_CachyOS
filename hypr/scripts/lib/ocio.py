#!/usr/bin/env python3
"""
hypr/scripts/lib/ocio.py - que es ocio: lo que el modo estudio aparta.

Es una CLASIFICACION sobre los .desktop, igual que catalogo.clase_de_desktop
clasifica juegos y lanzadores. No lee nada por su cuenta: le pide las entradas a
catalogo._entradas_desktop() (el orden XDG ya resuelto) y usa catalogo._visible(),
para no tener dos lectores de .desktop que se separen a plazos.

LA IDEA
-------
El modo estudio es el primo del modo programador: aparta lo mismo (juegos y
tiendas) y ademas el ocio, que es lo que quita el estudio. Se decide por las
Categories= de freedesktop y, para lo que se declara mal, por su id.

SE APARTA (el ocio)
-------------------
    juego     Game
    video     AudioVideo, Player, Video, TV
    musica    Audio, Music
    chats     Chat, InstantMessaging, IRCClient, Telephony, VideoConference
    redes     FeedReader, P2P, FileSharing, Social
              (Network no sirve para decidir: lo declara tambien el navegador,
              que se queda)

SE QUEDA (aunque lo parezca)
---------------------------
    el editor, la terminal y el navegador (documentacion). Se miran ANTES que
    las categorias: hay apps que se apuntan a Player solo por llevar un visor
    dentro, y una utilidad que se apunta a Game (gestores de mandos, de Proton)
    tampoco es ocio.

Uso:
    ocio.py            lista el ocio instalado: clase e id, separados por un tab
    ocio.py ID         dice la clase de esa app (vacio si no es ocio)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalogo  # noqa: E402

JUEGO = "juego"
VIDEO = "video"
MUSICA = "musica"
CHATS = "chats"
REDES = "redes"

# Por categoria de freedesktop, en orden: gana la primera clase que case.
CATEGORIAS = [
    (JUEGO, {"game"}),
    (VIDEO, {"audiovideo", "player", "video", "tv"}),
    (MUSICA, {"audio", "music"}),
    (CHATS, {"chat", "instantmessaging", "ircclient", "telephony", "videoconference"}),
    (REDES, {"feedreader", "p2p", "filesharing", "social"}),
]

# Lo que se queda aunque se apunte a lo de arriba: se mira ANTES que el resto.
SE_QUEDA = {
    # el navegador es documentacion
    "firefox", "firefox-esr", "firefox-developer-edition", "librewolf", "chromium",
    "google-chrome", "brave-browser", "vivaldi-stable", "qutebrowser", "epiphany",
    "org.gnome.epiphany", "microsoft-edge",
    # el editor
    "code", "code-oss", "vscodium", "codium", "visual-studio-code",
    # la terminal
    "alacritty", "kitty", "foot", "wezterm", "org.wezfurlong.wezterm",
    "konsole", "gnome-terminal", "xterm",
}

# Utilidades que se apuntan a Game o a AudioVideo y no son ocio.
HERRAMIENTAS = {
    "input-remapper", "antimicrox", "sc-controller", "protontricks", "winecfg",
    "pavucontrol", "pulseaudio-equalizer", "easyeffects", "helvum", "qpwgraph",
}


# Ids que se declaran mal: su .desktop no lleva la categoria que les toca
# (Telegram solo pone Network, por ejemplo), pero son ocio y se apartan.
POR_ID = {
    "telegram-desktop": CHATS,
    "telegramdesktop": CHATS,
    "discord": CHATS,
    "whatsapp-for-linux": CHATS,
    "spotify": MUSICA,
    "vlc": VIDEO,
    "mpv": VIDEO,
    "transmission-gtk": REDES,
    "qbittorrent": REDES,
}


def clase_de(ident, campos):
    """juego | video | musica | chats | redes | None (no es ocio)."""
    bajo = ident.lower()
    if bajo in SE_QUEDA:
        return None
    if bajo in POR_ID:
        return POR_ID[bajo]
    if bajo in HERRAMIENTAS:
        return None
    categorias = {c.strip().lower() for c in campos.get("Categories", "").split(";") if c.strip()}
    for clase, suyas in CATEGORIAS:
        if categorias & suyas:
            # Una utilidad que se apunta a Game (gestores de mandos, de Proton).
            if clase == JUEGO and categorias & {"utility", "settings"}:
                return None
            return clase
    return None


def es_ocio_id(ident):
    """True si ese id es ocio. Acepta el id con o sin .desktop."""
    if ident.endswith(".desktop"):
        ident = ident[:-len(".desktop")]
    entrada = catalogo._entradas_desktop().get(ident)
    if not entrada:
        # Sin .desktop instalado no hay Categories que leer: se decide por el id.
        return clase_de(ident, {}) is not None
    return clase_de(ident, entrada[1]) is not None


def ocio_instalado():
    """[(clase, id)] de lo que es ocio y esta instalado, ordenado por clase."""
    salida = []
    for ident, (_ruta, campos) in catalogo._entradas_desktop().items():
        if not catalogo._visible(campos):
            continue
        clase = clase_de(ident, campos)
        if clase:
            salida.append((clase, ident))
    return sorted(salida)


def main():
    if len(sys.argv) > 1:
        ident = sys.argv[1]
        if ident.endswith(".desktop"):
            ident = ident[:-len(".desktop")]
        entrada = catalogo._entradas_desktop().get(ident)
        if not entrada:
            return 1
        clase = clase_de(ident, entrada[1])
        if clase:
            print(clase)
        return 0 if clase else 1
    for clase, ident in ocio_instalado():
        print("%s\t%s" % (clase, ident))
    return 0


if __name__ == "__main__":
    sys.exit(main())
