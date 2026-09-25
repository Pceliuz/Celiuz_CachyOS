-- teclado-laptop.lua — lo que solo tiene sentido en un portatil.
--
-- ESTE MODULO NO SE CARGA SIEMPRE. hyprland.lua lo carga solo si lua/local.lua
-- dice `portatil = true`, y eso lo escribe instalar.sh despues de preguntarle a
-- scripts/lib/maquina.py. En un sobremesa no se lee ni una linea de aqui.
--
-- Se carga DESPUES de input.lua y de keybinds.lua, y eso es a proposito: gana el
-- ultimo que habla, asi que esto son correcciones sobre lo que ya dijeron los
-- otros dos. Si lo cargaramos antes, input.lua lo pisaria y parecerian ajustes
-- que "no hacen nada".

local S = "$HOME/.config/hypr/scripts/"

-- Como en keybinds.lua: cada atajo lleva descripcion, que es lo que enseña
-- `hyprctl binds` (con Lua, la accion sale como `__lua`). En los de orden, la
-- descripcion es la propia orden.
local function exec(t, orden, opciones)
    local o = { description = orden }
    for k, v in pairs(opciones) do o[k] = v end
    return hl.bind(t, hl.dsp.exec_cmd(orden), o)
end


-- --- Un teclado con TODAS sus teclas ----------------------------------------
--
-- Es el perfil «completo» de scripts/lib/maquina.py (`maquina.py teclado`).
--
-- input.lua pone `kb_options = lv3:switch`, que convierte el Ctrl DERECHO en
-- AltGr. Ahi esta bien puesto: el Attack Shark X820 es ANSI de 75% y NO TIENE
-- AltGr, asi que sin ese apano no hay tercer nivel y te quedas sin `@ \ ~ ^`.
--
-- El teclado interno de un portatil SI tiene AltGr y SI tiene la tecla `<>`. O
-- sea que heredaba el apano sin necesitarlo y perdia el Ctrl derecho a cambio de
-- nada. Aqui se deshace, y se deshace EN EL BLOQUE GLOBAL a proposito.
--
-- POR QUE GLOBAL Y NO UN `hl.device` CONCRETO, que es como estaba antes. El
-- bloque `input` de Hyprland se lo aplica a TODO teclado conectado. Un
-- dispositivo con nombre (`at-translated-set-2-keyboard`) solo rescataba el
-- teclado interno y dejaba con `lv3:switch` a todo lo demas: comprobado con
-- `hyprctl devices` en esta laptop, `ideapad-extra-buttons`, `video-bus` y
-- `power-button` seguian saliendo con `o "lv3:switch"` — y, lo que de verdad
-- importa, tambien cualquier teclado USB que enchufes al portatil. Vaciandolo
-- aqui, que se carga despues de input.lua, no queda ninguno fuera.
--
-- Si TU teclado si necesita el tercer nivel (uno ANSI sin AltGr, como el del
-- autor), la vuelta atras es una linea en tu personal.lua:
--     hl.config({ input = { kb_options = "lv3:switch" } })
--
-- `kb_layout` y `kb_variant` NO se repiten: al ser el mismo bloque global que
-- input.lua, lo que no se nombra se queda como estaba. Eso si hacia falta en el
-- dispositivo de antes, porque un bloque de dispositivo no hereda del global.
hl.config({ input = { kb_options = "" } })

-- El NumLock se deja como esta a proposito, y conviene saber por que para no
-- "arreglarlo" luego. En input.lua esta en `true` con el motivo de que el X820
-- no tiene bloque numerico y ahi la opcion ya solo enciende el LED. En un
-- portatil con teclado numerico de verdad, `true` es ademas lo que quiere
-- cualquiera: que el bloque escriba numeros y no flechas. Solo estorba en los
-- portatiles que superponen el numerico sobre las letras, que hoy son minoria y
-- suelen pedir Fn de todas formas. O sea que cambiarlo arreglaria a unos pocos y
-- romperia a la mayoria. Si eres de los pocos: `numlock_by_default = false`.


-- --- Touchpad ---------------------------------------------------------------
--
-- input.lua solo apaga el scroll natural, que es lo unico que le importaba a un
-- sobremesa con raton. Un portatil necesita el resto.
hl.config({
    input = {
        touchpad = {
            -- Tocar para hacer clic, sin llegar a hundir la superficie. Es lo que
            -- espera cualquiera que venga de otro sistema.
            tap_to_click = true,

            -- Dos dedos = clic derecho, tres = clic central.
            clickfinger_behavior = true,

            -- Ignora el touchpad mientras escribes. Sin esto, la palma roza la
            -- superficie a mitad de una frase y el cursor se va a otro parrafo: el
            -- sintoma es "se me mueve el texto solo" y cuesta relacionarlo.
            disable_while_typing = true,

            -- Arrastrar sin mantener el dedo hundido: tocas, tocas y deslizas.
            -- Se apaga el "bloqueo" porque deja el arrastre pegado hasta que
            -- vuelves a tocar, y se siente como si la ventana se hubiera quedado
            -- enganchada.
            tap_and_drag = true,
            drag_lock = false,

            natural_scroll = false,
        },

        -- Cuanto responde el touchpad. Va aparte del `sensitivity = 0` de
        -- input.lua porque ese esta calibrado para el raton, que en el mismo valor
        -- se queda corto aqui: cruzar la pantalla pidiendo tres pasadas de dedo.
        accel_profile = "adaptive",
    },
})


