// Recientes y favoritos (pantalla 6 de las maquetas). La lista vive EN LA PC
// (historial.py): si cambias de celular la conservas, y si te lo roban no se
// llevan la lista. Cada reciente dice cómo está contra la PC («igual», «hay
// versión nueva», «ya no está»), y si este celular tiene la copia se abre aquí.
import { useCallback, useEffect, useState } from 'react';
import { Alert, Pressable, RefreshControl, ScrollView, View } from 'react-native';

import { ErrorRemoto, type Conexion } from '../api/cliente';
import type { Favorito, Reciente } from '../api/protocolo';
import { TEXTO_ESTADO, agrupar, tamano } from '../archivos';
import * as f from '../formato';
import { colores } from '../paleta';
import IconoArchivo from '../componentes/IconoArchivo';
import { useDescargas } from '../componentes/useDescargas';
import { Aviso, Barra, Boton, Pantalla, Tarjeta, Texto, alfa, fondoRojo } from '../componentes/ui';

const COLOR_ESTADO: Record<Reciente['estado'], string> = {
  igual: colores.exito, nueva_version: colores.atencion, no_esta: colores.alerta,
};

export default function Recientes({ conexion, alVolver, alAbrirCarpeta, alVerPase, alCaducar }: {
  conexion: Conexion;
  alVolver: () => void;
  alAbrirCarpeta: (ruta: string) => void;
  alVerPase: () => void;
  alCaducar: (sesionCaducada: boolean) => void;
}) {
  const [vista, setVista] = useState<'recientes' | 'favoritos'>('recientes');
  const [recientes, setRecientes] = useState<Reciente[] | null>(null);
  const [favoritos, setFavoritos] = useState<Favorito[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const descargas = useDescargas(conexion, { alVerPase, alCaducar });
  const ahora = new Date();

  const tratar = useCallback((e: unknown) => {
    const err = e as ErrorRemoto;
    if (err.codigo === 'sin_sesion') return alCaducar(true);
    if (err.codigo === 'pase_vencido') return alVerPase();
    setError(err.message);
  }, [alCaducar, alVerPase]);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const [r, fav] = await Promise.all([conexion.recientes(), conexion.favoritos()]);
      setRecientes(r);
      setFavoritos(fav);
      setError(null);
    } catch (e) {
      tratar(e);
    } finally {
      setCargando(false);
    }
  }, [conexion, tratar]);

  useEffect(() => { cargar(); }, [cargar]);

  async function bajar(ruta: string) {
    if (await descargas.bajar(ruta)) cargar();
  }

  function olvidar(r: Reciente) {
    Alert.alert('¿Quitar de Recientes?', `«${r.nombre}» sale de la lista. El archivo no se toca, ni en la PC ni en el celular.`, [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Quitar', onPress: () => conexion.olvidarReciente(r.ruta).then(cargar, tratar) },
    ]);
  }

  async function soltar(fav: Favorito) {
    try {
      setFavoritos(await conexion.soltar(fav.ruta));
    } catch (e) {
      tratar(e);
    }
  }

  function boton(r: Reciente) {
    const copia = descargas.tieneCopia(r.ruta);
    const p = descargas.progreso[r.ruta];
    if (p !== undefined) return <View style={{ flex: 1 }}><Barra valor={p < 0 ? 0.5 : p} /></View>;
    if (r.estado === 'nueva_version') return <Boton texto="Bajar otra vez" alto={44} alPulsar={() => bajar(r.ruta)} />;
    if (copia) return <Boton texto={r.estado === 'no_esta' ? 'Abrir copia' : 'Abrir'} tipo="borde" alto={44}
                             alPulsar={() => descargas.abrirCopia(r.ruta)} />;
    if (r.estado === 'igual') return <Boton texto="Bajar" tipo="borde" alto={44} alPulsar={() => bajar(r.ruta)} />;
    return null;
  }

  return (
    <Pantalla relleno={false}>
      <View style={{ paddingHorizontal: 20, paddingTop: 20, paddingBottom: 12, gap: 14 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <Pressable accessibilityRole="button" accessibilityLabel="Volver a Archivos" onPress={alVolver}
                     style={{ width: 44, height: 44, borderRadius: 12, borderWidth: 1, borderColor: colores.apagado,
                              alignItems: 'center', justifyContent: 'center' }}>
            <Texto tipo="grande">‹</Texto>
          </Pressable>
          <Texto tipo="grande">Lo que ya bajaste</Texto>
        </View>
        <View style={{ flexDirection: 'row', backgroundColor: colores.superficie, borderRadius: 12, padding: 4, gap: 4 }}>
          {(['recientes', 'favoritos'] as const).map((v) => (
            <Pressable key={v} accessibilityRole="tab" accessibilityState={{ selected: vista === v }} onPress={() => setVista(v)}
                       style={{ flex: 1, height: 40, borderRadius: 9, alignItems: 'center', justifyContent: 'center',
                                backgroundColor: vista === v ? colores.apagado : undefined }}>
              <Texto tipo="chico" color={vista === v ? colores.luz : colores.tenue}>
                {v === 'recientes' ? 'Recientes' : `Favoritos${favoritos ? ` · ${favoritos.length}` : ''}`}
              </Texto>
            </Pressable>
          ))}
        </View>
        {error ? <Aviso texto={error} color={colores.alerta} fondo={fondoRojo} /> : null}
      </View>

      <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 20, gap: 10, flexGrow: 1 }}
                  refreshControl={<RefreshControl refreshing={cargando && recientes !== null} onRefresh={cargar}
                                                  tintColor={colores.amatista} colors={[colores.amatista]} />}>
        {vista === 'recientes' ? (
          <>
            {recientes?.length === 0 ? <Tarjeta><Texto color={colores.tenue}>Todavía no has bajado nada.</Texto></Tarjeta> : null}
            {agrupar(recientes ?? [], ahora).map(({ grupo, recientes: lista }) => (
              <View key={grupo} style={{ gap: 10 }}>
                <Texto tipo="etiqueta">{grupo}</Texto>
                {lista.map((r) => (
                  <Pressable key={r.ruta} onLongPress={() => olvidar(r)} accessibilityHint="Mantén pulsado para quitarlo de la lista">
                    <Tarjeta estilo={{ gap: 10, borderColor: r.estado === 'nueva_version' ? colores.atencion : colores.apagado }}>
                      <Texto lineas={2}>{r.nombre}</Texto>
                      <Texto tipo="chico" lineas={1}>
                        {`${r.carpeta || 'Inicio'} · bajado ${grupo === 'Hoy' ? `a las ${f.horaDe(r.bajado)}` : f.diaDe(r.bajado, ahora)} · ${tamano(r.tamano)}`}
                      </Texto>
                      <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
                        <View style={{ borderRadius: 999, paddingHorizontal: 9, paddingVertical: 5,
                                       backgroundColor: alfa(COLOR_ESTADO[r.estado], 0.16) }}>
                          <Texto tipo="chico" color={COLOR_ESTADO[r.estado]}>{TEXTO_ESTADO[r.estado]}</Texto>
                        </View>
                        <View style={{ marginLeft: 'auto', minWidth: 120 }}>{boton(r)}</View>
                      </View>
                    </Tarjeta>
                  </Pressable>
                ))}
              </View>
            ))}
          </>
        ) : (
          <>
            {favoritos?.length === 0 ? (
              <Tarjeta><Texto color={colores.tenue}>Sin favoritos. En Archivos, elige uno y pulsa «Favorito».</Texto></Tarjeta>
            ) : null}
            {favoritos?.map((fav) => (
              <Tarjeta key={fav.ruta} estilo={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12 }}>
                <IconoArchivo conexion={conexion} ruta={fav.ruta} nombre={fav.nombre} tipo={fav.tipo} />
                <Pressable accessibilityRole="button" style={{ flex: 1, gap: 3, minHeight: 44, justifyContent: 'center' }}
                           disabled={!fav.existe}
                           onPress={() => (fav.tipo === 'carpeta' ? alAbrirCarpeta(fav.ruta)
                             : descargas.tieneCopia(fav.ruta) ? descargas.abrirCopia(fav.ruta) : bajar(fav.ruta))}>
                  <Texto lineas={1}>{fav.nombre}</Texto>
                  <Texto tipo="chico" lineas={1} color={fav.existe ? colores.tenue : colores.alerta}>
                    {fav.existe ? (fav.ruta.includes('/') ? fav.ruta.slice(0, fav.ruta.lastIndexOf('/')) : 'Inicio') : 'Ya no está en la PC'}
                  </Texto>
                  {descargas.progreso[fav.ruta] !== undefined ? <Barra valor={Math.max(0, descargas.progreso[fav.ruta])} /> : null}
                </Pressable>
                <Pressable accessibilityRole="button" accessibilityLabel={`Quitar ${fav.nombre} de favoritos`}
                           onPress={() => soltar(fav)}
                           style={{ minWidth: 44, minHeight: 44, alignItems: 'center', justifyContent: 'center' }}>
                  <Texto tipo="chico" color={colores.neon}>Quitar</Texto>
                </Pressable>
              </Tarjeta>
            ))}
          </>
        )}
        <Texto tipo="chico">El historial vive en la PC, no en el celular: si cambias de celular lo conservas, y si te lo roban no se llevan la lista.</Texto>
      </ScrollView>
    </Pantalla>
  );
}
