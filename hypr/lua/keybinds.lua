-- keybinds.lua — atajos de teclado.
-- Workspaces dedicados para el flujo de ciberseguridad (VMs, terminales, Burp) se definen aqui tambien.
--
-- COMO SE LEE: `hl.bind("SUPER + SHIFT + P", accion, opciones)`. Las opciones son
-- las letras de hyprlang con nombre:
--   bindl -> { locked = true }      funciona con la pantalla bloqueada
--   binde -> { repeating = true }   repite si mantienes pulsado
--   bindr -> { release = true }     dispara al SOLTAR
--   bindm -> { mouse = true }       arrastrar con el raton
-- Y cada accion es un `hl.dsp.*`: `exec` es hl.dsp.exec_cmd, que pasa la orden
-- por un shell (asi que `$HOME` se expande como antes).

local M = require("lua.maquina")

local mainMod = "SUPER"
local S = "$HOME/.config/hypr/scripts/"

-- tecla(mods, tecla) -> "SUPER + SHIFT + P". `mods` vacio = sin modificador.
local function tecla(mods, t)
    if mods == nil or mods == "" then return t end
    return mods:gsub("%s+", " + ") .. " + " .. t
end

-- con(opciones, descripcion) — una copia de las opciones con su descripcion.
-- La descripcion es lo que enseña `hyprctl binds`: con la config en Lua, la
-- accion de un atajo sale ahi como `__lua` y un numero, y sin esto no habria
-- forma de saber desde fuera que hace cada uno (ni de comprobarlo, que es como
-- se verifico el paso de hyprlang a Lua). Copia, y no la misma tabla, porque
-- varias llamadas comparten `repite` y `bloqueada`.
local function con(opciones, descripcion)
    local o = {}
    for k, v in pairs(opciones or {}) do o[k] = v end
    o.description = descripcion
    return o
end

-- exec(mods, tecla, orden[, opciones]) — el `bind = mods, tecla, exec, orden`.
-- Su descripcion es la propia orden.
local function exec(mods, t, orden, opciones)
    return hl.bind(tecla(mods, t), hl.dsp.exec_cmd(orden), con(opciones, orden))
end

-- accion(mods, tecla, dispatcher, descripcion[, opciones]) — lo que no es exec.
local function accion(mods, t, dsp, descripcion, opciones)
    return hl.bind(tecla(mods, t), dsp, con(opciones, descripcion))
end

-- --- Ventanas y sesion ---
-- La terminal la pone lua/local.lua, que escribe instalar.sh con la que haya en
-- ESTA maquina: el repo es publico y no puede dar por hecho que tienes kitty.
--
-- Se lanza con scripts/lanzar.sh y no directamente por dos cosas: mete la app en
-- su propio scope de systemd (con `uwsm app --`, sin eso todo cae en el cgroup de
-- Hyprland y el congelado al bloquear la pantalla no puede distinguir una app del
-- compositor — ver gen-dock.py y lib/congelar.py), y avisa con una notificacion
-- si el comando no existe en vez de no hacer nada.
exec(mainMod, "RETURN", S .. "lanzar.sh " .. M.terminal)
accion(mainMod, "Q", hl.dsp.window.close(), "cerrar la ventana")
accion(mainMod, "V", hl.dsp.window.float({ action = "toggle" }), "flotante o en mosaico")
-- Menu de salida: bloquear, suspender, cerrar sesion, reiniciar, apagar. Va con P
-- y no con E porque la E estaba pegada a las teclas que se usan a diario y era
-- facil de rozar sin querer.
--
-- Y aun asi se rozaba: esto era un `exit` a secas y cerro la sesion con todo
-- abierto mas de una vez. Ahora abre un menu, y lo que no tiene vuelta atras
-- pregunta otra vez con «No» preseleccionado (el porque, en sesion.sh).
exec(mainMod .. " SHIFT", "P", S .. "sesion.sh")

