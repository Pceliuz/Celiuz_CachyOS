#!/usr/bin/env bash
# tests/e2e/remoto-archivos.sh — Celiuz Remoto, fase 6: el explorador de
# archivos. Servidor de verdad, celular de mentira, casa de mentira.
#
# POR QUE: es la primera vez que el celular SACA cosas de la PC. Lo que se
# mira, por orden de gravedad:
#   1. que no se sale de la carpeta personal por ningun camino (../, rutas
#      absolutas, enlaces que apuntan fuera);
#   2. que lo que abre las demas puertas no sale nunca (.ssh, los perfiles de
#      los navegadores, los telefonos emparejados), ni listando, ni buscando, ni
#      por un enlace, ni pidiendo los ocultos;
#   3. que todo pide el permiso de archivos Y el pase;
#   4. y lo que se usa: listar, buscar, descargar (con Range para reanudar),
#      miniaturas, recientes con su estado contra la PC, y favoritos.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
igual() { afirmar_igual "$2" "$3" "$1"; }   # con la descripcion delante, como afirmar
CLI="$REPO/remoto/servidor/celiuz-remoto.py"
TEL="$REPO/tests/lib/telefono_falso.py"

esperar_a() {
    local limite=$(( $(date +%s%N) + $1 * 1000000000 )); shift
    while [ "$(date +%s%N)" -lt "$limite" ]; do
        "$@" >/dev/null 2>&1 && return 0
        sleep 0.1
    done
    "$@" >/dev/null 2>&1
}
campo() { python3 -c 'import json,sys; d=json.loads(sys.argv[1]); print(eval(sys.argv[2]))' "$1" "$2"; }
puerto_libre() { python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])'; }
RED="$(puerto_libre)"; USB="$(puerto_libre)"
mkdir -p "$XDG_CONFIG_HOME/celiuz"
printf 'puerto_red = %s\npuerto_usb = %s\nsubir_max_mb = 1\n' "$RED" "$USB" > "$XDG_CONFIG_HOME/celiuz/remoto.conf"
binario_falso tailscale 0 'case "$*" in "ip -4") echo 127.0.0.1 ;; *) echo "{\"Peer\":{}}" ;; esac'
binario_falso systemctl 0
binario_falso pgrep 1
binario_falso notify-send 0
binario_falso loginctl 0 'echo "[]"'

# La casa de mentira, con sus trampas
mkdir -p "$HOME/Documentos/CV" "$HOME/Imagenes" "$HOME/.ssh" "$HOME/.config/BraveSoftware/Default" \
         "$HOME/.config/kitty" "$TMP/fuera"
printf 'hola mundo\n' > "$HOME/Documentos/nota.txt"
printf 'informe' > "$HOME/Documentos/Informe Final.pdf"
printf 'cv' > "$HOME/Documentos/CV/cv.docx"
printf 'PRIVADA' > "$HOME/.ssh/id_ed25519"
printf 'cookies' > "$HOME/.config/BraveSoftware/Default/Cookies"
printf 'font_size 11' > "$HOME/.config/kitty/kitty.conf"
printf 'oculto' > "$HOME/.notas"
printf 'secreto de fuera' > "$TMP/fuera/secreto.txt"
ln -s "$TMP/fuera" "$HOME/enlace_fuera"
ln -s "$HOME/.ssh/id_ed25519" "$HOME/Documentos/clave"
ln -s "$HOME/Documentos" "$HOME/atajo_docs"
ln -s "$HOME/no-existe" "$HOME/roto"

"$CLI" servir 2>"$TMP/servidor.log" &
PID_SERVIDOR=$!
trap 'kill $PID_SERVIDOR 2>/dev/null; wait $PID_SERVIDOR 2>/dev/null; limpiar_entorno' EXIT INT TERM
esta_arriba() { test -S "$XDG_RUNTIME_DIR/celiuz-remoto.sock"; }
esperar_a 10 esta_arriba

