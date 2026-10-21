// Terminal (pantalla 7 de las maquetas): la shell de la PC, con sudo.
//
// Pide lo que más pide el remoto (remoto/DISEÑO.md, «Terminal con sudo»): el
// permiso de terminal de este celular (se da en la PC), el pase de 24 h y la
// contraseña de la app OTRA VEZ, aunque ya se haya entrado. La de sudo se
// escribe dentro de la terminal y va directa a sudo: ni la app ni la PC la
// guardan.
//
// La terminal la pinta xterm.js dentro de un WebView (src/terminal/
// pagina.generada.ts, sin red). El WebSocket lo abre React Native, no la
// página: así lleva el token en la cabecera, como /v0/vivo. Lo que sale de la
// shell entra a la página por injectJavaScript (en base64) y lo que se teclea
// sale por postMessage.
//
// LO TECLEADO NO PASA POR XTERM: va por un TextInput nativo invisible con
// keyboardType="visible-password", que hace que el teclado mande cada letra sin
// componer palabras ni autocorregir. Por el textarea de xterm, Gboard mandaba lo
// compuesto repetido («echo hola» llegaba «echchho hholla», medido en el HONOR).
// El campo guarda siempre CENTINELA: lo que crece es lo tecleado, y lo que
// mengua son borrados (DEL).
//
// El teclado del celular no tiene Esc, Tab, Ctrl ni flechas: van en la fila de
// abajo. Ctrl y Alt se quedan puestos hasta la siguiente tecla.
//
// VARIAS, Y SE MINIMIZAN (el usuario, 2026-10-21): la terminal vive en la PC
// (terminal.py, `Sesion`), no en esta pantalla. «Minimizar», «Atrás», cambiar
// de pestaña o perder la red solo la SUELTAN: sigue corriendo y se retoma
// desde la lista, sin contraseña, con lo que salió mientras tanto. Solo
// «Cerrar» la mata. Si se corta la red, se reintenta sola unas veces. Cada vez
// que se engancha se monta un xterm NUEVO (la `clave` del WebView): la PC le
// repinta lo guardado, así que un xterm viejo lo enseñaría dos veces.
import { type ComponentType, type Ref, useCallback, useEffect, useRef, useState } from 'react';
import { Keyboard, Pressable, ScrollView, TextInput, View } from 'react-native';
import { WebView as WebViewOriginal } from 'react-native-webview';

import {
  ErrorRemoto, TERMINAL_CERRADA, TERMINAL_OTRO, TERMINAL_SALIO, TERMINAL_SIN_PERMISO, TERMINAL_SIN_SESION,
  type Conexion, type TerminalAbierta,
} from '../api/cliente';
import { aBase64 } from '../api/cripto';
import type { FichaTerminal } from '../api/protocolo';
import { duracion } from '../formato';
import { colores } from '../paleta';
import pagina from '../terminal/pagina.generada';
import Pestanas, { type Pestana } from '../componentes/Pestanas';
import { Aviso, Boton, Campo, Pantalla, Tarjeta, Texto, fondoRojo } from '../componentes/ui';

// react-native-webview 14 trae tipos de clase que React 19 no acepta (el
// componente sale como `never`): se le da el tipo de lo que se usa aqui.
interface Web { injectJavaScript(js: string): void }
const WebView = WebViewOriginal as unknown as ComponentType<{
  ref?: Ref<Web>; originWhitelist?: string[]; source: { html: string }; javaScriptEnabled?: boolean;
  onMessage?: (ev: { nativeEvent: { data: string } }) => void; style?: object;
  keyboardDisplayRequiresUserAction?: boolean; hideKeyboardAccessoryView?: boolean;
  setSupportMultipleWindows?: boolean; allowFileAccess?: boolean;
}>;

const CENTINELA = '··';
const REINTENTOS = 3;        // si se corta la red con la terminal abierta
const REINTENTO_MS = 2000;

// Por qué se cerró, dicho para una persona. null: fue la red (se reintenta).
export function porQueSeCerro(codigo: number): string | null {
  if (codigo === TERMINAL_SALIO) return 'La shell terminó.';
  if (codigo === TERMINAL_CERRADA) return 'Se cerró la terminal (la cerraste, o llevaba 1 h sin nadie mirándola).';
  if (codigo === TERMINAL_SIN_PERMISO) return 'Se cerró: a este celular se le quitó el pase o el permiso de terminal.';
  if (codigo === TERMINAL_OTRO) return 'La abriste en otra pantalla. Sigue abierta en la PC.';
  return null;
}

