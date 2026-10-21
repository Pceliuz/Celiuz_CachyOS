// El icono de una entrada del explorador: la miniatura que hace la PC si es una
// imagen o un vídeo, y si no un cuadro con el color de su clase y su extensión
// (sin librería de SVG: la app no la lleva y para esto no hace falta).
import { useState } from 'react';
import { Image, View } from 'react-native';

import type { Conexion } from '../api/cliente';
import { clase, extension, tieneMiniatura, type Clase } from '../archivos';
import { colores } from '../paleta';
import { Texto, alfa } from './ui';

const COLOR: Record<Clase, string> = {
  carpeta: colores.amatista, imagen: colores.exito, video: colores.alerta, audio: colores.neon,
  pdf: colores.alerta, documento: colores.luz, hoja: colores.exito, presentacion: colores.atencion,
  comprimido: colores.atencion, codigo: colores.neon, otro: colores.tenue,
};

export default function IconoArchivo({ conexion, ruta, nombre, tipo, lado = 40 }: {
  conexion: Conexion; ruta: string; nombre: string; tipo: 'carpeta' | 'archivo'; lado?: number;
}) {
  const [sinMiniatura, setSinMiniatura] = useState(false);
  const c = clase(nombre, tipo);
  if (tipo === 'archivo' && tieneMiniatura(nombre) && !sinMiniatura) {
    return (
      <Image source={{ uri: conexion.urlMiniatura(ruta, 128), headers: conexion.cabeceras() }}
             onError={() => setSinMiniatura(true)} accessibilityIgnoresInvertColors
             style={{ width: lado, height: lado, borderRadius: 10, backgroundColor: colores.apagado }} />
    );
  }
  if (c === 'carpeta') {
    // Una carpeta dibujada (pestaña + cuerpo): un glifo puede no estar en la
    // fuente del celular (pasó con ⏻ en la fase 4).
    return (
      <View style={{ width: lado, height: lado, alignItems: 'center', justifyContent: 'center' }}>
        <View style={{ width: lado * 0.8, gap: 0 }}>
          <View style={{ width: lado * 0.34, height: lado * 0.12, borderTopLeftRadius: 3, borderTopRightRadius: 3,
                         backgroundColor: COLOR.carpeta }} />
          <View style={{ height: lado * 0.52, borderRadius: 4, borderTopLeftRadius: 0,
                         backgroundColor: alfa(COLOR.carpeta, 0.35), borderWidth: 1.5, borderColor: COLOR.carpeta }} />
        </View>
      </View>
    );
  }
  const texto = (extension(nombre).slice(0, 4) || '·').toUpperCase();
  return (
    <View style={{ width: lado, height: lado, borderRadius: 10, alignItems: 'center', justifyContent: 'center',
                   backgroundColor: alfa(COLOR[c], 0.16), borderWidth: 1, borderColor: alfa(COLOR[c], 0.5) }}>
      <Texto tipo="chico" color={COLOR[c]}>{texto}</Texto>
    </View>
  );
}
