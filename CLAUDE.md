# Notas para Claude Code

Este repo es el escritorio de Hyprland de Parzival (`Pceliuz/Celiuz_CachyOS`),
sobre CachyOS. **Es público y se usa en más de un equipo**: una PC de sobremesa y
una laptop. Casi todo lo que sigue existe por esa razón.

## La regla de oro

**Nada que dependa de la máquina entra en git.** Se rompió justo por aquí el
2026-08-01: el dock del autor estaba versionado, así que al clonar el repo en la
laptop aparecieron sus 8 aplicaciones —incluidos dos juegos suyos lanzados por
`steam://rungameid/...`— y un `dock-icons.css` con rutas absolutas a
`/home/celiuz/...` que en la otra máquina no existen. Iconos ajenos, tres de
ellos imposibles de funcionar, y un buen rato perdido creyendo que el dock
detectaba las apps recién instaladas.

Ya está en `.gitignore`, pero antes de añadir cualquier fichero nuevo pregúntate
si su contenido sería correcto en el equipo de otra persona:

| No versionar | Por qué |
|---|---|
| `waybar/dock-apps.json` | las apps del dock son de cada equipo |
| `waybar/dock.jsonc` | generado de lo anterior |
| `waybar/dock-icons.css` | generado, con rutas absolutas de iconos |
| `hypr/conf/local.conf` | la terminal de cada equipo, y si es portátil |
| `waybar/local.jsonc` | el lado derecho de la barra: batería solo si hay |
| `hypr/wallpapers/*` | vídeos: pesan y no son redistribuibles |

Los cinco los crea `./instalar.sh`.

Y hay cosas que directamente **no viven en el repo**, por lo mismo:

| Fuera del repo | Qué es |
|---|---|
| `~/.config/celiuzpaper/carpetas.json` | las carpetas de fondos que añadió el usuario |
| `~/.cache/celiuzpaper/lock-*.conf` | fondo y medidas del bloqueo, rehechos en cada bloqueo |

**No cablees `~/dotfiles` en código nuevo.** Saca la raíz de donde está tu propio
fichero: `BASH_SOURCE` en bash, `__file__` en Python. Lo destapó una prueba: con
un `$HOME` de mentira, `gen-dock.py` acabó escribiendo en el repo **de verdad**
porque resolvía `~/dotfiles/waybar`.

**Ya está hecho (2026-08-03).** No queda ninguna ruta cableada en código: los
`.conf` se referencian por `$HOME/.config/hypr/...` —el enlace que crea
`instalar.sh`, que vale se clone el repo donde se clone— y los scripts sacan su
raíz de `realpath(__file__)` o de `readlink -f "$BASH_SOURCE"`. Lo de `realpath`
y no `abspath` importa: a estos scripts se les llama por `~/.config/hypr/...` y a
CeliuzPaper por `~/.local/bin/`, y hay que atravesar el enlace para llegar al
repo.

**`tests/unidad/portabilidad.sh` es el cerrojo**: falla si alguien vuelve a
escribir `$HOME/dotfiles` en código, y dice fichero y línea. Los comentarios sí
pueden mencionarlo.

**Ni se te ocurra "arreglar" esto detectando la máquina al instalar y escribiendo
un fichero.** Lo que depende del equipo se pregunta EN CALIENTE: la pantalla con
`lib/pantalla.py`, la terminal y el navegador con `lib/apps.py`, la carpeta de
vídeos con `wallpapers.carpeta_videos()`. Un valor detectado en la instalación se
queda viejo en cuanto cambias de monitor o de predeterminado, y encima falla en
silencio.

### La única excepción: portátil o sobremesa (`lib/maquina.py`)

Y conviene entender por qué es excepción, para no usarla de coartada.

La regla de arriba se sostiene en **que el dato cambia**: enchufas un proyector,
cambias de terminal por defecto, mueves la carpeta de vídeos. **El chasis no
cambia.** Un portátil no amanece siendo un sobremesa, así que preguntarlo en cada
arranque no compra nada.

