# Celiuz Remoto

> **Las 8 fases hechas** (2026-10-21): estado, apagar, apps, vigilancia, entrar
> tras un reinicio, archivos (que se guardan en la galería o en Descargas del
> celular), terminal, subir a la PC, ver y manejar la pantalla, despertar desde
> otro equipo y ayudar a un amigo sin cable. Qué está probado de verdad y qué
> no, en [`DISEÑO.md`](DISEÑO.md#fases).

## Para empezar

**La guía de instalación, paso a paso y con cómo comprobar cada paso, está en
[`INSTALAR.md`](INSTALAR.md).** Lo corto, en un equipo con el repo ya clonado:

```sh
./instalar.sh                 # lo de siempre (deja la app y su servicio, apagado)
./instalar.sh --remoto-todo   # paquetes, Tailscale y lo de tras reiniciar (pide sudo)
remoto/app/compilar.sh        # la app del celular (hace falta el SDK de Android)
celiuz-remoto revisar         # ¿qué falta todavía?
```

Y después, la ventana «Celiuz Remoto»: encender el servicio, conectar el
celular por cable, instalar la app y emparejar.

Una app Android para manejar tu PC o tu laptop desde cualquier sitio: ver su
estado en tiempo real, apagarla, ver y cerrar sus apps, sacar archivos y abrir
una terminal. Se instala en el celular por cable, desde la propia PC, y habla
con ella solo por Tailscale.

**Viene apagado.** Instalar el repo no lo enciende: se activa a mano desde la
PC, porque abrir un botón de «apagar» hacia fuera es decisión de cada uno.

| Fichero | Qué cuenta |
|---|---|
| [`DISEÑO.md`](DISEÑO.md) | qué hace, qué pide cada cosa y por qué (léelo primero) |
| [`PROTOCOLO.md`](PROTOCOLO.md) | lo que se dicen la app y el servidor |

| Carpeta | Qué es |
|---|---|
| `servidor/` | el servicio de la PC (Python) |
| `escritorio/` | la app de la PC para emparejar, dar permisos y revocar (GTK) |
| `app/` | la app del celular (React Native + Expo; `app/modules/celiuz-nativo`: guardar en la galería/Descargas y abrir con otras apps) |
| `sistema/` | lo único que corre como root: entrar desde SDDM y la regla de polkit (se COPIA, no se ejecuta desde aquí) |

## Para desarrollar

```sh
remoto/servidor/celiuz-remoto.py --help
remoto/servidor/celiuz-remoto.py servir           # el servicio, en primer plano
./tests/run.sh remoto                            # sus pruebas (unidad y punta a punta)
celiuz-remoto-config                             # la ventana de la PC
celiuz-remoto celulares                          # lo que hay conectado por cable
cd remoto/app && npm install && npx expo start     # la app, en modo desarrollo
```
