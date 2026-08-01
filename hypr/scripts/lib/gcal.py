#!/usr/bin/env python3
"""
~/dotfiles/hypr/scripts/lib/gcal.py

Trae los eventos de Google Calendar y los deja en un cache local que el panel
lee al instante. El panel NUNCA habla con la red: si tuviera que esperar a
Google para dibujarse, tardaria un segundo largo en abrirse cada vez.

Tres archivos, cada uno en su sitio y ninguno dentro del repo de dotfiles
(no queremos subir credenciales a git por accidente):

  ~/.config/gcal-panel/credentials.json  <- lo pones tu (client_id y secret)
  ~/.local/share/gcal-panel/token.json   <- lo escribe el flujo OAuth, es
                                            la sesion; se renueva sola
  ~/.cache/gcal-panel/events.json        <- el cache que lee el panel

Uso:
    python3 gcal.py auth    # primera vez: abre el navegador y autoriza
    python3 gcal.py sync    # baja eventos y reescribe el cache
    python3 gcal.py list    # muestra lo que hay en el cache

Los import de Google van dentro de las funciones a proposito: asi el panel
puede importar este modulo y mostrar el calendario peruano aunque las librerias
de Google no esten instaladas todavia.
"""

import datetime as dt
import json
import os
import sys

CONFIG_DIR = os.path.expanduser("~/.config/gcal-panel")
DATA_DIR = os.path.expanduser("~/.local/share/gcal-panel")
CACHE_DIR = os.path.expanduser("~/.cache/gcal-panel")

CRED_PATH = os.path.join(CONFIG_DIR, "credentials.json")
TOKEN_PATH = os.path.join(DATA_DIR, "token.json")
CACHE_PATH = os.path.join(CACHE_DIR, "events.json")

# Solo lectura. Aunque nos equivocaramos en el codigo, esta app no puede borrar
# ni modificar nada de tu calendario.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# Ventana de tiempo que se descarga. Un mes atras para poder mirar el mes
# pasado, y seis por delante que es de sobra para eventos de juegos.
DIAS_ATRAS = 31
DIAS_ADELANTE = 190


def _credenciales(interactivo):
    """Devuelve credenciales validas, refrescando o pidiendo login si toca."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if creds and creds.valid:
        return creds

    # El token de acceso dura una hora, pero el de refresco no caduca mientras
    # no revoques el permiso: esto es lo que evita tener que volver a loguearse.
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not interactivo:
            raise SystemExit(
                "gcal: no hay sesion valida. Corre primero:  python3 gcal.py auth"
            )
        if not os.path.exists(CRED_PATH):
            raise SystemExit(
                f"gcal: falta {CRED_PATH}\n"
                "Descarga el JSON de tu 'OAuth client ID' de tipo Desktop app\n"
                "desde Google Cloud Console y guardalo con ese nombre."
            )
        flow = InstalledAppFlow.from_client_secrets_file(CRED_PATH, SCOPES)
        # Levanta un servidor local un momento y abre el navegador: es el flujo
        # que Google exige para apps de escritorio.
        creds = flow.run_local_server(port=0)

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())
    os.chmod(TOKEN_PATH, 0o600)
    return creds


def sync(interactivo=False):
    """Baja los eventos de TODOS tus calendarios y reescribe el cache."""
    from googleapiclient.discovery import build

    creds = _credenciales(interactivo)
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    ahora = dt.datetime.now(dt.timezone.utc)
    t_min = (ahora - dt.timedelta(days=DIAS_ATRAS)).isoformat()
    t_max = (ahora + dt.timedelta(days=DIAS_ADELANTE)).isoformat()

    eventos = {}
    calendarios = []

    lista = service.calendarList().list().execute().get("items", [])
    for cal in lista:
        if cal.get("selected") is False:
            continue  # calendarios que tienes desmarcados en la web
        cal_id = cal["id"]
        cal_nombre = cal.get("summaryOverride") or cal.get("summary") or cal_id
        calendarios.append(cal_nombre)
        # Los calendarios de festivos de Google tienen todos esta forma de id:
        # es.pe#holiday@group.v.calendar.google.com
        es_festivo_google = "#holiday@group.v.calendar.google.com" in cal_id

        pagina = None
        while True:
            resp = service.events().list(
                calendarId=cal_id,
                timeMin=t_min,
                timeMax=t_max,
                # singleEvents expande las series (un cumpleanos anual llega ya
                # como una ocurrencia por ano, no como una regla de repeticion).
                singleEvents=True,
                orderBy="startTime",
                maxResults=2500,
                pageToken=pagina,
            ).execute()

            for ev in resp.get("items", []):
                if ev.get("status") == "cancelled":
                    continue
                inicio = ev.get("start", {})
                # "date" = evento de dia completo; "dateTime" = con hora.
                if "date" in inicio:
                    fecha = inicio["date"]
                    hora = ""
                else:
                    crudo = inicio.get("dateTime")
                    if not crudo:
                        continue
                    momento = dt.datetime.fromisoformat(crudo).astimezone()
                    fecha = momento.date().isoformat()
                    hora = momento.strftime("%H:%M")
                eventos.setdefault(fecha, []).append({
                    "hora": hora,
                    "titulo": ev.get("summary", "(sin titulo)"),
                    "calendario": cal_nombre,
                    "lugar": ev.get("location", ""),
                    # Los calendarios de festivos que Google agrega solos repiten
                    # lo que ya calcula pe_fechas.py. Se marcan para que el panel
                    # los tape cuando sobran, pero NO se tiran: los "dias no
                    # laborables" que salen por decreto cada ano solo estan aqui.
                    "festivo": es_festivo_google,
                })

            pagina = resp.get("nextPageToken")
            if not pagina:
                break

    for dia in eventos.values():
        dia.sort(key=lambda e: e["hora"] or "00:00")

    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = CACHE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump({
            "actualizado": dt.datetime.now().isoformat(timespec="seconds"),
            "calendarios": calendarios,
            "eventos": eventos,
        }, f, ensure_ascii=False, indent=1)
    # Renombrar es atomico: el panel nunca lee un archivo a medio escribir.
    os.replace(tmp, CACHE_PATH)

    total = sum(len(v) for v in eventos.values())
    return total, calendarios


def cargar_cache():
    """{'2026-07-28': [evento, ...]} de lo ya descargado. {} si no hay nada."""
    try:
        with open(CACHE_PATH) as f:
            return json.load(f).get("eventos", {})
    except (OSError, ValueError):
        return {}


def edad_cache():
    """Segundos desde la ultima sincronizacion, o None si nunca se hizo."""
    try:
        return dt.datetime.now().timestamp() - os.path.getmtime(CACHE_PATH)
    except OSError:
        return None


def hay_sesion():
    return os.path.exists(TOKEN_PATH)


if __name__ == "__main__":
    accion = sys.argv[1] if len(sys.argv) > 1 else "sync"

    if accion == "auth":
        total, cals = sync(interactivo=True)
        print(f"Listo. {total} eventos de {len(cals)} calendarios:")
        for c in cals:
            print(f"  - {c}")
    elif accion == "sync":
        total, cals = sync(interactivo=False)
        print(f"{total} eventos en {len(cals)} calendarios")
    elif accion == "list":
        cache = cargar_cache()
        for fecha in sorted(cache):
            for ev in cache[fecha]:
                print(f"{fecha} {ev['hora'] or '     '}  {ev['titulo']}  [{ev['calendario']}]")
    else:
        print(__doc__)