-- --- Lanzador de aplicaciones (fuzzel) ---
-- Config en fuzzel/fuzzel.ini.
-- SUPER+B es "drun": lista las apps instaladas por sus .desktop, con su icono.
-- SUPER+SHIFT+B es "run": ejecuta cualquier binario del PATH, aunque no tenga
-- lanzador propio.
--
-- OJO con el modo run: lanza el binario SIN terminal, asi que una herramienta de
-- consola (nmap, btop...) se ejecuta invisible y muere sin que veas nada. No esta
-- roto, es lo que hace. Si algun dia lo quieres con terminal, se le anade
-- `--launch-prefix="kitty -e"` a esta linea; el inconveniente es que entonces las
-- apps graficas tambien arrastran una terminal detras.
exec(mainMod, "B", "pkill fuzzel || fuzzel")
exec(mainMod .. " SHIFT", "B", "pkill fuzzel || fuzzel --mode=run")

-- --- Barra y dock ---
-- Un solo atajo saca las DOS: la barra de arriba y el dock de abajo. Antes eran
-- dos teclas distintas (una por barra) y no hacia falta.
--
-- La ruta del canal no se escribe aqui: lleva la firma de la sesion, para que
-- esto no acabe sacando las barras de OTRA sesion de Hyprland viva a la vez. La
-- calcula barras.sh, que ademas avisa si el demonio no esta — antes, con el FIFO
-- ausente, el atajo no hacia nada y no se quejaba nadie.
exec(mainMod, "C", S .. "barras.sh show dock:show")

-- Reiniciar el demonio de las barras (util al editar su config o si se cuelga).
-- Relanza las cuatro instancias de waybar.
--
-- Las barras nuevas nacen VISIBLES y se esconden solas a los ~1,5 s, como
-- cualquier otra vez que se sacan. Antes nacian escondidas si habia alguna app
-- abierta, y entonces este atajo parecia servir solo para hacerlas desaparecer.
-- Y si alguna se cae, el demonio la relanza en vez de apagarse: eso era lo que
-- dejaba el escritorio sin barras hasta cerrar sesion.
--
-- El reinicio lo hace el propio demonio con --reiniciar, y no un `pkill -f` aqui,
-- porque ese patron encajaba tambien con el shell que ejecuta este atajo (su
-- linea de comandos contiene la ruta) y se mataba a si mismo antes de relanzar.
exec(mainMod .. " SHIFT", "C", S .. "waybar-autohide.py --reiniciar")

-- --- Notificaciones ---
-- Descartar la de arriba. Es lo que mas se usa: llega algo, lo lees, fuera.
exec(mainMod, "N", "makoctl dismiss")

-- Descartarlas TODAS de golpe.
exec(mainMod .. " SHIFT", "N", "makoctl dismiss --all")

-- "No molestar". Es un MODO de mako (ver mako/config), no un apagado: mientras
-- esta puesto las notificaciones se siguen recibiendo y guardando, solo que no
-- se dibujan. Se recuperan despues con SUPER+CTRL+N.
exec(mainMod .. " ALT", "N", "makoctl mode -t no-molestar")

-- Sacar otra vez la ultima que descartaste, o las que llegaron mientras estabas
-- en "no molestar".
exec(mainMod .. " CTRL", "N", "makoctl restore")

-- El HISTORIAL: todo lo que ha llegado en esta sesion, con su hora, aunque ya lo
-- hubieras descartado. Es otra cosa que SUPER+CTRL+N — ese vuelve a SACAR una
-- notificacion a la pantalla y la quita de la pila de mako; esto solo mira, y
-- deja apartar lo que quieras conservar para hablarlo otro dia.
--
-- En H y no en otra N porque las cuatro combinaciones de N ya estan cogidas, y
-- porque mirar el historial es un gesto distinto de atender un aviso.
exec(mainMod, "H", S .. "avisos.py menu")

-- --- Config ---
-- Recargar la config. Va al script y NO a `hyprctl reload` a secas porque reload
-- contesta "ok" aunque la config tenga errores: el ajuste no se aplica y no te
-- enteras. recargar.sh mira `hyprctl configerrors` y ademas comprueba las
-- incoherencias silenciosas (ver el propio script).
--
-- Como un atajo no tiene donde escribir, se lanza dentro de una terminal
-- flotante (clase config-reload, con su regla de ventana) que se queda abierta
-- 4 s si todo fue bien y espera a que pulses una tecla si hubo algo que contar.
exec(mainMod .. " SHIFT", "R", S .. "terminal.sh config-reload " .. S .. "recargar.sh --esperar")

