-- monitors.lua — resolucion, posicion, escala y tasa de refresco de cada pantalla.
--
-- Sintaxis: hl.monitor({ output = nombre, mode = "resolucion@refresco",
--                        position = posicion, scale = escala })
--
-- AQUI NO SE NOMBRA NINGUNA SALIDA A PROPOSITO. Hasta el 2026-08-13 habia una
-- linea del equipo del autor —`HDMI-A-1, 1920x1080@100, 0x0, 1`, su monitor de
-- sobremesa— y el nombre de una salida NO identifica una pantalla: identifica
-- el conector. El HDMI de la laptop tambien se llama `HDMI-A-1`, asi que al
-- enchufar un televisor heredaba la linea entera y pasaban dos cosas, las dos
-- calladas:
--   - se le pedian 100 Hz que no tiene (cayo a 60, sin decir nada), y
--   - se le clavaba la posicion `0x0`, o sea el ORIGEN, con lo que la pantalla
--     interna se iba automaticamente a su derecha. El televisor quedaba a la
--     izquierda de la laptop pasara lo que pasara, y el raton salia al reves.
-- Es el mismo patron que ya mordio con el sensor hwmon y con la resolucion del
-- velo de hyprlock: un valor cableado que coincide con UNA de las dos maquinas.
--
-- La regla de abajo vale para cualquier equipo y no hay nada que ajustar:
--   `preferred`   el modo nativo que declara la propia pantalla en su EDID. No
--                 se usa `highrr` (la tasa mas alta) porque no mira la
--                 resolucion: el televisor de las pruebas anuncia 800x600@60.32,
--                 que tiene MAS refresco que su 1920x1080@60.00, y `highrr` lo
--                 habria dejado en 800x600.
--   `auto-right`  cada pantalla nueva se coloca a la derecha de la anterior, en
--                 el orden en que aparecen. Enchufar en caliente hace lo que
--                 esperas sin tocar nada.
hl.monitor({ output = "", mode = "preferred", position = "auto-right", scale = 1 })

-- EL REFRESCO NO SE QUEDA EN LO QUE DIGA `preferred`. Un monitor de 100 Hz suele
-- declarar 60 como preferido —los refrescos altos viven en los modos
-- extendidos—, asi que quedarse aqui seria dejarse la mitad de la pantalla sin
-- usar. Y no hay ninguna palabra que pida las dos cosas: el wiki de Hyprland dice
-- que los modos predefinidos «cannot be combined», y `highrr` a secas es la
-- trampa del 800x600 de aqui arriba.
--
-- Pero en Lua la config SI puede mirar: `hl.get_monitors()` trae los modos de
-- cada pantalla, con la marca de cual es el `preferred`. Asi que, para cada
-- pantalla que ya este encendida, se escribe una regla con SU nombre: la
-- resolucion del modo preferido y, dentro de ella, el refresco mas alto que
-- anuncie. 100 Hz en la PC del autor, 144 o 165 en otra, 60 en un televisor:
-- no hay ningun numero escrito aqui, sale de la propia pantalla.
--
-- Por que en la config y no solo en un script: cada recarga reaplica las
-- reglas, y con `preferred` a secas la pantalla BAJABA a 60 Hz y un script la
-- subia despues —dos cambios de modo, un parpadeo, en cada recarga (pasaba al
-- terminar `instalar.sh`, 2026-10-20)—. Con la regla buena ya escrita, recargar
-- no cambia el modo.
--
-- Lo que esto NO ve son las pantallas que aun no existen al leer la config: la
-- primera carga de la sesion (antes de que haya salidas) y una pantalla
-- enchufada despues. Esas caen en la regla generica de arriba, y las sube
-- `scripts/monitores.py`, que arranca desde lua/autostart.lua y reacciona al
-- enchufar y al recargar, con la misma eleccion. Para ver que haria:
--
--   hypr/scripts/monitores.py --ver
--
-- La regla lleva lo mismo que la generica (auto-right, escala 1): lo unico que
-- cambia es el modo. Y como `lua/personal.lua` se carga despues, una pantalla
-- que nombres ahi te obedece a ti y no a esto.
local function mejor_modo(pantalla)
    local modos = pantalla.available_modes or {}
    local ancho, alto
    for _, m in ipairs(modos) do
        if m.preferred then ancho, alto = m.width, m.height end
    end
    -- Sin modo marcado como preferido, la resolucion que tenga puesta.
    ancho, alto = ancho or pantalla.width, alto or pantalla.height
    local mejor
    for _, m in ipairs(modos) do
        if m.width == ancho and m.height == alto
           and (not mejor or m.refresh_rate > mejor) then
            mejor = m.refresh_rate
        end
    end
    if not (ancho and alto and mejor) then return nil end
    -- Con dos decimales, sin ceros de sobra: "100", "59.94", "143.86".
    local hz = string.format("%.2f", mejor):gsub("0+$", ""):gsub("%.$", "")
    return string.format("%dx%d@%s", ancho, alto, hz)
end

-- pcall: si la API cambia de forma en otra version de Hyprland, se pierde solo
-- esta mejora (queda la regla generica y el script), no el resto del modulo.
local ok, pantallas = pcall(function() return hl.get_monitors() end)
for _, pantalla in ipairs(ok and pantallas or {}) do
    local ok_modo, modo = pcall(mejor_modo, pantalla)
    if ok_modo and modo and pantalla.name then
        hl.monitor({ output = pantalla.name, mode = modo, position = "auto-right", scale = 1 })
    end
end

-- Si tu pantalla necesita algo distinto (una tasa concreta, escala, otra
-- disposicion), tu linea va en `lua/personal.lua`, que no se versiona. Ahi
-- nombras la salida y mandas tu: se carga despues que esto, y `monitores.py`
-- se salta cualquier salida que aparezca nombrada en ese fichero, asi que no vas
-- a estar peleandote con ninguno de los dos.
-- `hyprctl monitors` dice como se llama la tuya y que modos admite.
--   hl.monitor({ output = "DP-1", mode = "2560x1440@144", position = "0x0", scale = 1 })
--
-- La escala es siempre tuya y no se detecta a proposito: depende de la DISTANCIA
-- a la que miras, y eso no lo sabe ningun EDID. Un televisor de 1080p a distancia
-- de sofa son ~35 DPI y quiere 1.5; un monitor de 24" en la mesa son ~92 y quiere
-- 1. Ojo: Hyprland RECHAZA una escala que no de un tamano logico entero — en
-- 1080p las comodas son 1.5 (1280x720) y 1.25 (1536x864).
--
-- Y si lo que ves es la imagen SALIENDOSE por los bordes en un televisor, eso no
-- se arregla aqui: es el overscan del propio televisor. Se quita en su menu
-- ("Tamano de imagen" -> "Punto a punto" / "Just Scan" / "1:1"). Hyprland no
-- tiene ninguna opcion de underscan con la que compensarlo.
