# Por dónde seguir

Notas para retomar el trabajo sin reconstruir el contexto. Si esto se queda
viejo, mandan el `README.md` y el `CLAUDE.md`. Las crónicas de sesiones
anteriores, con todo lo medido, están en **`HISTORIAL.md`** (antes vivían aquí y
el fichero llegó a 1238 líneas).

Última sesión: **2026-10-21** (mañana), en la **PC**, manejada desde la
terminal de Celiuz Remoto (la PC en SDDM, el usuario en el trabajo).

---

## 2026-10-21 (noche, PC): el «modo mando» de la pantalla remota

Apuntar con el dedo en la pantalla encogida era «realmente horrible» (el
usuario). `remoto/app/scripts/mando.js`, pintado DENTRO de la página de noVNC
(sin pasar por el puente de React Native en cada movimiento): joystick (zona
muerta, velocidad cuadrática), la imagen como touchpad (arrastrar mueve, tocar
clica donde está el cursor), Clic / Derecho / Mantener / Rueda, y escritorios
1-9 (Super+número). Cursor propio, porque el de noVNC en un celular solo sigue
al dedo. De fábrica «mando»; «Modo táctil» en la cabecera vuelve a lo de antes.
Usa internos de noVNC 1.7 (`_sock`, `_display`, `_fbWidth`): si cambian, el
mando no hace nada y el táctil sigue. Prueba: `unidad/remoto-mando` (las
cuentas, con Node). Visto en un Chromium sin ventana (vertical y horizontal),
**sin probar en el celular**: APK en `~/Descargas/celiuz-remoto-mando.apk` de
la PC (firmado con la clave de la PC).

Después (el usuario, viéndolo en el HONOR: «en horizontal estaría mejor, la
ventana más grandecita»): **el mando gira el celular a horizontal solo**
(`lockAsync(LANDSCAPE)`; táctil deja girar libre; la contraseña, en vertical).
En horizontal la imagen ocupa todo el alto: sin barra de estado y sin las filas
de arriba y de abajo, que salen con «Menú» (arriba a la derecha) o al abrir el
teclado; los controles, medio transparentes. Instalado en el HONOR por adb,
**sin mirar aún con la pantalla conectada** (pide la contraseña de la app).

Y luego: «en la PC va normal, en el celular cortado y retrasado». La PC no
era (wayvnc tarda <10 ms por imagen entera; ~540 KB con la calidad 6 de
noVNC, ~440 con la 2). Era el wifi del HONOR (-76 dBm, **6 Mbps de bajada**,
ping por Tailscale 557 ms, aunque directo) **y la cola**: noVNC pide
«actualizaciones continuas», wayvnc las da (contesta el 150), la PC empuja
sin esperar y noVNC no tiene control de flujo, así que en un enlace lento lo
que se ve es de hace segundos. `pantalla-entrada.js` quita esa codificación
de la lista: una imagen en camino como mucho. Medido con la página generada
en un Brave sin ventana contra un wayvnc real (puente que espía SetEncodings):
«SIN continuas» y ~19 peticiones/s en local. Sin H.264: NVENC no sirve a
neatvnc (va por VAAPI y el driver de NVIDIA solo decodifica).

## 2026-10-21 (tarde-noche, PC): la guía de instalación del remoto, y SDDM sin uwsm

El usuario estaba instalando Celiuz Remoto con un amigo, en su laptop y la del
amigo, sin instrucciones. Hecho (sin commitear al escribir esto):
- **`remoto/INSTALAR.md`**: la guía entera, 11 pasos con cómo comprobar cada
  uno, las tres decisiones de antes (cuenta de Tailscale por persona, si el
  celular ya tiene la app, la misma clave de firma en varios equipos) y una
  tabla de problemas. CLAUDE.md y los README apuntan ahí.
- **SDDM entraba SIN uwsm al «Entrar» desde el celular** (lo encontró el Claude
  de la laptop; la PC tenía lo mismo): `/etc/sddm.conf` trae `[Autologin]
  Session=hyprland` del instalador de CachyOS y SDDM lo lee el último. Ahora
  `entrar.py` escribe `Session=` con la de la última vez (state.conf de SDDM;
  si no, `hyprland-uwsm.desktop`), y `--remoto-sistema` comenta esa línea
  (`remoto/sistema/sddm_conf.py`, con copia; no toca un autologin con
  `User=`). `celiuz-remoto revisar` dice si lo de root está «falta», «vieja»
  (un pull con arreglo) o si sddm.conf aún estorba.
- **El tema de SDDM viejo** ya lo avisa `./instalar.sh --revisar` (comparando
  la copia con el repo). La PC también lo tenía viejo (Colores.qml).
- **Firma del APK**: «Actualizar» desde un equipo con otra clave ya dice qué
  pasa (`adb.OTRA_FIRMA`) en vez de la línea de adb.
- **En cada equipo, tras traer esto**: `git pull && ./instalar.sh`, luego
  `./instalar.sh --remoto-sistema` (o `--remoto-todo`) y `./instalar.sh
  --sddm`; y seguir `remoto/INSTALAR.md` desde lo que diga `celiuz-remoto
  revisar`. En la laptop del usuario, su Claude ya había puesto
  `Session=hyprland-uwsm` a mano en /etc/sddm.conf: `--remoto-sistema` lo
  comenta igual (entrar.py ya escribe la buena).

## 2026-10-21 (tarde, desde la laptop): el saludo de la terminal

Lo pidió el usuario con capturas de la laptop. Hecho y con pruebas, **sin
verlo en pantalla** (la sesión corría en la PC, que estaba en SDDM):
- **Colores**: neones nuevos en la paleta (`$rojo_neon`, `$azul_electrico`,
  `$azul_neon`, `$verde_neon`, en su sección «solo para el saludo»). El cuadro
  se edita en `fastfetch/plantilla.jsonc` y `gen-colores.py` hace
  `fastfetch/config.jsonc` (GENERADO). Iconos en rueda de 6 colores, texto en
  `$luz`, porcentajes y puntos de la paleta (antes, ANSI del tema de kitty).
- **Imagen**: `saludo.sh medidas` según la terminal al abrirse: crece hasta el
  alto del cuadro (16 filas), centrada; si no cabe al lado, encima; si no
  cabe ni encima, sin imagen y sin el logo de la distro.
- **Pendiente, en la laptop**: (1) las terminales nuevas salen ENCIMA de la
  otra en vez de partir la pantalla; no se ve la causa en el repo, se le
  pidieron datos (`hyprctl clients`, `getoption misc:on_focus_under_fullscreen`,
  ¿modo gaming a medias?). (2) Los iconos chicos: kitty los pinta con su
  «Symbols Nerd Font Mono» de serie, de una celda; para que ocupen dos hace
  falta una fuente de símbolos ancha (`symbol_map` en kitty.conf, que no es del
  repo). (3) Las imágenes «se bugean» al redimensionar: las de kitty no se
  recolocan con el texto; mirar los marcadores Unicode de `kitten icat`.

## 2026-10-21 (PC, desde el celular): GPU «—», vigilancia a 1 h y modo gaming

**SIN COMMITEAR** y **sin reiniciar el servicio**: la sesión de Claude corría
DENTRO de `celiuz-remoto.service` (la terminal de la app), y reiniciarlo la
mataba. Hace falta `systemctl --user restart celiuz-remoto` (o reiniciar la PC)
para que valga lo de abajo.

- **La GPU salía «—» tras reiniciar**: con linger el servicio nace a las
  07:02:31 y `/dev/nvidiactl` a las 07:02:34; `nvmlInit` fallaba y no se
  reintentaba nunca. Ahora `Nvml` reintenta cada 30 s (`estado.py`, prueba en
  `unidad/remoto`).
- **Vigilancia: 1 h siempre** (antes 2 h, o 1 h con el «me están apagando»,
  que Android nunca llegó a mandar). Lo pidió el usuario: una mala conexión
  que apaga el celular es el mismo caso.
- **Vigilancia en el modo gaming: avisa y NO apaga** (estado `jugando`), le
  quita el pase igual. `escritorio.modo_gaming()` pregunta a
  `modo-gaming.py estado` (no copia la ruta; la prueba usa el script de
  verdad). El aviso va con la categoría `de-paso` de mako: se ve aunque el
  modo gaming tenga «no molestar», sin sonido, y se va a los 8 s (lo eligió
  el usuario). Hace falta recargar mako (`makoctl reload`) para verlo.
- **RAM, medido**: el servidor son ~80 MB; el 1,5 GB que da systemd es caché
  de disco (~1 GB, se reclama) más la propia sesión de Claude y sus MCP. En el
  arranque anterior los picos fueron: kitty-2776 9,8 GB (compilar el APK /
  gradle), el asistente 3,1 GB, Brave 3 GB, celiuz-remoto 412 MB. Convertir un
  4K con ffmpeg: 1,4 GB con 12 hilos; `-threads 6` en los dos lados 750 MB
  (9 s contra 8), 4+4 hilos 640 MB (12 s). **Hecho** (el usuario dijo que
  sí): `conversion.hilos()` según la RAM disponible en ese momento (6/4/2), en
  los dos lados, y al acabar se suelta la caché de disco del vídeo
  (`posix_fadvise DONTNEED`).
- **compilar.sh dejaba 4,7 GB ocupados** al terminar: el demonio de Gradle
  (3,3 GB) y el de Kotlin (1,5 GB) se quedan horas esperando. Ahora Kotlin
  compila dentro de Gradle y `gradlew --stop` al final, aunque falle. Medido:
  0 procesos Java tras compilar, la RAM igual que antes (144 s).
- **Terminales que se minimizan** (lo pidió el usuario: dejar algo corriendo,
  abrir otra para los commits, mirar el estado o bajar un .docx sin perder la
  sesión). La terminal es una `Sesion` de la PC (`terminal.py`): cerrar el
  WebSocket la SUELTA, no la mata; se retoma sin contraseña
  (`WS /v0/terminales/<id>`) con lo último que salió (512 KB) repintado;
  `GET/DELETE /v0/terminales`; hasta 5; suelta más de 1 h se cierra; el vigía
  de la PC la cierra también suelta si se pierde pase o permiso. App: la
  pestaña Terminal es una lista (Entrar / Cerrar / Abrir otra); dentro,
  «Minimizar» (y Atrás) la suelta; si se corta la red, reintenta 3 veces.
  Pruebas: secciones 6-8 de `e2e/remoto-terminal` (47) y la 6 de
  `e2e/remoto-app` (el cliente real con Node). **Sin probar en el HONOR**: el
  APK está en `~/Descargas/celiuz-remoto-2026-10-21.apk`, para bajarlo con la
  pestaña Archivos e instalarlo desde el gestor de archivos del celular,
  DESPUÉS de reiniciar el servicio (la app nueva contra el servidor viejo no
  ve la lista).

