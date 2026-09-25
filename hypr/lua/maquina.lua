-- hypr/lua/maquina.lua — lo que cambia de un equipo a otro.
--
-- Lo lee de `lua/local.lua`, que escribe instalar.sh y NO se versiona (ver «La
-- regla de oro» en el CLAUDE.md): la terminal de esta maquina, si es un
-- portatil, y la distribucion de su teclado. Aqui solo se ponen los valores de
-- fabrica para cuando ese fichero no esta — quien clona el repo y arranca antes
-- de pasar el instalador — o es de una version anterior y le falta algo.
--
-- Devuelve:
--   terminal    la orden de la terminal (la de lib/apps.py si no hay local.lua)
--   portatil    true / false. Con true se carga lua/teclado-laptop.lua.
--   kb_layout   las dos distribuciones, la activa primero (SUPER+DEL alterna)
--   kb_variant  su variante, en el mismo orden
--   motivo      por que se decidio lo de portatil (para `--revisar`)
--
-- POR QUE ESTO SE DECIDE AL INSTALAR, cuando la regla del repo es preguntar en
-- caliente: el chasis no cambia (un portatil no amanece siendo un sobremesa), y
-- el razonamiento entero, con el de la distribucion del teclado, esta en
-- scripts/lib/maquina.py. Lo que si cambio con Lua es que ya no hace falta el
-- truco de `nada.conf`: hyprlang no tenia condicionales y «no cargar nada»
-- habia que escribirlo como «cargar un fichero vacio». Aqui es un `if`.

local M = {
    terminal   = nil,
    portatil   = false,
    -- La distribucion del autor: su sobremesa lleva un ANSI de 75% sin AltGr
    -- (el porque, en lua/input.lua). En un portatil local.lua la pisa con la
    -- que se eligio al instalar el sistema.
    kb_layout  = "us,latam",
    kb_variant = "altgr-intl,",
    motivo     = "no hay lua/local.lua: pasa ./instalar.sh",
}

local ruta = os.getenv("HOME") .. "/.config/hypr/lua/local.lua"
local f = io.open(ruta, "r")
if f then
    f:close()
    -- Por el require de Hyprland: si local.lua tiene un error, sale en
    -- `hyprctl configerrors` con fichero y linea, y aqui se sigue con lo de
    -- fabrica en vez de dejar la sesion sin atajos.
    local ok, datos = pcall(require, "lua.local")
    if ok and type(datos) == "table" then
        for clave, valor in pairs(datos) do M[clave] = valor end
    end
end

-- Sin terminal apuntada, se pregunta a lib/apps.py (la misma logica que usa
-- instalar.sh): mejor unos milisegundos de mas en la primera carga que un
-- SUPER+ENTER que no abre nada.
if not M.terminal or M.terminal == "" then
    local p = io.popen(os.getenv("HOME") .. "/.config/hypr/scripts/lib/apps.py terminal 2>/dev/null")
    if p then
        M.terminal = (p:read("*l") or ""):match("^%s*(.-)%s*$")
        p:close()
    end
    if not M.terminal or M.terminal == "" then M.terminal = "kitty" end
end

return M
