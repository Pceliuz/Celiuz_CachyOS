// Confirmar apagar / reiniciar / suspender (pantalla 4 de las maquetas): una
// hoja que sube desde abajo. Lo que se confirma aqui no pasa al instante: en
// la PC sale un aviso con cuenta atras, y quien este delante puede cancelarlo.
import { Modal, Pressable, View } from 'react-native';

import type { AccionEnergia } from '../api/protocolo';
import { colores } from '../paleta';
import { Boton, Texto, fondoRojo } from './ui';

const VERBO: Record<AccionEnergia, [string, string]> = {
  apagar: ['Apagar', 'apagar'],
  reiniciar: ['Reiniciar', 'reiniciar'],
  suspender: ['Suspender', 'suspender'],
};

// El simbolo de encendido dibujado con formas: el glifo ⏻ (U+23FB) no esta en
// la fuente del celular y salia un cuadro vacio (medido en el HONOR).
function Encendido() {
  return (
    <View style={{ width: 24, height: 24, alignItems: 'center' }}>
      <View style={{ position: 'absolute', top: 3, width: 21, height: 21, borderRadius: 11,
                     borderWidth: 2.5, borderColor: colores.alerta, borderTopColor: 'transparent' }} />
      <View style={{ width: 2.5, height: 12, borderRadius: 2, backgroundColor: colores.alerta }} />
    </View>
  );
}

export default function HojaEnergia({ accion, equipo, apps, segundos, enviando, alConfirmar, alCerrar }: {
  accion: AccionEnergia | null;
  equipo: string;
  apps: number | null; // null: este celular no puede ver las apps
  segundos: number;
  enviando: boolean;
  alConfirmar: () => void;
  alCerrar: () => void;
}) {
  if (!accion) return null;
  const [Titulo, verbo] = VERBO[accion];
  return (
    <Modal transparent animationType="slide" visible onRequestClose={alCerrar} statusBarTranslucent>
      <Pressable style={{ flex: 1, backgroundColor: 'transparent' }} onPress={alCerrar} accessibilityLabel="Cerrar" />
      <View style={{ borderTopLeftRadius: 24, borderTopRightRadius: 24, backgroundColor: colores.superficie,
                     borderTopWidth: 1, borderColor: colores.apagado, paddingHorizontal: 22, paddingTop: 12,
                     paddingBottom: 34, gap: 18 }}>
        <View style={{ width: 40, height: 4, borderRadius: 2, backgroundColor: colores.apagado, alignSelf: 'center' }} />
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14 }}>
          <View style={{ width: 48, height: 48, borderRadius: 14, backgroundColor: fondoRojo,
                         alignItems: 'center', justifyContent: 'center' }}>
            <Encendido />
          </View>
          <View style={{ flex: 1 }}><Texto tipo="grande">¿{Titulo} {equipo}?</Texto></View>
        </View>
        {accion !== 'suspender' ? (
          <Texto color={colores.tenue}>
            {apps === null ? 'Las apps abiertas' : apps === 1 ? 'Hay 1 app abierta. Se le pedirá' : `Hay ${apps} apps abiertas. Se les pedirá`}
            {apps === null ? ' recibirán la orden de cerrarse' : ' cerrarse'}; lo que no esté guardado puede perderse.
          </Texto>
        ) : (
          <Texto color={colores.tenue}>Las apps se quedan como están, en pausa hasta que la PC despierte.</Texto>
        )}
        <View style={{ borderRadius: 14, backgroundColor: colores.abismo, borderWidth: 1, borderColor: colores.apagado, padding: 12 }}>
          <Texto tipo="chico" color={colores.luz}>
            En la PC saldrá un aviso con cuenta atrás de {segundos} s. Si hay alguien delante, puede cancelarlo. Tú también, desde aquí.
          </Texto>
        </View>
        <View style={{ gap: 10 }}>
          <Boton texto={Titulo} tipo="peligro" alPulsar={alConfirmar} cargando={enviando} />
          <Boton texto="Cancelar" tipo="borde" alto={52} alPulsar={alCerrar} />
        </View>
      </View>
    </Modal>
  );
}