hay_codigo() { grep -q '^CODIGO ' "$1"; }
emparejar() {   # <carpeta> <permisos>
    echo "clave-archivos" | "$CLI" emparejar --sin-adb --permisos "$2" > "$TMP/emp.out" 2>/dev/null &
    esperar_a 10 hay_codigo "$TMP/emp.out"
    "$TEL" emparejar "$USB" "$(sed -n 's/^CODIGO //p' "$TMP/emp.out")" "$1" > /dev/null
    wait $!
    rm -f "$TMP/emp.out"
}
emparejar "$TMP/tel" estado,archivos
emparejar "$TMP/sinpermiso" estado,energia
emparejar "$TMP/sinpase" estado,archivos
"$CLI" quitar-pase "$(cat "$TMP/sinpase/dispositivo")" >/dev/null
token() { campo "$("$TEL" entrar "$RED" "$1" clave-archivos)" 'd["cuerpo"]["token"]'; }
TOKEN="$(token "$TMP/tel")"; SINPERMISO="$(token "$TMP/sinpermiso")"; SINPASE="$(token "$TMP/sinpase")"
B="http://127.0.0.1:$RED"

# GET/PUT/DELETE con el token: {"http", "cuerpo" (JSON o texto), "cabeceras"}
pedir() { python3 - "$@" <<'FINPY'
import json, sys, urllib.request, urllib.error, urllib.parse
metodo, url, token = sys.argv[1], sys.argv[2], sys.argv[3]
cuerpo = sys.argv[4].encode() if len(sys.argv) > 4 and sys.argv[4] else None
extra = json.loads(sys.argv[5]) if len(sys.argv) > 5 else {}
p = urllib.request.Request(url, data=cuerpo, method=metodo,
                           headers=dict({"Authorization": "Bearer " + token, "Content-Type": "application/json"}, **extra))
try:
    with urllib.request.urlopen(p, timeout=30) as r:
        http, datos, cab = r.status, r.read(), dict(r.headers)
except urllib.error.HTTPError as e:
    http, datos, cab = e.code, e.read(), dict(e.headers)
try:
    c = json.loads(datos)
except ValueError:
    c = datos.decode("utf-8", "replace")
print(json.dumps({"http": http, "cuerpo": c, "cabeceras": cab}))
FINPY
}
q() { python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1]))' "$1"; }
http_de() { campo "$1" 'd["http"]'; }
nombres() { campo "$1" '" ".join(sorted(e["nombre"] for e in d["cuerpo"]["entradas"]))'; }

titulo "1. Todo pide permiso de archivos y el pase"
igual "sin permiso de archivos: 403" "403" "$(http_de "$(pedir GET "$B/v0/archivos?ruta=" "$SINPERMISO")")"
for ruta in "/v0/archivos?ruta=" "/v0/archivos/descargar?ruta=Documentos/nota.txt" "/v0/recientes" "/v0/favoritos" \
            "/v0/archivos/buscar?ruta=&q=nota"; do
    igual "sin pase: 423 en ${ruta%%\?*}" "423" "$(http_de "$(pedir GET "$B$ruta" "$SINPASE")")"
done
igual "sin sesion: 401" "401" "$(http_de "$(pedir GET "$B/v0/archivos?ruta=" "nada")")"

titulo "2. No se sale de la carpeta personal"
for ruta in "../" "../../etc/passwd" "/etc" "Documentos/../../" "enlace_fuera" "enlace_fuera/secreto.txt"; do
    r="$(pedir GET "$B/v0/archivos?ruta=$(q "$ruta")" "$TOKEN")"
    igual "listar «$ruta»: 403" "403" "$(http_de "$r")"
    r="$(pedir GET "$B/v0/archivos/descargar?ruta=$(q "$ruta")" "$TOKEN")"
    igual "  y descargarlo tampoco" "403" "$(http_de "$r")"
done
r="$(pedir GET "$B/v0/archivos?ruta=" "$TOKEN")"
igual "la carpeta personal: 200" "200" "$(http_de "$r")"
lista="$(nombres "$r")"
afirmar "  el enlace que sale de casa no aparece" sh -c "! echo '$lista' | grep -qw enlace_fuera"
afirmar "  ni el enlace roto" sh -c "! echo '$lista' | grep -qw roto"
afirmar "  el enlace que se queda en casa si" sh -c "echo '$lista' | grep -qw atajo_docs"
afirmar "  los ocultos no salen sin pedirlos" sh -c "! echo '$lista' | grep -q '\.notas'"
igual "  carpetas primero" "atajo_docs" "$(campo "$r" 'd["cuerpo"]["entradas"][0]["nombre"]')"

