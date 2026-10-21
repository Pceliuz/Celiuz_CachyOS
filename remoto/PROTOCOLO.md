# Celiuz Remoto — el protocolo (versión 0)

Lo que se dicen la app y el servidor. Es el contrato entre `app/` y
`servidor/`: si cambia aquí, cambia en los dos (y en `app/src/api/protocolo.ts`).
El porqué de cada regla está en `DISEÑO.md`.

Todo va bajo `/v0/`. Si un día cambia de forma incompatible, se abre `/v1/` y el
servidor sigue sirviendo `/v0/` hasta que no quede ninguna app vieja.

Lo marcado **(fase N)** todavía no existe en el servidor: contesta `404`.

## Dónde escucha

| Canal | Dirección | Para qué |
|---|---|---|
| **Red** | `http://<IP de Tailscale>:47110` | todo el uso normal |
| **USB** | `http://127.0.0.1:47111`, llevado al celular con `adb reverse` | emparejar y renovar el pase, y nada más |
| **Control** | `$XDG_RUNTIME_DIR/celiuz-remoto.sock` (0600) | la app de la PC y la CLI le hablan al servicio |

- Por la red **no hace falta TLS**: Tailscale ya cifra y autentica cada paquete
  (WireGuard). Escuchar solo en esa IP es lo que garantiza que no hay otro
  camino. **El servidor se niega a escuchar en cualquier dirección que no sea
  de Tailscale (100.64.0.0/10) o de bucle local**: nunca cae a `0.0.0.0`.
- El canal USB **solo está abierto mientras la app de la PC lo pide**
  (2 minutos), no siempre. Que la petición llegue por `adb reverse` es la
  prueba de que hay un cable entre los dos.

## Las llaves

1. **La clave del teléfono**: un par **Ed25519** que genera el celular al
   emparejar. La privada se queda en su almacén seguro; la PC guarda solo la
   **pública** (32 bytes, base64). El teléfono demuestra que es él firmando
   un reto. Ningún secreto suyo viaja ni vive en la PC.
2. **La contraseña de la app**: se crea en la PC al emparejar; la PC la
   comprueba contra su hash `scrypt`. Al **5.º fallo** seguido ese teléfono
   queda bloqueado y la PC lo avisa.
3. **La sesión** (`token`): la da la PC al entrar bien. Caduca tras 5 minutos
   sin uso (un `/v0/vivo` abierto cuenta como uso). Va en la cabecera
   `Authorization: Bearer <token>`. Un reinicio del servicio las borra todas.

Y encima, el **pase**: no es una llave que lleve el teléfono, es una fecha que
guarda la PC (`pase_hasta`). Las rutas marcadas «pase» contestan `423` si ya
pasó.

### Qué se firma

Siempre bytes UTF-8 de un texto con prefijo, para que una firma de una cosa no
valga para otra:

| Para | Texto firmado |
|---|---|
| entrar | `celiuz-remoto/v0/sesion:<reto>` |
| emparejar (prueba de que tiene la privada) | `celiuz-remoto/v0/emparejar:<codigo>` |
| renovar el pase | `celiuz-remoto/v0/renovar:<codigo>` |
| latido **(fase 4)** | `celiuz-remoto/v0/latido:<dispositivo>:<minuto UTC>:<0\|1>` |

Las firmas van en base64 (64 bytes).

## Respuestas de error (todas iguales)

```json
{"error": "pase_vencido", "mensaje": "El pase de 24 h venció a las 23:40."}
```

| HTTP | `error` | Cuándo |
|---|---|---|
| 400 | `peticion` | falta un campo o no es del tipo que toca |
| 401 | `sin_sesion` | falta el token o caducó → volver a entrar |
| 401 | `firma` | la firma no es de ese teléfono, o el reto no vale (caducó, ya se usó, no existe) |
| 401 | `contrasena` | contraseña mal; trae `intentos_restantes` |
| 403 | `bloqueado` | 5 fallos seguidos |
| 403 | `sin_permiso` | ese teléfono no tiene activado ese módulo |
| 404 | `no_existe` | ruta o recurso que no hay |
| 409 | `confirmar` | acción peligrosa sin `"confirmado": true` |
| 423 | `pase_vencido` | lo pedido necesita el pase |

