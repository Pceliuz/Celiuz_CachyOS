// Hablar con la PC: remoto/PROTOCOLO.md en codigo. TypeScript puro (sin React
// Native), con fetch y WebSocket INYECTADOS: en el celular son los de React
// Native, y en las pruebas los de Node contra el servidor de verdad.
//
// Dos cosas que no se notan leyendo y si al usarlo:
//  - Todo lleva tiempo maximo. Un fetch a una IP de Tailscale que no contesta
//    (la PC apagada) no falla: se queda colgado un minuto largo.
//  - El WebSocket lleva el token en una cabecera. React Native la admite como
//    tercer argumento del constructor (no es estandar); por eso lo crea quien
//    llama, con `abrirSocket`.
import { firmar } from './cripto.ts';
import {
  CIERRE_SIN_SESION,
  PUERTO_RED,
  PUERTO_USB,
  type CodigoError,
  type Emparejado,
  type Equipo,
  type Estado,
  type Hola,
  type Sesion,
} from './protocolo.ts';

export const ESPERA_MS = 8000;

export class ErrorRemoto extends Error {
  codigo: CodigoError | 'red' | 'respuesta';
  http: number;
  intentosRestantes?: number;

  constructor(codigo: ErrorRemoto['codigo'], mensaje: string, http = 0, intentos?: number) {
    super(mensaje);
    this.codigo = codigo;
    this.http = http;
    this.intentosRestantes = intentos;
  }
}

// Lo minimo de un WebSocket que se usa aqui: lo cumplen el de React Native y
// el de Node.
export interface Socket {
  onmessage: ((ev: { data: unknown }) => void) | null;
  onclose: ((ev: { code: number; reason?: string }) => void) | null;
  onerror: ((ev: unknown) => void) | null;
  close(code?: number): void;
}

export interface Herramientas {
  fetch: typeof fetch;
  abrirSocket: (url: string, cabeceras: Record<string, string>) => Socket;
}

// Lo que el celular guarda de cada equipo emparejado (sin la clave: esa va
// aparte, en el almacen seguro).
export interface EquipoGuardado {
  dispositivo: string;
  equipo: string;
  direccion: string; // IP de Tailscale:puerto
  permisos: string[];
  pase_hasta: string | null; // lo ultimo que dijo la PC (solo para enseñarlo)
}

async function pedir<T>(
  h: Herramientas,
  metodo: string,
  url: string,
  cuerpo?: unknown,
  token?: string,
  espera = ESPERA_MS,
): Promise<T> {
  const control = new AbortController();
  const reloj = setTimeout(() => control.abort(), espera);
  let r: Response;
  try {
    const cabeceras: Record<string, string> = {};
    if (cuerpo !== undefined) cabeceras['Content-Type'] = 'application/json';
    if (token) cabeceras.Authorization = `Bearer ${token}`;
    r = await h.fetch(url, {
      method: metodo,
      headers: cabeceras,
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
      signal: control.signal,
    });
  } catch {
    throw new ErrorRemoto('red', 'No llego a la PC. ¿Está encendida, con el servicio activo y Tailscale conectado en los dos?');
  } finally {
    clearTimeout(reloj);
  }
  let datos: any;
  try {
    datos = await r.json();
  } catch {
    throw new ErrorRemoto('respuesta', `La PC contestó algo que no entiendo (HTTP ${r.status}).`, r.status);
  }
  if (!r.ok) {
    throw new ErrorRemoto(datos?.error ?? 'respuesta', datos?.mensaje ?? `HTTP ${r.status}`, r.status, datos?.intentos_restantes);
  }
  return datos as T;
}

// --- El canal USB (solo con el cable puesto y la ventana de la PC abierta) ---

export const urlUsb = (puerto: number) => `http://127.0.0.1:${puerto}`;

export function hola(h: Herramientas, puerto: number): Promise<Hola> {
  return pedir<Hola>(h, 'GET', `${urlUsb(puerto)}/usb/hola`, undefined, undefined, 4000);
}

export function emparejar(h: Herramientas, puerto: number, codigo: string, clave: string,
                          publica: string, nombre: string): Promise<Emparejado> {
  return pedir<Emparejado>(h, 'POST', `${urlUsb(puerto)}/usb/emparejar`, {
    codigo, nombre, publica, firma: firmar(clave, 'emparejar', codigo),
  });
}

