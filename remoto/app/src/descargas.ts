// Bajar archivos de la PC al celular, guardarlos donde los ven las demás apps,
// y abrirlos (fase 6).
//
// DÓNDE SE GUARDA. La primera versión lo dejaba en la carpeta privada de la
// app, y eso no le servía a nadie: Google Fotos enseñaba la foto pero no la
// tenía, el .docx se abría pero no aparecía en el explorador, el vídeo ni se
// reproducía (lo probó el usuario el 2026-10-20 en su HONOR). Ahora va a
// MediaStore, que es lo que ven TODAS las apps del celular, con el módulo
// nativo propio (modules/celiuz-nativo):
//   fotos  -> Pictures/Celiuz Remoto  (galería, Google Fotos)
//   vídeos -> Movies/Celiuz Remoto    (galería, Google Fotos)
//   música -> Music/Celiuz Remoto
//   el resto -> Download/Celiuz Remoto (Archivos, Descargas)
// No pide permisos desde Android 10; en Android 9 y antes pide el de escribir.
//
// Se baja primero a la caché de la app («.parcial») y solo al acabar se pasa a
// MediaStore: una descarga cortada no deja medio vídeo en la galería. «Bajar
// otra vez» SUSTITUYE la copia anterior (si la persona no la borró), en vez de
// dejar «nota (1).docx».
//
// La app apunta qué guardó y dónde (Paths.document/guardados.json): así sabe
// «Abrir copia» en Recientes, y si la persona borró la foto de la galería, lo
// nota (`nativo.existe`) y deja de ofrecerla.
import { File, Paths } from 'expo-file-system';
import { PermissionsAndroid, Platform } from 'react-native';

import nativo, { disponible, type Guardado } from '../modules/celiuz-nativo';
import type { Conexion } from './api/cliente';
import { clase, claveGuardado, decidirVideo, type DecisionVideo, esTexto, mime } from './archivos';

export interface Copia extends Guardado {
  nombre: string;
  mime: string;
  bajado: string; // ISO, con el reloj del celular
}

const INDICE = () => new File(Paths.document, 'guardados.json');

function leerIndice(): Record<string, Copia> {
  try {
    const f = INDICE();
    return f.exists ? JSON.parse(f.textSync()) : {};
  } catch {
    return {};
  }
}

function escribirIndice(i: Record<string, Copia>) {
  INDICE().write(JSON.stringify(i));
}

// La copia de ESTE archivo de ESTE equipo, si sigue en el celular.
export function copia(conexion: Conexion, ruta: string): Copia | null {
  const c = leerIndice()[claveGuardado(conexion.equipo.equipo, ruta)];
  if (!c || !disponible) return null;
  return nativo.existe(c.uri) ? c : null;
}

export const tieneCopia = (conexion: Conexion, ruta: string) => copia(conexion, ruta) !== null;

export interface Progreso { bajado: number; total: number }

async function permisoViejo() {
  // Android 9 y antes: sin este permiso no se puede escribir en Descargas.
  if (Platform.OS !== 'android' || Number(Platform.Version) >= 29) return;
  const r = await PermissionsAndroid.request(PermissionsAndroid.PERMISSIONS.WRITE_EXTERNAL_STORAGE);
  if (r !== PermissionsAndroid.RESULTS.GRANTED) {
    throw new Error('Sin el permiso de almacenamiento no puedo guardarlo en el celular.');
  }
}

// VÍDEOS QUE EL CELULAR NO REPRODUCE (2026-10-21): antes de bajar un vídeo se
// le pide a la PC su ficha y se le pregunta al decodificador del celular si
// puede con él. Si no, la PC lo convierte a lo que sí (conversion.py) y se
// baja eso. null: se baja tal cual (no es vídeo, o no se pudo saber: mejor
// bajar el original que no bajar nada).
export async function revisarVideo(conexion: Conexion, ruta: string): Promise<DecisionVideo | null> {
  if (!disponible || clase(ruta.split('/').pop() || '') !== 'video') return null;
  try {
    const f = await conexion.fichaVideo(ruta);
    return decidirVideo(f, (m, w, h, r) => nativo.puedeVideo(m, w, h, r), (m) => nativo.puedeAudio(m));
  } catch {
    return null;
  }
}

export interface Convertido { id: string; nombre: string }

// Pide la conversión y espera a que acabe, preguntando cada segundo (que es lo
// que la mantiene viva en la PC). Con la señal abortada, la cancela en la PC.
export async function convertir(conexion: Conexion, ruta: string, lado: number, fps: number,
                                alProgreso?: (fraccion: number) => void, senal?: AbortSignal): Promise<Convertido> {
  let c = await conexion.convertir(ruta, lado, fps);
  while (c.estado === 'en_cola' || c.estado === 'convirtiendo') {
    alProgreso?.(c.progreso);
    await new Promise((r) => setTimeout(r, 1000));
    if (senal?.aborted) {
      await conexion.cancelarConversion(c.id).catch(() => undefined);
      throw new Error('Cancelada.');
    }
    c = await conexion.conversion(c.id);
  }
  if (c.estado !== 'listo') throw new Error(c.mensaje || 'La PC no pudo convertirlo.');
  return { id: c.id, nombre: c.nombre };
}

// Baja, guarda en público y devuelve dónde quedó. Lanza si falla. Con
// `convertido`, baja la versión convertida (y la guarda con su nombre).
export async function bajar(conexion: Conexion, ruta: string, alProgreso?: (p: Progreso) => void,
                            senal?: AbortSignal, convertido?: Convertido): Promise<Copia> {
  if (!disponible) throw new Error('Esta versión de la app no sabe guardar archivos: vuelve a instalarla desde la PC.');
  await permisoViejo();
  const nombre = convertido?.nombre ?? (ruta.split('/').pop() || 'archivo');
  const parcial = new File(Paths.cache, `bajando-${Date.now()}.parcial`);
  const tarea = File.createDownloadTask(conexion.urlDescarga(ruta, convertido?.id), parcial, {
    headers: conexion.cabeceras(),
    onProgress: ({ bytesWritten, totalBytes }) => alProgreso?.({ bajado: bytesWritten, total: totalBytes }),
    signal: senal,
  });
  try {
    const hecho = await tarea.downloadAsync();
    if (!hecho || !parcial.exists) throw new Error('La descarga no terminó.');
    const clave = claveGuardado(conexion.equipo.equipo, ruta);
    const indice = leerIndice();
    // Se sustituye la copia anterior solo si se llama igual: el original y la
    // versión convertida son dos archivos distintos en la galería.
    const anterior = indice[clave]?.nombre === nombre ? indice[clave].uri : null;
    const tipo = mime(nombre);
    const g = await nativo.guardarPublico(parcial.uri, nombre, tipo, anterior);
    const c: Copia = { ...g, nombre, mime: tipo, bajado: new Date().toISOString() };
    indice[clave] = c;
    escribirIndice(indice);
    return c;
  } finally {
    if (parcial.exists) parcial.delete();
  }
}

// Con la app que tenga el celular para ese tipo. false si no hay ninguna.
export async function abrir(c: Copia): Promise<boolean> {
  return nativo.abrir(c.uri, c.mime);
}

export async function compartir(c: Copia): Promise<void> {
  await nativo.compartir(c.uri, c.mime, c.nombre);
}

// Para el visor de texto de la app: lo que cabe en 1 MB.
export const MAX_TEXTO = 1024 * 1024;
export async function leerTexto(c: Copia): Promise<string> {
  return nativo.leerTexto(c.uri, MAX_TEXTO);
}

export { esTexto };
