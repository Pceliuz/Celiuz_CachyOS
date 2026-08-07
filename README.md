# Celiuz_CachyOS — dotfiles de Hyprland

Mi escritorio de **Hyprland sobre CachyOS** (base Arch), escrito desde cero: sin
dotfiles ajenos, sin shells prearmadas y sin la config que trae la distro. Todo
en **hyprlang** (`.conf`), no en Lua, para poder seguir la wiki y los foros sin
traducir sintaxis.

No es un tema para instalar y ya: es *mi* escritorio, con cosas hechas a medida
(el auto-ocultado de las barras, el dock generado, el panel de calendario, la app
del fondo de pantalla, la pantalla de bloqueo). Si te sirve algo, cógelo suelto.

---

## Qué hay dentro

| Carpeta | Qué es |
|---|---|
| `hypr/` | Hyprland. `hyprland.conf` solo hace `source` de los módulos de `conf/`. |
| `hypr/conf/` | Un módulo por asunto: monitores, teclado, atajos, reglas de ventana… `colores.conf` va el primero, porque define la paleta que usan los demás, y `teclado-laptop.conf` el último, y solo si estás en un portátil. |
| `hypr/scripts/` | Todo lo hecho a medida (ver abajo). |
| `hypr/scripts/lib/` | Bibliotecas compartidas por los scripts y por la CLI. |
| `waybar/` | Barra de arriba y dock de abajo. Cuatro instancias de waybar. |
| `fuzzel/` | Lanzador de aplicaciones. |
| `celiuzpaper/` | App propia para cambiar el fondo de pantalla. |
| `mako/` | Notificaciones. `config` a mano, `colores` generado. |
| `mpvpaper/` | Lista de programas que pausan el fondo en vídeo. |
| `sddm/celiuz/` | Tema de la pantalla de inicio de sesión, en QML. Opcional: se instala aparte con `--sddm` porque es lo único que pide root. |
| `tests/` | Pruebas automáticas. `./tests/run.sh` y listo — no hacen falta ni Hyprland corriendo ni nada instalado. Y `anidado.sh`, para lo que sí necesita un compositor. |

### Las piezas a medida

- **`waybar-autohide.py`** — demonio que gestiona las cuatro instancias de waybar
  (barra + dock, cada una con su línea-tirador). Sin ventanas en el escritorio la
  barra se queda puesta; con ventanas se esconde y aparece una línea fina arriba
  que la baja al pulsarla.
- **`gen-dock.py`** — genera `waybar/dock.jsonc` a partir de `waybar/dock-apps.json`.
  El dock **no se edita a mano**. Con clic derecho en cualquier icono se abre
  `dock-manager.py`, que añade y quita apps. Su lista de apps sale de
  `$XDG_DATA_DIRS` más los exports de Flatpak (usuario y sistema) y de Snap: una
  lista fija de carpetas se deja fuera lo que instales por vías nuevas.
- **`vista-escritorios.py`** — el selector de `SUPER + TAB`: enseña los
  escritorios que tienen apps abiertas y eliges a cuál ir. Ver su sección abajo.
- **`calendar-panel.py`** — al pulsar el reloj se abre un calendario con los
  feriados peruanos (`lib/pe_fechas.py`) y los eventos de Google Calendar
  (`lib/gcal.py`).
- **`celiuzpaper`** — cambia el fondo de pantalla, en vídeo o en imagen fija. Al moverte por la tira
  el fondo cambia **de verdad** a pantalla completa; Enter lo fija, Escape
  restaura. Los fondos vienen de varios sitios y cada uno es un **módulo** en la
  fila de arriba: el Workshop de Wallpaper Engine, **tu carpeta de vídeos**, **tu
  carpeta de imágenes** y las carpetas que añadas tú. `TAB` cambia de módulo. También sirve por CLI
  (`--list`, `--set`, `--random`, `--current`, `--carpetas`).
- **`lib/pantalla.py`** — dice qué pantalla hay delante y **de ahí salen las
  medidas** del bloqueo y del selector de fondos, en vez de estar escritas para
  el monitor del autor. Ver su sección abajo.
- **`lib/teclas.py`** — le pregunta **al kernel** qué teclas están pulsadas ahora
  mismo (`EVIOCGKEY`), sin depender de quién tenga el foco. Existe porque el
  evento de soltar `SUPER` no llega en un toque rápido; ver el cambiador de
  escritorios. Devuelve `None`, y no `False`, cuando no puede mirar.
- **`lock.sh` + `hyprlock.conf`** — la pantalla de bloqueo. Ver su sección abajo,
  porque hace bastante más que lanzar `hyprlock`.
- **`gen-colores.py`** — pasa la paleta de `colores.conf` al CSS de waybar y a la
  config de mako. Es lo que hace que el violeta esté escrito en un solo sitio.
- **`sonido-notificacion.sh`** — el «toc» de las notificaciones. Busca el
  reproductor y el sonido que haya en la máquina, y se calla sin protestar si no
  hay ninguno. `--revisar` dice qué usa, o por qué no suena.
- **`sddm-fondo.sh`** — pone tu fondo actual en la pantalla de inicio de sesión,
  sin permisos de root. Lo llama `aplicar()` en segundo plano cada vez que
  cambias de fondo; a mano, `--revisar` y `--forzar`.
- **`recargar.sh`** — recarga la config avisando de verdad si falla, y comprueba
  incoherencias que son config válida pero no hacen nada.
- **`wallpaper-pause.py`** — pausa el vídeo del fondo cuando queda tapado, y lo
  mata entero mientras corra algo de la `stoplist` (juegos).
- **`teclado.py`** — la sesión lleva dos distribuciones (us y latam). Este avisa
  por notificación de cuál hay puesta: al arrancar, y cada vez que la cambias con
  `SUPER + DEL`. Ver su sección abajo.

---

## Requisitos

Todo está en los repos oficiales de CachyOS/Arch. No hace falta nada del AUR.

```sh
sudo pacman -S hyprland waybar fuzzel kitty hyprlock hypridle mpvpaper mako \
               grim slurp wl-clipboard uwsm libnotify \
               python-gobject gtk-layer-shell ffmpeg librsvg \
               ttf-meslo-nerd noto-fonts-cjk \
               mission-center nvtop btop \
               ananicy-cpp cachyos-ananicy-rules \
               python-google-api-python-client python-google-auth-oauthlib
```

Y para las teclas de función, que van aparte porque el escritorio arranca igual
sin ellas:

```sh
sudo pacman -S wireplumber playerctl brightnessctl
```

Notas:

- **`ttf-meslo-nerd`** no es opcional: las barras usan la variante
  `MesloLGS Nerd Font Propo` para los iconos del dock (en la variante normal cada
  icono mide 24 px lógicos aunque dibuje 46, y salen descentrados).
- **`ananicy-cpp` + `cachyos-ananicy-rules`** no son solo para prioridades: la
  pantalla de bloqueo usa sus ~13.500 reglas `"type": "Game"` como base de datos
  de juegos, para saber qué no debe congelar.
- **`uwsm`** es imprescindible para lo mismo (ver abajo).
- **`wireplumber`, `playerctl` y `brightnessctl`** son los que mueven las teclas
  de volumen, de multimedia y de brillo. Si falta alguno, la tecla no hace nada
  **y no avisa de nada**: un `exec` que no existe no da error en Hyprland. Por
  eso el instalador los comprueba y lo dice. `brightnessctl` solo se pide en un
  portátil.

## Instalación

Se enlaza, no se copia, para que editar el repo sea editar la config:

```sh
git clone https://github.com/Pceliuz/Celiuz_CachyOS.git ~/dotfiles
cd ~/dotfiles
./instalar.sh
```

**Clónalo donde quieras.** `~/dotfiles`, `~/.dotfiles`, `~/repos/mis-configs`: da
igual. Los `.conf` se referencian entre ellos por `$HOME/.config/hypr/...`, que
es el enlace que crea el instalador, y los scripts averiguan la raíz del repo a
partir de dónde está su propio fichero. Lo único que no debes hacer es mover la
carpeta *después* de instalar sin volver a ejecutar `./instalar.sh`, porque los
enlaces de `~/.config` seguirían apuntando al sitio viejo.

(Antes esto no era así: el repo obligaba a clonar exactamente en `~/dotfiles` y,
si lo ponías en otro sitio, media configuración quedaba muerta **sin dar ningún
error**. Hay una prueba, `tests/unidad/portabilidad.sh`, que impide que la
costumbre vuelva.)

`instalar.sh` se puede repetir cuantas veces haga falta y no pisa lo que ya
esté hecho. Antes de nada, `./instalar.sh --revisar` cuenta lo que haría sin
tocar nada. Lo que hace:

- Avisa de los paquetes que falten (no instala nada por su cuenta).
- Enlaza `hypr`, `waybar`, `fuzzel`, `mako` y `mpvpaper` a `~/.config`,
  **apartando antes** lo que hubiera. Esto último importa: `ln -sfn` sobre una
  carpeta que ya existe crea el enlace *dentro* de ella y la config no se
  despliega, sin dar ningún error. En CachyOS `~/.config/hypr` ya existe.
- Avisa si aparece un `hyprland.lua`: Hyprland 0.56 lo prefiere antes que
  `hyprland.conf`, así que si CachyOS repone el suyo, esta config queda ignorada
  en silencio.
- Instala CeliuzPaper (binario, `.desktop` e icono) y refresca las cachés.
- **Crea el dock de esta máquina** con tu terminal y tu navegador
  predeterminado, averiguados en el sistema. Solo esos dos: el resto los pones
  tú con el clic derecho sobre cualquier icono del dock. El repo no trae apps de
  nadie a propósito — las del autor serían iconos muertos en tu equipo.