## 2026-10-21 (PC, mañana): Celiuz Remoto — vídeos que el celular no reproduce

Lo encontró el usuario en el HONOR: los vídeos se bajaban, salían en la
galería y no se reproducían. Medido: es el **decodificador**, no la descarga
(md5 igual). 1080p 30 bien; 1440p 24 a 12 Mb/s a medias (el reproductor que
abrió la app dijo que no, la galería sí); 4K 60 H.264 y 4K 30 HEVC en negro.

- **PC** (`conversion.py`): `GET /v0/archivos/video` (ficha de ffprobe),
  `POST/GET/DELETE /v0/archivos/convertir` (H.264 + AAC con libx264 CRF 20,
  de una en una, con progreso, se para sola si el celular deja de preguntar,
  caché de dos días) y `descargar?conversion=<id>`.
- **Celular**: `puedeVideo`/`puedeAudio` en el módulo nativo (decodificador
  por HARDWARE, con los performance points del fabricante), y
  `decidirVideo()` en `archivos.ts`: hasta 1440p, conservando los fps antes
  que la resolución mientras no baje de 1080p. Antes de bajar un vídeo que no
  va, pregunta: «Convertir a 1440p 60» / «Bajar el original» / «Cancelar».
- Pruebas: sección 8b de `e2e/remoto-archivos` y `decidirVideo` + la
  conversión de verdad en `e2e/remoto-app`. APK recompilado, servicio
  reiniciado.
- **Probado por el usuario en el HONOR** con el APK nuevo (2026-10-21): bien.

## 2026-10-20/21 (PC, de noche): arreglo de la fase 6, y fases 7 y 8 — Celiuz Remoto TERMINADO

**Sin commitear**: el usuario pidió hacer todo sin parar y subirlo él al final.
Él durmió; todo se probó en su HONOR manejándolo por adb.

**2026-10-21, al despertar**: el usuario volvió a emparejar el HONOR (ya no
lleva la contraseña temporal), hizo el commit, instaló wayvnc y probó APAGAR
desde el celular: funcionó. Reiniciar y suspender por botón, sin probar.

**El internet de la PC llega por USB desde un Redmi Note 10S** (anclaje,
`enp48s0f3u2`; el Redmi es otro celular, no el HONOR de la app). Al reiniciar,
el celular apaga el anclaje y la pantalla de inicio se queda sin internet ni
Tailscale. Arreglo, hecho y medido en vivo: `celiuz_remoto/anclaje.py` +
`celiuz-remoto-anclaje.service` (lo enciende instalar.sh), que le vuelve a
pedir el anclaje por adb (`svc usb setFunctions rndis`: la ruta volvió en 3 s).
Linger ya está puesto (`loginctl enable-linger`, 2026-10-21) y android-udev
también (el usuario, en `adbusers`) — sin este último, en SDDM el USB es del usuario `sddm` y adb no puede. Luego
reiniciar por el botón de la app y mirar `journalctl --user -u
celiuz-remoto-anclaje` («pedido»).

**HECHO (2026-10-21 ~05:45): el usuario reinició la PC con el BOTÓN de la
app y siguió usándola desde el celular: a prueba de reinicios.** Antes de reiniciar ya estaba todo: android-udev instalado y él en
`adbusers`, linger puesto, el servicio del anclaje corriendo y la wifi
conectada («REPETIDOR FAMILIA RAMOS2-5G», perfil de sistema: sin permissions,
autoconnect, psk-flags 0). Al retomar, preguntarle cómo fue y mirar:
`journalctl --user -b -u celiuz-remoto-anclaje` (con la wifi arriba lo normal
es que NO pida nada: hay ruta por defecto), `nmcli -t -f NAME,DEVICE
connection show --active` (¿entró la wifi en SDDM?), y el registro de
Celiuz Remoto (`celiuz-remoto registro`). Cambios SIN COMMITEAR: anclaje.py,
su unidad, su prueba, instalar.sh, remoto-escritorio.sh, CLAUDE.md y esto.
Pendientes de esta tanda: probar suspender por botón, `./instalar.sh
--remoto-sistema` y «Entrar» desde SDDM, revisar «Invitar a alguien».

**La wifi de la PC** (RTL8192EE, driver `rtl8192ee` del kernel) solo estaba
apagada en NetworkManager: `nmcli radio wifi on`. Las redes que se guardan
desde el panel de wifi son de sistema, así que conectan en la pantalla de
inicio sin entrar; con la wifi de la casa el anclaje deja de hacer falta y el
demonio no toca al celular (solo actúa sin ruta por defecto).

**Wake-on-LAN** está en la BIOS, pero `enp34s0` sigue SIN cable: por el
anclaje USB ni por wifi se puede despertar a la PC. Hace falta cable de red al
router en `enp34s0` y `sudo nmcli connection modify "Conexión cableada 1"
802-3-ethernet.wake-on-lan magic` (persistente; `ethtool -s` se pierde al
reiniciar).

**LO QUE TIENE QUE HACER EL USUARIO** (no se podía sin él):
1. ~~**El HONOR está emparejado con una contraseña TEMPORAL**~~ (hecho): `prueba-noche-2026`
   (registro `316a993b…`, con todos los permisos, para poder probar). Su
   emparejamiento de antes (`c0615dcf`) estaba roto desde la fase 4. Lo suyo:
   emparejar otra vez desde la ventana con SU contraseña y los permisos que
   quiera (se sustituye solo, por la serie USB).
2. ~~**Commit** de todo~~ (hecho) (la lista de ficheros nuevos, abajo).
3. **Fase 5 sin probar todavía**: `./instalar.sh --remoto-sistema`, apagar y
   encender el servicio en la ventana (linger), reiniciar y «Entrar» desde el
   celular. Receta en la entrada de la fase 5, más abajo.
4. ~~**Para ver la pantalla**: `sudo pacman -S wayvnc`~~ (hecho) (se probó con uno bajado
   a una carpeta temporal, sin instalar, y ya se quitó del servicio).
5. **Para despertar a la PC desde la laptop**: activar Wake-on-LAN en la BIOS
   y en `enp34s0` (`celiuz-remoto despertar` dice cómo), con la PC por cable.
   Ahora mismo la PC sale a internet por un adaptador USB (`enp22s0f0u1`) y
   `enp34s0` no tiene cable: así no se puede despertar.
6. **Mirar la ventana de la PC** (el botón «Invitar a alguien» y «Permisos» en
   cada teléfono): no se pudo retratar, la sesión estaba bloqueada y el
   anidado no pinta así.

**El arreglo de la fase 6** (lo que reportó el usuario: lo bajado no se
guardaba): módulo nativo propio `remoto/app/modules/celiuz-nativo` (Kotlin):
MediaStore → `Pictures/Movies/Music/Download` + `/Celiuz Remoto`, abrir con la
app predeterminada o el selector (o el visor de texto de la app para .md,
.txt...), compartir, «Bajar otra vez» sustituye. **Probado en el HONOR**: el
vídeo en Google Fotos reproduciéndose (con «Papelera»: es suyo), la foto en la
galería, el .md en Download y en el visor, sin copias repetidas.

**Fase 7, terminal**: `terminal.py` (PTY, billete de 30 s tras la contraseña
otra vez, vigilante cada 5 s, SIGHUP al grupo), xterm.js en un WebView
(`scripts/gen-terminal.mjs`, generado y sin versionar). **Probado en el HONOR**
con su fish: teclear, Borrar, Ctrl+C, `stty size`, `exit`, el registro.
Fallos encontrados probando: Gboard repetía letras en el WebView (→ campo
nativo visible-password), el campo controlado reenviaba todo, `setNativeProps`
no vaciaba (→ `clear()`), el teclado tapaba la fila de teclas (edge-to-edge).
Y en la ventana de la PC: «Permisos» por teléfono (antes solo por la CLI).

**Fase 8**: subir (a `Descargas/Celiuz Remoto`, sin pisar; probado: llegó
idéntico), Wake-on-LAN (`despertar.py`, `/v0/despertar`, tarjeta «Otros
equipos» en Inicio), escritorio remoto (`pantalla.py`: wayvnc en socket unix +
puente WebSocket + noVNC; probado: se veía el bloqueo de la PC en el celular),
invitación (`invitacion.py`, `/v0/invitacion`, `/control/invitacion`, ventana
«Invitar a alguien», app «Tengo una invitación»). El «me están apagando» de
Android se quedó fuera a propósito (DISEÑO.md, «Fase 8»).

**Pruebas nuevas**: `e2e/remoto-terminal` (28), `e2e/remoto-pantalla` (24),
`e2e/remoto-invitacion` (26), y secciones nuevas en `e2e/remoto-archivos`
(subir), `e2e/remoto-control` (WoL), `e2e/remoto-app` (invitación con el
código de la app). Cada una se comprobó rompiendo a propósito lo que vigila.
58 pruebas en verde.

## 2026-10-20 (PC): Celiuz Remoto, fase 6 — archivos

Subida (el arreglo de guardar en el celular va en la entrada de arriba). Escrita, con pruebas y el APK
instalado en el HONOR; **falta probarla en el celular** (hace falta entrar con
la contraseña de la app, que es del usuario). El usuario pidió seguir sin haber
hecho aún la prueba de verdad de la fase 5 (sigue pendiente, abajo).

- **Servidor**: `archivos.py` (listar, buscar, descargar, miniaturas con ffmpeg
  y cache en `~/.cache/celiuz/remoto/miniaturas`) y `historial.py` (recientes
  con su estado contra la PC, favoritos; 0600). Rutas `/v0/archivos`,
  `/buscar`, `/descargar` (Range), `/miniatura`, `/v0/recientes`,
  `/v0/favoritos`. Todo: permiso `archivos` + pase.
- **La frontera**: `realpath` primero y después mirar que queda en casa; y una
  lista `NUNCA` (.ssh, .gnupg, llaveros, perfiles de navegador, lo de Celiuz
  Remoto) que no sale ni listando, ni con ocultos, ni buscando, ni por enlace.
  Es decisión mía, no del usuario: se le contó al cerrar la fase.
