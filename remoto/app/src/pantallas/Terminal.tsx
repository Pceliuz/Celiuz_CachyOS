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
import { type ComponentType, type Ref, useCallback, useEffect, useRef, useState } from 'react';
import { Keyboard, Pressable, ScrollView, TextInput, View } from 'react-native';
import { WebView as WebViewOriginal } from 'react-native-webview';

import { ErrorRemoto, TERMINAL_SALIO, TERMINAL_SIN_PERMISO, type Conexion, type TerminalAbierta } from '../api/cliente';
import { aBase64 } from '../api/cripto';
import { colores } from '../paleta';
import pagina from '../terminal/pagina.generada';
import Pestanas, { type Pestana } from '../componentes/Pestanas';
import { Aviso, Boton, Campo, Pantalla, Texto, fondoRojo } from '../componentes/ui';

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

export default function Terminal({ conexion, alCambiar, alVerPase, alCaducar }: {
  conexion: Conexion;
  alCambiar: (p: Pestana) => void;
  alVerPase: () => void;
  alCaducar: (sesionCaducada: boolean) => void;
}) {
  const [contrasena, setContrasena] = useState('');
  const [billete, setBillete] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pidiendo, setPidiendo] = useState(false);
  const [cerrada, setCerrada] = useState<string | null>(null);
  const [mods, setMods] = useState({ ctrl: false, alt: false });
  const web = useRef<Web>(null);
  const campo = useRef<{ focus(): void; clear(): void }>(null);
  const abierta = useRef<TerminalAbierta | null>(null);

  useEffect(() => () => abierta.current?.cerrar(), []);

  // Con edge-to-edge (Android 15, Expo 58) la ventana NO se encoge al salir el
  // teclado: tapaba la fila de teclas y la línea en la que se escribe. Se le
  // deja sitio a mano, y la terminal se reajusta sola (xterm mide de nuevo).
  const [teclado, setTeclado] = useState(0);
  useEffect(() => {
    const a = Keyboard.addListener('keyboardDidShow', (e) => setTeclado(e.endCoordinates.height));
    const b = Keyboard.addListener('keyboardDidHide', () => setTeclado(0));
    return () => { a.remove(); b.remove(); };
  }, []);

  async function pedir() {
    setPidiendo(true);
    try {
      const b = await conexion.billeteTerminal(contrasena);
      setContrasena('');
      setError(null);
      setCerrada(null);
      setBillete(b);
    } catch (e) {
      const err = e as ErrorRemoto;
      if (err.codigo === 'sin_sesion') return alCaducar(true);
      if (err.codigo === 'pase_vencido') return alVerPase();
      setError(err.codigo === 'contrasena' && err.intentosRestantes !== undefined
        ? `Contraseña incorrecta. Te quedan ${err.intentosRestantes} intentos.` : err.message);
    } finally {
      setPidiendo(false);
    }
  }

  const inyectar = useCallback((js: string) => web.current?.injectJavaScript(`${js};true;`), []);

  const alMensaje = useCallback((datos: string) => {
    let m: { t: string; s?: string; f?: number; c?: number; ctrl?: boolean; alt?: boolean };
    try { m = JSON.parse(datos); } catch { return; }
    if (m.t === 'listo' && billete && !abierta.current) {
      abierta.current = conexion.terminal(billete, m.f ?? 24, m.c ?? 80,
        (b) => inyectar(`window.recibir(${JSON.stringify(aBase64(b))})`),
        (codigo) => {
          abierta.current = null;
          const texto = codigo === TERMINAL_SALIO ? 'La shell terminó.'
            : codigo === TERMINAL_SIN_PERMISO ? 'Se cerró: a este celular se le quitó el pase o el permiso de terminal.'
            : 'Se cortó la conexión con la PC.';
          setCerrada(texto);
          inyectar(`window.avisar(${JSON.stringify(texto)})`);
        });
    } else if (m.t === 'd' && m.s) {
      abierta.current?.escribir(m.s);
    } else if (m.t === 'tamano' && m.f && m.c) {
      abierta.current?.tamano(m.f, m.c);
    } else if (m.t === 'toque') {
      campo.current?.focus();
    }
  }, [billete, conexion, inyectar]);

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

  function otra() {
    abierta.current?.cerrar();
    abierta.current = null;
    setBillete(null);
    setCerrada(null);
  }

  if (!billete) {
    return (
      <Pantalla relleno={false}>
        <View style={{ flex: 1, padding: 20, gap: 16, justifyContent: 'center' }}>
          <Texto tipo="grande">Terminal de {conexion.equipo.equipo}</Texto>
          <Texto color={colores.tenue}>
            Una shell de verdad en la PC, con sudo. Por ser lo más delicado, pide la contraseña de la app otra vez. La de sudo la escribes dentro de la terminal y no se guarda en ningún sitio.
          </Texto>
          <Campo etiqueta="Contraseña de la app" valor={contrasena} alCambiar={setContrasena} alEnviar={pedir}
                 error={!!error} ayuda={error ?? 'La PC apunta que se abrió una terminal, cuándo y desde qué celular.'} />
          <Boton texto="Abrir la terminal" alPulsar={pedir} cargando={pidiendo} desactivado={!contrasena} />
        </View>
        <Pestanas actual="terminal" permisos={conexion.sesion.permisos} alCambiar={alCambiar} />
      </Pantalla>
    );
  }

  return (
    <Pantalla relleno={false}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 14, paddingVertical: 8 }}>
        <View style={{ flex: 1 }}>
          <Texto tipo="chico">{conexion.equipo.equipo}</Texto>
        </View>
        <Pressable accessibilityRole="button" onPress={() => Keyboard.dismiss()} style={{ minHeight: 40, justifyContent: 'center', paddingHorizontal: 8 }}>
          <Texto tipo="chico" color={colores.neon}>Ocultar teclado</Texto>
        </Pressable>
        <Pressable accessibilityRole="button" onPress={otra} style={{ minHeight: 40, justifyContent: 'center', paddingHorizontal: 8 }}>
          <Texto tipo="chico" color={colores.alerta}>Cerrar</Texto>
        </Pressable>
      </View>
      {cerrada ? (
        <View style={{ paddingHorizontal: 14, gap: 8, paddingBottom: 8 }}>
          <Aviso texto={cerrada} color={colores.alerta} fondo={fondoRojo} />
          <Boton texto="Abrir otra" tipo="borde" alto={44} alPulsar={otra} />
        </View>
      ) : null}
      <View style={{ flex: 1, backgroundColor: colores.abismo }}>
        <WebView ref={web} originWhitelist={['*']} source={{ html: pagina }} javaScriptEnabled
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
