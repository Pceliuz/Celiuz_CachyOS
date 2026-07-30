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
| `hypr/conf/` | Un módulo por asunto: monitores, teclado, atajos, reglas de ventana… `colores.conf` va el primero, porque define la paleta que usan los demás. |
| `hypr/scripts/` | Todo lo hecho a medida (ver abajo). |
| `hypr/scripts/lib/` | Bibliotecas compartidas por los scripts y por la CLI. |
| `waybar/` | Barra de arriba y dock de abajo. Cuatro instancias de waybar. |
| `fuzzel/` | Lanzador de aplicaciones. |
| `celiuzpaper/` | App propia para cambiar el fondo de pantalla. |
| `mpvpaper/` | Lista de programas que pausan el fondo en vídeo. |

### Las piezas a medida

- **`waybar-autohide.py`** — demonio que gestiona las cuatro instancias de waybar
  (barra + dock, cada una con su línea-tirador). Sin ventanas en el escritorio la
  barra se queda puesta; con ventanas se esconde y aparece una línea fina arriba
  que la baja al pulsarla.
- **`gen-dock.py`** — genera `waybar/dock.jsonc` a partir de `waybar/dock-apps.json`.
  El dock **no se edita a mano**. Con clic derecho en cualquier icono se abre
  `dock-manager.py`, que añade y quita apps.
- **`calendar-panel.py`** — al pulsar el reloj se abre un calendario con los
  feriados peruanos (`lib/pe_fechas.py`) y los eventos de Google Calendar
  (`lib/gcal.py`).
- **`celiuzpaper`** — cambia el fondo de pantalla en vídeo. Al moverte por la tira
  el fondo cambia **de verdad** a pantalla completa; Enter lo fija, Escape
  restaura. También sirve por CLI (`--list`, `--set`, `--random`, `--current`).
- **`lock.sh` + `hyprlock.conf`** — la pantalla de bloqueo. Ver su sección abajo,
  porque hace bastante más que lanzar `hyprlock`.
- **`wallpaper-pause.py`** — pausa el vídeo del fondo cuando queda tapado, y lo
  mata entero mientras corra algo de la `stoplist` (juegos).

---

## Requisitos

Todo está en los repos oficiales de CachyOS/Arch. No hace falta nada del AUR.

```sh
sudo pacman -S hyprland waybar fuzzel kitty hyprlock hypridle mpvpaper \
               grim slurp wl-clipboard uwsm \
               python-gobject gtk-layer-shell ffmpeg librsvg \
               ttf-meslo-nerd noto-fonts-cjk \
               mission-center nvtop btop \
               ananicy-cpp cachyos-ananicy-rules \
               python-google-api-python-client python-google-auth-oauthlib
```

Notas:

- **`ttf-meslo-nerd`** no es opcional: las barras usan la variante
  `MesloLGS Nerd Font Propo` para los iconos del dock (en la variante normal cada
  icono mide 24 px lógicos aunque dibuje 46, y salen descentrados).
- **`ananicy-cpp` + `cachyos-ananicy-rules`** no son solo para prioridades: la
  pantalla de bloqueo usa sus ~13.500 reglas `"type": "Game"` como base de datos
  de juegos, para saber qué no debe congelar.
- **`uwsm`** es imprescindible para lo mismo (ver abajo).

## Instalación

Se enlaza, no se copia, para que editar el repo sea editar la config:

```sh
git clone git@github.com:Pceliuz/Celiuz_CachyOS.git ~/dotfiles

ln -sfn ~/dotfiles/hypr     ~/.config/hypr
ln -sfn ~/dotfiles/waybar   ~/.config/waybar
ln -sfn ~/dotfiles/fuzzel   ~/.config/fuzzel
ln -sfn ~/dotfiles/mpvpaper ~/.config/mpvpaper

mkdir -p ~/.local/bin ~/.local/share/applications \
         ~/.local/share/icons/hicolor/scalable/apps
ln -sfn ~/dotfiles/celiuzpaper/celiuzpaper.py      ~/.local/bin/celiuzpaper
ln -sfn ~/dotfiles/celiuzpaper/celiuzpaper.desktop ~/.local/share/applications/
ln -sfn ~/dotfiles/celiuzpaper/celiuzpaper.svg     ~/.local/share/icons/hicolor/scalable/apps/
```

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
| `SUPER + RETURN` | Terminal (kitty) |
| `SUPER + Q` | Cerrar ventana |
| `SUPER + V` | Flotante / anclada |
| `SUPER + B` | Lanzador de aplicaciones |
| `SUPER + SHIFT + B` | Lanzador en modo "ejecutar binario" |
| `SUPER + C` | Sacar la barra y el dock |
| `SUPER + SHIFT + C` | Reiniciar el demonio de las barras |
| `SUPER + SHIFT + R` | Recargar la config (y avisar de verdad si falla) |
| `SUPER + L` | Bloquear la pantalla |
| `SUPER + S` | Captura de una zona |
| `SUPER + SHIFT + S` | Captura de la pantalla entera |
| `SUPER + 1..7` | Ir al escritorio |
| `SUPER + SHIFT + 1..7` | Mover la ventana al escritorio |
| `SUPER + flechas` | Mover el foco |
| `SUPER + clic izq/der` | Mover / redimensionar flotantes |
| `SUPER + SHIFT + P` | Salir de Hyprland |

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

## Archivos generados

No se editan a mano; los escribe un script y llevan cabecera avisándolo:

| Archivo | Lo genera |
|---|---|
| `waybar/dock.jsonc` | `hypr/scripts/gen-dock.py` |
| `waybar/dock-icons.css` | `hypr/scripts/gen-dock.py` |
| `waybar/colores.css` | `hypr/scripts/gen-colores.py` |
| `~/.cache/celiuzpaper/lock-fondo.conf` | `hypr/scripts/lock.sh` |

Se versionan los tres primeros a propósito, para que un clon recién hecho
arranque sin tener que ejecutar los generadores.

---

## Estado

Hecho: monitores, teclado, barra, dock, lanzador, fondo en vídeo, capturas,
calendario, monitores del sistema, pantalla de bloqueo, auto-bloqueo por
inactividad, y el aspecto (paleta, decoración y animaciones).

Pendiente: `env.conf` para Nvidia, reglas de ventana del flujo de seguridad,
historial del portapapeles y notificaciones.

> **Aviso de futuro:** Hyprland avisa al arrancar de que *el formato `.conf`
> dejará de estar soportado en la 0.57*. Todo este repo está en hyprlang `.conf`
> por decisión explícita (poder seguir la wiki y los foros sin traducir), así que
> antes de esa versión habrá que decidir: quedarse anclado, o portar a Lua.