titulo "3. Lo que abre las demas puertas no sale nunca"
r="$(pedir GET "$B/v0/archivos?ruta=&ocultos=1" "$TOKEN")"
lista="$(nombres "$r")"
afirmar "pidiendo los ocultos sale .notas" sh -c "echo '$lista' | grep -q '\.notas'"
afirmar "  y .config" sh -c "echo '$lista' | grep -q '\.config'"
afirmar "  pero no .ssh" sh -c "! echo '$lista' | grep -q '\.ssh'"
r="$(pedir GET "$B/v0/archivos?ruta=.config&ocultos=1" "$TOKEN")"
lista="$(nombres "$r")"
afirmar "en .config sale kitty" sh -c "echo '$lista' | grep -qw kitty"
afirmar "  pero no el perfil del navegador" sh -c "! echo '$lista' | grep -q BraveSoftware"
for ruta in ".ssh" ".ssh/id_ed25519" "Documentos/../.ssh/id_ed25519" ".config/BraveSoftware/Default/Cookies" \
            "Documentos/clave" ".local/state/celiuz/remoto/dispositivos.json"; do
    igual "descargar «$ruta»: 403" "403" "$(http_de "$(pedir GET "$B/v0/archivos/descargar?ruta=$(q "$ruta")" "$TOKEN")")"
done
r="$(pedir GET "$B/v0/archivos?ruta=Documentos" "$TOKEN")"
afirmar "el enlace a la clave no sale en la lista de Documentos" sh -c "! echo '$(nombres "$r")' | grep -qw clave"
r="$(pedir GET "$B/v0/archivos/buscar?ruta=&q=id_ed&ocultos=1" "$TOKEN")"
igual "buscando, tampoco aparece" "0" "$(campo "$r" 'len(d["cuerpo"]["resultados"])')"
r="$(pedir GET "$B/v0/archivos/buscar?ruta=&q=Cookies&ocultos=1" "$TOKEN")"
igual "  ni las cookies del navegador" "0" "$(campo "$r" 'len(d["cuerpo"]["resultados"])')"
igual "ni se puede fijar de favorito" "403" "$(http_de "$(pedir PUT "$B/v0/favoritos" "$TOKEN" '{"ruta":".ssh"}')")"

titulo "4. Listar y buscar"
r="$(pedir GET "$B/v0/archivos?ruta=Documentos" "$TOKEN")"
igual "Documentos: carpeta primero (CV)" "CV" "$(campo "$r" 'd["cuerpo"]["entradas"][0]["nombre"]')"
igual "  con cuantos elementos tiene" "1" "$(campo "$r" 'd["cuerpo"]["entradas"][0]["elementos"]')"
igual "  y el tamaño de cada archivo" "11" \
    "$(campo "$r" '[e for e in d["cuerpo"]["entradas"] if e["nombre"]=="nota.txt"][0]["tamano"]')"
igual "una carpeta que no hay: 404" "404" "$(http_de "$(pedir GET "$B/v0/archivos?ruta=Nada" "$TOKEN")")"
r="$(pedir GET "$B/v0/archivos/buscar?ruta=&q=informe" "$TOKEN")"
igual "buscar «informe» (sin mayusculas) lo encuentra" "Documentos/Informe Final.pdf" \
    "$(campo "$r" 'd["cuerpo"]["resultados"][0]["ruta"]')"
igual "buscar con una letra: 400" "400" "$(http_de "$(pedir GET "$B/v0/archivos/buscar?ruta=&q=a" "$TOKEN")")"

titulo "5. Descargar, y reanudar con Range"
r="$(pedir GET "$B/v0/archivos/descargar?ruta=Documentos/nota.txt" "$TOKEN")"
igual "200" "200" "$(http_de "$r")"
igual "  el contenido entero" "hola mundo" "$(campo "$r" 'd["cuerpo"].strip()')"
afirmar "  con su nombre" sh -c "echo '$(campo "$r" 'd["cabeceras"].get("Content-Disposition")')' | grep -q nota.txt"
r="$(pedir GET "$B/v0/archivos/descargar?ruta=Documentos/nota.txt" "$TOKEN" "" '{"Range":"bytes=5-9"}')"
igual "un Range: 206" "206" "$(http_de "$r")"
igual "  con solo ese trozo" "mundo" "$(campo "$r" 'd["cuerpo"]')"
igual "reanudar no cuenta como otra descarga" "1" \
    "$(grep -c '"accion": "descarga"' "$XDG_STATE_HOME/celiuz/remoto/registro.jsonl")"
igual "una carpeta no se descarga: 404" "404" \
    "$(http_de "$(pedir GET "$B/v0/archivos/descargar?ruta=Documentos/CV" "$TOKEN")")"