// «Terminal 1 · claude», y «abierta hace 12 min».
export function nombreTerminal(f: FichaTerminal): string {
  return f.titulo ? `Terminal ${f.numero} · ${f.titulo}` : `Terminal ${f.numero}`;
}
export function abiertaHace(f: FichaTerminal, ahora: number): string {
  return `abierta hace ${duracion(Math.max(0, ahora - f.desde * 1000))}`;
}

type Destino = { billete: string } | { retomar: string };

// Ctrl+letra es la letra menos 64 (Ctrl+C = 0x03); Alt+x es Esc y x.
export function conModificadores(t: string, ctrl: boolean, alt: boolean): string {
  let s = t;
  if (ctrl && s.length === 1) {
    const k = s.toUpperCase().charCodeAt(0);
    if (k >= 64 && k <= 95) s = String.fromCharCode(k - 64);
    else if (s === ' ') s = '\x00';
  }
  return alt ? `\x1b${s}` : s;
}

const TECLAS: { etiqueta: string; envia?: string; mod?: 'ctrl' | 'alt' }[] = [
  { etiqueta: 'Esc', envia: '\x1b' }, { etiqueta: 'Tab', envia: '\t' },
  { etiqueta: 'Ctrl', mod: 'ctrl' }, { etiqueta: 'Alt', mod: 'alt' },
  { etiqueta: '←', envia: '\x1b[D' }, { etiqueta: '↑', envia: '\x1b[A' },
  { etiqueta: '↓', envia: '\x1b[B' }, { etiqueta: '→', envia: '\x1b[C' },
  { etiqueta: '|', envia: '|' }, { etiqueta: '~', envia: '~' }, { etiqueta: '/', envia: '/' },
  { etiqueta: '-', envia: '-' }, { etiqueta: 'Inicio', envia: '\x1b[H' }, { etiqueta: 'Fin', envia: '\x1b[F' },
  { etiqueta: 'RePág', envia: '\x1b[5~' }, { etiqueta: 'AvPág', envia: '\x1b[6~' },
];

