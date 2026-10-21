// La app del celular de Celiuz Remoto. En construccion: por ahora solo dice que
// existe. Las pantallas van en src/pantallas/ (una por maqueta) y todo lo que
// hable con la PC, en src/api/.
//
// Los colores salen de src/paleta.ts (colores.json, que genera gen-colores.py
// de la paleta del escritorio): aqui no se escribe ningun hex a mano.
import { StatusBar } from 'expo-status-bar';
import { StyleSheet, Text, View } from 'react-native';

import { colores } from './src/paleta';

export default function App() {
  return (
    <View style={estilos.fondo}>
      <Text style={estilos.titulo}>Celiuz Remoto</Text>
      <Text style={estilos.texto}>En construcción</Text>
      <StatusBar style="light" />
    </View>
  );
}

const estilos = StyleSheet.create({
  fondo: {
    flex: 1,
    backgroundColor: colores.abismo,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  titulo: { color: colores.luz, fontSize: 26, fontWeight: '700' },
  texto: { color: colores.tenue, fontSize: 14 },
});