- Escribe `hypr/conf/local.conf` con tu terminal, que es la que abre
  `SUPER + RETURN`.

Cuando termine, **cierra la sesión y vuelve a entrar**: los `exec-once` de
Hyprland solo corren al arrancar la sesión, así que recargar con
`SUPER + SHIFT + R` no basta la primera vez.

Después, dos cosas que el repo **no** trae y hay que poner a mano:

1. **El fondo de pantalla.** Los vídeos no se suben (pesan mucho y no son míos
   para redistribuirlos). `hypr/wallpapers/current` es un enlace al vídeo activo;
   se apunta con `celiuzpaper` o con `hypr/scripts/set-wallpaper.sh`.
2. **Las credenciales de Google Calendar**, si quieres el panel del reloj. Viven
   **fuera del repo** a propósito:
   `~/.config/gcal-panel/credentials.json` (las pones tú, desde tu propio
   proyecto de Google Cloud) y `~/.local/share/gcal-panel/token.json` (lo escribe
   `hypr/scripts/lib/gcal.py auth`). Sin ellas el panel funciona igual, solo que
   sin eventos.

---

## Atajos

| Tecla | Qué hace |
|---|---|
| `SUPER + RETURN` | Terminal (la que detecte `instalar.sh`) |
| `SUPER + Q` | Cerrar ventana |
| `SUPER + V` | Flotante / anclada |
| `SUPER + B` | Lanzador de aplicaciones |
| `SUPER + SHIFT + B` | Lanzador en modo "ejecutar binario" |
| `SUPER + C` | Sacar la barra y el dock |
| `SUPER + SHIFT + C` | Reiniciar el demonio de las barras |
| `SUPER + N` | Descartar la notificación de arriba |
| `SUPER + SHIFT + N` | Descartarlas todas |
| `SUPER + ALT + N` | No molestar (encender / apagar) |
| `SUPER + CTRL + N` | Recuperar la última descartada |
| `SUPER + SHIFT + R` | Recargar la config (y avisar de verdad si falla) |
| `SUPER + L` | Bloquear la pantalla |
| `SUPER + S` | Captura de una zona |
| `SUPER + SHIFT + S` | Captura de la pantalla entera |
| `SUPER + 1..7` | Ir al escritorio |
| `SUPER + SHIFT + 1..7` | Mover la ventana al escritorio |
| `SUPER + flechas` | Mover el foco |
| `SUPER + clic izq/der` | Mover / redimensionar flotantes |
| `SUPER + TAB` | Cambiar de escritorio manteniendo SUPER, viendo cada uno de verdad |
| `SUPER + SHIFT + TAB` | Lo mismo, hacia atrás |
| `SUPER + DEL` | Cambiar de distribución de teclado (us ⇄ latam) |
| `SUPER + SHIFT + P` | Salir de Hyprland |

---

## El cambiador de escritorios (SUPER + TAB)

El gesto de Windows, pero de **escritorios** y no de ventanas:

1. **Mantienes `SUPER` y pulsas `TAB`**: aparecen flotando en el centro de la
   pantalla los escritorios **que tienen apps abiertas** (los vacíos no salen).
2. **Sin soltar `SUPER`**, cada `TAB` salta al siguiente — y el escritorio
   **cambia de verdad**, no es una miniatura: ves lo que hay.
3. **Sueltas `SUPER`** y te quedas donde estabas mirando.

`SUPER + SHIFT + TAB` va hacia atrás. `Escape` te devuelve al escritorio del que
saliste, marcado como **DESDE AQUI**. `1-9` va directo a ese escritorio. `Enter`
o un clic también confirman, por si sueltas `SUPER` antes de tiempo.

Igual que el Alt+Tab de Windows, la propia combinación ya te deja mirando el
**siguiente**: un toque rápido de `SUPER + TAB` te lleva al otro escritorio sin
pulsar nada más.

Son dos gestos distintos y conviene que sigan siéndolo:

| | |
|---|---|
| `SUPER + 1..7` | *"quiero **abrir** algo ahí"*. Saltas a ciegas, y está bien así. |
| `SUPER + TAB` | *"quiero **volver** a lo que tengo abierto"*, pero no te acuerdas de en cuál lo dejaste. Lo ves y lo eliges. |

### Por qué son tarjetas flotantes y no un panel

**La previsualización es el cambio de verdad**, igual que en CeliuzPaper al
elegir fondo: allí el fondo cambia a pantalla completa mientras te mueves por la
tira y `Escape` deja el que tenías. Aquí igual — y por eso **no hay ni barra ni
velo**: la capa ocupa la pantalla entera pero está vacía, y lo único que se
pinta son las tarjetas del centro. Cualquier fondo taparía justo lo que estás
eligiendo. (La primera versión era una tira apoyada abajo y tapaba parte de la
app previsualizada; por eso se cambió.)

Que eso funcione no era evidente: un `dispatch workspace` **con la capa abierta
sí cambia el escritorio a la vista**, porque las capas pertenecen al monitor y
no al escritorio, así que las tarjetas se quedan encima mientras por detrás
cambia todo. Comprobado en un Hyprland anidado antes de escribirlo.

### Quién mueve la selección (no es el teclado)

**La capa nunca llega a ver el `TAB`.** Hyprland atiende sus *binds* antes de
entregar la tecla al cliente, así que mientras `SUPER` siga pulsado cada `TAB`
vuelve a disparar el atajo y la ventana no se entera de nada. Está comprobado en
la sesión real con `VISTA_DEBUG`: en el registro no aparece ni una pulsación de
tecla, aparecen **procesos nuevos**.

Por eso el segundo `SUPER + TAB` **no abre nada**: le manda una señal
(`SIGUSR1`, o `SIGUSR2` hacia atrás) a la ventana que ya está abierta para que
avance, y se va. La primera versión mataba a la anterior y abría otra, y el
efecto era el que se notaba al usarlo: cambiaba a un escritorio y al segundo
`TAB` "se regresaba y se cerraba" — porque al morir por `SIGTERM` la anterior
volvía a su escritorio de partida.

**La trampa que costó encontrar:** ese mismo salto, hecho justo antes de cerrar
la capa, **se deshace solo**. `hyprctl` responde `ok` y el escritorio vuelve al
anterior sin ningún aviso: al destruirse una capa con el teclado en exclusiva,
Hyprland devuelve el foco a la ventana que lo tenía, y esa ventana se trae
consigo su escritorio. Por eso el destino se guarda y el salto **se repite
después** de cerrar.

### Cómo se detecta que sueltas `SUPER`

Esta es la parte que más ha costado, y la que más veces se dio por entendida sin
serlo. **El evento de soltar no es fiable**, así que hay tres caminos y ninguno
sobra — cada uno falla en un sitio distinto. Todo lo que sigue está medido el
2026-08-04 con el diario del propio script:

| | Camino | Cuándo sirve | Cuándo NO |
|---|---|---|---|
| 1 | `bindr` de Hyprland → `SIGWINCH` | Es el más rápido cuando llega | **Casi nunca llega**: disparó 2 de 10 veces, y las dos pulsando `SUPER` sola. Con `SUPER` en combo con `TAB` —o sea, en el gesto de verdad— no dispara |
| 2 | El evento de teclado de GTK | Con la capa ya en pantalla y con el teclado | Antes de eso no ve nada |
| 3 | Preguntarle al kernel (`lib/teclas.py`) | Siempre. No depende de quién tenga el foco ni de que llegue ningún evento | Solo si no se puede leer `/dev/input` |

El caso que se quedaba colgado era **el toque rápido**: la ventana tarda ~185 ms
en estar en pantalla (≈15 ms de arrancar Python y ≈120 ms de importar GTK), y si
sueltas dentro de ese rato el evento **se pierde entre dos sillas** — ni GTK, que
aún no tiene el teclado, ni el `bindr`, que en combo no dispara. La ventana se
quedaba puesta y había que rematar con `Enter`.

Lo arregla el camino 3: se le pregunta al kernel por el mapa de teclas pulsadas
(`EVIOCGKEY`), que es estado y no una cola de eventos. Y se le pregunta **antes
de enseñar la ventana**: si ya habías soltado, es que querías el siguiente
escritorio y lo querías ya, así que no se dibuja nada y el salto ya está hecho.
Cuesta 0,11 ms.

> **Lo que NO se puede hacer es preguntárselo a GTK.**
> `Gdk.Keymap.get_modifier_state()` devuelve **siempre `0x4000040`** en esta
> sesión, con el bit de SUPER puesto aunque no la toque nadie: no es el estado en
> vivo, es el mapa de qué bit le corresponde. Medido.

Y como la capa coge el teclado en exclusiva, lleva además dos salidas de
emergencia:

- **`Escape`**, que además te devuelve de donde saliste.
- **Cierre automático a los 20 s** sin tocar nada, que se rearma con cada tecla:
  no te echa mientras decides, solo si te fuiste y la dejaste puesta. Una capa
  así colgada te dejaría sin teclado en todo el escritorio, y eso no puede
  depender de que el código no falle nunca.

Para diagnosticar, el diario va a `$XDG_RUNTIME_DIR/vista-escritorios.log` y se
enciende de dos formas:

```sh
VISTA_DEBUG=1 hypr/scripts/vista-escritorios.py   # lanzándolo tú a mano
touch $XDG_RUNTIME_DIR/vista-escritorios.debug    # cuando lo lanza HYPRLAND
```

La segunda es la que sirve para medir carreras: un bind no tiene dónde ponerle un
entorno sin duplicarlo, y duplicarlo cambia justo lo que se está midiendo. Las
marcas van con **milisegundos y PID**, porque lo que se diagnostica aquí son
carreras de ~15 ms.

