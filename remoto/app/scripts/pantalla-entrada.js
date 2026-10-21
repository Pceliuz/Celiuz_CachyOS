// remoto/app/scripts/pantalla-entrada.js — lo que corre DENTRO del WebView del
// escritorio remoto (fase 8). gen-pantalla.mjs lo empaqueta con noVNC (esbuild)
// en una sola pagina, sin red.
//
// Habla con React Native (pantallas/Pantalla.tsx):
//   hacia fuera  window.ReactNativeWebView.postMessage({t: listo|conectado|desconectado|fallo})
//   hacia dentro conectar(url), texto(s), tecla(nombre), combinacion([nombres]), ajuste(si)
//
// El TECLADO no lo coge la pagina, por lo mismo que en la terminal: Gboard
// dentro de un WebView compone palabras y llegan repetidas. Lo teclea un campo
// nativo de React Native y llega aqui por texto().
import RFB from '../node_modules/@novnc/novnc/core/rfb.js';
import KeyTable from '../node_modules/@novnc/novnc/core/input/keysym.js';
import keysyms from '../node_modules/@novnc/novnc/core/input/keysymdef.js';

const rn = (o) => window.ReactNativeWebView.postMessage(JSON.stringify(o));
let rfb = null;

window.conectar = (url) => {
  if (rfb) rfb.disconnect();
  rfb = new RFB(document.getElementById('p'), url, { wsProtocols: ['binary'] });
  rfb.scaleViewport = true;     // la pantalla entera, a lo ancho del celular
  rfb.resizeSession = false;    // nunca cambiar la resolucion de la PC
  rfb.focusOnClick = false;     // que el WebView no saque su teclado
  rfb.background = getComputedStyle(document.body).backgroundColor;  // la paleta, no el gris de noVNC
  rfb.addEventListener('connect', () => rn({ t: 'conectado' }));
  rfb.addEventListener('disconnect', (e) => rn({ t: 'desconectado', limpio: !!e.detail.clean }));
  rfb.addEventListener('securityfailure', (e) => rn({ t: 'fallo', motivo: String(e.detail.reason || '') }));
};

window.texto = (s) => {
  if (!rfb) return;
  for (const ch of s) {
    if (ch === '\n') { rfb.sendKey(KeyTable.XK_Return, 'Enter'); continue; }
    rfb.sendKey(keysyms.lookup(ch.codePointAt(0)));
  }
};

window.tecla = (nombre) => {
  if (rfb && KeyTable[nombre] !== undefined) rfb.sendKey(KeyTable[nombre]);
};

// Varias a la vez (Super+Q, Ctrl+C...): se aprietan en orden y se sueltan al reves.
window.combinacion = (nombres) => {
  if (!rfb) return;
  const ks = nombres.map((n) => (KeyTable[n] !== undefined ? KeyTable[n] : keysyms.lookup(n.codePointAt(0))));
  ks.forEach((k) => rfb.sendKey(k, null, true));
  ks.slice().reverse().forEach((k) => rfb.sendKey(k, null, false));
};

// Ajustada a lo ancho, o a tamaño real arrastrando para moverse.
window.ajuste = (ajustada) => {
  if (!rfb) return;
  rfb.scaleViewport = ajustada;
  rfb.clipViewport = !ajustada;
  rfb.dragViewport = !ajustada;
};

window.desconectar = () => { if (rfb) rfb.disconnect(); };

rn({ t: 'listo' });
