// Archivos (pantalla 5 de las maquetas): el explorador de la carpeta personal
// de la PC. Todo pide el pase de 24 h; sin él, la pantalla lo dice y lleva a
// renovarlo. Solo lectura: se mira, se busca, se baja y se fija de favorito.
//
// Tocar una carpeta entra; tocar un archivo lo selecciona y abre abajo la
// tarjeta de Descargar / Ver / Favorito. «Atrás» sube de carpeta antes de salir
// de la pestaña (lo pide App.tsx con `fijarAtras`).
import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, FlatList, Image, Modal, Pressable, RefreshControl, ScrollView, TextInput, View } from 'react-native';

import { ErrorRemoto, type Conexion } from '../api/cliente';
import type { Entrada, Listado } from '../api/protocolo';
import { migas, padre, tamano, tieneMiniatura, unir } from '../archivos';
import { elegirYSubir, type ProgresoSubida } from '../subidas';
import * as f from '../formato';
import { colores } from '../paleta';
import IconoArchivo from '../componentes/IconoArchivo';
import Pestanas, { type Pestana } from '../componentes/Pestanas';
import { useDescargas } from '../componentes/useDescargas';
import { Aviso, Barra, Boton, Pantalla, Tarjeta, Texto, e as estilos, fondoRojo } from '../componentes/ui';

type Fila = Entrada & { ruta: string };

