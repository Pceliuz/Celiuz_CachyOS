# Celiuz Remoto — el diseño

Una app Android para manejar la PC y la laptop desde cualquier sitio: ver su
estado, apagarlas, ver y cerrar sus apps, sacar archivos y abrir una terminal.

**Cada punto de aquí salió de una conversación con el usuario (2026-10-20).**
Antes de cambiar una decisión, lee por qué se tomó. Las maquetas de las nueve
pantallas están en https://claude.ai/artifact/BGqHdnHe5W2Xu7LNuVwYUd (privadas).

---

## Las piezas

```
 Celular (app)  ── Tailscale (WireGuard) ──  PC / laptop
                                              ├─ servidor/   el servicio (Python, unidad de systemd --user)
                                              └─ escritorio/ la app de configuración (GTK, como CeliuzPaper)
      └────────────── cable USB (adb) ──────────────┘
                     emparejar y renovar el pase
```

| Carpeta | Qué es | Lenguaje |
|---|---|---|
| `servidor/` | el servicio que contesta a la app | Python 3, `aiohttp` |
| `escritorio/` | donde se empareja, se crea la contraseña y se dan permisos | Python + GTK 3 (`lib/panel_estilo.py` para el CSS) |
| `app/` | la app del celular | React Native con Expo, TypeScript |

El servidor **reutiliza lo que ya sabe el escritorio** y no lo duplica:
`lib/hardware.py` y `lib/sensores.py` para el estado (cada equipo enseña solo lo
que tiene), `lib/hypr.py` para las ventanas, `lib/juegos.py` si hace falta saber
si hay una partida, `lib/canales.py` para lo que sea de una sesión.

## Decisiones cerradas

### Solo Android, instalada por cable
- El APK se compila **en la PC** y se instala con `adb install`. Nada de Play
  Store ni de cuentas.
- **La clave con la que se firma el APK no se versiona**: vive en
  `~/.config/celiuz/remoto/firma.keystore`. Android solo deja actualizar una app
  con la misma firma; si esa clave se pierde, hay que desinstalar y volver a
  emparejar.

### La red: solo Tailscale, también en casa
- El servicio escucha **solo en la IP de Tailscale** (`100.x.y.z`), nunca en
  `0.0.0.0` ni en el wifi de casa. Sin Tailscale, no arranca.
- No se abre ningún puerto del router. Tailscale funciona detrás de CGNAT.
- Cada persona que use la config tiene su propia red de Tailscale: nadie ve los
  equipos de otro.

### Se activa desde la PC, y a mano
- No viene encendido al instalar el repo. Abrir un botón de «apagar» hacia fuera
  es una decisión de cada uno (igual que `instalar.sh --sddm`).
- Todo se configura desde `escritorio/`: detectar el celular por cable,
  instalarle la app, crear la contraseña, dar permisos, revocar.
- Un icono en la barra dice si el servicio está activo y si hay un celular
  conectado ahora mismo.

### Contraseña propia de la app
- **No es la de Linux.** Con la de Linux, el servicio tendría que recibir y
  comprobar la contraseña del sistema por la red, y quien la viera teclear en el
  celular tendría también la PC.
- **Se crea en la PC**, en el emparejamiento, y **la comprueba la PC** (nunca el
  celular), así que no se salta manipulando la app.
- Se guarda como hash `scrypt`, una por teléfono.
- La sesión caduca tras unos minutos sin usarla. Al **5.º fallo** ese teléfono
  queda bloqueado y la PC avisa con una notificación.
- Encima, opcional, la huella del celular.

### Cada teléfono tiene su clave, y se revoca
- Al emparejar, el celular genera un par de claves **Ed25519** y le pasa a la
  PC, por el cable, solo la **pública**. La privada no sale nunca del teléfono
  y en la PC no hay ningún secreto suyo que robar: con la pública se comprueba
  una firma, pero no se fabrica. (El primer borrador decía «clave aleatoria de
  la PC, guardando su hash» con un HMAC, y eso no se puede comprobar: para
  verificar un HMAC hace falta la clave entera.)
- Revocar: desde la app de la PC, o desde la consola web de Tailscale quitando el
  aparato (lo que se recomienda si te roban el celular: se corta al instante y
  sin venir a la PC).