-- --- Pantalla ---
-- Bloqueo con hyprlock. Se llama al script y no a hyprlock directo para que el
-- fondo de video siga en marcha mientras esta bloqueado (ver lock.sh).
exec(mainMod, "L", S .. "lock.sh")

-- RESCATE: enciende la pantalla. Funciona AUNQUE el monitor este negro, porque
-- Hyprland sigue leyendo el teclado con el DPMS apagado; lo unico que falta es
-- quien mande la orden.
--
-- Existe por lo que paso el 2026-07-27: un `hyprctl dispatch dpms` sin
-- argumento apago el monitor, la pantalla se quedo negra, no habia forma de
-- encenderla desde dentro y hubo que reiniciar a lo bruto perdiendo la sesion.
-- Con esto, ese apuro se resuelve con dos dedos.
--
-- D de "despertar". Si algun dia no responde, la pantalla no es el problema:
-- entra por otro tty con Ctrl+Alt+F2.
accion(mainMod .. " SHIFT", "D", hl.dsp.dpms({ action = "on" }), "encender la pantalla")

-- Captura de pantalla. SUPER+S recorta la zona que elijas con el raton; con SHIFT,
-- la pantalla entera; con ALT, solo la ventana que tengas delante. Las tres copian
-- al portapapeles Y guardan en ~/Imágenes/capturas/.
--
-- Va con SUPER y no con PGDN ni Ctrl+S a secas a proposito: Hyprland se queda la
-- tecla para el en todo el sistema, asi que PGDN dejaria de bajar pagina en el
-- navegador y la terminal, y Ctrl+S dejaria de guardar en los editores.
--
-- Y no va en Impr Pant porque ESTE TECLADO NO LA TIENE: el Attack Shark X820 es
-- un 75% ANSI y se audito tecla por tecla (ver "El teclado" en el README). Un
-- atajo sobre una tecla que el teclado no emite no falla, simplemente no salta
-- nunca — que es la peor forma de que un atajo no exista.
exec(mainMod, "S", S .. "screenshot.sh")
exec(mainMod .. " SHIFT", "S", S .. "screenshot.sh --full")

-- El modo ventana existia en screenshot.sh desde el principio y se habia quedado
-- SIN ATAJO: la unica forma de usarlo era escribir el comando a mano, asi que en
-- la practica no existia.
exec(mainMod .. " ALT", "S", S .. "screenshot.sh --ventana")

-- Grabar la pantalla en video. Mismo reparto que las capturas y con la tecla de
-- al lado: SUPER+R graba la zona que elijas, SUPER+ALT+R el monitor entero.
--
-- Son INTERRUPTORES: el mismo atajo que empieza es el que para. Dos atajos
-- distintos —uno para empezar y otro para parar— es justo lo que no se recuerda
-- con la grabacion ya corriendo, que es cuando hace falta.
--
-- SUPER+SHIFT+R no se usa aqui: ya es "recargar la configuracion" (mas arriba), y
-- de las tres es la que peor sienta pulsada por error en mitad de una grabacion.
--
-- El sonido va aparte, con --audio, y sin atajo a proposito: grabar la pantalla
-- es lo de todos los dias y grabar ademas lo que suena es la excepcion, no al
-- reves. Para eso: grabar.sh --audio  (o --full --audio).
exec(mainMod, "R", S .. "grabar.sh")
exec(mainMod .. " ALT", "R", S .. "grabar.sh --full")

-- --- Portapapeles ---
-- El historial de lo copiado, con cosas fijadas (hasta cerrar sesion) y guardadas
-- (para siempre). Dentro: Enter copia, Ctrl+F fija, Ctrl+G guarda, Ctrl+D borra.
-- Lo que se apunta lo vigila `portapapeles.py demonio` desde autostart.lua; el
-- porque de cada decision, en la cabecera del script.
exec(mainMod .. " SHIFT", "V", S .. "portapapeles.py menu")

-- --- Teclado ---
-- Alternar entre las dos distribuciones: us(altgr-intl) <-> latam (ver el porque
-- en lua/input.lua). Avisa por notificacion en cual acabas de quedarte, que es
-- lo unico que hace incomodo tener dos.
--
-- Va en DEL y no en SPACE (que es lo habitual) porque lo pediste asi: DEL esta
-- arriba a la derecha, sola, lejos de todo lo que se pulsa a diario.
exec(mainMod, "DELETE", S .. "teclado.py cambiar")

