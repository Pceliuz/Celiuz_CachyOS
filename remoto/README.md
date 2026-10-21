# Celiuz Remoto

> **Las 8 fases hechas** (2026-10-21): estado, apagar, apps, vigilancia, entrar
> tras un reinicio, archivos (que se guardan en la galería o en Descargas del
> celular), terminal, subir a la PC, ver y manejar la pantalla, despertar desde
> otro equipo y ayudar a un amigo sin cable. Qué está probado de verdad y qué
> no, en [`DISEÑO.md`](DISEÑO.md#fases).

## Para empezar

> **Al clonar el repo en un equipo nuevo, antes de abrir la app**: no vayas
> instalando lo que falta de uno en uno. Desde la carpeta del repo, una sola vez:
>
> ```sh
> ./instalar.sh                # lo de siempre (deja la app y su servicio, apagado)
> ./instalar.sh --remoto-todo  # TODO lo del remoto de una vez (pide sudo)
> ```
>
> `--remoto-todo` instala todos los paquetes (`celiuz-remoto.py paquetes`: los
> del servidor, los opcionales —miniaturas, ver la pantalla— y Java 17 y node
> para compilar la app), enciende Tailscale y te pide iniciar sesión en él si
> aún no lo hiciste (sale un enlace para el navegador), y deja lo de apagar y
> entrar tras un reinicio (lo mismo que `--remoto-sistema`). Se puede repetir:
> no reinstala lo que ya está. Lo único que no pone es el **SDK de Android**,
> que no viene en los repos (Android Studio, en `~/Android/Sdk`).
>
> Si algo falta igual, la ventana de Celiuz Remoto lo dice arriba, con ese
> mismo comando; y `celiuz-remoto revisar` lo dice en la terminal.

1. `remoto/app/compilar.sh` (una vez; pide Java 17 y el SDK de Android).
2. Abre «Celiuz Remoto» en la PC, enciende el servicio, conecta el celular por
   cable (con la «Depuración USB») e instala la app desde ahí.
3. Crea la contraseña, elige qué puede hacer y pulsa «Emparejar».
4. En el celular, instala Tailscale y entra con **la misma cuenta** que la PC.
5. Para ver la pantalla desde el celular, da el permiso «Ver y manejar la
   pantalla» a ese celular (Permisos, en la ventana). Lo de quitar la parte de
   tras reiniciar: `./instalar.sh --remoto-sistema-quitar`.

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