Los colores no están escritos en el script: lee `conf/colores.conf` en caliente y
arma su CSS con la paleta, así que si cambia el amatista, esta pantalla cambia
sola.

---

## El teclado

El teclado es un **Attack Shark X820: ANSI de 75%**. Eso obligó a cambiar la
distribución, y conviene saber por qué antes de "arreglarla" otra vez.

`latam` es una distribución **ISO, de 105 teclas**, y este teclado no tiene dos
que ella da por hechas:

- **`<LSGT>`**, la tecla de `<` `>` entre el Shift izquierdo y la Z. En latam
  esos dos símbolos viven **solo** ahí: `Shift+,` y `Shift+.` dan `;` y `:`.
- **Alt derecho (AltGr)**. Comprobado pulsando el teclado entero con
  `xkbcli interactive-wayland`: no existe. Y en latam `@`, `\`, `~` y `^` están
  todos en el tercer nivel, o sea detrás de AltGr.

Con latam en este teclado, esos **seis símbolos eran imposibles de escribir**.
Además la serigrafía mentía en casi toda la fila de símbolos: la tecla que dice
`;:` daba `ñ`, la de `'"` daba `{[`.

La solución tiene tres partes, todas en `conf/input.conf`:

| | |
|---|---|
| `kb_layout = us,latam` | Dos distribuciones a la vez. La **#0 es `us`**, la que arranca. |
| `kb_variant = altgr-intl,` | La variante de `us` no cambia nada del nivel base — solo añade `ñ` y tildes en el tercer nivel. Sale gratis. |
| `kb_options = lv3:switch` | **El Ctrl derecho hace de AltGr.** Es la opción que xkb llama literalmente "Right Ctrl". |

Con `us` puesta, lo que dice la tecla es lo que sale: `< > @ \ | ~ ^` directos o
con Shift. El español no se pierde: `Ctrl derecho + n` da `ñ`, `+ a` da `á`,
`+ /` da `¿`, y `Ctrl derecho + Shift + 1` da `¡`. Y `latam` sigue de segunda,
intacta, para escribir con la memoria muscular de siempre.

**El coste, que es real:** el Ctrl derecho deja de ser Ctrl. Todos los atajos y
los juegos usan el izquierdo, así que no se nota — pero si algún día un Ctrl "no
responde", es esto y no un fallo.

### Saber en cuál estás

El problema de tener dos distribuciones no es cambiar: es no saber en cuál estás
hasta que escribes mal. Por eso `teclado.py` **avisa siempre**:

- Al arrancar la sesión (`exec-once` en `autostart.conf`), diciendo con cuál
  empiezas y recordando el atajo.
- Cada vez que pulsas `SUPER + DEL`.

Dos detalles que no son adorno:

- El aviso de arranque **espera a que mako coja el bus** antes de mandarse.
  `exec-once` no garantiza orden, y una notificación mandada antes de que exista
  el demonio se pierde sin dejar rastro — justo el fallo que este script existe
  para no tener.
- Los avisos llevan la etiqueta `x-canonical-private-synchronous`, que mako
  entiende como *sustituye al anterior*: pulsar el atajo cuatro veces seguidas
  reescribe un aviso, no apila cuatro.

`teclado.py estado` imprime la activa en una línea, para la barra o para el
asistente.

---

## Portátil o sobremesa: el repo se entera solo

Todo lo de arriba está escrito para el X820, y **en un portátil sobra**. El
teclado interno de cualquier laptop sí tiene AltGr y sí tiene la tecla `<>`, así
que `lv3:switch` no le arregla nada: solo le quita el Ctrl derecho.

Y el problema no era teórico. El bloque `input {}` de Hyprland es **global**: se
lo aplica a todo teclado conectado. Se ve en `hyprctl devices`, donde hasta el
`power-button` sale con `o "lv3:switch"`. O sea que cualquiera que clonara este
repo se quedaba sin Ctrl derecho por un teclado que no ha visto en su vida.

Ahora `instalar.sh` pregunta en qué clase de equipo está y **solo en un portátil**
carga `conf/teclado-laptop.conf`, que corrige lo que haga falta.

Quién decide qué es `hypr/scripts/lib/maquina.py`, y se le puede preguntar:

```sh
hypr/scripts/lib/maquina.py            # el resumen: equipo y perfil de teclado
hypr/scripts/lib/maquina.py teclado    # «completo» o «sin-altgr»
```

El perfil **`completo`** es el de un teclado que trae todas sus teclas —AltGr y
la `<>`—, o sea el de cualquier portátil: ahí `kb_options` se deja **vacío**.
El perfil **`sin-altgr`** es el del X820 y conserva `lv3:switch`.

> **Se vacía en el bloque `input {}` global, no en un `device`.** Durante un
> tiempo esto era un `device { name = at-translated-set-2-keyboard }`, que solo
> rescataba el teclado interno: cualquier **teclado USB que enchufaras al
> portátil** seguía perdiendo su Ctrl derecho, y lo mismo los pseudo-teclados
> `video-bus` y `power-button`. Medido en un Hyprland anidado: con la versión de
> antes y perfil de portátil, un teclado que no fuera el interno salía con
> `o "lv3:switch"`; ahora sale vacío.

### La distribución: que las teclas den lo que tienen escrito

`kb_options` era media historia. La otra es **qué distribución arranca activa**, y
el repo traía `us,latam` porque el teclado del autor está serigrafiado en us. En
un portátil eso suele ser falso: las teclas están impresas en otra cosa, y
entonces la `ñ`, los acentos y los símbolos salen donde no toca. Había que
corregir con `SUPER+DEL` en cada sesión.

En un **portátil** la distribución sale ahora de `/etc/vconsole.conf` — lo que
contestaste cuando el instalador de tu distro te preguntó por el teclado. Ahí es
de fiar, porque estabas **tecleando en el teclado interno mientras respondías**.
La tuya queda la primera y `us(altgr-intl)` la segunda, para alternar con
`SUPER+DEL` (hay atajos y juegos que dan por hecho un teclado us).

> **Y en un sobremesa esa misma fuente miente**, que es la trampa de todo esto.
> El `/etc/vconsole.conf` de la PC del autor dice `latam` y su teclado es un ANSI
> us: eligió latam al instalar y **cambió de teclado después**, que es lo normal
> en una torre. Por eso un sobremesa no la mira y se queda con la del autor —
> deducirlo de ahí arreglaría el portátil y rompería la PC.

Lo escribe `instalar.sh` en `hypr/conf/local.conf`, que no se versiona, y ahí se
puede cambiar a mano si te lo detectó mal:

```sh
hypr/scripts/lib/maquina.py layout      # latam,us
localectl list-x11-keymap-layouts       # los nombres válidos
```

`hyprland.conf` trae el valor de fábrica **antes** de leer `local.conf`, así que
quien clone el repo y arranque sin instalar no se come un error de hyprlang por
una variable sin definir — que además le dejaría sin teclado con el que
arreglarlo.

| | Sobremesa | Portátil |
|---|---|---|
| Distribución | `us,latam` (la del autor) | la del sistema primero, `us` de segunda |
| Ctrl derecho | hace de AltGr (lo necesita el X820) | vuelve a ser Ctrl, **en todos los teclados** |
| Touchpad | — | tap, arrastre, y se calla mientras escribes |
| Brillo | — | `Fn` + las teclas de brillo |
| Tapa | — | al cerrarla, bloquea |
| Barra de arriba | — | enseña la batería, a la derecha |

> **Si clonas esto en un sobremesa, lee esta línea.** El caso «sobremesa» se
> queda con el teclado del autor, que es ANSI de 75% y no tiene AltGr — o sea
> que **tu Ctrl derecho pasará a hacer de AltGr**. Con un teclado completo de
> 105 teclas eso no te hace falta y solo te quita una tecla: la vuelta atrás es
> poner `kb_options =` (vacío) en `hypr/conf/input.conf`. `./instalar.sh
> --revisar` te lo recuerda al detectar un sobremesa. No se decide sola a
> propósito: un teclado se enchufa y se desenchufa, y `kb_options` se lee al
> arrancar la sesión (el porqué largo está en `lib/maquina.py`).

El volumen y las teclas de multimedia **no** están ahí: viven en `keybinds.conf`
y funcionan en las dos máquinas. No son de portátil — cualquier teclado con
teclas de medios las emite, y en uno que no las tenga esas líneas sencillamente
no disparan.

### La batería de la barra

Va por otro camino que el teclado, porque waybar no lee `.conf` de hyprlang. Al
instalar se escribe `waybar/local.jsonc` —el lado derecho de la barra de **esta**
máquina— y `config.jsonc` lo carga con un `include`:

```
waybar/derecha.jsonc   versionado, sin batería. La lista de un sobremesa.
waybar/local.jsonc     generado, con batería si la caja es un portátil.
```

La lista con batería **no está escrita a mano en ninguna parte**: `instalar.sh`
lee la versionada y le mete `battery` delante de las notificaciones. Si añades un
módulo a `derecha.jsonc`, aparece en las dos máquinas sin tocar nada más.

No basta con que el módulo «no se vea» en un sobremesa: waybar crea el widget
aunque no encuentre ninguna batería —solo deja un `No batteries.` en el log— y
quedaría un hueco vacío en la barra. Por eso se decide sacándolo de la lista.

Que falte `local.jsonc` **no** rompe nada: waybar avisa en el log y sigue con
`derecha.jsonc`, así que quien clone el repo y arranque waybar antes de pasar el
instalador tiene barra igual, solo que sin batería.

### La temperatura de la barra

