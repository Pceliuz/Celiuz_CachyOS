-- windowrules.lua — reglas por ventana (flotante, opacidad, workspace fijo segun app).
-- Aqui van tambien las reglas especificas de tu flujo de seguridad (VMs, Burp,
-- etc) cuando se decidan.
--
-- Cada regla lleva `name`: es lo que la identifica en `hyprctl` y lo que permite
-- apagarla desde tu personal.lua sin tocar este fichero:
--     local r = hl.window_rule({ ... })   -- aqui
--     r:set_enabled(false)                -- o guardar la referencia

-- --- Terminales de consulta rapida (btop, nmtui) ---
-- Flotantes y centradas: son ventanas para mirar un momento y cerrar. Si
-- entraran en el mosaico le robarian la mitad de la pantalla a lo que estuvieras
-- usando, que es justo lo que no se quiere al echar un vistazo.
--
-- La clase "monitor-tui" no es de kitty: se la pasamos nosotros con
-- `terminal.sh monitor-tui ...` desde los clicks de waybar, para que floten SOLO
-- esas terminales y no todas las que tengas abiertas.
--
-- Recuerdo de hyprlang, por si alguna vez lees config vieja: en 0.53 las reglas
-- se rehicieron (criterio primero, `float on` con valor), y la forma antigua
-- solo fallaba en `hyprctl configerrors`, no en la salida de `hyprctl reload`,
-- que igual decia "ok". En Lua eso no puede pasar: el nombre de un campo mal
-- escrito es un error de la propia llamada.
hl.window_rule({
    name  = "monitor-tui",
    match = { class = "^(monitor-tui)$" },
    float = true, center = true, size = "1100 640",
})

-- La ventanita del resultado de recargar la config (SUPER+SHIFT+R). Misma idea:
-- se abre, lees y se va. Pequena porque casi siempre dice una sola linea.
hl.window_rule({
    name  = "config-reload",
    match = { class = "^(config-reload)$" },
    float = true, center = true, size = "900 320",
})

-- Un aviso del historial abierto entero (SUPER+H -> "Ver entero"). Mas alta que
-- las otras dos porque aqui lo que se lee es el cuerpo del mensaje, que puede
-- ocupar varias lineas, no una respuesta de una linea.
hl.window_rule({
    name  = "aviso-detalle",
    match = { class = "^(aviso-detalle)$" },
    float = true, center = true, size = "900 560",
})

-- La clase "dock-term" existe pero NO tiene regla, y es a proposito: es la que
-- lleva una app de consola puesta en el dock (un `.desktop` con Terminal=true,
-- que dock-manager.py abre por terminal.sh). Eso no es una consulta rapida sino
-- una app que pusiste tu, asi que sale en mosaico como las demas. Si prefieres
-- que floten, la regla va aqui.

-- --- Reglas de capa (layer_rule) ---
-- Los namespaces salen del campo "name" de cada .jsonc de waybar.
--
-- Estas reglas solo actuan al CREAR y DESTRUIR la capa, o sea al arrancar y
-- cerrar waybar — no en el auto-ocultado, porque al ocultarse waybar conserva
-- la superficie y solo la baja de capa. La animacion del auto-ocultado es el
-- fundido CSS de waybar/style.css.

-- --- Notificaciones (mako) ---
-- OJO: el namespace de la capa es `notifications`, NO `mako`. Sale de la
-- especificacion de layer-shell, no del nombre del programa; con `mako` las
-- reglas no casan y no avisa nadie.
--
-- El fondo de la notificacion es translucido a proposito (#1a0830eb, ver
-- mako/colores), asi que sin desenfoque el texto queda sobre lo que haya detras
-- y a veces no se lee. Con blur se convierte en cristal violeta.
--
-- `ignore_alpha 0.3` es lo que evita que se desenfoque TODO el rectangulo de la
-- capa: mako reserva una superficie mas grande que las notificaciones y el resto
-- esta en transparente total. Sin esto se veria un panel borroso flotando,
-- incluso sin ninguna notificacion a la vista.
hl.layer_rule({
    name  = "notificaciones",
    match = { namespace = "notifications" },
    blur = true, ignore_alpha = 0.3, animation = "slide",
})

-- El cambiador de escritorios (SUPER+TAB, scripts/vista-escritorios.py).
--
-- SIN DESENFOQUE, y es a proposito: su capa ocupa la pantalla entera pero esta
-- vacia salvo por las tarjetas del centro, porque lo que se esta eligiendo es el
-- escritorio de verdad que hay detras. Un `blur` sobre esta capa emborronaria
-- justo eso — la previsualizacion — que es lo unico que hay que ver.
hl.layer_rule({
    name  = "vista-escritorios",
    match = { namespace = "vista-escritorios" },
    animation = "fade",
})

-- Las cuatro superficies de waybar: la barra, el dock y sus dos lineas-tirador.
for _, capa in ipairs({ "waybar-main", "waybar-trigger", "waybar-dock", "waybar-dock-trigger" }) do
    hl.layer_rule({
        name  = capa,
        match = { namespace = capa },
        animation = "fade",
    })
end
