# Celiuz_CachyOS — dotfiles de Hyprland

Mi escritorio de **Hyprland sobre CachyOS** (base Arch), escrito desde cero: sin
dotfiles ajenos, sin shells prearmadas y sin la config que trae la distro. La
config de Hyprland está en **Lua** (`hyprland.lua`, desde el 2026-09-25): la 0.56
la trae nativa y la 0.57 retira la de hyprlang (`.conf`). Se pasó módulo a módulo
y se verificó contra la vieja opción por opción; ver «La config es Lua» abajo.

No es un tema para instalar y ya: es *mi* escritorio, con cosas hechas a medida
(el auto-ocultado de las barras, el dock generado, el panel de calendario, la app
del fondo de pantalla, la pantalla de bloqueo). Si te sirve algo, cógelo suelto.

---

## Qué hay dentro

| Carpeta | Qué es |
|---|---|
| `hypr/` | Hyprland. `hyprland.lua` solo carga los módulos de `lua/`. Aquí viven también `hyprlock.conf` y `hypridle.conf`, que siguen en hyprlang (la 0.57 no les afecta). |
| `hypr/lua/` | La config de Hyprland, un módulo por asunto: monitores, teclado, atajos, reglas de ventana… `colores.lua` y `maquina.lua` van los primeros porque los demás los usan, `teclado-laptop.lua` solo si estás en un portátil, y tu `personal.lua` el último. |
| `hypr/conf/` | `colores.conf`, **la paleta** (la leen la config Lua, hyprlock y `gen-colores.py`), y la config vieja en hyprlang, **congelada de puente** hasta que las dos máquinas entren con Lua. No se edita. |
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
- **`avisos.py`** — el historial de notificaciones. Un grabador escucha el bus y
  apunta todo lo que pasa por pantalla, con su hora; `SUPER + H` lo saca. Se
  borra al cerrar sesión salvo lo que apartes a mano. Ver su sección abajo.
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
- **`gen-colores.py`** — pasa la paleta de `colores.conf` a los cuatro sitios que
  no saben leer hyprlang: el CSS de waybar, la config de mako, el QML del tema de
  SDDM y el marcado Pango del bloqueo. Es lo que hace que el violeta esté escrito
  en un solo sitio.
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
- **`bluetooth.py`** — los auriculares Bluetooth se conectan solos al que tengas
  encendido, y **de uno en uno**: con uno puesto, los demás no pueden entrar
  hasta que lo sueltes. Ver su sección abajo.
- **`teclado.py`** — la sesión lleva dos distribuciones (us y latam). Este avisa
  por notificación de cuál hay puesta: al arrancar, y cada vez que la cambias con
  `SUPER + DEL`. Ver su sección abajo.
- **`sesion.sh`** — el menú de salida de `SUPER + SHIFT + P`: bloquear,
  suspender, cerrar sesión, reiniciar o apagar, y lo que no tiene vuelta atrás
  **pregunta otra vez**. Ver su sección abajo.
- **`portapapeles.py`** — el historial del portapapeles (`SUPER + SHIFT + V`),
  con cosas **fijadas** (hasta cerrar sesión) y **guardadas** (para siempre).
  Ver su sección abajo.
- **`osd.sh`** — las teclas de volumen, micro y brillo hacen el cambio **y lo
  enseñan**: un aviso abajo con el valor y una barra.
- **`lib/hypr.py` + `lib/hypr.sh`** (y `despachar.sh`) — le hablan a Hyprland en
  el idioma de su config: con la de Lua, `hyprctl dispatch workspace 3` y
  `hyprctl keyword` dan **error**. Ver «La config es Lua».

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

Y para grabar la pantalla (`SUPER + R`), que va aparte por lo mismo:

```sh
sudo pacman -S wf-recorder
```

Y el Bluetooth, **solo si el equipo tiene** (sin adaptador el icono de la barra
no sale y no hace falta nada):

```sh
sudo pacman -S bluez bluez-utils bluetui
sudo systemctl enable --now bluetooth
```

Notas:

- **Hyprland 0.56 o más nuevo**: la config es Lua, y una versión anterior no la
  sabe leer. El instalador lo comprueba.
- **`lua`** solo lo usan las pruebas (`tests/unidad/config-lua.sh` ejecuta la
  config sin Hyprland); si no está, esa prueba se salta y lo dice.
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
- **`wf-recorder`** es lo único que hace falta para grabar la pantalla; el
  instalador lo comprueba aparte por la misma razón que las teclas de función. Si
  falta, `SUPER + R` sí avisa —el script lo mira antes de nada—, pero el aviso
  necesita que el demonio de notificaciones esté vivo.
- **`bluetui`** es lo que abre el clic en el icono del Bluetooth: buscar,
  emparejar y conectar, en la terminal flotante, como `nmtui` en la red. Está en
  el repo oficial `extra`. El instalador lo pide solo si hay un adaptador.

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
- Comprueba que tu Hyprland lee Lua (**0.56 o más nuevo**) y, si hay sesión
  abierta, te dice si aún corre con la config vieja (hasta que cierres sesión).
- Instala CeliuzPaper (binario, `.desktop` e icono) y refresca las cachés.
- **Crea el dock de esta máquina** con tu terminal y tu navegador
  predeterminado, averiguados en el sistema. Solo esos dos: el resto los pones
  tú con el clic derecho sobre cualquier icono del dock. El repo no trae apps de
  nadie a propósito — las del autor serían iconos muertos en tu equipo.
- Escribe `hypr/lua/local.lua` con lo de esta máquina: tu terminal (la de
  `SUPER + RETURN`), si es un portátil y la distribución del teclado. (Y el
  `hypr/conf/local.conf` de la config vieja, mientras exista el puente.)
