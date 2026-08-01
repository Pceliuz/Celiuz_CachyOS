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
| `hypr/conf/local.conf` | la terminal de cada equipo |
| `hypr/wallpapers/*` | vídeos: pesan y no son redistribuibles |

Los cuatro los crea `./instalar.sh`.

## Generado vs. escrito a mano

Varios ficheros llevan `GENERADO — NO EDITAR` en su cabecera. Va en serio: al
editarlos a mano el cambio se pierde en la siguiente regeneración.

| Generado | Lo escribe | Desde |
|---|---|---|
| `waybar/dock.jsonc`, `waybar/dock-icons.css` | `hypr/scripts/gen-dock.py` | `waybar/dock-apps.json` |
| `waybar/colores.css`, `mako/colores` | `hypr/scripts/gen-colores.py` | `hypr/conf/colores.conf` |
| `hypr/conf/local.conf` | `instalar.sh` | detección en la máquina |

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

`fuzzel/fuzzel.ini` lo llama por `terminal=celiuz-terminal --sin-uwsm
fuzzel-term`, un enlace a ese mismo script que `instalar.sh` deja en
`~/.local/bin`. Va por el PATH y no por ruta a propósito: **fuzzel no expande `~`
ni `$HOME`** en esa opción. Y el `include=` de fuzzel tampoco vale para sacar la
línea a un fichero generado: si el fichero incluido no existe, fuzzel **sale con
1 y no abre el lanzador** (Hyprland, en cambio, solo avisa).

## Trampas comprobadas (no las redescubras)

- **`ln -sfn origen ~/.config/hypr` no sirve** si `~/.config/hypr` ya existe como
  carpeta real: crea el enlace *dentro* (`~/.config/hypr/hypr`) y la config no se
  despliega, **sin dar ningún error**. En CachyOS esa carpeta existe. Por eso hay
  instalador y no cuatro `ln` en el README.
- **`hyprland.lua` gana a `hyprland.conf`.** Hyprland 0.56 lo busca primero y
  CachyOS trae el suyo en Lua. Si reaparece, esta config queda ignorada en
  silencio. `instalar.sh` avisa.
- **`hyprctl reload` no basta** para probar cambios de `exec-once`: solo corren al
  arrancar la sesión. Y si la sesión arrancó desde un `.lua`, `reload` no cae de
  vuelta al `.conf`.
- **Para validar config sin arriesgar la sesión viva**, instancia anidada:
  ```sh
  env -u HYPRLAND_INSTANCE_SIGNATURE WLR_BACKENDS=headless Hyprland &
  hyprctl -i "$(ls -t /run/user/1000/hypr/ | head -1)" configerrors
  ```
- **waybar se traga el stderr de los `on-click`.** Un fallo ahí no deja rastro en
  el journal; por eso los lanzadores notifican.
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

## Antes de dar algo por terminado

1. `./instalar.sh --revisar` no debe sacar avisos inesperados.
2. `hyprctl configerrors` vacío.
3. Si tocaste el dock: `hypr/scripts/gen-dock.py list` — ninguna app debe salir
   `[NO INSTALADA]`.
4. Si tocaste el fondo: comprueba que el demonio está vivo y que `pause` sigue a
   `True` con ventanas abiertas.
5. Prueba pensando en **la otra máquina**, no solo en esta.

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
