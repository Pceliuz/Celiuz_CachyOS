// Bajar archivos de la PC al celular, y abrirlos (fase 6).
//
// La copia vive en la carpeta de la app (Paths.document/descargas/<equipo>/<ruta
// de la PC>), no en Descargas de Android: así no hace falta ningún permiso de
// almacenamiento, y la app sabe sola qué tiene ya bajado (Recientes: «Abrir
// copia»). Para llevarla a otro sitio está «Compartir» (Drive, Archivos,
// WhatsApp...), y «Abrir» se la da a la app que toque por su tipo.
//
// Se baja primero a «<nombre>.parcial» y solo al acabar se cambia por la copia:
// una descarga cortada (sin red, sesión caducada) no estropea la que ya había.
import { Directory, File, Paths } from 'expo-file-system';
import { getContentUriAsync } from 'expo-file-system/legacy';
import * as IntentLauncher from 'expo-intent-launcher';
import * as Sharing from 'expo-sharing';

import type { Conexion } from './api/cliente';
import { mime, rutaLocal } from './archivos';

const RAIZ = 'descargas';

export function copia(conexion: Conexion, ruta: string): File {
  return new File(Paths.document, RAIZ, ...rutaLocal(conexion.equipo.equipo, ruta));
}

export function tieneCopia(conexion: Conexion, ruta: string): boolean {
  try {
    return copia(conexion, ruta).exists;
  } catch {
    return false;
  }
}

export interface Progreso { bajado: number; total: number }

// Devuelve la copia ya en su sitio. Lanza si falla (y deja la vieja intacta).
export async function bajar(conexion: Conexion, ruta: string, alProgreso?: (p: Progreso) => void,
                            senal?: AbortSignal): Promise<File> {
  const destino = copia(conexion, ruta);
  destino.parentDirectory.create({ intermediates: true, idempotent: true });
  const parcial = new File(destino.parentDirectory, `${destino.name}.parcial`);
  if (parcial.exists) parcial.delete();
  const tarea = File.createDownloadTask(conexion.urlDescarga(ruta), parcial, {
    headers: conexion.cabeceras(),
    onProgress: ({ bytesWritten, totalBytes }) => alProgreso?.({ bajado: bytesWritten, total: totalBytes }),
    signal: senal,
  });
  let hecho: File | null = null;
  try {
    hecho = await tarea.downloadAsync();
  } catch (e) {
    if (parcial.exists) parcial.delete();
    throw e;
  }
  if (!hecho || !parcial.exists) throw new Error('La descarga no terminó.');
  await parcial.move(destino, { overwrite: true });
  return destino;
}

export function borrarCopia(conexion: Conexion, ruta: string): void {
  const f = copia(conexion, ruta);
  if (f.exists) f.delete();
}

// Con la app que le toque por su tipo. Android pide un content:// (un file://
// de la carpeta de la app no se puede pasar a otra app).
export async function abrir(f: File): Promise<void> {
  const uri = await getContentUriAsync(f.uri);
  await IntentLauncher.startActivityAsync('android.intent.action.VIEW', {
    data: uri,
    type: mime(f.name),
    flags: 1, // FLAG_GRANT_READ_URI_PERMISSION
  });
}

export async function compartir(f: File): Promise<void> {
  await Sharing.shareAsync(f.uri, { mimeType: mime(f.name), dialogTitle: f.name });
}

// Lo que ocupa todo lo bajado, para enseñarlo y poder vaciarlo.
export function carpetaDescargas(): Directory {
  return new Directory(Paths.document, RAIZ);
}