- Crea `hypr/lua/personal.lua`, **tu** fichero. Si tenías un
  `hypr/conf/personal.conf` con algo dentro, lo **traduce** a Lua; lo que no
  sepa traducir lo deja comentado y te avisa.

Cuando termine, **cierra la sesión y vuelve a entrar**: lo que arranca con la
sesión (`lua/autostart.lua`) solo corre al arrancarla, así que recargar con
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

## La config es Lua (y el puente con hyprlang)

Hyprland 0.56 trae la config en **Lua** y avisa al arrancar de que la de
hyprlang (`hyprland.conf`) **deja de estar soportada en la 0.57**. Esta se pasó
el 2026-09-25: los mismos módulos, con sus mismos comentarios, en `hypr/lua/`.

**Cómo se comprobó que es la misma.** Se levantaron cuatro Hyprland anidados
—config vieja y nueva, como portátil y como sobremesa— y se compararon **las 354
opciones** una a una, los atajos (tecla, modificadores, banderas y lo que
hacen), las animaciones y sus curvas, los monitores, el teclado de cada
dispositivo y las reglas de ventana (abriendo ventanas de verdad con cada
clase). Iguales. Arrastrar y redimensionar con el ratón se probó a mano, con
un ratón de mentira por uinput.

**Lo que cambia para ti:**

- Lo tuyo va en `hypr/lua/personal.lua` (el instalador te traduce tu
  `personal.conf`), y lo de la máquina en `hypr/lua/local.lua`.
- **`hyprctl` habla otro idioma** con la config en Lua, y esto es lo que más
  puede morder: `hyprctl dispatch workspace 3` y `hyprctl keyword ...` dan
  **error**. En Lua es `hyprctl dispatch 'hl.dsp.focus({ workspace = 3 })'` y
  `hyprctl eval 'hl.config({ misc = { ... } })'`. Los scripts del repo pasan por
  `lib/hypr.py` / `lib/hypr.sh`, que preguntan en qué idioma está la sesión y lo
  dicen en ese; desde un bind o una terminal, `hypr/scripts/despachar.sh
  workspace 3` hace lo mismo.
- `hyprctl getoption` también devuelve otros campos (`"bool": true` en vez de
  `"int": 1`, `"gradient"`/`"css"` en vez de `"custom"`). Quien lo lea tiene que
  mirar los dos.
- Los errores de la config salen igual en `hyprctl configerrors` y en
  `SUPER + SHIFT + R`, con fichero y línea, y **el resto se carga igual**: un
  módulo roto no te deja sin atajos.

**El puente.** Los `.conf` de `hypr/conf/` se quedan **congelados** una
temporada, y no por nostalgia: Hyprland recarga solo cuando cambian sus
ficheros, y una sesión abierta con la config vieja **que los viera desaparecer
se quedaría sin atajos** (medido en un anidado: de 62 a 6, y encima regeneró un
`hyprland.conf` de fábrica dentro del repo). Con el puente, un `git pull` con la
sesión abierta no rompe nada, y al volver a entrar Hyprland ya coge el `.lua`
(lo prefiere). Cuando las dos máquinas hayan entrado con Lua, el puente se borra.
**No se editan**: todo lo nuevo va en `hypr/lua/`.

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
| `SUPER + H` | Historial: todo lo que llegó en esta sesión, con su hora |
| `SUPER + SHIFT + R` | Recargar la config (y avisar de verdad si falla) |
| `SUPER + L` | Bloquear la pantalla |
| `SUPER + SHIFT + D` | Encender la pantalla (rescate si se quedó en negro) |
| `SUPER + S` | Captura de una zona |
| `SUPER + SHIFT + S` | Captura de la pantalla entera |
| `SUPER + ALT + S` | Captura de la ventana que tengas delante |
| `SUPER + R` | Grabar una zona en vídeo (la misma tecla la para) |
| `SUPER + ALT + R` | Grabar el monitor entero (la misma tecla lo para) |
| `SUPER + SHIFT + V` | Historial del portapapeles (Enter copia, Ctrl+F fija, Ctrl+G guarda, Ctrl+D borra) |
| Volumen, silencio, micro, brillo | Lo cambian **y enseñan** cómo queda (abajo, con una barra) |
| `SUPER + 1..7` | Ir al escritorio |
| `SUPER + SHIFT + 1..7` | Mover la ventana al escritorio |
| `SUPER + flechas` | Mover el foco |
| `SUPER + clic izq/der` | Mover / redimensionar flotantes |
| `SUPER + TAB` | Cambiar de escritorio manteniendo SUPER, viendo cada uno de verdad |
| `SUPER + SHIFT + TAB` | Lo mismo, hacia atrás |
| `SUPER + DEL` | Cambiar de distribución de teclado (us ⇄ latam) |
| `SUPER + SHIFT + P` | Menú de salida: bloquear, suspender, cerrar sesión, reiniciar, apagar (lo último pregunta otra vez) |

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

Los colores no están escritos en el script: lee `conf/colores.conf` (la paleta) en caliente y
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

La solución tiene tres partes, todas en `lua/input.lua`:

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

- Al arrancar la sesión (en `lua/autostart.lua`), diciendo con cuál
  empiezas y recordando el atajo.
- Cada vez que pulsas `SUPER + DEL`.

Dos detalles que no son adorno:

- El aviso de arranque **espera a que mako coja el bus** antes de mandarse.
  el arranque no garantiza orden, y una notificación mandada antes de que exista
  el demonio se pierde sin dejar rastro — justo el fallo que este script existe
  para no tener.
