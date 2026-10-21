// Inicio (pantalla 2 de las maquetas): el estado del equipo en tiempo real,
// por el WebSocket /v0/vivo. Solo se enseña lo que el equipo tiene: sin
// sensor no hay temperatura, sin GPU dedicada no hay VRAM, sin bateria no sale.
//
// Apagar, Apps, Archivos y Terminal estan en la maqueta pero llegan en las
// fases 4, 6 y 7 (remoto/DISEÑO.md, «Fases»): se ven, apagados, con «pronto».
import { useEffect, useState } from 'react';
import { Pressable, ScrollView, View } from 'react-native';

import type { Conexion } from '../api/cliente';
import type { Estado } from '../api/protocolo';
import * as f from '../formato';
import { colores } from '../paleta';
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

const PESTANAS = ['Inicio', 'Apps', 'Archivos', 'Terminal'];

export default function Inicio({ conexion, cpu, alSalir, alCaducar, alVerPase }: {
  conexion: Conexion;
  cpu: string | null;
  alSalir: () => void;
  alCaducar: (sesionCaducada: boolean) => void;
  alVerPase: () => void;
}) {
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
              <Cifra titulo={`CPU · ${f.familiaCpu(cpu)}`} cifra={`${estado.cpu.uso}%`}
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

        <View style={{ flexDirection: 'row', gap: 10, marginTop: 6 }}>
          {['Apagar', 'Reiniciar', 'Suspender'].map((t, i) => (
            <View key={t} style={{ flex: 1 }}>
              <Boton texto={t} tipo={i === 0 ? 'peligro' : 'borde'} alto={64} desactivado />
            </View>
          ))}
        </View>
        <Texto tipo="chico" centrado>Apagar, reiniciar y suspender: pronto (fase 4).</Texto>
        <Boton texto="Salir" tipo="borde" alto={48} alPulsar={alSalir} />
      </ScrollView>

      <View style={{ height: 64, borderTopWidth: 1, borderTopColor: colores.apagado, backgroundColor: colores.superficie,
                     flexDirection: 'row' }}>
        {PESTANAS.map((p, i) => (
          <View key={p} accessibilityState={{ disabled: i > 0 }} style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: 2,
                                                                          opacity: i === 0 ? 1 : 0.45 }}>
            <Texto tipo="chico" color={i === 0 ? colores.neon : colores.tenue}>{p}</Texto>
            {i > 0 ? <Texto tipo="chico">pronto</Texto> : null}
          </View>
        ))}
      </View>
    </Pantalla>
  );
}
