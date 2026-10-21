// Sin ningun equipo emparejado: que hacer. Emparejar se empieza SIEMPRE desde
// la PC (ahi se crea la contraseña), asi que aqui solo se explica.
import { View } from 'react-native';

import { colores } from '../paleta';
import { Boton, Pantalla, Tarjeta, Texto } from '../componentes/ui';

const PASOS = [
  'Instala Tailscale en este celular y entra con la misma cuenta que la PC.',
  'Conecta el celular a la PC por cable, con la «Depuración USB» activada.',
  'En la PC, abre «Celiuz Remoto», crea la contraseña y pulsa «Emparejar».',
];

export default function Bienvenida({ alInvitacion }: { alInvitacion?: () => void }) {
  return (
    <Pantalla>
      <View style={{ flex: 1, justifyContent: 'center', gap: 28 }}>
        <View style={{ gap: 10, alignItems: 'center' }}>
          <Texto tipo="titulo">Celiuz Remoto</Texto>
          <Texto centrado color={colores.tenue}>Todavía no hay ninguna PC emparejada.</Texto>
        </View>
        <Tarjeta estilo={{ gap: 14 }}>
          <Texto tipo="normal">Para emparejar (una vez por PC)</Texto>
          {PASOS.map((p, i) => (
            <View key={i} style={{ flexDirection: 'row', gap: 12 }}>
              <View style={{ width: 26, height: 26, borderRadius: 13, backgroundColor: colores.apagado,
                             alignItems: 'center', justifyContent: 'center' }}>
                <Texto tipo="chico" color={colores.luz}>{i + 1}</Texto>
              </View>
              <View style={{ flex: 1 }}><Texto>{p}</Texto></View>
            </View>
          ))}
        </Tarjeta>
        <Texto tipo="chico" centrado>La app se abrirá sola cuando la PC empiece a emparejar.</Texto>
        {alInvitacion ? <Boton texto="Tengo una invitación (ayudar a alguien)" tipo="borde" alto={48} alPulsar={alInvitacion} /> : null}
      </View>
    </Pantalla>
  );
}
