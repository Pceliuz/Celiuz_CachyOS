// Inicio (pantalla 2 de las maquetas): el estado del equipo en tiempo real,
// por el WebSocket /v0/vivo. Solo se enseña lo que el equipo tiene: sin
// sensor no hay temperatura, sin GPU dedicada no hay VRAM, sin bateria no sale.
//
// Apagar/reiniciar/suspender abren la hoja de confirmar (HojaEnergia); con una
// cuenta atras en marcha, sale arriba con «Cancelar». Con la PC en la pantalla
// de inicio (tras reiniciar), una tarjeta ofrece «Entrar»: la sesion arranca
// bloqueada (remoto/DISEÑO.md, «Tras reiniciar»). Archivos y Terminal
// llegan en las fases 6 y 7: en la barra de abajo, con «pronto».
import { useEffect, useState } from 'react';
import { Alert, Pressable, ScrollView, View } from 'react-native';

import type { Conexion, ErrorRemoto } from '../api/cliente';
import type { AccionEnergia, Equipo, Estado } from '../api/protocolo';
import * as f from '../formato';
import { colores } from '../paleta';
import HojaEnergia from '../componentes/HojaEnergia';
import Pestanas, { type Pestana } from '../componentes/Pestanas';
import { Barra, Boton, Pantalla, Tarjeta, Texto, fondoRojo, fondoVerde, verde } from '../componentes/ui';

function Cifra({ titulo, cifra, detalle }: { titulo: string; cifra: string; detalle?: string }) {
  return (
    <Tarjeta estilo={{ flexBasis: '47%', flexGrow: 1, gap: 6 }}>
      <Texto tipo="chico">{titulo}</Texto>
      <Texto tipo="cifra">{cifra}</Texto>
      {detalle ? <Texto tipo="chico">{detalle}</Texto> : null}
    </Tarjeta>
  );
}

function Fila({ titulo, valor }: { titulo: string; valor: string }) {
  return (
    <Tarjeta estilo={{ flexDirection: 'row', justifyContent: 'space-between' }}>
      <Texto color={colores.tenue}>{titulo}</Texto>
      <Texto>{valor}</Texto>
    </Tarjeta>
  );
}