### El pase de 24 h
- **24 horas exactas desde que se conecta**, ni más ni menos. El usuario lo
  conecta antes de dormir para que el tiempo empiece a correr cuando no lo usa.
- **Uno por equipo**: conectar a la PC no renueva el de la laptop.
- **Solo se renueva por cable Y con la contraseña** (sin contraseña, quien te
  quitara el celular podría enchufarlo un momento y llevarse 24 h).
- **Lo da y lo comprueba la PC, con su reloj**: cambiar la hora del celular no
  sirve de nada.
- La app avisa antes de que caduque.

### Qué pide cada cosa (opción B: el pase solo para lo peligroso)

| Función | Pide |
|---|---|
| Ver el estado en tiempo real | contraseña |
| Apagar, reiniciar, suspender | contraseña |
| Ver las apps abiertas | contraseña |
| Cerrar apps | contraseña + pase |
| Archivos: explorar, descargar, recientes, favoritos | contraseña + pase |
| Terminal (con sudo) | contraseña OTRA VEZ + pase + permiso de terminal para ese teléfono |

Apagar va sin pase a propósito: estando de viaje es justo cuando más falta hace,
y apagar no le hace daño a nadie.

Lo peligroso pide confirmación en la app. Al apagar, la PC enseña una
notificación con **cuenta atrás de 60 s** que se puede cancelar desde ella.

### La vigilancia (el interruptor por silencio del celular)
- El celular manda un **latido** cada pocos minutos. Cualquier latido, aunque
  llegue con internet bajo, **reinicia la cuenta atrás de 2 horas**.
- Si Android avisa de que lo están apagando (`ACTION_SHUTDOWN`), la app manda un
  último «me están apagando» y la cuenta pasa a **1 hora**. Es de mejor
  esfuerzo: si en ese momento no hay red, no llega, y vale la regla de 2 h. El
  modo avión no avisa.
- Al llegar a cero:
  - **si hay una persona delante** (teclado o ratón recientes, **o un vídeo
    reproduciéndose**: viendo anime no se toca el ratón en 20 minutos), **no se
    apaga**: notifica «tu celular lleva 2 h sin dar señales, revísalo» y vuelve
    a contar;
  - si no hay nadie, **se apaga**. Una descarga o un render en marcha NO cuentan
    como persona: si te roban el celular, la PC no debe quedarse encendida
    porque estaba bajando algo.
- Con varios teléfonos: al que pasa 2 h callado **se le quita el pase** (no se
  desempareja: se recupera por cable); si callan todos, se apaga la PC.
- Si se va el internet de casa más de 2 h, la PC tampoco oye a nadie y se
  apaga. Es lo correcto para lo que se quiere.
- Para que Android no mate la app, mientras la vigilancia está armada la app
  lleva una **notificación fija** y hay que quitarle la optimización de batería.
  La app de la PC guía ese paso al instalar.

### Tras reiniciar: la PC en la pantalla de SDDM (decidido 2026-10-20)
- El usuario quiere que el servicio **arranque solo tras un reinicio** y poder
  «entrar» a la PC desde la app aunque esté en la pantalla de inicio de sesión.
- Por eso el servicio acaba siendo **de sistema** (siempre activo, corre como
  el usuario), no de la sesión gráfica.
- Con la PC en SDDM, la app ofrece «Entrar»: contraseña **de la app** + pase →
  la PC escribe un **autologin de un solo uso** (un drop-in que se borra al
  entrar) y la sesión arranca **ya bloqueada**. La contraseña de Linux nunca
  viaja.
- Lo que se pierde: gnome-keyring / kwallet quedan cerrados hasta que alguien
  escriba la contraseña de Linux delante de la PC.
- Hasta la fase 5 el servicio es de la sesión (`systemd --user`).

### La vigilancia escucha a Tailscale, no a la app
- Para saber si el celular sigue vivo se mira `Online` de ese aparato en
  `tailscale status --json`: no gasta batería y no depende de que Android deje
  viva la app. Hay que quitarle a **Tailscale** la optimización de batería.
- El latido de la app queda solo para el «me están apagando».
- La GPU se lee por NVML (la librería del driver), no lanzando `nvidia-smi`.

### Archivos: un explorador propio, no Dolphin
- Ver Dolphin de verdad sería escritorio remoto, incómodo en un celular. La app
  lleva su explorador, que lee las carpetas de la PC a través del servicio.