- **App**: pestaña Archivos (maqueta 5: buscar, migas, miniaturas, tarjeta
  Descargar/Ver/Favorito; «Atrás» sube de carpeta) y Recientes (maqueta 6, por
  días, con «Abrir», «Bajar otra vez», «Abrir copia»; mantener pulsado
  olvida). Copias en la carpeta de la app (`descargas/<equipo>/<ruta>`), por
  `.parcial`; «Abrir» con IntentLauncher y «Compartir» con expo-sharing (módulos
  nuevos: expo-file-system, expo-sharing, expo-intent-launcher).
- **Pruebas**: `e2e/remoto-archivos` (75; sin la frontera fallan 13, sin
  `NUNCA` 16) y la ronda 4 de `e2e/remoto-app` (las llamadas y las cuentas de
  `src/archivos.ts`).
- **El HONOR no puede entrar todavía**: su registro `c0615dcf` es el que se
  rompió en la fase 4. Hay que emparejarlo otra vez desde la ventana (con
  Archivos marcado) y después probar: explorar, buscar, bajar un PDF y
  abrirlo, ver una foto, fijar un favorito, Recientes tras cambiar el archivo
  en la PC («Hay versión nueva»).

## 2026-10-20 (PC): Celiuz Remoto, fase 5 — tras un reinicio (SDDM)

Subida en `84c598f`. Escrita y con pruebas; **falta la
prueba de verdad**, que necesita su sudo y salir a la pantalla de inicio (eso
cierra la sesión donde corre Claude, así que la hace él).

- **Arrancar con el equipo = linger**, no una unidad de sistema: el diseño
  pedía «siempre activo, corre como el usuario» y eso es `loginctl
  enable-linger` (sin contraseña). Así lo que escucha por la red nunca nace de
  root. La ventana lo enciende con el servicio y lo apaga solo si lo encendió
  ella (`linger-nuestro`). Como el servicio ya estaba encendido de antes, en la
  PC hay que **apagarlo y encenderlo** desde la ventana para que ponga el
  linger.
- **Medido**: sin sesión, polkit pide contraseña para apagar
  (`auth_admin_keep`; con sesión, `pkcheck` desde el servicio da 0). O sea que
  en SDDM la vigilancia no podría apagar. Por eso la regla de polkit.
- **Lo de root** (`remoto/sistema/`, lo instala `./instalar.sh
  --remoto-sistema`, se quita con `--remoto-sistema-quitar`): regla de polkit
  (apagar/reiniciar/suspender sin sesión + arrancar SOLO
  `celiuz-remoto-entrar@<usuario>.service`), esa unidad, su programa
  (`entrar.py`, COPIADO a `/usr/local/lib/celiuz-remoto/entrar`) y un tmpfiles
  que borra el autologin al arrancar. `entrar.py` se niega si hay una sesión en
  seat0 (reiniciar SDDM la cerraría) o si no sabe; escribe
  `/etc/sddm.conf.d/zz-celiuz-remoto-entrar.conf` (User=, sin Session=),
  reinicia SDDM, espera la sesión y lo borra. `instalar.sh` normal avisa si la
  copia de root se queda vieja.
- **Bloqueada al arrancar**: el servicio deja
  `$XDG_RUNTIME_DIR/celiuz-remoto/entrar-bloqueada`; lo PRIMERO de
  `lua/autostart.lua` es `celiuz-remoto al-entrar && lock.sh` (56 ms). Una
  marca de más de 3 min no cuenta.
- **Servidor**: `inicio.py`, `GET /v0/escritorio`, `POST
  /v0/escritorio/entrar` (energía + pase + confirmar; `409 estado` si no
  toca), `escritorio` en `/v0/vivo` y en `/control/estado` (con `linger` y
  `sistema`). CLI: `inicio`, `entrar`, `al-entrar`; `revisar` dice lo de tras
  reiniciar.
- **App**: tarjeta «En la pantalla de inicio» → «Entrar» (con confirmación;
  sin pase, lleva a renovarlo). Recompilada e instalada en el HONOR.
- **Pruebas**: `unidad/remoto-inicio` (74: la guardia de root falla 4 si se
  quita; la regla de polkit evaluada con Node), `e2e/remoto-inicio` (25), y
  rondas nuevas en `e2e/remoto-app`.
- **La prueba de verdad, en este orden**:
  1. `./instalar.sh --remoto-sistema` (pide sudo).
  2. En la ventana: apagar y encender el servicio (pone el linger);
     `celiuz-remoto revisar` debe decir «sí» en las dos líneas de «Tras
     reiniciar».
  3. Reiniciar la PC y NO entrar. En el celular: la tarjeta «En la pantalla de
     inicio» → Entrar. La PC tiene que abrir la sesión **ya bloqueada**, y
     `/etc/sddm.conf.d/zz-celiuz-remoto-entrar.conf` no tiene que existir
     después. Si algo falla: `journalctl -u celiuz-remoto-entrar@$USER` y
     `journalctl --user -u celiuz-remoto`.
  4. Con la PC en SDDM, apagar desde el celular (lo que hace posible polkit).
  5. Si SDDM se quedara con autologin: Ctrl+Alt+F2 y borrar ese fichero.

## 2026-10-20 (PC): Celiuz Remoto, fase 4 — control y vigilancia

Subida en `2aaef74`.

- **Servidor**: `escritorio.py` (Hyprland vivo en caliente, ventanas, cerrar
  pidiéndolo, presencia en tres salidas), `energia.py` (cuenta atrás,
  `notify-send --wait` con Cancelar que se cierra por id al cancelar, cerrar
  ventanas antes de `systemctl`), `vigilancia.py` (decidir puro; Online +
  LastSeen + LastHandshake + `tailscale ping`), rutas `/v0/energia`,
  `/v0/ventanas`, `/v0/ventanas/{id}/cerrar` (pase), `/v0/latido`,
  `/control/energia`, `/control/vigilancia`. `remoto.conf`: `cuenta_atras`.
  El mismo celular emparejado otra vez SUSTITUYE al viejo (por serie USB).
- **hypridle**: `listener` de 300 s que apunta la presencia
  (`celiuz-remoto presencia ausente|presente`). Hace falta
  `systemctl --user restart hypridle` para que lo lea (hecho en la PC).
- **CLI**: `cancelar`, `vigilancia [si|no]`, `presencia`, `barra`.
- **Barra**: `custom/remoto` (en `derecha.jsonc`): solo con el servicio
  encendido; tenue / verde (celular dentro) / rojo (apagando). Clic: la ventana.
  `instalar.sh` rehace `local.jsonc` al pasar.
- **Ventana**: página Vigilancia (interruptor, presencia, cada teléfono) y la
  cuenta atrás con Cancelar en la tarjeta del servicio. `--pagina vigilancia`.
- **App**: hoja de Apagar/Reiniciar/Suspender (maqueta 4), pestaña Apps
  (maqueta 3), cuenta atrás con Cancelar en Inicio. Recompilada e instalada.
- **Probado en el HONOR real**: suspender con 300 s → aviso en la PC + barra en
  rojo → cancelar desde el celular (y el aviso se quita); ver las apps reales;
  cerrar una ventana de prueba en el escritorio 9 (una kitty con algo corriendo
  pregunta, como debe); vigilancia armada reconociendo al celular.
- **Fallos encontrados probando**: `TypeError` por `accion=` en el registro;
  el aviso de la PC no se quitaba al cancelar; el glifo ⏻ no está en la fuente
  del celular; `Online` atascado del coordinador (→ handshake + ping); el mismo
  celular emparejado dos veces quedaba duplicado; el puerto USB chocaba al
  emparejar otra vez enseguida; títulos largos en varias líneas.
- **Un error mío en la prueba**: emparejé el celular de prueba encima del
  emparejamiento que el usuario había hecho a las 19:50, y la app sustituyó su
  clave. Su registro (`c0615dcf…`) sigue en la PC pero ya no puede entrar:
  **el usuario tiene que volver a emparejar** (con el arreglo de la serie, ese
  registro viejo se sustituye solo).
- **Pruebas**: `unidad/remoto-vigilancia` (39), `e2e/remoto-control` (41),
  `e2e/remoto-app` con ronda de control, `e2e/remoto` (81).
- **Falta de la fase 4**: el «me están apagando» del lado de Android (módulo
  nativo con `ACTION_SHUTDOWN`); el servidor ya lo acepta. Va a la fase 8 o
  cuando toque.
- **Lo siguiente: fase 5** — hecha arriba.

## 2026-10-20 (PC): Celiuz Remoto, fase 3 — la app del celular

**Sin commitear** (el usuario lo sube él).

- **Pantallas** (las maquetas 1, 2 y 8, más Bienvenida y la del cable):
  emparejar y renovar (las abre la PC por adb, con el puerto en el enlace
  `?p=`), Entrar (equipos con «En línea / Apagada», 5 intentos, «Olvidar» si
  la PC ya no lo reconoce), Inicio (estado cada segundo; solo lo que el equipo
  tiene) y Pase vencido. Apagar, Apps, Archivos y Terminal se ven apagados con
  «pronto». La huella («Usar la huella además») no está: irá con
  `requireAuthentication` de expo-secure-store.
- **Una clave Ed25519 por equipo**, en el almacén seguro de Android, sin copia
  de seguridad (`allowBackup: false`).
- **`remoto/app/compilar.sh`**: compila en la PC (Java 17 + `~/Android/Sdk`),
  firma con `~/.config/celiuz/remoto/firma.keystore` (creada la primera vez,
  contraseña al lado, 0600) y deja el APK en `~/.local/share/celiuz/remoto/`,
  de donde lo instala la ventana. Solo ARM: 33 MB (con x86, 67).
- **Paleta**: nuevo `$exito` (verde) en `colores.conf`, que vivía copiado a
  mano. La app no lleva ni un color escrito: los translúcidos con `alfa()`.
- **Probado en el HONOR X7b de verdad**: instalar desde la PC, emparejar por
  cable, «En línea» por Tailscale, contraseña mala (quedan 4), entrar, estado en
  vivo con los números de la PC, renovar el pase por cable, revocar desde la PC
  con la sesión abierta (se cae al instante), Olvidar, y actualizar el APK
  encima (misma firma). Capturas en la conversación.
- **Fallo encontrado así**: `adb shell` se comía la contraseña que la CLI leía
  por stdin. Arreglado y con prueba que lo caza.
