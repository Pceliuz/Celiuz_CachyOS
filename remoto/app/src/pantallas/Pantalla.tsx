// Escritorio remoto (fase 8): ver y manejar la pantalla de la PC.
//
// Tan poderoso como la terminal, así que pide lo mismo: el permiso de pantalla
// de este celular (se da en la PC), el pase y la contraseña de la app OTRA VEZ.
// Con la pantalla de la PC bloqueada se ve el bloqueo: no se salta nada.
//
// Lo pinta noVNC dentro de un WebView (src/pantalla/pagina.generada.ts, sin
// red), que abre él mismo el WebSocket con el billete de un solo uso. Tocar es
// un clic; dos dedos, clic derecho; arrastrar con el dedo mantiene pulsado.
// Lo tecleado va por un campo nativo invisible, como en la terminal (Gboard
// dentro de un WebView repetía las palabras), y llega a la página por texto().
// Mientras se mira, el celular puede girar a horizontal.
import * as ScreenOrientation from 'expo-screen-orientation';
import { type ComponentType, type Ref, useCallback, useEffect, useRef, useState } from 'react';
import { Keyboard, Pressable, ScrollView, TextInput, View } from 'react-native';
import { WebView as WebViewOriginal } from 'react-native-webview';

import type { Conexion, ErrorRemoto } from '../api/cliente';
import { colores } from '../paleta';
import pagina from '../pantalla/pagina.generada';
import { Aviso, Boton, Campo, Pantalla as Marco, Texto, fondoRojo } from '../componentes/ui';

interface Web { injectJavaScript(js: string): void }
const WebView = WebViewOriginal as unknown as ComponentType<{
  ref?: Ref<Web>; originWhitelist?: string[]; source: { html: string }; javaScriptEnabled?: boolean;
  onMessage?: (ev: { nativeEvent: { data: string } }) => void; style?: object;
  setSupportMultipleWindows?: boolean; allowFileAccess?: boolean; mixedContentMode?: string;
}>;

// Nombres de noVNC (core/input/keysym.js). `combo` se aprietan juntas.
const TECLAS: { etiqueta: string; tecla?: string; combo?: string[]; abrir?: boolean; ajuste?: boolean }[] = [
  { etiqueta: 'Teclado', abrir: true }, { etiqueta: 'Esc', tecla: 'XK_Escape' }, { etiqueta: 'Tab', tecla: 'XK_Tab' },
  { etiqueta: 'Intro', tecla: 'XK_Return' }, { etiqueta: 'Borrar', tecla: 'XK_BackSpace' },
  { etiqueta: 'Super', tecla: 'XK_Super_L' }, { etiqueta: 'Super+Q', combo: ['XK_Super_L', 'q'] },
  { etiqueta: 'Ctrl+C', combo: ['XK_Control_L', 'c'] }, { etiqueta: 'Ctrl+V', combo: ['XK_Control_L', 'v'] },
  { etiqueta: '←', tecla: 'XK_Left' }, { etiqueta: '↑', tecla: 'XK_Up' }, { etiqueta: '↓', tecla: 'XK_Down' },
  { etiqueta: '→', tecla: 'XK_Right' }, { etiqueta: 'Zoom', ajuste: true },
];

