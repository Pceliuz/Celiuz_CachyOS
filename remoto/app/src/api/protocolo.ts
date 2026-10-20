// Los tipos de lo que se dicen la app y la PC. Es remoto/PROTOCOLO.md en
// TypeScript: si cambia alli, cambia aqui (y en servidor/).

export const VERSION_PROTOCOLO = 0;
export const PUERTO_RED = 47110;
export const PUERTO_USB = 47111;

export type Permiso = 'estado' | 'energia' | 'ventanas' | 'archivos' | 'terminal';

export type CodigoError =
  | 'sin_sesion'
  | 'contrasena'
  | 'bloqueado'
  | 'sin_permiso'
  | 'pase_vencido'
  | 'confirmar';

export interface ErrorRemoto {
  error: CodigoError;
  mensaje: string;
  intentos_restantes?: number;
}

export interface Sesion {
  token: string;
  caduca_en: number; // segundos sin uso
  pase_hasta: string | null; // ISO 8601, con el reloj de la PC
  permisos: Permiso[];
}

export interface Gpu {
  nombre: string;
  uso: number;
  temp?: number; // solo si la tarjeta tiene sensor
  vram?: [number, number]; // solo si es dedicada: [usada, total] en GB
}

// Lo que llega cada segundo por /v0/vivo. Solo trae lo que el equipo tiene.
export interface Estado {
  cpu: { uso: number; temp?: number };
  gpu: Gpu[];
  ram: [number, number];
  disco: [number, number];
  red: { bajada: number; subida: number }; // bytes por segundo
  bateria: { nivel: number; cargando: boolean } | null;
  encendida_desde: string;
  pase_hasta: string | null;
  vigilancia: 'armada' | 'desarmada' | 'avisando';
}

export type AccionEnergia = 'apagar' | 'reiniciar' | 'suspender';

export interface Ventana {
  id: string;
  app: string;
  titulo: string;
  escritorio: number;
}

export interface Entrada {
  nombre: string;
  tipo: 'carpeta' | 'archivo';
  tamano: number;
  modificado: string;
}

export interface Reciente {
  ruta: string;
  bajado: string;
  tamano: number;
  estado: 'igual' | 'nueva_version' | 'no_esta';
}
