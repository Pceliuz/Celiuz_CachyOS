// Entrar (pantalla 1 de las maquetas): elegir el equipo y poner la contraseña
// de la app. La comprueba la PC, no el celular; el celular solo firma el reto
// con la clave de ese equipo (remoto/PROTOCOLO.md, «Entrar»).
import { useCallback, useEffect, useState } from 'react';
import { Alert, Pressable, ScrollView, View } from 'react-native';

import * as almacen from '../almacen';
import { Conexion, ErrorRemoto, enLinea, entrar, type EquipoGuardado } from '../api/cliente';
import * as f from '../formato';
import { herramientas } from '../herramientas';
import { colores } from '../paleta';
import { Aviso, Boton, Campo, Pantalla, Texto, fondoAmbar, fondoRojo, verde } from '../componentes/ui';

export default function Entrar({ equipos, aviso, alEntrar, alCambiarEquipos }: {
  equipos: EquipoGuardado[];
  aviso?: string;
  alEntrar: (c: Conexion) => void;
  alCambiarEquipos: () => void;
}) {
  const [elegido, setElegido] = useState(equipos[0]?.dispositivo);
  const [contrasena, setContrasena] = useState('');
  const [error, setError] = useState<{ texto: string; olvidable?: boolean } | null>(null);
  const [entrando, setEntrando] = useState(false);
  const [latencia, setLatencia] = useState<Record<string, number | null | undefined>>({});

  const equipo = equipos.find((x) => x.dispositivo === elegido) ?? equipos[0];

  const mirar = useCallback(() => {
    for (const e of equipos) {
      enLinea(herramientas, e).then((ms) => setLatencia((l) => ({ ...l, [e.dispositivo]: ms })));
    }
  }, [equipos]);

  useEffect(() => {
    mirar();
    const t = setInterval(mirar, 10000);
    return () => clearInterval(t);
  }, [mirar]);

  async function alPulsarEntrar() {
    if (!equipo || !contrasena) return;
    setEntrando(true);
    setError(null);
    try {
      const clave = await almacen.claveDe(equipo.dispositivo);
      if (!clave) throw new ErrorRemoto('firma', 'Falta la clave de este equipo en el celular.');
      const c = await entrar(herramientas, equipo, clave, contrasena);
      await almacen.actualizarPase(equipo.dispositivo, c.sesion.pase_hasta);
      setContrasena('');
      alEntrar(c);
    } catch (err) {
      const e = err as ErrorRemoto;
      if (e.codigo === 'contrasena') {
        setError({ texto: `Contraseña incorrecta. Quedan ${e.intentosRestantes ?? '?'} intentos.` });
      } else if (e.codigo === 'firma') {
        // La PC no reconoce a este celular: lo revocaron, o se empareja otra
        // vez desde otra instalacion de la app.
        setError({ texto: 'Esta PC ya no reconoce a este celular (¿lo revocaron?). Vuelve a emparejarlo por cable.',
                   olvidable: true });
      } else {
        setError({ texto: e.message });
      }
    } finally {
      setEntrando(false);
    }
  }

  function olvidar() {
    if (!equipo) return;
    Alert.alert(`¿Olvidar ${equipo.equipo}?`, 'Se borra la clave de ese equipo de este celular. Para volver a usarlo, hay que emparejarlo otra vez por cable.', [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Olvidar', style: 'destructive', onPress: async () => {
        await almacen.olvidar(equipo.dispositivo);
        setError(null);
        alCambiarEquipos();
      } },
    ]);
  }

  const pase = equipo ? f.pase(equipo.pase_hasta, new Date()) : null;

  return (
    <Pantalla relleno={false}>
      <ScrollView contentContainerStyle={{ paddingHorizontal: 28, paddingTop: 56, paddingBottom: 24, gap: 26, flexGrow: 1 }}
                  keyboardShouldPersistTaps="handled">
        <View style={{ alignItems: 'center', gap: 12 }}>
          <Texto tipo="titulo">Celiuz Remoto</Texto>
          <Texto centrado color={colores.tenue}>La contraseña la creaste en la PC.{'\n'}La comprueba la PC, no el celular.</Texto>
        </View>

        {aviso ? <Aviso texto={aviso} /> : null}

        <View style={{ gap: 8 }}>
          <Texto tipo="etiqueta">Equipo</Texto>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
            {equipos.map((e) => {
              const ms = latencia[e.dispositivo];
              const activo = e.dispositivo === equipo?.dispositivo;
              return (
                <Pressable key={e.dispositivo} accessibilityRole="button" accessibilityState={{ selected: activo }}
                           onPress={() => { setElegido(e.dispositivo); setError(null); }} onLongPress={olvidar}
                           style={{ flexBasis: '47%', flexGrow: 1, height: 64, borderRadius: 14, backgroundColor: colores.superficie,
                                    borderWidth: activo ? 1.5 : 1, borderColor: activo ? colores.amatista : colores.apagado,
                                    paddingHorizontal: 14, justifyContent: 'center', gap: 4 }}>
                  <Texto>{e.equipo}</Texto>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                    <View style={{ width: 7, height: 7, borderRadius: 4,
                                   backgroundColor: ms === undefined ? colores.apagado : ms === null ? colores.tenue : verde }} />
                    <Texto tipo="chico" color={ms ? verde : colores.tenue}>
                      {ms === undefined ? 'mirando…' : ms === null ? 'Apagada o sin red' : 'En línea'}
                    </Texto>
                  </View>
                </Pressable>
              );
            })}
          </View>
        </View>

        <Campo etiqueta="Contraseña de la app" valor={contrasena} alCambiar={(t) => { setContrasena(t); setError(null); }}
               alEnviar={alPulsarEntrar} error={!!error}
               ayuda={error?.texto ?? 'Al quinto fallo seguido, este celular se bloquea y la PC te avisa.'} />

        <Boton texto="Entrar" alPulsar={alPulsarEntrar} cargando={entrando} desactivado={!contrasena} />
        {error?.olvidable ? <Boton texto={`Olvidar ${equipo?.equipo}`} tipo="peligro" alto={48} alPulsar={olvidar} /> : null}

        {/* Si la PC ya no reconoce al celular, el pase guardado no vale: no se enseña. */}
        {pase && !error?.olvidable ? (
          <View style={{ marginTop: 'auto' }}>
            <Aviso
              texto={pase.vigente
                ? `Pase de 24 h de ${equipo?.equipo}: quedan ${pase.restante}. Conéctala por cable antes de dormir.`
                : `Sin pase en ${equipo?.equipo}: lo de ver y apagar funciona; cerrar apps, archivos y terminal no. Se renueva por cable.`}
              color={pase.vigente ? colores.atencion : colores.alerta}
              fondo={pase.vigente ? fondoAmbar : fondoRojo} />
          </View>
        ) : null}
      </ScrollView>
    </Pantalla>
  );
}