Un `dispositivo` desconocido (o revocado) contesta lo mismo que una firma mala
(`401 firma`): por fuera no se puede saber qué ids existen.

## Red: `/v0/...`

### Entrar
- `GET /v0/reto?dispositivo=<id>` → `{"reto": "<32 bytes en base64url>", "caduca": 30}`.
  El reto vale una sola vez y 30 s. Un teléfono desconocido recibe un reto igual
  (que luego no valdrá): así no se distinguen.
- `POST /v0/sesion`
  `{"dispositivo": "<id>", "reto": "...", "firma": "<base64>", "contrasena": "..."}`
  → `{"token": "...", "caduca_en": 300, "pase_hasta": "2026-10-21T23:40:00-05:00" | null, "permisos": ["estado","energia"], "equipo": "Celiuz-CachyOS"}`
  Primero se mira la firma y después la contraseña: una firma mala no gasta
  intentos (no es el teléfono, y no debe poder bloquearlo).
- `DELETE /v0/sesion` → `{"ok": true}`.

### Estado en tiempo real — permiso `estado`
- `GET /v0/equipo` →
  `{"nombre": "Celiuz-CachyOS", "tipo": "escritorio", "cpu": "AMD Ryzen 5 5500", "gpus": ["NVIDIA GeForce RTX 3050"], "ram": 31.2, "bateria": false, "protocolo": 0}`
- `WS /v0/vivo` (con la cabecera `Authorization`) → cada segundo:
  ```json
  {"cpu": {"uso": 23, "temp": 52}, "gpu": [{"nombre": "RTX 3050", "uso": 31, "temp": 48, "vram": [1.2, 6]}],
   "ram": [8.4, 31.2], "disco": [508, 544], "red": {"bajada": 2400000, "subida": 140000},
   "bateria": null, "encendida_desde": "...", "pase_hasta": "..." | null, "vigilancia": "desarmada"}
  ```
  Solo van los campos que el equipo tiene: sin sensor no hay `temp`, sin GPU
  dedicada no hay `vram`, sin batería `bateria` es `null`. Una GPU dormida (la
  NVIDIA de un portátil híbrido) sale `{"nombre": ..., "dormida": true}` y **no
  se despierta** para medirla. RAM, VRAM y disco en GiB; red en bytes por segundo. `tipo` es el de
  `lib/maquina.py` (`portatil` / `escritorio`).
  Al caducar la sesión, el servidor cierra con el código 4401.

### Latido (vigilancia) — **(fase 4)**
- `POST /v0/latido` `{"dispositivo", "minuto", "apagando", "firma"}` — sin
  sesión: lo manda un servicio de fondo. Solo para el «me están apagando»; que
  el celular vive se mira en Tailscale (ver `DISEÑO.md`).

### Energía — permiso `energia` **(fase 4)**
- `POST /v0/energia` `{"accion": "apagar"|"reiniciar"|"suspender", "confirmado": true}`
  → `{"cuenta_atras": 60}`. La PC enseña la notificación cancelable.
- `DELETE /v0/energia` → cancelar desde el celular.

### Ventanas — permiso `ventanas` **(fase 4)**
- `GET /v0/ventanas` → `[{"id": "0x55d...", "app": "Brave", "titulo": "...", "escritorio": 2}]`
- `POST /v0/ventanas/<id>/cerrar` `{"confirmado": true}` — **pase**. Cierra
  pidiéndolo (como `SUPER+Q`), no matando.

