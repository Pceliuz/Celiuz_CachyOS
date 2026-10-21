"""
remoto/servidor/celiuz_remoto/vigilancia.py — el interruptor por silencio del celular.

Lo que se decidio con el usuario (remoto/DISEÑO.md, «La vigilancia»):

- La ARMA la persona desde la PC (ventana, pagina Vigilancia); viene desarmada.
- Vigila a los telefonos CON PASE: el pase es «llevo el celular encima». Y solo
  a los que ya han entrado alguna vez por Tailscale, porque es asi como se
  sabe cual de los aparatos de la tailnet es cada uno (su IP).
- Que un telefono vive se mira en Tailscale (`Online` / `LastSeen` de
  `tailscale status --json`), no con latidos de la app: no gasta bateria ni
  depende de que Android deje viva la app.
- Cualquier señal reinicia su cuenta de 1 h. Era de 2 h, con 1 h si el
  telefono avisaba «me estan apagando»; el usuario lo igualó (2026-10-21): un
  celular que se apaga por una mala conexion es el mismo caso que uno que
  avisa, y ese aviso de Android no se llegó a hacer (DISEÑO.md, «Fase 8»).
- Al que calla mas de su margen se le QUITA EL PASE (no se desempareja: se
  recupera por cable).
- Si callan TODOS los vigilados y la PC esta en el MODO GAMING, no se apaga:
  se avisa y ya (lo pidió el usuario: jugando no mira el celular, y apagarle
  la PC a media partida es peor que el riesgo). Se le quita el pase igual.
- Si no, si hay una PERSONA delante (escritorio.presencia:
  teclado, raton o un video) o no se sabe, NO se apaga y se avisa en la PC; si
  no hay nadie, se apaga (con la cuenta atras de energia.py, que alguien que
  llegue justo puede cancelar). Una descarga no es una persona.
- Si se va el internet de casa mas de 1 h, la PC tampoco oye a nadie y se
  apaga. Es lo que se quiere.

`decidir` es una funcion pura (sin red, sin reloj, sin disco) para que las
pruebas recorran la hora sin esperarla.
"""

import datetime as dt
import json
import os
import subprocess
import time

from . import escritorio, pase, registro, rutas

