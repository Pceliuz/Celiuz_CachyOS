# Por dónde seguir

Notas para retomar el trabajo sin tener que reconstruir el contexto. Si esto se
queda viejo, manda el `README.md` y el `CLAUDE.md`.

Última sesión: **2026-08-05**, en el **portátil** (lo último se subió el
**2026-08-07**; las fechas de cada apartado son las de cuando se midió). Fue una
auditoría de «¿esto vale para quien clone el repo?», que sacó tres cosas que la
adaptación anterior no había cubierto: la distribución del teclado —la laptop
escribía con la de la PC—, ocho rutas cableadas a `~/dotfiles` en ficheros que el
cerrojo no miraba, y el sensor de temperatura de la barra, que seguía siendo el
del Ryzen de la PC. Antes, el supervisor de las barras y el perfil de teclado de
portátil para todos los teclados.

## Lo primero al abrir el repo

```sh
./tests/run.sh          # 12 pruebas. Deben salir todas
./instalar.sh --revisar # no debe sacar avisos inesperados
hyprctl configerrors    # vacío
```

Si las pruebas fallan **antes** de tocar nada, eso es lo que hay que arreglar
primero: significa que algo del sistema cambió por debajo (una actualización de
Hyprland, de mpv o de waybar).

---

## El reinicio del 2026-08-03: cerrado

Se reinició para estrenar de golpe la pantalla de SDDM, lo que vino de la PC y la
detección de portátil. Salió, y está subido: `ee3b726` (SDDM) y `8709245`
(teclado según la máquina) están en `origin/main`, que era el último paso de
aquella lista. La lista se ha borrado de aquí; si hiciera falta, está en el
historial de este fichero.

Lo único que sigue igual son las dos cosas que se dejaron sin comprobar **a
propósito**, y que siguen abajo, en «Lo siguiente»: el bind de modo avión y la
perilla del X820.

## Lo último: la laptop escribe con SU teclado (2026-08-05, portátil)

Lo pilló el usuario: se había arreglado `kb_options` (el Ctrl derecho) pero **no
la distribución**. La laptop arrancaba en `us(altgr-intl)` —la del teclado ANSI
del autor— cuando su teclado está serigrafiado en **latam**, así que la `ñ`, los
acentos y los símbolos salían donde no toca y había que corregir con `SUPER+DEL`
en cada sesión.

Ahora, en un portátil, la distribución sale de `/etc/vconsole.conf`: lo que se
contestó al instalar la distro, que en un portátil es de fiar porque se respondió
tecleando en el teclado interno. Queda `latam,us` con variante `,altgr-intl`.

**La trampa, y está en el `CLAUDE.md`: en un sobremesa esa fuente miente.** El
`/etc/vconsole.conf` de la PC también dice `latam` y su teclado es un ANSI us
—se eligió latam al instalar y se cambió de teclado después—, así que un
sobremesa NO la mira y conserva la del autor. Comprobado forzando esa rama sobre
una copia del repo: sigue dando `us,latam` y `altgr-intl,`, o sea que **al pasar
`./instalar.sh` en la PC no cambia nada**.

El valor viaja por `$kb_layout` / `$kb_variant`: valor de fábrica en
`hyprland.conf` (antes del `source` de `local.conf`, para que un clon sin
instalar no se coma un error de hyprlang por una variable sin definir) y lo pisa
el generado `local.conf`, editable a mano.

Verificado en la sesión viva tras `hyprctl reload`: el teclado interno **y el
USB** salen con `l "latam,us"`, índice 0 y `active keymap: Spanish (Latin
American)`, con `o ""`. Lo cubre `tests/unidad/maquina.sh` (46 comprobaciones),
que prueba las dos ramas y los casos raros: valores entre comillas, un portátil
ya instalado en `us`, y una caja sin `/etc/vconsole.conf`.

## Antes: lo que la adaptación no había cubierto (2026-08-05, portátil)

Se auditó el repo entero preguntando «¿esto vale para quien lo clone?», no solo
el cambio de la sesión. Salieron dos cosas, las dos venidas de la PC.

**1. Ocho rutas cableadas a `~/dotfiles`, en ficheros que el cerrojo no miraba.**
`waybar/config.jsonc` tenía siete (los `on-click` de btop y nmtui, el `exec` del
módulo de notificaciones y el del panel de calendario) y `mako/config` una (el
`include=` de los colores). Clonar el repo en otra ruta dejaba esos clicks
muertos, el módulo de notificaciones vacío y mako sin colores, **en silencio**.

