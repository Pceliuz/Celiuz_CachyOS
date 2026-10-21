// tests/lib/app_remoto.ts — el codigo de la APP del celular (remoto/app/src),
// el mismo que va en el APK, ejecutado con Node contra el servidor de verdad.
// Lo lanza tests/e2e/remoto-app.sh; imprime «ok|texto» o «fallo|texto».
//
//   node app_remoto.ts <puerto_red> <puerto_usb> <codigo_emparejar> <contrasena> <fase>
//
// fase «emparejar»: hola + emparejar + entrar + estado; deja lo emparejado en
// $TMP/equipo.json. Fase «renovar»: renueva con el codigo dado.
import { randomBytes } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';

import * as c from '../../remoto/app/src/api/cliente.ts';
import { nuevaClave, publica } from '../../remoto/app/src/api/cripto.ts';
import * as f from '../../remoto/app/src/formato.ts';

const [puertoRed, puertoUsb, codigo, contrasena, fase] = process.argv.slice(2);
const TMP = process.env.TMP!;
const azar = (n: number) => new Uint8Array(randomBytes(n));

function comprobar(desc: string, cond: boolean, detalle?: unknown) {
  console.log((cond ? 'ok|' : 'fallo|') + desc + (cond || detalle === undefined ? '' : ` -> ${JSON.stringify(detalle)}`));
}

const h: c.Herramientas = {
  fetch,
  // En Node el WebSocket (undici) admite cabeceras en un objeto de opciones;
  // en React Native van como tercer argumento. Por eso lo inyecta quien llama.
  abrirSocket: (url, cabeceras) => new (WebSocket as any)(url, { headers: cabeceras }) as c.Socket,
};

async function error(p: Promise<unknown>): Promise<c.ErrorRemoto | null> {
  try { await p; return null; } catch (e) { return e as c.ErrorRemoto; }
}

async function emparejarYEntrar() {
  const hola = await c.hola(h, Number(puertoUsb));
  comprobar('hola por el canal USB dice que toca emparejar', hola.modo === 'emparejar', hola);

  const clave = nuevaClave(azar);
  const r = await c.emparejar(h, Number(puertoUsb), codigo, clave, publica(clave), 'Celular de Node');
  comprobar('la PC acepta la clave pública y la firma hechas por la app', !!r.dispositivo, r);
  comprobar('   y da el pase de 24 h al emparejar', f.pase(r.pase_hasta, new Date()).vigente, r.pase_hasta);
  const equipo: c.EquipoGuardado = { dispositivo: r.dispositivo, equipo: r.equipo, direccion: r.direccion,
                                     permisos: r.permisos, pase_hasta: r.pase_hasta };
  writeFileSync(`${TMP}/equipo.json`, JSON.stringify({ equipo, clave }));

  comprobar('urlRed sale de la dirección que dio la PC', c.urlRed(equipo.direccion) === `http://127.0.0.1:${puertoRed}`);
  const ms = await c.enLinea(h, equipo);
  comprobar('«en línea» mide lo que tarda la PC', ms !== null && ms >= 0, ms);
  comprobar('una PC que no contesta sale apagada, y pronto (no un minuto)',
            (await c.enLinea(h, { ...equipo, direccion: '127.0.0.1:1' })) === null);

  const mal = await error(c.entrar(h, equipo, clave, 'mala'));
  comprobar('contraseña mal: error «contrasena» con los intentos que quedan',
            mal?.codigo === 'contrasena' && mal.intentosRestantes === 4, mal && { ...mal, m: mal.message });
  const otraClave = nuevaClave(azar);
  const ajena = await error(c.entrar(h, equipo, otraClave, contrasena));
  comprobar('con la clave de OTRO celular no entra', ajena?.codigo === 'firma', ajena?.codigo);

  const con = await c.entrar(h, equipo, clave, contrasena);
  comprobar('con su clave y la contraseña, entra', !!con.sesion.token);
  const datos = await con.datosEquipo();
  comprobar('datos del equipo, con los segundos de la cuenta atrás de la PC', datos.protocolo === 0 && datos.ram > 0 && datos.cuenta_atras === 30, datos);

  const estados: any[] = [];
  let caducada: boolean | null = null;
  const cerrar = con.vivo((e) => estados.push(e), (s) => { caducada = s; });
  await new Promise((r) => setTimeout(r, 2600));
  comprobar('/v0/vivo llega cada segundo al cliente de la app', estados.length >= 2, estados.length);
  comprobar('   con los campos que pinta Inicio', estados.length > 0 && estados[0].cpu.uso >= 0 && estados[0].ram[1] > 0);
  cerrar();
  comprobar('   cerrarlo a mano no se toma por sesión caducada', caducada === null);

  // Sin token valido: el socket se cierra (no se abre), y la app vuelve a entrar
  const falsa = new c.Conexion(h, equipo, { ...con.sesion, token: 'inventado' });
  let motivo: boolean | null = null;
  falsa.vivo(() => {}, (s) => { motivo = s; });
  await new Promise((r) => setTimeout(r, 1500));
  comprobar('un token que no vale cierra el socket', motivo !== null);
  await con.salir();
  const tras = await error(con.datosEquipo());
  comprobar('tras salir, el token ya no vale', tras?.codigo === 'sin_sesion', tras?.codigo);
}