Por el mismo camino, y por el mismo motivo. La ruta del sensor de la CPU **no se
puede versionar**: cada familia de procesador nombra el suyo de otra forma y lo
cuelga de otro sitio del `/sys` — `k10temp` en AMD, `coretemp` en Intel,
`cpu_thermal` en las ARM.

```
waybar/sensores.jsonc  versionado: formato, iconos, umbral. Sin la ruta.
waybar/local.jsonc     generado: la ruta del sensor de ESTA caja.
```

Quién lo averigua es `hypr/scripts/lib/sensores.py`, y se le puede preguntar:

```sh
hypr/scripts/lib/sensores.py         # el resumen: driver, ruta y grados de ahora
hypr/scripts/lib/sensores.py ruta    # lo que va en "hwmon-path-abs"
```

Busca por el `name` que publica cada driver en `/sys/class/hwmon`, y de dentro
coge la entrada del **encapsulado entero** (`Tctl`, `Tdie`, `Package id 0`) y no
la de un núcleo suelto, que salta 20 grados según qué hilo esté trabajando.

> **El número de `hwmonN` no sirve como ruta.** Es lo primero que apetece usar y
> está mal: ese número se reparte por orden de arranque de los módulos del
> kernel y **cambia entre reinicios**, así que la barra podría pasar a enseñar la
> temperatura de la batería sin avisar. Lo estable es la ruta del dispositivo, a
> donde apunta ese enlace: `/sys/class/hwmon/hwmon3` →
> `/sys/devices/platform/coretemp.0/hwmon/hwmon3`. Se guarda la carpeta padre,
> que es lo que espera `hwmon-path-abs`.

Si no reconoce ningún sensor **no se inventa una ruta**: se deja la clave fuera y
waybar cae a su `thermal_zone0`. Un número de procedencia desconocida en la barra
es peor que el valor por defecto, porque parece bueno.

> Aquí estuvo escrita a mano la ruta del **Ryzen 5 5500** del autor
> (`/sys/devices/pci0000:00/0000:00:18.3/hwmon`), dentro de `config.jsonc`, que
> sí se versiona. En su propio portátil —Intel, sensor `coretemp`— esa ruta no
> existe, así que el módulo no podía leer nada; y en la máquina de quien clonara
> el repo, tampoco. Lo vigila `tests/unidad/sensores.sh`, que además falla si
> alguien vuelve a escribir la ruta de un sensor en un `.jsonc` versionado.

### Cómo lo sabe

```sh
hypr/scripts/lib/maquina.py          # resumen
hypr/scripts/lib/maquina.py tipo     # laptop | escritorio
```

Se lo pregunta al **DMI de la BIOS** (`/sys/class/dmi/id/chassis_type`), que es
lo que grabó el fabricante y es la respuesta buena cuando existe. Si el DMI dice
`Other` o `Unknown` —máquinas virtuales, placas que no rellenan el campo— pasa a
mirar batería y tapa. Si tampoco hay nada, responde **sobremesa**, que es la
config de siempre: equivocarse por ahí no cambia nada de lo que ya funcionaba.

**Una batería sola no basta**, y por eso se pide también que haya tapa: un
sobremesa con un SAI conectado por USB enseña una batería en
`/sys/class/power_supply/`, y si eso decidiera, una torre acabaría con ajustes de
touchpad. Un SAI no tiene tapa.

`maquina.py` dice siempre **por qué** ha decidido lo que ha decidido, y ese
motivo queda escrito dentro del `local.conf` generado. Cuando alguien reporte
«me detectó mal», es lo primero que hay que mirar.

### Por qué se decide al instalar y no al arrancar

Al revés que `pantalla.py`, que se mide en caliente. La diferencia: los monitores
cambian —conectas un proyector, giras la pantalla—, pero **la caja no**. Un
portátil no amanece siendo un sobremesa.

Y encima hyprlang **no tiene condicionales**: no hay forma de escribir «carga
esto solo si...» dentro de un `.conf`. Lo que sí se puede es que el `source` del
final apunte a una variable. Así que `instalar.sh` escribe en `local.conf` a
dónde apunta `$conf_maquina`, y en un sobremesa apunta a `conf/nada.conf`, que
está **vacío a propósito**: «no cargar nada» hay que escribirlo como «cargar un
fichero que no tiene nada dentro».

Ese `source` va **el último de todos** en `hyprland.conf`, y ahí está el detalle
que se puede romper sin querer: son *correcciones* sobre `input.conf` y
`keybinds.conf`, y en hyprlang gana el último que habla. Cargarlo antes lo
dejaría pisado, y el síntoma sería «puse el fichero y no hace nada». Hay una
prueba que lo vigila.

> **Si mueves el disco de un equipo a otro**, vuelve a pasar `./instalar.sh`. Es
> el mismo trato que ya tiene el dock.

---

## El aspecto

Un solo tono, muchas alturas. La idea es una **vía láctea de un solo color**: no
repartir violeta hasta que grite, sino que cada variante tenga *un* trabajo y no
invada el del vecino. Si dos tonos hacen lo mismo, sobra uno.

La base es el **negro**, no el violeta. La pantalla parte del vacío y el color
aparece solo donde hay algo que decir, como en un panel OLED: el amatista resalta
porque lo de al lado es negro de verdad y no gris.

### La paleta

Está en `hypr/conf/colores.conf`, que se hace `source` **el primero** en
`hyprland.conf` — las variables de hyprlang son sustitución de texto, así que
tienen que existir antes de que alguien las use.

| Variable | Color | Su papel |
|---|---|---|
| `$negro` | `#000000` | El vacío. Es lo que hace brillar a todo lo demás |
| `$abismo` | `#0d0418` | Negro que sabe de qué familia es |
| `$superficie` | `#1a0830` | El suelo donde se apoya el texto (barra, bloqueo) |
| `$apagado` | `#2d1b4e` | Lo que existe pero no reclama nada |
| `$violeta` | `#6a00f4` | **El grave.** Arranca el degradado y tiñe los halos |
| `$amatista` | `#b16cff` | El color de la casa |
| `$neon` | `#c77dff` | Mismo tono, más vueltas. El núcleo encendido |
| `$luz` | `#e4c7ff` | El punto más caliente. Solo al final y en poca cantidad |

Los tres últimos se usan **juntos y en ese orden**. Por separado son violetas
cualesquiera; lo que hace el efecto neón es el recorrido del grave al agudo, como
un tubo de neón, que tiene el color saturado en los bordes y el núcleo casi
blanco.

Además de esos ocho hay tres tonos con un papel más concreto: **`$tenue`**
(`#8a7aa8`) para el texto secundario, que `$apagado` no puede hacer porque sobre
negro no se leería; y **`$alerta`** (`#eb6f92`) y **`$atencion`** (`#f6c177`),
los dos únicos que no son violeta.

Esos dos se salen de la familia a propósito, y es la misma regla la que los
justifica: un color se gana su sitio por tener un papel, y *"algo va mal"* es un
papel que el violeta no puede hacer — si el aviso fuera violeta como todo lo
demás, dejaría de ser un aviso. Se usan **solo donde significan algo** (sensor en
crítico, contraseña fallida, comprobando), nunca como decoración. Lo que antes
eran acentos decorativos (ámbar en la CPU, rosa en la temperatura, los dos azules
de red y memoria) pasó a la familia violeta.

### Cómo llega la paleta a cada sitio

| Destino | Cómo la lee |
|---|---|
| Hyprland | `source` directo de `colores.conf` |
| hyprlock | `source` directo: habla el mismo hyprlang |
| waybar | `waybar/colores.css`, **generado** por `hypr/scripts/gen-colores.py` |

waybar es el raro: se estiliza con CSS de GTK, que no sabe leer un `.conf`. El
generador emite un `@define-color` por variable. Si cambias un color en
`colores.conf`, **vuelve a lanzar `gen-colores.py`** o la barra se queda con el
viejo; `gen-colores.py --check` avisa si están desincronizados.

> **Dos trampas del formato de color, que muerden en direcciones opuestas:**
>
> - En los **archivos** de config, Hyprland escribe `rgba(RRGGBBAA)` — el alfa al
>   final. Pero `hyprctl getoption` los **devuelve** como `AARRGGBB`, con el alfa
>   delante. Leer uno con las reglas del otro no rompe nada visible: da colores
>   parecidos con el alfa cambiado.
> - **Las transparencias no necesitan variables propias.** El CSS de GTK las
>   deriva con `alpha(@amatista, 0.35)`. hyprlang **no** puede, así que en
>   `hyprlock.conf` las sombras siguen siendo literales, anotadas en el archivo.

### La decoración

| Ajuste | Valor | Por qué |
|---|---|---|
| `rounding` | 10 | **Va atado a `gaps_in = 4`** |
| `rounding_power` | 3 | Curva de iOS (*squircle*), no circunferencia |
| `border_size` | 2 | Un degradado de tres colores en 1 px es un color plano |
| `dim_inactive` | 0.30 | Hunde hacia el negro lo que no usas |
| `blur` | `brightness 0.80`, `vibrancy 0.35`, `contrast 1.10` | El efecto OLED |

**Las esquinas redondeadas necesitan un hueco donde vivir.** Lo que molestaba de
los gaps por defecto era el marco *exterior* de 20 px, así que `gaps_out` se
queda en 0 — las ventanas llegan al borde de la pantalla — y `gaps_in` sube a 4.
Con 0, las esquinas curvas de dos ventanas pegadas dejan un agujero con forma de
rombo por el que se ve el fondo. **Si vuelves a `gaps_in = 0`, quita también el
rounding.**