export default function Terminal({ conexion, alCambiar, alVerPase, alCaducar, fijarAtras }: {
  conexion: Conexion;
  alCambiar: (p: Pestana) => void;
  alVerPase: () => void;
  alCaducar: (sesionCaducada: boolean) => void;
  fijarAtras: (fn: (() => boolean) | null) => void;
}) {
  const [contrasena, setContrasena] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [pidiendo, setPidiendo] = useState(false);
  const [lista, setLista] = useState<FichaTerminal[] | null>(null);
  const [max, setMax] = useState(5);
  // La terminal en pantalla: a qué se engancha, su ficha y la clave del xterm.
  const [destino, setDestino] = useState<Destino | null>(null);
  const [ficha, setFicha] = useState<FichaTerminal | null>(null);
  const [clave, setClave] = useState(0);
  const [cerrada, setCerrada] = useState<string | null>(null);
  const [reconectando, setReconectando] = useState(false);
  const [reintentable, setReintentable] = useState(false);
  const [mods, setMods] = useState({ ctrl: false, alt: false });
  const web = useRef<Web>(null);
  const campo = useRef<{ focus(): void; clear(): void }>(null);
  const abierta = useRef<TerminalAbierta | null>(null);
  const intentos = useRef(0);
  const idActual = useRef<string | null>(null);

  // Al irse de la pantalla (otra pestaña, salir) solo se suelta: sigue en la PC.
  useEffect(() => () => abierta.current?.cerrar(), []);

  const fallo = useCallback((e: unknown) => {
    const err = e as ErrorRemoto;
    if (err.codigo === 'sin_sesion') { alCaducar(true); return true; }
    if (err.codigo === 'pase_vencido') { alVerPase(); return true; }
    return false;
  }, [alCaducar, alVerPase]);

  const refrescar = useCallback(async () => {
    try {
      const r = await conexion.terminales();
      setLista(r.terminales);
      setMax(r.max);
    } catch (e) {
      if (!fallo(e)) setLista((l) => l ?? []);
    }
  }, [conexion, fallo]);

  // La lista se mira al entrar y cada 5 s mientras se ve (lo que corre cambia).
  useEffect(() => {
    if (destino) return undefined;
    refrescar();
    const t = setInterval(refrescar, 5000);
    return () => clearInterval(t);
  }, [destino, refrescar]);

  // Con edge-to-edge (Android 15, Expo 58) la ventana NO se encoge al salir el
  // teclado: tapaba la fila de teclas y la línea en la que se escribe. Se le
  // deja sitio a mano, y la terminal se reajusta sola (xterm mide de nuevo).
  const [teclado, setTeclado] = useState(0);
  useEffect(() => {
    const a = Keyboard.addListener('keyboardDidShow', (e) => setTeclado(e.endCoordinates.height));
    const b = Keyboard.addListener('keyboardDidHide', () => setTeclado(0));
    return () => { a.remove(); b.remove(); };
  }, []);

  function enganchar(d: Destino) {
    abierta.current?.cerrar();
    abierta.current = null;
    idActual.current = 'retomar' in d ? d.retomar : null;
    setCerrada(null);
    setReintentable(false);
    setDestino(d);
    setClave((k) => k + 1);
  }

  async function abrirOtra() {
    setPidiendo(true);
    try {
      const b = await conexion.billeteTerminal(contrasena);
      setContrasena('');
      setError(null);
      setFicha(null);
      intentos.current = 0;
      enganchar({ billete: b });
    } catch (e) {
      if (fallo(e)) return;
      const err = e as ErrorRemoto;
      setError(err.codigo === 'contrasena' && err.intentosRestantes !== undefined
        ? `Contraseña incorrecta. Te quedan ${err.intentosRestantes} intentos.` : err.message);
    } finally {
      setPidiendo(false);
    }
  }

  function retomar(f: FichaTerminal) {
    setFicha(f);
    intentos.current = 0;
    enganchar({ retomar: f.id });
  }

  // Minimizar: se suelta y se vuelve a la lista. La PC la deja corriendo.
  const minimizar = useCallback(() => {
    Keyboard.dismiss();
    abierta.current?.cerrar();
    abierta.current = null;
    setDestino(null);
    setCerrada(null);
    setReconectando(false);
  }, []);

  async function cerrar(id: string | null) {
    minimizar();
    if (!id) return;
    try {
      setLista(await conexion.cerrarTerminal(id));
    } catch (e) {
      if (!fallo(e)) refrescar();
    }
  }

  // Atrás, con una terminal en pantalla, la minimiza (no la cierra).
  const atras = useRef<() => boolean>(() => false);
  atras.current = () => {
    if (destino) { minimizar(); return true; }
    return false;
  };
  useEffect(() => {
    fijarAtras(() => atras.current());
    return () => fijarAtras(null);
  }, [fijarAtras]);

  const inyectar = useCallback((js: string) => web.current?.injectJavaScript(`${js};true;`), []);

  const alCerrar = useCallback((codigo: number) => {
    abierta.current = null;
    if (codigo === TERMINAL_SIN_SESION) { alCaducar(true); return; }
    const texto = porQueSeCerro(codigo);
    if (texto) {
      setCerrada(texto);
      inyectar(`window.avisar(${JSON.stringify(texto)})`);
      return;
    }
    // La red. Si ya se sabe su id, se retoma sola unas veces.
    const id = idActual.current;
    if (id && intentos.current < REINTENTOS) {
      intentos.current += 1;
      setReconectando(true);
      setTimeout(() => enganchar({ retomar: id }), REINTENTO_MS);
      return;
    }
    setReconectando(false);
    setReintentable(true);
    setCerrada('Se cortó la conexión con la PC. La terminal sigue abierta allí.');
  }, [alCaducar, inyectar]);

  const alMensaje = useCallback((datos: string) => {
    let m: { t: string; s?: string; f?: number; c?: number };
    try { m = JSON.parse(datos); } catch { return; }
    if (m.t === 'listo' && destino && !abierta.current) {
      abierta.current = conexion.terminal(destino, m.f ?? 24, m.c ?? 80,
        (b) => {
          if (intentos.current) { intentos.current = 0; setReconectando(false); }
          inyectar(`window.recibir(${JSON.stringify(aBase64(b))})`);
        },
        alCerrar,
        (f) => { idActual.current = f.id; setFicha(f); });
    } else if (m.t === 'd' && m.s) {
      abierta.current?.escribir(m.s);
    } else if (m.t === 'tamano' && m.f && m.c) {
      abierta.current?.tamano(m.f, m.c);
    } else if (m.t === 'toque') {
      campo.current?.focus();
    }
  }, [destino, conexion, inyectar, alCerrar]);

  // Lo que manda el teclado. El campo NO es controlado: guarda su texto, y lo
  // tecleado es la diferencia con lo ÚLTIMO que se vio (devolverlo al
  // centinela en cada letra no llegaba a tiempo y se reenviaba todo:
  // «cclclecleaclear»). Se vacía al pulsar Intro o si se hace largo, con
  // clear() (setNativeProps no hace nada en la arquitectura nueva: el campo se
  // quedaba con lo anterior y se reenviaba). Vacío, Borrar llega por onKeyPress.
  const ultimo = useRef(CENTINELA);
  const reiniciar = () => {
    ultimo.current = '';
    campo.current?.clear();
  };
  function alTeclear(t: string) {
    const antes = ultimo.current;
    let comun = 0;
    while (comun < antes.length && comun < t.length && antes[comun] === t[comun]) comun += 1;
    const borrados = antes.length - comun;
    const nuevo = t.slice(comun);
    let envio = '\x7f'.repeat(borrados);
    if (nuevo) {
      envio += conModificadores(nuevo, mods.ctrl, mods.alt);
      if (mods.ctrl || mods.alt) setMods({ ctrl: false, alt: false });
    }
    if (envio) abierta.current?.escribir(envio);
    ultimo.current = t;
    if (t.length === 0 || t.length > 120) reiniciar();
  }

  function tecla(t: (typeof TECLAS)[number]) {
    if (t.mod) {
      setMods((x) => ({ ...x, [t.mod!]: !x[t.mod!] }));
      campo.current?.focus();
    } else if (t.envia) {
      abierta.current?.escribir(t.envia);
    }
  }

  if (!destino) {
    const ahora = Date.now();
    const caben = (lista?.length ?? 0) < max;
    return (
      <Pantalla relleno={false}>
        <ScrollView contentContainerStyle={{ padding: 20, gap: 16, flexGrow: 1, justifyContent: lista?.length ? 'flex-start' : 'center' }}
                    keyboardShouldPersistTaps="handled">
          <Texto tipo="grande">Terminales de {conexion.equipo.equipo}</Texto>
          {lista?.length ? (
            <>
              <Texto color={colores.tenue}>
                Siguen abiertas en la PC aunque no las mires. Entra en una para seguir donde lo dejaste.
              </Texto>
              {lista.map((f) => (
                <Tarjeta key={f.id} estilo={{ gap: 10 }}>
                  <View>
                    <Texto>{nombreTerminal(f)}</Texto>
                    <Texto tipo="chico" color={colores.tenue}>
                      {abiertaHace(f, ahora)}{f.mirando ? ' · abierta en otra pantalla' : ''}
                    </Texto>
                  </View>
                  <View style={{ flexDirection: 'row', gap: 10 }}>
                    <View style={{ flex: 1 }}><Boton texto="Entrar" alto={44} alPulsar={() => retomar(f)} /></View>
                    <View style={{ flex: 1 }}><Boton texto="Cerrar" tipo="borde" alto={44} alPulsar={() => cerrar(f.id)} /></View>
                  </View>
                </Tarjeta>
              ))}
            </>
          ) : (
            <Texto color={colores.tenue}>
              Una shell de verdad en la PC, con sudo. Por ser lo más delicado, pide la contraseña de la app otra vez. La de sudo la escribes dentro de la terminal y no se guarda en ningún sitio.
            </Texto>
          )}
          {caben ? (
            <>
              <Campo etiqueta="Contraseña de la app" valor={contrasena} alCambiar={setContrasena} alEnviar={abrirOtra}
                     error={!!error} ayuda={error ?? 'La PC apunta que se abrió una terminal, cuándo y desde qué celular.'} />
              <Boton texto={lista?.length ? 'Abrir otra terminal' : 'Abrir la terminal'} alPulsar={abrirOtra}
                     cargando={pidiendo} desactivado={!contrasena} />
            </>
          ) : (
            <Aviso texto={`Ya hay ${max} terminales abiertas en la PC: cierra alguna para abrir otra.`} />
          )}
        </ScrollView>
        <Pestanas actual="terminal" permisos={conexion.sesion.permisos} alCambiar={alCambiar} />
      </Pantalla>
    );
  }

  return (
    <Pantalla relleno={false}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 14, paddingVertical: 8 }}>
        <View style={{ flex: 1 }}>
          <Texto tipo="chico" lineas={1}>{ficha ? nombreTerminal(ficha) : conexion.equipo.equipo}</Texto>
        </View>
        <Pressable accessibilityRole="button" onPress={() => Keyboard.dismiss()} style={{ minHeight: 40, justifyContent: 'center', paddingHorizontal: 8 }}>
          <Texto tipo="chico" color={colores.neon}>Teclado</Texto>
        </Pressable>
        <Pressable accessibilityRole="button" onPress={minimizar} style={{ minHeight: 40, justifyContent: 'center', paddingHorizontal: 8 }}>
          <Texto tipo="chico" color={colores.neon}>Minimizar</Texto>
        </Pressable>
        <Pressable accessibilityRole="button" onPress={() => cerrar(idActual.current)} style={{ minHeight: 40, justifyContent: 'center', paddingHorizontal: 8 }}>
          <Texto tipo="chico" color={colores.alerta}>Cerrar</Texto>
        </Pressable>
      </View>
      {reconectando ? (
        <View style={{ paddingHorizontal: 14, paddingBottom: 8 }}>
          <Aviso texto="Se cortó la conexión. Reconectando… (la terminal sigue en la PC)" />
        </View>
      ) : null}
      {cerrada ? (
        <View style={{ paddingHorizontal: 14, gap: 8, paddingBottom: 8 }}>
          <Aviso texto={cerrada} color={colores.alerta} fondo={fondoRojo} />
          {reintentable && idActual.current ? (
            <Boton texto="Reintentar" alto={44} alPulsar={() => { intentos.current = 0; enganchar({ retomar: idActual.current! }); }} />
          ) : null}
          <Boton texto="Volver a la lista" tipo="borde" alto={44} alPulsar={minimizar} />
        </View>
      ) : null}
      <View style={{ flex: 1, backgroundColor: colores.abismo }}>
        <WebView key={clave} ref={web} originWhitelist={['*']} source={{ html: pagina }} javaScriptEnabled
                 onMessage={(ev) => alMensaje(ev.nativeEvent.data)} style={{ backgroundColor: colores.abismo }}
                 keyboardDisplayRequiresUserAction={false} hideKeyboardAccessoryView
                 setSupportMultipleWindows={false} allowFileAccess={false} />
      </View>
      <TextInput ref={campo as never} defaultValue={CENTINELA} onChangeText={alTeclear}
                 onSubmitEditing={() => { abierta.current?.escribir('\r'); reiniciar(); }} submitBehavior="submit"
                 onKeyPress={(e) => {
                   if (e.nativeEvent.key === 'Backspace' && ultimo.current === '') abierta.current?.escribir('\x7f');
                 }}
                 keyboardType="visible-password" autoCapitalize="none" autoCorrect={false}
                 autoComplete="off" spellCheck={false} importantForAutofill="no" caretHidden
                 accessibilityLabel="Teclado de la terminal"
                 style={{ position: 'absolute', left: -1000, width: 10, height: 10, opacity: 0 }} />
      <ScrollView horizontal keyboardShouldPersistTaps="always" showsHorizontalScrollIndicator={false}
                  style={{ flexGrow: 0, marginBottom: teclado, borderTopWidth: 1, borderTopColor: colores.apagado, backgroundColor: colores.superficie }}
                  contentContainerStyle={{ gap: 6, padding: 6 }}>
        {TECLAS.map((t) => {
          const puesta = t.mod ? mods[t.mod] : false;
          return (
            <Pressable key={t.etiqueta} accessibilityRole="button" accessibilityState={{ selected: puesta }}
                       onPress={() => tecla(t)}
                       style={{ minWidth: 44, height: 40, borderRadius: 10, paddingHorizontal: 10, alignItems: 'center',
                                justifyContent: 'center', borderWidth: 1,
                                borderColor: puesta ? colores.neon : colores.apagado,
                                backgroundColor: puesta ? colores.apagado : colores.abismo }}>
              <Texto tipo="chico" color={puesta ? colores.neon : colores.luz}>{t.etiqueta}</Texto>
            </Pressable>
          );
        })}
      </ScrollView>
    </Pantalla>
  );
}