- Los avisos llevan la etiqueta `x-canonical-private-synchronous`, que mako
  entiende como *sustituye al anterior*: pulsar el atajo cuatro veces seguidas
  reescribe un aviso, no apila cuatro.

`teclado.py estado` imprime la activa en una línea, para la barra o para
cualquier otro script.

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
carga `lua/teclado-laptop.lua`, que corrige lo que haga falta.

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

Lo escribe `instalar.sh` en `hypr/lua/local.lua`, que no se versiona, y ahí se
puede cambiar a mano si te lo detectó mal:

```sh
hypr/scripts/lib/maquina.py layout      # latam,us
localectl list-x11-keymap-layouts       # los nombres válidos
```

`lua/maquina.lua` pone el valor de fábrica y solo lo pisa con lo que diga
`local.lua` si existe, así que quien clone el repo y arranque sin instalar tiene
teclado igual (y terminal: se la pregunta a `lib/apps.py`) — sin él se quedaría
sin teclado con el que arreglarlo.

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
> poner `hl.config({ input = { kb_options = "" } })` en tu `hypr/lua/personal.lua`. `./instalar.sh
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
motivo queda escrito dentro del `local.lua` generado. Cuando alguien reporte
«me detectó mal», es lo primero que hay que mirar.

### Por qué se decide al instalar y no al arrancar

Al revés que `pantalla.py`, que se mide en caliente. La diferencia: los monitores
cambian —conectas un proyector, giras la pantalla—, pero **la caja no**. Un
portátil no amanece siendo un sobremesa.

Con hyprlang esto obligaba a un truco —no tenía condicionales, así que «no
cargar nada» se escribía como «cargar un fichero vacío» (`conf/nada.conf`)—. En
Lua es un `if`: `instalar.sh` escribe `portatil = true` o `false` en
`local.lua`, y `hyprland.lua` carga `lua/teclado-laptop.lua` solo si toca.

Lo que no cambia es el **orden**, y ahí está el detalle que se puede romper sin
querer: son *correcciones* sobre `input.lua` y `keybinds.lua`, y gana el último
que habla. Cargarlo antes lo dejaría pisado, y el síntoma sería «puse el
fichero y no hace nada». Hay una prueba que lo vigila (`tests/unidad/maquina.sh`).

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

Está en `hypr/conf/colores.conf`, en hyprlang, y es **la única fuente**: la lee
la config Lua (`lua/colores.lua`, sin copiarla), la hace `source` hyprlock y la
reparte `gen-colores.py` a los demás. Por eso sigue en ese formato aunque la
config de Hyprland ya sea Lua.

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
| hyprlock, texto del campo | `hypr/conf/colores-pango.conf`, **generado** — ver abajo |
| waybar | `waybar/colores.css`, **generado** por `hypr/scripts/gen-colores.py` |

waybar es el raro: se estiliza con CSS de GTK, que no sabe leer un `.conf`. El
generador emite un `@define-color` por variable. Si cambias un color en
`colores.conf`, **vuelve a lanzar `gen-colores.py`** o la barra se queda con el
viejo; `gen-colores.py --check` avisa si están desincronizados.

Y hay un rincón de hyprlock que tampoco puede leer la paleta directamente: el
texto del campo de la contraseña (`placeholder_text` y `fail_text`) es **marcado
Pango**, y Pango quiere `#RRGGBB`, no el `rgba()` de hyprlang. Por eso el
generador emite además `hypr/conf/colores-pango.conf` con la paleta en ese
formato. Tú no tienes que tocarlo: **cambia el color en `colores.conf` y vuelve a
lanzar el generador**, como con todo lo demás.

> Si te asomas a ese fichero verás `$pango_tenue = ##8a7aa8`, con **dos**
> almohadillas. No es una errata: en hyprlang `#` abre un comentario, así que un
> color literal se escapa doblándola, y lo que le llega a Pango es `#8a7aa8`.
> Con una sola, la variable se queda vacía y el texto sale sin color, **sin dar
> ningún error**.

**Ninguno de los colores de la pantalla de bloqueo puede salirse de la paleta**,
y eso lo vigila `tests/unidad/paleta-bloqueo.sh`. Ahí quedan hexadecimales
escritos a mano por narices —hyprlang no sabe sacar «`$amatista` al 55%» de una
variable, así que una sombra translúcida hay que escribirla `rgba(b16cff8c)`—,
pero la parte del color tiene que ser la de alguna variable de `colores.conf`; el
alfa es libre. Sin esa prueba las copias se separan solas y no se nota: cuando se
escribió ya había dos, y la consecuencia era que quien clonara el repo y se
pusiera su propio tono se encontraba media pantalla de bloqueo con el violeta del
autor.

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
> comenta la línea `animar("borderangle", ...)` de `hypr/lua/animations.lua` (o
> ponla en tu `personal.lua` con `hl.animation({ leaf = "borderangle", enabled = false })`).

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

### Los workspaces son puntos

En el centro, junto al reloj, hay siete puntos: uno por workspace, los mismos que
`SUPER+1..7`. Se leen de un vistazo y sin números:

| | |
|---|---|
| punto apagado | workspace vacío |
| punto encendido | tiene ventanas |
| **pastilla** amatista | donde estás |

El activo es lo único que cambia de **forma** en toda la barra, que es lo que
permite encontrarlo sin leer nada. El número no desaparece del todo: sigue en el
tooltip, al posar el puntero.

