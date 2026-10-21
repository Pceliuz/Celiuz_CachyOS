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
import { useCallback, useEffect, useRef, useState } from 'react';
import { BackHandler, Linking } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import * as almacen from './src/almacen';
import type { Pestana } from './src/componentes/Pestanas';
import { leerEnlace, type Conexion, type Enlace, type EquipoGuardado } from './src/api/cliente';
import type { Equipo } from './src/api/protocolo';
import Bienvenida from './src/pantallas/Bienvenida';
import Cable from './src/pantallas/Cable';
import Entrar from './src/pantallas/Entrar';
import Apps from './src/pantallas/Apps';
import Archivos from './src/pantallas/Archivos';
import Recientes from './src/pantallas/Recientes';
import Terminal from './src/pantallas/Terminal';
import Invitacion from './src/pantallas/Invitacion';
import VerPantalla from './src/pantallas/Pantalla';
import Inicio from './src/pantallas/Inicio';
import PaseVencido from './src/pantallas/PaseVencido';

export default function App() {
  const [equipos, setEquipos] = useState<EquipoGuardado[] | null>(null);
  const [enlace, setEnlace] = useState<Enlace | null>(null);
  const [conexion, setConexion] = useState<Conexion | null>(null);
  const [datos, setDatos] = useState<Equipo | null>(null);
  const [verPase, setVerPase] = useState(false);
  const [pestana, setPestana] = useState<Pestana>('inicio');
  const [aviso, setAviso] = useState<string | undefined>();
  const [verRecientes, setVerRecientes] = useState(false);
  const [verPantalla, setVerPantalla] = useState(false);
  const [verInvitacion, setVerInvitacion] = useState(false);
  const [carpetaInicial, setCarpetaInicial] = useState('');
  // Lo que la pantalla de dentro quiera hacer con «Atrás» antes que App (el
  // explorador sube de carpeta). Un ref y no otro listener: el orden en que
  // React vuelve a apuntar los listeners no es el de las pantallas.
  const atrasDeDentro = useRef<(() => boolean) | null>(null);
  const fijarAtras = useCallback((fn: (() => boolean) | null) => { atrasDeDentro.current = fn; }, []);

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
      if (verInvitacion) { setVerInvitacion(false); return true; }
      if (verRecientes) { setVerRecientes(false); return true; }
      if (verPantalla) { setVerPantalla(false); return true; }
      if (atrasDeDentro.current?.()) return true;
      if (pestana !== 'inicio') { setPestana('inicio'); return true; }
      if (conexion) { salir(); return true; }
      return false;
    });
    return () => s.remove();
  }, [verPase, verRecientes, verPantalla, verInvitacion, pestana, conexion, salir]);

  const entrar = useCallback((c: Conexion) => {
    setAviso(undefined);
    setPestana('inicio');
    setVerRecientes(false);
    setVerPantalla(false);
    setCarpetaInicial('');
    setConexion(c);
    setDatos(null);
    c.datosEquipo().then((d) => {
      setDatos(d);
      if (d.despertar?.mac !== undefined) almacen.actualizarMac(c.equipo.dispositivo, d.despertar.mac).then(recargar);
    }).catch(() => setDatos(null));
  }, []);

  let pantalla;
  if (enlace) {
    pantalla = <Cable enlace={enlace} alTerminar={() => { setEnlace(null); recargar(); }} />;
  } else if (verInvitacion && !conexion) {
    pantalla = <Invitacion alVolver={() => setVerInvitacion(false)}
                           alTerminar={() => { setVerInvitacion(false); recargar(); }} />;
  } else if (equipos === null) {
    pantalla = null;
  } else if (equipos.length === 0) {
    pantalla = <Bienvenida alInvitacion={() => setVerInvitacion(true)} />;
  } else if (!conexion) {
    pantalla = <Entrar equipos={equipos} aviso={aviso} alEntrar={entrar} alCambiarEquipos={recargar}
                       alInvitacion={() => setVerInvitacion(true)} />;
  } else if (verPase) {
    pantalla = <PaseVencido equipo={conexion.equipo.equipo} paseHasta={conexion.sesion.pase_hasta}
                            alVolver={() => setVerPase(false)} />;
  } else if (verPantalla) {
    pantalla = <VerPantalla conexion={conexion} alVolver={() => setVerPantalla(false)} alCaducar={caducar}
                            alVerPase={() => setVerPase(true)} />;
  } else if (pestana === 'archivos' && verRecientes) {
    pantalla = <Recientes conexion={conexion} alVolver={() => setVerRecientes(false)} alCaducar={caducar}
                          alVerPase={() => setVerPase(true)}
                          alAbrirCarpeta={(r) => { setCarpetaInicial(r); setVerRecientes(false); }} />;
  } else if (pestana === 'archivos') {
    pantalla = <Archivos conexion={conexion} inicial={carpetaInicial} alCambiar={setPestana} alCaducar={caducar}
                         alVerPase={() => setVerPase(true)} alRecientes={() => setVerRecientes(true)}
                         fijarAtras={fijarAtras} />;
  } else if (pestana === 'terminal') {
    pantalla = <Terminal conexion={conexion} alCambiar={setPestana} alCaducar={caducar}
                         alVerPase={() => setVerPase(true)} fijarAtras={fijarAtras} />;
  } else if (pestana === 'apps') {
    pantalla = <Apps conexion={conexion} alCambiar={setPestana} alVerPase={() => setVerPase(true)}
                     alCaducar={caducar} />;
  } else {
    pantalla = <Inicio conexion={conexion} datos={datos} otros={(equipos ?? []).filter((x) => x.dispositivo !== conexion.equipo.dispositivo)}
                       alSalir={salir} alCaducar={caducar} alVerPantalla={() => setVerPantalla(true)}
                       alVerPase={() => setVerPase(true)} alCambiar={setPestana} />;
  }

  return (
    <SafeAreaProvider>
      {pantalla}
      <StatusBar style="light" />
    </SafeAreaProvider>
  );
}