Y encima no había alternativa: hyprlang **no tiene condicionales**. No se puede
escribir «carga esto solo si...» dentro de un `.conf`, y la decisión de qué
`source` se lee tiene que tomarla alguien de fuera.

Lo que sí se respeta del espíritu de la regla:

- `lib/maquina.py` se puede preguntar en caliente, y dice **por qué** ha decidido
  lo que ha decidido. Lo generado es solo el cableado, no el conocimiento.
- El motivo queda escrito dentro del `local.conf` generado, así que un fallo de
  detección se diagnostica leyendo el fichero.
- No falla en silencio: `./instalar.sh --revisar` dice siempre qué equipo ve.

El único modo de fallo real es **mover el disco de un equipo a otro sin volver a
pasar el instalador**. Es el mismo trato que ya tiene el dock, y está escrito en
el README.

Si alguna vez necesitas algo parecido, la pregunta que decide es: *¿este dato
puede cambiar sin que se reinstale?* Si puede, va en caliente y no se discute.

## Generado vs. escrito a mano

Varios ficheros llevan `GENERADO — NO EDITAR` en su cabecera. Va en serio: al
editarlos a mano el cambio se pierde en la siguiente regeneración.

| Generado | Lo escribe | Desde |
|---|---|---|
| `waybar/dock.jsonc`, `waybar/dock-icons.css` | `hypr/scripts/gen-dock.py` | `waybar/dock-apps.json` |
| `waybar/colores.css`, `mako/colores`, `sddm/celiuz/Colores.qml` | `hypr/scripts/gen-colores.py` | `hypr/conf/colores.conf` |
| `hypr/conf/local.conf` | `instalar.sh` | `lib/apps.py` (terminal) y `lib/maquina.py` (portátil o sobremesa) |
| `waybar/local.jsonc` | `instalar.sh` | `waybar/derecha.jsonc` + `lib/maquina.py` |
| `~/.cache/celiuzpaper/lock-medidas.conf` | `hypr/scripts/lock.sh` | `lib/pantalla.py` |

Ese último es la excepción que confirma la regla: `hyprlock.conf` trae **también**
sus propios valores por defecto y el generado solo los pisa. Si el fichero no
existe, hyprlock se queja del `source` pero dibuja igual. Con las medidas solo en
el generado, un fallo al medir dejaría la config llena de variables sin definir —
y quedarse sin pantalla de bloqueo es lo peor que puede pasar en este repo.

## Nada de apps concretas cableadas

El repo no debe dar por hecho que hay kitty, Brave o Steam. Si necesitas la
terminal o el navegador, pregúntaselo a `hypr/scripts/lib/apps.py`:

```sh
hypr/scripts/lib/apps.py terminal            # imprime el comando
hypr/scripts/lib/apps.py navegador --json    # label, cmd, icon_name
```

- El navegador sale de `xdg-settings` / `xdg-mime`. **`$BROWSER` miente**: en
  CachyOS viene puesta a `firefox` de fábrica aunque el predeterminado sea otro.
  Por eso se mira la última.
- La terminal no tiene estándar equivalente: va por `$TERMINAL` y luego una lista
  de conocidas.

Para lanzar cosas:

- `hypr/scripts/lanzar.sh <cmd>` — apps del dock y binds. Mete la app en su
  propio scope de systemd y avisa por notificación si no está instalada.
- `hypr/scripts/terminal.sh <clase> <cmd>` — ventanas flotantes (btop, nmtui, el
  aviso de recarga). Cada terminal nombra la opción de clase distinto y la tabla
  está solo ahí. La clase no es decorativa: es lo que activa `windowrules.conf`.
  Con `--sin-uwsm` delante se salta el prefijo de systemd, para quien ya lo pone.

