// Las piezas que se repiten en las pantallas, con las medidas de las maquetas
// (https://claude.ai/artifact/BGqHdnHe5W2Xu7LNuVwYUd) y los colores de la
// paleta generada: aqui no se escribe ningun hex a mano.
//
// Los fondos oscuros de la maqueta (verde, rojo, ambar) son el mismo color de
// la paleta con poca opacidad: se derivan con `alfa`, no se copian.
import type { ReactNode } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View, type ViewStyle } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colores } from '../paleta';

// '#rrggbb' de la paleta -> 'rgba(r, g, b, a)'
export function alfa(hex: string, a: number): string {
  const n = parseInt(hex.slice(1, 7), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
}

export const verde = colores.exito;
export const fondoVerde = alfa(colores.exito, 0.12);
export const fondoRojo = alfa(colores.alerta, 0.16);
export const fondoAmbar = alfa(colores.atencion, 0.12);

export function Pantalla({ children, relleno = true }: { children: ReactNode; relleno?: boolean }) {
  const borde = useSafeAreaInsets();
  return (
    <View style={[e.pantalla, { paddingTop: borde.top, paddingBottom: borde.bottom }]}>
      <View style={[{ flex: 1 }, relleno && e.relleno]}>{children}</View>
    </View>
  );
}

export function Tarjeta({ children, estilo }: { children: ReactNode; estilo?: ViewStyle }) {
  return <View style={[e.tarjeta, estilo]}>{children}</View>;
}

export function Texto({ children, tipo = 'normal', color, centrado }: {
  children: ReactNode;
  tipo?: 'titulo' | 'grande' | 'normal' | 'chico' | 'etiqueta' | 'cifra';
  color?: string;
  centrado?: boolean;
}) {
  return <Text style={[e[tipo], color ? { color } : null, centrado ? { textAlign: 'center' } : null]}>{children}</Text>;
}

export function Boton({ texto, alPulsar, tipo = 'lleno', desactivado, cargando, alto = 56 }: {
  texto: string;
  alPulsar?: () => void;
  tipo?: 'lleno' | 'borde' | 'peligro';
  desactivado?: boolean;
  cargando?: boolean;
  alto?: number;
}) {
  const inactivo = desactivado || cargando;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: !!inactivo }}
      onPress={inactivo ? undefined : alPulsar}
      style={({ pressed }) => [e.boton, e[`boton_${tipo}`], { height: alto }, pressed && !inactivo && { opacity: 0.75 },
                               inactivo && { opacity: 0.45 }]}>
      {cargando ? (
        <ActivityIndicator color={tipo === 'lleno' ? colores.abismo : colores.luz} />
      ) : (
        <Text style={[e.botonTexto, e[`botonTexto_${tipo}`]]}>{texto}</Text>
      )}
    </Pressable>
  );
}

export function Campo({ etiqueta, valor, alCambiar, alEnviar, ayuda, error }: {
  etiqueta: string;
  valor: string;
  alCambiar: (t: string) => void;
  alEnviar?: () => void;
  ayuda?: string;
  error?: boolean;
}) {
  return (
    <View style={{ gap: 8 }}>
      <Texto tipo="etiqueta">{etiqueta}</Texto>
      <TextInput
        accessibilityLabel={etiqueta}
        value={valor}
        onChangeText={alCambiar}
        onSubmitEditing={alEnviar}
        secureTextEntry
        autoCapitalize="none"
        autoCorrect={false}
        returnKeyType="go"
        placeholderTextColor={colores.tenue}
        selectionColor={colores.neon}
        style={[e.campo, error && { borderColor: colores.alerta }]}
      />
      {ayuda ? <Texto tipo="chico" color={error ? colores.alerta : colores.tenue}>{ayuda}</Texto> : null}
    </View>
  );
}

export function Barra({ valor, color = colores.amatista }: { valor: number; color?: string }) {
  return (
    <View style={e.barra}>
      <View style={[e.barraLlena, { width: `${Math.round(Math.max(0, Math.min(1, valor)) * 100)}%`, backgroundColor: color }]} />
    </View>
  );
}

export function Aviso({ texto, color = colores.atencion, fondo = colores.superficie }: {
  texto: string; color?: string; fondo?: string;
}) {
  return (
    <View style={[e.tarjeta, { backgroundColor: fondo, borderColor: color, paddingVertical: 12 }]}>
      <Texto tipo="chico" color={color}>{texto}</Texto>
    </View>
  );
}

export const e = StyleSheet.create({
  pantalla: { flex: 1, backgroundColor: colores.abismo },
  relleno: { paddingHorizontal: 24, paddingVertical: 20 },
  tarjeta: {
    borderRadius: 16, backgroundColor: colores.superficie, borderWidth: 1, borderColor: colores.apagado,
    paddingHorizontal: 16, paddingVertical: 14, gap: 8,
  },
  titulo: { color: colores.luz, fontSize: 26, fontWeight: '700', letterSpacing: -0.5 },
  grande: { color: colores.luz, fontSize: 20, fontWeight: '700' },
  normal: { color: colores.luz, fontSize: 14, lineHeight: 20 },
  chico: { color: colores.tenue, fontSize: 12, lineHeight: 17 },
  etiqueta: { color: colores.tenue, fontSize: 12, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 1 },
  cifra: { color: colores.luz, fontSize: 26, fontWeight: '700' },
  boton: { borderRadius: 16, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 16 },
  boton_lleno: { backgroundColor: colores.amatista },
  boton_borde: { borderWidth: 1, borderColor: colores.apagado },
  boton_peligro: { backgroundColor: fondoRojo, borderWidth: 1, borderColor: colores.alerta },
  botonTexto: { fontSize: 15, fontWeight: '700' },
  botonTexto_lleno: { color: colores.abismo },
  botonTexto_borde: { color: colores.neon },
  botonTexto_peligro: { color: colores.luz },
  campo: {
    height: 54, borderRadius: 14, backgroundColor: colores.superficie, borderWidth: 1, borderColor: colores.apagado,
    color: colores.luz, fontSize: 18, paddingHorizontal: 16, letterSpacing: 3,
  },
  barra: { height: 6, borderRadius: 3, backgroundColor: colores.apagado, overflow: 'hidden' },
  barraLlena: { height: 6, borderRadius: 3 },
});
