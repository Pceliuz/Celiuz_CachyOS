// Lo que comparten Archivos y Recientes: bajar con progreso, guardar en el
// celular (galería o Descargas: descargas.ts) y al acabar decir DÓNDE quedó y
// ofrecer Abrir o Compartir. Los textos se ven en la propia app (VisorTexto):
// no todo celular tiene una app para un .md. Los errores del servidor con
// salida propia (pase vencido, sesión caducada) se los pasa a quien llama.
//
// Devuelve también `visor`, el elemento del visor de texto: la pantalla lo
// pinta donde quiera (una vez).
import { useCallback, useState } from 'react';
import { Alert } from 'react-native';

import type { Conexion, ErrorRemoto } from '../api/cliente';
import * as d from '../descargas';
import VisorTexto from './VisorTexto';

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
  const [texto, setTexto] = useState<{ copia: d.Copia; texto: string } | null>(null);
  // Para que las pantallas se vuelvan a pintar al guardar (tieneCopia cambia).
  const [, setVersion] = useState(0);

  const fallo = useCallback((e: unknown, titulo: string) => {
    const r = porQue(e);
    if (r === 'pase') alVerPase();
    else if (r === 'sesion') alCaducar(true);
    else Alert.alert(titulo, r);
  }, [alVerPase, alCaducar]);

  const compartir = useCallback((c: d.Copia) => {
    d.compartir(c).catch((e) => fallo(e, 'No se pudo compartir'));
  }, [fallo]);

  const abrirFuera = useCallback(async (c: d.Copia) => {
    try {
      if (await d.abrir(c)) return;
      Alert.alert('Ninguna app lo abre', `El celular no tiene ninguna app para este tipo de archivo. Está guardado en ${c.carpeta}; puedes compartirlo.`,
        [{ text: 'Cerrar', style: 'cancel' }, { text: 'Compartir', onPress: () => compartir(c) }]);
    } catch (e) {
      fallo(e, 'No se pudo abrir');
    }
  }, [compartir, fallo]);

  // Abrir: los textos en la app; lo demás con la app del celular.
  const abrir = useCallback(async (c: d.Copia) => {
    if (d.esTexto(c.nombre)) {
      try {
        setTexto({ copia: c, texto: await d.leerTexto(c) });
        return;
      } catch {
        /* si no se puede leer, que lo intente otra app */
      }
    }
    abrirFuera(c);
  }, [abrirFuera]);

  const ofrecer = useCallback((c: d.Copia) => {
    Alert.alert(c.nombre, `Guardado en el celular, en ${c.carpeta}.`, [
      { text: 'Cerrar', style: 'cancel' },
      { text: 'Compartir', onPress: () => compartir(c) },
      { text: 'Abrir', onPress: () => abrir(c) },
    ]);
  }, [abrir, compartir]);

  const bajar = useCallback(async (ruta: string, avisar = true) => {
    if (progreso[ruta] !== undefined) return null;
    setProgreso((p) => ({ ...p, [ruta]: 0 }));
    try {
      const c = await d.bajar(conexion, ruta, ({ bajado, total }) =>
        setProgreso((p) => ({ ...p, [ruta]: total > 0 ? bajado / total : -1 })));
      setVersion((v) => v + 1);
      if (avisar) ofrecer(c);
      return c;
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
    const c = d.copia(conexion, ruta);
    if (c) abrir(c);
    else Alert.alert('No hay copia', 'Este celular ya no lo tiene (o se borró de la galería o de Descargas).');
  }, [conexion, abrir]);

  const visor = (
    <VisorTexto nombre={texto?.copia.nombre ?? null} texto={texto?.texto ?? ''}
                cortado={(texto?.texto.length ?? 0) >= d.MAX_TEXTO}
                alCerrar={() => setTexto(null)}
                alAbrirFuera={() => texto && abrirFuera(texto.copia)}
                alCompartir={() => texto && compartir(texto.copia)} />
  );

  return { progreso, bajar, abrirCopia, tieneCopia: (ruta: string) => d.tieneCopia(conexion, ruta), fallo, visor };
}