- **Pruebas**: `e2e/remoto-app` (40, el código de la app con Node contra el
  servidor) y lo que se añadió a `e2e/remoto` (78) y `unidad/generados`.
- **Lo dejé así**: servicio APAGADO, ningún teléfono emparejado (el de prueba
  se revocó y se olvidó), la app instalada en el HONOR. El usuario empareja el
  suyo con su contraseña desde la ventana.
- **Lo siguiente: fase 4** — apagar / reiniciar / suspender con cuenta atrás,
  ver y cerrar apps, la vigilancia (Tailscale `Online` + presencia) y el icono
  de la barra.

## 2026-10-20 (PC): Celiuz Remoto, fase 2 — la ventana de la PC y el servicio

**Sin commitear** (el usuario lo sube él).

- **La ventana** (`remoto/escritorio/celiuz-remoto-config.py`, lanzador
  «Celiuz Remoto»): la pantalla 9 de las maquetas. Teléfonos (los pasos del
  cable: depuración USB, Tailscale, la app, contraseña, permisos; y los
  emparejados con su pase, desbloquear, quitar el pase, revocar), Registro y
  Ajustes; abajo, el interruptor del servicio. Flotante y centrada (regla en
  `lua/windowrules.lua`); el tamaño lo elige ella (la maqueta, 1200x760, no
  cabe en la laptop). Mirada en el anidado a 1920x1080 y a 1366x768.
- **`adb.py`** (detectar, `-s serie` siempre, nombre comercial, abrir el canal,
  intent explícito, instalar) y **`cable.py`** (los pasos, que usan igual la
  CLI y la ventana; cierra el canal salga como salga). Probado con los dos
  celulares reales: HONOR X7b (Android 14, con Tailscale: es el `node` de la
  tailnet) y Redmi Note 10S (Android 13, SIN Tailscale).
- **Emparejar ya da el pase de 24 h** (la maqueta dice «Emparejar y dar pase»):
  se cumple lo que pide, cable + contraseña recién creada delante de la PC. Y
  cada teléfono guarda su serie USB, para reconocerlo al enchufarlo.
- **El servicio**: `celiuz-remoto.service` (de usuario, `Restart=on-failure`
  mientras Tailscale no tenga IP). `instalar.sh` lo deja puesto y APAGADO
  (sección 9; la recarga de la sesión pasó a ser la 10). **Fallo encontrado
  probándolo**: enlazada, `systemctl --user disable` borraba la unidad; ahora
  se copia. Probado en la PC: dos ciclos encender/apagar, escucha solo en la
  IP de Tailscale, sin un traceback. **Lo dejé apagado**: lo enciende el
  usuario desde la ventana.
- **Pruebas**: `e2e/remoto` (77: emparejar por el cable con un `adb` de
  mentira que hace de celular; canal cerrado aunque falle a medias),
  `unidad/remoto-escritorio` (42: textos, adb, CSS sin colores a mano, viene
  apagado, no cae a X11). Las dos cazan sus mutaciones.
- **Pendiente de la fase 2 del diseño que no entra aquí**: el icono en la barra
  («¿está activo? ¿hay un celular ahora?») va con la vigilancia, en la fase 4.
- **Lo siguiente: fase 3**, la app del celular. Hace falta un JDK para Gradle
  (`sudo pacman -S jdk17-openjdk`); el SDK de Android ya está en
  `~/Android/Sdk` (build-tools 36, plataformas 36.1 y 37). Se probará en el
  HONOR, que es el que tiene Tailscale.

## 2026-10-20 (PC): Celiuz Remoto, fase 1 — el corazón del servidor

**Sin commitear** (el usuario lo sube él). El plan va en 8 fases
(`remoto/DISEÑO.md`, «Fases»); el usuario pidió cerrar cada una probada y sin
fallos antes de pasar a la siguiente.

- **Decidido con el usuario** (era la propuesta pendiente): el servicio acaba
  siendo de SISTEMA para contestar tras un reinicio, con autologin de un solo
  uso y la sesión arrancando bloqueada (fase 5); la vigilancia mira `Online`
  en `tailscale status` en vez de latidos; la GPU por NVML. En `DISEÑO.md`.
- **Corregido en el protocolo**: el borrador guardaba `sha256(clave)` y
  comprobaba un HMAC con ella, y eso es imposible (un HMAC se verifica con la
  clave entera). Ahora el celular genera un par **Ed25519** y la PC guarda
  solo la pública. Todo lo que se firma lleva prefijo (`PROTOCOLO.md`).
- **Hecho**: `dispositivos.py` (0600, flock, un fichero roto no se pisa),
  `sesion.py` (reto de un uso, firma ANTES que contraseña para que un intruso
  no pueda bloquear al bueno, 5 intentos, sesión que caduca sin uso),
  `pase.py`, `registro.py` (tacha secretos), `red.py` (solo 100.64.0.0/10 o
  bucle local, nunca 0.0.0.0), `estado.py` (psutil + NVML por ctypes; en un
  híbrido la dedicada no se toca), `ajustes.py` (`remoto.conf`), `servidor.py`
  (red, canal USB que se abre y se cierra, socket de control) y la CLI
  (`servir`, `estado`, `dispositivos`, `emparejar`/`renovar --sin-adb`,
  `revocar`, `desbloquear`, `quitar-pase`, `permisos`, `registro`).
- **La paleta de la app la genera ya `gen-colores.py`** (`colores.json`), y
  `app.json` pasó a `app.config.ts` para leerla.
- **Probado**: `tests/e2e/remoto.sh` (64, servidor de verdad contra un celular
  de mentira; caza las mutaciones «contraseña antes que firma» y «renovar sin
  contraseña») y `tests/unidad/remoto.sh` (38). Y en vivo con el Tailscale de
  la PC: escucha solo en `100.113.246.39:47110`, entra por ahí, y no contesta
  en `127.0.0.1` ni en la LAN.
- **Lo siguiente: fase 2**, la app de la PC (GTK) + `adb.py` + la unidad de
  systemd + `instalar.sh --revisar`.

## 2026-10-20 (PC): nace Celiuz Remoto (`remoto/`), solo la estructura

**Sin commitear todavía** (a petición del usuario): `git status` lo enseña todo.

Una app Android para manejar la PC y la laptop desde fuera: estado en tiempo
real, apagar, ver y cerrar apps, archivos y terminal con sudo. **Todavía no hace
nada**: hoy se cerró el diseño con el usuario y se armó el esqueleto.

- **Léelo antes de tocar nada**: `remoto/DISEÑO.md` (cada decisión y su porqué:
  contraseña propia creada en la PC, pase de 24 h exactas que solo se renueva
  por cable, vigilancia que apaga la PC si el celular calla 2 h sin nadie
  delante...) y `remoto/PROTOCOLO.md` (el contrato app ↔ servidor, v0).
- Maquetas de las 9 pantallas, aprobadas por el usuario «tal cual»:
  https://claude.ai/artifact/BGqHdnHe5W2Xu7LNuVwYUd
- Lo que ya funciona: `remoto/servidor/celiuz-remoto.py revisar` (qué le falta
  al equipo) y `rutas`; lo vigila `tests/unidad/remoto.sh`. Los módulos de
  `servidor/celiuz_remoto/` solo tienen su cabecera con lo que harán.
- La app (`remoto/app/`, Expo SDK 58 + TypeScript) arranca y pasa
  `npm run typecheck`. `node_modules` (377 MB) no se versiona.
- **A la PC le falta** `sudo pacman -S tailscale python-aiohttp android-tools`
  (y para compilar el APK, `jdk17-openjdk` y el SDK de Android).
- **Pendiente antes de la fase 1**: que `gen-colores.py` genere la paleta de la
  app (`App.tsx` y `app.json` llevan el violeta copiado a mano, avisado en el
  propio fichero); y decidir qué pasa con la PC en la pantalla de SDDM (el
  servicio es de la sesión).
- `tests/unidad/portabilidad.sh` se salta ahora `node_modules` y `.expo`.

## 2026-10-20 (PC): la barra de arriba ya no se escondía, y cada pantalla a sus Hz más altos

- **Qué era**: una waybar de arriba de las 05:13 seguía viva como hija del
  demonio, pero `self.proc` ya no la nombraba. Se quedaba en `top` sin recibir
  un solo toggle, y al haber dos barras de arriba en niveles distintos,
  `realinear()` relanzaba la apuntada cada 5 s sin tocar la otra: un bucle
  para siempre. Se veía con `pgrep -af 'waybar -c'` (dos `config.jsonc`) y en
  `hyprctl layers` (dos `waybar-main`, una en cada nivel).
- **Qué no era**: no ignoraba SIGTERM (comprobado: muere con él). El demonio
  nunca se lo mandó. **No se averiguó qué camino la soltó**; en el diario no
  hay bloqueo ni modo gaming a esa hora. Si vuelve a pasar, apunta la hora y
  lo que se hizo justo antes.
- **El arreglo** (`58b2153`): `relanzar()`, por donde pasan todos los
  relanzamientos, barre por PPID y ruta de config (`hijos_con_config`) a
  cualquier otra waybar con la misma config, y remata con SIGKILL la que no se
  vaya con SIGTERM. Sea cual sea la causa, el primer realineo la recoge.
  `unidad/barras-supervisor` (16; falla 5 contra el código viejo). Trampa
  nueva en `CLAUDE.md`.
- **Y la PC se quedaba a 60 Hz tras cada recarga.** Salió al repasar las
  notas: `hyprctl reload` reaplica `preferred` (el modo del EDID, 60) y
  `monitores.py` solo escuchaba enchufes. Como `instalar.sh` recarga ya la
  sesión al final (`fa50d4a`), cada `git pull && ./instalar.sh` la bajaba a
  60. Ahora escucha también `configreloaded` (medido: Hyprland lo emite en
  cada reload); `unidad/monitores` 5b (falla contra el código viejo). En vivo:
  demonio reiniciado, `reload`, y se queda en 100.
