# Por dónde seguir

Notas para retomar el trabajo sin tener que reconstruir el contexto. Si esto se
queda viejo, manda el `README.md` y el `CLAUDE.md`.

Última sesión: **2026-08-03**. Lo último fue la pantalla de inicio de sesión
(SDDM) y la detección de portátil vs. sobremesa.

## Lo primero al abrir el repo

```sh
./tests/run.sh          # 7 pruebas. Deben salir todas
./instalar.sh --revisar # no debe sacar avisos inesperados
hyprctl configerrors    # vacío
```

Si las pruebas fallan **antes** de tocar nada, eso es lo que hay que arreglar
primero: significa que algo del sistema cambió por debajo (una actualización de
Hyprland, de mpv o de waybar).

---

## COMPROBAR TRAS EL REINICIO DEL 2026-08-03

Se reinició para estrenar tres cosas a la vez: la pantalla de SDDM, lo que vino
de la PC (fondos como imagen, CeliuzPaper por módulos, pruebas) y la detección de
portátil. Nada de esto se había visto funcionando en un arranque de verdad.

Va en orden: si falla el paso 1, los demás no dicen nada.

### 0. ¿Se llegó a pasar el instalador completo?

```sh
grep conf_maquina ~/dotfiles/hypr/conf/local.conf
```

Tiene que salir `$conf_maquina = ...teclado-laptop.conf`. **Si no sale nada**, es
que solo se pasó `./instalar.sh --sddm`, que es exclusivo y no reescribe
`local.conf`. Se arregla con `./instalar.sh` a secas y volviendo a entrar. Todo
lo de teclado de abajo dependerá de esto.

### 1. La pantalla de inicio de sesión

Se ve al arrancar, antes del escritorio. Debe salir la tarjeta violeta con el
reloj y **el vídeo detrás** (484 K, reescalado a 1366x768).

- **Si sale la de siempre de SDDM**: el tema no se aplicó. Mirar
  `/etc/sddm.conf.d/10-celiuz.conf` y que no haya un `Current=` en
  `/etc/sddm.conf` ganándole.
- **Si sale negra pero se puede escribir la contraseña**: el degradado de reserva
  hizo su trabajo; falló el vídeo. Falta `qt6-multimedia-ffmpeg`.
- **Si no se puede entrar**: `Ctrl+Alt+F2`, consola, y
  `sudo rm /etc/sddm.conf.d/10-celiuz.conf`.

### 2. El Ctrl derecho volvió a ser Ctrl

Es el motivo de todo el trabajo de detección. En una terminal, con algo
corriendo (`ping 1.1.1.1`), pulsar **Ctrl DERECHO + C**: tiene que cortarlo.

Antes no cortaba: hacía de AltGr, heredado de la config del Attack Shark X820.
Si sigue sin cortar, mirar que `hyprctl devices` enseñe el
`at-translated-set-2-keyboard` **sin** `o "lv3:switch"` — el resto de teclados sí
lo llevan, y está bien que lo lleven.

### 3. Las dos distribuciones siguen alternando

`SUPER + DEL` tiene que seguir cambiando entre `us` y `latam`, avisando por
notificación. Es el riesgo propio del bloque `device` nuevo: si se hubiera
quedado sin `kb_layout`, este teclado tendría solo `us` y el atajo no tendría
entre qué alternar.

### 4. Teclas de función

| Tecla | Qué debe pasar |
|---|---|
| Brillo arriba/abajo | cambia, y **manteniendo pulsado repite** |
| Brillo al mínimo | se queda en 1, nunca en negro total |
| Volumen y mute | cambian, y también con la pantalla bloqueada |
| Play / siguiente / anterior | controlan lo que esté sonando |
| Micro-mute | silencia el micrófono |

Si el brillo no responde: `brightnessctl set 50%` a mano. Si eso sí funciona, el
problema es el bind; si tampoco, es permisos (aquí escribía por logind, sin regla
udev).

**Modo avión (`XF86RFKill`) está SIN comprobar.** El riesgo es que funcione dos
veces —si el kernel ya conmuta solo, el bind lo devuelve— y parezca muerta.
Comprobar con `rfkill list` antes y después de pulsarla. Si conmuta sola, comentar
la línea en `conf/teclado-laptop.conf`.

### 5. Touchpad y tapa

- Tocar hace clic; dos dedos, clic derecho.
- Escribir un párrafo largo **sin que el cursor se vaya solo** (esa es la prueba
  de `disable_while_typing`).
- Cerrar la tapa y abrirla: debe pedir la contraseña, y la pantalla debe
  **volver** al abrir. Que vuelva es lo que hay que mirar: si se queda negra, el
  `dpms on` del `switch:off` no está haciendo su trabajo.
- **No debe suspender.** Se dejó así a propósito.

### 6. Lo que vino de la PC

- El fondo en vídeo sigue puesto y se pausa con ventanas abiertas encima.
- CeliuzPaper abre y enseña **la carpeta de imágenes como un módulo más**.
- Poner una **imagen fija** de fondo: debe quedarse puesta, no desaparecer a los
  5 segundos.

### 7. Y entonces

```sh
./tests/run.sh
hyprctl configerrors
```

Si todo lo de arriba está bien, **queda hacer commit**: el trabajo de la
detección de máquina estaba sin commitear cuando se reinició, y el commit de SDDM
(`ee3b726`) sigue sin subir a `origin/main`.

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
