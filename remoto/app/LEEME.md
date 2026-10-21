# La app del celular

React Native con **Expo** (SDK 58) y TypeScript. Solo Android.

```
App.tsx              arranque y navegación (sin librería: el estado decide la pantalla)
app.config.ts        la config de Expo (es .ts para leer la paleta generada)
compilar.sh          el APK, compilado y firmado EN ESTA PC
src/paleta.ts        los colores, de src/colores.json (lo genera gen-colores.py: no se edita)
src/api/             TypeScript PURO, sin React Native: lo prueban con Node contra el
  protocolo.ts         servidor de verdad (tests/e2e/remoto-app.sh)
  cripto.ts            las claves Ed25519, una por equipo
  cliente.ts           el protocolo: canal USB, entrar, estado en vivo
src/formato.ts       números y fechas en castellano (también puro)
src/almacen.ts       el almacén seguro de Android (equipos y sus claves)
src/herramientas.ts  fetch, WebSocket y el azar de React Native
src/pantallas/       Bienvenida, Cable (emparejar y renovar), Entrar, Inicio, PaseVencido
src/componentes/     lo que se repite (tarjetas, botones, campo, barra)
```

## Compilar e instalar

```sh
remoto/app/compilar.sh --revisar   # qué falta (Java 17, SDK de Android)
remoto/app/compilar.sh             # deja el APK en ~/.local/share/celiuz/remoto/
```

Y se instala desde la ventana de la PC («Celiuz Remoto» → «Instalar la app»),
con el celular por cable. La PC abre la app ella sola al emparejar.

## Reglas

- **Se compila en la PC**, nunca en la nube de Expo (EAS).
- **La lógica va en `src/api/` y `src/formato.ts`, sin React Native**: es lo que
  se prueba con Node contra el servidor de verdad. Las pantallas solo pintan.
  Esos ficheros se importan entre sí CON la extensión `.ts` (Node la exige).
- Las dependencias se añaden con `npx expo install <paquete>`, no con
  `npm install`: elige la versión que va con el SDK.
- `android/` lo genera Expo (`npx expo prebuild`) y no se versiona ni se edita a
  mano: lo nativo se configura en `app.config.ts` y con plugins.
- La clave de firma del APK vive en `~/.config/celiuz/remoto/firma.keystore`,
  nunca aquí. Si se pierde, hay que desinstalar la app y volver a emparejar.
- **Ningún color a mano**, tampoco un `rgba(...)`: los translúcidos se derivan
  con `alfa()` (`src/componentes/ui.tsx`). Lo vigila `tests/unidad/generados.sh`.
- Expo cambia mucho entre versiones: antes de usar una API, la documentación de
  **esa** versión (`https://docs.expo.dev/versions/v58.0.0/`).
- Antes de dar algo por terminado: `npm run typecheck` y
  `npx expo config --type public` (el typecheck no ve los fallos de la config).

## Trampas

- **Hermes no trae `crypto.getRandomValues`**: el azar de las claves sale de
  `expo-crypto`, y se le pasa a `cripto.ts` (que no lo busca solo).
- **El WebSocket de React Native lleva las cabeceras en el TERCER argumento**
  (`new WebSocket(url, null, { headers })`); el de Node, en un objeto de
  opciones. Por eso `cliente.ts` recibe quién lo abre.
- **Un `fetch` a una IP de Tailscale que no contesta se queda colgado un minuto**:
  todo lleva tiempo máximo (`ESPERA_MS`).
- **Android bloquea el HTTP sin TLS**: `usesCleartextTraffic` en `app.config.ts`.
  Es seguro aquí porque solo se habla por Tailscale (cifrado) o por el cable.
