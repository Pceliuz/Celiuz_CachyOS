# Instalar Celiuz Remoto, paso a paso

Para un equipo con este repo (CachyOS + Hyprland **con uwsm** + SDDM) y un
celular Android. Vale para tu PC, tu laptop o la laptop de un amigo. Cada paso
dice qué hacer y **cómo saber que quedó bien**: si ya lo está, sáltalo.

> **¿Por dónde voy?** Dos órdenes lo dicen, y se pueden pasar cuantas veces
> quieras (no tocan nada):
>
> ```sh
> ./instalar.sh --revisar        # el escritorio y lo de root
> celiuz-remoto revisar          # lo del remoto: paquetes, Tailscale, tras reiniciar
> ```
>
> **Para el Claude Code de cada equipo:** pasa esas dos, y sigue esta guía
> desde el primer paso que no esté bien. No repitas lo que ya está. Si al
> traer cambios (`git pull`) alguna dice que algo quedó **viejo**, es un
> arreglo nuevo que hay que volver a instalar: la orden que sale al lado.

## Antes de empezar: tres decisiones

1. **Cuenta de Tailscale: una por persona.** El celular y los equipos de una
   persona van con LA MISMA cuenta. Un amigo usa la suya, no la tuya. (Para
   ayudarle a él desde tu celular está «Invitar a alguien», en la ventana.)
2. **¿Este celular ya tiene la app** (la instaló otro equipo tuyo)? Entonces
   aquí **no hace falta compilarla ni instalarla**: emparejar funciona con la
   que ya tiene. Salta los pasos 4 y 5.
3. **Varios equipos tuyos, un solo celular, y quieres poder actualizar la app
   desde cualquiera:** todos tienen que firmarla con LA MISMA clave. Antes del
   paso 5 copia del primer equipo al nuevo, con los permisos tal cual:
   ```sh
   # en el equipo nuevo (la carpeta, 700; los dos ficheros, 600)
   mkdir -p -m 700 ~/.config/celiuz/remoto
   scp primer-equipo:.config/celiuz/remoto/firma.{keystore,clave} ~/.config/celiuz/remoto/
   chmod 600 ~/.config/celiuz/remoto/firma.*
   ```
   Si no, actualizar desde el otro equipo dice «la instaló OTRO equipo, firmada
   con otra clave» (Android no deja), y tocaría desinstalarla y volver a
   emparejar.

## Los pasos

### 1. El repo, al día
```sh
cd ~/dotfiles && git pull && ./instalar.sh
```
**Bien si:** `./instalar.sh --revisar` acaba en «sin pendientes». Si sale
«Your config has errors: cannot open .../hyprland.lua», `SUPER+SHIFT+R`.

### 2. Todo lo del remoto, de una vez (pide sudo)
```sh
./instalar.sh --remoto-todo
```
Instala los paquetes (`celiuz-remoto paquetes`), enciende Tailscale y, si no
tiene sesión, saca un enlace: ábrelo y entra con **tu** cuenta. Deja también lo
de apagar y entrar tras reiniciar, que hace dos cosas con root:
- copia `entrar.py`, su unidad y la regla de polkit a `/usr/local` y `/etc`
  (nunca se ejecutan desde el repo);
- **comenta en `/etc/sddm.conf` el `Session=` de `[Autologin]`** que deja el
  instalador de CachyOS (`Session=hyprland`, SIN uwsm). SDDM lee ese fichero el
  último, así que pisaba la sesión al entrar desde el celular, y sin uwsm
  fallan los lanzadores. Guarda antes `/etc/sddm.conf.antes-celiuz-remoto`. Si
  tienes un autologin tuyo de verdad (con `User=`), no lo toca y te avisa.

Escríbelo **sin** `sudo` delante: lo pide él (con `sudo`, la regla quedaría a
nombre de root).

**Bien si:** `celiuz-remoto revisar` dice «No falta nada» y, en «Tras
reiniciar», «entrar desde SDDM: sí». Si dice «VIEJA» o «/etc/sddm.conf entraría
SIN uwsm», vuelve a pasar `./instalar.sh --remoto-sistema`.

### 3. El tema de la pantalla de inicio, al día (si lo usas; pide sudo)
```sh
./instalar.sh --sddm
```
Lo que se ve al arrancar es una COPIA del tema: tras un `git pull` con colores
nuevos, hay que volver a copiarla. **Bien si:** `./instalar.sh --revisar` no
avisa del tema.

### 4. El SDK de Android (solo para compilar la app)
No está en los repos: Android Studio, y en él «SDK Manager» → Android SDK
Platform y Build-Tools. Tiene que quedar en `~/Android/Sdk` (o en
`$ANDROID_HOME`).
**Bien si:** `remoto/app/compilar.sh --revisar` dice «No falta nada para
compilar».