> Si vas a tocar el tamaño de los puntos, mira antes
> `tests/unidad/barra-workspaces.sh`. En el CSS de GTK el alto de un punto solo
> se puede acotar con el margen vertical, así que sale de una resta contra el
> alto de la barra —`"height"` en `config.jsonc`— y los dos números viven en
> ficheros distintos. Moviendo uno solo, los puntos salen deformados y **no falla
> nada**: a 60 px de barra se convierten en cápsulas verticales y el activo en un
> círculo. La prueba existe para que eso se vea en rojo y no en tu escritorio.

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
> cuando el arranque vuelve a correr. Lo cubre
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

Lo mismo vale para el fondo y para la pantalla de bloqueo: el socket de mpvpaper
lleva la firma de la sesión, y ni el fondo ni el bloqueo se buscan ya «por
nombre». Antes, con dos sesiones vivas, arrancar el fondo en una **mataba el de
la otra**, y bloquear la pantalla teniendo la otra sesión bloqueada **no
bloqueaba nada** — salía creyendo que ya estaba puesto.

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
Bluetooth, notificaciones y bandeja.

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

## El Bluetooth

A la derecha de la red. Es el módulo de serie de waybar: el icono dice si está
apagado (tachado), encendido o conectado, y con algo conectado enseña su nombre
y su batería si la informa. **Solo se ilumina con algo conectado.** En un equipo
sin Bluetooth no aparece.

| | |
|---|---|
| clic | `bluetui` en una terminal flotante: buscar, emparejar, conectar (si no está instalado, te lo dice en vez de abrir una terminal que se cierra sola) |
| clic derecho | encender / apagar (y si lo apagó la tecla de modo avión, desbloquearlo) |
| clic central | **soltar el auricular que llevas**: entra el otro que tengas encendido |

### Los auriculares se conectan solos, y de uno en uno

Eso no es del módulo: es de `hypr/scripts/bluetooth.py`, que arranca con la
sesión. Tres reglas:

1. **Se conecta solo.** Con el Bluetooth encendido y ningún auricular puesto,
   llama a los emparejados uno detrás de otro, **el último que usaste primero**,
   y se queda con el primero que conteste — el que tengas encendido. Con dos
   encendidos gana el de la última vez.
2. **El cerrojo.** Con un auricular conectado, los demás **no pueden entrar**
   hasta que lo sueltes: ni llamando ellos, ni conectándolos tú desde `bluetui`.
   Si uno se cuela, se le echa y sale un aviso diciendo por qué.
3. **Soltar a mano no es una caída.** Si lo desconectas tú (clic central,
   `bluetui`, `bluetooth.py soltar`), no vuelve solo: se prueba con los demás y
   ese se queda quieto **hasta que apagues y enciendas el Bluetooth** o lo
   conectes tú. Si en cambio lo apagas, lo metes en el estuche o te alejas, se le
   vuelve a buscar.

O sea que **cambiar de auricular** es: enciendes el otro, clic central en el
icono, y entra el nuevo.

**Por qué hace falta un demonio.** BlueZ no persigue a nadie: *Trusted* solo
significa que acepta la conexión si el aparato la pide, y muchos auriculares no
la piden después de una desconexión desde este lado. Alguien tiene que llamarlos.

**Cómo sabe si lo soltaste tú.** No lo supone: BlueZ trae el motivo de cada
desconexión (`Local`, `Remote`, `Timeout`, `Suspend`…) en la señal
`Device1.Disconnected`. Solo `Local` cuenta como soltarlo, y solo si no fue el
propio cerrojo quien lo echó.

**Por qué el cerrojo lleva dos capas.** Los demás se **bloquean** (la propiedad
`Blocked` de BlueZ), y eso hace que el kernel rechace su llamada antes de que
llegue a nada, sin que el audio salte. Pero se midió que `Blocked` **no frena una
conexión pedida desde este lado**: con los auriculares bloqueados,
`bluetoothctl connect` se puso a buscarlos igual. Por eso además se echa en el
acto a cualquiera que se cuele.

**Lo que se toca y lo que no.** Solo auriculares y altavoces: lo que anuncia que
recibe audio (A2DP) o que hace de manos libres. El móvil habla los mismos
perfiles pero desde el otro lado, y ni él, ni un ratón, ni un teclado se
bloquean ni se llaman nunca. **Y un aparato que bloqueaste tú a mano no se toca**:
el demonio solo desbloquea lo que bloqueó él, y lo lleva apuntado.

### Si no quieres el cerrojo

Es un gusto, no una ley, y este repo lo usa más gente. Se apaga sin tocar nada
versionado, en `~/.config/celiuz/bluetooth.conf`:

```conf
cerrojo = no    # deja conectar varios a la vez (unos cascos y un altavoz)
auto = no       # no llamar a nadie: conectar es cosa tuya
```

Se relee solo al guardarlo, sin reiniciar nada. Sin ese archivo, los dos valen
`si`. Con `cerrojo = no` el demonio suelta lo que hubiera bloqueado y se limita
a conectar el primero que conteste; `bluetooth.py --ver` lo dice cuando no están
los de fábrica.

**Y si el equipo no tiene Bluetooth, no hay nada que apagar:** el icono no
aparece en la barra y el demonio se queda dormido esperando. Está comprobado
contra un BlueZ sin adaptador, no deducido del manual.

### Lo que se guarda

| Archivo | Qué | Por qué ahí |
|---|---|---|
| `~/.local/state/celiuz/bluetooth.json` | cuándo usaste cada auricular, y cuáles bloqueó el cerrojo | el `Blocked` de BlueZ se guarda en disco y sobrevive a un reinicio, así que la lista de quién lo puso también |
| `$XDG_RUNTIME_DIR/celiuz-bluetooth.json` | los que soltaste a mano | un reinicio los olvida a propósito |

