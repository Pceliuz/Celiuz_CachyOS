// El visor de texto de la app: un .md, un .txt, un .conf que ya está en el
// celular. Hace falta porque no todo celular tiene una app para cada cosa (el
// HONOR del usuario no tenía ninguna para markdown). Markdown muy por encima:
// los títulos más grandes y los bloques de código en monoespaciada; el resto,
// tal cual y seleccionable para copiarlo.
import { Modal, Pressable, ScrollView, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colores } from '../paleta';
import { Boton, Texto } from './ui';

function lineas(texto: string, markdown: boolean) {
  const salida: { t: string; tipo: 'titulo' | 'codigo' | 'normal' }[] = [];
  let enCodigo = false;
  for (const l of texto.split('\n')) {
    if (markdown && l.trimStart().startsWith('```')) { enCodigo = !enCodigo; continue; }
    if (enCodigo || !markdown) salida.push({ t: l, tipo: markdown ? 'codigo' : 'normal' });
    else if (/^#{1,6}\s/.test(l)) salida.push({ t: l.replace(/^#+\s*/, ''), tipo: 'titulo' });
    else if (/^\s*[-*+]\s/.test(l)) salida.push({ t: l.replace(/^(\s*)[-*+]\s/, '$1• '), tipo: 'normal' });
    else salida.push({ t: l, tipo: 'normal' });
  }
  return salida;
}

// **negrita**, *cursiva* y `código` dentro de una línea de markdown.
function enLinea(t: string, md: boolean, base: object) {
  if (!md) return t;
  return t.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/).filter(Boolean).map((trozo, i) => {
    if (trozo.startsWith('**') && trozo.endsWith('**') && trozo.length > 4)
      return <Text key={i} style={[base, { fontWeight: '700' }]}>{trozo.slice(2, -2)}</Text>;
    if (trozo.startsWith('`') && trozo.endsWith('`') && trozo.length > 2)
      return <Text key={i} style={[base, { fontFamily: 'monospace', color: colores.neon }]}>{trozo.slice(1, -1)}</Text>;
    if (trozo.startsWith('*') && trozo.endsWith('*') && trozo.length > 2)
      return <Text key={i} style={[base, { fontStyle: 'italic' }]}>{trozo.slice(1, -1)}</Text>;
    return trozo;
  });
}

export default function VisorTexto({ nombre, texto, cortado, alCerrar, alAbrirFuera, alCompartir }: {
  nombre: string | null;
  texto: string;
  cortado: boolean;
  alCerrar: () => void;
  alAbrirFuera: () => void;
  alCompartir: () => void;
}) {
  const md = !!nombre && /\.(md|markdown)$/i.test(nombre);
  const mono = !md && !!nombre && !/\.txt$/i.test(nombre);
  // Un Modal no hereda el margen de la barra de estado: se pide aparte (la
  // cabecera salía encima de la hora).
  const borde = useSafeAreaInsets();
  return (
    <Modal visible={!!nombre} animationType="slide" onRequestClose={alCerrar} statusBarTranslucent>
      <View style={{ flex: 1, backgroundColor: colores.abismo, paddingTop: borde.top + 12, paddingBottom: borde.bottom }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 16, paddingBottom: 10 }}>
          <Pressable accessibilityRole="button" accessibilityLabel="Cerrar" onPress={alCerrar}
                     style={{ width: 44, height: 44, borderRadius: 12, borderWidth: 1, borderColor: colores.apagado,
                              alignItems: 'center', justifyContent: 'center' }}>
            <Texto tipo="grande">‹</Texto>
          </Pressable>
          <View style={{ flex: 1 }}><Texto lineas={1}>{nombre}</Texto></View>
        </View>
        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, gap: 2 }}>
          {lineas(texto, md).map((l, i) => (
            <Text key={i} selectable
                  style={{ color: l.tipo === 'titulo' ? colores.neon : colores.luz,
                           fontSize: l.tipo === 'titulo' ? 18 : mono || l.tipo === 'codigo' ? 13 : 15,
                           fontWeight: l.tipo === 'titulo' ? '700' : '400',
                           fontFamily: mono || l.tipo === 'codigo' ? 'monospace' : undefined,
                           marginTop: l.tipo === 'titulo' ? 10 : 0 }}>
              {l.t ? (l.tipo === 'normal' ? enLinea(l.t, md, { color: colores.luz, fontSize: 15 }) : l.t) : ' '}
            </Text>
          ))}
          {cortado ? <Texto tipo="chico">(Solo se enseña el primer mega.)</Texto> : null}
        </ScrollView>
        <View style={{ flexDirection: 'row', gap: 8, padding: 14 }}>
          <View style={{ flex: 1 }}><Boton texto="Abrir con otra app" tipo="borde" alto={48} alPulsar={alAbrirFuera} /></View>
          <View style={{ flex: 1 }}><Boton texto="Compartir" tipo="borde" alto={48} alPulsar={alCompartir} /></View>
        </View>
      </View>
    </Modal>
  );
}