Se coló porque `tests/unidad/portabilidad.sh` **solo escaneaba `.conf`, `.sh` y
`.py`**: los `.jsonc` y los ficheros sin extensión le eran invisibles. El
vigilante tenía el mismo agujero que el código vigilado. Ahora mira todo fichero
de texto menos la documentación, y se comprobó al revés: con el cerrojo nuevo y
el código viejo, falla y lista las ocho. La ruta buena es `$HOME/.config/...`,
el enlace que crea `instalar.sh`.

**2. El sensor de temperatura era el de la PC.** `config.jsonc` llevaba a mano
`"hwmon-path-abs": "/sys/devices/pci0000:00/0000:00:18.3/hwmon"` — el k10temp del
Ryzen 5 5500. Este portátil es un Intel i5-8250U y esa ruta **no existe**, o sea
que el módulo llevaba tiempo sin poder leer nada.

Se arregló con el patrón que ya usaba la batería: `hypr/scripts/lib/sensores.py`
lo averigua en caliente y `instalar.sh` escribe la ruta en `waybar/local.jsonc`,
que no se versiona. Lo que se ve (formato, iconos, umbral) vive en
`waybar/sensores.jsonc`, versionado, que además es la red de seguridad si falta
el generado. **`temperature` ya no puede estar en `config.jsonc`**: en waybar
gana el primero que define una clave, y el que incluye va antes que el incluido.

Verificado con captura (`grim`): la barra marca **42 °C** leyendo el `coretemp`
de esta caja. Y `tests/unidad/sensores.sh` prueba las dos familias de CPU con un
`/sys` de mentira —contra el de verdad solo se vería la de esta máquina— y falla
si alguien vuelve a escribir la ruta de un sensor en un `.jsonc` versionado.

**Trampa que costó las barras, y está en el `CLAUDE.md`:**
`waybar-autohide.py --reiniciar` no es un comando que termina, **se convierte en
el demonio**. Lanzarlo desde un shell que espera y que algo lo mate por tiempo
deja el escritorio sin barras y sin FIFO. Se levanta con
`setsid nohup ... >/dev/null 2>&1 </dev/null &`.

## Antes: las barras que no volvían, y el teclado (2026-08-05, portátil)

**`SUPER+SHIFT+C` ya no deja el escritorio sin barras.** Eran dos fallos:

1. **El demonio se suicidaba.** El bucle acababa en
   `if not all(bar.alive()): cleanup()`, así que **una** waybar caída mataba a
   las otras tres y al propio demonio — y ya no quedaba nadie que las levantara,
   ni el atajo de reinicio, que empieza hablando con él. Había que cerrar sesión.
   Medido: matando una sola de las cuatro, a los 4 s no quedaba ninguna capa
   waybar viva. Ahora `Bar.supervisar()` relanza la pareja caída; si se cae 5
   veces en un minuto se rinde con una notificación, y la otra barra sigue.
2. **Tras reiniciar quedaban escondidas.** `Bar.__init__` nacía con
   `manual = False` mientras `relanzar()` lo ponía a `True`, así que con apps
   abiertas las barras nuevas se escondían en el primer ciclo y el atajo parecía
   servir sólo para hacerlas desaparecer. Ahora nacen «sacadas a mano»: se ven
   ~1,5 s y luego se ocultan como siempre. Al arrancar la sesión no cambia nada,
   porque el escritorio está vacío.

Lo cubre `tests/unidad/barras-supervisor.sh`, y **la prueba se comprobó contra el
código viejo**: fallan 4 de sus 11 afirmaciones.

**Y el perfil de teclado de portátil ya vale para TODOS los teclados.** Estaba en
un `device { name = at-translated-set-2-keyboard }`, que sólo rescataba el
teclado interno: un teclado USB enchufado al portátil seguía perdiendo su Ctrl
derecho, igual que `video-bus` y `power-button`. Ahora se vacía `kb_options` en
el bloque `input {}` global de `conf/teclado-laptop.conf` — que es el último
fichero que lee `hyprland.conf`, así que gana. Nuevo en el detector:
`maquina.py teclado` (`completo` / `sin-altgr`) y `maquina.py motivo`.

