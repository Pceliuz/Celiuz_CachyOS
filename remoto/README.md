# Celiuz Remoto

> **En construcción.** Fases 1 y 2 de 8 hechas (2026-10-20): el servidor y la
> ventana de la PC («Celiuz Remoto» en el lanzador) ya están; falta la app del
> celular que los use. Las fases, en [`DISEÑO.md`](DISEÑO.md#fases).

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
| `app/` | la app del celular (React Native + Expo) |

## Para desarrollar

```sh
remoto/servidor/celiuz-remoto.py --help
remoto/servidor/celiuz-remoto.py servir           # el servicio, en primer plano
./tests/run.sh remoto                            # sus pruebas (unidad y punta a punta)
celiuz-remoto-config                             # la ventana de la PC
celiuz-remoto celulares                          # lo que hay conectado por cable
cd remoto/app && npm install && npx expo start     # la app, en modo desarrollo
```
