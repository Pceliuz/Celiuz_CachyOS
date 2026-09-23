# Por dónde seguir

Notas para retomar el trabajo sin tener que reconstruir el contexto. Si esto se
queda viejo, manda el `README.md` y el `CLAUDE.md`.

Última sesión: **2026-09-23**, en el **portátil**, segunda parte: **repaso de
portabilidad** de lo recién subido, pensando en quien clone el repo con otra
máquina.

### Lo que se cambió, y por qué

- **El cerrojo del Bluetooth es configurable.** Era una decisión de uso metida
  en código: quien tenga unos cascos y un altavoz querrá los dos a la vez. Se
  apaga en `~/.config/celiuz/bluetooth.conf` (`cerrojo = no`, `auto = no`), que
  **no se versiona** y se relee sola al guardarla, como `personal.conf` para
  Hyprland.
- **El clic de la barra pasa por `bluetooth.py gestionar`.** Antes llamaba
  directo a `terminal.sh monitor-tui bluetui`: sin bluetui instalado eso abría
  una terminal que se cerraba sola, sin decir nada. Ahora avisa y dice el
  paquete.
- **`--ver` ya no miente** sobre el demonio: si no está la unidad de systemd,
  mira si hay un proceso suelto.
- **Las capturas no esperan si tienes las animaciones apagadas.** Es lo que hace
  quien va justo de recursos, y ahí no hay desvanecido que esperar.

### Lo que se midió (y una trampa que casi cuela un falso verde)

- **En un equipo sin Bluetooth el módulo desaparece de la barra**, y el resto
  (el reloj al lado) queda intacto. Hasta ahora se decía fiándose del manual de
  waybar; ahora está visto.
- **`"controller": "un-alias-que-no-existe"` NO simula un equipo sin adaptador**:
  waybar coge cualquier controlador y la barra se ve igual. La primera prueba
  dio verde sin probar nada. Lo que sí vale: `tests/anidado.sh` +
  `dbus-run-session` con `DBUS_SYSTEM_BUS_ADDRESS` apuntando al bus privado donde
  sirve `tests/lib/bluez_falso.py servir <json> --sin-adaptador`.
- **Sin BlueZ corriendo el demonio no se rompe**: lo dice y espera. Con BlueZ
  pero sin radio, no llama ni bloquea a nadie.

### Cuántas comprobaciones hay ahora

`unidad/bluetooth` 45, `e2e/bluetooth` 77, `unidad/captura` 16. Las tres cubren
lo nuevo: los ajustes, las dos ramas del clic, el equipo sin radio y la captura
sin animaciones.

### Un aviso que salió solo

El Hyprland anidado sacó este cartel: **«you are using the .conf config format,
support for which will be removed in Hyprland 0.57»**. Todo este repo es `.conf`.
No corre prisa —0.56 es la que hay— pero conviene mirarlo antes de esa versión,
porque el día que llegue no arrancaría la config entera.

---

Última sesión: **2026-09-23**, en el **portátil**: **el recuadro que salía
dentro de las capturas de zona** (`SUPER + S`).

### El síntoma

Cada captura hecha con `SUPER + S` traía un recuadro violeta dentro, del mismo
tamaño y en el mismo sitio, daba igual lo que se seleccionara. Con
`SUPER + SHIFT + S` (pantalla entera) no pasaba nunca.

### Lo que dijo la propia captura, sin tocar nada

Analizando la imagen que mandó el usuario, píxel a píxel:

- La franja de arriba (`y` 0–471) tenía un **tinte amatista `#b16cff` al 7,2 %**
  y la banda de abajo no. El mismo alfa cuadraba en colores muy distintos —el
  fondo plano y una burbuja verde de WhatsApp—, o sea que era una **capa
  encima**, no un cambio de contenido.
- La línea de `y` 472 era ese borde **al 42 % de opacidad**.
- La línea vertical de `x` 474 **no era un fallo**: es el separador de paneles
  de WhatsApp. Conviene descartar lo que es contenido antes de perseguirlo.

O sea: la capa de selección de slurp, **a mitad de apagarse**, dentro de la foto.

### La causa

Al soltar el botón, slurp termina — pero su capa no desaparece de golpe:
**Hyprland la desvanece** (`fadeLayersOut`). Medido con un cliente de
gtk-layer-shell de mentira que crea la misma capa (`namespace: selection`) y
sale solo: la capa se sigue viendo entre **90 y 125 ms** después de que el
proceso muere, pasando por 65 %, 55 %, 47 % y 39 % de opacidad. grim pide su
fotograma mucho antes de eso. Por eso `--full` no lo sufría: ahí no hay slurp.

### Dos caminos que NO valen (medidos, para no repetirlos)

- **`layerrule = noanim ...`**: en Hyprland 0.56 da `invalid field type noanim`,
  con valor y sin él. Solo sale en `hyprctl configerrors`.
- **`layerrule = animation none, match:namespace selection`**: se acepta sin
  error, pero **no apaga el desvanecido** — solo el deslizamiento. Con la regla
  puesta, la capa seguía viéndose igual. Apagar `fadeLayersOut` global sí lo
  arregla, pero se llevaría por delante la transición de las barras.
- **Preguntar a `hyprctl layers` y capturar**: la capa deja de listarse a los
  ~10 ms, mucho antes de dejar de verse. Necesario, pero no suficiente.

### El arreglo

`screenshot.sh` espera, y solo en el camino de la zona: primero a que Hyprland
deje de listar la capa (el fin del proceso) y después el plazo del desvanecido
(`ESPERA_SELECCION=0.3`, el doble del peor caso medido). No se puede preguntar
si una animación acabó, así que esa parte es un plazo fijo y está razonado en el
propio fichero.

### Cómo se comprobó

- **De punta a punta, con el script de verdad**: un `slurp` de mentira que pinta
  una capa verde chillón con el mismo `namespace` y devuelve una geometría, más
  un `wl-copy` que no hace nada, y `HOME` a un temporal. **Sin la espera: 4 de 4
  capturas con la capa dentro (51–71 % de píxeles verdes). Con ella: 4 de 4
  limpias (0,6 %, que es contenido real).** La receta está en el historial de
  esta sesión y se rehace en dos minutos con `gtk-layer-shell`.
- **`tests/unidad/captura.sh`** (14 comprobaciones, sin compositor): vigila la
  secuencia —que entre slurp y grim pasen ≥ 200 ms, que se pregunte por la capa,
  y que `--full` y `--ventana` NO paguen esa espera—. Quitando la llamada a la
  espera, falla con «solo pasaron 17 ms».

### Lo que queda de aquí

1. **Confirmarlo a mano**: un `SUPER + S` de verdad y mirar que la captura salga
   sin el recuadro. Es lo único que no se puede automatizar aquí.
2. Si algún día alguien sube el desvanecido de las capas, `ESPERA_SELECCION` se
   queda corta **en silencio**. La prueba no lo detecta: vigila la secuencia, no
   el fotograma.

---

La sesión anterior: **2026-09-21**, en el **portátil**: **el Bluetooth**. Hasta hoy se
manejaba solo por consola (`bluetoothctl`, unas funciones de fish y un demonio
`auris-reconectar` que vivía fuera del repo con la MAC de unos TWS cableada).

### Lo que se hizo

- **Un módulo en la barra**, el `bluetooth` de serie de waybar, a la derecha de
  la red. Clic: `bluetui` en la terminal flotante (repo oficial `extra`).
  Derecho: encender/apagar, y quita el bloqueo de rfkill si lo hay. Central:
  **soltar el auricular en uso**. Sin adaptador no aparece
  (`format-no-controller` vacío).
- **`hypr/scripts/bluetooth.py`**, que sustituye a `auris-reconectar` y ya vale
  para cualquiera: los auriculares **se conectan solos** al que esté encendido,
  **el último usado primero**; **con uno puesto los demás no entran** hasta
  soltarlo (el cerrojo); y **soltar a mano no se deshace solo** — ese no vuelve
  hasta apagar y encender el Bluetooth. Las reglas y su porqué, en su cabecera
  y en la sección «El Bluetooth» del README.
- Arranca desde `autostart.conf` como **unidad transitoria** (`systemd-run`,
  `celiuz-bluetooth`): `Restart=on-failure` y `PartOf=graphical-session.target`,
  porque deja estado en disco (ver abajo) y no puede morirse sin soltarlo.
- `instalar.sh` pide `bluetui` y el servicio de BlueZ **solo si hay adaptador**.
- Fuera del repo, en el portátil: `auris-reconectar` (script y unidad) **borrado
  y deshabilitado**, y `auris` / `auris-off` / `auris-estado` de fish pasan a ser
  envoltorios de `bluetooth.py conectar` / `soltar` / `--ver`.

### Lo que se midió, y cambió el diseño

**`Blocked` de BlueZ NO frena una conexión pedida desde este lado.** Con los TWS
bloqueados, `bluetoothctl connect` (y `Device1.Connect` por D-Bus) se puso a
buscarlos igual: acabó en `br-connection-page-timeout`, no en un rechazo. Solo
rechaza las conexiones que inicia el aparato. Por eso el cerrojo tiene **dos
capas**: bloquear a los demás de antemano y, si alguno se cuela (desde bluetui),
echarlo en el acto con un aviso que dice por qué.

Y `Blocked` **se guarda en disco** (`/var/lib/bluetooth`): si el equipo se apaga
con un auricular puesto, los otros amanecen bloqueados. El demonio apunta lo que
bloquea en `~/.local/state/celiuz/bluetooth.json` y **solo desbloquea lo suyo**:
lo que bloquees tú a mano no lo toca nunca.

