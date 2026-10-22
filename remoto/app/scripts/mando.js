// remoto/app/scripts/mando.js — el «modo mando» del escritorio remoto: el
// ratón se maneja como en un juego del celular, no tocando la imagen.
//
// POR QUE (el usuario, 2026-10-21): con la pantalla de la PC encogida al ancho
// del celular, tocar para apuntar era «realmente horrible»: un dedo tapa media
// barra y cada toque cae unos píxeles al lado. Ahora:
//   - un JOYSTICK abajo a la izquierda mueve el cursor (más lejos del centro,
//     más rápido; cerca del centro, fino);
//   - arrastrar el dedo SOBRE LA IMAGEN lo mueve como un touchpad, y tocarla
//     es un clic donde está el cursor (no donde está el dedo);
//   - botones a la derecha: clic, clic derecho, rueda arriba/abajo y
//     «Mantener» (el botón izquierdo queda pulsado para arrastrar ventanas);
//   - una fila de ESCRITORIOS (1-9) que manda Super+número, como en la PC.
// El teclado y las teclas sueltas siguen en la fila de abajo, que es de React
// Native (pantallas/Pantalla.tsx).
//
// VNC solo entiende posiciones ABSOLUTAS, así que aquí se lleva un cursor
// propio en coordenadas de la pantalla de la PC (fx, fy) y se manda esa
// posición. Y se pinta un cursor propio encima: el de noVNC en un celular
// solo se mueve con eventos del dedo, y se quedaría donde se tocó la última vez.
//
// Lo puro (cuentas) va exportado y lo prueba tests/unidad/remoto-mando.sh con
// Node; lo del DOM, en montar().

// --- cuentas -----------------------------------------------------------------

// Velocidad del cursor según cuánto se empuja el joystick (0..1), en anchos de
// la pantalla de la PC por segundo. Cuadrática: el primer tercio es para
// apuntar fino y el final para cruzar la pantalla en ~1 s.
export const VELOCIDAD_MAX = 0.9;
export const ZONA_MUERTA = 0.08;

export function velocidad(empuje) {
  const d = Math.min(1, Math.max(0, empuje));
  if (d < ZONA_MUERTA) return 0;
  const t = (d - ZONA_MUERTA) / (1 - ZONA_MUERTA);
  return VELOCIDAD_MAX * t * t;
}

// Un paso del cursor: posición, empuje del joystick (dx, dy en -1..1), segundos
// desde el anterior y tamaño de la pantalla de la PC. Nunca se sale de ella.
export function paso(pos, dx, dy, dt, ancho, alto) {
  const n = Math.hypot(dx, dy);
  if (!n || !ancho || !alto) return pos;
  const v = velocidad(n) * ancho * dt;
  return {
    x: Math.min(ancho - 1, Math.max(0, pos.x + (dx / n) * v)),
    y: Math.min(alto - 1, Math.max(0, pos.y + (dy / n) * v)),
  };
}

// Del punto de la PC al punto de la pantalla del celular, y al revés. `vista`
// es lo que pinta noVNC: dónde está el lienzo (rect), con qué escala y qué
// trozo de la pantalla de la PC enseña (vp: x, y).
export function aPantalla(pos, vista) {
  return { x: vista.rect.left + (pos.x - vista.vp.x) * vista.escala,
           y: vista.rect.top + (pos.y - vista.vp.y) * vista.escala };
}

// Arrastrar el dedo sobre la imagen (touchpad): lo que se mueve el dedo en el
// celular, pasado a la PC y un poco acelerado, para no tener que hacer diez
// pasadas con una pantalla de 1920 en un celular de 400.
export const GANANCIA_TOUCHPAD = 1.6;
export function arrastre(pos, ddx, ddy, escala, ancho, alto) {
  const k = GANANCIA_TOUCHPAD / (escala || 1);
  return {
    x: Math.min(ancho - 1, Math.max(0, pos.x + ddx * k)),
    y: Math.min(alto - 1, Math.max(0, pos.y + ddy * k)),
  };
}

// Un toque (y no un arrastre): poco movimiento y poco tiempo.
export function esToque(movido, ms) {
  return movido < 10 && ms < 300;
}