El **NumLock se dejó como estaba a propósito**: en un portátil con teclado
numérico de verdad, `true` es lo que quiere cualquiera. El porqué está escrito en
`conf/teclado-laptop.conf`.

Comprobado, además de las pruebas: `hyprctl devices` dentro del anidado con los
dos perfiles (portátil da `kb_options` vacío, sobremesa da `lv3:switch`), y
`Hyprland --verify-config` limpio apuntando a los dos sitios.

Y comprobado también **en la sesión viva del portátil**, que es la prueba que de
verdad cierra el asunto: los **cinco** teclados de `hyprctl devices` salen con
`o ""`, incluido `usb-optical-mouse--keyboard` —un teclado USB, justo el que el
`device {}` de antes dejaba fuera— además de `ideapad-extra-buttons`,
`video-bus` y `power-button`.

**Y el sobremesa ajeno ya está avisado.** Quien clone el repo en un sobremesa se
queda con el perfil `sin-altgr`, que es el teclado del autor, y perdía el Ctrl
derecho sin que nada se lo dijera. No se detecta solo a propósito (un teclado se
enchufa y se desenchufa; `kb_options` se lee al arrancar), así que se avisa por
los tres sitios donde se mira: `./instalar.sh --revisar`, el README y el propio
`conf/input.conf`. Comprobado forzando el camino del sobremesa sobre una copia
del repo, que es la única forma de ver esa rama desde el portátil.

## El fondo del login, automático (2026-08-05)

**Cambiar de fondo ya actualiza también la pantalla de inicio de sesión, sin
pedir contraseña.** Antes obligaba a pasar `./instalar.sh --sddm` a mano, que
para quien cambia de fondo a menudo es lo mismo que no funcionar.

La clave: el greeter corre como el usuario `sddm` y no puede leer tu `$HOME`
(está a 700), y `/usr/share` es de root. Se resolvió **sin** aflojar permisos de
la casa y **sin** ninguna regla NOPASSWD: `--sddm` crea una vez
`/var/lib/sddm-celiuz` (tuya, grupo `sddm`, modo **2750** — el setgid es lo que
hace que el greeter pueda leer lo que escribas) y deja los dos ficheros del tema
como enlaces ahí. Después, `hypr/scripts/sddm-fondo.sh` lo rehace solo desde
`aplicar()`, en segundo plano.

**Si vienes de una instalación anterior, hay que pasar `./instalar.sh --sddm` una
vez más** (la última). El instalador lo detecta y lo saca como pendiente en rojo.
**Ya está pasado en las dos máquinas** (el portátil, el 2026-08-05); hasta
hacerlo, la pantalla de login se veía negra, que era el síntoma.

Verificado de punta a punta en la PC: `aplicar()` vuelve al instante, el fondo se
regeneró solo en 9 s, y los ficheros quedan con grupo `sddm` y modo 644.

Y verificado también en el portátil (2026-08-05): el greeter dibuja el fondo, la
tarjeta y el campo de contraseña a 1366x768 —`sddm-greeter-qt6 --test-mode`
dentro del anidado—, y regenerar el fondo con otro vídeo tardó 18 s **sin pedir
contraseña**, dejando los ficheros con grupo `sddm` y modo 644.

## El SUPER+TAB y el sonido (2026-08-04)

**El `SUPER+TAB` ya se cierra al soltar SUPER, que era lo que faltaba.** Antes
había que rematar con `Enter`. Dos fallos distintos, los dos medidos y no
deducidos:

1. **El `bindr` estaba escrito sin modificador** (`bindr = , SUPER_L`) y por eso
   no disparaba **nunca**. Va con él delante: `bindr = SUPER, SUPER_L`. Y hacen
   falta las dos combinaciones de cada tecla, porque el modmask coincide exacto y
   soltar SUPER con SHIFT pulsado es otro caso.
2. **El toque rápido** seguía dejando la ventana colgada: si sueltas antes de que
   la capa tenga el teclado (~185 ms), el evento **no lo ve nadie**. Se resolvió
   preguntándole al kernel con el módulo nuevo **`hypr/scripts/lib/teclas.py`**,
   y preguntándoselo *antes* de dibujar la ventana: si ya soltaste, no se enseña
   nada y saltas directo.

Lo verificado en vivo: taps rápidos (sin ventana, salto directo), gesto lento,
`SUPER+SHIFT+TAB` hacia atrás y `Escape`. El detalle técnico está en el README y
las trampas en el `CLAUDE.md` — **no vuelvas a deducirlas**.

