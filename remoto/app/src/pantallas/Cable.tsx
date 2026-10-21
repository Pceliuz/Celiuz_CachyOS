// Lo que pasa con el celular enchufado a la PC: emparejar y renovar el pase.
// Esta pantalla la abre LA PC (adb, con un intent explicito y un codigo de un
// solo uso: remoto/PROTOCOLO.md, «USB»); no se llega a ella desde la app.
//
// Emparejar no pide nada aqui: la contraseña se creo en la PC. Renovar si: es
// lo que impide que quien te quite el celular lo enchufe un momento y se lleve
// 24 h (remoto/DISEÑO.md, «El pase de 24 h»).
import { useEffect, useState } from 'react';
import { View } from 'react-native';

import * as almacen from '../almacen';
import { ErrorRemoto, emparejar, hola, renovar, type Enlace, type EquipoGuardado } from '../api/cliente';
import { nuevaClave, publica } from '../api/cripto';
import * as f from '../formato';
import { azar, herramientas } from '../herramientas';
import { colores } from '../paleta';
import { Aviso, Boton, Campo, Pantalla, Tarjeta, Texto, fondoRojo, fondoVerde, verde } from '../componentes/ui';

type Fase = 'mirando' | 'pidiendo' | 'trabajando' | 'hecho' | 'error';

export default function Cable({ enlace, alTerminar }: { enlace: Enlace; alTerminar: () => void }) {
  const [fase, setFase] = useState<Fase>('mirando');
  const [equipo, setEquipo] = useState<string>('');
  const [mensaje, setMensaje] = useState('');
  const [contrasena, setContrasena] = useState('');
  const [guardado, setGuardado] = useState<EquipoGuardado | null>(null);

  useEffect(() => {
    let vivo = true;
    (async () => {
      try {
        const h = await hola(herramientas, enlace.puerto);
        if (!vivo) return;
        setEquipo(h.equipo);
        if (h.modo !== enlace.modo) throw new ErrorRemoto('respuesta', 'La PC esperaba otra cosa. Vuelve a empezar desde la PC.');
        if (enlace.modo === 'emparejar') {
          setFase('trabajando');
          const clave = nuevaClave(azar);
          const r = await emparejar(herramientas, enlace.puerto, enlace.codigo, clave, publica(clave), 'Android');
          const e: EquipoGuardado = { dispositivo: r.dispositivo, equipo: r.equipo, direccion: r.direccion,
                                      permisos: r.permisos, pase_hasta: r.pase_hasta };
          await almacen.guardarEquipo(e, clave);
          if (!vivo) return;
          setGuardado(e);
          setFase('hecho');
        } else {
          const e = (await almacen.equipos()).find((x) => x.equipo === h.equipo);
          if (!e) throw new ErrorRemoto('respuesta', `Este celular no está emparejado con ${h.equipo}. Empareja primero desde la PC.`);
          setGuardado(e);
          setFase('pidiendo');
        }
      } catch (err) {
        if (!vivo) return;
        const e = err as ErrorRemoto;
        setMensaje(e.codigo === 'red'
          ? 'No llego al canal USB de la PC. Vuelve a empezar desde la ventana de la PC (el canal dura 2 minutos).'
          : e.message);
        setFase('error');
      }
    })();
    return () => { vivo = false; };
  }, [enlace]);

  async function renovarPase() {
    if (!guardado) return;
    setFase('trabajando');
    setMensaje('');
    try {
      const clave = await almacen.claveDe(guardado.dispositivo);
      if (!clave) throw new ErrorRemoto('respuesta', 'Falta la clave de este equipo en el celular: vuelve a emparejarlo.');
      const r = await renovar(herramientas, enlace.puerto, enlace.codigo, clave, guardado.dispositivo, contrasena);
      await almacen.actualizarPase(guardado.dispositivo, r.pase_hasta);
      setGuardado({ ...guardado, pase_hasta: r.pase_hasta });
      setContrasena('');
      setFase('hecho');
    } catch (err) {
      const e = err as ErrorRemoto;
      setMensaje(e.codigo === 'contrasena' && e.intentosRestantes !== undefined
        ? `Contraseña incorrecta. Quedan ${e.intentosRestantes} intentos.` : e.message);
      setFase(e.codigo === 'contrasena' ? 'pidiendo' : 'error');
    }
  }

  const pase = guardado ? f.pase(guardado.pase_hasta, new Date()) : null;
  const titulo = enlace.modo === 'emparejar' ? 'Emparejar con la PC' : 'Renovar el pase de 24 h';

  return (
    <Pantalla>
      <View style={{ flex: 1, justifyContent: 'center', gap: 22 }}>
        <View style={{ gap: 6, alignItems: 'center' }}>
          <Texto tipo="etiqueta">Por cable</Texto>
          <Texto tipo="titulo" centrado>{titulo}</Texto>
          {equipo ? <Texto centrado color={colores.tenue}>{equipo}</Texto> : null}
        </View>

        {fase === 'mirando' || (fase === 'trabajando' && enlace.modo === 'emparejar') ? (
          <Tarjeta><Texto>{fase === 'mirando' ? 'Hablando con la PC por el cable…' : 'Creando la clave de este celular y emparejando…'}</Texto></Tarjeta>
        ) : null}

        {fase === 'pidiendo' || (fase === 'trabajando' && enlace.modo === 'renovar') ? (
          <View style={{ gap: 16 }}>
            <Campo etiqueta="Contraseña de la app" valor={contrasena} alCambiar={setContrasena}
                   alEnviar={renovarPase} error={!!mensaje} ayuda={mensaje || 'La que creaste en la PC al emparejar.'} />
            <Boton texto="Renovar 24 h" alPulsar={renovarPase} cargando={fase === 'trabajando'} desactivado={!contrasena} />
          </View>
        ) : null}

        {fase === 'hecho' && pase ? (
          <Tarjeta estilo={{ backgroundColor: fondoVerde, borderColor: verde, gap: 6 }}>
            <Texto tipo="grande" color={verde}>{enlace.modo === 'emparejar' ? 'Emparejado' : 'Pase renovado'}</Texto>
            <Texto>Pase de 24 h: {pase.texto} (quedan {pase.restante}).</Texto>
            <Texto tipo="chico">Ya puedes desconectar el cable.</Texto>
          </Tarjeta>
        ) : null}

        {fase === 'error' ? <Aviso texto={mensaje} color={colores.alerta} fondo={fondoRojo} /> : null}

        {fase === 'hecho' || fase === 'error' ? <Boton texto="Continuar" alPulsar={alTerminar} /> : null}
      </View>
    </Pantalla>
  );
}