// Botones de VNC (máscara): izquierdo, medio, derecho, rueda arriba, abajo.
export const BOTON = { izquierdo: 1, medio: 2, derecho: 4, ruedaArriba: 8, ruedaAbajo: 16 };

// --- el DOM -----------------------------------------------------------------

const CSS = `
#mando { position: absolute; inset: 0; pointer-events: none; display: none; font-family: sans-serif; }
#mando.si { display: block; }
#mando .zona, #mando button { pointer-events: auto; }
#touchpad { position: absolute; left: 0; right: 0; top: 0; }
#cursor { position: absolute; width: 22px; height: 22px; margin: -2px 0 0 -2px; pointer-events: none;
  filter: drop-shadow(0 0 2px #000); display: none; }
#mando.si #cursor { display: block; }
#escritorios { position: absolute; left: 0; right: 0; display: flex; gap: 6px; justify-content: center;
  padding: 6px; overflow-x: auto; }
#mando button { border-radius: 14px; border: 1px solid var(--borde); background: var(--fondo);
  color: var(--texto); font-size: 15px; touch-action: none; -webkit-user-select: none; user-select: none; }
#mando button.puesto { border-color: var(--acento); color: var(--acento); box-shadow: 0 0 10px var(--acento); }
#escritorios button { min-width: 38px; height: 38px; }
#mando.horizontal button, #mando.horizontal #joy { background: var(--fondo-claro); }
#mando.horizontal #perilla { opacity: .7; }
#mando.horizontal #escritorios button { min-width: 34px; height: 34px; font-size: 14px; }
#joy { position: absolute; border-radius: 50%; border: 2px solid var(--borde); background: var(--fondo);
  touch-action: none; }
#perilla { position: absolute; left: 50%; top: 50%; width: 42%; height: 42%; margin: -21% 0 0 -21%;
  border-radius: 50%; background: var(--acento); opacity: .85; box-shadow: 0 0 14px var(--acento); }
#botones { position: absolute; display: grid; gap: 8px; }
#botones .grande { grid-column: span 2; height: 64px; font-size: 17px; }
#botones button { height: 48px; }
`;

const FLECHA = '<svg viewBox="0 0 22 22" width="22" height="22"><path d="M2 2 L2 18 L6.5 13.5 L9.5 20 L12.5 18.7 '
  + 'L9.6 12.3 L16 12.3 Z" fill="#fff" stroke="#000" stroke-width="1.4" stroke-linejoin="round"/></svg>';

