# La app del celular

React Native con **Expo** (SDK 58) y TypeScript. Solo Android.

```
App.tsx              arranque (por ahora, una pantalla de «en construcción»)
src/paleta.ts        los colores, de src/colores.json (lo genera gen-colores.py: no se edita)
src/api/             todo lo que habla con la PC; protocolo.ts = PROTOCOLO.md en tipos
src/pantallas/       una por maqueta: Entrar, Inicio, Apps, Apagar, Archivos,
                     Recientes, Terminal, PaseVencido
src/componentes/     lo que se repite (tarjetas, menú de abajo, botones)
```

## Reglas

- **Se compila en la PC**, nunca en la nube de Expo (EAS): `npx expo run:android`
  o el APK de release con Gradle. Lo instala la app de la PC por cable.
- Las dependencias se añaden con `npx expo install <paquete>`, no con
  `npm install`: elige la versión que va con el SDK.
- `android/` lo genera Expo (`npx expo prebuild`) y no se versiona ni se edita a
  mano: lo nativo se configura en `app.config.ts` y con plugins.
- La clave de firma del APK vive en `~/.config/celiuz/remoto/firma.keystore`,
  nunca aquí.
- Expo cambia mucho entre versiones: antes de usar una API, la documentación de
  **esa** versión (`https://docs.expo.dev/versions/v58.0.0/`).
- Antes de dar algo por terminado: `npm run typecheck`.

## Lo que hará falta (fase 3)

| Para | Módulo de Expo |
|---|---|
| guardar la clave del teléfono | `expo-secure-store` (almacén seguro de Android) |
| la huella | `expo-local-authentication` |
| el latido con la app cerrada y el aviso de apagado | módulo nativo propio (servicio en primer plano + `ACTION_SHUTDOWN`) |
| descargas | `expo-file-system` |
| la terminal | `@xterm/xterm` en un `react-native-webview` |