Una app del dock con `Terminal=true` en su `.desktop` sale por los dos a la vez:
`dock-manager.py` le pone `terminal.sh --sin-uwsm dock-term` delante al añadirla,
y `gen-dock.py` antepone `lanzar.sh` al generar. El `--sin-uwsm` es obligatorio
ahí: sin él saldrían dos scopes de systemd anidados. La clase `dock-term` no
tiene windowrule a propósito — sale en mosaico, como cualquier otra app del dock.

`fuzzel/fuzzel.ini` lo llama por `terminal=celiuz-terminal --sin-uwsm
fuzzel-term`, un enlace a ese mismo script que `instalar.sh` deja en
`~/.local/bin`. Va por el PATH y no por ruta a propósito: **fuzzel no expande `~`
ni `$HOME`** en esa opción. Y el `include=` de fuzzel tampoco vale para sacar la
línea a un fichero generado: si el fichero incluido no existe, fuzzel **sale con
1 y no abre el lanzador** (Hyprland, en cambio, solo avisa).

## La pantalla de inicio de sesión (SDDM) es territorio aparte

`sddm/celiuz/` es lo único del repo que **pide root** y lo único que se ejecuta
**fuera de tu sesión**. Las reglas cambian ahí dentro:

- **Lo que se ve al arrancar es una COPIA** en `/usr/share/sddm/themes/celiuz`.
  Editar el QML del repo no cambia nada hasta pasar `./instalar.sh --sddm`. Es
  el error de bucle más fácil de cometer: tocas, pruebas, no cambia, y te vuelves
  loco.
- **El greeter corre como el usuario `sddm`**, que no puede entrar en
  `/home/<tú>` (está a 700). Nada de rutas a tu carpeta: el fondo se copia dentro
  del tema, y por eso no se actualiza solo al cambiar de wallpaper.
- **Se instala aparte a propósito.** El resto del repo no pide contraseña nunca y
  así debe seguir. `sddm_estado()` solo informa en la instalación normal.
- **La función de bash NO se llama `sddm`**: se llama `sddm_instalar`, porque
  `command -v sddm` encontraría la función en vez del programa y la comprobación
  de "¿está instalado SDDM?" diría que sí hasta en un equipo sin él.
- **Se escribe un drop-in en `/etc/sddm.conf.d/`, nunca `/etc/sddm.conf`**: ese
  fichero puede tener cosas del usuario (aquí tenía un autologin a medias). Ojo:
  un `Current=` en `/etc/sddm.conf` **gana** sobre el drop-in, y entonces el tema
  se instala y no se ve. El instalador lo comprueba y avisa.
- **Probar es gratis y hay que hacerlo**: `sddm-greeter-qt6 --test-mode --theme
  <ruta>` abre una ventana normal. Un tema roto deja el arranque sin pantalla; se
  sale por `Ctrl+Alt+F2` y borrando el drop-in.

## Trampas comprobadas (no las redescubras)

- **Un `import` que falla en QML tumba el fichero ENTERO**, no solo esa línea. Si
  `import QtMultimedia` estuviera en `Main.qml`, un equipo sin `qt6-multimedia`
  se quedaría sin pantalla de inicio de sesión —negra, sin campo de contraseña—
  y sin más salida que un TTY. Por eso el vídeo vive solo en `FondoVideo.qml` y
  entra por un `Loader`: así lo peor que pasa es que el fondo caiga al fotograma.
  **Cualquier import nuevo que pueda faltar va en su propio fichero.**
- **`Qt.formatDate(fecha, "dddd")` NO respeta el idioma del sistema.** Con un
  formato propio usa siempre los nombres en inglés. Medido dentro del greeter
  enseñando las dos cosas juntas: `Qt.locale().name` decía `es_MX` y la misma
  línea salía `Monday · 03 de August`. Hay que pasar el locale a mano, y eso solo
  lo admite `toLocaleDateString(Qt.locale(), formato)`.