-- --- Brillo de la pantalla --------------------------------------------------
--
-- En este portatil las teclas de brillo NO salen del teclado: las emite el
-- `Video Bus` de ACPI, un dispositivo aparte (comprobado en
-- /proc/bus/input/devices). Da igual para el atajo —Hyprland recibe el simbolo
-- igual—, pero explica por que no aparecen al pulsar el teclado con
-- `xkbcli interactive-wayland`.
--
-- `repeating` y `locked` hacen falta las dos: subir el brillo de uno en uno
-- seria inutil, y a oscuras se sube el brillo ANTES de entrar.
--
-- brightnessctl escribe por logind cuando /sys/class/backlight es de root, que
-- es el caso normal. No hace falta regla udev ni estar en el grupo `video`.
-- `-n` al bajar es el suelo: deja el minimo en 1 y nunca en 0. Sin el, bajando
-- de 5 en 5 se llega a apagar la retroiluminacion del todo, y una pantalla negra
-- que no responde al brillo es indistinguible de un equipo colgado.
-- Pasan por `scripts/osd.sh`, como el volumen, para ver el brillo que queda.
local repite = { locked = true, repeating = true }
exec("XF86MonBrightnessUp",   S .. "osd.sh brillo subir", repite)
exec("XF86MonBrightnessDown", S .. "osd.sh brillo bajar", repite)


-- --- Modo avion y camara ----------------------------------------------------
--
-- En este portatil las emite `Ideapad extra buttons`, un tercer dispositivo
-- distinto del teclado y del Video Bus. En otros portatiles salen del teclado; da
-- igual, el simbolo que llega a Hyprland es el mismo.
--
-- SIN COMPROBAR, y se dice claro: probarlo aqui significaba tumbar la wifi de la
-- sesion en la que estabamos trabajando. El riesgo real no es que no funcione,
-- es que funcione DOS VECES: en algunos portatiles el propio kernel ya conmuta el
-- rfkill al pulsar la tecla, y entonces este atajo lo devuelve a donde estaba y
-- parece que la tecla no hace nada.
--
-- Como saber cual es tu caso: quita el atajo desde tu personal.lua
-- (`hl.unbind("XF86RFKill")`), recarga con SUPER+SHIFT+R y pulsa la tecla
-- mirando `rfkill list`. Si ya conmuta sola, dejalo quitado.
-- Necesita estar en el grupo `rfkill` (o una regla polkit) para escribir en
-- /dev/rfkill.
exec("XF86RFKill", "rfkill toggle all", { locked = true })

-- La tecla de la camara (`XF86WebCam`) se queda SIN asignar a proposito: no hay
-- ninguna accion obvia y util detras. Tapar la camara por software no la apaga
-- de verdad, y arrancar una app de video al pulsarla es de esas cosas que
-- sorprenden mas de lo que ayudan. Si algun dia le encuentras uso, es
--     hl.bind("XF86WebCam", hl.dsp.exec_cmd("<lo que sea>"), { locked = true })


-- --- La tapa ----------------------------------------------------------------
--
-- Al cerrarla se bloquea la sesion, con el mismo lock.sh de SUPER+L: misma
-- pantalla, mismo congelado de apps, mismas barras restauradas al volver.
--
-- `locked` es obligatorio aqui: sin el, el atajo no dispara con la sesion ya
-- bloqueada, y cerrar la tapa dos veces seguidas se quedaria sin hacer nada.
--
-- `Lid Switch` es el nombre que reporta `hyprctl devices` en el apartado
-- switches. Es el nombre estandar del interruptor de tapa en Linux.
--
-- NO se suspende a proposito. Suspender y volver es justo donde aparecen los
-- problemas feos en Wayland (mas con NVIDIA), y el sintoma seria "cierro la tapa
-- y pierdo la sesion". Si algun dia lo quieres, la linea es:
--     hl.bind("switch:on:Lid Switch", hl.dsp.exec_cmd("systemctl suspend"), { locked = true })
exec("switch:on:Lid Switch", S .. "lock.sh", { locked = true })

-- Al abrir, la pantalla vuelve. Hace falta decirlo: si la tapa se cerro con el
-- monitor ya apagado por hypridle, Hyprland no lo enciende solo al abrirla y te
-- encuentras una pantalla negra que parece un cuelgue. Es el mismo salvavidas
-- que SUPER+SHIFT+D.
hl.bind("switch:off:Lid Switch", hl.dsp.dpms({ action = "on" }),
        { locked = true, description = "encender la pantalla" })