- **Y luego, a petición del usuario («que cada máquina tenga sus Hz más
  altos»)**: `monitores.py` ya era genérico (ningún 100 escrito: el refresco
  más alto a la resolución de cada pantalla), pero cada recarga seguía pasando
  por 60 y subiendo, un parpadeo. Ahora **`lua/monitors.lua` elige al
  cargarse** con `hl.get_monitors()` (que trae `available_modes` y la marca
  `preferred`) y escribe la regla con el nombre de cada pantalla encendida.
  Medido en la PC sin el demonio: durante un `reload`, 55 de 55 muestras a 100.
  Y medido que gana la última regla de una salida, así que `personal.lua`
  manda. `monitores.py` queda para la primera carga (sin salidas aún) y lo que
  se enchufa, y ahora sube el refresco aunque la resolución puesta no sea la
  mayor (antes se rendía). Pruebas: `config-lua` §8 (100, 144, el televisor,
  personal gana) y `monitores` (120 dentro de 720p, 144, 165 de portátil).
  **En la laptop**: el televisor está fijado en su `personal.lua` y se le
  respeta; si se quiere que suba solo, quitar de esa línea el `mode`
  (comprobar antes con `monitores.py --ver` qué anuncia). La pantalla interna
  sube sola.
- **En la PC**: los dos demonios reiniciados y `./instalar.sh` pasado: 43/43,
  «sin pendientes», `configerrors` vacío, 62 atajos, 100 Hz, una waybar por
  config y la de arriba escondida con ventanas abiertas.
- **En la laptop**: `git pull && ./instalar.sh`, y luego volver a entrar (o
  `SUPER+SHIFT+C` para las barras) para que los dos demonios carguen el código
  nuevo. Allí lo de los 60 Hz importa con el televisor puesto.
- **Prueba intermitente**: `unidad/portapapeles` falló una vez en «no toco la
  cache real del usuario» y pasó al repetirla. La huella de
  `~/.cache/celiuzpaper` cambió por la sesión real mientras corría, no por la
  prueba. Si se repite a menudo, que esa comprobación ignore lo que escribe la
  sesión (el `lock.log`, los `lock-*.conf`).

## 2026-10-20 (laptop): con el bloqueo solo se ve el fondo

Reporte de alguien que usa el repo: una partida de Minecraft detrás del bloqueo.
Era el vigilante del modo gaming devolviendo del escritorio 99 al del juego.
Arreglado en tres capas: el vigilante respeta el 99 (`WS_BLOQUEO`), `lock.sh`
mira que no se vea nada en ninguna pantalla antes de encender el xray (si no,
fotograma), y un vigía lo apaga si aparece una ventana bloqueado.
`e2e/bloqueo` (58), `unidad/a-la-vista` (13).

Probado por el usuario en el modo gaming: salía NEGRO, porque el modo apaga el
video del fondo y el xray no tenía nada que enseñar. Ahora, sin video vivo, el
fotograma se saca del fichero (`wallpapers/current`) y se usa en vez del xray.
Encender el video solo para el bloqueo se descartó con el usuario (~430 MB y la
GPU con el juego detrás, y 3-8 s de negro en la NVIDIA). **Falta en vivo**:
bloquear otra vez en el modo gaming (debe salir el fondo, quieto); y en la PC con
el televisor puesto y ventanas en él.

## 2026-10-20 (laptop): teclado de España y aviso al conectar

- La tarjeta de `teclados.py` tiene tres opciones: `Ñ Ç` España (`es,us`), `Ñ`
  Latinoamérica, `; :` Inglés. Salió de un teclado Fiddler de España de un
  amigo del usuario. Vista en anidado; `es,us` aplicado da «Spanish».
- Al conectar un teclado ya conocido, aviso «Teclado X conectado… configuración
  cambiada automáticamente» (no en el arranque de la sesión).
  `unidad/teclados` (36). `teclado.py` (SUPER+Supr) nombra también «Español
  (España)».
- Cada teclado lleva su distribución a la vez (`hl.device`): falta **verlo en
  vivo** con el teclado US de la PC enchufado a la laptop, escribiendo en los
  dos.

## 2026-10-20 (laptop): la barra de FPS no salía

- Faltaba **MangoHud** en la laptop (instalado; ahora `instalar.sh` avisa).
- Y Silksong es **nativo con OpenGL**: `MANGOHUD=1` solo vale para Vulkan. El
  modo pone ahora `mangohud %command%` en las opciones de lanzamiento VACÍAS al
  preparar Steam (`modo-gaming.juegos_sin_mangohud`, `unidad/mangohud-lanzamiento`).
  Como Steam ya corría con el overlay, la próxima entrada al modo lo reinicia
  una vez para escribirlo. La tecla estaba bien: «Ins» manda `Insert` (medido
  con `xkbcli interactive-wayland`).
- **Visto**: la barra sale en Silksong con Ins.
- **La barra enseña solo lo que el equipo tiene**: `lib/hardware.py` (pedido por
  el usuario) mira al entrar al modo cada GPU (integrada o dedicada, sensor,
  memoria propia), el sensor del CPU y la bateria. Integrada: sin «0 °C» ni
  «VRAM 0.0»; hibrido: con el nombre de la GPU; portatil: con bateria (añadido
  sin pedirlo: si no la quiere, fuera). `hardware.py` da el resumen con el
  porque; `unidad/hardware` (21). **En la PC**: `hypr/scripts/lib/hardware.py`
  debe decir NVIDIA dedicada y la barra, temperatura y VRAM de la 3050.

## 2026-10-20 (portátil): el repo pasa a privado y trae las imágenes del saludo

El usuario lo hizo privado y las 455 imágenes de `~/Imágenes/terminal` se
movieron a `fastfetch/imagenes/` (33 MB). `saludo.sh --carpeta` las busca ahí,
junto al propio script. **En la PC, tras `git pull`**: abrir una kitty y ver
que sale una imagen; la carpeta vieja de allí (`~/Imágenes/terminal`, si la
tenía) ya no se mira.

Y un aviso que salió en la laptop durante el rebase, «module 'lua.teclados' not
found»: git escribió `hyprland.lua` antes que el módulo nuevo y Hyprland recargó
en el hueco. Ahora se carga solo si el fichero está (`5ffad6f`).

## 2026-10-20 (PC): traído `b6ee1bb`

- `git pull` + `./instalar.sh`: 43/43, «sin pendientes», `configerrors`
  vacío, 62 atajos. La tarjeta salió por la X820 y quedó `us,latam`
  (`altgr-intl,`, lo mismo que el global). Barras recargadas.
- **El pull dejó «Your config has errors: cannot open hyprland.lua»** y a
  Hyprland sin vigilar la config: trampa nueva en `CLAUDE.md` («Y un `git pull`
  puede dejar a Hyprland ciego»). `instalar.sh` recarga ahora la sesión al final.
- `e2e/bluetooth-panel` falló UNA vez en la tanda completa y luego pasó 19 de
  19 (suelta, en tanda y 12 en paralelo). Parece de tiempos, como
  `unidad/modo-gaming`: si vuelve, guarda la salida (`./tests/run.sh > log`)
  para ver qué comprobación cae. Sospechosas: el plazo fijo de 1,2 s de
  «buscar» y «A sale»/«B sale», que no esperan.
- El saludo, visto en kitty en la PC: sale la imagen.
- **La PC no tiene Bluetooth** (sin `/sys/class/bluetooth`; la placa no trae):
  el módulo se esconde solo y el panel no se prueba ahí. En la laptop va bien.
- Falta en la PC: el panel de red, Ctrl+RePag/AvPag y SUPER+Supr en vivo.

## 2026-10-20 (portátil): saludo sin repetir, Insert para el overlay, y cada teclado con su distribución

- **El saludo** sale al azar **sin repetirse** hasta haber enseñado todas, y la
  vuelta nueva no empieza por la última (`unidad/saludo`).
- **El overlay de FPS**: Supr en la PC, **Insert** (o «Ins», el mismo keysym)
  en un portátil — `modo-gaming.tecla_overlay()`, lo lee MangoHud
  (`toggle_hud`). **Falta probarlo con un juego** en las dos máquinas.
- **Cada teclado con su distribución** (`hypr/scripts/teclados.py` +
  `hypr/lua/teclados.lua`), elegido por el usuario («preguntar una vez»): al
  enchufar un teclado desconocido sale una tarjeta «¿Qué tiene la tecla de la
  derecha de la L? Ñ / ; :», se aplica en el acto a ese teclado y se recuerda
  en `~/.config/celiuz/teclados.conf`. Probado en anidado (aplica en caliente
  y aguanta un `reload`) y en `unidad/teclados` (31). En la laptop no pregunta
  nada (el interno y el ratón USB quedan fuera: `teclados.py ver`). Demonio
  lanzado a mano en la sesión de la laptop; arranca solo al volver a entrar.
  **Pendiente en la PC**: tras `git pull`, cerrar sesión y entrar; debe salir
  la tarjeta por la X820 → contestar `; :`. Comprobar con `teclados.py ver` y
  `hyprctl devices` que queda `us,latam`, y que SUPER+Supr sigue alternando.

## 2026-10-19 (portátil): paneles que se excluyen y el saludo de la terminal

- **Los paneles de la barra se excluyen** (`lib/panel_capa.PANELES`): abrir el
  reloj cierra el de red, etc. Probado en la sesión real (WiFi → reloj →
  Bluetooth: siempre una sola capa) y con `unidad/paneles-exclusivos` (12).
- **El saludo de la terminal**: `fastfetch/config.jsonc` + `hypr/scripts/saludo.sh`
  (`celiuz-saludo`), imagen al azar de `fastfetch/imagenes/` (en el repo desde el 2026-10-20) por el protocolo
  de kitty, enganchado a fish por `instalar.sh` (`saludo_fish`). Visto en
  anidado; `unidad/saludo` (21). Las imágenes se adaptan (`lib/imagen_saludo.py`:
  recorte del aire transparente, esquinas redondeadas, 400 px) a una caché, en
  segundo plano la primera vez. Aplicado a mano en la
  laptop (los dos enlaces, la carpeta y la línea de config.fish).
  Pendiente: que el usuario ponga sus imágenes; en la PC, `./instalar.sh`.

## 2026-10-19 (portátil): el panel del Bluetooth

Los auriculares no conectaban: unos TWS con dirección nueva, sin emparejar (ver
la trampa en `CLAUDE.md`). Emparejados a mano, y de ahí salió **el panel**
(`hypr/scripts/bluetooth-panel.py`), elegido por el usuario entre dos maquetas
(un menú propio y blueman): el clic en el icono ya no abre bluetui, abre el
panel. Probado en anidado con el BlueZ falso (capturas del abierto, del editor
del «⋯», de emparejar) y con pruebas: `unidad/bluetooth-panel` (48) y
`e2e/bluetooth-panel` (31, con el demonio delante).