- **En QML el alfa va DELANTE (`#AARRGGBB`); en los `.conf` de hyprlang va detrás
  (`RRGGBBAA`).** Son ocho hex en los dos y ninguno se queja del otro: darle a QML
  un `RRGGBBAA` no da error, pinta otro color con otra transparencia. Por eso
  `gen-colores.py` emite los opacos como `#RRGGBB`, que no tiene ambigüedad.
- **`Component.onCompleted` llega antes que las propiedades que pone un `Loader`
  asíncrono.** El vídeo del greeter no arrancaba porque el `play()` estaba ahí y
  la ruta se asignaba después, en `onLoaded`: el fichero se abría (ffmpeg lo
  anunciaba en el diario) pero `playbackState` nunca pasaba a `Playing`. Va en
  `onSourceChanged`.
- **`userModel.lastUser` viene vacío si nunca ha entrado nadie.** En un equipo
  recién instalado eso dejaría la pantalla pidiendo la contraseña de nadie. El
  primer delegado de la lista rellena el hueco, y si no hay ninguna cuenta sale
  un campo para escribirla.

- **`ln -sfn origen ~/.config/hypr` no sirve** si `~/.config/hypr` ya existe como
  carpeta real: crea el enlace *dentro* (`~/.config/hypr/hypr`) y la config no se
  despliega, **sin dar ningún error**. En CachyOS esa carpeta existe. Por eso hay
  instalador y no cuatro `ln` en el README.
- **`hyprland.lua` gana a `hyprland.conf`.** Hyprland 0.56 lo busca primero y
  CachyOS trae el suyo en Lua. Si reaparece, esta config queda ignorada en
  silencio. `instalar.sh` avisa.
- **`source` con ruta RELATIVA no funciona en hyprlang, y falla en silencio.**
  `source = conf/trozo.conf` desde `hyprland.conf` no carga nada: las variables
  del fichero quedan sin definir y **`configerrors` sale vacío** (medido en un
  anidado: el valor se quedó en el de fábrica). Los `source` van con ruta
  absoluta. La buena es `$HOME/.config/hypr/...`, que vale se clone el repo
  donde se clone, porque ese enlace lo crea `instalar.sh`.
- **`hyprctl reload` no basta** para probar cambios de `exec-once`: solo corren al
  arrancar la sesión. Y si la sesión arrancó desde un `.lua`, `reload` no cae de
  vuelta al `.conf`.
- **Un `bindr` sobre una tecla modificadora LLEVA ESE MODIFICADOR DELANTE.** En
  el instante en que sueltas `SUPER_L`, Hyprland todavía cuenta SUPER dentro del
  modmask, así que `bindr = , SUPER_L` (modmask 0) **no coincide jamás**. Y no
  avisa nadie: se carga sin error y sale en `hyprctl binds` como cualquier otro,
  solo que nunca dispara. Lo bueno es `bindr = SUPER, SUPER_L`. Medido el
  2026-08-04 con tres binds a la vez, uno por forma: de diez pulsaciones, las
  diez las cogió la forma con modificador y cero la forma sin él. El modmask
  tiene que coincidir **exacto**, así que soltar SUPER con SHIFT aún pulsado es
  un caso distinto y necesita su propia línea.
- **Y aun así, un `bindr` sobre `SUPER` casi no dispara si SUPER venía en un
  combo.** En el diario de la sesión real disparó 2 de 10 veces, y las dos
  pulsando SUPER sola; con `SUPER+TAB` no dispara. O sea que **no se puede
  construir un gesto de "suelta el modificador" solo con `bindr`**.
