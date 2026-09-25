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

1. **Modo gaming** (lo próximo que quiere el usuario, 2026-09-25). Aún sin
   diseñar: no des por hecho qué debe hacer, pregúntaselo. **Antes de escribir
   nada, mira lo que YA existe**, porque media pieza está hecha:
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