Nuevo para diagnosticar: `touch $XDG_RUNTIME_DIR/vista-escritorios.debug` enciende
el diario cuando el script lo lanza **Hyprland**, que es el único caso en el que
se pueden medir estas carreras.

**Y las notificaciones ya suenan** (`hypr/scripts/sonido-notificacion.sh`, sonido
`message` del tema freedesktop). Queda mudo en «no molestar», que hubo que poner
expresamente: `on-notify` se dispara igual con `invisible=1`. Para saber qué usa o
por qué no suena, `sonido-notificacion.sh --revisar` — mako no enseña esos errores.

## La batería de la barra (2026-08-04)

En un portátil, la barra de arriba enseña la batería a la derecha; en un
sobremesa, no. Cómo funciona está contado en el README («La batería de la
barra»), y el porqué de cada umbral y cada color, en los comentarios de
`waybar/config.jsonc` y `waybar/style.css`.

Lo que hay que saber para no romperlo: **el lado derecho de la barra ya no se
escribe en `config.jsonc`**. Sale de `waybar/derecha.jsonc` (versionado, sin
batería) por un `include`, y `instalar.sh` genera `waybar/local.jsonc` metiéndole
`battery` si la caja es un portátil. Para añadir un módulo a la derecha, va en
`derecha.jsonc` y en ningún otro sitio.

Está comprobado, en esta máquina y para la otra:

- Las pruebas, `./instalar.sh --revisar` y `hyprctl configerrors`, limpios.
- El módulo, vivo en la barra y con su color (captura con `grim`).
- El camino del **sobremesa**: el generador con `BATERIA=no` saca la lista sin
  batería.
- Que **falte `local.jsonc`** —un clon recién hecho, antes de pasar el
  instalador— no deja sin barra: medido en un Hyprland anidado, waybar deja un
  `[warning] Unable to find resource file` y sigue con `derecha.jsonc`.

**Lo que no se ha visto nunca en pantalla** son los estados que dependen de la
carga: `full` (100 %), `not-charging` (el corte al 80 % de algunos portátiles) y
la alarma roja de `critico` (≤10 % **sin** cable). Si alguno se ve raro, el sitio
es el bloque `#battery` de `style.css`; están escritos, no probados.

## El susto del fondo (2026-08-04), y lo que dejó

Levantar un Hyprland **anidado** con el `$HOME` de verdad dejó el escritorio real
sin fondo y sin el demonio que lo pausa: el anidado corre tu `autostart.conf`, y
`wallpaper.sh` empieza con `pkill -x mpvpaper` y `pkill -f wallpaper-paus[e].py`,
que no distinguen de qué sesión es cada proceso. Al cerrar el anidado, su demonio
—que nace con `setsid`— sobrevivió apuntando a un compositor muerto, y como
`wallpaper.sh` pregunta si hay demonio con un `pgrep` por nombre, el zombi
contestaba que sí y nadie levantaba uno bueno. Resultado: el vídeo corriendo con
ventanas encima y quieto en el bloqueo.

De ahí salieron tres cosas, y **las tres están puestas**: el demonio **se va
solo** si pasa `ABANDONO` (60 s) sin poder hablar con su Hyprland,
`tests/unidad/fondo-huerfano.sh` lo vigila por los dos lados, y el anidado ya no
se levanta a pelo:

```sh
./tests/anidado.sh hyprctl configerrors   # levanta, ejecuta y recoge
./tests/anidado.sh                        # se queda abierto; Ctrl+C lo tumba
```

`tests/anidado.sh` monta `$HOME` desechable, una copia del repo enlazada como la
enlaza `instalar.sh`, `autostart.conf` vaciado y `$XDG_RUNTIME_DIR` propio; al
salir barre los procesos que quedaran con la firma de esa instancia y borra la
casa. Comprobado: con él, el `mpvpaper` y el demonio de la sesión real siguen
con el mismo PID después de usarlo, y un proceso lanzado con `setsid` dentro
queda recogido al cerrar.

**Lo que sigue sin cubrir**, y conviene tenerlo presente: `pkill` mata por
NOMBRE, y eso no lo aísla ningún `$HOME`. Si dentro del anidado lanzas a mano
algo que mate por nombre —`wallpaper.sh`, sin ir más lejos—, se llevará por
delante lo de la sesión de fuera igual. Allí no arranca nada solo; a partir de
ahí, ojo con lo que lanzas.

