-- autostart.lua — lo que arranca con la sesion: barras, demonios, fondo...
--
-- Todo va dentro de `hl.on("hyprland.start", ...)`, que es el `exec-once` de
-- hyprlang: corre UNA vez, al arrancar la sesion. Medido el 2026-09-25: una
-- recarga (SUPER+SHIFT+R) vuelve a leer la config entera pero no vuelve a
-- disparar este evento, asi que no se duplica ningun demonio.
--
-- `hl.exec_cmd` pasa la orden por un shell, asi que `$HOME` se expande igual que
-- en los `exec-once` de antes.

local S = "$HOME/.config/hypr/scripts/"

hl.on("hyprland.start", function()
    -- Barra de estado y dock. Config en waybar/ (enlazado a ~/.config/waybar).
    -- No se lanza waybar directamente: el demonio arranca las cuatro instancias
    -- (la barra de arriba y el dock de abajo, cada una con su linea-tirador) y
    -- gestiona el auto-ocultado de las dos.
    hl.exec_cmd(S .. "waybar-autohide.py")

    -- A cada pantalla, el refresco mas alto que admita a su resolucion nativa.
    --
    -- Hace falta un demonio para esto porque Hyprland no sabe pedirlo: sus cuatro
    -- palabras para el modo (`preferred`, `highres`, `highrr`, `maxwidth`) no se
    -- pueden combinar, y ninguna dice «la resolucion nativa Y el mejor refresco a
    -- esa resolucion». El porque entero, con la trampa medida del `highrr`, esta
    -- en la cabecera de scripts/monitores.py.
    --
    -- `--demonio` porque el caso que importa es el de despues: enchufar una
    -- pantalla ya empezada la sesion. Se queda escuchando `monitoradded` y se la
    -- ajusta sola.
    --
    -- NO pisa nada tuyo: si nombras una salida en lua/personal.lua, se la salta.
    hl.exec_cmd(S .. "monitores.py --demonio")

    -- Auto-bloqueo por inactividad (hypridle, repo oficial cachyos-extra-v3).
    -- Los tiempos y el porque de cada uno estan en hypr/hypridle.conf, que
    -- hypridle encuentra solo: ~/.config/hypr es un enlace a hypr/ del repo.
    --
    -- Se arranca por su unidad de systemd y no con `hypridle` a pelo, por tres
    -- cosas que la unidad da gratis:
    --   - `Restart=on-failure`: si el demonio se cae, el auto-bloqueo dejaria de
    --     funcionar EN SILENCIO. Asi se levanta solo.
    --   - `PartOf=graphical-session.target`: se muere con la sesion, sin huerfanos.
    --   - Cae en `app.slice` como un .service, y lib/congelar.py solo congela
    --     unidades `.scope`, asi que el bloqueo no puede congelar a quien lo
    --     gobierna.
    -- La orden va aqui y no con `systemctl --user enable` a proposito: enable deja
    -- estado fuera del repo, y este archivo tiene que contar la sesion entera.
    hl.exec_cmd("systemctl --user start hypridle")

    -- Notificaciones (mako, repo oficial extra). Es quien atiende
    -- org.freedesktop.Notifications por D-Bus: sin el, todo lo que mande
    -- `notify-send` se pierde sin dejar rastro.
    --
    -- Por su unidad de systemd, por lo mismo que hypridle, y ademas por una razon
    -- propia: mako CAE EN app.slice COMO .service, y lib/congelar.py solo congela
    -- unidades `.scope`. Si se lanzara con `uwsm app --` como el resto de
    -- programas, tendria un scope propio y el bloqueo lo congelaria — y entonces
    -- cualquier app que mandara una notificacion con la pantalla bloqueada se
    -- quedaria esperando una respuesta por D-Bus que no llega.
    --
    -- La unidad es `Type=dbus` con BusName=org.freedesktop.Notifications, asi que
    -- systemd espera a que mako coja el bus antes de darla por arrancada.
    hl.exec_cmd("systemctl --user start mako")

    -- Historial de notificaciones. Escucha el bus y apunta todo lo que pasa por
    -- pantalla, con su hora; SUPER+H lo saca. El registro vive en
    -- $XDG_RUNTIME_DIR, que systemd borra al cerrar sesion, salvo lo que apartes a
    -- mano.
    --
    -- Va lo mas arriba posible a proposito: lo que llegue antes de que este vivo
    -- NO se graba, y un aviso perdido no se puede rellenar despues. No depende de
    -- mako —espia la llamada, no la atiende—, asi que no importa el orden entre
    -- los dos.
    --
    -- Y no lleva `uwsm app --`: con scope propio, lib/congelar.py lo congelaria al
    -- bloquear la pantalla, y justo entonces es cuando interesa que siga
    -- apuntando.
    hl.exec_cmd(S .. "avisos.py --demonio")

    -- Los auriculares Bluetooth: se conectan solos al que tengas encendido (el
    -- ultimo que usaste primero) y de uno en uno — con uno puesto, los demas no
    -- pueden entrar hasta que lo sueltes. El porque de cada regla esta en la
    -- cabecera de scripts/bluetooth.py. En un equipo sin Bluetooth se queda
    -- esperando a que aparezca BlueZ, sin gastar nada.
    --
    -- Va como unidad TRANSITORIA de systemd (`systemd-run`), y hace falta por lo
    -- que este demonio deja puesto: bloquea a los otros auriculares mientras usas
    -- uno, y ese bloqueo lo guarda BlueZ en disco. Si el demonio muriera sin mas,
    -- se quedarian bloqueados hasta la siguiente sesion. Asi:
    --   - `Restart=on-failure`: si se cae, se levanta y lo primero que hace es
    --     repasar los bloqueos.
    --   - `PartOf=graphical-session.target`: al cerrar sesion le llega un
    --     SIGTERM, y con el desbloquea todo antes de irse.
    --   - Cae en app.slice como .service, y lib/congelar.py solo congela `.scope`:
    --     el bloqueo de pantalla no lo para.
    -- Sin fichero de unidad fuera del repo, que es lo que pide la regla de
    -- hypridle de mas arriba. Si ya hay uno corriendo (otra sesion abierta), el
    -- segundo `systemd-run` sale sin hacer nada.
    --
    -- El diario:  journalctl --user -u celiuz-bluetooth
    hl.exec_cmd("systemd-run --user --unit=celiuz-bluetooth --collect --quiet"
        .. " -p Restart=on-failure -p RestartSec=5 -p PartOf=graphical-session.target "
        .. S .. "bluetooth.py --demonio")

    -- El historial del portapapeles (SUPER+SHIFT+V): apunta lo que copias. Es un
    -- `wl-paste --watch`, asi que muere solo con el compositor; y lleva un
    -- cerrojo para que haya uno por sesion aunque se lance dos veces.
    hl.exec_cmd(S .. "portapapeles.py demonio")

    -- Aviso de que distribucion de teclado quedo puesta al arrancar (us o latam,
    -- ver lua/input.lua). El script espera a que mako coja el bus antes de mandar
    -- nada: el arranque no garantiza orden, y un aviso mandado antes de tiempo se
    -- pierde sin dejar rastro.
    hl.exec_cmd(S .. "teclado.py avisar")

    -- Fondo de pantalla en video (mpvpaper, del repo oficial cachyos).
    -- El video activo es el enlace hypr/wallpapers/current; para cambiarlo se usa
    -- scripts/set-wallpaper.sh, no se toca este archivo.
    -- Si aun no hay ninguno elegido, el script no hace nada y no molesta.
    hl.exec_cmd(S .. "wallpaper.sh")
end)

-- Si quieres arrancar algo mas con la sesion y es solo tuyo, no lo anadas aqui:
-- ponlo en `lua/personal.lua`, que no se versiona y se carga el ultimo. Asi tus
-- cosas no te salen como cambios cada vez que traigas actualizaciones del repo:
--     hl.on("hyprland.start", function() hl.exec_cmd("mi-programa") end)
