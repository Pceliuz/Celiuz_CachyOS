# Por dónde seguir

Notas para retomar el trabajo sin reconstruir el contexto. Si esto se queda
viejo, mandan el `README.md` y el `CLAUDE.md`. Las crónicas de sesiones
anteriores, con todo lo medido, están en **`HISTORIAL.md`** (antes vivían aquí y
el fichero llegó a 1238 líneas).

Última sesión: **2026-09-25**, primero en el **portátil** y luego en la **PC**.

---

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
| Overlay | `Delete` (es `DEL` y es `Supr`: el mismo keysym), atrapado por Hyprland y mandado con `mangohudctl` |

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
