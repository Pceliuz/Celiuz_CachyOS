// El modulo nativo de Celiuz Remoto (android/.../CeliuzNativoModule.kt):
// guardar lo bajado donde lo ven las demas apps del celular (la galeria, Google
// Fotos, el explorador de archivos), abrirlo con la app que tenga el celular
// para ese tipo, y compartirlo. Sin el modulo (en Node, en las pruebas),
// `disponible` es false y nadie lo llama.
import { requireOptionalNativeModule } from 'expo';

export interface Guardado {
  uri: string; // content://media/... : lo que se le pasa a otra app
  carpeta: string; // donde lo vera la persona: «Pictures/Celiuz Remoto»
}

interface Nativo {
  guardarPublico(origen: string, nombre: string, mime: string, sustituir: string | null): Promise<Guardado>;
  existe(uri: string): boolean;
  // ¿Lo decodifica el celular por hardware a esa velocidad? (mime de Android:
  // «video/avc», «video/hevc»...)
  puedeVideo(mime: string, ancho: number, alto: number, fps: number): boolean;
  puedeAudio(mime: string): boolean;
  abrir(uri: string, mime: string): Promise<boolean>;
  compartir(uri: string, mime: string, titulo: string): Promise<void>;
  borrar(uri: string): Promise<boolean>;
  leerTexto(uri: string, maximo: number): Promise<string>;
}

const nativo = requireOptionalNativeModule<Nativo>('CeliuzNativo');
export const disponible = nativo !== null;
export default nativo as Nativo;