Pendiente:
- **Probarlo en la sesión real de la laptop** (la PC no tiene Bluetooth) tras recargar las barras
  (`SUPER+SHIFT+C`): abrir, cerrar, «Usar este» entre dos auriculares
  encendidos, y emparejar unos de verdad. Con el televisor enchufado, que
  salga bajo el icono de la pantalla donde se pincha.
- Los dos TWS viejos de la laptop (`41:42:47…`, `41:42:39…`) ya no aparecen:
  el usuario decide si se olvidan (el «⋯» del panel lo hace).
- **El panel del reloj** (`calendar-panel.py`, reescrito sobre `PanelCapa`):
  la maqueta 2 (`~/Imágenes/maqueta-reloj/`), con el tiempo girando despacio
  alrededor de la hora, luna, zodiaco y el próximo feriado. El tiempo y la
  ubicación con las reglas de privacidad del usuario (cabecera de
  `lib/clima.py`). Probado en anidado y en `unidad/reloj-panel` (42).
- **El panel de red** (`hypr/scripts/wifi-panel.py`): elegido por el usuario
  sobre dos maquetas (`~/Imágenes/maqueta-wifi/`), con el QR dentro del «⋯» →
  «Compartir red». Comparte base con el del Bluetooth (`lib/panel_capa.py` +
  `lib/panel_estilo.py`). Probado en anidado con un `nmcli` de mentira y con
  pruebas: `unidad/wifi-panel` (48), `e2e/wifi-panel` (18). **Falta probarlo en
  la sesión real conectando a una red nueva de verdad** (la conexión por D-Bus
  solo se ha ejercido contra el NetworkManager falso), y en la PC, que va por
  cable y quizá sin wifi.
- **Las teclas de volumen** movían la salida predeterminada (los altavoces) y
  no la que sonaba (los TWS). Arreglado en `osd.sh` + `lib/sonido.py salida`,
  comprobado en vivo en el portátil. **En la PC, comprobar Ctrl+RePag/AvPag**
  con lo que suele usar (¿auriculares, HDMI?) tras el pull.
- `unidad/modo-gaming` falló una vez en la tanda completa y pasó sola (78/78):
  parece de tiempos. Vigilar.

## Lo PRIMERO la próxima vez

1. `git status`, `git log --oneline -5`, y este fichero.
2. **En la laptop: cerrar sesión y volver a entrar**, si no se hizo ya. La
   sesión de ese día siguió en la config vieja (hyprlang) a propósito; al volver
   a entrar Hyprland coge `hypr/hyprland.lua`. Comprobar:
   - `./instalar.sh --revisar` → debe decir «la sesión abierta ya usa la config
     en Lua» (y ya no avisar de lo contrario).
   - `hyprctl configerrors` vacío; `hyprctl binds -j | jq length` → **62**.
   - Las pantallas: con el televisor enchufado, que salga a la derecha y a
     escala **1.5** (vienen de `hypr/lua/personal.lua`, traducido del
     `personal.conf`).
   - A mano, un momento: `SUPER+SHIFT+P` (menú; Escape), `SUPER+SHIFT+V`
     (portapapeles), subir/bajar volumen y brillo (el aviso de abajo), `SUPER+L`
     y desbloquear, arrastrar una ventana con `SUPER + clic`, `SUPER+TAB`.
3. **La PC ya está hecha y verificada** (abajo). No hay que repetir nada ahí.

---

## Lo que se verificó en la PC (2026-09-25, tras entrar con Lua)

La PC hizo `git pull` hasta `24d1fe5` + `./instalar.sh`, cerró sesión y entró.
Todo lo que trajo el pull funciona. Medido, no supuesto:

| Comprobación | Esperado | Salió |
|---|---|---|
| `./instalar.sh --revisar` | «ya usa la config en Lua» | eso dice, y «sin pendientes» |
| `hyprctl configerrors` | vacío | vacío |
| `hyprctl binds -j \| jq length` | 57 | **58** — ver abajo |
| Pantalla | sus 100 Hz | `HDMI-A-1 1920x1080@100Hz`, «ya está en su mejor modo» |
| `./tests/run.sh` | 30 en verde | 30/30 |
| `./instalar.sh --sddm` (estaba pendiente) | — | ya hecho: `Current=celiuz` |

**Los 58 atajos no son un error.** El de más es del usuario: `SUPER+A →
celiuzpanel`, puesto en `hypr/lua/personal.lua`, que no se versiona y se carga
el último. 58 − 1 = los 57 del repo. Si algún día ese número no cuadra, mira ahí
antes de buscar en `lua/keybinds.lua`.

Lo nuevo, probado en vivo y no solo leído del disco:

- **Menú de salida**: `SUPER+SHIFT+P` está atado a `sesion.sh`. No se lanzó
  desde la terminal a propósito —abre el fuzzel y le roba el teclado a quien
  esté delante—; sus 43 comprobaciones pasan.
- **Portapapeles**: el vigilante vive (`wl-paste --watch … portapapeles.py
  recibir`). Se copió una cadena de prueba, el historial pasó de 0 a 1, y se
  dejó como estaba (`portapapeles.py vaciar`, y el portapapeles del usuario
  intacto).
- **Volumen a la vista**: bajar + subir devolvió el volumen exacto a `0.80` y
  mako aceptó el aviso (el id quedó apuntado en `$XDG_RUNTIME_DIR`). En esta
  máquina no hay atajos de brillo, como toca en un sobremesa.
- **Lua**: `hyprctl` responde en modo Lua, `local.lua` detectó bien (sobremesa,
  `us,latam`) y `personal.lua` se tradujo entero, sin ningún «SIN TRADUCIR».

Los demonios están todos arriba: las 4 waybar, mako, mpvpaper con el fondo,
`avisos.py`, `monitores.py`, `bluetooth.py`, `waybar-autohide.py`,
`wallpaper-pause.py` y `celiuz-core` (el asistente, que arranca desde
`personal.lua` y vive en **otro repo**).

---

## Lo que se hizo el 2026-09-25

Cuatro cosas, en este orden, todas con prueba automática y probadas en vivo:

1. **Menú de salida** (`SUPER+SHIFT+P`, `hypr/scripts/sesion.sh`). Antes era un
   `exit` a secas y se rozaba. Cerrar sesión, reiniciar y apagar preguntan otra
   vez con «No» en la primera línea (la que fuzzel preselecciona). Cerrar sesión
   va por `uwsm stop` si la sesión es de uwsm.
2. **Historial del portapapeles** (`SUPER+SHIFT+V`, `hypr/scripts/portapapeles.py`)
   con **fijados** (hasta cerrar sesión, en `$XDG_RUNTIME_DIR` con la firma) y
   **guardados** (en `~/.local/share/celiuz/portapapeles/`). Ctrl+F / Ctrl+G /
   Ctrl+D fijan, guardan y borran; la segunda vez deshacen. El historial caduca
   a las 24 h y a las 50 entradas (`~/.config/celiuz/portapapeles.conf`). Nunca
   apunta lo que un gestor de contraseñas marca como secreto. Sin cliphist y sin
   paquetes nuevos.
3. **Volumen y brillo a la vista** (`hypr/scripts/osd.sh`): un aviso de mako
   abajo con barra, que se reescribe en vez de apilarse, sin sonido, fuera del
   historial de avisos (`avisos.py` ya no apunta los transitorios) y visible en
   «no molestar».
4. **La config de Hyprland pasa a Lua** (`hypr/hyprland.lua` + `hypr/lua/`),
   antes de que la 0.57 retire hyprlang. Todo lo que hay que saber de esto está
   en el CLAUDE.md («La config es Lua»); lo esencial:
   - **`hyprctl` cambia de idioma** con el modo de la sesión: en Lua,
     `dispatch workspace 3` y `keyword` dan error. Todo el repo pasa por
     `lib/hypr.py` / `lib/hypr.sh` / `scripts/despachar.sh`. Se encontraron y
     arreglaron tres lectores de `getoption` que en Lua habrían fallado en
     silencio (`lock.sh` con el xray, `recargar.sh` con avisos falsos,
     `screenshot.sh`).
   - **Verificada contra la vieja**: 354 opciones, atajos con su acción,
     animaciones, monitores, teclado y reglas de ventana, en cuatro anidados
     (hyprlang/Lua × portátil/sobremesa). Las herramientas quedaron en
     `tests/herramientas/` (`volcar.py` + `comparar.py`).
   - Pruebas nuevas: `hypr-compat`, `config-lua` (la config entera con un `hl`
     de mentira, sin compositor), `migrar-personal`, y el modo Lua en `bloqueo`,
     `monitores` y `captura`. **30 pruebas en verde**, también en una copia con
     solo lo versionado (como la tendría quien clona).

### El puente (y cuándo quitarlo)

Los `.conf` de `hypr/conf/` y `hypr/hyprland.conf` se quedan **congelados**:
una sesión que arrancó con ellos y los viera desaparecer se quedaría sin atajos
(medido: de 62 a 6, y Hyprland regeneró un `hyprland.conf` de fábrica en el
repo). **No se editan**; lo nuevo va en `hypr/lua/`.

**Se borran cuando las DOS máquinas hayan entrado con Lua.** La PC ya entró
(2026-09-25, verificado arriba); **falta confirmar la laptop**. Lo que hay que
tocar ese día:

- Borrar `hypr/hyprland.conf` y de `hypr/conf/` todo menos `colores.conf` y
  `colores-pango.conf` (esos dos siguen: la paleta y hyprlock).
- `instalar.sh`: dejar de escribir `hypr/conf/local.conf` y de crear
  `hypr/conf/personal.conf` (la traducción a `personal.lua` puede quedarse para
  quien venga de una copia vieja).
- `tests/anidado.sh`: quitar el vaciado de `autostart.conf` y el `local.conf`
  de respaldo.
- `tests/unidad/maquina.sh`: las secciones que miran `hyprland.conf` y
  `$conf_maquina`; `tests/unidad/portabilidad.sh`: la sección 2 (los `.conf`).
- `hypr/scripts/lib/hypr.py` / `hypr.sh`: la rama de hyprlang puede quedarse
  (no molesta) o irse; si se va, `hypr-compat.sh` y el caso hyprlang de
  `bloqueo.sh` con ella.
- README (tabla «Qué hay dentro», «El puente») y CLAUDE.md.

---

## Pendientes, por orden de valor

