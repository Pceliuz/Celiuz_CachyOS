// Los tipos de lo que se dicen la app y la PC. Es remoto/PROTOCOLO.md en
// TypeScript: si cambia alli, cambia aqui (y en servidor/).

export const VERSION_PROTOCOLO = 0;
export const PUERTO_RED = 47110;
export const PUERTO_USB = 47111;

export type Permiso = 'estado' | 'energia' | 'ventanas' | 'archivos' | 'terminal' | 'pantalla';

export type CodigoError =
  | 'peticion'
  | 'sin_sesion'
  | 'firma'
  | 'contrasena'
  | 'bloqueado'
  | 'sin_permiso'
  | 'no_existe'
  | 'confirmar'
  | 'estado' // no toca ahora (fase 5: entrar con la sesion abierta)
  | 'fuera' // sale de la carpeta personal, o es de lo que nunca se enseña (fase 6)
  | 'pase_vencido';

// Lo que se firma con la clave privada Ed25519 del telefono: siempre con
// prefijo, para que la firma de una cosa no valga para otra.
export const PREFIJO_FIRMA = 'celiuz-remoto/v0/';
export type Firmable = 'sesion' | 'emparejar' | 'renovar' | 'invitacion';
export const textoFirmado = (para: Firmable, dato: string) => `${PREFIJO_FIRMA}${para}:${dato}`;

// El WebSocket /v0/vivo se cierra con este codigo cuando caduca la sesion.
export const CIERRE_SIN_SESION = 4401;

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
  equipo: string;
}

export interface Equipo {
  nombre: string;
  tipo: 'portatil' | 'escritorio';
  cpu: string | null;
  gpus: string[];
  ram: number; // GiB
  bateria: boolean;
  protocolo: number;
  cuenta_atras: number; // segundos de aviso en la PC antes de apagar
  despertar?: Despertar; // fase 8: como despertar a ESTE equipo desde otro
}

// Wake-on-LAN (fase 8): la MAC de la tarjeta de cable y si tiene pinta de poder.
export interface Despertar {
  mac: string | null;
  tarjeta: string | null;
  wol: 'si' | 'no' | 'no_lo_se';
  motivo: string;
}

export interface Gpu {
  nombre: string;
  uso?: number; // no lo da una Intel integrada
  temp?: number; // solo si la tarjeta tiene sensor
  vram?: [number, number]; // solo si es dedicada: [usada, total] en GiB
  dormida?: boolean; // la dedicada de un portatil hibrido: no se mide
}

// Lo que llega cada segundo por /v0/vivo. Solo trae lo que el equipo tiene.
export interface Estado {
  cpu: { uso: number; temp?: number };
  gpu: Gpu[];
  ram: [number, number]; // GiB
  disco: [number, number]; // GiB
  red: { bajada: number; subida: number }; // bytes por segundo
  bateria: { nivel: number; cargando: boolean } | null;
  encendida_desde: string;
  pase_hasta: string | null;
  vigilancia: 'desarmada' | 'sin_telefonos' | 'armada' | 'avisando' | 'jugando' | 'apagando';
  energia: EstadoEnergia | null; // una cuenta atras en marcha
  escritorio?: Escritorio; // desde la fase 5 (un servidor viejo no lo manda)
}

// ¿Hay sesion abierta, o la PC esta en la pantalla de inicio (tras reiniciar)?
// «no_lo_se» no es «pantalla_inicio»: con eso no se ofrece entrar.
export interface Escritorio {
  sesion: 'abierta' | 'pantalla_inicio' | 'no_lo_se';
  puede_entrar: boolean; // en la pantalla de inicio y con lo de root instalado
  motivo: string; // lo que se enseña si no se puede
}

export interface EstadoEnergia {
  accion: AccionEnergia;
  quedan: number; // segundos
  hasta: string; // ISO, con el reloj de la PC
  origen: string; // el nombre del telefono que lo pidio, o «pc»
}

// El canal USB (por adb reverse), solo mientras la app de la PC lo abre.
export interface Hola {
  modo: 'emparejar' | 'renovar';
  equipo: string;
}

export interface Emparejado {
  dispositivo: string;
  equipo: string;
  direccion: string; // IP de Tailscale:puerto
  permisos: Permiso[];
  pase_hasta: string; // emparejar da el pase de 24 h
  expira?: string; // solo por invitación (fase 8): a esta hora deja de valer
}

export type AccionEnergia = 'apagar' | 'reiniciar' | 'suspender';

export interface Ventana {
  id: string;
  app: string;
  titulo: string;
  escritorio: string | number;
}

// Archivos (fase 6). Las rutas son relativas a la carpeta personal de la PC
// ("" es la carpeta personal).
export interface Entrada {
  nombre: string;
  tipo: 'carpeta' | 'archivo';
  tamano?: number; // solo archivos, en bytes
  elementos?: number | null; // solo carpetas
  modificado: string; // ISO, con el reloj de la PC
  favorito?: boolean; // en /v0/archivos
  ruta?: string; // en /v0/archivos/buscar: la ruta entera
}

export interface Listado {
  ruta: string;
  entradas: Entrada[];
  truncado: boolean; // la carpeta tiene mas de las que caben
}

export interface Busqueda {
  ruta: string;
  q: string;
  resultados: (Entrada & { ruta: string })[];
  truncado: boolean;
}

export interface Reciente {
  ruta: string;
  nombre: string;
  carpeta: string;
  bajado: string;
  tamano: number;
  dispositivo: string; // el telefono que lo bajo
  estado: 'igual' | 'nueva_version' | 'no_esta'; // contra lo que hay AHORA en la PC
}

// La ficha de un vídeo (GET /v0/archivos/video, conversion.py): con ella el
// celular decide si su decodificador puede, o pide una conversión.
export interface FichaVideo {
  contenedor: string; // el format_name de ffprobe: «mov,mp4,m4a,3gp,3g2,mj2», «matroska,webm», «avi»
  duracion: number;
  video: { codec: string; mime: string; perfil: string; ancho: number; alto: number; fps: number; rotacion: number };
  audio: { codec: string; mime: string } | null;
}

export interface Conversion {
  id: string;
  estado: 'en_cola' | 'convirtiendo' | 'listo' | 'error' | 'cancelado';
  progreso: number; // 0..1
  nombre: string; // «fondo (1080p 60).mp4»
  tamano?: number; // al estar lista
  mensaje?: string;
}

export interface Favorito {
  ruta: string;
  nombre: string;
  tipo: 'carpeta' | 'archivo';
  existe: boolean;
  desde: string;
}

// Una terminal abierta en la PC (terminal.py, `Sesion.ficha`). `desde` en
// segundos de época; `titulo`, lo que corre delante (fish, claude, vim...);
// `mirando`, si hay una pantalla enganchada ahora mismo.
export interface FichaTerminal {
  id: string;
  numero: number;
  desde: number;
  titulo: string;
  mirando: boolean;
}