**Cada color hace un papel opuesto a propósito.** La ventana activa lleva glow
`$neon` y derrama una sombra *violeta*: su sombra deja de ser sombra y pasa a ser
resplandor. La inactiva no brilla y tira una sombra **negra de verdad**, que la
hunde en el fondo. Si todo brillara, no brillaría nada.

El glow usa `$neon` y no `$amatista` — medio tono por encima del borde. Si fueran
el mismo color se sumarían en una mancha; así el borde se lee como el núcleo
encendido y el glow como lo que ese núcleo desprende.

Las tres opciones del blur son lo que hace que kitty (que es translúcida) no se
llene de la luz del vídeo que tiene detrás: `brightness` apaga lo que se cuela,
`vibrancy` satura el poco color que queda y `contrast` evita el gris medio.

**No hay opacidad global.** Volvería translúcidos también Brave, Steam y los
juegos, con el vídeo moviéndose por detrás. Cuando una app deba serlo, va por
`windowrule` en `windowrules.conf`, una a una.

### El movimiento

Si la decoración va de luz, el movimiento también. Dos reglas ordenan todas las
velocidades:

1. **Arrancar rápido, frenar largo.** El ojo lee la velocidad del principio, no
   la del final.
2. **Salir es más rápido que entrar.** Lo que se abre merece presentarse; lo que
   cierras ya no te interesa. Ningún `Out` dura más que su `In`.

Nada pasa de 400 ms: por encima de eso una animación deja de ser sensación y pasa
a ser espera.

**La pieza principal es el neón vivo.** `borderangle` en estilo `loop` gira el
ángulo del degradado sin parar — 8 segundos por vuelta — así que el recorrido de
luz da vueltas despacio a la ventana que tienes delante. `glowangle` gira
sincronizado con él, misma velocidad y misma curva, para que se lean como una
sola fuente de luz con su resplandor y no como dos luces peleándose.

> Esto **solo funciona con un borde en degradado**. Con un color plano no hay
> ángulo que girar y la animación no hace nada.

**`fadeGlow`, `fadeDim` y `fadeShadow` van los tres a 300 ms a propósito.** Al
cambiar de ventana el glow se enciende, el atenuado se cruza y la sombra pasa de
negra a violeta; al ir sincronizados se leen como *un* gesto en vez de tres.
`fadeDim` no es opcional: con el atenuado a 0.30, sin animación el oscurecido
salta de golpe.

Los escritorios usan `slidefade 15%` — se deslizan solo un 15 % de la pantalla
mientras se funden. Con 7 escritorios y atajos directos saltas mucho y a menudo
lejos, y un deslizado completo te haría esperar el viaje cada vez.

#### Lo que cuesta el giro, medido

Con el escritorio quieto, el fondo en vídeo pausado y una ventana en mosaico:

| | Giro encendido | Apagado | Diferencia |
|---|---|---|---|
| CPU de Hyprland | 2,5 – 3,3 % de **un** núcleo | 0,15 % | ≈ +3 puntos |
| Utilización de GPU | 8 – 16 % | 0 % | +8 a +12 puntos |
| Consumo de GPU | 8,6 – 12,4 W | 7,6 W | +1 a +4,7 W |

Sobre 12 hilos, esos 3 puntos son **~0,25 % de la CPU total**. En reposo cuesta
alrededor de un vatio.

> **A pantalla completa no cuesta nada: +0,08 puntos de CPU.** Una ventana en
> fullscreen no dibuja borde, así que no hay nada que animar. El aviso que había
> aquí antes —que esto te comería frames jugando— **era falso**, y la medición lo
> desmiente. Ojo con el matiz: un juego en *ventana sin bordes* sí tiene borde
> para Hyprland, y ahí el giro sigue corriendo.

> **El giro se para al recargar la config y no vuelve solo.** Tras un
> `hyprctl reload` (o `SUPER+SHIFT+R`) la animación queda puesta pero detenida
> hasta que **cambias el foco** de ventana. Si alguna vez te parece que el borde
> dejó de moverse, no está roto: pulsa `SUPER + flecha` y arranca.
>
> Para apagarlo del todo:
> `hyprctl keyword animation 'borderangle,0,80,giro,loop'`.

> **`hyprctl reload` contesta `ok` aunque la config tenga errores**, y el ajuste
> simplemente no se aplica sin decir nada. Por eso existe
> `hypr/scripts/recargar.sh` (`SUPER+SHIFT+R`): recarga, mira `configerrors` de
> verdad y además comprueba dos incoherencias que son config válida pero no hacen
> nada — el giro sin degradado, y `rounding` con `gaps_in = 0`.

---

## La barra

Cuatro instancias de waybar: la barra de arriba, el dock de abajo y una
línea-tirador para cada una. La barra en sí es **invisible** — solo flotan los
iconos, y la pastilla violeta de cada módulo aparece al pasar el puntero. El
auto-ocultado lo lleva `waybar-autohide.py`.

Ese script además **vigila y relanza**: si una de las cuatro instancias se cae,
la vuelve a levantar. Si se cae una y otra vez —una config rota, un módulo que
revienta al arrancar—, se rinde después de cinco intentos en un minuto y **avisa
por notificación**, en vez de quedarse lanzando procesos en bucle. La otra barra
sigue funcionando y el demonio no se apaga.

> Esto era el fallo de **«pulso `SUPER+SHIFT+C` y las barras se van para
> siempre»**. El bucle terminaba en `if not all(bar.alive()): cleanup()`: una
> waybar caída mataba a las otras tres y al propio demonio, y ya no quedaba
> nadie que las levantara — ni el atajo de reinicio servía, porque lo primero
> que hace es hablar con el demonio. La única salida era cerrar sesión, que es
> cuando `exec-once` vuelve a correr. Lo cubre
> `tests/unidad/barras-supervisor.sh`.

Y **solo manda un demonio a la vez**: al arrancar echa a cualquier otro que esté
gobernando el mismo escritorio, y si el suyo propio se queda sin Hyprland —cerrar
sesión no lo mata, porque nace con `setsid`— se aparta a los 60 s llevándose sus
barras.

> Ese barrido no es a ciegas: solo se lleva por delante a un duplicado de la
> propia sesión o a un huérfano —uno cuyo Hyprland ya no contesta—. Si tienes
> **dos sesiones de Hyprland vivas a la vez** con el mismo usuario (dos TTY, o un
> cambio rápido de usuario), cada una conserva sus barras **y sus órdenes**: el
> canal por el que se le habla al demonio lleva la firma de la sesión en el
> nombre, así que un `SUPER+C` va siempre a la sesión desde la que lo pulsas.

Las órdenes se mandan con `hypr/scripts/barras.sh`, que es lo que hay detrás del
atajo y de las dos líneas-tirador:

```sh
hypr/scripts/barras.sh show            # saca la barra de arriba
hypr/scripts/barras.sh show dock:show  # las dos, que es lo que hace SUPER+C
```

Existe en vez de un `echo` al FIFO por tres razones, y las tres han mordido aquí:
la ruta ya no es fija (lleva la firma de la sesión), escribir en un FIFO se
bloquea si nadie lee —así que va con `timeout`, o un click colgaría la barra—, y
sobre todo porque **`echo x > ruta-que-no-es-un-FIFO` crea un fichero normal y
sale con 0**: el atajo parecía funcionar y no hacía nada. Ahora avisa por
notificación, que es la única forma de enterarse (waybar se traga el `stderr` de
los `on-click`).

> Esto era el fallo de **«las barras no se ocultan, se ven sobre el bloqueo y al
> desbloquear salen dobles»**. Parecen tres cosas y era una: un demonio de una
> sesión anterior seguía vivo, y como **`WAYLAND_DISPLAY` se reutiliza entre
> sesiones**, sus cuatro waybar se dibujaban sobre la sesión nueva. No se
> ocultaban porque, sin poder hablar con su Hyprland, veía siempre «escritorio
> vacío»; y el `lock` de la pantalla de bloqueo llegaba al *otro* demonio, que
> solo mata las suyas. Lo cubre `tests/unidad/barras-huerfanas.sh`.
>
> Si alguna vez vuelve a pasar, se mira así: `pgrep -af waybar-autohide.py` (debe
> salir **uno**) y `ls -l /proc/<pid>/fd | grep fifo` — un `(deleted)` ahí es un
> demonio sordo, que no recibe ninguna orden.

Reparto: a la izquierda los sensores (velocidad, temperatura, CPU, memoria); en
el centro el reloj y los siete escritorios; a la derecha volumen, red,
notificaciones y bandeja.

### La velocidad de internet

A la izquierda del todo, `↓ 252.9kB/s  ↑ 5.8kB/s`. Es una **segunda instancia
del módulo `network`** de waybar (`network#velocidad`), no un script: el módulo ya
calcula el ancho de banda, solo estaba escondido en el tooltip. La instancia de la
derecha sigue enseñando la IP.

No se le fija `interface` a propósito — waybar toma sola la de la ruta por
defecto, así que sigue funcionando si cambias de cable o pasas a wifi.

> **`min-width` en el CSS no es cosmético.** Las cifras cambian de ancho todo el
> rato (`0 B` → `12.4 MB`), y sin un hueco reservado el módulo crece y encoge,
> **empujando de lado a todos los sensores de su derecha** varias veces por
> segundo.

> Dos detalles que se pagan si no se saben: los campos `bandwidth*` **ya traen la
> unidad por segundo** (`252.9kB/s`), así que añadir `/s` da `kB/s/s`. Y el
> `interval` **es también la ventana de promediado**, porque waybar calcula la
> velocidad entre dos lecturas; por debajo de 2 s las cifras saltan demasiado
> para leerlas.

---

## Notificaciones