Al salir de la sesión, al apagar el Bluetooth y al arrancar, el demonio suelta
todo lo que bloqueó y no haga falta. Si se cae, systemd lo levanta (es una
unidad transitoria, `celiuz-bluetooth`) y lo primero que hace es repasarlo.

### Si algo no cuadra

```sh
hypr/scripts/bluetooth.py --ver              # el estado y quién bloqueó a quién
journalctl --user -u celiuz-bluetooth -e     # lo que ha ido haciendo el demonio
bluetoothctl unblock <MAC>                   # soltar uno a mano
rfkill list bluetooth                        # si no se ve nada: ¿modo avión?
```

`bluetooth.py conectar` llama ya al primero que conteste, sin esperar la
siguiente ronda (que se va espaciando de 10 s a 60 s cuando no contesta nadie,
para no tener la radio buscando todo el rato: en un portátil suele ser la misma
tarjeta que la del wifi).

**Por qué no blueman.** Está en los repos oficiales, pero es GTK3 con su propio
aspecto (no coge la paleta), deja un applet corriendo y trae su propia lógica de
reconexión, que se pelearía con esta. Y un panel propio no compensa: lo difícil
no es la ventana sino emparejar (los PIN, las confirmaciones), y eso `bluetui`
ya lo hace bien.

---

## Las capturas

`SUPER + S` recorta una zona con el ratón, `SUPER + SHIFT + S` coge la pantalla
entera y `SUPER + ALT + S` la ventana que tengas delante. Las tres van a **dos
sitios a la vez**: al portapapeles, para pegarlas al instante, y a un archivo en
`~/Imágenes/capturas/`, para no perderlas si copias otra cosa después.

> **Entre soltar el ratón y disparar la foto hay un tercio de segundo de espera,
> y no es un descuido.** Cuando sueltas el botón, slurp —el que dibuja la
> selección— termina, pero **su capa no desaparece de golpe: Hyprland la
> desvanece**. Medido: entre 90 y 125 ms, pasando por 65 %, 55 %, 47 % y 39 % de
> opacidad. grim pide su fotograma mucho antes de eso, así que la captura salía
> con el relleno violeta de la selección y un trozo de su borde **dentro de la
> imagen** — un recuadro en medio de la foto, siempre, eligieras lo que
> eligieras. `SUPER + SHIFT + S` nunca lo sufrió, y esa fue la pista: ahí no hay
> slurp.
>
> El script espera a que Hyprland deje de listar la capa **y además** a que
> termine el desvanecido, que es lo que no se puede preguntar: ningún
> compositor avisa de que una animación acabó. Por eso el plazo es fijo.
>
> **Si tienes las animaciones apagadas, no se espera nada**: sin desvanecido, la
> capa se va con su proceso, y cobrar el plazo haría lento lo que en tu equipo
> es instantáneo.

---

## El menú de salida (SUPER + SHIFT + P)

Antes era un `exit` a secas, y rozarlo **cerró la sesión con todo abierto** más
de una vez. Ahora abre un menú (fuzzel, con la paleta de siempre):

| | |
|---|---|
| Bloquear | el mismo `lock.sh` de `SUPER + L` |
| Suspender | el bloqueo lo pone hypridle al dormir |
| Cerrar sesión | **pregunta otra vez** |
| Reiniciar | **pregunta otra vez** |
| Apagar | **pregunta otra vez** |

En la pregunta, **«No» es la primera línea**, y fuzzel preselecciona la primera:
un Enter por inercia —que es justo el accidente del que venimos— vuelve atrás en
vez de apagar. Escape cancela en los dos menús.

Cerrar sesión se le pide a **uwsm** si la sesión es suya (la de CachyOS), para
que las unidades de la sesión se apaguen en orden; si no, el `exit` de Hyprland.
Lo vigila `tests/unidad/sesion.sh`, con un fuzzel de mentira: nada se apaga de
verdad.

---

## El portapapeles (SUPER + SHIFT + V)

Lo que copias se apunta solo, texto o imagen, y `SUPER + SHIFT + V` lo saca en
un menú. Tres listas:

| | Dura | Para |
|---|---|---|
| **Historial** | 24 h, y como mucho 50 cosas (lo más viejo sale primero) | lo que vas copiando |
| **Fijados** 󰐃 | hasta cerrar sesión o apagar | lo que usas a cada rato; salen arriba del todo |
| **Guardados** 󰆓 | para siempre, aunque apagues | lo que quieres tener cualquier día |

En el menú (la ayuda sale escrita en la caja de búsqueda):

| Tecla | |
|---|---|
| `Enter` | lo copia (y ya puedes pegarlo) |
| `Ctrl + F` | lo fija; sobre algo fijado, lo **desfija** |
| `Ctrl + G` | lo guarda; sobre algo guardado, lo **quita** de guardados |
| `Ctrl + D` | lo borra de todas las listas (si era un guardado, avisa: no vuelve solo) |

Tras fijar, guardar o borrar, el menú se vuelve a abrir en el mismo sitio, para
que veas el cambio y sigas. Las imágenes salen con su **miniatura**.

**Lo que no se apunta nunca:** lo que un gestor de contraseñas marca como
secreto (KeePassXC y compañía: `wl-paste` lo avisa), el portapapeles vacío y lo
que pese más de 16 MB.

**Dónde vive cada cosa**, y por qué:

- El historial y los fijados, **en memoria** (`$XDG_RUNTIME_DIR`), en una
  carpeta con la firma de la sesión: por el portapapeles pasa de todo —códigos,
  direcciones, trozos de conversaciones— y guardarlo en disco sin pedirlo lo
  dejaría ahí después de apagar. Al arrancar, se barre lo de sesiones que ya no
  están.