«Lo soltaste tú» no se supone: BlueZ 5.87 trae el motivo de cada desconexión en
`Device1.Disconnected` (`Local`, `Remote`, `Timeout`, `Suspend`…).

### Cómo se probó

- `tests/unidad/bluetooth.sh` (28): `decidir()` a pelo, con fotos inventadas.
- `tests/e2e/bluetooth.sh` (70): el demonio de verdad contra
  `tests/lib/bluez_falso.py`, un BlueZ de mentira en un bus de `dbus-run-session`
  al que se apunta `DBUS_SYSTEM_BUS_ADDRESS`. **Sin ninguna variable de pruebas
  en el script.** Tres guardias antes de arrancar nada (bus privado, nombre
  `org.bluez` conseguido, `--ver` ve los falsos y no los tuyos).
- **Siete mutantes** (romper a propósito una regla y ver que la prueba cae).
  Dos sobrevivieron al principio y los dos eran de la prueba: el falso
  desconectaba ANTES de marcar `Blocked` (el real lo hace al revés), y las caídas
  llegaban antes de los 3 s de `MINIMO_EN_USO`, que tapaba el motivo. Ahora caen
  todos.
- **Falsa alarma, tres veces en la sesión:** «no tocó la caché real» falló porque
  la pantalla se **bloqueó sola a mitad de la suite** (o se desbloqueó) y
  `lock.sh` reescribió `lock-*`. Se confirma mirando la hora en `lock.log`.

### Lo que queda de aquí

1. **Probarlo con los TWS de verdad.** El demonio está corriendo en el portátil
   desde el 2026-09-21 y con los TWS apagados da `page-timeout`, que es lo
   esperado; falta encenderlos y ver que entran solos, soltar con el clic
   central, y apagar/encender el Bluetooth. `bluetooth.py --ver` y
   `journalctl --user -u celiuz-bluetooth` cuentan lo que pasa.
2. **El cerrojo con DOS auriculares reales no se ha visto nunca**: en el
   portátil solo hay uno emparejado. La lógica está cubierta por el e2e, pero la
   parte de «el kernel rechaza al bloqueado sin que el audio salte» viene de la
   documentación de BlueZ, no de una medida.
3. **En la PC**: `git pull && ./instalar.sh`, cerrar sesión y entrar. Si no
   tiene Bluetooth, el icono no debería salir (se fía del manual de waybar: un
   formato vacío esconde el módulo) y el demonio se queda esperando sin gastar.
   Mirarlo.
4. La batería de los auriculares en la barra depende de que la informen
   (`Battery1`); con los TWS no se ha visto.

---

La sesión anterior: **2026-09-14**, en el **portátil**. Salió de un fallo de uso:
`SUPER + L` llevaba cinco horas sin bloquear la pantalla.

**El atajo no estaba roto.** Es lo primero que se descartó y conviene recordar
cómo, porque el bind de Hyprland estaba perfecto (`hyprctl binds` lo daba con
`modmask 64`, sin submaps ni conflictos) y aun así no pasaba nada. Lo que lo
resolvió fue el **diario de `lock.sh`** (`~/.cache/celiuzpaper/lock.log`), que
tenía una línea por cada pulsación:

```
=== 2026-09-14 10:20:26 lock.sh arranca (pid 45650) ===
lock: ya hay un hyprlock corriendo en esta sesion, no hago nada
```

> **Ojo con el log de Hyprland para esto: NO apunta los `exec` de los binds.**
> Se buscó ahí primero y no había ni rastro de `lock.sh`, lo que parecía decir
> «el bind no dispara». Era mentira: `grep -c Executing` en el log da 0 siempre.
> Para saber si un bind corrió, el rastro es el del propio script.

### La avería: una carrera en el guardia de instancia única

A las **09:15:45 entraron dos `lock.sh` en el mismo segundo** (dos pulsaciones
seguidas). El guardia de entonces *miraba* «¿hay algún hyprlock vivo?» y
*actuaba* después, y entre lo uno y lo otro cabe otro `lock.sh` entero: los dos
miraron antes de que ninguno hubiera lanzado el suyo y los dos siguieron.

El `ext_session_lock` de Wayland **solo lo puede tener uno**. El segundo hyprlock
se quedó vivo sin conseguirlo —ni pintaba, ni moría— y a partir de ahí el guardia
lo veía y salía sin bloquear. Y la segunda instancia leyó el xray que acababa de
encender la primera, lo tomó por «el valor de antes» y al desbloquear lo dejó
**encendido para siempre**: la fuga permanente que vigila `tests/e2e/bloqueo.sh`.

### Lo que se hizo

Tres piezas en `lock.sh`, en ese orden y no en otro:

1. **`hyprctl locked`** en vez de contar procesos. Es el compositor diciendo un
   hecho; «hay algo que se llama hyprlock» era la suposición que falló. Se lee
   con **tres** respuestas —`si`, `no`, `nose`— y no con dos: `locked` **funciona
   pero NO sale en `hyprctl --help`**, o sea que es superficie no documentada.
   Un Hyprland que no la conozca contesta `unknown request`, y leer eso como
   «no bloqueada» haría que el script matara un hyprlock legítimo y
   **desbloqueara la pantalla sola**. Con `nose` no se toca nada y se bloquea
   igual.
2. **`flock`**: mirar y coger el turno en una sola operación atómica. Si no hay
   `flock` (caja sin util-linux) se sigue **sin** cerrojo: tratar «no hay flock»
   y «el turno lo tiene otro» igual dejaría una máquina sin bloquear nunca.
   El hyprlock se lanza con `9>&-` para que no herede el cerrojo.
3. **El huérfano se retira**, no se le cede el paso. La dirección segura de este
   fichero es acabar bloqueando; negarse en silencio es su peor fallo posible.

Un riesgo que destapó la propia prueba y casi se cuela: la primera versión salía
en cuanto la sesión estaba bloqueada, y eso **cerraba la vía de recuperación** de
la pantalla «you locked your screen but the lockscreen app died». Ahora, si está
bloqueada pero sin hyprlock, **relanza para retomar** (`allow_session_lock_restore`).

### Cómo se comprobó

`tests/e2e/bloqueo.sh` pasa de 28 a **38 comprobaciones**. La de la carrera se
ejecutó **contra el `lock.sh` viejo y falla** (`esperaba «1», obtuve «2»`): la
prueba reproduce la avería, no la decora. Las otras cuatro nuevas cubren la
pantalla muerta, un `hyprctl` sin `locked` y una caja sin `flock`.

Y con hyprlock **de verdad** en `tests/anidado.sh`: dos simultáneos → uno se
aparta; pulsar estando bloqueada → no apila; matar el hyprlock → el vigilante lo
relanza y `locked` sigue `true`.

> **Arreglado de paso** lo que esta nota tenía como «primer candidato»: el
> `pgrep -x` **global** de `tests/e2e/bloqueo.sh` ya busca por RUTA
> (`$FALSOS/$BLOQUEO`), así que bloquear la pantalla mientras corre la suite ya
> no la hace fallar en falso.

### Lo que queda de aquí

- **`grabar.sh` es la única pieza del repo sin pruebas.** Se sube en esta tanda
  (venía del 9 de septiembre) y en esta máquina **no se ha podido ejercitar:
  `wf-recorder` no está instalado**, así que `SUPER + R` hoy solo avisa. El
  instalador ya lo dice (`--revisar` lo saca como aviso).
- **Una rama de `lock.sh` sin prueba automática**: la que retira al huérfano. Pide
  un proceso cuyo `comm` sea exactamente `hyprlock` **con la firma de la sesión**,
  y un falso con almohadilla-bang tiene por `comm` su intérprete. Se comprobó a
  mano contra el huérfano real (pid 13318) antes de retirarlo.
- **Sin explicar**: al desbloquear, `congelar.py` descongeló
  `android-studio` cuando el bloqueo había apuntado `congeladas (0)` y lo daba
  por salvado. La red de seguridad (barre todos los scopes, no se fía del parte)
  hizo justo lo suyo, pero **algo lo congeló y no fue `lock.sh`**; no hubo
  suspensión y systemd no deja rastro de las transiciones del freezer.

---

Sesión anterior: **2026-09-07**, en el **portátil**. Sesión de repaso que acabó
en código: se revisó el repo entero, se cerró lo del 13 de agosto que llevaba
tres semanas sin commitear, y salió una pieza nueva —`scripts/monitores.py`—.

**TODO SUBIDO.** Al empezar había 1 commit sin empujar (el de la pantalla de
inicio de sesión, del 10 de agosto) y trabajo suelto de dos días distintos.

Lo que se comprobó antes de tocar nada, que es lo que conviene repetir al
recoger esto en la otra máquina: **21 pruebas / 386 comprobaciones** en verde,
`instalar.sh --revisar` sin pendientes y con las 8 secciones enteras,
`configerrors` vacío, los demonios vivos y —esto es lo que casi nunca se
mira— **el demonio de las barras corriendo el código nuevo** y no el de antes
del reinicio (`ps -o lstart` contra la fecha del fichero).

> Un aviso sobre las pruebas: `e2e/bloqueo.sh` falló una vez y **no era el
> código**. Comprueba «no quedó ningún bloqueo vivo» con un `pgrep -x`
> **global**, así que si bloqueas la pantalla mientras corre la suite, ve tu
> hyprlock de verdad y lo toma por suyo. Es el patrón que el `CLAUDE.md` ya
> documenta —`pgrep -x` no distingue de qué sesión es cada proceso— y
> `lib/canales.sh` tiene la herramienta buena (`pids_de_esta_sesion`).
> **Está sin arreglar**, es el primer candidato para la próxima sesión.