titulo "6. Recientes: su estado contra la PC"
pedir GET "$B/v0/archivos/descargar?ruta=$(q "Documentos/Informe Final.pdf")" "$TOKEN" >/dev/null
pedir GET "$B/v0/archivos/descargar?ruta=Documentos/CV/cv.docx" "$TOKEN" >/dev/null
estado_de() { local r; r="$(pedir GET "$B/v0/recientes" "$TOKEN")"
    python3 -c 'import json,sys; d=json.loads(sys.argv[1]); print([x["estado"] for x in d["cuerpo"]["recientes"] if x["ruta"]==sys.argv[2]][0])' "$r" "$1"; }
r="$(pedir GET "$B/v0/recientes" "$TOKEN")"
igual "tres bajados, el ultimo arriba" "Documentos/CV/cv.docx" "$(campo "$r" 'd["cuerpo"]["recientes"][0]["ruta"]')"
igual "  con quien lo bajo" "$(cat "$TMP/tel/dispositivo")" "$(campo "$r" 'd["cuerpo"]["recientes"][0]["dispositivo"]')"
igual "sin tocar: igual" "igual" "$(estado_de Documentos/nota.txt)"
printf 'hola mundo, cambiado\n' > "$HOME/Documentos/nota.txt"
igual "al cambiar en la PC: nueva_version" "nueva_version" "$(estado_de Documentos/nota.txt)"
rm "$HOME/Documentos/CV/cv.docx"
igual "al borrarlo: no_esta" "no_esta" "$(estado_de Documentos/CV/cv.docx)"
afirmar "el historial es solo tuyo (0600)" test "$(stat -c %a "$XDG_STATE_HOME/celiuz/remoto/historial.json")" = 600
r="$(pedir DELETE "$B/v0/recientes?ruta=Documentos/CV/cv.docx" "$TOKEN")"
igual "olvidar uno" "1" "$(campo "$r" 'd["cuerpo"]["olvidados"]')"
igual "  quedan dos" "2" "$(campo "$(pedir GET "$B/v0/recientes" "$TOKEN")" 'len(d["cuerpo"]["recientes"])')"

titulo "7. Favoritos"
r="$(pedir PUT "$B/v0/favoritos" "$TOKEN" '{"ruta":"Documentos/CV"}')"
igual "fijar una carpeta" "carpeta" "$(campo "$r" 'd["cuerpo"]["favoritos"][0]["tipo"]')"
pedir PUT "$B/v0/favoritos" "$TOKEN" '{"ruta":"Documentos/CV/"}' >/dev/null
igual "  dos veces (con / al final) es una" "1" "$(campo "$(pedir GET "$B/v0/favoritos" "$TOKEN")" 'len(d["cuerpo"]["favoritos"])')"
r="$(pedir GET "$B/v0/archivos?ruta=Documentos" "$TOKEN")"
igual "  y la lista lo marca" "True" "$(campo "$r" '[e for e in d["cuerpo"]["entradas"] if e["nombre"]=="CV"][0]["favorito"]')"
rmdir "$HOME/Documentos/CV"
igual "si se borra en la PC, sigue y dice que no existe" "False" \
    "$(campo "$(pedir GET "$B/v0/favoritos" "$TOKEN")" 'd["cuerpo"]["favoritos"][0]["existe"]')"
r="$(pedir DELETE "$B/v0/favoritos?ruta=Documentos/CV" "$TOKEN")"
igual "  y se puede quitar igual" "0" "$(campo "$r" 'len(d["cuerpo"]["favoritos"])')"
igual "fijar algo que no hay: 404" "404" "$(http_de "$(pedir PUT "$B/v0/favoritos" "$TOKEN" '{"ruta":"Nada"}')")"

titulo "8. Miniaturas"
if ! command -v ffmpeg >/dev/null 2>&1; then
    _gris "  (se salta: sin ffmpeg no hay miniaturas)"
