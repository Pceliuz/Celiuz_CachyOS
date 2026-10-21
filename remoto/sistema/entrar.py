#!/usr/bin/python3 -I
"""
remoto/sistema/entrar.py — entrar a la sesion desde la pantalla de inicio (SDDM), una vez.

LO EJECUTA ROOT, y por eso no se ejecuta desde el repo: `instalar.sh
--remoto-sistema` lo COPIA a /usr/local/lib/celiuz-remoto/entrar, de root y
755. Si la unidad apuntara al repo, cualquier programa del usuario podria
editar este fichero y tendria root (es la misma razon por la que el tema de
SDDM es una copia). El `-I` del shebang deja fuera PYTHONPATH y el site del
usuario, por lo mismo.

Lo arranca `celiuz-remoto-entrar@<usuario>.service`, y al usuario lo deja
arrancarlo la regla de polkit (celiuz-remoto.rules.in): solo esa unidad, solo
con su nombre, solo `start`. El servicio de Celiuz Remoto, que NO es root, la
pide cuando el celular pulsa «Entrar» (con la contraseña de la app y el pase:
remoto/DISEÑO.md, «Tras reiniciar»).

Lo que hace:
  1. Mira que NADIE tiene sesion en el asiento (seat0). Reiniciar SDDM se
     lleva por delante todas las sesiones que arranco, asi que esta es la
     comprobacion que no se puede saltar: no se fia de que el servicio la haya
     hecho antes.
  2. Mira que SDDM esta en la pantalla de inicio (hay una sesion `greeter`).
  3. Escribe un autologin de un solo uso (DROPIN) y reinicia SDDM, que solo
     lee el autologin al arrancar.
  4. Espera a que aparezca la sesion del usuario y BORRA el autologin. Si no
     aparece, lo borra igual al rendirse. Por si este proceso muriera a medias,
     la unidad lo borra tambien al acabar (ExecStopPost) y tmpfiles al
     arrancar el equipo (celiuz-remoto.tmpfiles): un autologin olvidado seria
     una PC que se abre sola en cada arranque.

La contraseña de Linux no pasa por aqui: la sesion arranca y se bloquea sola
(la marca la deja el servicio en $XDG_RUNTIME_DIR, lua/autostart.lua la mira).

Codigos de salida: 0 entro; 2 mal llamado; 3 ya hay una sesion; 4 no esta en
la pantalla de inicio; 5 el gestor de pantallas no es SDDM; 6 no aparecio la
sesion a tiempo.
"""

import json
import os
import pwd
import subprocess
import sys
import time

# Los caminos se pueden cambiar SOLO para las pruebas: la unidad de systemd
# arranca con un entorno limpio, y un usuario no puede pasarle variables a una
# unidad de sistema.
DROPIN = os.environ.get("CELIUZ_ENTRAR_DROPIN", "/etc/sddm.conf.d/zz-celiuz-remoto-entrar.conf")
ESPERA = float(os.environ.get("CELIUZ_ENTRAR_ESPERA", "90"))


def decir(texto):
    print(f"celiuz-remoto-entrar: {texto}", file=sys.stderr, flush=True)


def sesiones():
    """Las de logind, o None si no se pudo preguntar (y entonces NO se entra:
    «no lo se» no es «no hay nadie»)."""
    try:
        r = subprocess.run(["loginctl", "list-sessions", "-j"], capture_output=True,
                           text=True, timeout=10, check=False)
        datos = json.loads(r.stdout) if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    return datos if isinstance(datos, list) else None


def de_persona(s):
    # systemd 256+ tiene user, user-early, user-incomplete, user-light: todas
    # son personas. `manager` (el user@.service de alguien con linger) NO tiene
    # asiento y no cuenta: es justo lo que hay tras reiniciar.
    return str(s.get("class", "")).startswith("user") and s.get("seat") == "seat0"


def de_inicio(s):
    return s.get("class") == "greeter" and s.get("seat") == "seat0"


def gestor_de_pantallas():
    try:
        r = subprocess.run(["systemctl", "show", "-p", "Id", "--value", "display-manager.service"],
                           capture_output=True, text=True, timeout=10, check=False)
        return r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def borrar_dropin():
    try:
        os.unlink(DROPIN)
    except FileNotFoundError:
        pass


def escribir_dropin(usuario):
    # Sin Session=: SDDM usa la ultima con la que se entro (lo que quiere quien
    # clone el repo con otra sesion). Relogin=false: si se sale, no vuelve a
    # entrar solo.
    texto = ("# Celiuz Remoto: entrada de UN SOLO USO desde el celular.\n"
             "# La borra remoto/sistema/entrar.py al entrar; si la ves aqui, borrala.\n"
             f"[Autologin]\nUser={usuario}\nRelogin=false\n")
    tmp = DROPIN + ".nuevo"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(texto)
    os.chmod(tmp, 0o644)
    os.replace(tmp, DROPIN)


def principal(argv):
    if len(argv) != 2:
        decir("uso: entrar <usuario>")
        return 2
    usuario = argv[1]
    try:
        cuenta = pwd.getpwnam(usuario)
    except KeyError:
        decir(f"no existe el usuario «{usuario}»")
        return 2
    if cuenta.pw_uid < 1000:
        decir(f"«{usuario}» es una cuenta del sistema: no se entra con ella")
        return 2

    lista = sesiones()
    if lista is None:
        decir("no pude preguntarle a logind quién hay: no toco nada")
        return 3
    ocupadas = [s for s in lista if de_persona(s)]
    if ocupadas:
        quien = ", ".join(sorted({str(s.get("user")) for s in ocupadas}))
        decir(f"ya hay una sesión en la pantalla ({quien}): reiniciar SDDM la cerraría")
        return 3
    if not any(de_inicio(s) for s in lista):
        decir("no está en la pantalla de inicio de sesión")
        return 4
    gestor = gestor_de_pantallas()
    if gestor != "sddm.service":
        decir(f"el gestor de pantallas es «{gestor or 'ninguno'}», no SDDM")
        return 5

    escribir_dropin(usuario)
    try:
        decir(f"autologin de un solo uso para {usuario}: reinicio SDDM")
        subprocess.run(["systemctl", "restart", "display-manager.service"],
                       timeout=60, check=False)
        limite = time.monotonic() + ESPERA
        while time.monotonic() < limite:
            lista = sesiones() or []
            if any(de_persona(s) and s.get("uid") == cuenta.pw_uid for s in lista):
                decir(f"{usuario} ya tiene sesión")
                return 0
            time.sleep(1)
        decir(f"la sesión de {usuario} no apareció en {ESPERA:.0f} s")
        return 6
    finally:
        borrar_dropin()


if __name__ == "__main__":
    sys.exit(principal(sys.argv))