### Lo nuevo: cada pantalla coge su mejor refresco sola

Salió de una pregunta, y la pregunta era buena: al quitar de `monitors.conf` la
línea del monitor de la PC (ver más abajo, lo del 13) se quitó también su
`@100`, y `preferred` **es el modo del EDID** — un monitor de 100 Hz suele
declarar 60. O sea que «portable» se había vuelto «a 60 Hz en todas partes».

Y no se arregla con configuración: el wiki dice que los modos predefinidos
*«cannot be combined»*, así que «la resolución nativa **y** el mejor refresco **a
esa** resolución» no se puede pedir. `highres` deja el refresco sin especificar y
`highrr` es la trampa del 800x600 del televisor. Lo pidieron en
hyprwm/Hyprland#8758 y se cerró como *not planned*.

Pero `hyprctl monitors -j` trae `availableModes` entero, así que elegir bien es
aritmética. Eso es **`hypr/scripts/monitores.py`**, que arranca desde
`autostart.conf` con `--demonio` y reacciona a `monitoradded`. Tres cosas suyas
que conviene no deshacer, y están en el `CLAUDE.md`: agrupa **por resolución
primero**; **no toca la escala** (depende de la distancia a la que miras, y eso
no lo sabe ningún EDID); y **se salta cualquier salida nombrada en
`personal.conf`**.

> **En el portátil esto no hace nada, y está bien así**: `personal.conf` fija las
> dos salidas porque el televisor necesita su escala 1.5. Es el cambalache
> conocido — fijar la escala te cuesta el refresco automático. Si molesta, la
> mejora pendiente es saltarse una salida solo cuando su línea fije **el modo**,
> no cuando fije escala o posición.

> **PENDIENTE EN LA PC (2026-09-08 por la noche).** Tras `git pull &&
> ./instalar.sh`, cerrar sesión y volver a entrar, **no le escribas ninguna línea
> de monitor**: debería coger sus 100 Hz sola. Se comprueba con
> `hypr/scripts/monitores.py --ver`, que es ensayo en seco y no toca nada. Es lo
> único de todo esto que no se ha podido verificar en la máquina que toca.

### Y lo que llevaba desde el 13 de agosto sin subir

Aquella sesión salió de conectar un televisor por HDMI al portátil, y destapó el
mismo patrón de siempre: **un valor cableado que coincide con una de las dos
máquinas**. Está contado entero en el `CLAUDE.md`; el resumen:

- `conf/monitors.conf` llevaba la línea del monitor de la PC, con el comentario
  de que «en otra máquina no existe ese nombre». **Sí existe**: el nombre de una
  salida es el del **conector**, y el HDMI del portátil se llama igual. Al
  enchufar el televisor heredaba los 100 Hz que no tiene y la posición `0x0` —el
  origen—, así que la pantalla interna se iba sola a su derecha y el ratón salía
  al revés.
- **waybar dibuja una superficie por salida**, y `waybar-autohide.py` estaba
  escrito para una sola pantalla en tres sitios. El grave: `layer_levels()`
  devolvía un nivel por namespace escrito dentro del bucle de monitores, así que
  con dos salidas **ganaba la última**. Y como waybar solo ofrece el toggle y lo
  aplica a todas sus superficies a la vez, dos superficies desfasadas ya no se
  juntan con señales — la señal mueve las dos y conserva el desfase. Barra y dock
  puestos en el portátil y escondidos en el televisor, para siempre. El único
  remedio es relanzar (`Bar.realinear`).

Lo vigilan `tests/unidad/barras-multipantalla.sh` (falla 27 de 28 contra el
código anterior) y `tests/unidad/monitores.sh`, que tiene la trampa del 800x600
como caso de prueba.

Antes, el **2026-08-10**, en el **portátil**, recogiendo lo de la PC (la
paleta del bloqueo y el redondeo medido). El pull entró limpio y no rompió nada
—18 pruebas, `--revisar` sin pendientes, `configerrors` vacío—, pero verificarlo
destapó un fallo **que ya llevaba dos sesiones ahí**: el resumen de
`lib/pantalla.py` reventaba con `KeyError: 'lock_tarjeta_w'`, la medida que dejó
de generarse al pasar el bloqueo de tarjeta a columna en `4ade398`.

Lo que importa no es el `KeyError`, es **por qué nadie se enteró**: `instalar.sh`
decidía si había ido bien mirando si salió texto (y un fallo a media impresión
deja texto), la prueba comprobaba el `$?` una línea tarde —medía el `afirmar`
anterior— y su otra afirmación pasaba en verde justamente porque el traceback
llenaba la variable. Tres tapaderas, la sección 7 cortada por la mitad y «sin
pendientes» al final. Está contado entero en el `CLAUDE.md`.

Arreglado por los tres sitios: el resumen ya no nombra medidas que no existen y
degrada a `?` en vez de reventar, `instalar.sh` mira el **código de salida** y
avisa, y la prueba ejecuta la CLI de verdad (falla 6 de 27 contra el código
anterior, y caza un renombrado por el `?`).

> La costumbre que lo habría cazado antes, y que conviene mantener: **al traer
> cambios, no te quedes en «las pruebas pasan»**. Ejecuta también lo que solo
> mira un humano —`instalar.sh --revisar` entero, leyendo cada sección— y
> sospecha de cualquier apartado que termine a media frase.

Y después, en la misma sesión, **la pantalla de inicio de sesión se puso al día
con la de bloqueo**. Tenía el diseño anterior —la tarjeta violeta centrada— y su
propia cabecera lo decía: se quedó atrás cuando el bloqueo pasó a columna en
`4ade398` y llevaba una semana así. La misma enfermedad de la mañana: **una copia
no avisa cuando se separa de su original**, porque sigue siendo válida por su
cuenta.

Ahora `sddm/celiuz/Main.qml` es la banda de la izquierda con su filo amatista, la
columna con título, cuenta, reloj, fecha y campo, y las **mismas medidas** —469
de banda, 65 de margen, campo de 299x40 y redondeo 10 en esta pantalla, idénticas
a las que da `pantalla.py`—. Lo que el bloqueo no tiene se colocó donde no
estorba: sesión y teclado al pie de la banda, y el apagado abajo a la derecha,
lejos del campo de la contraseña. El velo bajó de 0.36 a 0.30, que es el de
hyprlock.

> **`tests/unidad/login-bloqueo.sh` es el cerrojo nuevo**, y es el que faltaba:
> compara las 16 medidas base, las constantes de escala y las transparencias de
> las dos pantallas. Falla 8 de 12 contra el tema anterior, o sea que habría
> cazado la separación el día que ocurrió.

Comprobado de verdad con `sddm-greeter-qt6 --test-mode`, capturando las dos
formas en que llega: **sin `fondo.jpg`** (que es como lo recibe quien clona el
repo — sale el degradado de la paleta) y con él. Los números se leyeron
enseñándolos en la propia pantalla, porque el `console.log` de QML no sale por el
stderr del greeter.

> **OJO, ESTO NO SE VE HASTA REINSTALAR EL TEMA.** Lo que sale al arrancar es la
> copia de `/usr/share/sddm/themes/celiuz`, así que hace falta `./instalar.sh
> --sddm` (es el único paso que pide root). Mientras no se pase, el arranque
> sigue enseñando la tarjeta vieja.

Antes, el **2026-08-09**, en la **PC**, recogiendo lo del portátil. Se trajo
el rediseño del bloqueo y se le pasó la pregunta de siempre —*¿esto vale para
quien clone el repo?*—, de la que salieron **tres colores y una medida que no
salían de donde deberían**. Ver «La paleta del bloqueo», aquí abajo.

Antes, el mismo día en el **portátil**, la sesión de aspecto: el
icono de CeliuzPaper —que llevaba sin verse en el dock—, los iconos de la barra
más grandes, los workspaces convertidos en **puntos**, y la pantalla de bloqueo
rediseñada a una **columna a la izquierda**. Ver abajo, que de las tres salieron
fallos que no se veían.

**TODO SUBIDO Y SINCRONIZADO.** Y por tercera vez seguida el push se rechazó a
mitad —esta vez fue el portátil el que subió estas notas mientras la PC
trabajaba—: rebase, sin conflictos (solo tocaba este fichero), y **todo
verificado otra vez después**. **18 pruebas** en verde, `instalar.sh --revisar`
sin pendientes, `configerrors` vacío, y la sesión viva intacta: un solo demonio
de cada uno con los mismos PID que antes de empezar. Respaldo en
`~/respaldo-dotfiles-20260809/`.

> Que el push se rechace ya no es un imprevisto, es **el modo normal de trabajar
> a dos máquinas**. La costumbre que funciona: `git fetch` justo antes de
> empujar, rebase, y volver a verificar entero — nunca dar por buena la
> verificación de antes del rebase.

> Antes del rebase se copiaron aparte los cinco generados (`dock-apps.json`,
> `dock.jsonc`, `dock-icons.css`, `local.conf`, `local.jsonc`). No hicieron
> falta, pero es la precaución del `CLAUDE.md` y cuesta diez segundos.

Antes, el **2026-08-08**, en la **PC**: llegó el historial de
notificaciones (`SUPER+H`), la captura de la ventana con foco (`SUPER+ALT+S`),
se cerró el diálogo de «no responde» que asomaba sobre la pantalla de bloqueo, y
apareció `hypr/conf/personal.conf` para lo que es de una máquina y de nadie más.
Respaldo previo en `~/respaldo-dotfiles-20260808/`.