1. **Modo gaming — EN CONSTRUCCIÓN.** El diseño está cerrado con el usuario
   (2026-09-25) y va en la sección «Modo gaming: el diseño», más abajo; las
   maquetas que aprobó están en `~/Imágenes/modo-gaming/` (fuera del repo).
   Lo que ya existía y en lo que se apoya:
   - `hypr/scripts/lib/juegos.py` — **ya sabe decir si algo es un juego**, por
     cuatro capas (Steam, ananicy, flatpak de juego, pantalla completa) más las
     excepciones a mano de `hypr/congelar-excepciones.json`. Lo usa `lock.sh`
     para no congelar una partida al bloquear. Cualquier modo gaming debería
     apoyarse aquí en vez de inventarse otra detección.
   - `hypr/scripts/wallpaper-pause.py` — ya **mata mpvpaper entero** mientras
     corra algo de `~/.config/mpvpaper/stoplist` (ahora mismo: `gamescope`), y
     lo levanta al salir. Libera ~430 MB de RAM y la VRAM. Añadir un juego al
     modo puede ser tan fácil como añadirlo a esa lista.
   - Candidatos que NO están hechos: barras fuera, avisos en «no molestar»,
     `lua/env.lua` (sigue vacío; es el sitio de lo de Nvidia), y el
     `hyprpolkitagent` del punto 3.
   - **Fuera del repo, pero importa para jugar en ESTA PC**: el teclado
     X820UItra (`3151:5002`) se anuncia como joystick y dejaba sin mando a
     todos los juegos. Arreglado con `/etc/udev/rules.d/99-fix-fake-joystick.rules`
     + `~/.local/share/mando-check/aplicar-fix.sh` + el comando `mando-check`.
     Nada de esto se versiona aquí: **se pierde al reinstalar el sistema.** Si
     un mando «deja de funcionar», corre `mando-check` antes de tocar el repo.
2. **Agente de polkit.** No hay ninguno (comprobado el 2026-09-25: corre
   `polkitd`, pero ningún agente), así que `pkexec`, GParted y compañía fallan
   sin pedir contraseña. Candidato: `hyprpolkitagent` (repo `extra`) arrancado
   desde `lua/autostart.lua` o por su unidad de systemd. El usuario lo está
   pensando.
3. **Atajos básicos que faltan**: pantalla completa, mover ventanas con
   SUPER+SHIFT+flechas, redimensionar con el teclado, escritorio especial
   (cajón), cambiar de escritorio con SUPER + rueda. Todo en `lua/keybinds.lua`
   con `accion(...)` (lleva descripción; `hyprctl binds` la enseña).
4. **`hypr/scripts/ir-a-windows.sh` está sin versionar.** Existe solo en la PC
   (`git status` lo saca como `??`), reinicia a Windows escribiendo la variable
   EFI `BootNext`, y `instalar.sh` ya le hace `chmod +x` porque barre
   `scripts/*.sh`. O entra al repo o se va: a medias, la laptop no lo tiene y
   una reinstalación se lo lleva. **Preguntar al usuario antes de subirlo.**
5. **Mantenimiento del repo**: integración continua con `shellcheck`, `ruff` y
   `./tests/run.sh` (necesita `lua` para `config-lua`).
6. **`lua/env.lua` para Nvidia** (vacío). Solo se puede medir en la PC. Pista:
   el anidado sobre esa NVIDIA pide `AQ_NO_MODIFIERS=1`.
7. Reglas de ventana del flujo de seguridad; el login y el TTY en `latam`.

## Modo gaming: el diseño (cerrado con el usuario el 2026-09-25)

**La idea**: un atajo (o el asistente del usuario, en su PC) mete el escritorio
en un modo en el que todo lo que no sea jugar se quita de en medio, y en su
lugar sale una biblioteca de juegos propia a pantalla completa.

**El repo es público: aquí no se nombra al asistente.** Para quien clone el
repo, el modo es un atajo y nada más. Lo que el asistente necesita son dos
puntos de enganche genéricos, que valen para cualquiera:
- `hypr/scripts/modo-gaming.py on|off|toggle|estado [--json]` (el CLI que llama
  él; `on`/`off` sin tarjeta con `--sin-preguntar`, porque ya confirma él).
- `~/.config/celiuz/modo-gaming.d/`: ejecutables que el modo corre al entrar y
  al salir (`on` / `off` como argumento). Vacía para quien clona.

### El flujo (rehecho el 2026-09-26 a petición del usuario)
1. **Atajo del modo** → tarjeta de confirmación (Enter / A; Esc / B, o se va
   sola a los 5 s sin hacer nada). Al salir igual, y avisa si hay un juego.
2. **Al entrar**, detrás del vídeo de entrada del usuario (`video_entrada` en su
   `modo-gaming.json`, con fundido; se salta con Enter/Esc/A): se cierran las
   ventanas que no son juego, lanzador, app permitida ni terminal; lo que queda
   se guarda en un escritorio **oculto** (`special:modo-gaming`); se apagan
   fondo, barras y efectos; Steam a la bandeja con el overlay. Al acabar el
   vídeo, **en el escritorio 1 solo está la biblioteca**.
3. **Un juego lanzado desde la biblioteca se abre en el 1** y la biblioteca se
   cierra. Si el juego se cierra, la biblioteca vuelve al 1.
4. **Todo lo que se abre después** (desde el menú rápido, o una terminal con
   SUPER+Enter) va al **escritorio siguiente** (2, 3...) y te lleva. Una
   segunda ventana de la misma app va con la primera. No hay huecos: si uno se
   vacía, los de detrás corren un puesto; y no se puede ir a uno vacío.
5. **Al salir**, detrás del vídeo de salida: cada ventana guardada vuelve a su
   escritorio, lo abierto durante el modo va a donde estabas, y los efectos
   vuelven cuando acaba el vídeo.
Probado entero en anidado el 2026-09-26 (con los vídeos del usuario, un juego
falso, apps en scopes de systemd como las reales, y una terminal guardada que
volvió a su escritorio 3).

### Tercera ronda (2026-09-26, tras la prueba del usuario)
- Overlay: centrado y del ancho de lo que enseña (`horizontal_stretch=0`).
- Shaders: la causa de esperar 7-15 min en Aniimo era que Steam tenía APAGADO
  el procesado de fondo (`EnableShaderBackgroundProcessing`, apagado de fábrica
  en PC): bajó los shaders nuevos a la 01:34 y no los tocó hasta lanzar el
  juego a las 08:10 (shader_log). `preparar-steam` lo enciende (con Steam
  cerrado) y arranca ANTES del vídeo de entrada. **Lo que no se hace**: seguir
  procesando mientras juegas. Steam lo pausa a propósito con un juego abierto,
  y forzarlo por fuera (fossilize_replay a mano) es competir con el juego por
  la CPU sin saber si Steam lo daría por hecho; se descartó y se le dijo.
- Al empezar un juego se cierran las ventanas de los lanzadores (Steam a la
  bandeja), también la que Steam abre justo después del juego.
- SUPER+1..7 pasan por `modo-gaming.py ir N` mientras dura el modo (antes
  cambiaba y rebotaba, y se veía el fondo vacío un instante).
- Con un juego abierto NO se sale del modo: tarjeta «Tienes un juego abierto»
  (`--forzar` se lo salta).
- Salida: el vídeo va primero y a pantalla completa (se le fuerza), y detrás
  se cierran biblioteca y lanzadores. Probado en la sesión real.

### Cuarta ronda (2026-09-26)
- Al salir del modo se CIERRA lo abierto durante él (pidiéndolo; lo que no se
  deja, como kitty que pregunta, se trae a tu escritorio para que respondas).
  Lo que ya estaba abierto al entrar vuelve a su sitio. Probado en la sesión real.
- Barras y fondo vuelven DESPUÉS del vídeo de salida (antes asomaban encima).
- Fondo negro en el modo: fuera el logo / fondo de fábrica de Hyprland.
- Ctrl+RePág / Ctrl+AvPág: volumen general (le quita a los navegadores el
  cambio de pestaña; queda Ctrl+Tab). Comprobado con un teclado virtual.
- Menú rápido: «ABIERTO» con TODO lo abierto (también lo guardado), el volumen
  de cada app/juego por su árbol de procesos (así sale Glassy, cuyo audio se
  llama «Chromium»), Ir y Cerrar; cerrar un juego pregunta (ir a guardar /
  cerrar ya / cancelar). Quitados los volúmenes por grupo y la lista de
  escritorios.
- Biblioteca: los shaders pendientes se leen EN VIVO del shader_log de Steam
  (config.vdf solo se guarda al cerrar Steam), con el porcentaje del que va.
- Vídeos del usuario en `hypr/modo-gaming/` (no versionado: son de YouTube, y
  el final es de Undertale). Idea pendiente, a decidir por el usuario: unos
  vídeos PROPIOS generados con ffmpeg para que el repo traiga algo de fábrica.
- Arreglado: Glassy Music no se reconocía como app permitida (clase
  `nankill.xyz.glassymusic.mod`) y el modo la cerraba al entrar.
- No se puede: volumen por pestaña del navegador (Chromium saca UN flujo de
  audio para todo el navegador; eso es de una extensión, no del escritorio).

### Quinta ronda (2026-09-26): el menú rápido, más fino
- «ABIERTO» enseña SOLO lo abierto dentro del modo (no lo guardado al entrar).
- «MÚSICA»: una tarjeta por reproductor MPRIS (Brave y Glassy a la vez), cada
  una con el volumen de SU app, e ir / cerrar. La app de cada reproductor sale
  del PID dueño de su nombre en D-Bus (`GetConnectionUnixProcessID`), que es el
  de su ventana; esas apps no se repiten en «abierto».
- Las tarjetas, al estilo de la maqueta (carátula, «jugando · X min», EN
  CURSO) con botones redondos y el volumen fino dentro; sin «sin sonido».
- Probado en anidado con reproductores MPRIS de mentira que suenan silencio
  con `paplay` (con `pw-cat` el flujo no lleva el PID del proceso; las apps de
  verdad van por pipewire-pulse y sí).

### Escritorios
Cada cosa en el suyo, porque es lo que menos gasta: Hyprland no compone ni pide
fotogramas a lo que no se ve, y un juego solo y a pantalla completa puede ir
por *direct scanout* (sin componer nada).

