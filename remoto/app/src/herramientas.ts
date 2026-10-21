// fetch y WebSocket de React Native para el cliente del protocolo
// (api/cliente.ts los recibe inyectados, y asi las pruebas usan los de Node).
import { getRandomBytes } from 'expo-crypto';

import type { Herramientas, Socket } from './api/cliente.ts';

export const herramientas: Herramientas = {
  fetch: (...args) => fetch(...args),
  // React Native acepta cabeceras en el TERCER argumento (no es estandar).
  abrirSocket: (url, cabeceras) =>
    new (WebSocket as any)(url, null, { headers: cabeceras }) as Socket,
};

// El azar para las claves, del generador del sistema (Hermes no trae
// crypto.getRandomValues).
export const azar = (n: number) => getRandomBytes(n);
