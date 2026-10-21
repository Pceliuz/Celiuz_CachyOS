// Lo que comparten Archivos y Recientes: bajar con progreso, y al acabar
// ofrecer Abrir o Compartir. Los errores del servidor que tienen salida propia
// (pase vencido, sesión caducada) se los pasa a quien llama.
import { useCallback, useState } from 'react';
import { Alert } from 'react-native';

import type { Conexion, ErrorRemoto } from '../api/cliente';
import * as d from '../descargas';

export interface Errores {
  alVerPase: () => void;
  alCaducar: (sesionCaducada: boolean) => void;
}

// Cuando la descarga la corta el servidor, expo-file-system no trae el cuerpo
// del error: solo el código HTTP en el mensaje. Se traduce lo que importa.
function porQue(e: unknown): 'pase' | 'sesion' | string {
  const m = String((e as Error)?.message ?? e);
  if ((e as ErrorRemoto)?.codigo === 'pase_vencido' || /\b423\b/.test(m)) return 'pase';
  if ((e as ErrorRemoto)?.codigo === 'sin_sesion' || /\b401\b/.test(m)) return 'sesion';
  if (/\b403\b/.test(m)) return 'Ese archivo no se puede sacar desde el celular.';
  if (/\b404\b/.test(m)) return 'Ya no está en la PC.';
  return m;
}

export function useDescargas(conexion: Conexion, { alVerPase, alCaducar }: Errores) {
  // ruta -> fracción bajada (0..1), o -1 si no se sabe el total
  const [progreso, setProgreso] = useState<Record<string, number>>({});

  const fallo = useCallback((e: unknown, titulo: string) => {
    const r = porQue(e);
    if (r === 'pase') alVerPase();
    else if (r === 'sesion') alCaducar(true);
    else Alert.alert(titulo, r);
  }, [alVerPase, alCaducar]);

  const ofrecer = useCallback((f: ReturnType<typeof d.copia>) => {
    Alert.alert(f.name, 'Ya está en el celular.', [
      { text: 'Cerrar', style: 'cancel' },
      { text: 'Compartir', onPress: () => d.compartir(f).catch((e) => fallo(e, 'No se pudo compartir')) },
      { text: 'Abrir', onPress: () => d.abrir(f).catch(() => Alert.alert(
        'Ninguna app lo abre', 'No hay ninguna app en el celular para este tipo de archivo. Prueba con Compartir.')) },
    ]);
  }, [fallo]);

  const bajar = useCallback(async (ruta: string, avisar = true) => {
    if (progreso[ruta] !== undefined) return null;
    setProgreso((p) => ({ ...p, [ruta]: 0 }));
    try {
      const f = await d.bajar(conexion, ruta, ({ bajado, total }) =>
        setProgreso((p) => ({ ...p, [ruta]: total > 0 ? bajado / total : -1 })));
      if (avisar) ofrecer(f);
      return f;
    } catch (e) {
      fallo(e, 'No se pudo bajar');
      return null;
    } finally {
      setProgreso((p) => {
        const { [ruta]: _, ...resto } = p;
        return resto;
      });
    }
  }, [conexion, progreso, ofrecer, fallo]);

  const abrirCopia = useCallback((ruta: string) => {
    const f = d.copia(conexion, ruta);
    if (f.exists) ofrecer(f);
    else Alert.alert('No hay copia', 'Este celular no lo tiene bajado.');
  }, [conexion, ofrecer]);

  return { progreso, bajar, abrirCopia, tieneCopia: (ruta: string) => d.tieneCopia(conexion, ruta), fallo };
}
