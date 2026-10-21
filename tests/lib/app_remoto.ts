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
import * as a from '../../remoto/app/src/archivos.ts';
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
  comprobar('   y dice que la sesión está abierta (fase 5)', estados.some((x) => x.escritorio?.sesion === 'abierta'),
            estados[0]?.escritorio);
  const ab = await error(con.entrarEscritorio());
  comprobar('entrarEscritorio() con la sesión abierta: «estado»', ab?.codigo === 'estado', ab?.codigo);
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

// Fase 6: el explorador, con el código de la app. La casa de mentira la monta
// remoto-app.sh (Documentos/nota.txt, .ssh/id_ed25519).
function cuentasDeArchivos() {
  comprobar('tamaños como Dolphin', a.tamano(48 * 1024) === '48 KB' && a.tamano(1.2 * 1024 * 1024) === '1,2 MB'
            && a.tamano(512) === '512 B' && a.tamano(8.4 * 1024 ** 3) === '8,4 GB',
            [a.tamano(48 * 1024), a.tamano(1.2 * 1024 * 1024), a.tamano(8.4 * 1024 ** 3)]);
  const m = a.migas('Documentos/CV');
  comprobar('migas desde la carpeta personal', m.length === 3 && m[2].ruta === 'Documentos/CV' && m[0].ruta === '', m);
  comprobar('padre y unir', a.padre('Documentos/CV') === 'Documentos' && a.padre('Documentos') === ''
            && a.unir('', 'x') === 'x' && a.unir('a', 'x') === 'a/x');
  comprobar('cada copia, por equipo y ruta (dos PCs con el mismo Documentos/nota.txt)',
            a.claveGuardado('PC', 'Documentos/nota.txt') !== a.claveGuardado('Laptop', 'Documentos/nota.txt'));
  comprobar('los textos se ven en la app (un .md sin app de markdown)', a.esTexto('notas.md') && a.esTexto('kitty.conf')
            && a.esTexto('.bashrc') && !a.esTexto('foto.png') && !a.esTexto('informe.docx'));
  comprobar('clase por extensión, sin mayúsculas', a.clase('Informe.PDF') === 'pdf' && a.clase('x', 'carpeta') === 'carpeta'
            && a.clase('sin-extension') === 'otro');
  comprobar('el tipo para abrirlo', a.mime('foto.JPG') === 'image/jpeg' && a.mime('raro.xyz') === 'application/octet-stream');
  comprobar('miniatura solo de imagen y vídeo (lo mismo que archivos.py)', a.tieneMiniatura('a.png') && a.tieneMiniatura('b.mkv')
            && !a.tieneMiniatura('c.pdf'));
  const ahora = new Date('2026-10-21T04:00:00Z'); // 23:00 del 20 en la PC (-05:00)
  comprobar('agrupar: hoy, en la zona de la PC', a.grupo('2026-10-20T08:00:00-05:00', ahora) === 'Hoy',
            a.grupo('2026-10-20T08:00:00-05:00', ahora));
  comprobar('   ayer', a.grupo('2026-10-19T23:59:00-05:00', ahora) === 'Ayer');
  comprobar('   esta semana y antes', a.grupo('2026-10-16T10:00:00-05:00', ahora) === 'Esta semana'
            && a.grupo('2026-09-01T10:00:00-05:00', ahora) === 'Antes');
}

