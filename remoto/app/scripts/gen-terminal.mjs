// remoto/app/scripts/gen-terminal.mjs — hace src/terminal/pagina.generada.ts:
// la pagina de la terminal (xterm.js) ENTERA, en una cadena, para el WebView.
//
// Por que generada y no un fichero en assets/: el WebView la carga con
// `source={{ html }}` sin red (la app no puede pedir xterm a una CDN: el
// celular puede estar sin internet salvo Tailscale, y no queremos depender de
// terceros). xterm.js sale de node_modules, que no se versiona; por eso esto
// tampoco (.gitignore). Lo llaman compilar.sh y `npm run typecheck`.
//
// Los colores, de src/colores.json (que genera gen-colores.py de la paleta del
// escritorio): ni un hex a mano.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const APP = join(dirname(fileURLToPath(import.meta.url)), '..');
const leer = (r) => readFileSync(join(APP, r), 'utf8');
const c = JSON.parse(leer('src/colores.json')).colores;
const xterm = leer('node_modules/@xterm/xterm/lib/xterm.js');
const fit = leer('node_modules/@xterm/addon-fit/lib/addon-fit.js');
const css = leer('node_modules/@xterm/xterm/css/xterm.css');
const tema = {
  background: c.abismo, foreground: c.luz, cursor: c.neon, cursorAccent: c.abismo,
  selectionBackground: c.apagado, black: c.negro, brightBlack: c.tenue, red: c.alerta, brightRed: c.alerta,
  green: c.exito, brightGreen: c.exito, yellow: c.atencion, brightYellow: c.atencion,
  blue: c.violeta, brightBlue: c.amatista, magenta: c.amatista, brightMagenta: c.neon,
  cyan: c.neon, brightCyan: c.luz, white: c.luz, brightWhite: '#ffffff',
};

// Lo que habla con React Native: window.ReactNativeWebView.postMessage hacia
// fuera; recibir()/avisar() hacia dentro (injectJavaScript).
//
// LA PAGINA NO RECIBE EL TECLADO. Con el teclado del celular escribiendo en el
// textarea de xterm, Gboard compone palabras y xterm las recibe repetidas: «echo
// hola» llegaba «echchho hholla» (medido el 2026-10-20 en el HONOR). El textarea
// queda de solo lectura y un toque en la terminal le pide a React Native que
// abra SU campo de texto (Terminal.tsx), que manda letra a letra.
const puente = `
(function () {
  var rn = function (o) { window.ReactNativeWebView.postMessage(JSON.stringify(o)); };
  var term = new Terminal({ fontFamily: 'monospace', fontSize: 13, cursorBlink: true, scrollback: 5000,
                            theme: ${JSON.stringify(tema)} });
  var ajuste = new FitAddon.FitAddon();
  term.loadAddon(ajuste);
  term.open(document.getElementById('t'));
  ajuste.fit();
  if (term.textarea) {
    term.textarea.setAttribute('readonly', 'readonly');
    term.textarea.setAttribute('inputmode', 'none');
  }
  // Las respuestas que xterm genera solo (posicion del cursor, etc.) si salen.
  term.onData(function (d) { rn({ t: 'd', s: d }); });
  var x0 = 0, y0 = 0, movio = false;
  document.addEventListener('touchstart', function (e) { x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; movio = false; }, { passive: true });
  document.addEventListener('touchmove', function (e) {
    if (Math.abs(e.touches[0].clientX - x0) > 10 || Math.abs(e.touches[0].clientY - y0) > 10) movio = true;
  }, { passive: true });
  document.addEventListener('touchend', function () { if (!movio) rn({ t: 'toque' }); });
  term.onResize(function (e) { rn({ t: 'tamano', f: e.rows, c: e.cols }); });
  window.addEventListener('resize', function () { try { ajuste.fit(); } catch (e) {} });
  window.recibir = function (b64) {
    var bin = atob(b64), u = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
    term.write(u);
  };
  window.avisar = function (texto) { term.write('\\r\\n\\x1b[2m' + texto + '\\x1b[0m\\r\\n'); };
  rn({ t: 'listo', f: term.rows, c: term.cols });
})();`;

const html = `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<style>${css}
html, body { margin: 0; height: 100%; background: ${c.abismo}; overflow: hidden; }
#t { position: absolute; inset: 4px; }
</style></head><body><div id="t"></div>
<script>${xterm}</script><script>${fit}</script><script>${puente}</script></body></html>`;

const destino = join(APP, 'src/terminal/pagina.generada.ts');
mkdirSync(dirname(destino), { recursive: true });
writeFileSync(destino, `// GENERADO por scripts/gen-terminal.mjs — NO EDITAR (y no se versiona)\nexport default ${JSON.stringify(html)};\n`);
console.log(`pagina de la terminal: ${(html.length / 1024).toFixed(0)} KB`);
