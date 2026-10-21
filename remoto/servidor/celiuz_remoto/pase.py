"""
remoto/servidor/celiuz_remoto/pase.py — el pase de 24 h, uno por equipo.

- 24 h EXACTAS desde que se renueva, con el reloj de la PC (el del celular no
  cuenta para nada: cambiarle la hora no alarga nada).
- Solo se renueva por el canal USB y con la contraseña (servidor.py, /usb/renovar).
- Lo piden: cerrar apps, archivos, terminal. No lo piden: estado y energia.

Las fechas se guardan en ISO 8601 CON zona: comparar una sin zona contra la
hora de ahora es comparar dos relojes distintos sin saberlo.
"""

import datetime as dt

DURACION = dt.timedelta(hours=24)


def ahora():
    return dt.datetime.now().astimezone()


def iso(momento):
    return momento.isoformat(timespec="seconds")


def leer(texto):
    """ISO -> datetime con zona, o None si no hay o no se entiende."""
    if not texto:
        return None
    try:
        m = dt.datetime.fromisoformat(texto)
    except (TypeError, ValueError):
        return None
    return m if m.tzinfo else None


def renovado(desde=None):
    """El pase_hasta de un pase que se renueva ahora mismo."""
    return iso((desde or ahora()) + DURACION)


def vigente(disp, cuando=None):
    hasta = leer((disp or {}).get("pase_hasta"))
    return hasta is not None and (cuando or ahora()) < hasta


def mensaje_vencido(disp):
    hasta = leer((disp or {}).get("pase_hasta"))
    if hasta is None:
        return "Este celular no tiene pase: conéctalo por cable a la PC para sacarlo."
    return ("El pase de 24 h venció el %s a las %s. Conecta el celular por cable para renovarlo."
            % (hasta.strftime("%d/%m"), hasta.strftime("%H:%M")))