- **El evento de soltar una tecla se PIERDE del todo mientras una capa
  `EXCLUSIVE` está cogiendo el teclado.** Ni lo ve el cliente por GTK (aún no
  tiene el teclado) ni lo ve el `bindr`. Son ~185 ms en los que no se entera
  nadie. Si necesitas saber si una tecla sigue pulsada, **pregúntaselo al
  kernel** con `hypr/scripts/lib/teclas.py` (`EVIOCGKEY`: es estado, no una cola
  de eventos), que cuesta 0,11 ms y no depende del foco. Requiere estar en el
  grupo `input`, y por eso devuelve `None` —no `False`— cuando no puede mirar:
  en otra máquina, confundir "no lo sé" con "no está pulsada" rompe el gesto
  entero. Mirar todos los `/dev/input/event*` cuesta 170 ms porque los que no son
  teclados tardan 4-11 ms en abrirse; hay que filtrarlos.
- **A GTK no le preguntes por los modificadores**:
  `Gdk.Keymap.get_modifier_state()` devuelve siempre `0x4000040` en esta sesión,
  con el bit de SUPER puesto aunque no la toque nadie. No es el estado en vivo,
  es el mapa de qué bit le corresponde.
- **Para validar config sin arriesgar la sesión viva**, `tests/anidado.sh`:
  ```sh
  ./tests/anidado.sh hyprctl configerrors   # levanta, ejecuta y recoge
  ./tests/anidado.sh                        # se queda abierto; Ctrl+C lo tumba
  ```
  **No levantes Hyprland a pelo para esto.** Un anidado suelto NO es un cajón de
  arena: usa TU `$HOME`, así que corre TU `autostart.conf`, y ahí hay
  `exec-once` que muerden a la sesión de fuera. El peor es `wallpaper.sh`, que
  empieza con `pkill -x mpvpaper` y `pkill -f wallpaper-paus[e].py` —matan por
  NOMBRE, sin mirar de qué sesión es cada proceso—, así que te deja el
  escritorio real **sin fondo y sin el demonio que lo pausa**; y los
  `systemctl --user` de hypridle y mako manosean las unidades de verdad. Pasó el
  2026-08-04 y el síntoma no apareció hasta horas después.
  El script aísla lo que se puede aislar: `$HOME` desechable (que es lo que
  redirige el árbol entero, porque el repo se referencia por
  `$HOME/.config/hypr/...`), una copia del repo enlazada igual que la enlaza
  `instalar.sh`, `autostart.conf` vaciado, `$XDG_RUNTIME_DIR` propio, y al salir
  barre los procesos que se quedaron con la firma de esa instancia y borra la
  casa. Lo que **no** puede aislar es un `pkill` por nombre que lances tú a mano
  ahí dentro.
  Si ya levantaste uno a pelo: mira `pgrep -af mpvpaper` y el demonio, y
  levántalos otra vez con `hypr/scripts/wallpaper.sh`.
  `AQ_BACKENDS`, no `WLR_BACKENDS`: desde 0.5x el backend es aquamarine y la
  variable de wlroots la ignora en silencio. Sobre esta NVIDIA hace falta además
  `AQ_NO_MODIFIERS=1` o se queda en `bo null` sin monitor.
- **libwayland se APROPIA de un socket que no tenga su `.lock` al lado**: lo
  borra y se pone en su sitio. Se descubrió montando el anidado: el enlace al
  socket del padre se llamaba `wayland-1`, igual que fuera, y el compositor
  anidado lo hizo desaparecer y llamó `wayland-1` a su propio display — o sea
  que el nombre de dentro y el de fuera pasaban a ser el mismo, que es la mejor
  manera de creer que apuntas a un sitio mientras apuntas al otro. Por eso el
  enlace se llama `wayland-padre`.
- **`HYPRLAND_INSTANCE_SIGNATURE` NO mete un programa gráfico en el anidado.** Esa
  variable solo le dice a `hyprctl` con quién hablar; un cliente Wayland elige
  compositor por **`WAYLAND_DISPLAY`** y por nada más. Lanzar algo con solo la
  primera es creer que apuntas al anidado mientras apuntas a la sesión real —
  así se bloqueó la pantalla del autor el 2026-08-03, con `lock.sh`. La señal
  que lo delata está en el diario: `Configuring surface for logical [1920, 1080]`,
  el tamaño de la pantalla de verdad y no la del anidado.
  **Comprueba la puntería con algo inofensivo antes de lanzar nada serio**: abre
  una terminal con ese `WAYLAND_DISPLAY` y mira que sale en
  `hyprctl -i "$INST" clients` y **no** en `hyprctl clients`.
