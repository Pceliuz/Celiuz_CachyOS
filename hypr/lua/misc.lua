-- misc.lua — ajustes sueltos que no encajan en otro modulo.

local C = require("lua.colores")

hl.config({
    misc = {
        -- EL NEGRO DE FONDO. Es lo que se ve donde no hay ni ventana ni fondo de
        -- pantalla: al arrancar antes de que mpvpaper cargue, y en los huecos de
        -- algunas transiciones. Hyprland trae ff111111, que es GRIS MUY OSCURO, no
        -- negro — y ese gris es justo lo que rompe el efecto OLED, porque el
        -- amatista deja de tener un negro de verdad contra el que resaltar.
        background_color = C.negro,

        -- RED DE SEGURIDAD DEL BLOQUEO. Con esto en true, un hyprlock nuevo puede
        -- ADOPTAR un bloqueo que quedo huerfano (porque el anterior murio o lo
        -- mataron) en vez de que Hyprland te plante la pantalla de "Oopsie daisy, it
        -- looks like you locked your screen but the lockscreen app died", que solo se
        -- sale yendo a otro tty. Es lo que paso el 2026-07-27.
        --
        -- Sin esta opcion, el bucle vigilante de scripts/lock.sh no puede hacer nada:
        -- el hyprlock que relanza no tiene derecho a retomar el bloqueo. Las dos
        -- piezas van juntas.
        --
        -- No abre ningun agujero: retomar el bloqueo sigue exigiendo la contrasena.
        -- Lo unico que permite es volver a DIBUJAR la pantalla de bloqueo.
        allow_session_lock_restore = true,

        -- EL FONDO EN MOVIMIENTO DETRAS DEL BLOQUEO. Con esto en true, Hyprland deja
        -- ver lo que hay debajo de la pantalla de bloqueo — que es lo que permite que
        -- se vea el video del fondo moviendose de verdad, y no una foto.
        --
        -- Se queda en FALSE aqui a proposito. Lo enciende scripts/lock.sh justo antes
        -- de bloquear y lo devuelve a este valor al desbloquear, porque el xray NO
        -- ensena solo el fondo: ensena TODO lo que hay debajo. Dejarlo puesto seria
        -- una fuga permanente — cualquier bloqueo que no pasara por lock.sh (y por su
        -- escritorio vacio y sus barras apagadas) ensenaria tus ventanas, tus
        -- sensores y tu IP a quien pasara por delante. Comprobado en anidado.
        session_lock_xray = false,
    },

    render = {
        -- SIN HDR AUTOMATICO A PANTALLA COMPLETA. De fabrica (1) Hyprland pasa el
        -- monitor a HDR cuando una app a pantalla completa lo pide, y Brave lo pide
        -- con un video de YouTube aunque el video no sea HDR. En la PC (RTX 3050,
        -- GS27QCA) eso es un cambio de modo: la pantalla se apaga, el driver se
        -- queda colgado en «Flip event timeout on head 0» (3 s cada vez), la
        -- primera F no llega a poner la pantalla completa y el video sale lleno de
        -- bloques. Lo delata el diario del kernel: «Infoframe changed on CRTC 0
        -- (hdr=1 ...)» justo antes de cada timeout (2026-11-20, siete veces en
        -- una tarde). Con 0 el monitor se queda en SDR y el video se ve como en
        -- la ventana. Quien tenga un monitor HDR y lo quiera, lo enciende en su
        -- personal.lua con `hl.monitor({ ..., cm = "hdr" })`.
        cm_auto_hdr = 0,
    },
})
