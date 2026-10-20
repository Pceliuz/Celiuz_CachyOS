# Celiuz Remoto — el protocolo (versión 0, borrador)

Lo que se dicen la app y el servidor. Es el contrato entre `app/` y
`servidor/`: si cambia aquí, cambia en los dos. El porqué de cada regla está en
`DISEÑO.md`.

Todo va bajo `/v0/`. Si un día cambia de forma incompatible, se abre `/v1/` y el
servidor sigue sirviendo `/v0/` hasta que no quede ninguna app vieja.

## Dónde escucha

| Canal | Dirección | Para qué |
|---|---|---|
| **Red** | `http://<IP de Tailscale>:47110` | todo el uso normal |
| **USB** | `http://127.0.0.1:47111`, llevado al celular con `adb reverse` | emparejar y renovar el pase, y nada más |

- Por la red **no hace falta TLS**: Tailscale ya cifra y autentica cada paquete
  (WireGuard). Escuchar solo en esa IP es lo que garantiza que no hay otro
  camino.
- El canal USB **solo está abierto mientras la app de la PC lo pide** (unos
  2 minutos), no siempre. Que la petición llegue por `adb reverse` es la prueba
  de que hay un cable entre los dos.

## Las tres llaves

1. **Clave del teléfono** (`clave`): 32 bytes aleatorios que la PC genera al
   emparejar y entrega por el canal USB. El celular la guarda en el almacén
   seguro de Android; la PC guarda solo `sha256(clave)`. **Nunca viaja por la
   red**: el teléfono demuestra que la tiene firmando un reto (HMAC-SHA256).
2. **Contraseña de la app**: la escribe el usuario; la PC la comprueba contra su
   hash `scrypt`.
3. **Sesión** (`token`): la da la PC al entrar bien. Caduca tras 5 minutos sin
   uso (ajustable). Va en la cabecera `Authorization: Bearer <token>`.

Y encima, el **pase**: no es una llave que lleve el teléfono, es una fecha que
guarda la PC (`pase_hasta`). Las rutas marcadas «pase» contestan `423` si ya
pasó.

## Respuestas de error (todas iguales)

```json
{"error": "pase_vencido", "mensaje": "El pase de 24 h venció a las 23:40."}
```

| HTTP | `error` | Cuándo |
|---|---|---|
| 401 | `sin_sesion` | falta el token o caducó → volver a entrar |
| 401 | `contrasena` | contraseña mal; trae `intentos_restantes` |
| 403 | `bloqueado` | 5 fallos, o teléfono revocado |
| 403 | `sin_permiso` | ese teléfono no tiene activado ese módulo |
| 423 | `pase_vencido` | lo pedido necesita el pase |
| 409 | `confirmar` | acción peligrosa sin `"confirmado": true` |

## Red: `/v0/...`

### Entrar
- `GET /v0/reto?dispositivo=<id>` → `{"reto": "<32 bytes en base64>", "caduca": 30}`
- `POST /v0/sesion`
  `{"dispositivo": "<id>", "firma": "<HMAC(clave, reto)>", "contrasena": "..."}`
  → `{"token": "...", "caduca_en": 300, "pase_hasta": "2026-10-21T23:40:00-05:00", "permisos": ["estado","energia","ventanas","archivos"]}`
- `DELETE /v0/sesion` → salir.

### Latido (vigilancia)
- `POST /v0/latido`
  `{"dispositivo": "<id>", "reto": "...", "firma": "...", "apagando": false}`
  No pide contraseña ni sesión: lo manda un servicio de fondo de la app, sin
  nadie delante. Solo prueba que el teléfono sigue vivo. Para firmarlo sin
  pedir antes un reto, el reto es la hora (minuto UTC) y el servidor acepta el
  minuto actual y el anterior.
  → `{"siguiente_en": 300}`

### Estado en tiempo real
- `GET /v0/equipo` → nombre, modelo de CPU y GPU, RAM total, si es portátil
  (de `lib/hardware.py` y `lib/maquina.py`).
- `WS /v0/vivo` → cada segundo:
  ```json
  {"cpu": {"uso": 23, "temp": 52}, "gpu": [{"nombre": "RTX 3050", "uso": 31, "temp": 48, "vram": [1.2, 6]}],
   "ram": [7.1, 16], "disco": [588, 1000], "red": {"bajada": 2400000, "subida": 140000},
   "bateria": null, "encendida_desde": "...", "pase_hasta": "...", "vigilancia": "armada"}
  ```
  Solo van los campos que el equipo tiene: sin GPU dedicada no hay `vram`, sin
  batería `bateria` es `null`.

### Energía
- `POST /v0/energia` `{"accion": "apagar"|"reiniciar"|"suspender", "confirmado": true}`
  → `{"cuenta_atras": 60}`. La PC enseña la notificación cancelable.
- `DELETE /v0/energia` → cancelar desde el celular.

### Ventanas
- `GET /v0/ventanas` → `[{"id": "0x55d...", "app": "Brave", "titulo": "...", "escritorio": 2}]`
- `POST /v0/ventanas/<id>/cerrar` `{"confirmado": true}` — **pase**. Cierra
  pidiéndolo (como `SUPER+Q`), no matando.

### Archivos — todo **pase**
- `GET /v0/archivos?ruta=Documentos` → `{"ruta": "...", "entradas": [{"nombre", "tipo": "carpeta"|"archivo", "tamano", "modificado"}]}`
  Las rutas son relativas a la carpeta personal; una que salga de ella (`..`,
  enlaces que apunten fuera) da `403`.
- `GET /v0/archivos/descargar?ruta=...` → el archivo (admite `Range`, para
  reanudar). Se apunta en Recientes.
- `GET /v0/archivos/miniatura?ruta=...&lado=256` → JPEG.
- `GET /v0/recientes` → `[{"ruta", "bajado", "tamano", "estado": "igual"|"nueva_version"|"no_esta"}]`
- `GET /v0/favoritos`, `PUT /v0/favoritos` `{"ruta"}`, `DELETE /v0/favoritos?ruta=...`

### Terminal — **pase** + permiso `terminal` + contraseña otra vez
- `POST /v0/terminal` `{"contrasena": "..."}` → `{"terminal": "<id>"}`
- `WS /v0/terminal/<id>` → bytes en los dos sentidos; mensajes de control
  `{"tamano": [filas, columnas]}`.

## USB: `/usb/...` (solo por `adb reverse`, solo con la app de la PC esperando)

- `POST /usb/emparejar` `{"codigo": "...", "nombre": "Redmi Note 13"}`
  → `{"dispositivo": "<id>", "clave": "<base64>", "equipo": "Celiuz-CachyOS", "direccion": "100.x.y.z:47110"}`.
  El `codigo` es de un solo uso: la app de la PC se lo pasa a la app del
  celular al abrirla por adb, para que ningún otro proceso de la PC pueda
  emparejarse aprovechando la ventana abierta. La contraseña NO se escribe en
  el celular: se crea en la PC en ese mismo paso.
- `POST /usb/renovar` `{"dispositivo", "firma", "contrasena"}`
  → `{"pase_hasta": "..."}` (24 h exactas desde ahora, con el reloj de la PC).

## Por decidir al codificar

- Cómo le pasa la app de la PC el `codigo` al celular (un `intent` con
  `adb shell am start`) sin que quede a la vista de otras apps del teléfono.
- Cada cuánto el latido: más a menudo gasta batería; menos, tarda más en
  enterarse. Propuesta: 5 minutos.