- **Una ventana normal se dibuja POR DEBAJO de una capa `OVERLAY`.** Un diálogo
  abierto desde una app que es capa a pantalla completa (CeliuzPaper) queda
  detrás y parece que la app se colgó. Hay que esconder la capa (`hide()`)
  mientras dure y volver a mostrarla después; y soltarle el teclado, porque una
  capa en modo `EXCLUSIVE` no deja escribir al diálogo.
- **En hyprlock, un `shape` más grande que la pantalla no se recorta: se
  reescala.** El velo del bloqueo tenía `size = 1920, 1080` escrito a mano y en
  la laptop (1366x768) salía un rectángulo de 1089x612 pegado a la esquina
  superior izquierda —el 63% de la pantalla— con un escalón visible entre la
  parte oscurecida y la clara. En el sobremesa no se notaba porque allí el
  número coincidía con la resolución. Lo que va a pantalla completa se pone en
  **porcentaje** (`size = 100%, 100%`), que hyprlock mide contra la salida.
- **Un toggle perdido invierte las barras para siempre.** waybar solo ofrece
  SIGUSR1 (alternar), así que un estado *recordado* que se desvíe una vez deja
  las barras al revés: puestas con apps abiertas y escondidas con el escritorio
  vacío. Pasaba al desbloquear la pantalla: `recomponer()` manda `unlock` —que
  relanza waybar— y vuelve al escritorio con ventanas **en el mismo instante**,
  así que la señal de ocultar salía cuando waybar aún no tenía superficie y se
  perdía. En el sobremesa waybar arrancaba a tiempo y por eso allí no se veía;
  en la laptop se reprodujo 3 de 3. Por eso `update()` lee la capa REAL con
  `j/layers` (`top` = puesta, `bottom` = escondida) en vez de recordarla: si una
  señal se pierde, el ciclo siguiente lo corrige solo. **No vuelvas a un estado
  recordado**, por barato que parezca.
- **waybar se traga el stderr de los `on-click`.** Un fallo ahí no deja rastro en
  el journal; por eso los lanzadores notifican.
- **ffmpeg elige el formato de salida POR LA EXTENSIÓN.** Un temporal llamado
  `fondo.jpg.nuevo` termina en `.nuevo` y ffmpeg responde *«Unable to choose an
  output format»* sin escribir nada. La extensión real va **al final**:
  `fondo.nuevo.jpg`. Ha mordido **dos veces** en este repo —la pantalla de
  bloqueo (`lock-bg.tmp.jpg`) y el fondo del login—, y las dos veces con el
  stderr silenciado, así que el síntoma fue «no pasa nada».
- **Para que un servicio del sistema lea un fichero tuyo, carpeta compartida con
  setgid — no aflojes los permisos de `$HOME` ni pongas un NOPASSWD.** El
  greeter de SDDM corre como el usuario `sddm` y no puede entrar en `/home/tu`
  (está a 700). La solución del repo es `/var/lib/sddm-celiuz` en modo **2750**,
  de tu usuario y del grupo del servicio: **el setgid hace que lo que crees
  dentro nazca con ese grupo**, y con eso el servicio lee y tú escribes sin
  privilegios. Sin el setgid los ficheros nacen con TU grupo y el servicio se
  encuentra un permiso denegado que no verás por ningún lado. Se monta una sola
  vez desde `instalar.sh --sddm`; después, cero sudo.