MARGEN = 3600
TEXTO_MARGEN = "%d h" % (MARGEN // 3600)   # el MARGEN, dicho para una persona
CADA = 60     # segundos entre vueltas
SONDEO_TRAS = 600     # sin señal 10 min: se le pregunta directamente
SONDEO_CADA = 300     # y como mucho cada 5 min (un paquete: nada de bateria)


def _epoch(texto):
    try:
        m = dt.datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    except ValueError:
        return None
    # Tailscale pone 0001-01-01 cuando no hay dato.
    return m.timestamp() if m.year > 2000 else None


def leer_tailscale(texto):
    """`tailscale status --json` -> {ip: {"online", "visto", "nombre"}}."""
    try:
        datos = json.loads(texto)
    except ValueError:
        return None
    salida = {}
    for p in (datos.get("Peer") or {}).values():
        # `Online` y `LastSeen` los da el servidor de coordinacion y van CON
        # RETRASO: medido el 2026-10-20, el HONOR reconectado decia «offline,
        # last seen 18m ago» con trafico directo con la PC en ese momento. El
        # ultimo saludo de WireGuard (`LastHandshake`) es de la PC misma y es
        # inmediato. Se toma el mas reciente de los dos.
        vistos = [x for x in (_epoch(p.get("LastSeen")), _epoch(p.get("LastHandshake"))) if x]
        info = {"online": bool(p.get("Online")), "visto": max(vistos) if vistos else None,
                "nombre": p.get("HostName") or ""}
        for ip in p.get("TailscaleIPs") or []:
            salida[ip] = info
    return salida


def preguntar_tailscale():
    """Los aparatos de la tailnet, o None si tailscale no contesta."""
    try:
        r = subprocess.run(["tailscale", "status", "--json"], capture_output=True,
                           text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return leer_tailscale(r.stdout) if r.returncode == 0 else None


def sondear_tailscale(ip):
    """`tailscale ping`: le pregunta AL CELULAR, sin pasar por el servidor de
    coordinacion. Hace falta porque el `Online` de ese servidor se atasca:
    medido el 2026-10-20, el HONOR salia «offline, last seen 27m ago» con
    trafico directo con la PC, y el ping contesto en 80 ms."""
    try:
        r = subprocess.run(["tailscale", "ping", "--c", "1", "--timeout", "5s", ip],
                           capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0 and "pong" in r.stdout


def decidir(telefonos, aparatos, ahora):
    """La vuelta de la vigilancia, sin efectos.

    telefonos: los vigilados [{id, nombre, ip_tailscale, ultima_senal, apagando_en}]
    aparatos:  leer_tailscale(...) o None (tailscale no contesta: no se oye a nadie)
    Devuelve (senales, callados, todos_callados):
      senales  {id: epoch} la ultima señal de cada uno, a guardar
      callados [ids] los que pasaron su margen
    """
    senales, callados = {}, []
    for t in telefonos:
        senal = t.get("ultima_senal")
        p = (aparatos or {}).get(t.get("ip_tailscale"))
        if p and p["online"]:
            senal = ahora
        elif p and p["visto"]:
            senal = max(senal or 0, p["visto"])
        if senal is None:
            # Nunca se le ha oido desde que se vigila: se empieza a contar ya,
            # no desde 1970.
            senal = ahora
        senales[t["id"]] = senal
        if ahora - senal > MARGEN:
            callados.append(t["id"])
    return senales, callados, bool(telefonos) and len(callados) == len(telefonos)


class Vigilancia:
    def __init__(self, almacen, apagar, avisar, aparatos=preguntar_tailscale,
                 presencia=escritorio.presencia, reloj=time.time, sondear=sondear_tailscale,
                 jugando=escritorio.modo_gaming, avisar_jugando=None):
        """`apagar()` empieza la cuenta atras de apagado. La vuelta corre en un
        hilo (llama a tailscale), y la cuenta es una tarea de asyncio: quien la
        da se encarga de pasarla al bucle (call_soon_threadsafe)."""
        self.almacen = almacen
        self.apagar = apagar
        self.avisar = avisar
        self.aparatos = aparatos
        self.presencia = presencia
        self.reloj = reloj
        self.sondear = sondear
        self.jugando = jugando
        # Jugando, el aviso se ve aunque haya «no molestar», sin sonido, y se
        # va solo (lo pidió el usuario): no el critico, que se queda.
        self.avisar_jugando = avisar_jugando or avisar
        self._sondeado = {}       # ip -> cuando se le pregunto por ultima vez
        self.estado = "desarmada"
        self.ultima_vuelta = None

    # --- armada o no (lo decide la persona, desde la PC) ---

    def armada(self):
        try:
            with open(rutas.vigilancia(), encoding="utf-8") as fh:
                return bool(json.load(fh).get("armada"))
        except (OSError, ValueError):
            return False

    def armar(self, si):
        ruta = rutas.vigilancia()
        os.makedirs(os.path.dirname(ruta), mode=0o700, exist_ok=True)
        tmp = ruta + ".nuevo"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"armada": bool(si)}, fh)
        os.replace(tmp, ruta)
        registro.apuntar("vigilancia_armada" if si else "vigilancia_desarmada")
        self.vuelta()

    def vigilados(self):
        return [d for d in self.almacen.todos() if pase.vigente(d) and d.get("ip_tailscale")]

    # --- la vuelta ---

    def vuelta(self):
        self.ultima_vuelta = self.reloj()
        if not self.armada():
            self.estado = "desarmada"
            return self.estado
        telefonos = self.vigilados()
        if not telefonos:
            self.estado = "sin_telefonos"
            return self.estado
        ahora = self.reloj()
        aparatos = self.aparatos()
        aparatos = self._sondear_callados(telefonos, aparatos, ahora)
        senales, callados, todos = decidir(telefonos, aparatos, ahora)
        for t in telefonos:
            if senales[t["id"]] != t.get("ultima_senal"):
                self.almacen.cambiar(t["id"], ultima_senal=senales[t["id"]])
        nombres = {t["id"]: t["nombre"] for t in telefonos}
        for i in callados:
            self.almacen.cambiar(i, pase_hasta=None)
            registro.apuntar("vigilancia_pase_quitado", i, callado_s=round(ahora - senales[i]))
        if todos:
            lista = ", ".join(nombres[i] for i in callados)
            if self.jugando():
                registro.apuntar("vigilancia_avisa", quien="jugando", motivo="modo gaming")
                self.avisar_jugando("Celiuz Remoto: tu celular no da señales",
                                    f"{lista} lleva más de {TEXTO_MARGEN} sin dar señales mientras "
                            "jugabas. No apago la PC porque estás en el modo gaming. Le "
                            "quité el pase: dale una revisada cuando puedas.")
                self.estado = "jugando"
                return self.estado
            quien, motivo = self.presencia()
            if quien == "nadie":
                registro.apuntar("vigilancia_apaga", motivo=motivo)
                self.avisar("Celiuz Remoto: vigilancia",
                            f"{lista} lleva más de {TEXTO_MARGEN} sin dar señales y no hay nadie delante: "
                            "se apaga la PC (puedes cancelarlo).")
                self.apagar()
                self.estado = "apagando"
            else:
                registro.apuntar("vigilancia_avisa", quien=quien, motivo=motivo)
                self.avisar("Celiuz Remoto: tu celular no da señales",
                            f"{lista} lleva más de {TEXTO_MARGEN} sin dar señales. No apago la PC porque "
                            f"{'hay alguien delante' if quien == 'presente' else 'no sé si hay alguien delante'} "
                            "(" + motivo + "). Le quité el pase: revisa el celular.")
                self.estado = "avisando"
        else:
            self.estado = "armada"
        return self.estado

    def _sondear_callados(self, telefonos, aparatos, ahora):
        """A los que llevan un rato sin señal se les pregunta directamente
        (sondear_tailscale). Si contestan, cuentan como en linea."""
        aparatos = dict(aparatos or {})
        for t in telefonos:
            ip = t["ip_tailscale"]
            p = aparatos.get(ip)
            ultima = max([x for x in (t.get("ultima_senal"), p and p["visto"]) if x] or [0])
            if (p and p["online"]) or ahora - ultima < SONDEO_TRAS:
                continue
            if ahora - self._sondeado.get(ip, 0) < SONDEO_CADA:
                continue
            self._sondeado[ip] = ahora
            if self.sondear(ip):
                aparatos[ip] = dict(p or {"nombre": ""}, online=True, visto=ahora)
        return aparatos

    def resumen(self):
        """Para la ventana de la PC y la CLI."""
        ahora = self.reloj()
        aparatos = self.aparatos() if self.armada() else None
        filas = []
        for d in self.almacen.todos():
            senal = d.get("ultima_senal")
            p = (aparatos or {}).get(d.get("ip_tailscale"))
            filas.append({
                "id": d["id"], "nombre": d["nombre"], "vigilado": pase.vigente(d) and bool(d.get("ip_tailscale")),
                "pase": pase.vigente(d), "ip_tailscale": d.get("ip_tailscale"),
                "en_linea": bool(p and p["online"]),
                "callado_s": round(ahora - senal) if senal else None,
            })
        quien, motivo = self.presencia()
        return {"armada": self.armada(), "estado": self.estado, "telefonos": filas,
                "presencia": quien, "presencia_motivo": motivo,
                "margen_s": MARGEN}
