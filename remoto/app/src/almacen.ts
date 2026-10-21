// Lo que el celular guarda, en el almacen seguro de Android (expo-secure-store,
// cifrado con el Keystore del sistema):
//
//   equipos            la lista de equipos emparejados (sin secretos)
//   clave.<dispositivo> la clave privada Ed25519 de ESE equipo
//
// Una clave por equipo: emparejar la laptop no tiene por que saber nada de la
// clave de la PC, y revocar uno no toca al otro.
import * as SecureStore from 'expo-secure-store';

import type { EquipoGuardado } from './api/cliente.ts';

const LISTA = 'equipos';
const clave = (dispositivo: string) => `clave.${dispositivo.replace(/[^A-Za-z0-9._-]/g, '_')}`;

export async function equipos(): Promise<EquipoGuardado[]> {
  try {
    const texto = await SecureStore.getItemAsync(LISTA);
    const lista = texto ? JSON.parse(texto) : [];
    return Array.isArray(lista) ? lista : [];
  } catch {
    return [];
  }
}

async function guardarLista(lista: EquipoGuardado[]) {
  await SecureStore.setItemAsync(LISTA, JSON.stringify(lista));
}

// Emparejar otra vez con la misma PC (mismo nombre) sustituye al viejo: la PC
// tambien lo sustituye, y una entrada vieja ya no podria entrar.
export async function guardarEquipo(e: EquipoGuardado, privada: string) {
  const lista = await equipos();
  for (const viejo of lista.filter((x) => x.equipo === e.equipo && x.dispositivo !== e.dispositivo)) {
    await SecureStore.deleteItemAsync(clave(viejo.dispositivo));
  }
  await SecureStore.setItemAsync(clave(e.dispositivo), privada);
  await guardarLista([...lista.filter((x) => x.equipo !== e.equipo), e]);
}

export async function actualizarPase(dispositivo: string, paseHasta: string | null) {
  const lista = await equipos();
  await guardarLista(lista.map((x) => (x.dispositivo === dispositivo ? { ...x, pase_hasta: paseHasta } : x)));
}

export async function claveDe(dispositivo: string): Promise<string | null> {
  return SecureStore.getItemAsync(clave(dispositivo));
}

export async function olvidar(dispositivo: string) {
  await SecureStore.deleteItemAsync(clave(dispositivo));
  await guardarLista((await equipos()).filter((x) => x.dispositivo !== dispositivo));
}