export default function Archivos({ conexion, inicial = '', alCambiar, alVerPase, alCaducar, alRecientes, fijarAtras }: {
  conexion: Conexion;
  inicial?: string;
  alCambiar: (p: Pestana) => void;
  alVerPase: () => void;
  alCaducar: (sesionCaducada: boolean) => void;
  alRecientes: () => void;
  fijarAtras: (fn: (() => boolean) | null) => void;
}) {
  const [ruta, setRuta] = useState(inicial);
  const [listado, setListado] = useState<Listado | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sinPase, setSinPase] = useState(false);
  const [cargando, setCargando] = useState(false);
  const [q, setQ] = useState('');
  const [resultados, setResultados] = useState<Fila[] | null>(null);
  const [elegido, setElegido] = useState<Fila | null>(null);
  const [visor, setVisor] = useState<Fila | null>(null);
  const ahora = new Date();
  const errores = { alVerPase, alCaducar };
  const descargas = useDescargas(conexion, errores);
  const [subiendo, setSubiendo] = useState<ProgresoSubida | null>(null);

  // Del celular a la PC (fase 8): siempre a Descargas/Celiuz Remoto.
  async function subir() {
    if (subiendo) return;
    setSubiendo({ nombre: '', enviado: 0, total: 0, cual: 0, cuantos: 0 });
    try {
      const hechos = await elegirYSubir(conexion, setSubiendo);
      if (!hechos) return;
      const carpeta = padre(hechos[0].ruta);
      Alert.alert(hechos.length === 1 ? `Subido «${hechos[0].nombre}»` : `Subidos ${hechos.length} archivos`,
        `Está en la PC, en ${carpeta}.`,
        [{ text: 'Cerrar', style: 'cancel' }, { text: 'Ver la carpeta', onPress: () => ir(carpeta) }]);
      if (carpeta === ruta) cargar(ruta);
    } catch (e) {
      const err = e as Error & { codigo?: string };
      if (err.codigo === 'pase_vencido') setSinPase(true);
      else if (err.codigo === 'sin_sesion') alCaducar(true);
      else Alert.alert('No se pudo subir', err.message);
    } finally {
      setSubiendo(null);
    }
  }

  const tratar = useCallback((e: unknown) => {
    const err = e as ErrorRemoto;
    if (err.codigo === 'sin_sesion') return alCaducar(true);
    if (err.codigo === 'pase_vencido') return setSinPase(true);
    setError(err.message);
  }, [alCaducar]);

  const cargar = useCallback(async (r: string) => {
    setCargando(true);
    try {
      const l = await conexion.archivos(r);
      setListado(l);
      setRuta(l.ruta);
      setError(null);
      setSinPase(false);
    } catch (e) {
      tratar(e);
    } finally {
      setCargando(false);
    }
  }, [conexion, tratar]);

  useEffect(() => { cargar(inicial); }, [cargar, inicial]);

  const ir = useCallback((r: string) => {
    setElegido(null);
    setResultados(null);
    setQ('');
    cargar(r);
  }, [cargar]);

  // Atrás: cerrar la búsqueda o la selección, y si no, subir de carpeta.
  const atras = useRef<() => boolean>(() => false);
  atras.current = () => {
    if (visor) { setVisor(null); return true; }
    if (elegido) { setElegido(null); return true; }
    if (resultados) { setResultados(null); setQ(''); return true; }
    if (ruta) { ir(padre(ruta)); return true; }
    return false;
  };
  useEffect(() => {
    fijarAtras(() => atras.current());
    return () => fijarAtras(null);
  }, [fijarAtras]);

  async function buscar() {
    if (q.trim().length < 2) return;
    setCargando(true);
    try {
      const b = await conexion.buscar(ruta, q.trim());
      setResultados(b.resultados);
      setElegido(null);
      if (b.truncado) setError('Hay más resultados de los que caben: afina la búsqueda.');
    } catch (e) {
      tratar(e);
    } finally {
      setCargando(false);
    }
  }

  async function alternarFavorito(fila: Fila) {
    try {
      if (fila.favorito) await conexion.soltar(fila.ruta);
      else await conexion.fijar(fila.ruta);
      const nuevo = { ...fila, favorito: !fila.favorito };
      setElegido(nuevo);
      setListado((l) => l && { ...l, entradas: l.entradas.map((x) => (x.nombre === fila.nombre && unir(l.ruta, x.nombre) === fila.ruta ? nuevo : x)) });
    } catch (e) {
      tratar(e);
    }
  }

  function ver(fila: Fila) {
    if (tieneMiniatura(fila.nombre)) setVisor(fila);
    else descargas.bajar(fila.ruta);   // lo que no es imagen se «ve» abriéndolo en el celular
  }

  if (sinPase) {
    return (
      <Pantalla relleno={false}>
        <View style={{ flex: 1, padding: 20, gap: 14, justifyContent: 'center' }}>
          <Texto tipo="grande">Archivos necesita el pase</Texto>
          <Texto color={colores.tenue}>Explorar y bajar archivos de la PC pide el pase de 24 h, que se renueva conectando el celular por cable.</Texto>
          <Boton texto="Cómo renovarlo" alPulsar={alVerPase} />
        </View>
        <Pestanas actual="archivos" permisos={conexion.sesion.permisos} alCambiar={alCambiar} />
      </Pantalla>
    );
  }

  const filas: Fila[] = resultados ?? (listado?.entradas ?? []).map((x) => ({ ...x, ruta: unir(listado!.ruta, x.nombre) }));
  const carpeta = migas(ruta, 'Inicio');

  return (
    <Pantalla relleno={false}>
      <View style={{ paddingHorizontal: 20, paddingTop: 20, paddingBottom: 8, gap: 12 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <View style={{ flex: 1 }}><Texto tipo="grande">Archivos</Texto></View>
          <Pressable accessibilityRole="button" onPress={subir} disabled={!!subiendo}
                     style={{ minHeight: 44, justifyContent: 'center', paddingHorizontal: 14, borderRadius: 999,
                              borderWidth: 1, borderColor: colores.apagado, opacity: subiendo ? 0.5 : 1 }}>
            <Texto tipo="chico" color={colores.neon}>Subir</Texto>
          </Pressable>
          <Pressable accessibilityRole="button" onPress={alRecientes}
                     style={{ minHeight: 44, justifyContent: 'center', paddingHorizontal: 14, borderRadius: 999,
                              borderWidth: 1, borderColor: colores.apagado }}>
            <Texto tipo="chico" color={colores.neon}>Recientes</Texto>
          </Pressable>
        </View>
        <TextInput accessibilityLabel="Buscar en la PC" value={q} onChangeText={setQ} onSubmitEditing={buscar}
                   placeholder={`Buscar en ${carpeta[carpeta.length - 1].nombre}…`} returnKeyType="search"
                   autoCapitalize="none" autoCorrect={false} placeholderTextColor={colores.tenue}
                   selectionColor={colores.neon} style={[estilos.campo, { height: 48, letterSpacing: 0, fontSize: 15 }]} />
        {resultados ? (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <View style={{ flex: 1 }}>
              <Texto tipo="chico">{`${resultados.length} con «${q}» en ${carpeta[carpeta.length - 1].nombre}`}</Texto>
            </View>
            <Pressable accessibilityRole="button" onPress={() => { setResultados(null); setQ(''); }}
                       style={{ minHeight: 44, justifyContent: 'center' }}>
              <Texto tipo="chico" color={colores.neon}>Quitar búsqueda</Texto>
            </Pressable>
          </View>
        ) : (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6, alignItems: 'center' }}>
            {carpeta.map((m, i) => (
              <View key={m.ruta} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                {i > 0 ? <Texto tipo="chico">›</Texto> : null}
                <Pressable accessibilityRole="button" onPress={() => ir(m.ruta)} style={{ minHeight: 36, justifyContent: 'center' }}>
                  <Texto tipo="chico" color={i === carpeta.length - 1 ? colores.luz : colores.tenue}>{m.nombre}</Texto>
                </Pressable>
              </View>
            ))}
          </ScrollView>
        )}
        {error ? <Aviso texto={error} color={colores.alerta} fondo={fondoRojo} /> : null}
        {subiendo && subiendo.cuantos > 0 ? (
          <Tarjeta estilo={{ gap: 8 }}>
            <Texto tipo="chico" lineas={1}>
              {`Subiendo ${subiendo.cuantos > 1 ? `${subiendo.cual} de ${subiendo.cuantos} · ` : ''}${subiendo.nombre}`}
            </Texto>
            <Barra valor={subiendo.total > 0 ? subiendo.enviado / subiendo.total : 0} />
          </Tarjeta>
        ) : null}
      </View>

      <FlatList
        data={filas}
        keyExtractor={(x) => x.ruta}
        contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 12 }}
        refreshControl={<RefreshControl refreshing={cargando && listado !== null} onRefresh={() => cargar(ruta)}
                                        tintColor={colores.amatista} colors={[colores.amatista]} />}
        ListEmptyComponent={
          <Tarjeta><Texto color={colores.tenue}>
            {listado === null && !error ? 'Preguntando a la PC…' : resultados ? 'Nada con ese nombre.' : 'Carpeta vacía.'}
          </Texto></Tarjeta>}
        ListFooterComponent={listado?.truncado && !resultados
          ? <Texto tipo="chico" centrado>Hay más de las que caben: busca por nombre.</Texto> : undefined}
        renderItem={({ item }) => {
          const marcado = elegido?.ruta === item.ruta;
          const p = descargas.progreso[item.ruta];
          const detalle = item.tipo === 'carpeta'
            ? `${item.elementos ?? '?'} elemento${item.elementos === 1 ? '' : 's'}`
            : `${tamano(item.tamano)} · ${f.diaDe(item.modificado, ahora)}`;
          return (
            <Pressable accessibilityRole="button" accessibilityState={{ selected: marcado }}
                       onPress={() => (item.tipo === 'carpeta' ? ir(item.ruta) : setElegido(marcado ? null : item))}
                       style={{ flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 10,
                                borderBottomWidth: 1, borderBottomColor: colores.superficie,
                                backgroundColor: marcado ? colores.superficie : undefined,
                                marginHorizontal: -20, paddingHorizontal: 20 }}>
              <IconoArchivo conexion={conexion} ruta={item.ruta} nombre={item.nombre} tipo={item.tipo} />
              <View style={{ flex: 1, gap: 3 }}>
                <Texto lineas={1}>{item.nombre}</Texto>
                <Texto tipo="chico" lineas={1}>
                  {resultados && item.ruta.includes('/') ? `${padre(item.ruta)} · ${detalle}` : detalle}
                  {item.favorito ? ' · favorito' : ''}
                  {item.tipo === 'archivo' && descargas.tieneCopia(item.ruta) ? ' · en el celular' : ''}
                </Texto>
                {p !== undefined ? <Barra valor={p < 0 ? 0.5 : p} /> : null}
              </View>
            </Pressable>
          );
        }}
      />

      {elegido ? (
        <View style={{ marginHorizontal: 14, marginBottom: 10, borderRadius: 18, backgroundColor: colores.superficie,
                       borderWidth: 1, borderColor: colores.amatista, padding: 14, gap: 12 }}>
          <Texto tipo="chico" lineas={1}>{`${elegido.nombre} · ${tamano(elegido.tamano)}`}</Texto>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <View style={{ flex: 1 }}>
              {descargas.tieneCopia(elegido.ruta) ? (
                <Boton texto="Abrir" alto={48} alPulsar={() => descargas.abrirCopia(elegido.ruta)} />
              ) : (
                <Boton texto="Descargar" alto={48} cargando={descargas.progreso[elegido.ruta] !== undefined}
                       alPulsar={() => descargas.bajar(elegido.ruta)} />
              )}
            </View>
            <View style={{ flex: 1 }}>
              {descargas.tieneCopia(elegido.ruta) ? (
                <Boton texto="Bajar otra vez" tipo="borde" alto={48} alPulsar={() => descargas.bajar(elegido.ruta)} />
              ) : (
                <Boton texto="Ver" tipo="borde" alto={48} alPulsar={() => ver(elegido)} />
              )}
            </View>
            <View style={{ flex: 1 }}>
              <Boton texto={elegido.favorito ? 'Quitar fav.' : 'Favorito'} tipo="borde" alto={48}
                     alPulsar={() => alternarFavorito(elegido)} />
            </View>
          </View>
        </View>
      ) : null}

      <Pestanas actual="archivos" permisos={conexion.sesion.permisos} alCambiar={alCambiar} />

      {descargas.visor}
      <Modal visible={!!visor} transparent animationType="fade" onRequestClose={() => setVisor(null)}>
        <Pressable accessibilityRole="button" accessibilityLabel="Cerrar" onPress={() => setVisor(null)}
                   style={{ flex: 1, backgroundColor: colores.abismo, justifyContent: 'center', padding: 12, gap: 12 }}>
          {visor ? (
            <>
              <Image source={{ uri: conexion.urlMiniatura(visor.ruta, 1024), headers: conexion.cabeceras() }}
                     resizeMode="contain" style={{ width: '100%', height: '75%' }} />
              <Texto centrado lineas={2}>{visor.nombre}</Texto>
              <Texto tipo="chico" centrado>Vista reducida. Toca para cerrar; para tenerlo entero, Descargar.</Texto>
            </>
          ) : null}
        </Pressable>
      </Modal>
    </Pantalla>
  );
}
