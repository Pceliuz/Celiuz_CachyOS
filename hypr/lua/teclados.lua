-- hypr/lua/teclados.lua — la distribucion de cada teclado que ya se pregunto.
--
-- Ningun teclado le dice al ordenador si sus teclas son latinoamericanas o
-- inglesas (se pregunto al hardware: «Not supported», como casi todos). Asi que
-- se le pregunta al usuario UNA vez por teclado, con una tarjeta, y la
-- respuesta se apunta en ~/.config/celiuz/teclados.conf, que es de cada equipo
-- y no vive en el repo. Lo hace scripts/teclados.py (demonio del arranque),
-- que ademas la aplica en caliente al contestar.
--
-- Aqui solo se vuelve a aplicar en cada carga de la config, porque lo puesto
-- en caliente (`hyprctl eval 'hl.device(...)'`) lo deshace un `reload`: medido
-- en anidado el 2026-10-20, el teclado volvio a la distribucion global.
--
-- El fichero lo escribe teclados.py, una linea por nombre de Hyprland,
-- separada por tabuladores:
--     nombre  kb_layout  kb_variant  id-del-aparato  descripcion
-- Con kb_layout = «-» es un aparato que dijo no ser un teclado (un raton que
-- se anuncia tambien como teclado): no se toca.
--
-- `kb_options` no se nombra a proposito: un `hl.device` que no lo dice hereda
-- el del bloque `input` global (medido), y eso es de cada maquina (input.lua y
-- teclado-laptop.lua).
--
-- Va antes que personal.lua, que puede pisarlo con su propio hl.device.

local base = os.getenv("XDG_CONFIG_HOME")
if not base or base == "" then base = os.getenv("HOME") .. "/.config" end

local f = io.open(base .. "/celiuz/teclados.conf", "r")
if not f then return end

for linea in f:lines() do
    if not linea:match("^%s*#") then
        local nombre, layout, variante = linea:match("^([^\t]+)\t([^\t]+)\t([^\t]*)")
        if nombre and layout ~= "-" then
            hl.device({ name = nombre, kb_layout = layout, kb_variant = variante })
        end
    end
end
f:close()