Antes, el **2026-08-07** en el **portátil**. Se cerró el caso de las barras
que no se ocultaban, se veían sobre el bloqueo y salían dobles al desbloquear:
eran **un solo** fallo, un demonio huérfano de la sesión del 05 (ver abajo). De
tirar de ese hilo salió lo demás: **nada de una sesión puede llamarse igual en
dos sesiones**, ni los FIFO de órdenes, ni el socket del fondo — y **ya no queda
ningún `pkill` por nombre** en el repo.

Antes, el **2026-08-05**, una auditoría de «¿esto vale para quien clone el
repo?», que sacó tres cosas que la
adaptación anterior no había cubierto: la distribución del teclado —la laptop
escribía con la de la PC—, ocho rutas cableadas a `~/dotfiles` en ficheros que el
cerrojo no miraba, y el sensor de temperatura de la barra, que seguía siendo el
del Ryzen de la PC. Antes, el supervisor de las barras y el perfil de teclado de
portátil para todos los teclados.

## Lo primero al abrir el repo

```sh
./tests/run.sh          # 18 pruebas. Deben salir todas
./instalar.sh --revisar # no debe sacar avisos inesperados
hyprctl configerrors    # vacío
```

Si las pruebas fallan **antes** de tocar nada, eso es lo que hay que arreglar
primero: significa que algo del sistema cambió por debajo (una actualización de
Hyprland, de mpv o de waybar).

### Y si acabas de traer cambios con la sesión abierta

Los demonios que ya estaban corriendo son del código **viejo**, y eso no se nota
hasta que algo falla raro. Lo más corto y seguro es **cerrar sesión y volver a
entrar**. Si no quieres, hay que relanzarlos a mano:

```sh
hyprctl dispatch exec "$HOME/.config/hypr/scripts/waybar-autohide.py --reiniciar"
hyprctl dispatch exec "$HOME/.config/hypr/scripts/wallpaper.sh"
```

Van por `hyprctl dispatch exec` y no a pelo para que cuelguen de Hyprland, como
un `exec-once`; lanzados desde una terminal se mueren con ella.

**Y después comprueba que no quedó un `mpvpaper` de más** (`pgrep -c mpvpaper`
tiene que decir 1). Al traer los canales con firma pasó justo eso: el que ya
corría no lleva firma, el código nuevo no lo reconoce y levanta otro al lado —
el huérfano se quedó gastando GPU con **1 GB de RSS**. Está contado en el
`CLAUDE.md`.

---

## La paleta del bloqueo (2026-08-09, PC)

Al traer el rediseño se le pasó la pregunta de la casa —*¿esto sería correcto en
el equipo de otra persona?*— y salieron **cuatro cosas que no venían de donde
deberían**. Ninguna fallaba; ése es justo el problema.

**Tres colores fuera de la paleta.** `placeholder_text` ponía `#8b86a3` cuando
`$tenue` es `#8a7aa8` —una copia que ya se había separado sola—, y el velo más
dos sombras usaban `090312`, que no es de nadie: lo parecido es `$abismo`,
`0d0418`. Para quien clone el repo eso significa cambiar la paleta y encontrarse
media pantalla de bloqueo con el violeta del autor.

El del campo estaba copiado porque es **marcado Pango**, que no entiende el
`rgba()` de hyprlang, y se había dado por hecho que no había alternativa. La hay,
y se midió en el anidado antes de creérselo: **hyprlang sí sustituye variables
dentro del marcado Pango**. Se pintó un placeholder de verde puro por variable y
salió verde. Lo que faltaba era la paleta en formato Pango, y eso ya sabe hacerlo
`gen-colores.py`: cuarto destino, `hypr/conf/colores-pango.conf`.

> Ahí dentro se lee `$pango_tenue = ##8a7aa8`, con **dos** almohadillas. No es
> una errata: en hyprlang `#` abre comentario, así que un color literal se escapa
> doblándola. Con una sola, la variable queda vacía y el texto sale sin color,
> sin dar ningún error.

**Y una medida muerta.** `$lock_rounding` se calculaba, se escribía en el
generado y se declaraba en el `.conf`… y no la leía nadie: se quedó suelta al
pasar de la tarjeta a la columna. Mientras tanto el campo tenía un `rounding = 14`
escrito a mano — o sea que el único redondeo visible era el único que no
escalaba. En 1080p no cambia nada; en el portátil pasa de 14 fijo a 10.

**El cerrojo es `tests/unidad/paleta-bloqueo.sh`**, y como manda la casa se
comprobó contra el código anterior: **falla 7 de sus 9**, diciendo fichero, línea
y color. Lo que exige es lo único exigible sin prohibir los literales —que en
hyprlock son inevitables, porque no hay forma de escribir «`$amatista` al 55%»—:
**la parte RGB de cada literal tiene que ser la de algún color de
`colores.conf`**; el alfa es libre.

Verificado dibujando el bloqueo con hyprlock de verdad en `tests/anidado.sh`,
**y esta vez a 1920x1080**, con la receta de más abajo (`hyprctl keyword monitor`
dentro del anidado): la proporción de la pantalla de casa, no la de la ventanita.

## La sesión de aspecto (2026-08-09, portátil)

Tres encargos que parecían de cinco minutos cada uno. De los tres salió un fallo
que no se veía, y ése es el patrón que conviene recordar: **en lo visual, «se
dibuja algo» no significa «está bien»**.

### 1. El icono de CeliuzPaper no se veía en el dock

No faltaba el icono: el SVG llevaba su comentario de diseño **entre la
declaración XML y el `<svg>`**, y gdk-pixbuf olfatea el formato en los primeros
bytes. Se plantaba con *«Couldn't recognize the image file format»*, y como el
dock carga los iconos por `background-image`, una imagen que no carga no da
error — deja un botón **vacío**. La app estaba ahí, solo que invisible salvo por
el tooltip.

El comentario ahora va dentro del `<svg>`. **Cualquier icono nuevo del repo
empieza por `<svg`**, y hay un comando de una línea para comprobarlo en el
`CLAUDE.md`.

### 2. Los iconos de la barra, y los workspaces como puntos

Los glifos pasaron del 130% al 150%, y con ellos **cuatro sitios que no se
enteran unos de otros**: la altura de la barra (o GTK recorta las pastillas de
hover), el `font-size` de los workspaces, y el `icon-size` del tray. Está
anotado en el comentario de `style.css`.

Los workspaces son ahora puntos, y el activo una pastilla. Dos hallazgos:

- **`#workspaces button.occupied` no había pintado nunca nada.** El módulo de
  Hyprland marca los workspaces **vacíos** (`.empty`), no los llenos. Con números
  apenas se notaba; con puntos, un workspace con ventanas se veía igual que uno
  vacío. Se descubrió pintando `.empty` de rojo. La lógica va ahora al revés
  —encendido es el caso base— para que degrade del lado bueno.
- **En el CSS de GTK el alto solo se acota con el margen vertical.** `min-height`
  es un suelo y no hay techo; probado también moviendo la forma a la etiqueta,
  que parecía la salida elegante: se estira igual. O sea que la forma del punto
  sale de una **resta** contra el alto de la barra, y los dos números viven en
  ficheros distintos. A 60 px de barra los puntos salen cápsulas verticales y el
  activo un círculo — el diseño del revés, sin un solo error. Lo vigila
  `tests/unidad/barra-workspaces.sh`.

### 3. La pantalla de bloqueo, a una columna izquierda

Era una tarjeta en el centro y se plantaba justo encima de lo que estuvieras
mirando. Ahora: banda oscura a la izquierda, título y usuario centrados en ella,
y debajo reloj, fecha, campo y una fila con batería, teclado y red.

Lo que hay que saber si se toca:

- **`halign` de hyprlock centra en la PANTALLA.** Para centrar dentro de la banda
  hace falta `halign = center` con un desplazamiento **negativo**
  (`$lock_col_centro`). Con `halign = left` la x es el borde izquierdo del texto
  y habría que saber cuánto mide — cambia con la fuente y con los kanji. Ese
  número depende del ancho del monitor, así que lo calcula `pantalla.py`.
- **`px()` tiene un suelo (`FACTOR_MIN`)**, o sea que en una pantalla estrecha
  devuelve más ancho del que cabe. Medido en el anidado con una salida de 351 px:
  la banda salía de 409 y el desplazamiento se volvía **positivo** — el título se
  iba a la derecha en vez de centrarse. Todo ancho que tenga que caber lleva
  ahora su tope contra el ancho real.
- **La fila de datos** la imprime `hypr/scripts/lock-info.sh` en una línea con
  marcado Pango. Una etiqueta y no tres porque hyprlang no sabe sumar, y así lo
  que no aplica —la batería en la PC— desaparece sin dejar hueco. Sus colores se
  **leen** de `colores.conf`: escribirlos habría sido una cuarta copia de la
  paleta, y quien clone con otro tono se encontraría el violeta del autor.

### Cómo se prueba una pantalla de bloqueo sin bloquearte

Esto es lo más reutilizable de la sesión. **No se prueba en el escritorio vivo**
—así se quedó bloqueado el autor el 2026-08-03—, se prueba en el anidado:

```sh
./tests/anidado.sh env FUERA_RUNTIME="$XDG_RUNTIME_DIR" /ruta/a/tu-script.sh
```

