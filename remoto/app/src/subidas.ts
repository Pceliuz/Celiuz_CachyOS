// Subir archivos del celular a la PC (fase 8). Se eligen con el selector de
// Android (cualquier app: Galería, Archivos, Drive...), se copian a la caché de
// la app y se mandan tal cual. La PC los deja SIEMPRE en <Descargas>/Celiuz
// Remoto y nunca pisa nada (servidor: archivos.py, «subir»).
import * as DocumentPicker from 'expo-document-picker';
import { File, UploadType } from 'expo-file-system';

import type { Conexion } from './api/cliente';

export interface Subido { ruta: string; nombre: string; tamano: number }
export interface ProgresoSubida { nombre: string; enviado: number; total: number; cual: number; cuantos: number }

// null si la persona no eligió nada. Lanza con el mensaje de la PC si falla.
export async function elegirYSubir(conexion: Conexion, alProgreso: (p: ProgresoSubida) => void): Promise<Subido[] | null> {
  const r = await DocumentPicker.getDocumentAsync({ multiple: true, copyToCacheDirectory: true });
  if (r.canceled || !r.assets?.length) return null;
  const hechos: Subido[] = [];
  for (const [i, a] of r.assets.entries()) {
    const f = new File(a.uri);
    try {
      const tarea = f.createUploadTask(conexion.urlSubir(a.name), {
        httpMethod: 'POST',
        uploadType: UploadType.BINARY_CONTENT,
        mimeType: 'application/octet-stream',
        headers: { ...conexion.cabeceras(), 'Content-Type': 'application/octet-stream' },
        onProgress: ({ bytesSent, totalBytes }) =>
          alProgreso({ nombre: a.name, enviado: bytesSent, total: totalBytes, cual: i + 1, cuantos: r.assets.length }),
      });
      const res = await tarea.uploadAsync();
      if (!res) throw new Error('La subida se canceló.');
      let cuerpo: { ruta?: string; nombre?: string; tamano?: number; mensaje?: string; error?: string } = {};
      try { cuerpo = JSON.parse(res.body); } catch { /* sin JSON: se dice el código */ }
      if (res.status !== 200) {
        const e = new Error(cuerpo.mensaje ?? `La PC contestó ${res.status}.`) as Error & { codigo?: string };
        e.codigo = cuerpo.error;
        throw e;
      }
      hechos.push({ ruta: cuerpo.ruta!, nombre: cuerpo.nombre!, tamano: cuerpo.tamano! });
    } finally {
      try { if (f.exists) f.delete(); } catch { /* la caché se limpia sola */ }
    }
  }
  return hechos;
}