else
    ffmpeg -hide_banner -loglevel error -f lavfi -i color=c=purple:s=800x600 -frames:v 1 "$HOME/Imagenes/foto.png"
    r="$(pedir GET "$B/v0/archivos/miniatura?ruta=Imagenes/foto.png&lado=128" "$TOKEN")"
    igual "una imagen: 200" "200" "$(http_de "$r")"
    igual "  en JPEG" "image/jpeg" "$(campo "$r" 'd["cabeceras"].get("Content-Type")')"
    pedir GET "$B/v0/archivos/miniatura?ruta=Imagenes/foto.png&lado=128" "$TOKEN" >/dev/null
    igual "  la segunda vez sale de la cache (una sola hecha)" "1" \
        "$(find "$XDG_CACHE_HOME/celiuz/remoto/miniaturas" -name '*.jpg' | wc -l)"
    afirmar "  y ningun temporal a medias" sh -c "! find '$XDG_CACHE_HOME/celiuz/remoto/miniaturas' -name '*.nuevo.*' | grep -q ."
    igual "un .txt no tiene miniatura: 404" "404" \
        "$(http_de "$(pedir GET "$B/v0/archivos/miniatura?ruta=Documentos/nota.txt" "$TOKEN")")"
    igual "la de .ssh tampoco: 403" "403" \
        "$(http_de "$(pedir GET "$B/v0/archivos/miniatura?ruta=.ssh/id_ed25519" "$TOKEN")")"
fi

titulo "9. Subir a la PC (fase 8): solo a Descargas/Celiuz Remoto, sin pisar nada"
SUB="$HOME/Descargas/Celiuz Remoto"
subir() {   # <token> <nombre> <fichero> -> {"http", "cuerpo"}
    python3 - "$B" "$1" "$2" "$3" <<'FINPY'
import json, sys, urllib.request, urllib.error, urllib.parse
b, token, nombre, fichero = sys.argv[1:5]
datos = open(fichero, "rb").read()
p = urllib.request.Request(f"{b}/v0/archivos/subir?nombre={urllib.parse.quote(nombre)}", data=datos, method="POST",
                           headers={"Authorization": "Bearer " + token, "Content-Type": "application/octet-stream"})
try:
    with urllib.request.urlopen(p, timeout=30) as r:
        print(json.dumps({"http": r.status, "cuerpo": json.loads(r.read())}))
except urllib.error.HTTPError as e:
    print(json.dumps({"http": e.code, "cuerpo": json.loads(e.read() or b"{}")}))
FINPY
}
head -c 300000 /dev/urandom > "$TMP/grande.bin"
printf 'hola desde el celular' > "$TMP/nota.txt"
igual "sin pase: 423" "423" "$(campo "$(subir "$SINPASE" nota.txt "$TMP/nota.txt")" 'd["http"]')"
igual "sin permiso de archivos: 403" "403" "$(campo "$(subir "$SINPERMISO" nota.txt "$TMP/nota.txt")" 'd["http"]')"
r="$(subir "$TOKEN" "foto del celular.bin" "$TMP/grande.bin")"
igual "subir: 200" "200" "$(campo "$r" 'd["http"]')"
igual "  a Descargas/Celiuz Remoto" "Descargas/Celiuz Remoto/foto del celular.bin" "$(campo "$r" 'd["cuerpo"]["ruta"]')"
afirmar "  entero y sin cambiar un byte" cmp -s "$TMP/grande.bin" "$SUB/foto del celular.bin"
r="$(subir "$TOKEN" "foto del celular.bin" "$TMP/nota.txt")"
igual "otro con el mismo nombre no pisa: «(1)»" "foto del celular (1).bin" "$(campo "$r" 'd["cuerpo"]["nombre"]')"
afirmar "  y el primero sigue igual" cmp -s "$TMP/grande.bin" "$SUB/foto del celular.bin"
r="$(subir "$TOKEN" "../../.bashrc" "$TMP/nota.txt")"
igual "«../../.bashrc» se queda dentro, sin carpetas y sin punto" "Descargas/Celiuz Remoto/bashrc" "$(campo "$r" 'd["cuerpo"]["ruta"]')"
afirmar "  y no toca el .bashrc de casa" test ! -e "$HOME/.bashrc"
head -c 1500000 /dev/urandom > "$TMP/enorme.bin"
igual "más grande que subir_max_mb: 413" "413" "$(campo "$(subir "$TOKEN" enorme.bin "$TMP/enorme.bin")" 'd["http"]')"
afirmar "  y no se queda" test ! -e "$SUB/enorme.bin"
afirmar "no queda ningun .parcial" sh -c "! ls -A '$SUB' | grep -q parcial"
afirmar "la PC avisa de lo recibido" grep -q "archivo recibido" "$REGISTRO/notify-send.log"
afirmar "y lo apunta" grep -q '"accion": "subida"' "$XDG_STATE_HOME/celiuz/remoto/registro.jsonl"

afirmar "el servidor no se quejo" sh -c "! grep -q Traceback '$TMP/servidor.log'"
afirmar_intacta_la_casa_real
resumen