y dentro del script, antes de lanzar nada: poner la salida a la resolución de
verdad (`hyprctl keyword monitor <nombre>,1366x768@60,0x0,1`), generar las
medidas con `pantalla.py --hyprlock`, lanzar `hyprlock -c ... --no-fade-in`,
esperar, `grim`, y matarlo.

**El seguro no puede ser el nombre del display.** El anidado llama al suyo
`wayland-1`, igual que la sesión de fuera, así que compararlos da un falso
positivo — pasó en esta sesión. Lo que separa a los dos es el
**`XDG_RUNTIME_DIR`**, y de propina que `$HOME` sea el desechable.

### Lo que quedó pendiente de aquí

- **SDDM ya no hace juego con el bloqueo.** El login sigue con la tarjeta violeta
  centrada. Está anotado en el `README.md` para que no parezca un descuido. Si se
  quiere igualar, es trabajo aparte y encima es lo único que pide `sudo`.
- **El teclado sale como «Spanish», no «latam».** Es lo que reporta Hyprland como
  distribución activa (`active_keymap`), y distingue bien de «English». Para el
  código corto habría que mapearlo a mano.
- El usuario **aún no ha visto el bloqueo nuevo en su pantalla**: falta el
  `SUPER+L` real. Ya está dibujado con hyprlock de verdad en el anidado **y a
  1920x1080** (la sesión de la PC, 2026-08-09), así que la proporción de la
  pantalla de casa está comprobada; lo que queda es verlo con los ojos.

## Lo último: las barras dobles eran un huérfano (2026-08-07, portátil)

Lo trajo el usuario como **tres** quejas: las barras no se ocultaban aunque
hubiera una app delante, se veían sobre la pantalla de bloqueo —donde no debe
haber más que el fondo— y al desbloquear parecían «dos barras peleándose». Era un
solo fallo, y ninguno de los tres síntomas se parece a él.

**Había DOS demonios.** `waybar-autohide.py` de la sesión del **05** seguía vivo
el 07, adoptado por `systemd --user`. Y sus barras se veían porque
**`WAYLAND_DISPLAY` se reutiliza entre sesiones** (`wayland-1` las dos veces).
Medido en la sesión viva antes de tocar nada:

- PID 35735 (del 05) con `HYPRLAND_INSTANCE_SIGNATURE` de una instancia muerta,
  dueño de las **cuatro waybar que se veían**, y con el FIFO marcado `(deleted)`
  en `ls -l /proc/35735/fd`: sordo, no le llegaba ninguna orden.
- PID 148924 (del 07) con el FIFO bueno —o sea que `lock`, `unlock` y `SUPER+C`
  iban a él— y sus cuatro waybar en **zombi**.

De ahí salen los tres síntomas: no se ocultaban porque el socket muerto no
contesta y el valor de reserva de `read_state()` es 0 ventanas («escritorio
vacío», que es cuando se quedan puestas); se veían en el bloqueo porque el `lock`
llegaba al demonio bueno, que mata solo las suyas; y al desbloquear el `unlock`
relanzaba las cuatro del bueno **encima** de las cuatro del huérfano.

Es **la misma enfermedad del «susto del fondo»** del 04, que se documentó en el
`CLAUDE.md` como regla general y solo se vacunó a un enfermo: `wallpaper-pause.py`
tenía su `ABANDONO` y este no.

Arreglado por las dos puntas, y hacen falta las dos:

1. **`ABANDONO`** (60 s sin poder hablar con su Hyprland → se aparta y se lleva
   sus barras). Cubre al que se queda huérfano ya en marcha.
2. **`matar_otros()` en TODOS los arranques**, no solo con `--reiniciar`. Era lo
   que dejaba que el demonio nuevo conviviera tan tranquilo con el huérfano al
   abrir sesión.

Dos trampas que costaron una vuelta cada una, las dos en el `CLAUDE.md`:
**«contestó» no es «está vivo»** (el `recv` tiene timeout de 1 s, así que un
Hyprland atareado devuelve el mismo vacío que uno muerto; lo que decide es el
`connect`, y por eso existe `hypr_alcanzable()`), y **el barrido se filtra por
`XDG_RUNTIME_DIR`** — sin eso, correr las pruebas mataría el demonio de la sesión
real, que es el `pkill` por nombre de siempre.

Lo cubre `tests/unidad/barras-huerfanas.sh` (9 comprobaciones), **comprobada
contra el código viejo: fallan 4 de 9**. Y verificado en la sesión viva: un solo
demonio, las barras en `bottom` con ventanas abiertas, y el ciclo del bloqueo por
el FIFO deja **0** barras con el bloqueo puesto y **4** —no 8— al desbloquear.

**Y el primer intento (`7c7f3ee`) tenía una regresión, encontrada al preguntarse
«¿esto vale para quien clone el repo?».** El barrido filtraba solo por
`XDG_RUNTIME_DIR`, y **dos sesiones Hyprland vivas del mismo usuario lo
comparten** (dos TTY, cambio rápido de usuario): el segundo en entrar dejaba al
primero sin barras con su compositor delante. Peor que el fallo original, y
`ABANDONO` no lo salva porque a ese demonio no le pasa nada — lo matan. Ahora se
mata solo al duplicado de la propia firma y al huérfano (otra firma cuyo Hyprland
ya no contesta); una tercera sesión viva se deja en paz. La afirmación 5 de la
prueba lo vigila, y **falla contra `7c7f3ee`**.

## Y los canales de órdenes, uno por sesión (2026-08-07, portátil)

Salió de tirar del hilo anterior: **`$XDG_RUNTIME_DIR` es del USUARIO, no de la
sesión**. Los dos demonios ponían ahí un FIFO de nombre fijo
(`waybar-autohide.fifo`, `wallpaper-pause.fifo`), así que dos sesiones de Hyprland
vivas a la vez se lo robaban en bucle —cada demonio rehace el suyo cuando ve que
no es el suyo— y las órdenes acababan donde les tocara. El `SUPER+C` era lo
visible; lo grave era el `lock`/`unlock` de la pantalla de bloqueo.

Ahora el canal lleva la firma: `waybar-autohide.<firma>.fifo`. Lo calcula
**`hypr/scripts/lib/canales.py`**, con gemelo **`lib/canales.sh`** porque
`lock.sh` corre en cada bloqueo y no puede pagar un arranque de python. Que la
convención esté escrita dos veces es deuda a la fuerza, y por eso
`tests/unidad/canales.sh` **compara las dos implementaciones caso por caso**.

Sin firma (a mano desde un TTY o por ssh) se usa el único canal si hay uno solo,
y **no se adivina si hay varios**: mandar un `unlock` a la pantalla de bloqueo de
otra sesión es peor que no hacer nada.

Los seis que escriben pasan por ahí. Y los tres de la config (el `SUPER+C` de
`keybinds.conf` y los `on-click` de `trigger.jsonc` y `dock-trigger.jsonc`) ya no
llevan la ruta escrita: llaman a **`hypr/scripts/barras.sh`**, que además **avisa
si no hay demonio**. Eso tapa el fallo silencioso de siempre: `echo x >
ruta-que-no-es-un-FIFO` crea un fichero normal y sale con 0, así que el atajo
parecía ir y no hacía nada — y waybar se traga el `stderr` de los `on-click`.

Verificado en la sesión viva: los dos canales con firma, `SUPER+C` saca las
barras de `bottom` a `top`, el `on-click` tal cual lo lanza waybar sale con 0, y
`configerrors` vacío. 14 pruebas en verde.

## El fondo y el bloqueo, también por sesión (2026-08-07, portátil)

Es lo que en la entrada anterior quedaba anotado como «no se tocó». Se cogió
después, a petición del usuario, y **ya no queda ningún `pkill -x` en el repo**.

**Lo que había.** `mpvpaper.sock` con nombre fijo, y cuatro sitios matando o
contando por nombre: `pkill -x mpvpaper` (dos veces en `wallpaper.sh`, dos en
`wallpaper-pause.py`), `pkill -f 'wallpaper-paus[e].py'` y `pgrep -x hyprlock`.
Ese último es el peor de todos: con otra sesión del mismo usuario bloqueada,
`lock.sh` se daba por hecho y **salía sin bloquear nada**. Pedir el bloqueo te
dejaba la pantalla abierta.

**Lo que hay ahora.** El socket de mpv lleva la firma, igual que los dos FIFO
(`canales.py` creció con `socket_mpv()`), y los procesos se buscan en `/proc`:

- `pids_de_esta_sesion <programa>` — por la firma del entorno. Lo usa `lock.sh`.
- `pids_con_marca <programa> <marca>` — por un trozo de la línea de comandos. Es
  como se reconoce a **nuestro** mpvpaper: la ruta de su `--input-ipc-server` ya
  lleva la firma, así que el proceso dice solo de qué sesión es.
- `wallpaper-pause.py` tiene ya su `matar_otros()`, como el de las barras, y
  `wallpaper.sh` **ya no mata al demonio**: eso quita de paso una carrera que
  estaba confesada en un comentario (si el viejo tardaba en morir, el `pgrep` lo
  veía, no se lanzaba a nadie, y la sesión se quedaba sin demonio).

### Tres cosas que casi salen mal, y por qué están en el `CLAUDE.md`

**1. «Sin firma, no filtres» habría sido el mismo `pkill -x`.** La primera
versión de `pids_de_esta_sesion` no filtraba si faltaba la variable. Medido: con
esa versión, llamarla desde el entorno de pruebas devolvía **el mpvpaper real del
usuario** — o sea que correr la suite te habría apagado el fondo. La regla buena
es «sin firma no se reclama nada», y el lado seguro cae solo para quien llama.
Lo vigila la sección 9 de `tests/unidad/canales.sh`.

