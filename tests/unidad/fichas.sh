#!/usr/bin/env bash
# tests/unidad/fichas.sh — la ficha de cada app del catalogo (celiuz-app.json)
# y la lista de las que se ofrecen (apps/lista.json), en hypr/scripts/lib/fichas.py.
#
# QUE VIGILA
# ----------
# - Que las fichas del repo (Celiuz Remoto, la radio) y la lista son validas:
#   si alguien rompe una, el catalogo la ensenaria como un error.
# - Que el validador no deja pasar lo que importa: una orden de instalar con
#   sudo dentro (la regla de la contraseña), un `sistema` sin decir para que,
#   un icono que se sale del repo o que no es imagen, un id raro.
# - Que la lista no admite una app a la vez de fuera y de dentro, ni una de
#   dentro que apunte fuera de los dotfiles.
# - Que «instalada» es «anunciada» y que un anuncio roto no cuenta.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno
FICHAS="$REPO/hypr/scripts/lib/fichas.py"

titulo "1. Lo que trae el repo"
afirmar "la ficha de Celiuz Remoto es valida" python3 "$FICHAS" validar "$REPO/remoto"
afirmar "la de la radio tambien" python3 "$FICHAS" validar "$REPO/sistema/radio"
salida="$(python3 "$FICHAS" lista 2>&1)"; codigo=$?
afirmar_igual "0" "$codigo" "la lista de apps se lee"
afirmar "  y trae Cell-Cast de GitHub" grep -q '^cell-cast	https://github.com/' <<< "$salida"
afirmar "  y las dos de dentro" grep -qx 'celiuz-remoto	dentro: remoto' <<< "$salida"

titulo "2. El validador"
APP="$TMP/app"
mkdir -p "$APP/img"
printf '<svg xmlns="http://www.w3.org/2000/svg"/>\n' > "$APP/img/icono.svg"
buena() {
    cat > "$APP/celiuz-app.json" <<'EOF'
{"ficha": 1, "id": "de-prueba", "nombre": "De prueba", "resumen": "r", "descripcion": "d",
 "categoria": "stream", "icono": "img/icono.svg", "capturas": [], "necesita": ["android"],
 "pide_sudo": "para algo", "ordenes": {"instalar": "./i.sh", "revisar": "./i.sh -r",
 "quitar": "./i.sh -q", "sistema": "./i.sh -s", "sistema_quitar": "./i.sh -S"}}
EOF
}
# cambiar 'expresion python sobre f' → reescribe la ficha
cambiar() {
    buena
    python3 - "$APP/celiuz-app.json" "$1" <<'EOF'
import json, sys
f = json.load(open(sys.argv[1]))
exec(sys.argv[2])
json.dump(f, open(sys.argv[1], "w"))
EOF
}
mal() {   # mal "descripcion" 'cambio' 'texto del error'
    cambiar "$2"
    local s; s="$(python3 "$FICHAS" validar "$APP" 2>&1)"
    if [ $? -ne 0 ] && grep -q -- "$3" <<< "$s"; then ok "$1"; else fallo "$1" "$s"; fi
}
buena
afirmar "una ficha buena pasa" python3 "$FICHAS" validar "$APP"
mal "instalar con sudo dentro: no" 'f["ordenes"]["instalar"] = "sudo ./i.sh"' 'pide contrasena'
mal "  ni con pkexec en medio" 'f["ordenes"]["quitar"] = "x && pkexec rm y"' 'pide contrasena'
mal "sistema sin decir para que: no" 'f["pide_sudo"] = None' 'no dice para que'
mal "sistema sin sistema_quitar: no" 'del f["ordenes"]["sistema_quitar"]' 'van juntas'
mal "pide_sudo sin sistema: no" 'del f["ordenes"]["sistema"]; del f["ordenes"]["sistema_quitar"]' 'no hay orden'
mal "un icono que se sale del repo: no" 'f["icono"] = "../../etc/passwd"' 'icono'
mal "un icono que no es imagen: no" 'open(sys.argv[1].replace("celiuz-app.json","x.txt"),"w").write("x"); f["icono"] = "x.txt"' '.svg o .png'
mal "un id con mayusculas: no" 'f["id"] = "De-Prueba"' 'id'
mal "una categoria inventada: no" 'f["categoria"] = "juegos"' 'categoria'
mal "una necesidad inventada: no" 'f["necesita"] = ["wifi6"]' 'no conoce'
mal "una orden desconocida: no" 'f["ordenes"]["borrar"] = "rm -rf ."' 'desconocida'
mal "aplica con sudo: no" 'f["ordenes"]["aplica"] = "sudo true"' 'pide contrasena'
cambiar 'f["ordenes"]["aplica"] = "./i.sh -a"'
afirmar "aplica es una orden opcional valida" python3 "$FICHAS" validar "$APP"

titulo "3. La lista"
lista_con() { printf '{"apps": [%s]}\n' "$1" > "$TMP/lista.json"; }
lista_mal() {   # lista_mal "descripcion" 'entradas' 'texto'
    lista_con "$2"
    local s; s="$(CELIUZ_APPS_LISTA="$TMP/lista.json" python3 "$FICHAS" lista 2>&1)"
    if [ $? -ne 0 ] && grep -q -- "$3" <<< "$s"; then ok "$1"; else fallo "$1" "$s"; fi
}
lista_mal "de fuera y de dentro a la vez: no" \
    '{"id": "x", "repo": "https://github.com/a/b", "dentro": "remoto"}' 'una de las dos'
lista_mal "de dentro fuera de los dotfiles: no" '{"id": "x", "dentro": "../../etc"}' 'carpeta de los dotfiles'
lista_mal "de dentro sin ficha: no" '{"id": "x", "dentro": "hypr"}' 'carpeta de los dotfiles'
lista_mal "un repo que no es de GitHub: no" '{"id": "x", "repo": "https://evil.example/a/b"}' 'github'
lista_mal "dos con el mismo id: no" \
    '{"id": "x", "dentro": "remoto"}, {"id": "x", "dentro": "sistema/radio"}' 'repetido'

titulo "4. Instalada es anunciada"
ANUNCIOS="$XDG_DATA_HOME/celiuz/apps.d"
mkdir -p "$ANUNCIOS"
buena
ln -s "$APP" "$ANUNCIOS/de-prueba"
ln -s "$TMP/no-existe" "$ANUNCIOS/rota"
afirmar_igual "de-prueba" "$(python3 "$FICHAS" instaladas | cut -f1 | paste -sd' ')" \
    "la anunciada cuenta y el anuncio roto no"

afirmar_intacta_la_casa_real
resumen
