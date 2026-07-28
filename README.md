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
| `hypr/conf/` | Un módulo por asunto: monitores, teclado, atajos, reglas de ventana… |
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
| `SUPER + L` | Bloquear la pantalla |
| `SUPER + S` | Captura de una zona |
| `SUPER + SHIFT + S` | Captura de la pantalla entera |
| `SUPER + 1..7` | Ir al escritorio |
| `SUPER + SHIFT + 1..7` | Mover la ventana al escritorio |
| `SUPER + flechas` | Mover el foco |
| `SUPER + clic izq/der` | Mover / redimensionar flotantes |
| `SUPER + SHIFT + P` | Salir de Hyprland |

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
| `~/.cache/celiuzpaper/lock-fondo.conf` | `hypr/scripts/lock.sh` |

Se versionan los dos primeros a propósito, para que un clon recién hecho arranque
sin tener que ejecutar el generador.

---

## Estado

Hecho: monitores, teclado, barra, dock, lanzador, fondo en vídeo, capturas,
calendario, monitores del sistema, pantalla de bloqueo y auto-bloqueo por
inactividad.

Pendiente: `decoration.conf` y `animations.conf` (redondeos, blur, sombras),
historial del portapapeles y notificaciones.
