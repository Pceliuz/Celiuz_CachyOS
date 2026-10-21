"""
remoto/escritorio/textos.py — lo que la app de la PC le dice a la persona.

Sin GTK a proposito: son cuentas con fechas y frases, y las pruebas las
comprueban sin pantalla (tests/unidad/remoto-escritorio.sh). Todas reciben
«ahora» para poder probarlas con un reloj fijo.
"""

import datetime as dt

# Lo que se puede activar por telefono, como lo enseña la maqueta (pantalla 9):
# una casilla puede ser mas de un permiso del protocolo.
CASILLAS = [
    ("Estado y apagar", ("estado", "energia"), True),
    ("Ver y cerrar apps", ("ventanas",), True),
    ("Archivos", ("archivos",), True),
    ("Terminal con sudo", ("terminal",), False),
]

ACCIONES = {
    "servicio_arranca": "El servicio arrancó",
    "servicio_para": "El servicio se apagó",
    "servicio_encendido": "Se encendió el servicio desde la PC",
    "servicio_apagado": "Se apagó el servicio desde la PC",
    "ventana_usb": "Se abrió el canal USB",
    "ventana_usb_cerrada": "Se cerró el canal USB sin terminar",
    "emparejado": "Se emparejó",
    "entrar": "Entró",
    "entrar_mal": "Intento de entrada fallido",
    "salir": "Salió",
    "pase_renovado": "Renovó el pase de 24 h",
    "renovar_mal": "Intento de renovar el pase fallido",
    "pase_quitado": "Se le quitó el pase",
    "revocado": "Se revocó",
    "desbloqueado": "Se desbloqueó",
    "permisos": "Cambiaron sus permisos",
}

MOTIVOS = {"contrasena": "contraseña incorrecta", "bloqueado": "bloqueado por intentos"}


def leer_fecha(texto):
    if not texto:
        return None
    try:
        m = dt.datetime.fromisoformat(texto)
    except (TypeError, ValueError):
        return None
    return m if m.tzinfo else None


def hace(momento, ahora):
    """«hace 12 s», «hace 5 min», «hace 2 h 05 min», «el 18/10»."""
    if momento is None:
        return "nunca"
    s = int((ahora - momento).total_seconds())
    if s < 0:
        s = 0
    if s < 60:
        return f"hace {s} s"
    if s < 3600:
        return f"hace {s // 60} min"
    if s < 86400:
        h, m = divmod(s // 60, 60)
        return f"hace {h} h {m:02d} min"
    return "el " + momento.strftime("%d/%m")


def dia(momento, ahora):
    """«hoy», «mañana», «ayer» o la fecha."""
    d = (momento.date() - ahora.date()).days
    return {0: "hoy", 1: "mañana", -1: "ayer"}.get(d, momento.strftime("%d/%m"))


def pase(disp, ahora):
    """(texto, fraccion que queda de 0 a 1, o None si no hay pase)."""
    hasta = leer_fecha(disp.get("pase_hasta"))
    if hasta is None:
        return "Sin pase: se saca por cable, con la contraseña", None
    if hasta <= ahora:
        return f"Pase vencido {dia(hasta, ahora)} a las {hasta:%H:%M}", None
    queda = (hasta - ahora).total_seconds() / 86400
    return f"Pase: vence {dia(hasta, ahora)} a las {hasta:%H:%M}", max(0.0, min(1.0, queda))


def permisos_de(casillas_marcadas):
    """Lista de casillas marcadas (por indice) -> permisos del protocolo."""
    salida = []
    for i in casillas_marcadas:
        salida.extend(CASILLAS[i][1])
    return salida


def resumen_permisos(permisos):
    nombres = [n for n, ps, _ in CASILLAS if all(p in permisos for p in ps)]
    return " · ".join(nombres) if nombres else "ningún permiso"


def contrasena_valida(uno, dos):
    """None si vale, o lo que falla."""
    if len(uno) < 4:
        return "La contraseña tiene que tener al menos 4 caracteres."
    if uno != dos:
        return "Las dos contraseñas no coinciden."
    return None


def linea_registro(linea, nombres, ahora):
    """Una linea de registro.jsonl -> (cuando, texto) para enseñarla."""
    cuando = leer_fecha(linea.get("cuando"))
    accion = linea.get("accion", "?")
    texto = ACCIONES.get(accion, accion)
    disp = linea.get("dispositivo")
    if disp:
        texto += f" · {nombres.get(disp) or linea.get('nombre') or disp[:8]}"
    if linea.get("motivo"):
        texto += f" ({MOTIVOS.get(linea['motivo'], linea['motivo'])})"
    if accion == "ventana_usb" and linea.get("modo"):
        texto += f" para {linea['modo']}"
    if accion == "ventana_usb_cerrada" and linea.get("estado"):
        texto += f" ({linea['estado']})"
    if cuando is None:
        return "", texto
    hora = cuando.strftime("%H:%M:%S")
    return (hora if cuando.date() == ahora.date() else cuando.strftime("%d/%m %H:%M")), texto