export default function Pantalla({ conexion, alVolver, alVerPase, alCaducar }: {
  conexion: Conexion;
  alVolver: () => void;
  alVerPase: () => void;
  alCaducar: (sesionCaducada: boolean) => void;
}) {
  const [contrasena, setContrasena] = useState('');
  const [billete, setBillete] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pidiendo, setPidiendo] = useState(false);
  const [estado, setEstado] = useState<'conectando' | 'conectado' | 'cerrado'>('conectando');
  const [ajustada, setAjustada] = useState(true);
  const [teclado, setTeclado] = useState(0);
  const web = useRef<Web>(null);
  const campo = useRef<{ focus(): void; clear(): void }>(null);
  const ultimo = useRef('');

  // Girar solo aquí: el resto de la app está pensada en vertical.
  useEffect(() => {
    ScreenOrientation.unlockAsync().catch(() => {});
    return () => { ScreenOrientation.lockAsync(ScreenOrientation.OrientationLock.PORTRAIT_UP).catch(() => {}); };
  }, []);
  useEffect(() => {
    const a = Keyboard.addListener('keyboardDidShow', (e) => setTeclado(e.endCoordinates.height));
    const b = Keyboard.addListener('keyboardDidHide', () => setTeclado(0));
    return () => { a.remove(); b.remove(); };
  }, []);

  const inyectar = useCallback((js: string) => web.current?.injectJavaScript(`${js};true;`), []);
  useEffect(() => () => inyectar('window.desconectar && window.desconectar()'), [inyectar]);

  async function pedir() {
    setPidiendo(true);
    try {
      const b = await conexion.billetePantalla(contrasena);
      setContrasena('');
      setError(null);
      setEstado('conectando');
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

  function alMensaje(datos: string) {
    let m: { t: string };
    try { m = JSON.parse(datos); } catch { return; }
    if (m.t === 'listo' && billete) inyectar(`window.conectar(${JSON.stringify(conexion.urlPantalla(billete))})`);
    else if (m.t === 'conectado') setEstado('conectado');
    else if (m.t === 'desconectado' || m.t === 'fallo') setEstado('cerrado');
  }

  // Lo tecleado: la diferencia con lo último que tenía el campo (ver Terminal.tsx).
  function alTeclear(t: string) {
    const antes = ultimo.current;
    let comun = 0;
    while (comun < antes.length && comun < t.length && antes[comun] === t[comun]) comun += 1;
    for (let i = 0; i < antes.length - comun; i += 1) inyectar("window.tecla('XK_BackSpace')");
    const nuevo = t.slice(comun);
    if (nuevo) inyectar(`window.texto(${JSON.stringify(nuevo)})`);
    ultimo.current = t;
    if (t.length > 120) { ultimo.current = ''; campo.current?.clear(); }
  }

  function tecla(t: (typeof TECLAS)[number]) {
    if (t.abrir) campo.current?.focus();
    else if (t.ajuste) { inyectar(`window.ajuste(${!ajustada})`); setAjustada(!ajustada); }
    else if (t.combo) inyectar(`window.combinacion(${JSON.stringify(t.combo)})`);
    else if (t.tecla) inyectar(`window.tecla(${JSON.stringify(t.tecla)})`);
  }

  if (!billete) {
    return (
      <Marco relleno={false}>
        <View style={{ flex: 1, padding: 20, gap: 16, justifyContent: 'center' }}>
          <Texto tipo="grande">Pantalla de {conexion.equipo.equipo}</Texto>
          <Texto color={colores.tenue}>
            Ver y manejar el escritorio de la PC. Por ser tan delicado como la terminal, pide la contraseña de la app otra vez. Si la PC está bloqueada, verás el bloqueo.
          </Texto>
          <Campo etiqueta="Contraseña de la app" valor={contrasena} alCambiar={setContrasena} alEnviar={pedir}
                 error={!!error} ayuda={error ?? 'La PC avisa de que alguien está viendo la pantalla.'} />
          <Boton texto="Ver la pantalla" alPulsar={pedir} cargando={pidiendo} desactivado={!contrasena} />
          <Boton texto="Volver" tipo="borde" alto={48} alPulsar={alVolver} />
        </View>
      </Marco>
    );
  }

  return (
    <Marco relleno={false}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 14, paddingVertical: 6 }}>
        <View style={{ flex: 1 }}>
          <Texto tipo="chico">{estado === 'conectado' ? conexion.equipo.equipo : estado === 'conectando' ? 'Conectando…' : 'Desconectada'}</Texto>
        </View>
        <Pressable accessibilityRole="button" onPress={() => { setBillete(null); alVolver(); }}
                   style={{ minHeight: 40, justifyContent: 'center', paddingHorizontal: 8 }}>
          <Texto tipo="chico" color={colores.alerta}>Cerrar</Texto>
        </Pressable>
      </View>
      {estado === 'cerrado' ? (
        <View style={{ paddingHorizontal: 14, gap: 8, paddingBottom: 8 }}>
          <Aviso texto="Se cerró la conexión con la pantalla (se quitó el permiso o el pase, o la PC cerró la sesión)."
                 color={colores.alerta} fondo={fondoRojo} />
          <Boton texto="Volver a pedirla" tipo="borde" alto={44} alPulsar={() => setBillete(null)} />
        </View>
      ) : null}
      <View style={{ flex: 1, backgroundColor: colores.abismo }}>
        <WebView ref={web} originWhitelist={['*']} source={{ html: pagina }} javaScriptEnabled
                 mixedContentMode="always" onMessage={(ev) => alMensaje(ev.nativeEvent.data)}
                 style={{ backgroundColor: colores.abismo }} setSupportMultipleWindows={false} allowFileAccess={false} />
      </View>
      <TextInput ref={campo as never} defaultValue="" onChangeText={alTeclear}
                 onSubmitEditing={() => { inyectar("window.tecla('XK_Return')"); ultimo.current = ''; campo.current?.clear(); }}
                 submitBehavior="submit" keyboardType="visible-password" autoCapitalize="none" autoCorrect={false}
                 autoComplete="off" spellCheck={false} importantForAutofill="no" caretHidden
                 onKeyPress={(e) => { if (e.nativeEvent.key === 'Backspace' && ultimo.current === '') inyectar("window.tecla('XK_BackSpace')"); }}
                 accessibilityLabel="Teclado de la pantalla remota"
                 style={{ position: 'absolute', left: -1000, width: 10, height: 10, opacity: 0 }} />
      <ScrollView horizontal keyboardShouldPersistTaps="always" showsHorizontalScrollIndicator={false}
                  style={{ flexGrow: 0, marginBottom: teclado, borderTopWidth: 1, borderTopColor: colores.apagado,
                           backgroundColor: colores.superficie }}
                  contentContainerStyle={{ gap: 6, padding: 6 }}>
        {TECLAS.map((t) => (
          <Pressable key={t.etiqueta} accessibilityRole="button" onPress={() => tecla(t)}
                     style={{ minWidth: 44, height: 40, borderRadius: 10, paddingHorizontal: 10, alignItems: 'center',
                              justifyContent: 'center', borderWidth: 1, borderColor: colores.apagado,
                              backgroundColor: colores.abismo }}>
            <Texto tipo="chico" color={t.ajuste && !ajustada ? colores.neon : colores.luz}>
              {t.ajuste ? (ajustada ? 'Zoom 1:1' : 'Ajustar') : t.etiqueta}
            </Texto>
          </Pressable>
        ))}
      </ScrollView>
    </Marco>
  );
}
