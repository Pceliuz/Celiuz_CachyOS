# El catálogo de apps (la ventana de instalación)

**Estado (2026-11-18): pasos 1, 2 y 3 hechos.** La ventana existe
(`celiuz-catalogo`, «Catálogo Celiuz» en el lanzador) y Celiuz Remoto y la
radio ya no se instalan con todo lo demás: se eligen ahí. Falta **probarlo en
la sesión real** (instalar y quitar Cell-Cast de verdad) y los pasos 4 y 5 de
abajo.

| Pieza | Dónde |
|---|---|
| La ventana (GTK3, paleta del repo) | `hypr/scripts/catalogo-apps.py` (`--png RUTA [ID]` la dibuja sin crear ventana) |
| Lo que hace cada botón, sin GTK | `hypr/scripts/lib/apps_catalogo.py` (`estado`, `instalar`, `actualizar`, `quitar` por CLI) |
| La ficha y la lista | `hypr/scripts/lib/fichas.py`, `apps/lista.json` |
| Las fichas de dentro | `remoto/celiuz-app.json`, `sistema/radio/celiuz-app.json` |
| Lo que llaman esas fichas | `instalar.sh --remoto`, `--remoto-quitar`, `--remoto-revisar`, `--radio-elegir`, `--radio-dejar`, `--radio-revisar`, `--radio-aplica` (y los de siempre: `--remoto-todo`, `--radio`…) |
| Las pruebas | `tests/unidad/fichas.sh`, `tests/unidad/catalogo-apps.sh` |

**Cómo se añade una app de fuera:** su repo lleva un `celiuz-app.json` en la
raíz (el formato, en la cabecera de `fichas.py`; se comprueba con
`fichas.py validar <carpeta>`), su instalador deja el anuncio
`~/.local/share/celiuz/apps.d/<id>` → la raíz de su repo y lo quita al
desinstalarse, y se añade una línea a `apps/lista.json` con su `id` y su
`repo`. Nada más: la ventana la saca sola.

**Cómo se comporta** (decidido con el usuario el 2026-11-18): ventana flotante,
lista a la izquierda y la ficha a la derecha (descripción, qué necesita,
capturas, GitHub). Se abre desde el lanzador o con `celiuz-catalogo`, sin
atajo. Lo que pide contraseña lo dice antes con la frase de su ficha y deja
instalar sin esa parte; la contraseña la pide la tarjeta del repo
(`pedir-clave.py`), con un `sudo -A` que el catálogo pone delante en el PATH
(el instalador de la app escribe `sudo` como siempre). Lo que imprime cada
orden sale en un registro, con los enlaces clicables (el de Tailscale).

**La migración:** un equipo que ya tenía Celiuz Remoto (la orden
`celiuz-remoto` enlazada al repo, o lo de tras reiniciar) o la radio (sus
ficheros en `/etc`) los conserva: `./instalar.sh` los marca como elegidos y
los sigue poniendo al día. Quien instala de cero no se los lleva.

## Por qué

La configuración la usan amigos del usuario con gustos muy distintos: gente de
sistemas, gamers y gente que hace stream. Hoy, quien instala los dotfiles se lo
lleva todo, use lo que use. Lo que no se usa **está de adorno** y además gasta.
El usuario quiere que cada uno **descargue e instale solo lo que va a usar**.

## La decisión: las apps van por separado, el catálogo va aquí

- **Las apps que sirven a cualquiera tienen su propio repo** y no viven en los
  dotfiles. La primera es **Cell-Cast** (antes «Celiuz Cast»), en
  `git@github.com:Pceliuz/Cachy_Cell-Cast.git`: el celular como cámara y
  micrófono para OBS. Solo necesita Linux, OBS y un Android; no necesita el
  escritorio.
- **Lo que solo tiene sentido con este escritorio se queda dentro**: Celiuz
  Remoto (`remoto/`, que habla con Hyprland y SDDM), el modo gaming y el arreglo
  de la radio (`instalar.sh --radio`).
- **La ventana del catálogo va en los dotfiles**, y muestra las dos clases en
  **una sola lista**, igual para quien la usa.

## Cómo funcionaría

1. **Un solo catálogo** con todo lo opcional. Cada app sale con su icono, su
   descripción, sus capturas, la URL del repo y su estado: *no instalada*,
   *instalada* o *hay versión nueva*.
   - **Las de fuera** se clonan y se instalan.
   - **Las de dentro** ya están en la carpeta, pero **no se activan** hasta que
     alguien las elige. Celiuz Remoto ya hace eso hoy: viene apagado.
