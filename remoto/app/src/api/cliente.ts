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
  type AccionEnergia,
  CIERRE_SIN_SESION,
  type EstadoEnergia,
  type Busqueda,
  type Conversion,
  type Favorito,
  type FichaTerminal,
  type FichaVideo,
  type Listado,
  type Reciente,
  type Ventana,
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
  onopen?: (() => void) | null;
  binaryType?: string;
  send?(datos: string | ArrayBuffer): void;
  close(code?: number): void;
}

// La terminal abierta (fase 7): lo que se le manda y como cerrarla.
export interface TerminalAbierta {
  escribir(texto: string): void;
  tamano(filas: number, columnas: number): void;
  cerrar(): void;
}
// Como se cierra una terminal (terminal.py): 4000 la shell salió, 4001 la
// retomó otra pantalla, 4002 la cerraron (o llevaba 1 h sola), 4401 caducó la
// sesión de la app (la terminal SIGUE en la PC) y 4403 se le quitó el pase o
// el permiso. Cualquier otro cierre es la red: la terminal sigue en la PC.
export const TERMINAL_SALIO = 4000;
export const TERMINAL_OTRO = 4001;
export const TERMINAL_CERRADA = 4002;
export const TERMINAL_SIN_SESION = 4401;
export const TERMINAL_SIN_PERMISO = 4403;

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
  mac?: string | null; // fase 8: para despertarlo desde otro equipo de casa
  expira?: string | null; // fase 8: entró por invitación y caduca a esta hora
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

  // Apagar / reiniciar / suspender: empieza la cuenta atras en la PC (con su
  // aviso cancelable). Siempre confirmado: la confirmacion la hace la pantalla.
  async energia(accion: AccionEnergia): Promise<EstadoEnergia> {
    const r = await pedir<{ energia: EstadoEnergia }>(this.h, 'POST', `${this.base}/v0/energia`,
      { accion, confirmado: true }, this.sesion.token);
    return r.energia;
  }

  async cancelarEnergia(): Promise<boolean> {
    const r = await pedir<{ cancelada: boolean }>(this.h, 'DELETE', `${this.base}/v0/energia`,
      undefined, this.sesion.token);
    return r.cancelada;
  }

  // Con la PC en la pantalla de inicio (tras reiniciar): la PC se abre sola
  // con un autologin de un solo uso y la sesion arranca BLOQUEADA. Pide el
  // pase y el permiso de energia; sin pase, ErrorRemoto «pase_vencido».
  async entrarEscritorio(): Promise<string> {
    const r = await pedir<{ mensaje: string }>(this.h, 'POST', `${this.base}/v0/escritorio/entrar`,
      { confirmado: true }, this.sesion.token);
    return r.mensaje;
  }

  // --- archivos (fase 6): todo pide el pase ---

  async archivos(ruta: string, ocultos = false): Promise<Listado> {
    return pedir<Listado>(this.h, 'GET',
      `${this.base}/v0/archivos?ruta=${encodeURIComponent(ruta)}${ocultos ? '&ocultos=1' : ''}`,
      undefined, this.sesion.token);
  }

  // Por nombre, en esa carpeta y sus subcarpetas (al menos dos letras).
  async buscar(ruta: string, q: string): Promise<Busqueda> {
    return pedir<Busqueda>(this.h, 'GET',
      `${this.base}/v0/archivos/buscar?ruta=${encodeURIComponent(ruta)}&q=${encodeURIComponent(q)}`,
      undefined, this.sesion.token, 15000);
  }

  async recientes(): Promise<Reciente[]> {
    return (await pedir<{ recientes: Reciente[] }>(this.h, 'GET', `${this.base}/v0/recientes`,
      undefined, this.sesion.token)).recientes;
  }

  async olvidarReciente(ruta: string): Promise<void> {
    await pedir(this.h, 'DELETE', `${this.base}/v0/recientes?ruta=${encodeURIComponent(ruta)}`,
      undefined, this.sesion.token);
  }

  async favoritos(): Promise<Favorito[]> {
    return (await pedir<{ favoritos: Favorito[] }>(this.h, 'GET', `${this.base}/v0/favoritos`,
      undefined, this.sesion.token)).favoritos;
  }

  async fijar(ruta: string): Promise<Favorito[]> {
    return (await pedir<{ favoritos: Favorito[] }>(this.h, 'PUT', `${this.base}/v0/favoritos`,
      { ruta }, this.sesion.token)).favoritos;
  }

  async soltar(ruta: string): Promise<Favorito[]> {
    return (await pedir<{ favoritos: Favorito[] }>(this.h, 'DELETE',
      `${this.base}/v0/favoritos?ruta=${encodeURIComponent(ruta)}`, undefined, this.sesion.token)).favoritos;
  }

  // --- vídeos que el celular no puede reproducir (conversion.py) ---

  async fichaVideo(ruta: string): Promise<FichaVideo> {
    return pedir<FichaVideo>(this.h, 'GET', `${this.base}/v0/archivos/video?ruta=${encodeURIComponent(ruta)}`,
      undefined, this.sesion.token, 20000);
  }

  // Empieza (o retoma, si ya estaba) la conversión al lado corto y los fps dados.
  async convertir(ruta: string, lado: number, fps: number): Promise<Conversion> {
    return pedir<Conversion>(this.h, 'POST', `${this.base}/v0/archivos/convertir`,
      { ruta, lado, fps }, this.sesion.token, 20000);
  }

  // Cómo va. Preguntar es lo que la mantiene viva: sin preguntas, la PC la para.
  async conversion(id: string): Promise<Conversion> {
    return pedir<Conversion>(this.h, 'GET', `${this.base}/v0/archivos/convertir/${encodeURIComponent(id)}`,
      undefined, this.sesion.token);
  }

  async cancelarConversion(id: string): Promise<void> {
    await pedir(this.h, 'DELETE', `${this.base}/v0/archivos/convertir/${encodeURIComponent(id)}`,
      undefined, this.sesion.token);
  }

  // --- terminal (fase 7): pase, permiso de terminal y la contraseña OTRA VEZ ---

  // Devuelve el billete (vale 30 s y una sola vez) para abrir la terminal.
  async billeteTerminal(contrasena: string): Promise<string> {
    return (await pedir<{ terminal: string }>(this.h, 'POST', `${this.base}/v0/terminal`,
      { contrasena }, this.sesion.token)).terminal;
  }

  // Las terminales de ESTE celular que siguen abiertas en la PC (minimizadas o
  // que se cortaron), y cuántas caben como mucho entre todos.
  async terminales(): Promise<{ terminales: FichaTerminal[]; max: number }> {
    return pedir(this.h, 'GET', `${this.base}/v0/terminales`, undefined, this.sesion.token);
  }

  // Cerrarla de verdad (la shell y lo que corra en ella).
  async cerrarTerminal(id: string): Promise<FichaTerminal[]> {
    return (await pedir<{ terminales: FichaTerminal[] }>(this.h, 'DELETE',
      `${this.base}/v0/terminales/${encodeURIComponent(id)}`, undefined, this.sesion.token)).terminales;
  }

  // Abre una terminal nueva (con el billete) o retoma una abierta (con su id,
  // sin contraseña). Lo primero que llega es su ficha, en texto, a `alFicha`;
  // después, en bytes, lo que sale de la shell (al retomarla, primero lo que
  // salió mientras nadie miraba). Se escribe en texto (UTF-8).
  terminal(destino: { billete: string } | { retomar: string }, filas: number, columnas: number,
           alDatos: (b: Uint8Array) => void, alCerrar: (codigo: number, motivo: string) => void,
           alFicha: (f: FichaTerminal) => void = () => {}): TerminalAbierta {
    const ruta = 'billete' in destino ? `terminal/${encodeURIComponent(destino.billete)}`
      : `terminales/${encodeURIComponent(destino.retomar)}`;
    const url = `${this.base.replace(/^http/, 'ws')}/v0/${ruta}?filas=${filas}&columnas=${columnas}`;
    const s = this.h.abrirSocket(url, { Authorization: `Bearer ${this.sesion.token}` });
    s.binaryType = 'arraybuffer';
    const pendiente: string[] = [];
    let abierta = false;
    let cerrada = false;
    const mandar = (m: string) => (abierta ? s.send?.(m) : pendiente.push(m));
    s.onopen = () => {
      abierta = true;
      for (const m of pendiente.splice(0)) s.send?.(m);
    };
    s.onmessage = (ev) => {
      const d = ev.data;
      if (d instanceof ArrayBuffer) alDatos(new Uint8Array(d));
      else if (typeof d === 'string') {
        let ficha: FichaTerminal | undefined;
        try { ficha = (JSON.parse(d) as { terminal?: FichaTerminal }).terminal; } catch { /* no es JSON */ }
        if (ficha) alFicha(ficha);
        else alDatos(new TextEncoder().encode(d));
      }
    };
    s.onclose = (ev) => {
      if (!cerrada) alCerrar(ev.code, ev.reason ?? '');
      cerrada = true;
    };
    s.onerror = () => {};
    return {
      escribir: (texto) => mandar(JSON.stringify({ texto })),
      tamano: (f, c) => mandar(JSON.stringify({ tamano: [f, c] })),
      cerrar: () => { cerrada = true; s.close(1000); },
    };
  }

  // --- escritorio remoto (fase 8): permiso de pantalla, pase y la contraseña otra vez ---

  async billetePantalla(contrasena: string): Promise<string> {
    return (await pedir<{ pantalla: string }>(this.h, 'POST', `${this.base}/v0/pantalla`,
      { contrasena }, this.sesion.token)).pantalla;
  }

  // La abre la página del WebView (noVNC), que no puede poner cabeceras: la
  // llave es el billete, de un solo uso.
  urlPantalla(billete: string): string {
    return `${this.base.replace(/^http/, 'ws')}/v0/pantalla/${encodeURIComponent(billete)}`;
  }

  // Lo que bajan otros (el gestor de descargas, <Image>): la URL y la cabecera.
  // Con `conversion`, lo convertido para el celular en vez del original.
  urlDescarga(ruta: string, conversion?: string): string {
    return `${this.base}/v0/archivos/descargar?ruta=${encodeURIComponent(ruta)}`
      + (conversion ? `&conversion=${encodeURIComponent(conversion)}` : '');
  }

  // Subir (fase 8): el cuerpo es el archivo tal cual; la PC lo deja en
  // <Descargas>/Celiuz Remoto y nunca pisa nada.
  urlSubir(nombre: string): string {
    return `${this.base}/v0/archivos/subir?nombre=${encodeURIComponent(nombre)}`;
  }

  urlMiniatura(ruta: string, lado = 256): string {
    return `${this.base}/v0/archivos/miniatura?ruta=${encodeURIComponent(ruta)}&lado=${lado}`;
  }

  cabeceras(): Record<string, string> {
    return { Authorization: `Bearer ${this.sesion.token}` };
  }

  // Despertar a OTRO equipo de la red de casa (Wake-on-LAN, fase 8): lo
  // manda ESTE, que está encendido. Permiso de energía, sin pase.
  async despertar(mac: string): Promise<boolean> {
    return (await pedir<{ enviado: boolean }>(this.h, 'POST', `${this.base}/v0/despertar`,
      { mac, confirmado: true }, this.sesion.token)).enviado;
  }

  async ventanas(): Promise<Ventana[]> {
    const r = await pedir<{ ventanas: Ventana[] }>(this.h, 'GET', `${this.base}/v0/ventanas`,
      undefined, this.sesion.token);
    return r.ventanas;
  }

  // Pide el pase: sin el, ErrorRemoto con codigo «pase_vencido» (423).
  async cerrarVentana(id: string): Promise<void> {
    await pedir(this.h, 'POST', `${this.base}/v0/ventanas/${encodeURIComponent(id)}/cerrar`,
      { confirmado: true }, this.sesion.token);
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

// --- ayudar a un amigo (fase 8): entrar SIN cable con una invitación ---

export interface Invitacion { direccion: string; codigo: string }

// Lo que manda el amigo, pegado tal cual (el texto de su PC, de WhatsApp...):
// la dirección de Tailscale con su puerto, y el código de 16 letras. El código
// se normaliza (sin guiones ni espacios, en mayúsculas), que es lo que firma.
export function leerInvitacion(texto: string): Invitacion | null {
  const dir = /\b(100\.\d{1,3}\.\d{1,3}\.\d{1,3}|127\.0\.0\.1):(\d{2,5})\b/.exec(texto);
  const grupos = '([A-Za-z0-9]{4})[- ]?([A-Za-z0-9]{4})[- ]?([A-Za-z0-9]{4})[- ]?([A-Za-z0-9]{4})';
  // Con la etiqueta «Código:» primero (el texto de la PC la lleva); si no, el
  // primer grupo de 16 que no sea de la dirección.
  const cod = new RegExp(`C[óo]digo:?\\s*${grupos}\\b`, 'i').exec(texto)
    ?? new RegExp(`\\b${grupos}\\b`).exec(texto.replace(/(Dirección|Direccion)[^\n]*/i, ''));
  if (!dir || !cod) return null;
  return { direccion: `${dir[1]}:${dir[2]}`, codigo: cod.slice(1, 5).join('').toUpperCase() };
}

export async function aceptarInvitacion(h: Herramientas, inv: Invitacion, clave: string, pub: string,
                                        nombre: string): Promise<Emparejado> {
  return pedir<Emparejado>(h, 'POST', `${urlRed(inv.direccion)}/v0/invitacion`, {
    codigo: inv.codigo, nombre, publica: pub, firma: firmar(clave, 'invitacion', inv.codigo),
  });
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
