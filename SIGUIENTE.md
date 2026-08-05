# Por dónde seguir

Notas para retomar el trabajo sin tener que reconstruir el contexto. Si esto se
queda viejo, manda el `README.md` y el `CLAUDE.md`.

Última sesión: **2026-08-04**. Lo último fue la batería en la barra de arriba,
que sale solo en los portátiles.

## Lo primero al abrir el repo

```sh
./tests/run.sh          # 8 pruebas. Deben salir todas
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

## Lo último: la batería de la barra (2026-08-04)

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

### 2. ~~Teclas multimedia~~ — hecho, menos la perilla

Volumen, mute, micro y multimedia ya están en `keybinds.conf`, y funcionan en las
dos máquinas. Brillo, touchpad y tapa en `conf/teclado-laptop.conf`, que solo se
carga en portátiles (ver «Portátil o sobremesa» en el README).

**Queda por comprobar en la PC**: si la perilla del X820 manda de verdad
`XF86AudioRaiseVolume`. Anuncia dispositivos `-consumer-control` y
`-system-control` aparte, y nunca se probó. Si con los binds puestos la perilla
ya cambia el volumen, está resuelto; si no, hay que ver qué manda con
`wev` o `libinput debug-events`.

**Y sin comprobar en el portátil**: el bind de modo avión (`XF86RFKill`). Probarlo
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