async function explorar() {
  const { equipo, clave } = JSON.parse(readFileSync(`${TMP}/equipo.json`, 'utf8'));
  const con = await c.entrar(h, equipo, clave, contrasena);
  const casa = await con.archivos('');
  comprobar('archivos(""): la carpeta personal', casa.ruta === '' && casa.entradas.some((e) => e.nombre === 'Documentos'), casa);
  comprobar('   sin .ssh', !casa.entradas.some((e) => e.nombre === '.ssh'));
  const docs = await con.archivos('Documentos');
  const nota = docs.entradas.find((e) => e.nombre === 'nota.txt');
  comprobar('archivos("Documentos"): con su tamaño', nota?.tamano === 11, nota);
  const fuera = await error(con.archivos('../'));
  comprobar('salir de casa: «fuera»', fuera?.codigo === 'fuera', fuera?.codigo);
  const b = await con.buscar('', 'nota');
  comprobar('buscar() encuentra por nombre', b.resultados.some((r) => r.ruta === 'Documentos/nota.txt'), b);
  const r = await fetch(con.urlDescarga('Documentos/nota.txt'), { headers: con.cabeceras() });
  comprobar('urlDescarga() + cabeceras(): lo que usa el gestor de descargas', r.status === 200 && (await r.text()) === 'hola mundo\n');
  const sinToken = await fetch(con.urlDescarga('Documentos/nota.txt'));
  comprobar('   y sin la cabecera no baja nada', sinToken.status === 401, sinToken.status);
  const rec = await con.recientes();
  comprobar('recientes(): la acaba de bajar, igual que en la PC', rec[0]?.ruta === 'Documentos/nota.txt' && rec[0].estado === 'igual', rec[0]);
  comprobar('   con su nombre y su carpeta', rec[0]?.nombre === 'nota.txt' && rec[0].carpeta === 'Documentos');
  const fav = await con.fijar('Documentos');
  comprobar('fijar()', fav.length === 1 && fav[0].tipo === 'carpeta' && fav[0].existe, fav);
  const otra = await con.archivos('');
  comprobar('   y el listado lo marca', otra.entradas.find((e) => e.nombre === 'Documentos')?.favorito === true);
  comprobar('soltar()', (await con.soltar('Documentos')).length === 0);
  await con.olvidarReciente('Documentos/nota.txt');
  comprobar('olvidarReciente()', (await con.recientes()).length === 0);
}

// Fase 8: entrar SIN cable con la invitación que abrió la PC. El texto es el
// de verdad (remoto-app.sh lo pide al socket de control y lo deja en un
// fichero), como lo pegaría la persona.
async function invitacion() {
  const d = JSON.parse(readFileSync(`${TMP}/invitacion.json`, 'utf8'));
  const inv = c.leerInvitacion(d.texto);
  comprobar('leerInvitacion() saca la dirección y el código del texto de la PC',
            inv?.codigo === d.codigo.replaceAll('-', '') && inv?.direccion.endsWith(`:${puertoRed}`), { inv, texto: d.texto });
  comprobar('   y vale pegado en minúsculas y con espacios',
            c.leerInvitacion(`${inv!.direccion} ${d.codigo.toLowerCase().replaceAll('-', ' ')}`)?.codigo === inv!.codigo);
  comprobar('   sin código no hay invitación', c.leerInvitacion(`Dirección: ${inv!.direccion}`) === null);
  const clave = nuevaClave(azar);
  const r = await c.aceptarInvitacion(h, inv!, clave, publica(clave), 'Amigo de Node');
  comprobar('aceptarInvitacion(): entra, con su hora de caducidad', !!r.dispositivo && !!r.expira && r.permisos.includes('estado'), r);
  const e: c.EquipoGuardado = { dispositivo: r.dispositivo, equipo: r.equipo, direccion: r.direccion,
                                permisos: r.permisos, pase_hasta: r.pase_hasta, expira: r.expira };
  const con = await c.entrar(h, e, clave, d.contrasena);
  comprobar('   y luego entra con la contraseña de la invitación', !!con.sesion.token);
  const otra = await error(c.aceptarInvitacion(h, inv!, nuevaClave(azar), publica(nuevaClave(azar)), 'Otro'));
  comprobar('la misma invitación otra vez: «firma» (un solo uso)', otra?.codigo === 'firma', otra?.codigo);
}

async function sinPase() {
  const { equipo, clave } = JSON.parse(readFileSync(`${TMP}/equipo.json`, 'utf8'));
  const con = await c.entrar(h, equipo, clave, contrasena);
  const e = await error(con.cerrarVentana('0xaaa'));
  comprobar('sin pase, cerrar apps da «pase_vencido» (y la app enseña cómo renovarlo)', e?.codigo === 'pase_vencido', e?.codigo);
  const en = await error(con.entrarEscritorio());
  comprobar('sin pase, entrar desde la pantalla de inicio da «pase_vencido»', en?.codigo === 'pase_vencido', en?.codigo);
  comprobar('   pero apagar sí funciona sin pase', (await con.energia('suspender')).accion === 'suspender');
  await con.cancelarEnergia();
}

try {
  if (fase === 'emparejar') { enlacesYFormatos(); cuentasDeArchivos(); await emparejarYEntrar(); }
  else if (fase === 'archivos') await explorar();
  else if (fase === 'invitacion') await invitacion();
  else if (fase === 'control') await controlar();
  else if (fase === 'sinpase') await sinPase();
  else await renovarPase();
} catch (e) {
  comprobar(`sin excepciones: ${(e as Error).message}`, false);
}
