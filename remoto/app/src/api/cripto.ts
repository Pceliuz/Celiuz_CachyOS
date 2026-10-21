// Las claves del celular: un par Ed25519 POR EQUIPO (PC, laptop...). La
// privada no sale nunca de aqui; a la PC solo le llega la publica, al
// emparejar (remoto/PROTOCOLO.md, «Las llaves»).
//
// TypeScript puro, sin React Native: las pruebas lo ejecutan con Node contra el
// servidor de verdad (tests/e2e/remoto-app.sh), que es lo que demuestra que una
// firma hecha aqui la acepta la PC.
//
// El azar NO lo saca esta libreria: Hermes no trae crypto.getRandomValues, y se
// lo pasa quien llama (expo-crypto en el celular, node:crypto en las pruebas).
import * as ed from '@noble/ed25519';
import { sha512 } from '@noble/hashes/sha2.js';

import { textoFirmado, type Firmable } from './protocolo.ts';

ed.hashes.sha512 = sha512;

export type Azar = (n: number) => Uint8Array;

const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

// Base64 a mano: btoa/atob trabajan con «cadenas binarias» y Buffer no existe
// en React Native. Son veinte lineas y no dependen de nadie.
export function aBase64(bytes: Uint8Array): string {
  let s = '';
  for (let i = 0; i < bytes.length; i += 3) {
    const n = (bytes[i] << 16) | ((bytes[i + 1] ?? 0) << 8) | (bytes[i + 2] ?? 0);
    s += B64[(n >> 18) & 63] + B64[(n >> 12) & 63];
    s += i + 1 < bytes.length ? B64[(n >> 6) & 63] : '=';
    s += i + 2 < bytes.length ? B64[n & 63] : '=';
  }
  return s;
}

export function deBase64(texto: string): Uint8Array {
  const limpio = texto.replace(/-/g, '+').replace(/_/g, '/').replace(/=+$/, '');
  const salida: number[] = [];
  let buf = 0;
  let bits = 0;
  for (const c of limpio) {
    const v = B64.indexOf(c);
    if (v < 0) throw new Error('base64 no válido');
    buf = (buf << 6) | v;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      salida.push((buf >> bits) & 255);
    }
  }
  return new Uint8Array(salida);
}

export function nuevaClave(azar: Azar): string {
  const secreto = azar(32);
  if (secreto.length !== 32) throw new Error('el azar no dio 32 bytes');
  return aBase64(secreto);
}

export function publica(clave: string): string {
  return aBase64(ed.getPublicKey(deBase64(clave)));
}

export function firmar(clave: string, para: Firmable, dato: string): string {
  const mensaje = new TextEncoder().encode(textoFirmado(para, dato));
  return aBase64(ed.sign(mensaje, deBase64(clave)));
}
