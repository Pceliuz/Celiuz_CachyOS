// remoto/app/scripts/gen-pantalla.mjs — hace src/pantalla/pagina.generada.ts:
// el escritorio remoto (noVNC, empaquetado con esbuild) ENTERO en una cadena,
// para el WebView. Sin red, como la terminal (gen-terminal.mjs), y por lo mismo
// no se versiona. Lo llaman compilar.sh y `npm run typecheck`.
import { buildSync } from 'esbuild';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const APP = join(dirname(fileURLToPath(import.meta.url)), '..');
const c = JSON.parse(readFileSync(join(APP, 'src/colores.json'), 'utf8')).colores;
const r = buildSync({
  entryPoints: [join(APP, 'scripts/pantalla-entrada.js')],
  // ESM y no IIFE: noVNC usa await en lo alto del modulo. El WebView de
  // Android (Chromium) carga un <script type="module"> en linea sin problema.
  bundle: true, format: 'esm', minify: true, write: false, target: 'es2022',
  logLevel: 'error',
});
const js = r.outputFiles[0].text;
const html = `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<style>html, body { margin: 0; height: 100%; background: ${c.abismo}; overflow: hidden; touch-action: none; }
#p { position: absolute; inset: 0; }</style></head>
<body><div id="p"></div><script type="module">${js.replace(/<\/script/g, '<\\/script')}</script></body></html>`;
const destino = join(APP, 'src/pantalla/pagina.generada.ts');
mkdirSync(dirname(destino), { recursive: true });
writeFileSync(destino, `// GENERADO por scripts/gen-pantalla.mjs — NO EDITAR (y no se versiona)\nexport default ${JSON.stringify(html)};\n`);
console.log(`pagina del escritorio remoto: ${(html.length / 1024).toFixed(0)} KB`);