-- --- Teclas de funcion: sonido y multimedia ---------------------------------
-- Estas van AQUI y no en lua/teclado-laptop.lua aunque suenen a portatil,
-- porque no son de portatil: cualquier teclado con teclas de medios las emite, y
-- en un equipo que no las tenga estas lineas no hacen nada — la tecla no existe,
-- el atajo no dispara. Lo que SI es de portatil (brillo, touchpad, tapa) esta en
-- el otro fichero.
--
-- `repeating`: repite si mantienes pulsado (subir el volumen de uno en uno
-- seria inutil) y `locked`: funciona con la pantalla bloqueada, que es justo
-- cuando quieres bajar el volumen sin desbloquear.
--
-- Todas pasan por `scripts/osd.sh`, que hace el cambio con wpctl y ENSEÑA como
-- quedo: un aviso abajo en el centro con el valor y una barra, que se reescribe
-- en cada pulsacion en vez de apilarse. Antes se cambiaba a ciegas.
--
-- El tope de `-l 1.0` sigue alli dentro, y es importante: sin el, wpctl pasa del
-- 100% amplificando por software. Eso no suena "mas alto", suena ROTO —recorta
-- los picos— y con unos cascos puestos es desagradable de verdad. Y subir el
-- volumen quita el silencio, que es lo que esperas al pulsar «mas».
local repite = { locked = true, repeating = true }
local bloqueada = { locked = true }
exec("", "XF86AudioRaiseVolume", S .. "osd.sh volumen subir", repite)
exec("", "XF86AudioLowerVolume", S .. "osd.sh volumen bajar", repite)

-- El silencio va con `locked` y sin `repeating`: repetir un interruptor lo unico
-- que hace es encenderlo y apagarlo muy rapido.
exec("", "XF86AudioMute",    S .. "osd.sh volumen silenciar", bloqueada)
exec("", "XF86AudioMicMute", S .. "osd.sh micro silenciar", bloqueada)

-- playerctl habla con quien este reproduciendo por MPRIS: el navegador, mpv,
-- Spotify. No hace falta configurar cual.
exec("", "XF86AudioPlay", "playerctl play-pause", bloqueada)
exec("", "XF86AudioNext", "playerctl next", bloqueada)
exec("", "XF86AudioPrev", "playerctl previous", bloqueada)
exec("", "XF86AudioStop", "playerctl stop", bloqueada)

-- --- Workspaces ---
-- Cambiar de workspace (1-7), y SHIFT para mover alli la ventana activa. Son los
-- mismos 7 que la barra dibuja siempre (persistent-workspaces en
-- waybar/config.jsonc): si cambias uno, cambia el otro.
for i = 1, 7 do
    accion(mainMod, tostring(i), hl.dsp.focus({ workspace = i }), "ir al escritorio " .. i)
    accion(mainMod .. " SHIFT", tostring(i), hl.dsp.window.move({ workspace = i }),
           "mover la ventana al escritorio " .. i)
end

-- Cambiar de escritorio al estilo del Alt+Tab de Windows: MANTIENES SUPER, y
-- cada TAB salta al siguiente escritorio CON APPS ABIERTAS mientras una tira de
-- abajo te dice cuales hay. El escritorio cambia de verdad a cada salto (es una
-- previsualizacion como la de CeliuzPaper con los fondos), y al soltar SUPER te
-- quedas donde estabas mirando. Escape te devuelve al de partida.
--   SUPER+1..7  — "quiero abrir algo ahi". Saltas a ciegas, y esta bien asi.
--   SUPER+TAB   — "quiero volver a lo que tengo abierto", pero no te acuerdas
--                 de en cual escritorio lo dejaste. Lo ves y lo eliges.
--
-- El atajo es solo la pulsacion: lo de "mientras SUPER siga pulsado" lo lleva el
-- script, que coge el teclado en exclusiva y escucha cuando lo sueltas. Hyprland
-- no tiene atajos de "al soltar" para esto.
--
-- Y OJO con lo de "cada TAB salta al siguiente": eso NO lo hace el teclado de la
-- ventana. Hyprland atiende sus atajos antes de entregar la tecla al cliente, asi
-- que mientras SUPER siga pulsado la capa no llega a ver ni un TAB — es este
-- mismo atajo, disparandose otra vez, el que le manda una senal a la ventana ya
-- abierta para que avance. Por eso los dos atajos llaman al mismo script.
exec(mainMod, "TAB", S .. "vista-escritorios.py")
exec(mainMod .. " SHIFT", "TAB", S .. "vista-escritorios.py --atras")