// montar(cosas) — pone el mando encima de la pantalla. `cosas`:
//   lienzo()        el contenedor donde dibuja noVNC (#p)
//   vista()         {rect, escala, vp, ancho, alto} de lo que pinta noVNC, o null
//   raton(x, y, m)  manda la posición y los botones a la PC
//   combinacion(t)  manda varias teclas juntas (Super+1)
//   colores         la paleta (src/colores.json)
// Devuelve {poner(si), recolocar()}.
export function montar(cosas) {
  const c = cosas.colores;
  const estilo = document.createElement('style');
  estilo.textContent = CSS + `:root { --fondo: ${c.superficie}cc; --borde: ${c.apagado}; --texto: ${c.luz};`
    + ` --fondo-claro: ${c.superficie}77; --acento: ${c.neon}; }`;
  document.head.appendChild(estilo);

  const raiz = document.createElement('div');
  raiz.id = 'mando';
  raiz.innerHTML = `<div id="touchpad" class="zona"></div><div id="cursor">${FLECHA}</div>
    <div id="escritorios" class="zona"></div>
    <div id="joy" class="zona"><div id="perilla"></div></div>
    <div id="botones" class="zona">
      <button class="grande" data-boton="izquierdo">Clic</button>
      <button data-boton="derecho">Derecho</button><button id="mantener">Mantener</button>
      <button data-rueda="ruedaArriba">Rueda ▲</button><button data-rueda="ruedaAbajo">Rueda ▼</button>
    </div>`;
  document.body.appendChild(raiz);
  const $ = (id) => raiz.querySelector(id);
  const touchpad = $('#touchpad'), cursor = $('#cursor'), joy = $('#joy'), perilla = $('#perilla');
  const botones = $('#botones'), escritorios = $('#escritorios');

  for (let n = 1; n <= 9; n += 1) {
    const b = document.createElement('button');
    b.textContent = String(n);
    b.addEventListener('click', () => cosas.combinacion(['XK_Super_L', String(n)]));
    escritorios.appendChild(b);
  }

  let pos = null;           // el cursor, en la pantalla de la PC
  let mascara = 0;          // los botones pulsados ahora
  let mantener = false;
  let empuje = { x: 0, y: 0 };
  let ultimo = 0;
  let enviado = 0;

  function vista() { return cosas.vista(); }
  function pintar() {
    const v = vista();
    if (!v || !pos) return;
    const p = aPantalla(pos, v);
    cursor.style.left = `${p.x}px`;
    cursor.style.top = `${p.y}px`;
  }
  function mandar(forzar) {
    const v = vista();
    if (!v || !pos) return;
    const ahora = performance.now();
    if (!forzar && ahora - enviado < 30) return;   // ~33 por segundo, como noVNC
    enviado = ahora;
    cosas.raton(Math.round(pos.x), Math.round(pos.y), mascara);
  }
  function asegurar() {
    const v = vista();
    if (v && !pos) pos = { x: v.ancho / 2, y: v.alto / 2 };
    return v;
  }

  // El joystick: el dedo dentro de la base; el bucle mueve mientras se empuja.
  function bucle(t) {
    const v = asegurar();
    if (v && (empuje.x || empuje.y)) {
      const dt = ultimo ? Math.min(0.05, (t - ultimo) / 1000) : 0;
      pos = paso(pos, empuje.x, empuje.y, dt, v.ancho, v.alto);
      pintar();
      mandar(false);
    }
    ultimo = t;
    if (empuje.x || empuje.y) requestAnimationFrame(bucle);
    else { ultimo = 0; mandar(true); }
  }
  function moverJoy(ev) {
    const r = joy.getBoundingClientRect();
    const radio = r.width / 2;
    let dx = (ev.clientX - (r.left + radio)) / radio;
    let dy = (ev.clientY - (r.top + radio)) / radio;
    const n = Math.hypot(dx, dy);
    if (n > 1) { dx /= n; dy /= n; }
    const arrancar = !empuje.x && !empuje.y;
    empuje = { x: dx, y: dy };
    perilla.style.transform = `translate(${dx * radio * 0.6}px, ${dy * radio * 0.6}px)`;
    if (arrancar && (dx || dy)) requestAnimationFrame(bucle);
  }
  joy.addEventListener('pointerdown', (ev) => { joy.setPointerCapture(ev.pointerId); asegurar(); moverJoy(ev); });
  joy.addEventListener('pointermove', (ev) => { if (joy.hasPointerCapture(ev.pointerId)) moverJoy(ev); });
  const soltarJoy = () => { empuje = { x: 0, y: 0 }; perilla.style.transform = ''; };
  joy.addEventListener('pointerup', soltarJoy);
  joy.addEventListener('pointercancel', soltarJoy);

  // Los botones: pulsar y soltar como un ratón (con el clic apretado se puede
  // arrastrar con el joystick); «Mantener» lo deja apretado hasta otro toque.
  function apretar(bit, si) {
    mascara = si ? (mascara | bit) : (mascara & ~bit);
    if (asegurar()) mandar(true);
  }
  botones.querySelectorAll('[data-boton]').forEach((b) => {
    const bit = BOTON[b.dataset.boton];
    b.addEventListener('pointerdown', (ev) => { b.setPointerCapture(ev.pointerId); b.classList.add('puesto'); apretar(bit, true); });
    const fin = () => { b.classList.remove('puesto'); if (!(mantener && bit === BOTON.izquierdo)) apretar(bit, false); };
    b.addEventListener('pointerup', fin);
    b.addEventListener('pointercancel', fin);
  });
  const bMantener = $('#mantener');
  bMantener.addEventListener('click', () => {
    mantener = !mantener;
    bMantener.classList.toggle('puesto', mantener);
    apretar(BOTON.izquierdo, mantener);
  });
  // La rueda: un «clic» de rueda al tocar, y seguido mientras se mantenga.
  botones.querySelectorAll('[data-rueda]').forEach((b) => {
    const bit = BOTON[b.dataset.rueda];
    let rep = null;
    const una = () => { apretar(bit, true); apretar(bit, false); };
    b.addEventListener('pointerdown', (ev) => {
      b.setPointerCapture(ev.pointerId); b.classList.add('puesto'); una();
      rep = setInterval(una, 110);
    });
    const fin = () => { b.classList.remove('puesto'); clearInterval(rep); rep = null; };
    b.addEventListener('pointerup', fin);
    b.addEventListener('pointercancel', fin);
  });

  // La imagen como touchpad: arrastrar mueve el cursor, tocar es un clic.
  let dedo = null;
  touchpad.addEventListener('pointerdown', (ev) => {
    touchpad.setPointerCapture(ev.pointerId);
    asegurar();
    dedo = { x: ev.clientX, y: ev.clientY, movido: 0, t: performance.now() };
  });
  touchpad.addEventListener('pointermove', (ev) => {
    const v = vista();
    if (!dedo || !v || !pos) return;
    const ddx = ev.clientX - dedo.x, ddy = ev.clientY - dedo.y;
    dedo.movido += Math.hypot(ddx, ddy);
    dedo.x = ev.clientX; dedo.y = ev.clientY;
    pos = arrastre(pos, ddx, ddy, v.escala, v.ancho, v.alto);
    pintar();
    mandar(false);
  });
  touchpad.addEventListener('pointerup', () => {
    if (dedo && esToque(dedo.movido, performance.now() - dedo.t) && !mantener) {
      apretar(BOTON.izquierdo, true);
      apretar(BOTON.izquierdo, false);
    } else {
      mandar(true);
    }
    dedo = null;
  });

  // Dónde va cada cosa: en vertical, la pantalla arriba y el mando debajo (el
  // hueco que quedaba vacío); en horizontal —lo normal: la app gira sola al
  // entrar en el mando—, la pantalla entera y el mando encima, en las
  // esquinas y medio transparente, como los botones de un juego del celular.
  function recolocar() {
    const W = window.innerWidth, H = window.innerHeight;
    const lienzo = cosas.lienzo();
    const vertical = H > W;
    raiz.classList.toggle('horizontal', !vertical);
    const lado = Math.round(Math.min(vertical ? W * 0.42 : H * 0.42, 190));
    if (vertical) {
      const v = vista();
      const prop = v && v.ancho ? v.alto / v.ancho : 9 / 16;
      const altoImagen = Math.round(Math.min(H * 0.5, W * prop));
      lienzo.style.bottom = `${H - altoImagen}px`;
      touchpad.style.height = `${altoImagen}px`;
      escritorios.style.top = `${altoImagen + 6}px`;
      escritorios.style.bottom = '';
    } else {
      lienzo.style.bottom = '0px';
      touchpad.style.height = `${H}px`;
      escritorios.style.top = '0px';
    }
    joy.style.width = joy.style.height = `${lado}px`;
    joy.style.left = '18px';
    joy.style.bottom = '18px';
    botones.style.right = '14px';
    botones.style.bottom = '14px';
    botones.style.gridTemplateColumns = `repeat(2, ${Math.round(lado * 0.55)}px)`;
    pintar();
    // noVNC reescala el lienzo DESPUÉS (con su ResizeObserver): el cursor
    // propio se vuelve a poner cuando ya ha cambiado.
    setTimeout(pintar, 150);
  }
  window.addEventListener('resize', recolocar);

  return {
    poner(si) {
      raiz.classList.toggle('si', si);
      if (!si) {
        // Al salir del mando, nada pulsado y la pantalla entera otra vez.
        if (mascara) { mascara = 0; mandar(true); }
        mantener = false;
        bMantener.classList.remove('puesto');
        cosas.lienzo().style.bottom = '0px';
      } else {
        recolocar();
        asegurar();
        pintar();
      }
    },
    recolocar,
  };
}