**mako**, del repo oficial. Es quien atiende `org.freedesktop.Notifications` por
D-Bus: sin un demonio, todo lo que mande `notify-send` desaparece en silencio,
que es como estuvo este escritorio hasta ahora.

Se eligió frente a dunst, swaync y fnott. **dunst** quedó fuera por arrastrar
librerías de X11 (`libxinerama`, `libxrandr`, `libxss`) en un escritorio Wayland
puro. **swaync** es el más completo —trae panel de historial— pero pide `gtk4`,
`libadwaita`, `granite7` y `gvfs`: los toolkits de GNOME y de elementary enteros
para dibujar unos globos. mako usa cairo y pango, que ya estaban.

La pega de mako era que su config no es CSS y no tiene variables, así que el
violeta acabaría escrito por segunda vez. Se resolvió extendiendo
`gen-colores.py`: ahora emite también `mako/colores`, y `mako/config` lo trae con
`include=`.

> **El `include` va AL FINAL de `mako/config`, y no es un capricho.** En mako las
> opciones globales tienen que ir antes de la primera sección `[criterio]`. Como
> el archivo generado trae secciones, cualquier opción global escrita después se
> leería como parte de la última sección — sin dar ningún error. Si añades
> secciones a mano, van después del `include`.

**Se arranca por su unidad de systemd, no con `uwsm app --` como el resto.** Es
deliberado: `uwsm` le daría un *scope* propio, y `lib/congelar.py` congela los
scopes al bloquear la pantalla. Con mako congelado, cualquier app que mandara una
notificación se quedaría esperando una respuesta de D-Bus que no llega. Como
`.service` cae en `app.slice` y el bloqueo no lo toca.

Las notificaciones son translúcidas (`#1a0830eb`) con **blur de Hyprland** encima,
así que se leen sobre cualquier fondo:

```
layerrule = blur on,          match:namespace notifications
layerrule = ignore_alpha 0.3, match:namespace notifications
```

> **Dos trampas ahí:** el namespace de la capa es **`notifications`**, no `mako` —
> sale de layer-shell, no del nombre del programa. Y en esta versión los campos
> son `ignore_alpha` **con guion bajo** (`ignorealpha` da *"invalid field type"*) y
> `blur` **necesita valor** (`blur on`). Los dos fallos salen solo en
> `hyprctl configerrors`.

### El sonido

Una notificación que solo se ve no sirve de nada si estás jugando o mirando a
otra pantalla, así que mako suena al abrirla, con `on-notify=exec`. El sonido es
`message` del tema **freedesktop**: un toc corto y neutro, elegido porque los más
largos cansan cuando llegan tres seguidas.

Lo reproduce `hypr/scripts/sonido-notificacion.sh`, **y no la línea de una sola
orden que sugiere el manual de mako** (`on-notify=exec mpv /usr/share/...`). Esa
línea cablea dos cosas que este repo no puede dar por hechas: el reproductor y el
fichero, que viene del paquete `sound-theme-freedesktop` y no es obligatorio. El
script busca lo que haya —`pw-play`, `paplay`, `ffplay`, `mpv`— y si no encuentra
nada se calla sin protestar, porque el aviso visual sigue funcionando igual.

```sh
hypr/scripts/sonido-notificacion.sh --revisar   # qué está usando, o por qué no suena
```

Ese `--revisar` existe por una razón concreta: **mako se traga los errores de
`on-notify`**. Si el comando falla, no aparece en el journal ni en ningún sitio —
te quedas sin sonido y sin nada que mirar.

> **`on-notify` se dispara igual en «no molestar».** Comprobado: `invisible=1`
> oculta la notificación pero **no** impide que corra el comando, así que sin
> hacer nada más el modo silencioso sonaría en cada aviso —lo peor de los dos
> mundos, porque además no verías qué ha llegado—. Por eso la sección
> `[mode=no-molestar]` lleva **`on-notify=none`** expresamente. Anular la opción
> desde la sección del modo sí funciona (también comprobado).

`pw-play` va el primero de la lista por ser el cliente nativo de PipeWire, que es
el servidor de audio de esta distro. **`aplay` no está en la lista a propósito**,
aunque casi siempre esté instalado: solo sabe WAV y estos ficheros son OGG.

Y mako **no espera** a que termine el sonido: medido, `notify-send` tarda 7 ms con
el sonido puesto, no los ~330 ms que dura el fichero.

### El módulo de la barra

`waybar/scripts/notificaciones.sh` devuelve texto, tooltip y **clase**; el color de
cada estado se decide en `style.css` a partir de esa clase, así que no hay ni un
color escrito en el script.

| Estado | Icono | Color | Por qué |
|---|---|---|---|
| Nada pendiente | campana de contorno | `$tenue` | "no tienes nada" no merece llamarte |
| Hay sin leer | campana rellena | `$amatista` | el color de la casa |
| No molestar | campana tachada | `$atencion` | no es un error, pero estar en silencio sin saberlo es como se pierden los avisos |

Clic izquierdo descarta, derecho conmuta "no molestar", central recupera.

> `makoctl list` **no devuelve JSON** pese al nombre: es texto para leer. Por eso
> el script cuenta con `grep` y no parsea nada.

> **Los glifos de la Nerd Font se escriben con escapes, no como caracteres.** Están
> en el rango de Uso Privado y, escritos tal cual, las herramientas de texto los
> aplastan: ya pasó dos veces en este repo — la última, la campana de "sin nada" y
> la de "hay pendientes" acabaron con el **mismo** codepoint y los dos estados se
> veían idénticos. En JSON van como `\uf063`; en Python, con `chr(0xf063)`.

---

## La pantalla de bloqueo

`SUPER+L` no lanza `hyprlock` a secas. `hypr/scripts/lock.sh`:

1. Guarda el escritorio en el que estás y salta a uno **vacío** (el 99).
2. **Mata** las barras (no las esconde: ver más abajo).
3. **Congela** las aplicaciones, menos los juegos y las terminales.
4. Enciende `misc:session_lock_xray` y bloquea.
5. Al desbloquear lo deshace todo con un `trap`, pase lo que pase.

**Por qué tanto lío.** Hyprland tiene `misc:session_lock_xray`, que deja ver lo
que hay debajo del bloqueo — con eso, el vídeo del fondo se ve **moviéndose** de
verdad detrás de la tarjeta, no una foto. Pero no enseña solo el fondo: enseña
*todo* lo que hay debajo. Con las ventanas y la barra puestas se leían por encima
del bloqueo el contenido de una ventana, los sensores, la hora y la IP. De ahí el
escritorio vacío y las barras muertas.

Y no vale con "esconder" la barra: en waybar esconder es bajarla de capa, la
superficie sigue existiendo, y con el escritorio vacío no hay nada que la tape.
Por eso el demonio tiene las órdenes `lock` / `unlock`, que la matan y la
levantan.

**El congelado** usa el *freezer* de cgroup v2 (`systemctl --user freeze`), que es
atómico y reversible. Qué se salva lo decide `lib/juegos.py` por capas:

1. Steam · 2. la base de datos de ananicy · 3. flatpaks con `Categories=Game`
· 4. lo que esté a pantalla completa

más `hypr/congelar-excepciones.json` para lo que se les escape. Las terminales
nunca se congelan, para no tirar sesiones SSH.

**Esto obliga a lanzar las apps con `uwsm app --`** (ya está puesto en el
lanzador, el dock y `SUPER+RETURN`). Sin eso, todas las apps caen en el mismo
cgroup que Hyprland y no hay forma de congelar una sin congelar el compositor.

Si algo se quedara congelado, desde cualquier terminal:

```sh
~/dotfiles/hypr/scripts/lib/congelar.py descongelar
```

> **Aviso para quien toque esto:** no ejecutes `hyprlock` a mano para probar. Te
> bloquea la sesión al instante y, si el proceso que lo lanzó muere, te quedas en
> la pantalla *"you locked your screen but the lockscreen app died"*, de la que
> solo se sale por otro tty. Para probar, un Hyprland anidado.

### Auto-bloqueo por inactividad

`hypr/hypridle.conf`, arrancado por su unidad de systemd desde `autostart.conf`:

| Inactividad | Qué pasa |
|---|---|
| 10 min | Bloquea, llamando al mismo `lock.sh` que `SUPER+L` |
| 12 min | Apaga el monitor (`dpms off`) |
| — | **No** suspende la máquina: es un escritorio que se queda con descargas y escaneos corriendo solos |

Va por systemd y no con `exec-once = hypridle` a pelo por el `Restart=on-failure`:
si el demonio se cayera, el auto-bloqueo dejaría de funcionar en silencio. Y como
es un `.service` y no un `.scope`, el congelado del bloqueo no puede congelar a
quien lo gobierna.

El fondo de pantalla en vídeo **no** lo estorba, aunque mpv lleve
`stop-screensaver=yes`: mpvpaper pinta con la API de render de libmpv, sin
ventana propia, así que nunca llega a crear un inhibidor. Lo que sí para el
contador son las apps que inhiben por D-Bus (un vídeo a pantalla completa en el
navegador), y eso es justo lo que se quiere.

> **`SUPER+SHIFT+D` enciende la pantalla.** Es un salvavidas, no un adorno:
> `hyprctl dispatch dpms` **sin argumento apaga el monitor**, Hyprland contesta
> `ok` tan tranquilo, y la pantalla no vuelve sola — se vive como si la PC se
> hubiera apagado sin apagarse. Con el DPMS apagado Hyprland sigue leyendo el
> teclado, así que el atajo funciona justo cuando no ves nada.
>
> Y solo el input **real** de hardware reinicia el contador de inactividad:
> `movecursor`, `sendshortcut`, `cyclenext` y `workspace` no cuentan, así que no
> sirven para probar el despertar desde un script.

