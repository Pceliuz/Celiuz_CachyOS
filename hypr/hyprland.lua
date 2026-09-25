-- ~/dotfiles/hypr/hyprland.lua
-- Punto de entrada. Solo une los modulos de lua/, no metas configs sueltas aqui.
--
-- POR QUE LUA. Hyprland 0.56 trae config nativa en Lua y avisa al arrancar de
-- que la de hyprlang (`hyprland.conf`) deja de estar soportada en la 0.57. Esta
-- config se porto el 2026-09-25, modulo a modulo y con sus comentarios, y se
-- verifico contra la de hyprlang en dos Hyprland anidados comparando todas las
-- opciones, los atajos y las reglas (ver SIGUIENTE.md).
--
-- Hyprland busca `hyprland.lua` ANTES que `hyprland.conf`, asi que con los dos
-- en la carpeta manda este. Los .conf de conf/ se quedan de PUENTE, congelados:
-- una sesion que arranco con ellos sigue leyendolos hasta cerrar sesion, y si
-- desaparecieran de golpe (un `git pull` con la sesion abierta) Hyprland
-- recargaria solo y se quedaria sin atajos — medido: de 62 a 6. Se borran
-- cuando las dos maquinas hayan entrado con este fichero. NO se editan.
--
-- Como se carga cada modulo: `require("lua.x")` lee ~/.config/hypr/lua/x.lua.
-- El require de Hyprland aguanta los fallos: si un modulo tiene un error, sale
-- en `hyprctl configerrors` con fichero y linea (recargar.sh lo enseña) y los
-- demas se cargan igual. Y cada recarga empieza de cero, sin nada cacheado.
--
-- OJO al hablarle a Hyprland desde fuera: con esta config, `hyprctl dispatch
-- workspace 3` y `hyprctl keyword ...` dan ERROR. Los scripts pasan por
-- scripts/lib/hypr.py y lib/hypr.sh (o scripts/despachar.sh), que lo dicen en
-- el idioma que toque. El porque, en la cabecera de lib/hypr.py.

-- colores y maquina se cargan los primeros porque los demas los usan: la
-- paleta (de conf/colores.conf, la misma de hyprlock y la barra) y lo que es
-- de este equipo (lua/local.lua, que escribe instalar.sh).
require("lua.colores")
require("lua.maquina")

require("lua.monitors")
require("lua.input")
require("lua.env")
require("lua.autostart")
require("lua.general")
require("lua.decoration")
require("lua.animations")
require("lua.keybinds")
require("lua.windowrules")
require("lua.workspaces")
require("lua.misc")

-- Lo que depende de QUE CLASE DE EQUIPO es esto: en un portatil, el touchpad,
-- la tapa, el brillo y el teclado interno. Va DESPUES de input y keybinds
-- porque son correcciones sobre lo que ellos ya dijeron, y aqui tambien gana
-- el ultimo que habla (una opcion puesta dos veces se queda con la segunda).
if require("lua.maquina").portatil then
    require("lua.teclado-laptop")
end

-- Y DESPUES DE TODO, lo tuyo. `lua/personal.lua` lo crea instalar.sh y NO se
-- versiona: es donde van tus anadidos —un programa que arranque contigo, un
-- atajo para algo que no esta en este repo, un ajuste que prefieres distinto—
-- sin editar los ficheros del repo y sin que te salgan como cambios en cada
-- `git pull`. Va el ultimo para que pueda pisar cualquier cosa de arriba.
--
-- Se mira si existe antes de cargarlo: sin el (quien clona el repo y aun no
-- paso el instalador) no hay nada tuyo que cargar, y un require de algo que no
-- esta seria un error en configerrors por nada.
local personal = os.getenv("HOME") .. "/.config/hypr/lua/personal.lua"
local f = io.open(personal, "r")
if f then
    f:close()
    require("lua.personal")
end
