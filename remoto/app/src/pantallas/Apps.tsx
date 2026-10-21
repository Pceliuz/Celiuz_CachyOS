// Apps abiertas (pantalla 3 de las maquetas). Verlas pide la contraseña;
// cerrarlas, el pase de 24 h. Se cierran PIDIENDOLO (como SUPER+Q), no
// matando: lo que tenga algo sin guardar preguntara en la PC.
import { useCallback, useEffect, useState } from 'react';
import { Alert, Pressable, RefreshControl, ScrollView, View } from 'react-native';

import { ErrorRemoto, type Conexion } from '../api/cliente';
import type { Ventana } from '../api/protocolo';
import { colores } from '../paleta';
import Pestanas, { type Pestana } from '../componentes/Pestanas';
import { Aviso, Pantalla, Tarjeta, Texto, fondoRojo } from '../componentes/ui';

const iniciales = (app: string) => (app.replace(/[^A-Za-zÁÉÍÓÚáéíóúñÑ0-9 ]/g, '').trim().slice(0, 2) || '?');

export default function Apps({ conexion, alCambiar, alVerPase, alCaducar }: {
  conexion: Conexion;
  alCambiar: (p: Pestana) => void;
  alVerPase: () => void;
  alCaducar: (sesionCaducada: boolean) => void;
}) {
  const [lista, setLista] = useState<Ventana[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cerrando, setCerrando] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      setLista(await conexion.ventanas());
      setError(null);
    } catch (e) {
      const err = e as ErrorRemoto;
      if (err.codigo === 'sin_sesion') return alCaducar(true);
      setError(err.message);
    } finally {
      setCargando(false);
    }
  }, [conexion, alCaducar]);

  useEffect(() => {
    cargar();
    const t = setInterval(cargar, 5000);
    return () => clearInterval(t);
  }, [cargar]);

  function cerrar(v: Ventana) {
    Alert.alert(`¿Cerrar ${v.app}?`, 'Se le pide cerrarse, como con SUPER+Q. Si tiene algo sin guardar, preguntará en la PC.', [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Cerrar', style: 'destructive', onPress: async () => {
        setCerrando(v.id);
        try {
          await conexion.cerrarVentana(v.id);
          setTimeout(cargar, 1200);
        } catch (e) {
          const err = e as ErrorRemoto;
          if (err.codigo === 'pase_vencido') alVerPase();
          else if (err.codigo === 'sin_sesion') alCaducar(true);
          else setError(err.message);
        } finally {
          setCerrando(null);
        }
      } },
    ]);
  }

  return (
    <Pantalla relleno={false}>
      <View style={{ paddingHorizontal: 20, paddingTop: 20, paddingBottom: 10, gap: 4 }}>
        <Texto tipo="chico">{conexion.equipo.equipo}</Texto>
        <Texto tipo="grande">Apps abiertas{lista ? ` · ${lista.length}` : ''}</Texto>
      </View>
      <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 16, gap: 10, flexGrow: 1 }}
                  refreshControl={<RefreshControl refreshing={cargando && lista !== null} onRefresh={cargar}
                                                  tintColor={colores.amatista} colors={[colores.amatista]} />}>
        {error ? <Aviso texto={error} color={colores.alerta} fondo={fondoRojo} /> : null}
        {lista === null && !error ? <Tarjeta><Texto color={colores.tenue}>Preguntando a la PC…</Texto></Tarjeta> : null}
        {lista?.length === 0 ? <Tarjeta><Texto color={colores.tenue}>No hay ninguna app abierta (o no hay nadie con la sesión iniciada).</Texto></Tarjeta> : null}
        {lista?.map((v) => (
          <Tarjeta key={v.id} estilo={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12, paddingRight: 12 }}>
            <View style={{ width: 36, height: 36, borderRadius: 10, backgroundColor: colores.apagado,
                           alignItems: 'center', justifyContent: 'center' }}>
              <Texto tipo="chico" color={colores.amatista}>{iniciales(v.app)}</Texto>
            </View>
            <View style={{ flex: 1, gap: 3 }}>
              <Texto lineas={1}>{v.app}</Texto>
              <Texto tipo="chico" lineas={1}>{`${v.titulo || '—'} · escritorio ${v.escritorio}`}</Texto>
            </View>
            <Pressable accessibilityRole="button" accessibilityLabel={`Cerrar ${v.app}`} onPress={() => cerrar(v)}
                       disabled={cerrando === v.id}
                       style={{ width: 44, height: 44, borderRadius: 12, backgroundColor: fondoRojo, borderWidth: 1,
                                borderColor: colores.alerta, alignItems: 'center', justifyContent: 'center',
                                opacity: cerrando === v.id ? 0.4 : 1 }}>
              <Texto tipo="grande" color={colores.alerta}>×</Texto>
            </Pressable>
          </Tarjeta>
        ))}
        <View style={{ marginTop: 'auto', borderRadius: 14, borderWidth: 1, borderStyle: 'dashed',
                       borderColor: colores.apagado, padding: 12 }}>
          <Texto tipo="chico">Verlas solo pide la contraseña. Cerrarlas pide el pase de 24 h. La app la cierra pidiéndolo, no la mata: si tiene algo sin guardar, preguntará en la PC.</Texto>
        </View>
      </ScrollView>
      <Pestanas actual="apps" permisos={conexion.sesion.permisos} alCambiar={alCambiar} />
    </Pantalla>
  );
}