---

## Los fondos pueden ser vídeo o imagen

Los dos los pinta el mismo mpvpaper. La diferencia es **una sola bandera**:
`--image-display-duration=inf`. Sin ella mpv enseña una imagen 5 segundos y luego
se queda en negro — el síntoma sería «puse un fondo y desapareció solo», que
cuesta relacionar con su causa. `wallpaper.sh` la añade mirando la extensión del
fichero al que apunta el enlace `current` (no la del enlace, que no tiene).

Importa porque casi todo lo que se descarga por ahí son imágenes: wallhaven.cc y
los repos de colecciones de fondos de GitHub no tienen vídeo. Por eso **tu
carpeta de imágenes es un módulo propio** en CeliuzPaper, igual que la de vídeos:
ahí es donde acaban de verdad los fondos que uno se baja. Y cualquier otra
carpeta se añade con el botón `＋`.

Las dos carpetas se preguntan al estándar XDG, así que salen con **el nombre que
tengan en tu idioma** — aquí `Vídeos` e `Imágenes`, en un sistema en inglés
`Videos` y `Pictures`, en alemán `Bilder`. No se adivina ningún nombre. Si las
dos apuntaran al mismo sitio, sale una sola pestaña.

Extensiones que se reconocen:

| | |
|---|---|
| Vídeo | `.mp4` `.mkv` `.webm` `.mov` `.avi` `.m4v` |
| Imagen | `.jpg` `.jpeg` `.png` `.webp` `.bmp` `.avif` `.jxl` |

Dos detalles que se notan al usarlo: la miniatura de una imagen **no** se saca
buscando un fotograma a los 3 segundos (ahí no hay nada que buscar, y saldría
vacía), y su ficha dice «imagen fija» en vez de inventarse una duración —
`ffprobe` le adjudica 0,04 s a un jpg, que no significa nada.

## La pantalla de inicio de sesión (SDDM)

La que sale al encender el equipo, antes de que exista tu escritorio. Es la
hermana de la pantalla de bloqueo: misma tarjeta violeta, mismo título, mismo
reloj y tu fondo en vídeo detrás. Vive en `sddm/celiuz/` y está escrita en QML.

**Es opcional y es lo único de este repo que pide `sudo`.** Un tema de SDDM no
tiene equivalente por usuario: tiene que copiarse a `/usr/share/sddm/themes`. Por
eso no se instala con el resto y hay que pedirlo:

```sh
./instalar.sh --sddm            # instalar (pide contraseña)
./instalar.sh --sddm --revisar  # ver qué haría, sin tocar nada ni pedirla
./instalar.sh --sddm-quitar     # quitarla y volver a la de siempre
```

Sin ejecutarlo, el escritorio funciona igual; solo te falta esa pantalla.

### Pruébala sin reiniciar

```sh
sddm-greeter-qt6 --test-mode --theme /usr/share/sddm/themes/celiuz
```

Abre una ventana normal, sin cerrar tu sesión ni tocar el arranque. **Hazlo antes
de reiniciar**: un tema roto deja el arranque sin pantalla de inicio de sesión.

> **Si algo saliera mal**, no estás encerrado: `Ctrl+Alt+F2` te da una consola,
> entras con tu usuario y `sudo rm /etc/sddm.conf.d/10-celiuz.conf` deja SDDM
> como estaba. Al reiniciar vuelve su pantalla de fábrica.

### Nunca se queda en negro

Un tema que da por hecho que el vídeo existe deja al que clona el repo mirando
una pantalla negra sin campo de contraseña, o sea fuera de su propio sistema. Por
eso el fondo baja tres escalones solo:

| Hay | Se ve |
|---|---|
| `fondo.mp4` | el vídeo, como en tu escritorio |
| solo `fondo.jpg` | un fotograma quieto |
| nada | un degradado sacado de `colores.conf` |

El último no depende de ningún fichero, de ningún códec ni de ninguna GPU. **Un
clon recién bajado no trae vídeo** —los vídeos no se versionan, pesan— y aun así
la pantalla se dibuja entera y te deja entrar.

Lo mismo con el resto: si `qt6-multimedia` no está instalado, se pierde el vídeo
y nada más; si el sistema no ofrece apagar, ese botón no aparece en vez de fallar
al pulsarlo; si nunca ha entrado nadie y SDDM no recuerda ninguna cuenta, se coge
la primera de la lista; y si no hay ninguna, sale un campo para escribirla.

### El fondo del arranque se actualiza solo

Cambias de fondo con CeliuzPaper y el del arranque cambia con él. Sin comandos y
**sin pedirte la contraseña ni una vez**.

Costó llegar aquí, y el porqué importa. El greeter corre como el usuario `sddm`,
que **no puede leer tu carpeta personal** (está a 700), así que el vídeo no puede
leerse de `~`. La primera versión lo copiaba dentro del tema, en `/usr/share`… que
es de root. Consecuencia: cada cambio de fondo obligaba a pasar `--sddm` a mano y
teclear la contraseña, y quien cambia de fondo a menudo se quedaba con un login
desactualizado para siempre. La conclusión de entonces —«hacerlo automático sería
una app gráfica pidiendo sudo»— era falsa: había una tercera vía.

**La vuelta que se le dio.** `--sddm` crea **una sola vez** una carpeta
compartida y deja los dos ficheros del tema como enlaces a ella:

```
/usr/share/sddm/themes/celiuz/fondo.jpg ─┐
/usr/share/sddm/themes/celiuz/fondo.mp4 ─┴─> /var/lib/sddm-celiuz/
                                              (tuya, la lee el grupo sddm)
```

La carpeta es `2750`, de tu usuario y del grupo `sddm`. **El setgid es la pieza
clave**: hace que los ficheros que crees dentro nazcan con ese grupo, y por eso
el greeter puede leerlos. Sin él nacerían con tu grupo y el greeter se
encontraría un permiso denegado, que en el arranque se ve como «el fondo no
sale» y ninguna explicación más.

A partir de ahí, escribir el fondo del login es escribir en una carpeta tuya:
cero privilegios. Lo hace `hypr/scripts/sddm-fondo.sh`, y lo llama
`lib/wallpapers.py` desde `aplicar()` — el único punto por el que pasan todos los
caminos (CeliuzPaper, `--set`, `--random`, `set-wallpaper.sh`). Enganchado en
cualquier otro sitio se quedaría alguno fuera.

**No se espera a que termine.** Reescalar cuesta unos 8 segundos medidos (4K a
1080p), así que se lanza en segundo plano con `nice`: tu fondo cambia al instante
como siempre y el del login se pone al día por detrás. Además lleva una huella
(origen + fecha + resolución) para no reencodear el mismo fondo dos veces, y un
`flock` para que fijar tres fondos seguidos no deje tres ffmpeg peleándose.

```sh
hypr/scripts/sddm-fondo.sh --revisar   # qué hay puesto y si está al día
hypr/scripts/sddm-fondo.sh --forzar    # rehacerlo aunque parezca al día
SDDM_SEGUNDOS=60 ./instalar.sh --sddm  # más de 30 s de vídeo
```

Se reescala a **tu** pantalla y se recorta a 30 segundos: en `/usr/share` —o en
`/var/lib`— no tiene sentido dejar 700 MB de vídeo para una pantalla que se ve
diez segundos. La huella incluye la resolución, así que **cambiar de monitor
también lo rehace**.

> **Los temporales se llaman `fondo.nuevo.jpg`, no `fondo.jpg.nuevo`.** ffmpeg
> elige el formato de salida **por la extensión**: con `.nuevo` al final responde
> *«Unable to choose an output format»* y no escribe nada. Como esto corre en
> segundo plano con el stderr silenciado, el síntoma era exactamente que no
> pasaba nada. Este repo ya había tropezado con lo mismo en la pantalla de
> bloqueo (`lock-bg.tmp.jpg`). Lo vigila `tests/unidad/sddm-fondo.sh`.

### Ajustes

En `theme.conf`, sin tocar QML: el título (`彼岸花` es el del autor, pon el tuyo),
las fuentes, el formato de la fecha, cuánto oscurece el velo y si quieres ver la
lista de cuentas aunque solo haya una. Borrar una línea no rompe nada: cada
opción lleva su valor de fábrica dentro del QML.

Los nombres de día y mes **salen en el idioma del sistema**, el de
`/etc/locale.conf` —que es el que ve el greeter, no el tuyo—. Aquí no hay ningún
idioma cableado, por la misma razón que no lo hay en el reloj de la barra.

### Requisitos

`qt6-multimedia` y `qt6-multimedia-ffmpeg`, los dos en los repos oficiales. El
instalador comprueba que estén, que SDDM esté instalado **y habilitado**, y que no
tengas ya un `Current=` en `/etc/sddm.conf` que ganaría sobre el nuestro. Lo dice
todo antes de tocar nada.

La configuración se escribe en `/etc/sddm.conf.d/10-celiuz.conf`, un fichero
propio: **no se toca tu `/etc/sddm.conf`**, que puede tener cosas tuyas.

---

## Pruebas

```sh
./tests/run.sh              # todas
./tests/run.sh bloqueo      # solo las que lleven ese texto en el nombre
```

**No hacen falta ni Hyprland corriendo, ni Steam, ni un monitor concreto.** Cada
prueba se monta un `$HOME` desechable, así que dan el mismo resultado en el
equipo del autor que en uno recién clonado. Sirven desde un TTY o por SSH.