export function renovar(h: Herramientas, puerto: number, codigo: string, clave: string,
                        dispositivo: string, contrasena: string): Promise<{ pase_hasta: string }> {
  return pedir(h, 'POST', `${urlUsb(puerto)}/usb/renovar`, {
    codigo, dispositivo, contrasena, firma: firmar(clave, 'renovar', codigo),
  });
}

// --- La red (por Tailscale) ---

export const urlRed = (direccion: string) =>
  `http://${direccion.includes(':') ? direccion : `${direccion}:${PUERTO_RED}`}`;

export class Conexion {
  private h: Herramientas;
  readonly equipo: EquipoGuardado;
  readonly sesion: Sesion;

  constructor(h: Herramientas, equipo: EquipoGuardado, sesion: Sesion) {
    this.h = h;
    this.equipo = equipo;
    this.sesion = sesion;
  }

  get base() {
    return urlRed(this.equipo.direccion);
  }

  datosEquipo(): Promise<Equipo> {
    return pedir<Equipo>(this.h, 'GET', `${this.base}/v0/equipo`, undefined, this.sesion.token);
  }

  // Cada segundo, el estado. Devuelve como cerrarlo. `alCerrar` dice si fue
  // porque caduco la sesion (hay que volver a entrar) o por otra cosa.
  vivo(alEstado: (e: Estado) => void, alCerrar: (sesionCaducada: boolean) => void): () => void {
    const url = this.base.replace(/^http/, 'ws') + '/v0/vivo';
    const s = this.h.abrirSocket(url, { Authorization: `Bearer ${this.sesion.token}` });
    let cerrado = false;
    s.onmessage = (ev) => {
      try {
        alEstado(JSON.parse(String(ev.data)) as Estado);
      } catch {
        /* un mensaje roto no tumba la pantalla */
      }
    };
    s.onclose = (ev) => {
      if (!cerrado) alCerrar(ev.code === CIERRE_SIN_SESION);
      cerrado = true;
    };
    s.onerror = () => {};
    return () => {
      cerrado = true;
      s.close(1000);
    };
  }

  async salir(): Promise<void> {
    try {
      await pedir(this.h, 'DELETE', `${this.base}/v0/sesion`, undefined, this.sesion.token, 3000);
    } catch {
      /* salir es de mejor esfuerzo: el token caduca solo */
    }
  }
}

export async function entrar(h: Herramientas, equipo: EquipoGuardado, clave: string,
                             contrasena: string): Promise<Conexion> {
  const base = urlRed(equipo.direccion);
  const { reto } = await pedir<{ reto: string }>(
    h, 'GET', `${base}/v0/reto?dispositivo=${encodeURIComponent(equipo.dispositivo)}`);
  const sesion = await pedir<Sesion>(h, 'POST', `${base}/v0/sesion`, {
    dispositivo: equipo.dispositivo, reto, firma: firmar(clave, 'sesion', reto), contrasena,
  });
  return new Conexion(h, equipo, sesion);
}

// ¿Contesta? Para el «En línea / Apagada» de la pantalla de entrar. Pide un
// reto (no gasta nada ni dice si el id existe: PROTOCOLO.md).
export async function enLinea(h: Herramientas, equipo: EquipoGuardado): Promise<number | null> {
  const t0 = Date.now();
  try {
    await pedir(h, 'GET', `${urlRed(equipo.direccion)}/v0/reto?dispositivo=${encodeURIComponent(equipo.dispositivo)}`,
                undefined, undefined, 3000);
    return Date.now() - t0;
  } catch {
    return null;
  }
}

// El enlace con que la PC abre la app por el cable:
//   celiuzremoto://emparejar/<codigo>?p=<puerto USB>
export interface Enlace {
  modo: 'emparejar' | 'renovar';
  codigo: string;
  puerto: number;
}

export function leerEnlace(url: string | null | undefined): Enlace | null {
  if (!url) return null;
  const m = /^celiuzremoto:\/\/(emparejar|renovar)\/([A-Za-z0-9_-]{16,128})(?:\?p=(\d{4,5}))?$/.exec(url);
  if (!m) return null;
  const puerto = m[3] ? Number(m[3]) : PUERTO_USB;
  if (puerto < 1024 || puerto > 65535) return null;
  return { modo: m[1] as Enlace['modo'], codigo: m[2], puerto };
}