async function renovarPase() {
  const { equipo, clave } = JSON.parse(readFileSync(`${TMP}/equipo.json`, 'utf8'));
  const hola = await c.hola(h, Number(puertoUsb));
  comprobar('hola dice que toca renovar', hola.modo === 'renovar' && hola.equipo === equipo.equipo, hola);
  const mal = await error(c.renovar(h, Number(puertoUsb), codigo, clave, equipo.dispositivo, 'mala'));
  comprobar('renovar con la contraseña mal, no', mal?.codigo === 'contrasena', mal?.codigo);
  const r = await c.renovar(h, Number(puertoUsb), codigo, clave, equipo.dispositivo, contrasena);
  const p = f.pase(r.pase_hasta, new Date());
  comprobar('renovar con la buena: 24 h', p.vigente && p.restante.startsWith('23 h 59') || p.restante.startsWith('24 h'), p);
}

function enlacesYFormatos() {
  const e = c.leerEnlace('celiuzremoto://emparejar/AbCdEfGhIjKlMnOpQrSt_-12?p=47111');
  comprobar('lee el enlace con que la PC abre la app', e?.modo === 'emparejar' && e.puerto === 47111, e);
  comprobar('sin ?p= usa el puerto de fábrica', c.leerEnlace('celiuzremoto://renovar/AbCdEfGhIjKlMnOpQrSt')?.puerto === 47111);
  for (const malo of ['celiuzremoto://borrar/AbCdEfGhIjKlMnOpQrSt', 'celiuzremoto://emparejar/corto',
                      'celiuzremoto://emparejar/AbCdEfGhIjKlMnOpQrSt?p=80', 'https://x/emparejar/AbCdEfGhIjKlMnOpQrSt',
                      'celiuzremoto://emparejar/AbCdEfGhIjKlMnOpQrSt;rm']) {
    comprobar(`rechaza un enlace raro: ${malo}`, c.leerEnlace(malo) === null);
  }
  const ahora = new Date('2026-10-21T04:00:00Z'); // 23:00 del 20 en -05:00
  comprobar('«vence mañana 23:40»', f.pase('2026-10-21T23:40:00-05:00', ahora).texto === 'vence mañana 23:40',
            f.pase('2026-10-21T23:40:00-05:00', ahora));
  comprobar('el día se cuenta en la zona de la PC, no en UTC',
            f.pase('2026-10-20T23:40:00-05:00', ahora).texto === 'vence hoy 23:40');
  comprobar('«quedan 24 h 40 min»', f.pase('2026-10-21T23:40:00-05:00', ahora).restante === '24 h 40 min');
  comprobar('vencido', f.pase('2026-10-20T22:00:00-05:00', ahora).texto === 'venció hoy a las 22:00');
  comprobar('velocidades', f.velocidad(2400000) === '2,4 MB/s' && f.velocidad(140000) === '140 KB/s');
  comprobar('GB con coma', f.gb(7.1) === '7,1 GB' && f.gb(31.2) === '31 GB' && f.gb(1863) === '1,8 TB', [f.gb(7.1), f.gb(31.2), f.gb(1863)]);
  comprobar('familia de la CPU', f.familiaCpu('AMD Ryzen 5 5500') === 'Ryzen' && f.familiaCpu(null) === 'CPU');
  comprobar('hace 6 h 12 min', f.desde('2026-10-20T16:48:00-05:00', ahora) === 'hace 6 h 12 min',
            f.desde('2026-10-20T16:48:00-05:00', ahora));
}

async function controlar() {
  const { equipo, clave } = JSON.parse(readFileSync(`${TMP}/equipo.json`, 'utf8'));
  const con = await c.entrar(h, equipo, clave, contrasena);
  const e = await con.energia('apagar');
  comprobar('energia(): empieza la cuenta atrás en la PC', e.accion === 'apagar' && e.quedan > 0, e);
  const estados: any[] = [];
  const cerrar = con.vivo((x) => estados.push(x), () => {});
  await new Promise((r) => setTimeout(r, 1300));
  cerrar();
  comprobar('   y el estado en vivo trae la cuenta atrás', estados.some((x) => x.energia?.accion === 'apagar'), estados[0]?.energia);
  comprobar('cancelarEnergia() la para', (await con.cancelarEnergia()) === true);
  comprobar('   y no queda nada que cancelar', (await con.cancelarEnergia()) === false);
  const vs = await con.ventanas();
  comprobar('ventanas() trae las apps de la PC', vs.length === 2 && vs.some((v) => v.app === 'Brave'), vs);
  await con.cerrarVentana('0xaaa');
  comprobar('cerrarVentana() con pase: la PC la cierra', true);
  const no = await error(con.cerrarVentana('0xzzz'));
  comprobar('   una que ya no está: «no_existe»', no?.codigo === 'no_existe', no?.codigo);
  writeFileSync(`${TMP}/token`, con.sesion.token);
}

async function sinPase() {
  const { equipo, clave } = JSON.parse(readFileSync(`${TMP}/equipo.json`, 'utf8'));
  const con = await c.entrar(h, equipo, clave, contrasena);
  const e = await error(con.cerrarVentana('0xaaa'));
  comprobar('sin pase, cerrar apps da «pase_vencido» (y la app enseña cómo renovarlo)', e?.codigo === 'pase_vencido', e?.codigo);
  comprobar('   pero apagar sí funciona sin pase', (await con.energia('suspender')).accion === 'suspender');
  await con.cancelarEnergia();
}

try {
  if (fase === 'emparejar') { enlacesYFormatos(); await emparejarYEntrar(); }
  else if (fase === 'control') await controlar();
  else if (fase === 'sinpase') await sinPase();
  else await renovarPase();
} catch (e) {
  comprobar(`sin excepciones: ${(e as Error).message}`, false);
}