2. **`instalar.sh` instala solo la base** que todos reciben: la barra, el dock,
   el bloqueo, los fondos, SDDM aparte, etc. Lo opcional sale del instalador
   normal y pasa al catálogo. **Decidido (2026-11-03): pasan al catálogo Celiuz
   Remoto y la radio (`--radio`); el modo gaming se queda en la base.**
3. **Cada app trae su propia ficha** en su repo (por ejemplo
   `celiuz-app.json`), y el catálogo de los dotfiles guarda solo la lista de
   URLs. La ficha lleva:
   - el nombre, la descripción, el icono y las capturas. Las imágenes viven en
     el repo de la app, no aquí, para no engordar los dotfiles;
   - qué necesita: «solo portátil», «NVIDIA», «un celular Android»…;
   - cómo se **instala**, cómo se **revisa** (`--revisar`) y cómo se
     **desinstala**. Desinstalar tiene que dejar el equipo limpio: quien prueba
     algo y no le gusta, lo quita.
4. **Dónde se descargan**: `~/.local/share/celiuz/apps/<nombre>`, fuera del repo,
   por la regla de oro de no versionar nada que dependa del equipo.
5. **Las actualizaciones**: la ventana avisa cuando hay versión nueva (un
   `git fetch` y compara) y actualiza con un `git pull` más el instalador de la
   app.
6. **sudo**: si una app pide contraseña, la ventana lo dice **antes** de
   instalar, nunca a escondidas. Se sigue la misma regla que con SDDM y con
   `--remoto-sistema`: la instalación normal no pide contraseña.
7. **El aspecto**: GTK3 en Python, como los paneles, con la paleta de
   `gen-colores.py`.

## El catálogo sale lo primero (idea del usuario, 2026-11-03)

Quien clona el repo por primera vez tiene que ver el catálogo antes que nada,
elegir sus apps, y que los dotfiles se configuren de paso. Salen juntas las
incluidas en los dotfiles y las de fuera, con lo que hace cada una y el enlace
a su GitHub. Como `./instalar.sh` puede correr desde un TTY sin Hyprland (no
hay donde abrir una ventana):

- con sesión gráfica, `instalar.sh` abre el catálogo al terminar;
- sin ella, sale **la primera vez que se entra a Hyprland** (se apunta que ya
  se vio en `~/.local/state/celiuz/`, para no salir más);
- y se puede abrir a mano cuando se quiera.

## El detector: la app se anuncia

Idea del usuario: que los dotfiles detecten una app descargada y la configuren.
No se busca por el disco (se puede clonar en cualquier carpeta): **la app avisa**.
Su instalador deja un enlace `~/.local/share/celiuz/apps.d/<id>` → la raíz de
su repo, y lo quita al desinstalarse. Vale igual si se instaló desde el
catálogo o clonándola a mano desde GitHub. `fichas.py instaladas` las lista.
Hecho en Cell-Cast. Pendiente: que la ficha diga QUÉ integrar en el escritorio
(entrada en el dock, regla de ventana, atajo) y que los dotfiles lo apliquen al
ver el anuncio.

## Lo que ya se decidió (2026-11-03)

- **Los dotfiles son públicos**, y las imágenes de `fastfetch/imagenes/` se
  quedan dentro y bajan con el repo: el usuario las considera indispensables.
  Así lo clonan los amigos, y así el usuario trabaja desde la PC y la laptop
  (siendo privado no podía).
- **Cell-Cast es público** (`Pceliuz/Cachy_Cell-Cast`) y está terminado.
- **Lo opcional de dentro: Celiuz Remoto y la radio.** El modo gaming se queda
  en la base.

## Orden propuesto

1. ~~Definir la ficha (`celiuz-app.json`) y estrenarla con Cell-Cast.~~ (2026-11-03)
2. ~~Hacer la ventana con lo de fuera (Cell-Cast).~~ (2026-11-18)
3. ~~Pasar a la ventana lo opcional de dentro (Remoto y radio) y
   sacarlo del instalador normal.~~ (2026-11-18; falta `./instalar.sh
   --revisar` en la laptop)
4. Que el catálogo salga lo primero (arriba, «El catálogo sale lo primero»).
5. Que la ficha diga qué integrar en el escritorio (dock, regla de ventana,
   atajo) y que los dotfiles lo apliquen al ver el anuncio (arriba, «El
   detector»).
