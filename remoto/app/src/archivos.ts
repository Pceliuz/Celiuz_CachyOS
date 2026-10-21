// Las cuentas del explorador (fase 6), sin React Native: se prueban con Node
// (tests/lib/app_remoto.ts). Lo que pinta, en pantallas/Archivos.tsx y
// pantallas/Recientes.tsx; lo que baja, en descargas.ts.
import type { Reciente } from './api/protocolo.ts';
import { decimal } from './formato.ts';

// «48 KB», «1,2 MB», «8,4 GB». En base 1024, como Dolphin.
export function tamano(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return '';
  if (bytes < 1024) return `${bytes} B`;
  const unidades = ['KB', 'MB', 'GB', 'TB'];
  let n = bytes / 1024;
  let i = 0;
  while (n >= 1024 && i < unidades.length - 1) { n /= 1024; i += 1; }
  return `${decimal(n, n < 10 && i > 0 ? 1 : 0)} ${unidades[i]}`;
}

// Las migas de pan: [{nombre, ruta}] desde la carpeta personal.
export function migas(ruta: string, casa = 'Inicio'): { nombre: string; ruta: string }[] {
  const partes = ruta.split('/').filter(Boolean);
  return [{ nombre: casa, ruta: '' },
          ...partes.map((p, i) => ({ nombre: p, ruta: partes.slice(0, i + 1).join('/') }))];
}

export const unir = (carpeta: string, nombre: string) => (carpeta ? `${carpeta}/${nombre}` : nombre);
export const padre = (ruta: string) => ruta.split('/').filter(Boolean).slice(0, -1).join('/');

// Para el icono y su color (los de la maqueta 5).
export type Clase = 'carpeta' | 'imagen' | 'video' | 'audio' | 'pdf' | 'documento' | 'hoja' | 'presentacion'
  | 'comprimido' | 'codigo' | 'otro';
const EXTENSIONES: Record<string, Clase> = {};
const poner = (c: Clase, ex: string) => ex.split(' ').forEach((e) => { EXTENSIONES[e] = c; });
poner('imagen', 'jpg jpeg png webp gif bmp avif tif tiff heic svg');
poner('video', 'mp4 mkv webm mov avi m4v');
poner('audio', 'mp3 flac ogg opus wav m4a aac');
poner('pdf', 'pdf');
poner('documento', 'doc docx odt rtf txt md');
poner('hoja', 'xls xlsx ods csv');
poner('presentacion', 'ppt pptx odp');
poner('comprimido', 'zip rar 7z tar gz xz zst bz2');
poner('codigo', 'py ts tsx js json sh lua conf toml yaml yml html css c h cpp rs go');

export function extension(nombre: string): string {
  const i = nombre.lastIndexOf('.');
  return i > 0 ? nombre.slice(i + 1).toLowerCase() : '';
}

export function clase(nombre: string, tipo: 'carpeta' | 'archivo' = 'archivo'): Clase {
  if (tipo === 'carpeta') return 'carpeta';
  return EXTENSIONES[extension(nombre)] ?? 'otro';
}

// Lo que el servidor sabe convertir en miniatura (archivos.py: IMAGENES y VIDEOS).
export const tieneMiniatura = (nombre: string) =>
  ['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp', 'avif', 'tif', 'tiff', 'heic', 'mp4', 'mkv', 'webm', 'mov', 'avi', 'm4v']
    .includes(extension(nombre));

// El tipo MIME para abrirlo con otra app del celular.
const MIMES: Record<string, string> = {
  pdf: 'application/pdf', jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', webp: 'image/webp',
  gif: 'image/gif', mp4: 'video/mp4', mkv: 'video/x-matroska', webm: 'video/webm', mov: 'video/quicktime',
  mp3: 'audio/mpeg', flac: 'audio/flac', ogg: 'audio/ogg', opus: 'audio/opus', wav: 'audio/wav', m4a: 'audio/mp4',
  txt: 'text/plain', md: 'text/markdown', csv: 'text/csv', html: 'text/html', json: 'application/json',
  zip: 'application/zip', doc: 'application/msword',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  xls: 'application/vnd.ms-excel', xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  ppt: 'application/vnd.ms-powerpoint',
  pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  odt: 'application/vnd.oasis.opendocument.text', ods: 'application/vnd.oasis.opendocument.spreadsheet',
  odp: 'application/vnd.oasis.opendocument.presentation', apk: 'application/vnd.android.package-archive',
};
export const mime = (nombre: string) => MIMES[extension(nombre)] ?? 'application/octet-stream';

// La clave de una copia guardada en el celular (descargas.ts): el equipo y la
// ruta de la PC. Dos PCs pueden tener cada una su Documentos/nota.txt.
export const claveGuardado = (equipo: string, ruta: string) => `${equipo}\u0000${ruta}`;

// Lo que la app sabe enseñar ella misma, sin tener una app de markdown en el
// celular (el usuario no tenía ninguna para un .md).
const TEXTO = new Set('txt md markdown csv json log conf ini toml yaml yml lua py sh ts tsx js css html xml desktop service srt'.split(' '));
export const esTexto = (nombre: string) => TEXTO.has(extension(nombre)) || /^\.?[A-Za-z0-9_-]+rc$/.test(nombre);

// Recientes agrupados como en la maqueta 6: Hoy, Ayer, Esta semana, Antes. El
// día se cuenta en la zona de la PC (el ISO lleva su desfase), no en UTC.
export type Grupo = 'Hoy' | 'Ayer' | 'Esta semana' | 'Antes';
function diaLocal(iso: string): number {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return m ? Date.UTC(+m[1], +m[2] - 1, +m[3]) / 86400000 : 0;
}
export function grupo(bajado: string, ahora: Date, desfaseMin: number | null = null): Grupo {
  // El «hoy» de la PC: la fecha de ahora con el mismo desfase que trae el ISO.
  const m = /([+-])(\d{2}):(\d{2})$/.exec(bajado);
  const desfase = desfaseMin ?? (m ? (m[1] === '-' ? -1 : 1) * (+m[2] * 60 + +m[3]) : 0);
  const hoy = Math.floor((ahora.getTime() / 60000 + desfase) / 1440);
  const dias = hoy - diaLocal(bajado);
  if (dias <= 0) return 'Hoy';
  if (dias === 1) return 'Ayer';
  if (dias < 7) return 'Esta semana';
  return 'Antes';
}

export function agrupar(lista: Reciente[], ahora: Date): { grupo: Grupo; recientes: Reciente[] }[] {
  const orden: Grupo[] = ['Hoy', 'Ayer', 'Esta semana', 'Antes'];
  const mapa = new Map<Grupo, Reciente[]>();
  for (const r of lista) {
    const g = grupo(r.bajado, ahora);
    mapa.set(g, [...(mapa.get(g) ?? []), r]);
  }
  return orden.filter((g) => mapa.has(g)).map((g) => ({ grupo: g, recientes: mapa.get(g)! }));
}

export const TEXTO_ESTADO: Record<Reciente['estado'], string> = {
  igual: 'Igual que en la PC',
  nueva_version: 'Hay versión nueva en la PC',
  no_esta: 'Ya no está en la PC',
};