-- Y ESTO es el "suelta SUPER y te quedas ahi". `release` dispara AL SOLTAR.
--
-- Por que no lo detecta el propio script y punto: porque cuando das un toque
-- rapido, sueltas ANTES de que la ventana exista, y entonces no hay nadie
-- escuchando el teclado — la ventana se quedaba abierta hasta que volvias a
-- pulsar la combinacion. Y preguntar "sigue pulsado SUPER?" no es una opcion:
-- `Gdk.Keymap.get_modifier_state()` devuelve en esta sesion SIEMPRE 0x4000040,
-- con el bit de SUPER puesto aunque no la toque nadie (esta medido; no es el
-- estado en vivo, es el mapa de que bit le corresponde).
--
-- La orden es un `sh` de dos ordenes a proposito, no el script de Python: esto
-- se dispara cada vez que sueltas SUPER — o sea despues de CUALQUIER atajo — y
-- arrancar Python para no hacer nada costaria 100 ms cada vez. Asi, si no hay
-- ninguna ventana abierta, no hace absolutamente nada.
--
-- EL MODIFICADOR VA DELANTE, Y ES OBLIGATORIO. Esto estuvo escrito sin
-- modificador desde el primer dia, con la idea de que asi saltaria tambien
-- viniendo de SUPER+SHIFT+TAB. Es al reves, y el atajo se quedo sin su ultimo
-- eslabon: al soltar SUPER no pasaba nada y habia que rematar con Enter.
--
-- El motivo, MEDIDO el 2026-08-04 con tres atajos de prueba a la vez (uno por
-- forma) y un diario: en el instante en que sueltas SUPER_L, Hyprland TODAVIA
-- cuenta SUPER dentro del modmask. Un atajo declarado con modmask 0 no coincide
-- jamas. De diez pulsaciones, las diez las cogio `SUPER + SUPER_L`; la forma sin
-- modificador no se disparo ni una vez. Y no avisa nadie: el atajo se carga sin
-- error y sale en `hyprctl binds` como cualquier otro, solo que nunca dispara.
--
-- Por eso hacen falta las dos combinaciones de cada tecla: el modmask tiene que
-- coincidir EXACTO, asi que soltar SUPER con SHIFT todavia pulsado (o sea,
-- viniendo de SUPER+SHIFT+TAB) es un caso distinto y necesita su propia linea.
local soltar = "f=$XDG_RUNTIME_DIR/vista-escritorios.pid; test -f $f && xargs -r kill -WINCH < $f"
for _, t in ipairs({ "SUPER_L", "SUPER_R" }) do
    exec("SUPER", t, soltar, { release = true })
    exec("SUPER SHIFT", t, soltar, { release = true })
end

-- Mover foco entre ventanas
accion(mainMod, "left",  hl.dsp.focus({ direction = "left" }),  "foco a la izquierda")
accion(mainMod, "right", hl.dsp.focus({ direction = "right" }), "foco a la derecha")
accion(mainMod, "up",    hl.dsp.focus({ direction = "up" }),    "foco arriba")
accion(mainMod, "down",  hl.dsp.focus({ direction = "down" }),  "foco abajo")

-- Mouse: mover/redimensionar ventanas flotantes con SUPER + click
--
-- OJO si lo compruebas con `hyprctl binds`: estos dos salen con `"mouse":
-- false`, y NO es un fallo. En Lua el arrastre lo hace la propia accion
-- (hl.dsp.window.drag / resize), no la bandera. Medido el 2026-09-25 en un
-- anidado con un raton de mentira por uinput: la ventana se arrastro y se
-- redimensiono igual con `{ mouse = true }` que sin nada. Se deja la bandera
-- porque es como lo escribe el ejemplo oficial de Hyprland.
accion(mainMod, "mouse:272", hl.dsp.window.drag(),   "arrastrar la ventana",      { mouse = true })
accion(mainMod, "mouse:273", hl.dsp.window.resize(), "redimensionar la ventana", { mouse = true })