- **mako se traga igual los errores de `on-notify`.** Si el comando del sonido
  falla, no sale por ningún lado: te quedas sin sonido y sin nada que mirar. Por
  eso `hypr/scripts/sonido-notificacion.sh` tiene `--revisar`, y por eso no se
  cablea el reproductor ni el fichero como sugiere el manual de mako.
- **`on-notify` SE DISPARA con `invisible=1`.** O sea que el modo «no molestar»
  esconde la notificación pero **ejecuta el comando igual**: sin más, el modo
  silencioso sonaría en cada aviso, que es lo peor de los dos mundos porque
  además no ves qué llegó. La sección `[mode=no-molestar]` tiene que anularlo
  con `on-notify=none` — eso sí funciona. Las dos cosas están comprobadas.
- **`uwsm app -- inexistente` sale con 1 y notifica**, no falla en silencio. Si lo
  mides con `| head`, el `$?` que ves es el de `head`, no el de uwsm.
- **`fc-list | grep -q` con `set -o pipefail` da falso negativo**: `grep -q` cierra
  la tubería, `fc-list` muere por SIGPIPE y el pipeline devuelve fallo aunque
  hubiera coincidencia. Guarda la salida en una variable.
- **`pkill -f 'wallpaper-pause.py'` puede matar al propio shell** que lo lanza, si
  su línea de comandos contiene esa ruta. Mata por PID. Le pasaba al atajo
  `SUPER+SHIFT+C`, que por eso ahora usa `waybar-autohide.py --reiniciar`.
- **git borra los ficheros ignorados si vienen de un commit anterior.** Al
  cambiar a una rama donde `waybar/dock-apps.json` todavía estaba versionado,
  git lo sobrescribe con la versión del repo sin avisar (es "ignorado", no
  "sin seguimiento"); y al volver, lo borra del disco. Con él se va el dock del
  equipo. **Cópialos aparte antes de cualquier `checkout`, `merge`, `pull` o
  `stash` que cruce el commit `ef7a528`.** Pasó de verdad el 2026-08-01, en la
  laptop, después de haberlo documentado como riesgo para la otra máquina.
- **Si desaparece `$XDG_RUNTIME_DIR/waybar-autohide.fifo`, el escritorio se
  queda medio mudo**: seis piezas mandan órdenes por ahí (las dos
  líneas-tirador, `SUPER+C`, el panel de calendario, el gestor del dock y la
  pantalla de bloqueo) y `echo x > ruta-sin-fifo` **crea un fichero normal y
  sale con 0**, así que todas fallan calladas. El demonio ahora lo rehace solo
  cada segundo; para diagnosticarlo,
  `ls -l /proc/<pid>/fd` marca `(deleted)` el descriptor huérfano.
- **Un demonio que sobrevive a SU Hyprland es peor que no tener ninguno**, y el
  síntoma no se parece en nada a la causa. `wallpaper-pause.py` nace con
  `setsid` y fija su instancia al arrancar, así que un compositor muerto lo deja
  girando contra un socket que ya no contesta. Y estorba: `wallpaper.sh`
  pregunta «¿hay demonio?» con un `pgrep` **por nombre**, el zombi contesta que
  sí, y la sesión viva se queda sin nadie que pause el fondo — encima el FIFO de
  órdenes también es suyo, así que los `hold` y `release` del bloqueo y de
  CeliuzPaper se los traga sin leerlos. Lo que se ve es un demonio que parece ir
  al revés: el vídeo corriendo con ventanas encima, y quieto en el bloqueo.
  Ya no puede pasar —tras `ABANDONO` segundos sin poder hablar con Hyprland el
  demonio se va solo, y `tests/unidad/fondo-huerfano.sh` lo vigila—, pero el
  diagnóstico vale para cualquier otro: mira
  `tr '\0' '\n' < /proc/<pid>/environ | grep HYPRLAND_INSTANCE_SIGNATURE` y
  compáralo con el de tu sesión. **«Existe la carpeta de la instancia» NO sirve
  para saber si vive**: Hyprland no siempre la limpia al irse.

