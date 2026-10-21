// El pase de 24 h vencio (pantalla 8 de las maquetas): que sigue funcionando y
// como se renueva. El pase lo cuenta la PC con su reloj.
import { View } from 'react-native';

import * as f from '../formato';
import { colores } from '../paleta';
import { Boton, Pantalla, Tarjeta, Texto, fondoAmbar, fondoVerde, verde } from '../componentes/ui';

const PASOS = [
  'Conecta el celular por cable a esa PC.',
  'En la PC, abre «Celiuz Remoto» y pulsa «Solo renovar el pase».',
  'Pon aquí la contraseña de la app cuando te la pida: otras 24 h exactas desde ese momento.',
];
const SIGUE = ['Ver el estado', 'Ver apps abiertas', 'Apagar · reiniciar · suspender'];

export default function PaseVencido({ equipo, paseHasta, alVolver }: {
  equipo: string; paseHasta: string | null; alVolver: () => void;
}) {
  const p = f.pase(paseHasta, new Date());
  return (
    <Pantalla>
      <View style={{ flex: 1, gap: 22, paddingTop: 40 }}>
        <View style={{ alignSelf: 'center', width: 80, height: 80, borderRadius: 24, backgroundColor: fondoAmbar,
                       borderWidth: 1, borderColor: colores.atencion, alignItems: 'center', justifyContent: 'center' }}>
          <Texto tipo="titulo" color={colores.atencion}>24</Texto>
        </View>
        <View style={{ gap: 10 }}>
          <Texto tipo="titulo" centrado>{paseHasta ? 'El pase de 24 h venció' : 'Sin pase de 24 h'}</Texto>
          <Texto centrado color={colores.tenue}>
            {paseHasta ? `${p.texto[0].toUpperCase()}${p.texto.slice(1)} en ${equipo}. ` : `${equipo} no le ha dado pase a este celular. `}
            Hasta que lo renueves, la terminal, los archivos y cerrar apps están cerrados.
          </Texto>
        </View>
        <Tarjeta estilo={{ gap: 14 }}>
          <Texto>Para renovarlo (menos de 1 minuto)</Texto>
          {PASOS.map((t, i) => (
            <View key={i} style={{ flexDirection: 'row', gap: 12 }}>
              <View style={{ width: 26, height: 26, borderRadius: 13, backgroundColor: colores.apagado,
                             alignItems: 'center', justifyContent: 'center' }}>
                <Texto tipo="chico" color={colores.luz}>{i + 1}</Texto>
              </View>
              <View style={{ flex: 1 }}><Texto>{t}</Texto></View>
            </View>
          ))}
        </Tarjeta>
        <View style={{ gap: 8 }}>
          <Texto tipo="etiqueta">Sigue funcionando sin pase</Texto>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            {SIGUE.map((s) => (
              <View key={s} style={{ borderRadius: 999, paddingHorizontal: 12, paddingVertical: 8, backgroundColor: fondoVerde }}>
                <Texto tipo="chico" color={verde}>{s}</Texto>
              </View>
            ))}
          </View>
        </View>
        <View style={{ marginTop: 'auto' }}><Boton texto="Volver al inicio" alPulsar={alVolver} /></View>
      </View>
    </Pantalla>
  );
}
