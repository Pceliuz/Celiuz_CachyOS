// La barra de abajo (maquetas 2 y 3). Terminal llega en la fase 7: se ve,
// apagada, con «pronto». Apps y Archivos solo si este celular tiene el permiso
// (se da desde la PC).
import { Pressable, View } from 'react-native';

import { colores } from '../paleta';
import { Texto } from './ui';

export type Pestana = 'inicio' | 'apps' | 'archivos';

const TODAS: { clave: Pestana | null; nombre: string }[] = [
  { clave: 'inicio', nombre: 'Inicio' },
  { clave: 'apps', nombre: 'Apps' },
  { clave: 'archivos', nombre: 'Archivos' },
  { clave: null, nombre: 'Terminal' },
];

export default function Pestanas({ actual, permisos, alCambiar }: {
  actual: Pestana; permisos: string[]; alCambiar: (p: Pestana) => void;
}) {
  return (
    <View style={{ height: 64, borderTopWidth: 1, borderTopColor: colores.apagado,
                   backgroundColor: colores.superficie, flexDirection: 'row' }}>
      {TODAS.map(({ clave, nombre }) => {
        const usable = clave === 'inicio' || (clave === 'apps' && permisos.includes('ventanas'))
          || (clave === 'archivos' && permisos.includes('archivos'));
        const activa = clave === actual;
        return (
          <Pressable key={nombre} accessibilityRole="tab" accessibilityState={{ selected: activa, disabled: !usable }}
                     onPress={usable && clave ? () => alCambiar(clave) : undefined}
                     style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: 2, opacity: usable ? 1 : 0.45 }}>
            <Texto tipo="chico" color={activa ? colores.neon : colores.tenue}>{nombre}</Texto>
            {!usable ? <Texto tipo="chico">{clave ? 'sin permiso' : 'pronto'}</Texto> : null}
          </Pressable>
        );
      })}
    </View>
  );
}