## Las pruebas

```sh
./tests/run.sh              # todas
./tests/run.sh bloqueo      # solo las que lleven ese texto en el nombre
```

No necesitan Hyprland corriendo, ni Steam, ni un monitor concreto: cada una se
monta un `$HOME` de mentira. Valen desde un TTY o en integración continua.

`tests/anidado.sh` es la excepción y **no es una prueba, es una herramienta**:
levanta un Hyprland de verdad, así que pide una sesión Wayland de fuera donde
dibujarse y por eso `run.sh` no lo recoge (solo mira `tests/unidad` y
`tests/e2e`). Es lo que hay que usar para todo lo que necesite un compositor
—`configerrors`, aspecto, capturas—, y el porqué está arriba, en las trampas.

**Las dos reglas al escribir una prueba nueva:**

1. **Nada de tocar la sesión ni la config reales.** `preparar_entorno` (en
   `tests/lib/comun.sh`) crea un HOME desechable y redirige los `XDG_*`. Termina
   siempre con `afirmar_intacta_la_casa_real`, que compara una huella de
   `~/.cache/celiuzpaper` antes y después.
2. **Lo peligroso se sustituye por un binario falso**, con `binario_falso`. Deja
   en el `PATH` un ejecutable que solo apunta sus argumentos, y después se
   comprueba que se le llamó bien. Así `tests/e2e/bloqueo.sh` verifica la
   secuencia entera de la pantalla de bloqueo **sin bloquear nunca**, y
   `tests/e2e/fondo.sh` prueba `wallpaper.sh` con un `pkill` falso — ese script
   empieza matando mpvpaper, y ejecutarlo de verdad en una prueba te dejaría sin
   fondo.

Lo que **no** cubren: el aspecto. Que una capa GTK se dibuje donde toca o que un
icono salga centrado sigue necesitando un Hyprland anidado y una captura.

Cuidado con lo que ya mordió: los generadores sacan su destino de la ruta de su
propio `.py`, así que una prueba que los ejecute reescribe el repo de verdad. Usa
`copiar_repo`, que deja una copia entera en el temporal.

## Antes de dar algo por terminado

1. `./tests/run.sh` en verde.
2. `./instalar.sh --revisar` no debe sacar avisos inesperados.
3. `hyprctl configerrors` vacío.
4. Si tocaste el dock: `hypr/scripts/gen-dock.py list` — ninguna app debe salir
   `[NO INSTALADA]`.
5. Si tocaste el fondo: comprueba que el demonio está vivo, que es **de esta
   sesión** (`tr '\0' '\n' < /proc/<pid>/environ | grep HYPRLAND_INSTANCE_SIG`)
   y que `pause` sigue a `True` con ventanas abiertas.
6. Si tocaste el tema de SDDM: `sddm-greeter-qt6 --test-mode --theme <ruta>` y
   míralo de verdad. Y pruébalo **también sin `fondo.mp4` y sin `fondo.jpg`**,
   que es como llega a quien clona el repo.
7. Si tocaste el teclado o `conf/teclado-laptop.conf`: `Hyprland --verify-config`
   con `$conf_maquina` apuntando **a los dos sitios**, no solo al de esta caja.
   Es lo único que prueba el camino de la máquina que no tienes delante.
8. Prueba pensando en **la otra máquina**, no solo en esta.

## Cómo subir cambios

Historia lineal sobre `main`, mensajes en español y en presente, describiendo el
efecto y no el fichero tocado (`El gestor del dock no veía las apps de Flatpak de
usuario`, no `fix dock-manager.py`).

```sh
git status --short          # que no se cuelen los ficheros generados
./instalar.sh --revisar     # que siga instalando limpio
git add -p
git commit
git push origin main
```

Al traer cambios en el otro equipo: `git pull && ./instalar.sh`. El instalador es
idempotente y no toca el `dock-apps.json` que ya tengas.