- Los guardados, en `~/.local/share/celiuz/portapapeles/`: eso sí lo pediste tú.

Los números se cambian en `~/.config/celiuz/portapapeles.conf` (no se versiona,
se lee en cada copia):

```ini
maximo = 50     # cuantas cosas guarda el historial
horas = 24      # a las cuantas horas se olvida una
max_mb = 16     # lo que pese mas no se apunta
```

`portapapeles.py --ver` dice dónde está todo y cuántas hay; `portapapeles.py
vaciar` borra el historial (no toca fijados ni guardados). No usa cliphist a
propósito: no sabe de caducidad por tiempo ni de fijar o guardar, y montar eso
encima de su base de datos era más frágil que un fichero por entrada. Sin
paquetes nuevos: `wl-clipboard` y `fuzzel` ya estaban.

---

## Volumen y brillo, a la vista

Las teclas de volumen, silencio, micro y brillo hacen el cambio **y enseñan cómo
queda**: un aviso abajo en el centro con el valor y una barra que se rellena
(`hypr/scripts/osd.sh`). Antes se cambiaba a ciegas.

- **Uno solo, que se reescribe**: mantener la tecla no apila veinte avisos.
- **Sin sonido y fuera del historial** (`SUPER + H`): va como aviso
  *transitorio* y con su categoría, y `mako/config` lo trata aparte. Tampoco se
  esconde en «no molestar»: es la respuesta a una tecla que acabas de pulsar.
- Subir el volumen **quita el silencio**, y el tope del 100 % sigue ahí (por
  encima wpctl amplifica por software y suena roto).

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

### El historial: lo que pasó mientras no mirabas

Una notificación sale seis segundos y se va para siempre. Si estabas jugando,
leyendo o mirando a otro lado, se perdió — y no hay forma de saber qué era.
`SUPER+H` abre lo que ha llegado en esta sesión, con su hora, aunque ya lo
hubieras descartado.

```sh
avisos listar          # lo de esta sesión, lo último abajo
avisos ver 12          # uno entero, sin recortar
avisos guardar 12 "mirarlo mañana"
avisos guardados       # lo apartado, que sobrevive al reinicio
avisos listar --json   # para leerlo desde otro programa
```

**El trato es que se graba todo y casi nada se queda.** El registro de la sesión
vive en `$XDG_RUNTIME_DIR`, un tmpfs en modo 700 que systemd borra al cerrar la
última sesión: «se guarda hasta que cierro sesión y luego desaparece» no necesita
ni una línea de código de limpieza, ni un cron, ni acordarse. Por ahí pasa
cualquier cosa que una app decida notificar —un código de dos factores, el asunto
de un correo—, así que no toca el disco nunca. Lo único que baja a
`~/.local/share` es lo que apartas tú, uno a uno, porque justo eso es lo que le
pides.

`tests/unidad/avisos.sh` vigila esa promesa: si un día alguien cambia una ruta y
el registro entero empieza a caer en `~/.local`, eso no daría ningún error — solo
dejaría de cumplirse, en silencio.

#### Es otra cosa que `SUPER+CTRL+N`

`makoctl restore` vuelve a **sacar** una notificación a la pantalla y la quita de
la pila de mako. El historial solo mira. No comparten lista, y por eso no se
pelean.

#### Por qué espía el bus en vez de preguntarle a mako

mako 1.11 tiene su propio historial (`makoctl history -j`) y no sirve para esto,
por tres razones **medidas**:

1. **No trae la hora.** Sus campos son id, app_name, app_icon, category,
   desktop_entry, summary, body, urgency y actions. Un historial sin «cuándo» es
   media cosa.
2. Es un búfer **en memoria de 5** (`max-history`) que muere con mako.
3. `makoctl restore` **saca** cosas de ese búfer: es una pila de deshacer, no un
   archivo. Compartirlo sería pelearse por la misma lista.

Así que `hypr/scripts/avisos.py --demonio` escucha el bus directamente. La
ventaja de fondo es que **no sustituye al demonio de notificaciones**: mako sigue
haciendo su trabajo, y si el grabador se cae dejas de grabar pero no te quedas
sin avisos. No puede romper lo que ya funciona.

Apunta también qué fue de cada aviso: si expiró, si lo descartaste o si pulsaste
su acción — que es lo que distingue «no me enteré» de «lo vi y lo dejé pasar».

> **El id de la notificación no está en la llamada `Notify`, viene en la
> respuesta.** Se emparejan por `reply_serial`, que es igual al `serial` de la
> llamada. Sin eso no hay forma de saber a qué aviso se refiere un
> `NotificationClosed`.

> **La regla de espiado tiene que ser estrecha.** Para las respuestas va
> `type='method_return',sender='org.freedesktop.Notifications'`; con un
> `type='method_return'` a secas te llega **todo** el tráfico del bus (gsettings,
> systemd, portales) y el proceso se despierta constantemente para nada. Medido:
> con la regla estrecha, 16 mensajes en 9 s.

> **Una conexión que llama a `BecomeMonitor` ya no puede hablar**, solo escuchar.
> Por eso se abre una conexión privada y no la compartida de `Gio.bus_get_sync`.

> **Las hints pueden traer el icono en crudo** (`image-data`, un array de
> píxeles). Volcarlo al registro serían cientos de KB por aviso, en un tmpfs que
> comparte sitio con el fifo de las barras. Solo se guardan las hints escalares.

**No hay panel GTK propio a propósito**: fuzzel ya está montado, con la paleta
puesta y sabiendo buscar. Un panel más es una superficie más que mantener, y esto
se abre, se mira y se cierra. El `--json` está para leerlo desde fuera si algún
día quieres montarle otra cara.

