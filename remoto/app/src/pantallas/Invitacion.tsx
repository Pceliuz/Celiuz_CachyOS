// Tengo una invitación (fase 8, «ayudar a un amigo»): entrar SIN cable a la PC
// de otra persona, por un rato. Ella la abre en SU PC («Invitar a alguien»),
// le sale un texto con la dirección, un código y una contraseña, y te lo manda.
// Aquí se pega el texto entero; la contraseña se pone después, al entrar.
//
// Antes, esa persona tiene que compartirte su PC por Tailscale (consola de
// Tailscale -> Share): sin eso, su PC no está en tu red y no se llega.
import { useState } from 'react';
import { ScrollView, TextInput, View } from 'react-native';

import * as almacen from '../almacen';
import { ErrorRemoto, aceptarInvitacion, leerInvitacion, type EquipoGuardado } from '../api/cliente';
import { nuevaClave, publica } from '../api/cripto';
import { azar, herramientas } from '../herramientas';
import { colores } from '../paleta';
import { Aviso, Boton, Pantalla, Texto, e as estilos, fondoRojo } from '../componentes/ui';

export default function Invitacion({ alTerminar, alVolver }: {
  alTerminar: (e: EquipoGuardado) => void;
  alVolver: () => void;
}) {
  const [texto, setTexto] = useState('');
  const [nombre, setNombre] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [trabajando, setTrabajando] = useState(false);
  const inv = leerInvitacion(texto);

  async function usar() {
    if (!inv) return;
    setTrabajando(true);
    setError(null);
    try {
      const clave = nuevaClave(azar);
      const r = await aceptarInvitacion(herramientas, inv, clave, publica(clave), nombre.trim() || 'Amigo');
      const e: EquipoGuardado = { dispositivo: r.dispositivo, equipo: r.equipo, direccion: r.direccion,
                                  permisos: r.permisos, pase_hasta: r.pase_hasta, expira: r.expira ?? null };
      await almacen.guardarEquipo(e, clave);
      alTerminar(e);
    } catch (err) {
      const e = err as ErrorRemoto;
      setError(e.codigo === 'red'
        ? 'No llego a esa PC. ¿Te la compartió por Tailscale? ¿Está encendida?'
        : e.codigo === 'firma'
          ? 'La invitación no vale: caducó (dura 15 minutos), ya se usó, o el código está mal. Pide otra.'
          : e.message);
    } finally {
      setTrabajando(false);
    }
  }

  return (
    <Pantalla>
      <ScrollView contentContainerStyle={{ gap: 16, paddingVertical: 20 }} keyboardShouldPersistTaps="handled">
        <Texto tipo="grande">Tengo una invitación</Texto>
        <Texto color={colores.tenue}>
          Para ayudar a alguien con su PC sin ir a su casa. Pega aquí el texto que te mandó: trae la dirección, un código y una contraseña. Vale 15 minutos y una sola vez, y el acceso caduca solo en unas horas.
        </Texto>
        <TextInput accessibilityLabel="El texto de la invitación" value={texto} onChangeText={setTexto} multiline
                   placeholder="Celiuz Remoto — invitación a…" placeholderTextColor={colores.tenue}
                   autoCapitalize="none" autoCorrect={false} selectionColor={colores.neon}
                   style={[estilos.campo, { minHeight: 140, textAlignVertical: 'top', letterSpacing: 0, fontSize: 14, paddingTop: 12 }]} />
        {texto && !inv ? <Texto tipo="chico" color={colores.atencion}>No encuentro la dirección (100.x.y.z:puerto) o el código de 16 letras.</Texto> : null}
        {inv ? <Texto tipo="chico" color={colores.exito}>{`PC en ${inv.direccion} · código ${inv.codigo.replace(/(.{4})(?!$)/g, '$1-')}`}</Texto> : null}
        <View style={{ gap: 8 }}>
          <Texto tipo="etiqueta">Tu nombre (lo verá en su PC)</Texto>
          <TextInput accessibilityLabel="Tu nombre" value={nombre} onChangeText={setNombre} maxLength={40}
                     placeholderTextColor={colores.tenue} placeholder="Rodrigo" selectionColor={colores.neon}
                     style={[estilos.campo, { letterSpacing: 0, fontSize: 15 }]} />
        </View>
        {error ? <Aviso texto={error} color={colores.alerta} fondo={fondoRojo} /> : null}
        <Boton texto="Usar la invitación" alPulsar={usar} cargando={trabajando} desactivado={!inv} />
        <Boton texto="Volver" tipo="borde" alto={48} alPulsar={alVolver} />
        <Texto tipo="chico">Antes, quien te invita tiene que compartirte su PC por Tailscale (en la consola de Tailscale: la PC → Share). La contraseña de la invitación la pones luego, al entrar.</Texto>
      </ScrollView>
    </Pantalla>
  );
}
