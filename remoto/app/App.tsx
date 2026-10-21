// La app del celular de Celiuz Remoto. Sin libreria de navegacion: son pocas
// pantallas y el orden lo decide el estado (remoto/DISEÑO.md):
//
//   un enlace de la PC por el cable  -> Cable (emparejar o renovar)
//   sin equipos emparejados          -> Bienvenida
//   sin sesion                       -> Entrar
//   con sesion                       -> Inicio (o PaseVencido, si se pide)
//
// Los enlaces llegan de la PC por adb (`am start -n ... -d celiuzremoto://...`),
// con la app cerrada (getInitialURL) o abierta (el evento 'url').
//
// Los colores salen de src/paleta.ts (colores.json, que genera gen-colores.py
// de la paleta del escritorio): aqui no se escribe ningun hex a mano.
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useState } from 'react';
import { BackHandler, Linking } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import * as almacen from './src/almacen';
import { leerEnlace, type Conexion, type Enlace, type EquipoGuardado } from './src/api/cliente';
import Bienvenida from './src/pantallas/Bienvenida';
import Cable from './src/pantallas/Cable';
import Entrar from './src/pantallas/Entrar';
import Inicio from './src/pantallas/Inicio';
import PaseVencido from './src/pantallas/PaseVencido';

export default function App() {
  const [equipos, setEquipos] = useState<EquipoGuardado[] | null>(null);
  const [enlace, setEnlace] = useState<Enlace | null>(null);
  const [conexion, setConexion] = useState<Conexion | null>(null);
  const [cpu, setCpu] = useState<string | null>(null);
  const [verPase, setVerPase] = useState(false);
  const [aviso, setAviso] = useState<string | undefined>();

  const recargar = useCallback(() => almacen.equipos().then(setEquipos), []);

  useEffect(() => {
    recargar();
    Linking.getInitialURL().then((u) => setEnlace(leerEnlace(u)));
    const s = Linking.addEventListener('url', ({ url }) => {
      const e = leerEnlace(url);
      if (e) setEnlace(e);
    });
    return () => s.remove();
  }, [recargar]);

  const salir = useCallback(() => {
    conexion?.salir();
    setConexion(null);
    setVerPase(false);
  }, [conexion]);

  const caducar = useCallback((sesionCaducada: boolean) => {
    setConexion(null);
    setVerPase(false);
    setAviso(sesionCaducada
      ? 'La sesión caducó o la PC cerró la puerta a este celular. Vuelve a entrar.'
      : 'Se cortó la conexión con la PC. Vuelve a entrar cuando tenga red.');
  }, []);

  // Atras: del pase a Inicio, de Inicio fuera de la sesion (no cerrar la app
  // de golpe con la sesion abierta).
  useEffect(() => {
    const s = BackHandler.addEventListener('hardwareBackPress', () => {
      if (verPase) { setVerPase(false); return true; }
      if (conexion) { salir(); return true; }
      return false;
    });
    return () => s.remove();
  }, [verPase, conexion, salir]);

  const entrar = useCallback((c: Conexion) => {
    setAviso(undefined);
    setConexion(c);
    c.datosEquipo().then((d) => setCpu(d.cpu)).catch(() => setCpu(null));
  }, []);

  let pantalla;
  if (enlace) {
    pantalla = <Cable enlace={enlace} alTerminar={() => { setEnlace(null); recargar(); }} />;
  } else if (equipos === null) {
    pantalla = null;
  } else if (equipos.length === 0) {
    pantalla = <Bienvenida />;
  } else if (!conexion) {
    pantalla = <Entrar equipos={equipos} aviso={aviso} alEntrar={entrar} alCambiarEquipos={recargar} />;
  } else if (verPase) {
    pantalla = <PaseVencido equipo={conexion.equipo.equipo} paseHasta={conexion.sesion.pase_hasta}
                            alVolver={() => setVerPase(false)} />;
  } else {
    pantalla = <Inicio conexion={conexion} cpu={cpu} alSalir={salir} alCaducar={caducar}
                       alVerPase={() => setVerPase(true)} />;
  }

  return (
    <SafeAreaProvider>
      {pantalla}
      <StatusBar style="light" />
    </SafeAreaProvider>
  );
}