### 5. Compilar la app del celular
```sh
remoto/app/compilar.sh
```
Unos 3 minutos (la primera vez, más). Mientras compila usa unos 5 GB de RAM;
al acabar los suelta (no deja demonios de Gradle vivos).
**Bien si:** acaba en «Listo: ~/.local/share/celiuz/remoto/celiuz-remoto.apk».

### 6. Encender el servicio
Abre **«Celiuz Remoto»** (lanzador, o `celiuz-remoto-config`) y enciende el
servicio. Eso también hace que arranque con el equipo (linger), aunque nadie
entre.
**Bien si:** `systemctl --user is-active celiuz-remoto` dice `active`, y
`celiuz-remoto revisar` dice «arranca con el equipo: sí (linger)». Si arriba
de la ventana sale un aviso, es lo que falta (con su orden).

### 7. El celular, por cable
En el celular: Ajustes → Acerca del teléfono → toca 7 veces «Número de
compilación»; luego, en Opciones de desarrollador, activa **Depuración USB**.
Conéctalo y acepta la huella que pregunta.
**Bien si:** `celiuz-remoto celulares` lo lista (si dice `unauthorized`,
acepta en el celular; si dice `no permissions`, desenchufa y vuelve a
enchufar).

### 8. Instalar la app y emparejar
En la ventana: **«Instalar la app»** (sáltalo si ya la tiene, ver arriba),
luego crea la contraseña de la app, elige qué puede hacer ese celular y pulsa
**«Emparejar»**. La app se abre sola en el celular. Esto da también el pase de
24 h (terminal, archivos y cerrar apps lo piden).
**Bien si:** `celiuz-remoto dispositivos` lo lista con su pase.

### 9. Tailscale en el celular
Instala Tailscale (Play Store) y entra con **la misma cuenta** que el equipo.
**Bien si:** la app enseña el equipo «En línea» con la CPU y la RAM en vivo,
y `tailscale status` en el equipo lista el celular.

### 10. Probar cada cosa
Desde el celular, con el equipo delante:
- **Inicio:** el estado se mueve cada segundo.
- **Apps:** salen las ventanas abiertas; cerrar una, pregunta antes.
- **Archivos:** bajar un `.docx` o una foto; sale en Descargas o la galería.
- **Terminal** (hace falta el permiso «Terminal» en «Permisos»): abrir una,
  **minimizar**, ir a Inicio, volver y entrar: sigue donde estaba.
- **Pantalla** (permiso «Ver y manejar la pantalla»): se ve el escritorio.
- **Apagar / Reiniciar / Suspender:** sale la cuenta atrás en el equipo, y
  se puede cancelar.

### 11. Tras reiniciar (lo más delicado: hazlo con el equipo delante)
Reinicia desde la app. El equipo se queda en la pantalla de inicio y el
celular lo dice («En la pantalla de inicio») → **«Entrar»**. La sesión
arranca **bloqueada**.
**Bien si**, ya dentro, `systemctl --user list-units 'wayland-wm@*'` muestra
una unidad `active`: es la señal de que se entró CON uwsm. Si no sale nada, se
entró sin uwsm: `./instalar.sh --remoto-sistema` (paso 2) y otra vez.

## Opcional

| Para | Qué hace falta |
|---|---|
| Que el equipo saque internet de un celular **por USB** también en la pantalla de inicio | `sudo pacman -S android-udev` y `sudo usermod -aG adbusers $USER` (y volver a entrar). Lo dice `celiuz-remoto anclaje` |
| Despertar el equipo desde otro (Wake-on-LAN) | cable de red al router, WoL en la BIOS y `sudo nmcli connection modify "<la conexión cableada>" 802-3-ethernet.wake-on-lan magic`. Lo dice `celiuz-remoto despertar` |
| Vigilancia (apagar si te roban el celular) | se arma en la ventana, página «Vigilancia» |

## Cuando algo no va

| Lo que pasa | Por qué | Arreglo |
|---|---|---|
| Al entrar desde el celular, los lanzadores no abren nada | la sesión entró sin uwsm (`/etc/sddm.conf`) | `./instalar.sh --remoto-sistema` |
| El tema de inicio sale con los colores de antes | es una copia | `./instalar.sh --sddm` |
| «Actualizar» la app falla: «la instaló OTRO equipo» | cada equipo firma con su clave | no hace falta actualizar desde ahí; o la misma clave (decisión 3) |
| La app dice «Sin conexión» | Tailscale apagado en el celular o en el equipo, o cuentas distintas | `tailscale status` en los dos |
| Apagar desde la app no hace nada con el equipo en la pantalla de inicio | falta lo de root | paso 2 |
| La GPU sale «—» | el servicio nació antes que el driver (ya se reintenta solo cada 30 s) | esperar medio minuto |

Para entender el porqué de cada cosa: [`DISEÑO.md`](DISEÑO.md). Lo que se
dicen la app y el equipo: [`PROTOCOLO.md`](PROTOCOLO.md).