export default function Inicio({ conexion, datos, alSalir, alCaducar, alVerPase, alCambiar }: {
  conexion: Conexion;
  datos: Equipo | null;
  alSalir: () => void;
  alCaducar: (sesionCaducada: boolean) => void;
  alVerPase: () => void;
  alCambiar: (p: Pestana) => void;
}) {
  const [hoja, setHoja] = useState<AccionEnergia | null>(null);
  const [apps, setApps] = useState<number | null>(null);
  const [enviando, setEnviando] = useState(false);
  const puedeEnergia = conexion.sesion.permisos.includes('energia');

  async function abrirHoja(a: AccionEnergia) {
    setHoja(a);
    setApps(null);
    if (conexion.sesion.permisos.includes('ventanas')) {
      conexion.ventanas().then((v) => setApps(v.length)).catch(() => setApps(null));
    }
  }

  async function confirmar() {
    if (!hoja) return;
    setEnviando(true);
    try {
      await conexion.energia(hoja);
      setHoja(null);
    } catch (e) {
      Alert.alert('No se pudo', (e as ErrorRemoto).message);
    } finally {
      setEnviando(false);
    }
  }

  async function cancelarEnergia() {
    try {
      await conexion.cancelarEnergia();
    } catch (e) {
      Alert.alert('No se pudo cancelar', (e as ErrorRemoto).message);
    }
  }
  const [entrando, setEntrando] = useState(false);

  function entrarEscritorio() {
    Alert.alert('¿Abrir la sesión?',
      'La PC entra en tu sesión y la deja bloqueada: delante de ella seguirá haciendo falta tu contraseña de Linux.',
      [{ text: 'Cancelar', style: 'cancel' },
       { text: 'Entrar', onPress: async () => {
         setEntrando(true);
         try {
           await conexion.entrarEscritorio();
         } catch (e) {
           setEntrando(false);
           Alert.alert('No se pudo entrar', (e as ErrorRemoto).message);
         }
       } }]);
  }
  const [estado, setEstado] = useState<Estado | null>(null);
  const [ultimo, setUltimo] = useState(0);
  const [ahora, setAhora] = useState(() => new Date());

  useEffect(() => {
    const cerrar = conexion.vivo(
      (e) => { setEstado(e); setUltimo(Date.now()); setAhora(new Date()); },
      (caducada) => alCaducar(caducada),
    );
    return cerrar;
  }, [conexion, alCaducar]);

  // Sin mensajes en 5 s: la conexion se perdio aunque el socket no lo diga.
  const [sinSenal, setSinSenal] = useState(false);
  useEffect(() => {
    const t = setInterval(() => setSinSenal(ultimo > 0 && Date.now() - ultimo > 5000), 1000);
    return () => clearInterval(t);
  }, [ultimo]);

  const pase = f.pase(estado?.pase_hasta ?? conexion.sesion.pase_hasta, ahora);
  const escritorio = estado?.escritorio;
  // «Entrando…» hasta que la sesion se abra (o, si falla, vuelva a poder entrar).
  useEffect(() => {
    if (escritorio?.sesion === 'abierta') setEntrando(false);
  }, [escritorio?.sesion]);
  // Si la PC no llega a abrirla (SDDM tardó, o el ayudante de root dijo que no:
  // queda en su diario), a los 2 min se vuelve a ofrecer.
  useEffect(() => {
    if (!entrando) return;
    const t = setTimeout(() => setEntrando(false), 120000);
    return () => clearTimeout(t);
  }, [entrando]);
  const gpu = estado?.gpu?.[0];

  return (
    <Pantalla relleno={false}>
      <View style={{ paddingHorizontal: 20, paddingTop: 20, paddingBottom: 10, flexDirection: 'row', alignItems: 'center', gap: 12 }}>
        <View style={{ flex: 1, gap: 3 }}>
          <Texto tipo="chico">Conectado a</Texto>
          <Texto tipo="grande">{conexion.equipo.equipo}</Texto>
        </View>
        <View style={{ borderRadius: 999, paddingHorizontal: 10, paddingVertical: 6,
                       backgroundColor: sinSenal || !estado ? fondoRojo : fondoVerde }}>
          <Texto tipo="chico" color={sinSenal || !estado ? colores.alerta : verde}>
            {!estado ? 'Conectando…' : sinSenal ? 'Sin señal' : 'En línea'}
          </Texto>
        </View>
      </View>

      <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 16, gap: 12 }}>
        {estado?.energia ? (
          <Tarjeta estilo={{ backgroundColor: fondoRojo, borderColor: colores.alerta, gap: 10 }}>
            <Texto tipo="grande" color={colores.luz}>
              {{ apagar: 'Se apaga', reiniciar: 'Se reinicia', suspender: 'Se suspende' }[estado.energia.accion]} en {estado.energia.quedan} s
            </Texto>
            <Texto tipo="chico" color={colores.luz}>
              {estado.energia.origen === 'pc' ? 'Lo pidió la vigilancia de la PC.' : `Lo pidió «${estado.energia.origen}».`}
            </Texto>
            {puedeEnergia ? <Boton texto="Cancelar" tipo="borde" alto={48} alPulsar={cancelarEnergia} /> : null}
          </Tarjeta>
        ) : null}
        {escritorio?.sesion === 'pantalla_inicio' || entrando ? (
          <Tarjeta estilo={{ gap: 10, borderColor: colores.amatista }}>
            <Texto tipo="grande">{entrando ? 'Entrando…' : 'En la pantalla de inicio'}</Texto>
            <Texto tipo="chico">
              {entrando
                ? 'La PC está abriendo tu sesión. Arranca bloqueada.'
                : 'Nadie ha entrado desde que arrancó. Puedes abrir la sesión desde aquí: queda bloqueada.'}
            </Texto>
            {entrando ? null : !puedeEnergia ? (
              <Texto tipo="chico" color={colores.tenue}>Este celular no tiene permiso de energía (se da desde la PC).</Texto>
            ) : !escritorio?.puede_entrar ? (
              <Texto tipo="chico" color={colores.atencion}>{escritorio?.motivo}</Texto>
            ) : !pase.vigente ? (
              <Boton texto="Entrar necesita el pase" tipo="borde" alto={48} alPulsar={alVerPase} />
            ) : (
              <Boton texto="Entrar" alto={48} alPulsar={entrarEscritorio} />
            )}
          </Tarjeta>
        ) : null}
        <Pressable accessibilityRole="button" onPress={pase.vigente ? undefined : alVerPase}>
          <Tarjeta estilo={{ gap: 10 }}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
              <Texto>Pase de 24 h</Texto>
              <Texto color={pase.vigente ? colores.atencion : colores.alerta}>{pase.texto}</Texto>
            </View>
            <Barra valor={pase.queda} color={pase.vigente ? colores.amatista : colores.alerta} />
            <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
              <Texto tipo="chico">Vigilancia: {estado?.vigilancia ?? '…'}</Texto>
              <Texto tipo="chico">{pase.vigente ? `quedan ${pase.restante}` : 'toca para ver cómo renovarlo'}</Texto>
            </View>
          </Tarjeta>
        </Pressable>

        {estado ? (
          <>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
              <Cifra titulo={`CPU · ${f.familiaCpu(datos?.cpu)}`} cifra={`${estado.cpu.uso}%`}
                     detalle={estado.cpu.temp !== undefined ? `${estado.cpu.temp} °C` : undefined} />
              {gpu ? (
                <Cifra titulo={`GPU · ${gpu.nombre}`}
                       cifra={gpu.dormida ? 'dormida' : gpu.uso !== undefined ? `${gpu.uso}%` : '—'}
                       detalle={[gpu.temp !== undefined ? `${gpu.temp} °C` : '',
                                 gpu.vram ? `VRAM ${f.decimal(gpu.vram[0])} / ${f.decimal(gpu.vram[1], 0)} GB` : '']
                                .filter(Boolean).join(' · ') || undefined} />
              ) : null}
              <Cifra titulo="RAM" cifra={f.gb(estado.ram[0])} detalle={`de ${f.gb(estado.ram[1])}`} />
              <Cifra titulo="Disco" cifra={f.gb(estado.disco[1] - estado.disco[0])} detalle={`libres de ${f.gb(estado.disco[1])}`} />
              {estado.bateria ? (
                <Cifra titulo="Batería" cifra={`${estado.bateria.nivel}%`}
                       detalle={estado.bateria.cargando ? 'cargando' : 'con batería'} />
              ) : null}
            </View>
            <Fila titulo="Red" valor={`↓ ${f.velocidad(estado.red.bajada)} · ↑ ${f.velocidad(estado.red.subida)}`} />
            <Fila titulo="Encendida desde" valor={f.desde(estado.encendida_desde, ahora)} />
          </>
        ) : (
          <Tarjeta><Texto color={colores.tenue}>Esperando el estado de la PC…</Texto></Tarjeta>
        )}

        {puedeEnergia ? (
          <View style={{ flexDirection: 'row', gap: 10, marginTop: 6 }}>
            {(['apagar', 'reiniciar', 'suspender'] as AccionEnergia[]).map((a, i) => (
              <View key={a} style={{ flex: 1 }}>
                <Boton texto={a[0].toUpperCase() + a.slice(1)} tipo={i === 0 ? 'peligro' : 'borde'} alto={64}
                       alPulsar={() => abrirHoja(a)} desactivado={!!estado?.energia} />
              </View>
            ))}
          </View>
        ) : (
          <Texto tipo="chico" centrado>Este celular no tiene permiso para apagar (se da desde la PC).</Texto>
        )}
        <Boton texto="Salir" tipo="borde" alto={48} alPulsar={alSalir} />
      </ScrollView>

      <Pestanas actual="inicio" permisos={conexion.sesion.permisos} alCambiar={alCambiar} />
      <HojaEnergia accion={hoja} equipo={conexion.equipo.equipo} apps={apps}
                   segundos={datos?.cuenta_atras ?? 60} enviando={enviando} alConfirmar={confirmar} alCerrar={() => setHoja(null)} />
    </Pantalla>
  );
}
