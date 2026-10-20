// La app del celular de Celiuz Remoto. En construccion: por ahora solo dice que
// existe. Las pantallas van en src/pantallas/ (una por maqueta) y todo lo que
// hable con la PC, en src/api/.
//
// Los colores son PROVISIONALES: copiados a mano de hypr/conf/colores.conf. Una
// copia de la paleta se separa sola (ver CLAUDE.md, «Un color copiado no falla
// nunca»); antes de la fase 1 los tiene que generar gen-colores.py.
import { StatusBar } from 'expo-status-bar';
import { StyleSheet, Text, View } from 'react-native';

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
    backgroundColor: '#0d0418',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  titulo: { color: '#e4c7ff', fontSize: 26, fontWeight: '700' },
  texto: { color: '#8a7aa8', fontSize: 14 },
});