### Archivos — permiso `archivos`, todo **pase** **(fase 6)**
- `GET /v0/archivos?ruta=Documentos` → `{"ruta": "...", "entradas": [{"nombre", "tipo": "carpeta"|"archivo", "tamano", "modificado"}]}`
  Las rutas son relativas a la carpeta personal; una que salga de ella (`..`,
  enlaces que apunten fuera) da `403`.
- `GET /v0/archivos/descargar?ruta=...` → el archivo (admite `Range`).
- `GET /v0/archivos/miniatura?ruta=...&lado=256` → JPEG.
- `GET /v0/recientes`, `GET/PUT/DELETE /v0/favoritos`.

### Terminal — **pase** + permiso `terminal` + contraseña otra vez **(fase 7)**
- `POST /v0/terminal` `{"contrasena": "..."}` → `{"terminal": "<id>"}`
- `WS /v0/terminal/<id>` → bytes en los dos sentidos; control `{"tamano": [filas, columnas]}`.

## USB: `/usb/...` (solo por `adb reverse`, solo con la app de la PC esperando)

La app de la PC abre la ventana con un `codigo` de un solo uso y se lo pasa a
la app del celular **por el cable**, abriéndola con un intent explícito:

```sh
adb shell am start -n com.celiuz.remoto/.MainActivity -d 'celiuzremoto://emparejar/<codigo>?p=47111'
adb shell am start -n com.celiuz.remoto/.MainActivity -d 'celiuzremoto://renovar/<codigo>?p=47111'
```

`p` es el puerto del canal USB, que en la PC se puede cambiar (`remoto.conf`).

Un intent con `-n` solo lo recibe esa app. El código impide que otra app del
celular, que también vería `127.0.0.1:47111` mientras dure el `adb reverse`,
se empareje aprovechando la ventana abierta.

- `GET /usb/hola` → `{"modo": "emparejar"|"renovar", "equipo": "Celiuz-CachyOS"}`
  (para que el celular sepa qué le toca enseñar). Sin ventana abierta: `404`.
- `POST /usb/emparejar` `{"codigo", "nombre": "Redmi Note 13", "publica": "<base64>", "firma"}`
  → `{"dispositivo": "<id>", "equipo": "Celiuz-CachyOS", "direccion": "100.x.y.z:47110", "permisos": [...], "pase_hasta": "..."}`.
  La contraseña NO se escribe en el celular: se creó en la PC al abrir la
  ventana. Emparejar **da el pase** de 24 h: se cumple lo que pide (el cable,
  y la contraseña recién creada delante de la PC).
- `POST /usb/renovar` `{"codigo", "dispositivo", "firma", "contrasena"}`
  → `{"pase_hasta": "..."}` (24 h exactas desde ahora, con el reloj de la PC).
  Una contraseña mala cuenta como fallo, igual que al entrar.

Las dos cierran la ventana al salir bien. Un `codigo` malo contesta `401
firma` y **no** la cierra (no vaya a ser que otra app del celular la tumbe
adrede); se cierra sola a los 2 minutos.

## Control: el socket de la PC

HTTP sobre un socket Unix, solo para el usuario (0600). Lo usan la CLI y la app
de la PC; nadie de fuera llega aquí.

- `POST /control/ventana` `{"modo": "emparejar", "contrasena": "...", "permisos": [...], "nombre": "...", "serie": "<adb>"}`
  o `{"modo": "renovar"}` → `{"codigo": "...", "caduca": 120}`. Abre el canal
  USB. La contraseña se convierte en hash al llegar y no se guarda.
- `GET /control/ventana?espera=<s>` → espera a que se cierre y dice cómo:
  `{"estado": "abierta"|"hecho"|"caducada"|"cancelada", "dispositivo": "..."}`.
- `DELETE /control/ventana` → cerrarla ya.
- `GET /control/estado` → `{"red": "100.x.y.z:47110", "sesiones": 1, "ventana": null|"emparejar"}`.