---

## La pantalla de bloqueo

Todo vive en una **columna a la izquierda**, sobre una banda oscura: el título y
tu usuario centrados en ella, y debajo el reloj, la fecha, el campo de la
contraseña y una fila con la batería, el teclado y la red. Los otros dos tercios
de la pantalla quedan limpios para que se vea el fondo.

No siempre fue así: antes era una tarjeta flotando en el centro, y el problema no
era de gusto — se plantaba justo encima de lo que estuvieras mirando.

> **Si tocas las medidas**, ojo con dos cosas que el `hyprlock.conf` explica al
> detalle. La primera: el título se centra en la banda con `halign = center` y un
> desplazamiento **negativo** (`$lock_col_centro`), porque hyprlock centra en la
> *pantalla* y luego suma la posición; con `halign = left` habría que saber
> cuánto mide el texto, y eso cambia con la fuente y con los kanji. La segunda:
> ese número y el ancho de la banda **dependen del monitor**, así que los calcula
> `lib/pantalla.py` y no se escriben a mano.
>
> La fila de datos la imprime `hypr/scripts/lock-info.sh` en una sola línea con
> marcado Pango. Una sola etiqueta y no tres porque hyprlang no sabe sumar, y así
> además lo que no aplica —la batería en un sobremesa— desaparece sin dejar hueco.

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

#### El diálogo de «no responde» que salía detrás del bloqueo

Congelar una app es **dejarla muda a propósito**. Y Hyprland 0.56 vigila que cada
ventana conteste a su ping: cuando falla `misc:anr_missed_pings` veces (5 de
fábrica), dibuja *«{title} - {class} no responde»* con los botones **Esperar** y
**Forzar cierre**.

El resultado era una pantalla de bloqueo con un cuadro de diálogo detrás,
acusando a una aplicación de estar colgada... cuando la había congelado el propio
bloqueo dos líneas antes. Y se veía **por debajo** del bloqueo porque el modo
`xray` enseña todo lo que hay debajo.

Lo pinta **el compositor**, no la aplicación. Eso importa para diagnosticarlo: no
sale en `hyprctl clients`, no es un proceso aparte, y no se quita cerrando
ventanas ni saltando a un escritorio vacío. Buscarlo por ahí es perder la tarde.

Por eso `lock.sh` **apaga `misc:enable_anr_dialog` antes de congelar** y lo
devuelve al valor que tenía después de descongelar. El orden es parte del
arreglo, y `tests/e2e/bloqueo.sh` lo vigila:

- si se apagara *después* de congelar, el aviso ya habría salido;
- si se devolviera *antes* de descongelar, el compositor encontraría las apps
  todavía mudas y sacaría el diálogo justo al final.

No se toca `anr_missed_pings`: subirlo solo retrasa el aviso, y un bloqueo dura
lo que dura.

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

Va por systemd y no con `hypridle` a pelo por el `Restart=on-failure`:
si el demonio se cayera, el auto-bloqueo dejaría de funcionar en silencio. Y como
es un `.service` y no un `.scope`, el congelado del bloqueo no puede congelar a
quien lo gobierna.

El fondo de pantalla en vídeo **no** lo estorba, aunque mpv lleve
`stop-screensaver=yes`: mpvpaper pinta con la API de render de libmpv, sin
ventana propia, así que nunca llega a crear un inhibidor. Lo que sí para el
contador son las apps que inhiben por D-Bus (un vídeo a pantalla completa en el
navegador), y eso es justo lo que se quiere.

> **`SUPER+SHIFT+D` enciende la pantalla.** Es un salvavidas, no un adorno:
> un `dpms` **sin argumento apaga el monitor**, Hyprland contesta
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

La que sale al encender el equipo, antes de que exista tu escritorio. Comparte
paleta, título, reloj y tu fondo en vídeo con la pantalla de bloqueo. Vive en
`sddm/celiuz/` y está escrita en QML.

> Ojo, que ya **no son gemelas**: el bloqueo pasó a una columna a la izquierda y
> aquí sigue la tarjeta violeta centrada. Es a propósito por ahora —son dos
> ficheros que no comparten una línea de código, y el greeter es lo único que
> pide `sudo` y lo único que puede dejarte sin arrancar—, pero si buscas por qué
> se ven distintas, es esto y no un descuido.

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
| `unidad/bluetooth` | a qué auricular se llama primero, a quién bloquea el cerrojo y a quién no se toca nunca |
| `unidad/captura` | que la captura de una zona espere a que la selección se borre, y que las otras dos no paguen esa espera |
| `e2e/bluetooth` | el demonio entero contra un BlueZ falso en un bus privado: conectar solo, el cerrojo por las dos puertas, soltar, y no dejar nada bloqueado al salir |

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
`autostart.lua` (y `autostart.conf`) vaciados y su propio `$XDG_RUNTIME_DIR`. Al
salir barre lo que quedara vivo con la firma de esa instancia y borra la casa.

Lo de vaciar el arranque no es exceso de celo: los arranques de verdad
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
| `hypr/conf/colores-pango.conf` | `hypr/scripts/gen-colores.py` |
| `/var/lib/sddm-celiuz/fondo.{mp4,jpg}` | `hypr/scripts/sddm-fondo.sh`, solo, al cambiar de fondo |
| `/etc/sddm.conf.d/10-celiuz.conf` | `instalar.sh --sddm` |
| `~/.cache/celiuzpaper/lock-fondo.conf` | `hypr/scripts/lock.sh` |
| `~/.cache/celiuzpaper/lock-medidas.conf` | `hypr/scripts/lock.sh` (desde `lib/pantalla.py`) |
| `hypr/lua/local.lua` | `instalar.sh` |
| `hypr/conf/local.conf` | `instalar.sh` (el de la config vieja, mientras dure el puente) |
| `waybar/local.jsonc` | `instalar.sh` (desde `waybar/derecha.jsonc`) |

