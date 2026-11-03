# Pendiente: el catálogo de apps (la ventana de instalación)

**Estado: paso 1 hecho (2026-11-03): la ficha y su lector.** Se habló con el
usuario el 2026-11-03 desde la laptop. El trabajo lo lleva la sesión de Claude
Code de esta carpeta.

- **La ficha está definida**: el formato, en la cabecera de
  `hypr/scripts/lib/fichas.py` (que la valida: `fichas.py validar <carpeta>`).
  Lo que no deja pasar lo vigila `tests/unidad/fichas.sh`.
- **La lista de apps de fuera**: `apps/lista.json` (id + repo de GitHub).
- **Cell-Cast ya la tiene** (`celiuz-app.json` en su repo) y su instalador **se
  anuncia** (ver «El detector», abajo).
- Falta: la ventana (paso 2) y pasar Remoto y la radio (paso 3).

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

1. Definir la ficha (`celiuz-app.json`) y estrenarla con Cell-Cast.
2. Hacer la ventana con lo de fuera (Cell-Cast).
3. Pasar a la ventana lo opcional de dentro (Remoto y radio) y
   sacarlo del instalador normal, comprobando con `./instalar.sh --revisar` en
   las dos máquinas.