**2. `tests/e2e/fondo.sh` llevaba tiempo midiendo un script capado.** Copiaba
`wallpaper.sh` a un temporal **sin `lib/`**, así que el `source` fallaba — y en
bash un `source` roto no corta nada— y la prueba pasaba sin ejercer la parte que
decide a quién matar. De hecho es lo único que impidió que el fondo real muriera
mientras se probaba todo esto. Ahora la prueba copia `lib/`, y los dos scripts se
plantan con un mensaje si no la encuentran.

**3. El `2>/dev/null` iba en el sitio equivocado.** `read -r x < "$d/comm"
2>/dev/null` no silencia nada: bash procesa las redirecciones de izquierda a
derecha, así que un proceso que desaparece entre el glob y la lectura —pasa
constantemente— escupe el error igual. Se vio en la sesión viva al relanzar el
fondo. Va delante.

**Verificado en vivo**, que aquí es lo que cierra el asunto: el fondo relanzado
con su socket con firma, dibujando en la capa 0, respondiendo por IPC y con
`pause: True` con ventanas encima (o sea que el demonio de ahorro le habla bien);
un solo demonio de fondo; y `lock.sh` resolviendo los tres canales de esta
sesión. 14 pruebas en verde, `configerrors` vacío.

### Lo único que queda de esta familia

`pkill fuzzel` en `keybinds.conf` (`SUPER+B`). Es del mismo tipo, pero el lanzador
es una ventana efímera que solo está abierta mientras la usas, así que lo peor que
pasa es que se te cierre el fuzzel de la otra sesión. Se deja a propósito: no
merece un script nuevo solo para eso.

### Una falsa alarma de las pruebas, ya explicada

`afirmar_intacta_la_casa_real` saltó durante esta sesión sin que ninguna prueba
tocara nada: **la suite tarda minutos, y la pantalla se bloqueó por inactividad
mientras corría**, así que `lock.sh` reescribió `lock-bg.jpg`, `lock-fondo.conf`,
`lock-medidas.conf` y `lock.log` en la caché de verdad. Antes solo decía «la
huella cambió: a1b2 -> c3d4», que no le sirve a nadie; ahora **lista los ficheros
que cambiaron** y avisa de este caso por su nombre. La guardia no se ha
debilitado.

## El reinicio del 2026-08-03: cerrado

Se reinició para estrenar de golpe la pantalla de SDDM, lo que vino de la PC y la
detección de portátil. Salió, y está subido: `ee3b726` (SDDM) y `8709245`
(teclado según la máquina) están en `origin/main`, que era el último paso de
aquella lista. La lista se ha borrado de aquí; si hiciera falta, está en el
historial de este fichero.

Lo único que sigue igual son las dos cosas que se dejaron sin comprobar **a
propósito**, y que siguen abajo, en «Lo siguiente»: el bind de modo avión y la
perilla del X820.

## Lo último: la laptop escribe con SU teclado (2026-08-05, portátil)

Lo pilló el usuario: se había arreglado `kb_options` (el Ctrl derecho) pero **no
la distribución**. La laptop arrancaba en `us(altgr-intl)` —la del teclado ANSI
del autor— cuando su teclado está serigrafiado en **latam**, así que la `ñ`, los
acentos y los símbolos salían donde no toca y había que corregir con `SUPER+DEL`
en cada sesión.

Ahora, en un portátil, la distribución sale de `/etc/vconsole.conf`: lo que se
contestó al instalar la distro, que en un portátil es de fiar porque se respondió
tecleando en el teclado interno. Queda `latam,us` con variante `,altgr-intl`.

**La trampa, y está en el `CLAUDE.md`: en un sobremesa esa fuente miente.** El
`/etc/vconsole.conf` de la PC también dice `latam` y su teclado es un ANSI us
—se eligió latam al instalar y se cambió de teclado después—, así que un
sobremesa NO la mira y conserva la del autor. Comprobado forzando esa rama sobre
una copia del repo: sigue dando `us,latam` y `altgr-intl,`, o sea que **al pasar
`./instalar.sh` en la PC no cambia nada**.

El valor viaja por `$kb_layout` / `$kb_variant`: valor de fábrica en
`hyprland.conf` (antes del `source` de `local.conf`, para que un clon sin
instalar no se coma un error de hyprlang por una variable sin definir) y lo pisa
el generado `local.conf`, editable a mano.

Verificado en la sesión viva tras `hyprctl reload`: el teclado interno **y el
USB** salen con `l "latam,us"`, índice 0 y `active keymap: Spanish (Latin
American)`, con `o ""`. Lo cubre `tests/unidad/maquina.sh` (46 comprobaciones),
que prueba las dos ramas y los casos raros: valores entre comillas, un portátil
ya instalado en `us`, y una caja sin `/etc/vconsole.conf`.

## Antes: lo que la adaptación no había cubierto (2026-08-05, portátil)

Se auditó el repo entero preguntando «¿esto vale para quien lo clone?», no solo
el cambio de la sesión. Salieron dos cosas, las dos venidas de la PC.

**1. Ocho rutas cableadas a `~/dotfiles`, en ficheros que el cerrojo no miraba.**
`waybar/config.jsonc` tenía siete (los `on-click` de btop y nmtui, el `exec` del
módulo de notificaciones y el del panel de calendario) y `mako/config` una (el
`include=` de los colores). Clonar el repo en otra ruta dejaba esos clicks
muertos, el módulo de notificaciones vacío y mako sin colores, **en silencio**.

Se coló porque `tests/unidad/portabilidad.sh` **solo escaneaba `.conf`, `.sh` y
`.py`**: los `.jsonc` y los ficheros sin extensión le eran invisibles. El
vigilante tenía el mismo agujero que el código vigilado. Ahora mira todo fichero
de texto menos la documentación, y se comprobó al revés: con el cerrojo nuevo y
el código viejo, falla y lista las ocho. La ruta buena es `$HOME/.config/...`,
el enlace que crea `instalar.sh`.

**2. El sensor de temperatura era el de la PC.** `config.jsonc` llevaba a mano
`"hwmon-path-abs": "/sys/devices/pci0000:00/0000:00:18.3/hwmon"` — el k10temp del
Ryzen 5 5500. Este portátil es un Intel i5-8250U y esa ruta **no existe**, o sea
que el módulo llevaba tiempo sin poder leer nada.

Se arregló con el patrón que ya usaba la batería: `hypr/scripts/lib/sensores.py`
lo averigua en caliente y `instalar.sh` escribe la ruta en `waybar/local.jsonc`,
que no se versiona. Lo que se ve (formato, iconos, umbral) vive en
`waybar/sensores.jsonc`, versionado, que además es la red de seguridad si falta
el generado. **`temperature` ya no puede estar en `config.jsonc`**: en waybar
gana el primero que define una clave, y el que incluye va antes que el incluido.

Verificado con captura (`grim`): la barra marca **42 °C** leyendo el `coretemp`
de esta caja. Y `tests/unidad/sensores.sh` prueba las dos familias de CPU con un
`/sys` de mentira —contra el de verdad solo se vería la de esta máquina— y falla
si alguien vuelve a escribir la ruta de un sensor en un `.jsonc` versionado.

**Trampa que costó las barras, y está en el `CLAUDE.md`:**
`waybar-autohide.py --reiniciar` no es un comando que termina, **se convierte en
el demonio**. Lanzarlo desde un shell que espera y que algo lo mate por tiempo
deja el escritorio sin barras y sin FIFO. Se levanta con
`setsid nohup ... >/dev/null 2>&1 </dev/null &`.

## Antes: las barras que no volvían, y el teclado (2026-08-05, portátil)

**`SUPER+SHIFT+C` ya no deja el escritorio sin barras.** Eran dos fallos:

1. **El demonio se suicidaba.** El bucle acababa en
   `if not all(bar.alive()): cleanup()`, así que **una** waybar caída mataba a
   las otras tres y al propio demonio — y ya no quedaba nadie que las levantara,
   ni el atajo de reinicio, que empieza hablando con él. Había que cerrar sesión.
   Medido: matando una sola de las cuatro, a los 4 s no quedaba ninguna capa
   waybar viva. Ahora `Bar.supervisar()` relanza la pareja caída; si se cae 5
   veces en un minuto se rinde con una notificación, y la otra barra sigue.
2. **Tras reiniciar quedaban escondidas.** `Bar.__init__` nacía con
   `manual = False` mientras `relanzar()` lo ponía a `True`, así que con apps
   abiertas las barras nuevas se escondían en el primer ciclo y el atajo parecía
   servir sólo para hacerlas desaparecer. Ahora nacen «sacadas a mano»: se ven
   ~1,5 s y luego se ocultan como siempre. Al arrancar la sesión no cambia nada,
   porque el escritorio está vacío.

Lo cubre `tests/unidad/barras-supervisor.sh`, y **la prueba se comprobó contra el
código viejo**: fallan 4 de sus 11 afirmaciones.

**Y el perfil de teclado de portátil ya vale para TODOS los teclados.** Estaba en
un `device { name = at-translated-set-2-keyboard }`, que sólo rescataba el
teclado interno: un teclado USB enchufado al portátil seguía perdiendo su Ctrl
derecho, igual que `video-bus` y `power-button`. Ahora se vacía `kb_options` en
el bloque `input {}` global de `conf/teclado-laptop.conf` — que es el último
fichero que lee `hyprland.conf`, así que gana. Nuevo en el detector:
`maquina.py teclado` (`completo` / `sin-altgr`) y `maquina.py motivo`.

