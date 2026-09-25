-- tests/lib/hl_falso.lua — un `hl` de mentira para ejecutar la config Lua de
-- Hyprland sin Hyprland (lo usa tests/unidad/config-lua.sh).
--
-- Apunta cada llamada en `hl._` y deja el resultado en un JSON a mano (sin
-- librerias: el `lua` pelado del sistema no trae ninguna).
--
--   lua hl_falso.lua <salida.json>      con HOME apuntando a una casa cuya
--                                       ~/.config/hypr es la copia del repo
--
-- `require` se comporta como el de Hyprland para lo que importa aqui: busca en
-- ~/.config/hypr/?.lua. A diferencia del de Hyprland, un error NO se traga: en
-- una prueba se quiere ver.

local salida = arg[1]
local HOME = os.getenv("HOME")
package.path = HOME .. "/.config/hypr/?.lua;" .. package.path

local R = { opciones = {}, binds = {}, monitores = {}, env = {}, eventos = {},
            exec = {}, curvas = {}, animaciones = {}, reglas = {}, capas = {} }

local function fundir(dst, src, prefijo)
    for k, v in pairs(src) do
        local clave = prefijo and (prefijo .. "." .. k) or k
        if type(v) == "table" and not v.colors then
            fundir(dst, v, clave)
        else
            dst[clave] = v
        end
    end
end

local function dsp(nombre)
    return function(...)
        local args = { ... }
        return { dsp = nombre, args = args }
    end
end

hl = {
    config = function(t) fundir(R.opciones, t) end,
    bind = function(teclas, accion, opciones)
        R.binds[#R.binds + 1] = { teclas = teclas, accion = accion, opciones = opciones or {} }
        return { set_enabled = function() end }
    end,
    unbind = function(teclas) R.binds[#R.binds + 1] = { teclas = teclas, quitar = true } end,
    monitor = function(t) R.monitores[#R.monitores + 1] = t end,
    env = function(k, v) R.env[k] = v end,
    on = function(ev, fn) R.eventos[#R.eventos + 1] = { ev = ev, fn = fn } end,
    exec_cmd = function(cmd) R.exec[#R.exec + 1] = cmd end,
    curve = function(n, t) R.curvas[n] = t end,
    animation = function(t) R.animaciones[#R.animaciones + 1] = t end,
    window_rule = function(t) R.reglas[#R.reglas + 1] = t; return { set_enabled = function() end } end,
    layer_rule = function(t) R.capas[#R.capas + 1] = t; return { set_enabled = function() end } end,
    workspace_rule = function(t) end,
    device = function(t) end,
    dsp = {
        exec_cmd = dsp("exec_cmd"), dpms = dsp("dpms"), focus = dsp("focus"), exit = dsp("exit"),
        window = { close = dsp("window.close"), float = dsp("window.float"), move = dsp("window.move"),
                   drag = dsp("window.drag"), resize = dsp("window.resize") },
    },
}

dofile(HOME .. "/.config/hypr/hyprland.lua")

-- Lo que arranca con la sesion: se dispara hyprland.start como haria Hyprland.
local arranques = 0
for _, e in ipairs(R.eventos) do
    if e.ev == "hyprland.start" then arranques = arranques + 1; e.fn() end
end

-- JSON a mano, suficiente para tablas de cadenas, numeros y booleanos.
local function json(v)
    local t = type(v)
    if t == "table" then
        if #v > 0 or next(v) == nil then
            local p = {}
            for _, x in ipairs(v) do p[#p + 1] = json(x) end
            if #p > 0 or next(v) == nil then return "[" .. table.concat(p, ",") .. "]" end
        end
        local p, claves = {}, {}
        for k in pairs(v) do if type(k) == "string" then claves[#claves + 1] = k end end
        table.sort(claves)
        for _, k in ipairs(claves) do
            if type(v[k]) ~= "function" then p[#p + 1] = json(k) .. ":" .. json(v[k]) end
        end
        return "{" .. table.concat(p, ",") .. "}"
    elseif t == "string" then
        return '"' .. v:gsub('[%c"\\]', function(c)
            return string.format("\\u%04x", c:byte())
        end) .. '"'
    elseif t == "number" or t == "boolean" then
        return tostring(v)
    end
    return "null"
end

R.eventos = nil
R.arranques = arranques
local f = assert(io.open(salida, "w"))
f:write(json(R))
f:close()