### Y uno que es tuyo: `hypr/lua/personal.lua`

`instalar.sh` lo crea la primera vez —vacío, o **traducido de tu
`conf/personal.conf`** si tenías uno con algo— y **no lo vuelve a tocar nunca**.
No se versiona. Es donde van tus añadidos sin tener que editar los ficheros del
repo: un programa que arranque contigo, un atajo para algo que aquí no viene,
tus pantallas, o un ajuste que prefieres distinto.

```lua
hl.on("hyprland.start", function() hl.exec_cmd("mi-programa") end)
hl.bind("SUPER + G", hl.dsp.exec_cmd("otra-cosa"))
hl.monitor({ output = "HDMI-A-1", mode = "preferred", position = "auto-right", scale = 1.5 })
hl.config({ input = { kb_options = "" } })   -- pisar un ajuste del repo
```

Se carga **el último** de todos, así que desde ahí puedes pisar cualquier cosa:
gana quien habla al final. Y como está fuera de git, tus cambios no te salen
como modificaciones cada vez que traigas actualizaciones. Si tiene un error, sale
en `hyprctl configerrors` (y en `SUPER+SHIFT+R`) con su línea, y el resto de la
config se carga igual.

**`colores.css`, `mako/colores` y `Colores.qml` sí se versionan**: salen de la
paleta y son iguales en cualquier equipo. Los del dock, `local.lua`, `local.conf` y
`local.jsonc` **no**, porque dependen de la máquina — los crea `instalar.sh`. Los dos de `~/.cache`
tampoco: se rehacen en cada bloqueo. Y los tres de fuera del repo (el fondo del
arranque y el drop-in de SDDM) los pone `--sddm`, que es lo único que pide root.

Además, fuera del repo a propósito:

| Archivo | Qué guarda |
|---|---|
| `~/.config/celiuzpaper/carpetas.json` | las carpetas de fondos que añadiste tú |
| `~/.local/state/celiuz/bluetooth.json` | cuándo usaste cada auricular y a cuáles bloqueó el cerrojo |

Es de tu equipo, no del repo: en otra máquina esas rutas no existirían.

---

## Estado

**Hecho:** monitores, teclado (dos distribuciones), barra y dock con
auto-ocultado, lanzador, cambiador de escritorios (`SUPER+TAB`), fondo en vídeo o
imagen con su selector propio, capturas, calendario, monitores del sistema,
pantalla de bloqueo y auto-bloqueo, pantalla de inicio de sesión, Bluetooth
(auriculares que se conectan solos y de uno en uno), el aspecto
(paleta, decoración y animaciones), adaptación a la pantalla que haya,
portabilidad a cualquier ruta de clonado, pruebas automáticas, y desde el
2026-09-25: **menú de salida** con confirmación, **historial del portapapeles**
con fijados y guardados, **volumen y brillo a la vista**, y la **config en Lua**
lista para Hyprland 0.57.

**Pendiente, por orden de valor:**

| | Qué | Por qué importa |
|---|---|---|
| 1 | **Borrar el puente de hyprlang** (`hypr/hyprland.conf` y los módulos de `hypr/conf/` menos `colores*.conf`) | Solo cuando las **dos** máquinas hayan entrado con la config en Lua (`./instalar.sh --revisar` lo dice). Antes no: un `git pull` con una sesión vieja abierta se quedaría sin atajos. |
| 2 | **Un agente de polkit** | No hay ninguno en la sesión: los programas que piden permisos de administrador (`pkexec`, GParted…) fallan sin enseñar la ventana de contraseña. Candidato: `hyprpolkitagent` (repo `extra`). |
| 3 | **`env.lua` para Nvidia — está vacío** | Es lo que más puede afectar jugando en Wayland. Ojo: muchas variables que circulan por los foros llevan años obsoletas en 0.56 y algunas empeoran el rendimiento; hay que comprobar cuáles hacen falta de verdad, no copiar listas. Pista: el Hyprland anidado sobre esta NVIDIA solo levanta con `AQ_NO_MODIFIERS=1`. |
| 4 | **Atajos básicos que faltan** | Pantalla completa, mover ventanas y redimensionar con el teclado, escritorio especial (cajón), cambiar de escritorio con la rueda + SUPER. |
| 5 | **Integración continua** | `shellcheck`, `ruff` y `./tests/run.sh` en cada push: las dos máquinas empujan a `main`. |
| 6 | **Reglas de ventana del flujo de seguridad** | VMs, Burp… Hay que decidir antes qué herramientas se usan de verdad. |
| 7 | **El login (SDDM) y el TTY siguen en `latam`** | `/etc/vconsole.conf` gobierna la pantalla de login, así que la contraseña al encender se teclea con otra distribución que la de la sesión. Es un cambio de sistema, fuera del repo. |

Menores, ya ofrecidos y no pedidos: regla de sudo estrecha para
`ir-a-windows.sh`, regla de ventana para que su terminal salga flotante, atajo
propio para CeliuzPaper, y un botón de «añadir comando a mano» en el gestor del
dock (para AppImages y binarios sueltos, que ningún escaneo de `.desktop` cubre).

Para retomar el trabajo hay un **`SIGUIENTE.md`** con el detalle de cada
pendiente y las pistas que ya se encontraron.