El **NumLock se dejó como estaba a propósito**: en un portátil con teclado
numérico de verdad, `true` es lo que quiere cualquiera. El porqué está escrito en
`conf/teclado-laptop.conf`.

Comprobado, además de las pruebas: `hyprctl devices` dentro del anidado con los
dos perfiles (portátil da `kb_options` vacío, sobremesa da `lv3:switch`), y
`Hyprland --verify-config` limpio apuntando a los dos sitios.

Y comprobado también **en la sesión viva del portátil**, que es la prueba que de
verdad cierra el asunto: los **cinco** teclados de `hyprctl devices` salen con
`o ""`, incluido `usb-optical-mouse--keyboard` —un teclado USB, justo el que el
`device {}` de antes dejaba fuera— además de `ideapad-extra-buttons`,
`video-bus` y `power-button`.

**Y el sobremesa ajeno ya está avisado.** Quien clone el repo en un sobremesa se
queda con el perfil `sin-altgr`, que es el teclado del autor, y perdía el Ctrl
derecho sin que nada se lo dijera. No se detecta solo a propósito (un teclado se
enchufa y se desenchufa; `kb_options` se lee al arrancar), así que se avisa por
los tres sitios donde se mira: `./instalar.sh --revisar`, el README y el propio
`conf/input.conf`. Comprobado forzando el camino del sobremesa sobre una copia
del repo, que es la única forma de ver esa rama desde el portátil.

## El fondo del login, automático (2026-08-05)

**Cambiar de fondo ya actualiza también la pantalla de inicio de sesión, sin
pedir contraseña.** Antes obligaba a pasar `./instalar.sh --sddm` a mano, que
para quien cambia de fondo a menudo es lo mismo que no funcionar.

La clave: el greeter corre como el usuario `sddm` y no puede leer tu `$HOME`
(está a 700), y `/usr/share` es de root. Se resolvió **sin** aflojar permisos de
la casa y **sin** ninguna regla NOPASSWD: `--sddm` crea una vez
`/var/lib/sddm-celiuz` (tuya, grupo `sddm`, modo **2750** — el setgid es lo que
hace que el greeter pueda leer lo que escribas) y deja los dos ficheros del tema
como enlaces ahí. Después, `hypr/scripts/sddm-fondo.sh` lo rehace solo desde
`aplicar()`, en segundo plano.

**Si vienes de una instalación anterior, hay que pasar `./instalar.sh --sddm` una
vez más** (la última). El instalador lo detecta y lo saca como pendiente en rojo.
**Ya está pasado en las dos máquinas** (el portátil, el 2026-08-05); hasta
hacerlo, la pantalla de login se veía negra, que era el síntoma.

Verificado de punta a punta en la PC: `aplicar()` vuelve al instante, el fondo se
regeneró solo en 9 s, y los ficheros quedan con grupo `sddm` y modo 644.

Y verificado también en el portátil (2026-08-05): el greeter dibuja el fondo, la
tarjeta y el campo de contraseña a 1366x768 —`sddm-greeter-qt6 --test-mode`
dentro del anidado—, y regenerar el fondo con otro vídeo tardó 18 s **sin pedir
contraseña**, dejando los ficheros con grupo `sddm` y modo 644.

## El historial de notificaciones (2026-08-08, PC)

**`SUPER+H` enseña todo lo que ha llegado en esta sesión, con su hora, aunque ya
lo hubieras descartado.** Una notificación sale seis segundos y se va para
siempre; si estabas jugando o mirando a otro lado, se perdió.

Cómo funciona está en el README («El historial: lo que pasó mientras no
mirabas»); las trampas de D-Bus, en el `CLAUDE.md`. Lo esencial:

- `hypr/scripts/avisos.py --demonio` **espía el bus**, no le pregunta a mako. El
  historial de mako no vale: no trae la hora, son 5 en memoria, y `restore` saca
  cosas de él. Y espiando no se sustituye al demonio: si el grabador se cae,
  dejas de grabar pero **no te quedas sin avisos**.
- El registro vive en `$XDG_RUNTIME_DIR`, que systemd borra al cerrar sesión. Lo
  que quieras conservar se aparta a mano y baja a `~/.local/share`.
- CLI en el PATH (`avisos`): `listar | ver N | guardar N | guardados`, y
  `--json` para leerlo desde fuera.

**No hay panel GTK propio a propósito**: el visor es fuzzel, que ya está montado
y con la paleta puesta. Un panel más es superficie que mantener.

**Lo que no se ha visto nunca**: un aviso que traiga el icono como `image-data`
en crudo. El filtro de hints está escrito y probado con datos falsos
(`tests/unidad/avisos.sh`), pero ninguna app de esta máquina lo manda así.

## El diálogo de «no responde» sobre el bloqueo (2026-08-08, PC)

**Al bloquear salía un cuadro de diálogo detrás de la pantalla de bloqueo**,
acusando a una aplicación de no responder. Pasaba en la PC y en el portátil.

La causa: **congelar una app es dejarla muda a propósito**, y Hyprland vigila que
cada ventana conteste a su ping. A los 5 fallos dibuja «no responde» con
«Esperar» y «Forzar cierre». O sea que el bloqueo se acusaba a sí mismo, y se veía
porque el modo `xray` enseña lo que hay debajo.

**Lo pinta el compositor, no la app.** Por eso no sale en `hyprctl clients`, no es
un proceso aparte y no se quita cerrando ventanas ni saltando a un escritorio
vacío — que es justo donde se pierde el tiempo buscándolo. Lo que lo delató fue
que **el texto está traducido**: las ventanas de una app no las traduce Hyprland.

`lock.sh` apaga `misc:enable_anr_dialog` antes de congelar y lo devuelve tras
descongelar. El orden es parte del arreglo y lo vigila `tests/e2e/bloqueo.sh`
(4 comprobaciones nuevas). Detalle en el README, «El diálogo de "no responde"».

**Lo que NO se pudo reproducir a mano**: congelar una app suelta y esperar, ni
con el umbral bajado a 1 ping ni con la ventana enfocada, no saca el diálogo en
40 s. Se arregló por la causa, no por el síntoma reproducido — así que si vuelve
a verse, eso es lo primero que hay que contar.

## Un fichero para tus cosas: `personal.conf` (2026-08-08)

`hypr/conf/personal.conf` lo crea `instalar.sh` **vacío** y no lo toca nunca más.
No se versiona, y se carga **el último de todos**, así que desde ahí se puede
añadir lo que sea y pisar cualquier atajo o ajuste del repo.

Sirve para lo que es de una máquina y de nadie más, sin que salga como
modificación en cada `git pull`. La prueba `tests/unidad/maquina.sh` vigila que
siga siendo el último y que `$conf_maquina` sea el último **del repo**.

Ojo al clonar: hasta que no pases el instalador, Hyprland avisa de que no
encuentra ese `source` — el mismo trato que `local.conf`, y `--revisar` lo saca
como pendiente.

## El SUPER+TAB y el sonido (2026-08-04)

**El `SUPER+TAB` ya se cierra al soltar SUPER, que era lo que faltaba.** Antes
había que rematar con `Enter`. Dos fallos distintos, los dos medidos y no
deducidos:

1. **El `bindr` estaba escrito sin modificador** (`bindr = , SUPER_L`) y por eso
   no disparaba **nunca**. Va con él delante: `bindr = SUPER, SUPER_L`. Y hacen
   falta las dos combinaciones de cada tecla, porque el modmask coincide exacto y
   soltar SUPER con SHIFT pulsado es otro caso.
2. **El toque rápido** seguía dejando la ventana colgada: si sueltas antes de que
   la capa tenga el teclado (~185 ms), el evento **no lo ve nadie**. Se resolvió
   preguntándole al kernel con el módulo nuevo **`hypr/scripts/lib/teclas.py`**,
   y preguntándoselo *antes* de dibujar la ventana: si ya soltaste, no se enseña
   nada y saltas directo.

Lo verificado en vivo: taps rápidos (sin ventana, salto directo), gesto lento,
`SUPER+SHIFT+TAB` hacia atrás y `Escape`. El detalle técnico está en el README y
las trampas en el `CLAUDE.md` — **no vuelvas a deducirlas**.

Nuevo para diagnosticar: `touch $XDG_RUNTIME_DIR/vista-escritorios.debug` enciende
el diario cuando el script lo lanza **Hyprland**, que es el único caso en el que
se pueden medir estas carreras.

**Y las notificaciones ya suenan** (`hypr/scripts/sonido-notificacion.sh`, sonido
`message` del tema freedesktop). Queda mudo en «no molestar», que hubo que poner
expresamente: `on-notify` se dispara igual con `invisible=1`. Para saber qué usa o
por qué no suena, `sonido-notificacion.sh --revisar` — mako no enseña esos errores.

## La batería de la barra (2026-08-04)

En un portátil, la barra de arriba enseña la batería a la derecha; en un
sobremesa, no. Cómo funciona está contado en el README («La batería de la
barra»), y el porqué de cada umbral y cada color, en los comentarios de
`waybar/config.jsonc` y `waybar/style.css`.

Lo que hay que saber para no romperlo: **el lado derecho de la barra ya no se
escribe en `config.jsonc`**. Sale de `waybar/derecha.jsonc` (versionado, sin
batería) por un `include`, y `instalar.sh` genera `waybar/local.jsonc` metiéndole
`battery` si la caja es un portátil. Para añadir un módulo a la derecha, va en
`derecha.jsonc` y en ningún otro sitio.

