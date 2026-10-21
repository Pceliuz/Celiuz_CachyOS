// Como se enseñan los numeros y las fechas en la app: en castellano, con coma
// decimal y sin depender del idioma del celular (Intl en Hermes no siempre
// trae todos los idiomas). TypeScript puro: lo prueban las pruebas con Node.
//
// Todas reciben «ahora» cuando dependen de la hora, para poder probarlas con
// un reloj fijo. Las horas que se enseñan son las de la PC tal como las manda
// (ISO con su zona): el pase lo cuenta la PC, con su reloj.

export function decimal(n: number, cifras = 1): string {
  return n.toFixed(cifras).replace('.', ',').replace(/,0+$/, '');
}

export function gb(n: number): string {
  return n >= 1000 ? `${decimal(n / 1024, 1)} TB` : `${decimal(n, n < 10 ? 1 : 0)} GB`;
}

export function velocidad(bytesPorSegundo: number): string {
  const b = Math.max(0, bytesPorSegundo);
  if (b >= 1e6) return `${decimal(b / 1e6, 1)} MB/s`;
  if (b >= 1e3) return `${Math.round(b / 1e3)} KB/s`;
  return `${Math.round(b)} B/s`;
}

export function duracion(ms: number): string {
  const min = Math.max(0, Math.floor(ms / 60000));
  if (min < 1) return 'menos de 1 min';
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  if (h < 48) return `${h} h ${String(min % 60).padStart(2, '0')} min`;
  return `${Math.floor(h / 24)} días`;
}

// La hora de una fecha ISO tal como la escribio la PC (con SU zona), sin
// pasarla a la del celular: «23:40».
export function horaDe(iso: string): string {
  const m = /T(\d\d):(\d\d)/.exec(iso);
  return m ? `${m[1]}:${m[2]}` : '';
}

function fechaLocal(iso: string): string {
  return iso.slice(0, 10);
}

export function diaDe(iso: string, ahora: Date): string {
  // Se compara la fecha de la PC con la fecha de ahora EN LA ZONA DE LA PC.
  const zona = /([+-]\d\d):?(\d\d)$/.exec(iso);
  const desfase = zona ? (zona[1].startsWith('-') ? -1 : 1) * (Math.abs(Number(zona[1])) * 60 + Number(zona[2])) : 0;
  const ahoraPc = new Date(ahora.getTime() + desfase * 60000).toISOString().slice(0, 10);
  const dias = Math.round((Date.parse(fechaLocal(iso)) - Date.parse(ahoraPc)) / 86400000);
  if (dias === 0) return 'hoy';
  if (dias === 1) return 'mañana';
  if (dias === -1) return 'ayer';
  const [, mes, dia] = fechaLocal(iso).split('-');
  return `el ${dia}/${mes}`;
}

export interface EstadoPase {
  vigente: boolean;
  texto: string; // «vence mañana 23:40», «venció hoy a las 23:40», «sin pase»
  queda: number; // 0..1, para la barra
  restante: string; // «14 h 22 min»
}

export function pase(paseHasta: string | null | undefined, ahora: Date): EstadoPase {
  if (!paseHasta) return { vigente: false, texto: 'sin pase', queda: 0, restante: '' };
  const fin = Date.parse(paseHasta);
  if (Number.isNaN(fin)) return { vigente: false, texto: 'sin pase', queda: 0, restante: '' };
  const falta = fin - ahora.getTime();
  if (falta <= 0) {
    return { vigente: false, texto: `venció ${diaDe(paseHasta, ahora)} a las ${horaDe(paseHasta)}`,
             queda: 0, restante: '' };
  }
  return {
    vigente: true,
    texto: `vence ${diaDe(paseHasta, ahora)} ${horaDe(paseHasta)}`,
    queda: Math.min(1, falta / 86400000),
    restante: duracion(falta),
  };
}

export function desde(iso: string, ahora: Date): string {
  const t = Date.parse(iso);
  return Number.isNaN(t) ? '' : `hace ${duracion(ahora.getTime() - t)}`;
}

// «AMD Ryzen 5 5500» -> «Ryzen»: la tarjeta de la CPU dice la familia.
export function familiaCpu(nombre: string | null | undefined): string {
  if (!nombre) return 'CPU';
  const m = /(Ryzen|Core|Celeron|Pentium|Athlon|Xeon|Threadripper|EPYC|Snapdragon)/i.exec(nombre);
  return m ? m[1] : nombre.split(' ').slice(0, 2).join(' ');
}
