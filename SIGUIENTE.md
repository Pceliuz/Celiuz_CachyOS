# Por dónde seguir

Notas para retomar el trabajo sin tener que reconstruir el contexto. Si esto se
queda viejo, manda el `README.md` y el `CLAUDE.md`.

Última sesión: **2026-08-03**. Todo subido a `origin/main`, hasta `e4f3a0a`.

## Lo primero al abrir el repo

```sh
./tests/run.sh          # 6 pruebas, 108 comprobaciones. Deben salir todas
./instalar.sh --revisar # no debe sacar avisos inesperados
hyprctl configerrors    # vacío
```

Si las pruebas fallan **antes** de tocar nada, eso es lo que hay que arreglar
primero: significa que algo del sistema cambió por debajo (una actualización de
Hyprland, de mpv o de waybar).

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

### 2. Teclas multimedia y la perilla del teclado

No hay **ni un bind de volumen** en toda la config. El teclado (Attack Shark
X820) trae perilla y nunca se llegó a probar qué manda: anuncia dispositivos
`-consumer-control` y `-system-control` aparte. Es rápido y se nota a diario.

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
