"""
remoto/servidor/celiuz_remoto/cable.py — emparejar y renovar por el cable, paso a paso.

Lo usan la CLI (celiuz-remoto.py emparejar / renovar) y la app de la PC, para
que el orden de los pasos viva en un solo sitio:

    1. pedir al servicio la ventana USB (con la contraseña, si es emparejar)
    2. adb reverse: el celular ve el canal USB de la PC
    3. abrir la app del celular con el codigo (intent explicito)
    4. esperar a que el celular termine, o a que la ventana caduque
    5. cerrar el canal SIEMPRE, salga como salga (y la ventana, si sigue abierta)

`avisar(texto)` recibe cada paso, para enseñarlo.
"""

from . import adb, control

ESPERA_EXTRA = 15


class ErrorCable(Exception):
    pass


def elegir(celulares, serie=None):
    """El celular con que trabajar: el pedido, o el unico listo."""
    if serie:
        for c in celulares:
            if c["serie"] == serie:
                return c
        raise ErrorCable(f"no veo el celular {serie} por el cable")
    listos = [c for c in celulares if c["estado"] == "listo"]
    if not celulares:
        raise ErrorCable("no hay ningún celular conectado por cable")
    if not listos:
        raise ErrorCable("el celular no ha autorizado la depuración USB: "
                         "toca «Permitir» en su pantalla")
    if len(listos) > 1:
        nombres = ", ".join(f"{c['nombre']} ({c['serie']})" for c in listos)
        raise ErrorCable(f"hay {len(listos)} celulares conectados; di cuál: {nombres}")
    return listos[0]


def _pedir(metodo, ruta, cuerpo=None, timeout=10.0):
    try:
        return control.pedir(metodo, ruta, cuerpo, timeout=timeout)
    except control.SinServicio as e:
        raise ErrorCable(str(e)) from None


def _por_cable(serie, cuerpo, avisar):
    codigo, v = _pedir("POST", "/control/ventana", dict(cuerpo, serie=serie))
    if codigo != 200:
        raise ErrorCable(v.get("mensaje") or f"el servicio contestó {codigo}")
    puerto = v["puerto"]
    abierto = False
    try:
        avisar("Abriendo el canal USB…")
        adb.abrir_canal(serie, puerto)
        abierto = True
        avisar("Abriendo la app en el celular…")
        adb.abrir_app(serie, cuerpo["modo"], v["codigo"])
        avisar("Esperando al celular…")
        _, fin = _pedir("GET", f"/control/ventana?espera={v['caduca']}",
                        timeout=v["caduca"] + ESPERA_EXTRA)
    except adb.ErrorAdb as e:
        raise ErrorCable(str(e)) from None
    finally:
        if abierto:
            adb.cerrar_canal(serie, puerto)
        # Si algo fallo a medias, que la ventana no se quede abierta 2 minutos.
        try:
            control.pedir("DELETE", "/control/ventana")
        except control.SinServicio:
            pass
    if fin.get("estado") != "hecho":
        raise ErrorCable({"caducada": "el celular no contestó a tiempo (2 minutos)",
                          "cancelada": "cancelado"}.get(fin.get("estado"),
                                                        f"terminó así: {fin.get('estado')}"))
    return fin


def emparejar(serie, contrasena, permisos, nombre=None, avisar=lambda t: None):
    return _por_cable(serie, {"modo": "emparejar", "contrasena": contrasena,
                              "permisos": list(permisos), "nombre": nombre}, avisar)


def renovar(serie, avisar=lambda t: None):
    return _por_cable(serie, {"modo": "renovar"}, avisar)


def cancelar():
    try:
        control.pedir("DELETE", "/control/ventana")
    except control.SinServicio:
        pass