## Lo siguiente, por orden de valor

### 1. `env.conf` para Nvidia — está vacío

Es lo que más puede afectar jugando (RTX 3050 sobre Wayland). **No copiar listas
de los foros**: muchas variables que circulan llevan años obsoletas en Hyprland
0.56 y algunas empeoran el rendimiento. Hay que comprobar una por una cuáles
hacen falta de verdad en esta versión.

Pista fuerte encontrada durante las pruebas: el Hyprland **anidado** sobre esta
GPU solo levanta con `AQ_NO_MODIFIERS=1` (sin eso, `bo null` en bucle y se queda
sin monitor). Lo primero es averiguar si algo de eso hace falta también en la
sesión real o si es solo cosa del anidado.

### 2. ~~Teclas multimedia~~ — hecho

Volumen, mute, micro y multimedia ya están en `keybinds.conf`, y funcionan en las
dos máquinas. Brillo, touchpad y tapa en `conf/teclado-laptop.conf`, que solo se
carga en portátiles (ver «Portátil o sobremesa» en el README).

**Lo de la perilla del X820 queda cerrado (2026-08-04): ese teclado no tiene esas
teclas**, lo confirmó el usuario probándolo, y no le hace falta. O sea que en la
PC los binds de audio no los dispara nadie — y eso **no es un fallo**: un bind
sobre una tecla que el teclado no emite simplemente no salta, que es justo por lo
que estas líneas pueden vivir en el fichero común y no en el de portátil. No hay
nada que investigar aquí; si algún día se cambia de teclado, funcionarán solas.

**Sin comprobar en el portátil**: el bind de modo avión (`XF86RFKill`). Probarlo
significaba tumbar la wifi de la sesión. El riesgo no es que no funcione, es que
funcione **dos veces** —si el kernel ya conmuta el rfkill solo, el bind lo
devuelve— y parezca que la tecla no hace nada. Cómo saberlo, en el propio
fichero.

### 3. Historial del portapapeles

`SUPER+SHIFT+V` ya está reservado en `keybinds.conf`. Candidato: cliphist
(`wl-clipboard` ya está instalado).

### 4. Reglas de ventana del flujo de seguridad

VMs, Burp Suite, etc. **Preguntar primero qué herramientas se usan de verdad**
antes de escribir reglas para programas que quizá no se abren nunca.

### 5. El login (SDDM) y el TTY siguen en `latam`

`/etc/vconsole.conf` tiene `KEYMAP=la-latin1` y `XKBLAYOUT=latam`, y eso gobierna
la pantalla de login y el TTY de rescate — que son ajenos a Hyprland. O sea que
**la contraseña al encender se sigue tecleando en latam** sobre un teclado ANSI,
aunque la sesión ya use `us`. Se arregla con `localectl` y sudo.

Está fuera del repo y tiene un modo de fallo feo (cambia cómo se teclea la
contraseña en el login), así que **solo si se pide**.

## Menores, ya ofrecidos y no pedidos

- Regla de sudo estrecha para `ir-a-windows.sh`, en vez de pedir la contraseña
  en una terminal.
- `windowrule` para que la terminal de `ir-a-windows.sh` salga flotante.
- Atajo de teclado propio para CeliuzPaper.
- Botón de «añadir comando a mano» en el gestor del dock, para AppImages y
  binarios sueltos: ningún escaneo de `.desktop` los cubre.
- Pasar `dock-manager.py` y `celiuzpaper.py` a leer la paleta en caliente, como
  ya hace `vista-escritorios.py`.

## Cosas que están fuera del repo a propósito

- `hypr/scripts/ir-a-windows.sh` — sin seguimiento por decisión expresa: se
  considera algo aparte de la configuración del escritorio.
- Los vídeos e imágenes de fondo, las credenciales de Google Calendar, el dock
  de cada máquina y las carpetas de fondos añadidas. Ver la regla de oro del
  `CLAUDE.md`.

## Decisión que hay que tomar algún día

Hyprland avisa al arrancar de que **el formato `.conf` deja de estar soportado en
la 0.57**. Todo el repo está en hyprlang por decisión explícita. Antes de esa
versión: quedarse anclado, o portar a Lua.