Está comprobado, en esta máquina y para la otra:

- Las pruebas, `./instalar.sh --revisar` y `hyprctl configerrors`, limpios.
- El módulo, vivo en la barra y con su color (captura con `grim`).
- El camino del **sobremesa**: el generador con `BATERIA=no` saca la lista sin
  batería.
- Que **falte `local.jsonc`** —un clon recién hecho, antes de pasar el
  instalador— no deja sin barra: medido en un Hyprland anidado, waybar deja un
  `[warning] Unable to find resource file` y sigue con `derecha.jsonc`.

**Lo que no se ha visto nunca en pantalla** son los estados que dependen de la
carga: `full` (100 %), `not-charging` (el corte al 80 % de algunos portátiles) y
la alarma roja de `critico` (≤10 % **sin** cable). Si alguno se ve raro, el sitio
es el bloque `#battery` de `style.css`; están escritos, no probados.

## El susto del fondo (2026-08-04), y lo que dejó

Levantar un Hyprland **anidado** con el `$HOME` de verdad dejó el escritorio real
sin fondo y sin el demonio que lo pausa: el anidado corre tu `autostart.conf`, y
`wallpaper.sh` empieza con `pkill -x mpvpaper` y `pkill -f wallpaper-paus[e].py`,
que no distinguen de qué sesión es cada proceso. Al cerrar el anidado, su demonio
—que nace con `setsid`— sobrevivió apuntando a un compositor muerto, y como
`wallpaper.sh` pregunta si hay demonio con un `pgrep` por nombre, el zombi
contestaba que sí y nadie levantaba uno bueno. Resultado: el vídeo corriendo con
ventanas encima y quieto en el bloqueo.

De ahí salieron tres cosas, y **las tres están puestas**: el demonio **se va
solo** si pasa `ABANDONO` (60 s) sin poder hablar con su Hyprland,
`tests/unidad/fondo-huerfano.sh` lo vigila por los dos lados, y el anidado ya no
se levanta a pelo:

```sh
./tests/anidado.sh hyprctl configerrors   # levanta, ejecuta y recoge
./tests/anidado.sh                        # se queda abierto; Ctrl+C lo tumba
```

`tests/anidado.sh` monta `$HOME` desechable, una copia del repo enlazada como la
enlaza `instalar.sh`, `autostart.conf` vaciado y `$XDG_RUNTIME_DIR` propio; al
salir barre los procesos que quedaran con la firma de esa instancia y borra la
casa. Comprobado: con él, el `mpvpaper` y el demonio de la sesión real siguen
con el mismo PID después de usarlo, y un proceso lanzado con `setsid` dentro
queda recogido al cerrar.

**Lo que sigue sin cubrir**, y conviene tenerlo presente: `pkill` mata por
NOMBRE, y eso no lo aísla ningún `$HOME`. Si dentro del anidado lanzas a mano
algo que mate por nombre —`wallpaper.sh`, sin ir más lejos—, se llevará por
delante lo de la sesión de fuera igual. Allí no arranca nada solo; a partir de
ahí, ojo con lo que lanzas.

## Lo primero: una comprobación que solo se hace con los ojos

Son **dos**, y las dos se hacen con el mismo `SUPER+L`.

**La primera: mira el diseño nuevo del bloqueo.** Está verificado con hyprlock de
verdad dentro del anidado, a 1366x768 y con el fondo real, pero nadie lo ha visto
todavía en la pantalla de casa. Lo que se juzga con los ojos y no con una prueba:
si el reloj y el campo caen a gusto en la columna, si la banda tapa demasiado
—o demasiado poco— del fondo, y si la fila de datos de abajo se lee. La
contraseña no se tocó, así que el riesgo es cero: como mucho, se ve raro.

**La segunda: si vuelve a asomar el diálogo de «no responde».** El arreglo se hizo por la causa, no por el síntoma reproducido: en
la sesión del 08 no se consiguió provocar el diálogo a mano —congelando una app
con el foco puesto, 40 s, y hasta con `misc:anr_missed_pings` bajado a 1— así
que lo único que falta es verlo con un bloqueo de verdad, del que dure minutos.

Si vuelve a aparecer, **eso es lo primero que hay que contar**, porque
significaría que el diálogo no viene por el congelado y toda la explicación de
abajo se cae. Lo siguiente que miraría entonces: si ya estaba en pantalla antes
de bloquear (una app colgada de verdad), porque el `xray` lo enseñaría igual y el
arreglo no cubre ese caso.

## Lo siguiente, por orden de valor

### 1. `env.conf` para Nvidia — está vacío

Es lo que más puede afectar jugando (RTX 3050 sobre Wayland). **No copiar listas
de los foros**: muchas variables que circulan llevan años obsoletas en Hyprland
0.56 y algunas empeoran el rendimiento. Hay que comprobar una por una cuáles
hacen falta de verdad en esta versión.

Pista fuerte encontrada durante las pruebas: el Hyprland **anidado** sobre esta
GPU solo levanta con `AQ_NO_MODIFIERS=1` (sin eso, `bo null` en bucle y se queda
sin monitor). Lo primero es averiguar si algo de eso hace falta también en la
sesión real o si es solo cosa del anidado.

### 2. ~~Teclas multimedia~~ — hecho

Volumen, mute, micro y multimedia ya están en `keybinds.conf`, y funcionan en las
dos máquinas. Brillo, touchpad y tapa en `conf/teclado-laptop.conf`, que solo se
carga en portátiles (ver «Portátil o sobremesa» en el README).

**Lo de la perilla del X820 queda cerrado (2026-08-04): ese teclado no tiene esas
teclas**, lo confirmó el usuario probándolo, y no le hace falta. O sea que en la
PC los binds de audio no los dispara nadie — y eso **no es un fallo**: un bind
sobre una tecla que el teclado no emite simplemente no salta, que es justo por lo
que estas líneas pueden vivir en el fichero común y no en el de portátil. No hay
nada que investigar aquí; si algún día se cambia de teclado, funcionarán solas.

**Sin comprobar en el portátil**: el bind de modo avión (`XF86RFKill`). Probarlo
significaba tumbar la wifi de la sesión. El riesgo no es que no funcione, es que
funcione **dos veces** —si el kernel ya conmuta el rfkill solo, el bind lo
devuelve— y parezca que la tecla no hace nada. Cómo saberlo, en el propio
fichero.

### 3. Historial del portapapeles

`SUPER+SHIFT+V` ya está reservado en `keybinds.conf`. Candidato: cliphist
(`wl-clipboard` ya está instalado).

### 4. Reglas de ventana del flujo de seguridad

VMs, Burp Suite, etc. **Preguntar primero qué herramientas se usan de verdad**
antes de escribir reglas para programas que quizá no se abren nunca.

### 5. El login (SDDM) y el TTY siguen en `latam`

`/etc/vconsole.conf` tiene `KEYMAP=la-latin1` y `XKBLAYOUT=latam`, y eso gobierna
la pantalla de login y el TTY de rescate — que son ajenos a Hyprland. O sea que
**la contraseña al encender se sigue tecleando en latam** sobre un teclado ANSI,
aunque la sesión ya use `us`. Se arregla con `localectl` y sudo.

Está fuera del repo y tiene un modo de fallo feo (cambia cómo se teclea la
contraseña en el login), así que **solo si se pide**.

### 6. SDDM se quedó descolgado del rediseño del bloqueo

Desde el 2026-08-09 el bloqueo es una columna a la izquierda y el login sigue con
la tarjeta violeta centrada. **Dejaron de ser gemelos**, y está anotado en el
`README.md` para que nadie lo lea como un descuido.

Igualarlos no es traducir el `.conf`: son dos ficheros que no comparten una línea
—uno es hyprlang, el otro QML— y hay que rehacer el diseño a mano en
`sddm/celiuz/Main.qml`. Además el greeter es **lo único del repo que pide `sudo`**
y lo único que puede dejarte sin arrancar, así que se prueba sí o sí con
`sddm-greeter-qt6 --test-mode --theme <ruta>`, y también **sin `fondo.mp4` ni
`fondo.jpg`**, que es como le llega a quien clona.

Vale la pena solo si molesta la diferencia: funcionalmente no falla nada.

## Menores, ya ofrecidos y no pedidos

- Regla de sudo estrecha para `ir-a-windows.sh`, en vez de pedir la contraseña
  en una terminal.
- `windowrule` para que la terminal de `ir-a-windows.sh` salga flotante.
- Atajo de teclado propio para CeliuzPaper.
- Botón de «añadir comando a mano» en el gestor del dock, para AppImages y
  binarios sueltos: ningún escaneo de `.desktop` los cubre.
- Pasar `dock-manager.py` y `celiuzpaper.py` a leer la paleta en caliente, como
  ya hace `vista-escritorios.py`.

## Cosas que están fuera del repo a propósito

- `hypr/scripts/ir-a-windows.sh` — sin seguimiento por decisión expresa: se
  considera algo aparte de la configuración del escritorio.
- Los vídeos e imágenes de fondo, las credenciales de Google Calendar, el dock
  de cada máquina y las carpetas de fondos añadidas. Ver la regla de oro del
  `CLAUDE.md`.

## Decisión que hay que tomar algún día

Hyprland avisa al arrancar de que **el formato `.conf` deja de estar soportado en
la 0.57**. Todo el repo está en hyprlang por decisión explícita. Antes de esa
versión: quedarse anclado, o portar a Lua.
