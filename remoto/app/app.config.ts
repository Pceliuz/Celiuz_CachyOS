// La config de Expo. Es .ts y no app.json para que el fondo del icono salga
// de la paleta generada (src/colores.json, de hypr/conf/colores.conf) y no de
// un violeta copiado a mano.
import type { ExpoConfig } from 'expo/config';

import paleta from './src/colores.json';

const config: ExpoConfig = {
  name: 'Celiuz Remoto',
  slug: 'celiuz-remoto',
  version: '0.1.0',
  orientation: 'portrait',
  icon: './assets/icon.png',
  userInterfaceStyle: 'dark',
  // celiuzremoto://emparejar/<codigo>: por donde la app de la PC le pasa el
  // codigo del canal USB (remoto/PROTOCOLO.md, «USB»).
  scheme: 'celiuzremoto',
  platforms: ['android'],
  plugins: [
    // HTTP sin TLS: Android lo bloquea de fabrica, y aqui hace falta porque la
    // app solo habla por Tailscale (WireGuard ya cifra y autentica) o por el
    // canal USB (127.0.0.1). remoto/PROTOCOLO.md, «Dónde escucha».
    ['expo-build-properties', { android: { usesCleartextTraffic: true } }],
    // Las claves del almacen seguro no van a la copia de Google: restauradas
    // en otro celular no valdrian (el Keystore no viaja) y no deben salir.
    ['expo-secure-store', { configureAndroidBackup: true }],
  ],
  android: {
    package: 'com.celiuz.remoto',
    versionCode: 1,
    allowBackup: false,
    adaptiveIcon: {
      backgroundColor: paleta.colores.abismo,
      foregroundImage: './assets/android-icon-foreground.png',
      backgroundImage: './assets/android-icon-background.png',
      monochromeImage: './assets/android-icon-monochrome.png',
    },
    predictiveBackGestureEnabled: false,
  },
};

export default config;