- Acotado a la carpeta personal, y **solo lectura** al principio.
- **Recientes**: lo que ya se bajó, con su estado contra la PC («igual», «hay
  versión nueva», «ya no está»). **Favoritos**: archivos y carpetas fijados.
- El historial vive **en la PC**: si cambias de celular lo conservas, y si te lo
  roban no se llevan la lista.

### Terminal con sudo
- Una terminal de verdad (un PTY), con la shell del usuario.
- La contraseña de `sudo` se escribe en la terminal, viaja cifrada por Tailscale
  y va directa a `sudo`. **No se guarda en ningún sitio.**
- Apagada por defecto; se activa por teléfono desde la app de la PC.
- Queda registrado que se abrió, cuándo y desde qué teléfono.

## Fases

Cada fase se cierra con sus pruebas en verde y probada de verdad antes de
empezar la siguiente (acordado con el usuario el 2026-10-20).

1. **El corazón del servidor** ✅ (no se ve nada todavía): los teléfonos, la
   contraseña, el pase, el registro, el estado del equipo y el servidor HTTP
   con `/v0/reto`, `/v0/sesion`, `/v0/equipo`, `/v0/vivo` y el canal USB. Se
   prueba con un «teléfono de mentira» en Python contra un servidor de verdad.
   La paleta de la app pasa a generarla `gen-colores.py`.
2. **La app de la PC y encenderlo** ✅: la ventana GTK (detectar el celular,
   emparejar, contraseña, permisos, renovar, revocar), `adb.py`, la unidad de
   systemd y lo que diga `instalar.sh --revisar`.
3. **La app del celular, primera versión** ✅: emparejar por cable, entrar,
   inicio con el estado en tiempo real. APK compilado en la PC.
4. **Control**: apagar / reiniciar / suspender con cuenta atrás, ver y cerrar
   apps, y la vigilancia (con el icono de la barra: ¿activo?, ¿hay un celular?).
5. **Tras un reinicio (SDDM)**: servicio de sistema y entrada de un solo uso
   (ver «Tras reiniciar» arriba).
6. **Archivos**: explorador, descargas, recientes, favoritos.
7. **Terminal**.
8. **Extras**: subir archivos a la PC, escritorio remoto (`wayvnc`), encender a
   distancia (Wake-on-LAN, necesita otro aparato despierto en casa), modo
   «ayudar a un amigo» (compartir un equipo por Tailscale).

## Lo que NO entra en git (la regla de oro)

| Fuera del repo | Qué es |
|---|---|
| `~/.config/celiuz/remoto.conf` | ajustes: puerto, carpetas permitidas, márgenes |
| `~/.config/celiuz/remoto/firma.keystore` | la clave de firma del APK |
| `~/.local/share/celiuz/remoto/celiuz-remoto.apk` | el APK ya compilado, el que instala la ventana de la PC |
| `~/.config/systemd/user/celiuz-remoto.service` | COPIA de `servidor/celiuz-remoto.service` (la pone `instalar.sh`; enlazada, `disable` la borraba) |
| `~/.local/state/celiuz/remoto/dispositivos.json` (0600) | teléfonos: hash de su clave, hash de su contraseña, permisos, pase, último latido |
| `~/.local/state/celiuz/remoto/historial.json` | recientes y favoritos |
| `~/.local/state/celiuz/remoto/registro.jsonl` | qué hizo cada teléfono y cuándo |
| `remoto/app/node_modules`, `android/`, `.expo/`, los `.apk` | lo que genera la compilación |

## Lo que necesita cada equipo

| Paquete | Para qué | Quién |
|---|---|---|
| `tailscale` | la red | todos |
| `python-aiohttp` | el servidor (HTTP + WebSocket) | todos |
| `python-psutil` | CPU, RAM, red, disco | todos (ya está) |
| `android-tools` | `adb`: instalar y emparejar | todos |
| `nodejs`, `npm`, `jdk17-openjdk`, SDK de Android | compilar el APK | solo quien compila |

`instalar.sh --revisar` debería decir lo que falte, como ya hace con MangoHud.

## Preguntas abiertas

- Cómo escribe el servicio de sistema el autologin de un solo uso en
  `/etc/sddm.conf.d/` sin darle root al servicio entero (fase 5).
