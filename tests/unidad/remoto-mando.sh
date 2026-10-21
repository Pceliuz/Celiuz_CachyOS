#!/usr/bin/env bash
# tests/unidad/remoto-mando.sh — las cuentas del «modo mando» del escritorio
# remoto (remoto/app/scripts/mando.js), con Node y sin celular.
#
# POR QUE: el usuario pidió (2026-10-21) manejar el ratón con un joystick y
# botones porque apuntar con el dedo en la pantalla encogida era imposible. Lo
# que puede fallar sin que se vea en una captura son las cuentas: que el
# cursor se salga de la pantalla de la PC, que el joystick no tenga zona
# muerta (el cursor se arrastra solo con el pulgar apoyado), que lo fino no
# sea fino, o que el cursor propio se pinte en otro sitio que donde clica.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
MANDO="$REPO/remoto/app/scripts/mando.js"

if ! command -v node >/dev/null; then
    _gris "  sin node: se salta"
    afirmar_intacta_la_casa_real
    resumen
    exit
fi

titulo "1. Las cuentas del mando"
node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON --input-type=module - "$MANDO" > "$TMP/mando.txt" 2>"$TMP/mando.err" <<'FINJS'
const m = await import(process.argv[2]);
const ok = (d, c, x) => console.log((c ? 'ok|' : 'fallo|') + d + (c || x === undefined ? '' : ' -> ' + JSON.stringify(x)));
ok('zona muerta: el pulgar apoyado sin empujar no mueve nada', m.velocidad(0.05) === 0);
ok('empujar a fondo cruza la pantalla en algo más de un segundo', Math.abs(m.velocidad(1) - m.VELOCIDAD_MAX) < 1e-9 && m.VELOCIDAD_MAX <= 1);
ok('a medio empujar va MUCHO más lento que a fondo (para apuntar fino)', m.velocidad(0.5) < m.velocidad(1) / 3, m.velocidad(0.5));
ok('la velocidad nunca baja al empujar más', [0.1, 0.2, 0.4, 0.6, 0.8, 1].every((d, i, a) => !i || m.velocidad(d) >= m.velocidad(a[i - 1])));
let p = { x: 960, y: 540 };
p = m.paso(p, 1, 0, 0.1, 1920, 1080);
ok('un paso a la derecha mueve a la derecha y nada en vertical', p.x > 960 && p.y === 540, p);
let q = { x: 1900, y: 10 };
for (let i = 0; i < 100; i += 1) q = m.paso(q, 1, -1, 0.05, 1920, 1080);
ok('por mucho que se empuje, el cursor no se sale de la pantalla de la PC', q.x === 1919 && q.y === 0, q);
ok('sin pantalla todavía (0x0), no se mueve ni revienta', JSON.stringify(m.paso({ x: 5, y: 5 }, 1, 1, 0.1, 0, 0)) === '{"x":5,"y":5}');
const vista = { rect: { left: 0, top: 40 }, escala: 0.2, vp: { x: 0, y: 0 } };
const s = m.aPantalla({ x: 1000, y: 500 }, vista);
ok('el cursor propio se pinta donde clica: (1000,500) de la PC con escala 0,2', s.x === 200 && s.y === 140, s);
const r = m.arrastre({ x: 100, y: 100 }, 10, 0, 0.2, 1920, 1080);
ok('touchpad: 10 px de dedo con la imagen al 20 % son ~80 px de la PC', Math.round(r.x - 100) === Math.round(10 * m.GANANCIA_TOUCHPAD / 0.2), r);
ok('un toque es un toque, y un arrastre no', m.esToque(4, 120) && !m.esToque(40, 120) && !m.esToque(2, 800));
ok('los botones de VNC: izquierdo 1, derecho 4, rueda 8 y 16',
   m.BOTON.izquierdo === 1 && m.BOTON.derecho === 4 && m.BOTON.ruedaArriba === 8 && m.BOTON.ruedaAbajo === 16);
FINJS
while IFS='|' read -r res desc; do
    case "$res" in ok) ok "$desc" ;; fallo) fallo "$desc" ;; *) fallo "salida inesperada" "$res $desc" ;; esac
done < "$TMP/mando.txt"
afirmar "   dijeron algo (no reventó antes de empezar)" test "$(grep -c '^ok|' "$TMP/mando.txt")" -ge 10
afirmar "   sin nada por stderr" test ! -s "$TMP/mando.err"

titulo "2. La página lo lleva"
afirmar "pantalla-entrada.js monta el mando" grep -q "import { montar } from './mando.js'" "$REPO/remoto/app/scripts/pantalla-entrada.js"
afirmar "los escritorios mandan Super+número" grep -q "combinacion(\['XK_Super_L', String(n)\])" "$MANDO"
afirmar "la app empieza en modo mando" grep -q "useState<'mando' | 'tactil'>('mando')" "$REPO/remoto/app/src/pantallas/Pantalla.tsx"

afirmar_intacta_la_casa_real
resumen
