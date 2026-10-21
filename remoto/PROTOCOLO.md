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
| latido | `celiuz-remoto/v0/latido:<dispositivo>:<minuto>:<0\|1>` |

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
| 409 | `estado` | no toca ahora (entrar con la sesión ya abierta, o sin lo de root instalado); el `mensaje` dice por qué |
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
   "bateria": null, "encendida_desde": "...", "pase_hasta": "..." | null,
   "vigilancia": "desarmada"|"sin_telefonos"|"armada"|"avisando"|"apagando", "energia": null | {...},
   "escritorio": {"sesion": "abierta"|"pantalla_inicio"|"no_lo_se", "puede_entrar": false, "motivo": "..."}}
  ```
  Solo van los campos que el equipo tiene: sin sensor no hay `temp`, sin GPU
  dedicada no hay `vram`, sin batería `bateria` es `null`. Una GPU dormida (la
  NVIDIA de un portátil híbrido) sale `{"nombre": ..., "dormida": true}` y **no
  se despierta** para medirla. RAM, VRAM y disco en GiB; red en bytes por segundo. `tipo` es el de
  `lib/maquina.py` (`portatil` / `escritorio`).
  Al caducar la sesión, el servidor cierra con el código 4401.

### Latido — «me están apagando»
- `POST /v0/latido` `{"dispositivo", "minuto": "<minutos UTC desde 1970>", "apagando": true, "firma"}`
  Sin sesión: lo manda un servicio de fondo. La firma es sobre
  `<dispositivo>:<minuto>:<1|0>`, y la PC acepta su minuto y el anterior. Cuenta
  como señal y, con `apagando`, la vigilancia le da a ese teléfono 1 h en vez de
  2. Que el celular vive se mira en Tailscale (ver `DISEÑO.md`).
  → `{"siguiente_en": 300}`. Un minuto viejo o una firma de otro: `401 firma`.

### Energía — permiso `energia` (SIN pase, a propósito)
- `POST /v0/energia` `{"accion": "apagar"|"reiniciar"|"suspender", "confirmado": true}`
  → `{"cuenta_atras": 60, "energia": {...}}`. En la PC sale un aviso con botón
  «Cancelar». Al acabar, se piden cerrar las ventanas (como `SUPER+Q`), 5 s, y
  `systemctl`. Una orden nueva sustituye a la que hubiera.
- `GET /v0/energia` → `{"energia": {"accion", "quedan", "hasta", "origen"} | null}`.
- `DELETE /v0/energia` → `{"cancelada": true|false}`.
- La cuenta atrás va también en cada mensaje de `/v0/vivo` (`energia`), y la
  duración se cambia en `remoto.conf` (`cuenta_atras`).

### Tras reiniciar: la pantalla de inicio — permiso `energia` + **pase**
- `GET /v0/escritorio` (permiso `estado`) → `{"sesion", "puede_entrar", "motivo"}`, lo mismo
  que va en cada `/v0/vivo`. `abierta`: hay un Hyprland vivo. `pantalla_inicio`:
  SDDM esperando y nadie dentro. `no_lo_se`: cualquier otra cosa (una consola,
  una sesión que no es Hyprland, logind sin contestar), y con eso **no** se
  ofrece entrar. `puede_entrar` es `pantalla_inicio` y con la parte de root
  instalada en la PC (`./instalar.sh --remoto-sistema`).
- `POST /v0/escritorio/entrar` `{"confirmado": true}` → `{"pedido": true, "mensaje"}`.
  La PC escribe un autologin de un solo uso, reinicia SDDM, y la sesión
  **arranca bloqueada**: delante de la PC hace falta la contraseña de Linux
  igual. No espera a que entre (tarda lo que tarde SDDM): el celular ve el
  cambio en `escritorio` por `/v0/vivo`. Sin pase `423`, sin confirmar `409
  confirmar`, si no toca `409 estado`.

### Ventanas — permiso `ventanas`
- `GET /v0/ventanas` → `{"ventanas": [{"id": "0x55d...", "app": "Brave", "titulo": "...", "escritorio": "2"}], "sesion": true}`
  De la sesión de Hyprland viva (la busca el servidor en caliente).
- `POST /v0/ventanas/<id>/cerrar` `{"confirmado": true}` — **pase**. Cierra
  pidiéndolo (como `SUPER+Q`), no matando. `404` si ya no está.

### Archivos — permiso `archivos`, todo **pase**
Solo lectura. Las rutas son relativas a la carpeta personal (`""` es ella
misma) y se resuelven con `realpath` ANTES de mirar la frontera: una que salga
(`..`, una absoluta, un enlace que apunte fuera) da `403 fuera`. Y dentro de
casa hay sitios que no se enseñan nunca, ni pidiendo los ocultos, ni buscando,
ni por un enlace: `.ssh`, `.gnupg`, los llaveros, los perfiles de los
navegadores y lo propio de Celiuz Remoto (la lista, `NUNCA` en
`servidor/celiuz_remoto/archivos.py`).

- `GET /v0/archivos?ruta=Documentos[&ocultos=1]` →
  `{"ruta": "Documentos", "entradas": [{"nombre", "tipo": "carpeta"|"archivo", "tamano"?, "elementos"?, "modificado", "favorito"}], "truncado": false}`.
  Carpetas primero. Sin `ocultos=1` no salen los que empiezan por punto. Los
  enlaces rotos o que salen de casa no salen. Más de 2000: `truncado`.
- `GET /v0/archivos/buscar?ruta=&q=informe` → `{"ruta", "q", "resultados": [... con "ruta"], "truncado"}`.
  Por nombre, sin distinguir mayúsculas, en esa carpeta y las de dentro. Al
  menos dos letras (`400`). Como mucho 200 resultados y 3 s.
- `GET /v0/archivos/descargar?ruta=...` → el archivo, con `Range` (`206`) para
  reanudar. La que empieza por el principio se apunta en Recientes y en el
  registro; un `Range` que sigue a medias no cuenta como otra.
- `GET /v0/archivos/miniatura?ruta=...&lado=256` → JPEG (lado entre 64 y 1024)
  de una imagen o un vídeo, hecho con ffmpeg y guardado en
  `~/.cache/celiuz/remoto/miniaturas`. De lo demás, `404`.
- `GET /v0/recientes` → `{"recientes": [{"ruta", "nombre", "carpeta", "bajado", "tamano", "dispositivo", "estado": "igual"|"nueva_version"|"no_esta"}]}`.
  El estado compara el tamaño y la fecha que tenía al bajarlo con lo que hay
  ahora. `DELETE /v0/recientes?ruta=...` lo quita de la lista (sin `ruta`, todos).
- `GET /v0/favoritos`, `PUT /v0/favoritos` `{"ruta"}`, `DELETE /v0/favoritos?ruta=...`
  → `{"favoritos": [{"ruta", "nombre", "tipo", "existe", "desde"}]}`. Fijar
  algo que no hay, `404`; uno fijado que se borró sigue con `existe: false` y se
  puede quitar.

| HTTP | `error` | Cuándo |
|---|---|---|
| 403 | `fuera` | la ruta sale de la carpeta personal o es de lo que nunca se enseña |

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
- `GET /control/estado` → `{"red": "100.x.y.z:47110", "sesiones": 1, "ventana": null|"emparejar", "energia", "vigilancia", "escritorio", "linger": bool, "sistema": bool}`.
- `DELETE /control/energia` → cancelar un apagado desde la PC.
- `GET /control/vigilancia`, `POST /control/vigilancia` `{"armada": true}` →
  `{"armada", "estado", "presencia", "presencia_motivo", "telefonos": [...]}`.