### Qué es juego, lanzador o app (`lib/catalogo.py`)
- **Juego**: Steam con `type = game` en su `appinfo.vdf` (así caen fuera Proton,
  los runtimes, los redistribuibles y Wallpaper Engine, que es `Application`),
  y cualquier `.desktop` con `Categories=Game` que no sea lanzador ni
  herramienta (Soulframe, Hytale, Minecraft Bedrock). Los accesos directos que
  crea Steam (`steam://rungameid/N`) no se duplican: ya salen por Steam.
- **Lanzador**: Steam, Heroic, Lutris, Bottles, itch… Salen en el dock **y** en
  la biblioteca y el menú rápido (para la tienda y las descargas).
- **App permitida**: el navegador predeterminado (`lib/apps.py`) y las que añada
  cada usuario, en `~/.config/celiuz/modo-gaming.json` (no se versiona).
- **El dock no enseña juegos**: `gen-dock.py` los salta al generar.

### La biblioteca (maqueta 1, aprobada tal cual)
Fondo con la imagen grande del juego seleccionado (el «hero» de Steam, en
local), su logo, horas jugadas y última vez, carrusel de carátulas, pestañas
Juegos / Lanzadores / Apps, animación de entrada y otra de salida, y
navegación con **mando y teclado**. Arranca en el último juego jugado.

### El menú rápido (maqueta 2, con la columna de controles añadida)
Arriba lo que está pasando (juego en curso, la música por MPRIS con ⏮ ⏯ ⏭);
en medio los controles (volumen Juego / Música / Chat por PipeWire, silenciar
el micro, captura); abajo lo que se abre (apps, lanzadores, otro juego). Mando
y teclado.

### Atajos (tienen que valer en `us` y en `latam`, en la PC y en la laptop)
| Para | Atajo |
|---|---|
| Entrar / salir | `SUPER+G` |
| Menú rápido | `SUPER` + la tecla de al lado del 1, **por código** (`code:49`), no por símbolo: en `us` es `` ` `` y en `latam` es `\|`/`°` |
| Menú rápido con mando | Select + Start (el Guide es de Steam) |
| Overlay | `Delete` (`DEL`/`Supr`) en la PC, `Insert` (`Insert`/`Ins`, el mismo keysym) en un portátil: la lee MangoHud (`toggle_hud`, `modo-gaming.tecla_overlay()`), no Hyprland; el menú rápido lo alterna con `mangohudctl` |

### Overlay (MangoHud)
Una config del repo con la paleta, que el modo pasa a todo lo que lanza (Steam
arranca con `MANGOHUD=1` y sus juegos lo heredan). Diseño propio, no el de
Afterburner. Ya existía una config solo para Soulframe
(`~/Games/soulframe/mangohud.conf`, fuera del repo).

### Shaders de Steam (la ventana «Processing Vulkan shaders»)
Medido en la PC: la caché va atada a la versión del driver (el cambio del
24-ago la invalidó entera), Steam procesa con pocos hilos (no hay
`steam_dev.cfg`; la CPU tiene 12) y los juegos viven en un HDD. Lo acordado:
procesarlos al entrar al modo, **primero el último juego jugado** (reordenando
`ProcessingQueue` de `config.vdf` antes de arrancar Steam: está SIN comprobar
que Steam lo respete), dar más hilos, y avisar en la biblioteca de lo
pendiente. Steam pausa ese trabajo con un juego abierto.

### Rendimiento: se mide, no se supone
- `gamemode` aporta poco AQUÍ: la CPU ya está en `performance` (amd-pstate-epp)
  y ananicy-cpp ya prioriza juegos. No se mete por rendimiento.
- Candidatos reales, uno por uno y con números: `render:direct_scanout` (0 hoy;
  en NVIDIA ha dado guerra), `misc:vrr` (0 hoy), tearing en pantalla completa.

### Orden de construcción
1. **Cimientos — HECHO (2026-09-25)**:
   - `lib/catalogo.py` (juegos por el tipo de `appinfo.vdf`, lanzadores, apps;
     imágenes y horas de Steam). En la PC ve 7 juegos y deja fuera Proton,
     runtimes y Wallpaper Engine. Prueba: `tests/unidad/catalogo.sh`.
   - El dock salta los juegos sin renumerar los botones (el clic derecho quita
     la entrada N de `dock-apps.json`). En la PC salieron Minecraft y Soulframe.
   - `modo-gaming.py` + `modo-gaming-tarjeta.py`, atado a `SUPER+G`. Probado en
     anidado de punta a punta (cierra lo que toca, kitty no se deja, efectos
     vuelven como estaban, ganchos on/off). Prueba: `tests/unidad/modo-gaming.sh`.
   - `gaming-on`/`gaming-off` en `waybar-autohide.py` (estado aparte del
     bloqueo: desbloquear a mitad de partida no resucita las barras) y en
     `wallpaper-pause.py`. Pruebas: `barras-gaming.sh`, `fondo-gaming.sh`.
   - Los dos demonios de la PC se relanzaron con el código nuevo y se probaron
     en vivo: las barras se van y vuelven, y el fondo se apaga los 12 s del
     modo y vuelve al salir. Con la pausa en `true` con ventanas abiertas.
   - **Arreglado de paso un fallo viejo de `wallpaper-pause.py`**: resucitaba
     mpvpaper en la vuelta siguiente a matarlo por un juego (también con la
     stoplist), y decidía «hay fondo» por cualquier mpvpaper de cualquier sesión.
2. **La biblioteca — HECHA (2026-09-26)**: `biblioteca.py`, a pantalla
   completa en su escritorio, igual que la maqueta aprobada (fondo del juego con
   fundido, logo, horas, carrusel, pestañas, animación de entrada y de salida),
   con teclado, mando (`lib/mando.py`, sin dependencias) y ratón. Al lanzar un
   juego enseña «Lanzando…» y se cierra sola cuando el juego abre ventana; al
   cerrar el juego el vigilante la vuelve a abrir. Marca con «!» los juegos con
   shaders pendientes en Steam y los lista arriba a la derecha.
   Probado en anidado a 1920x1080 con un juego falso: entrar, diálogo de Steam
   flotando encima, lanzar, volver, salir. La tarjeta ya acepta el mando.
3. **El menú rápido — HECHO (2026-09-26)**: `menu-rapido.py`, capa encima del
   juego. SUPER + la tecla de al lado del 1 (`code:49`, vale en us y en latam),
   Select+Start en el mando (lo vigila el vigilante de `modo-gaming.py`) o X en la
   biblioteca. Juego en curso, música por MPRIS (⏮ ⏯ ⏭, portada), volumen por
   grupos juego/música/chat (`lib/sonido.py`), silenciar micro, overlay,
   captura, tus apps + lanzadores + «Añadir» (fuzzel), otro juego, tus escritorios del
   modo, salir. Rehecho el 2026-09-26: una columna con scroll, como la maqueta. Mientras está abierto el mando es solo suyo
   (EVIOCGRAB). Pruebas: `sonido.sh` y lo nuevo de `modo-gaming.sh`.
4. **Overlay y shaders — HECHO; rendimiento — PENDIENTE (con un juego de verdad)**:
   - Overlay: `modo-gaming.py` genera `~/.cache/celiuz/mangohud.conf` al entrar
     (paleta del repo, barra horizontal, escondido hasta Supr, `control=mangohud`
     para el botón del menú). Visto en anidado sobre `vkcube`. Los juegos de
     Steam lo llevan porque `preparar-steam` relanza Steam con `MANGOHUD=1` si
     corría sin él y no hay ningún juego abierto; la biblioteca y el menú
     lanzan con ese entorno. Solo sale en juegos Vulkan (Proton lo es); un juego
     nativo OpenGL no lo lleva.
   - Shaders: `preparar-steam`, con Steam cerrado, añade
     `unShaderBackgroundProcessingThreads` (núcleos − 2) a `steam_dev.cfg` si
     no lo había, y pone primero en `ProcessingQueue` el último juego jugado.
     **Sin comprobar que Steam respete ese orden**, ni cuánto acortan los hilos:
     hay que medirlo la próxima vez que Steam tenga shaders pendientes.
     Conviene que el usuario mire en Steam > Ajustes > Descargas que esté
     puesto el procesado de shaders en segundo plano.
   - Rendimiento (`direct_scanout`, VRR, tearing): sin tocar. Se mide con un
     juego de verdad y con el usuario delante, uno por uno.
   - **Probado en la sesión real de la PC el 2026-09-26**: entrar y salir con
     los dos vídeos, terminales y Brave ocultos y devueltos a su escritorio,
     barras/fondo/efectos fuera y de vuelta, Steam relanzado con el overlay,
     una terminal al escritorio 2 y vuelta al 1 al cerrarla, no poder ir a un
     escritorio vacío, el menú rápido. Y Supr alterna el overlay en una app
     Vulkan por XWayland (el camino de Proton). **Queda para el usuario**: la
     tarjeta con el mando, jugar de verdad con el overlay, `SUPER` + la tecla
     de al lado del 1 con el teclado real (un teclado virtual no dispara
     atajos con SUPER), y Select+Start.

## Queda por probar a mano (de antes)

- **`grabar.sh` (SUPER+R)**: es la única pieza sin prueba automática. En la PC
  **sí está `wf-recorder`**, así que aquí se puede probar; en la laptop falta
  (`sudo pacman -S wf-recorder`).
- Un `SUPER+S` real, para confirmar que la captura ya no trae el recuadro
  (arreglado el 2026-09-23).
- Los tres clics del módulo Bluetooth, y renombrar uno de los dos TWS, que se
  llaman igual.
- El atajo de modo avión (`XF86RFKill`): sin comprobar a propósito, tumba la
  wifi de la sesión.
- La perilla del teclado de la PC: si emite las teclas de volumen, ya enseña el
  aviso nuevo (el aviso en sí quedó comprobado el 2026-09-25); sin probar con la
  perilla.

## Si algo falla al entrar con Lua

- Sin atajos o con errores: `hyprctl configerrors` dice fichero y línea. Un
  módulo roto no tumba a los demás.
- Para volver a la config vieja en un apuro: renombrar
  `hypr/hyprland.lua` (p. ej. a `hyprland.lua.off`) y cerrar sesión; Hyprland
  coge el `hyprland.conf` del puente. **No borrar nada.**
- Si un script que habla con Hyprland deja de hacer efecto: `hyprctl eval
  'return 1'` dice el modo, y `hypr/scripts/lib/hypr.py dispatch lua workspace 3`
  enseña lo que se le mandaría.
