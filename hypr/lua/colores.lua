-- hypr/lua/colores.lua — LA PALETA, leida de conf/colores.conf.
--
-- La paleta NO se escribe aqui: vive en `conf/colores.conf`, en hyprlang, y es
-- la misma fuente de la que beben hyprlock (que sigue siendo hyprlang y la
-- hace `source`), `scripts/gen-colores.py` (barra, mako, pantalla de inicio) y
-- `lock-info.sh`. Una segunda copia en Lua seria la cuarta paleta del repo, y
-- un color copiado no falla nunca: se dibuja igual, del tono de otro (ver
-- «Trampas» en el CLAUDE.md). Asi que se lee el fichero y ya.
--
-- Devuelve una tabla { negro = "rgba(000000ff)", amatista = "rgba(b16cffff)",
-- ... } con el mismo nombre que la variable de hyprlang sin el `$`. El formato
-- `rgba(RRGGBBAA)` es el mismo que acepta hl.config.
--
-- Si el fichero faltara, se cae a los valores de fabrica de abajo (los del
-- repo) en vez de dejar la config llena de nil: un escritorio con el violeta
-- de fabrica es mejor que uno sin bordes. Y se dice por el diario.

local FABRICA = {
    negro       = "rgba(000000ff)",
    abismo      = "rgba(0d0418ff)",
    superficie  = "rgba(1a0830ff)",
    apagado     = "rgba(2d1b4eff)",
    violeta     = "rgba(6a00f4ff)",
    amatista    = "rgba(b16cffff)",
    neon        = "rgba(c77dffff)",
    luz         = "rgba(e4c7ffff)",
    tenue       = "rgba(8a7aa8ff)",
    alerta      = "rgba(eb6f92ff)",
    atencion    = "rgba(f6c177ff)",
    glow_activo = "rgba(c77dffcc)",
    halo        = "rgba(6a00f4aa)",
    sombra      = "rgba(000000cc)",
}

local C = {}
for nombre, valor in pairs(FABRICA) do C[nombre] = valor end

local ruta = os.getenv("HOME") .. "/.config/hypr/conf/colores.conf"
local f = io.open(ruta, "r")
if f then
    for linea in f:lines() do
        -- `$nombre = rgba(...)`, con lo que venga detras (un comentario) fuera.
        local nombre, valor = linea:match("^%s*%$([%w_]+)%s*=%s*(rgba%(%x+%))")
        if nombre then C[nombre] = valor end
    end
    f:close()
else
    io.stderr:write("colores.lua: no encuentro " .. ruta .. "; uso la paleta de fabrica\n")
end

return C
