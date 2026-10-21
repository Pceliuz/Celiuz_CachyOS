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
  android: {
    package: 'com.celiuz.remoto',
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