| Prueba | Qué cubre |
|---|---|
| `e2e/bloqueo` | la secuencia entera de la pantalla de bloqueo |
| `e2e/fondo` | con qué banderas se lanza el fondo (vídeo vs. imagen) |
| `unidad/pantalla` | detección de pantalla y medidas derivadas |
| `unidad/fondos` | de dónde salen los fondos y qué se reconoce |
| `unidad/generados` | dock y paleta: que lo generado cuadre |
| `unidad/maquina` | portátil vs. sobremesa, y que el orden de carga no se rompa |
| `unidad/portabilidad` | que no vuelva a colarse la ruta `~/dotfiles` en el código |
| `unidad/teclas` | que «no puedo saber si SUPER está pulsada» no se confunda con «no lo está» |
| `unidad/sddm-fondo` | que el fondo del login se rehaga solo, y que no se marque como hecho si falló |

### Cómo se prueba algo que te puede echar de tu sesión

La pantalla de bloqueo no se ejecuta **ni una vez**. Se pone en el `PATH` un
ejecutable falso con su mismo nombre que solo apunta cómo se le llamó y sale con
el código que le digamos. Con eso se comprueba que mide la pantalla, que guarda y
restaura tu escritorio, que enciende el xray y **lo devuelve**, que relanza el
bloqueo si se cae, y que aunque se agoten los intentos el `trap` lo deshace todo.

Lo mismo con `wallpaper.sh`, que empieza matando mpvpaper: ahí los falsos son
`pkill`, `pgrep` y `setsid`, y la prueba comprueba además que **tu** mpvpaper
sigue siendo el mismo proceso al terminar.

Cada prueba acaba comparando una huella de `~/.cache/celiuzpaper` de antes y de
después: si algo se escapara del corralito, lo canta.

**Lo que no cubren: el aspecto.** Que una capa GTK se dibuje donde toca o que un
icono salga centrado sigue necesitando un Hyprland anidado y una captura. Para
eso está `tests/anidado.sh`, que no es una prueba sino una herramienta:

```sh
./tests/anidado.sh hyprctl configerrors   # lo levanta, ejecuta eso y recoge
./tests/anidado.sh                        # se queda abierto; Ctrl+C lo tumba
```

Levanta un Hyprland **anidado que no puede tocar tu sesión**: `$HOME`
desechable, una copia del repo enlazada igual que la enlaza `instalar.sh`,
`autostart.conf` vaciado y su propio `$XDG_RUNTIME_DIR`. Al salir barre lo que
quedara vivo con la firma de esa instancia y borra la casa.

Lo de vaciar `autostart.conf` no es exceso de celo: los `exec-once` de verdad
matan por **nombre de proceso** (`pkill -x mpvpaper`) y arrancan unidades del
usuario (`systemctl --user start hypridle`), y ni el nombre ni las unidades
entienden de `$HOME`. Un anidado levantado a pelo te deja el escritorio real sin
fondo. Ese es también el límite del corralito: si ahí dentro lanzas tú algo que
mate por nombre, se llevará lo de fuera igual.

---

## La pantalla, y por qué nada va escrito en píxeles

`hypr/scripts/lib/pantalla.py` responde a una sola pregunta —**qué pantalla hay
delante**— y de su respuesta salen las medidas del bloqueo y del selector de
fondos.

Existe por un fallo real. El velo que oscurece la pantalla de bloqueo tenía el
tamaño escrito a mano, `1920, 1080`. En la laptop (1366x768) hyprlock **no lo
recortó: lo reescaló**, y quedó un rectángulo oscuro de 1089x612 pegado a la
esquina de arriba a la izquierda, con un escalón bien visible entre la zona
oscurecida y la clara. En el sobremesa no se notaba porque allí el número
coincidía con la resolución.

```sh
hypr/scripts/lib/pantalla.py            # qué hay y qué medidas salen
hypr/scripts/lib/pantalla.py --json     # todo, para otro script
hypr/scripts/lib/pantalla.py ancho      # un dato suelto
```

Tres cosas que conviene saber:

- **Se mide en caliente, no se genera al instalar.** Un fichero escrito en la
  instalación se queda viejo en cuanto cambias de monitor o conectas un
  proyector. Preguntándolo al arrancar, clonar el repo y usarlo es lo mismo.
- **Los datos salen de Hyprland**; si no hay sesión (instalando desde un TTY) se
  leen de `/sys/class/drm`, y en último caso se asume 1920x1080. Nunca se queda
  sin número.
- **Lo que puede ir en porcentaje, va en porcentaje.** El velo del bloqueo es
  `size = 100%, 100%`, que hyprlock mide contra la salida. Las medidas
  calculadas son solo para lo que no admite porcentaje, como el tamaño de fuente.

### Por qué el bloqueo trae sus medidas por duplicado

`hyprlock.conf` define las medidas de 1080p **y justo después** carga las de tu
pantalla, que pisan a las primeras (hyprlang deja redefinir una variable y gana
la última). Parece redundante y no lo es: si el fichero generado faltara —cache
borrada, primer arranque, un fallo al medir— hyprlock avisa del `source` que no
encuentra pero **sigue**, con los valores de fábrica.

Con las medidas solo en el fichero generado, ese mismo fallo dejaría la config
llena de variables sin definir. Una pantalla mal proporcionada es un defecto; un
bloqueo que no dibuja es quedarse fuera de la sesión.

---

## Archivos generados

No se editan a mano; los escribe un script y llevan cabecera avisándolo:

| Archivo | Lo genera |
|---|---|
| `waybar/dock.jsonc` | `hypr/scripts/gen-dock.py` |
| `waybar/dock-icons.css` | `hypr/scripts/gen-dock.py` |
| `waybar/colores.css` | `hypr/scripts/gen-colores.py` |
| `mako/colores` | `hypr/scripts/gen-colores.py` |
| `sddm/celiuz/Colores.qml` | `hypr/scripts/gen-colores.py` |
| `/var/lib/sddm-celiuz/fondo.{mp4,jpg}` | `hypr/scripts/sddm-fondo.sh`, solo, al cambiar de fondo |
| `/etc/sddm.conf.d/10-celiuz.conf` | `instalar.sh --sddm` |
| `~/.cache/celiuzpaper/lock-fondo.conf` | `hypr/scripts/lock.sh` |
| `~/.cache/celiuzpaper/lock-medidas.conf` | `hypr/scripts/lock.sh` (desde `lib/pantalla.py`) |
| `hypr/conf/local.conf` | `instalar.sh` |
| `waybar/local.jsonc` | `instalar.sh` (desde `waybar/derecha.jsonc`) |

**`colores.css`, `mako/colores` y `Colores.qml` sí se versionan**: salen de la
paleta y son iguales en cualquier equipo. Los del dock, `local.conf` y
`local.jsonc` **no**, porque dependen de la máquina — los crea `instalar.sh`. Los dos de `~/.cache`
tampoco: se rehacen en cada bloqueo. Y los tres de fuera del repo (el fondo del
arranque y el drop-in de SDDM) los pone `--sddm`, que es lo único que pide root.

Además, fuera del repo a propósito:

| Archivo | Qué guarda |
|---|---|
| `~/.config/celiuzpaper/carpetas.json` | las carpetas de fondos que añadiste tú |

Es de tu equipo, no del repo: en otra máquina esas rutas no existirían.

---

## Estado

**Hecho:** monitores, teclado (dos distribuciones), barra y dock con
auto-ocultado, lanzador, cambiador de escritorios (`SUPER+TAB`), fondo en vídeo o
imagen con su selector propio, capturas, calendario, monitores del sistema,
pantalla de bloqueo y auto-bloqueo, pantalla de inicio de sesión, el aspecto
(paleta, decoración y animaciones), adaptación a la pantalla que haya,
portabilidad a cualquier ruta de clonado, y pruebas automáticas.

**Pendiente, por orden de valor:**

| | Qué | Por qué importa |
|---|---|---|
| 1 | **`env.conf` para Nvidia — está vacío** | Es lo que más puede afectar jugando en Wayland. Ojo: muchas variables que circulan por los foros llevan años obsoletas en 0.56 y algunas empeoran el rendimiento; hay que comprobar cuáles hacen falta de verdad, no copiar listas. Pista: el Hyprland anidado sobre esta NVIDIA solo levanta con `AQ_NO_MODIFIERS=1`. |
| 2 | **Teclas multimedia y la perilla del teclado** | No hay ni un bind de volumen en toda la config. Es rápido. |
| 3 | **Historial del portapapeles** | `SUPER+SHIFT+V` ya está reservado. Candidato: cliphist. |
| 4 | **Reglas de ventana del flujo de seguridad** | VMs, Burp… Hay que decidir antes qué herramientas se usan de verdad. |
| 5 | **El login (SDDM) y el TTY siguen en `latam`** | `/etc/vconsole.conf` gobierna la pantalla de login, así que la contraseña al encender se teclea con otra distribución que la de la sesión. Es un cambio de sistema, fuera del repo. |

Menores, ya ofrecidos y no pedidos: regla de sudo estrecha para
`ir-a-windows.sh`, `windowrule` para que su terminal salga flotante, atajo propio
para CeliuzPaper, y un botón de «añadir comando a mano» en el gestor del dock
(para AppImages y binarios sueltos, que ningún escaneo de `.desktop` cubre).

Para retomar el trabajo hay un **`SIGUIENTE.md`** con el detalle de cada
pendiente y las pistas que ya se encontraron.

> **Aviso de futuro:** Hyprland avisa al arrancar de que *el formato `.conf`
> dejará de estar soportado en la 0.57*. Todo este repo está en hyprlang `.conf`
> por decisión explícita (poder seguir la wiki y los foros sin traducir), así que
> antes de esa versión habrá que decidir: quedarse anclado, o portar a Lua.
