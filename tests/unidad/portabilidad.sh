#!/usr/bin/env bash
# tests/unidad/portabilidad.sh — que el repo valga clonado en cualquier ruta.
#
# Este repo es publico y lo usa gente que no es el autor. Durante mucho tiempo
# obligaba a clonarlo exactamente en ~/dotfiles: los .conf y los scripts llevaban
# esa ruta escrita, asi que quien lo clonaba en ~/.dotfiles o ~/repos/dotfiles se
# quedaba con medio escritorio muerto **y sin ningun mensaje de error** — los
# `source` que no encuentran su fichero no se quejan.
#
# Esta prueba es un cerrojo: si alguien vuelve a escribir "$HOME/dotfiles" en
# codigo, falla. No comprueba que el repo funcione (de eso van las otras), sino
# que no se cuele la costumbre otra vez.
#
# Los comentarios SI pueden mencionar ~/dotfiles: sirven para explicarse y no
# afectan a nada.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

titulo "1. Ningun fichero de codigo cablea la ruta del repo"
python3 - "$REPO" > "$TMP/cableadas.txt" <<'PY'
import io, pathlib, re, sys, tokenize

raiz = pathlib.Path(sys.argv[1])
PATRON = re.compile(r'(\$HOME/dotfiles|~/dotfiles|["\']dotfiles/)')

def lineas_de_documentacion(f, src):
    """Las lineas que son comentario o docstring, que no afectan a nada."""
    doc = set()
    if f.suffix == ".py":
        try:
            for tok in tokenize.generate_tokens(io.StringIO(src).readline):
                if tok.type == tokenize.COMMENT or (
                        tok.type == tokenize.STRING and tok.string.startswith(('"""', "'''"))):
                    doc.update(range(tok.start[0], tok.end[0] + 1))
        except Exception:
            pass
    return doc

for f in sorted(raiz.rglob("*")):
    if f.suffix not in (".conf", ".sh", ".py") or ".git" in f.parts or "tests" in f.parts:
        continue
    src = f.read_text(encoding="utf-8", errors="replace")
    doc = lineas_de_documentacion(f, src)
    for n, linea in enumerate(src.splitlines(), 1):
        if not PATRON.search(linea):
            continue
        limpia = linea.strip()
        # Comentarios de shell/hyprlang, y prosa dentro de docstrings de Python.
        if limpia.startswith("#") or n in doc:
            continue
        # Una linea de docstring suelta (la ruta del fichero en su cabecera).
        if f.suffix == ".py" and limpia.startswith("~/dotfiles"):
            continue
        print(f"{f.relative_to(raiz)}:{n}: {limpia[:70]}")
PY

if [ -s "$TMP/cableadas.txt" ]; then
    fallo "ningun fichero de codigo cablea \$HOME/dotfiles" "$(cat "$TMP/cableadas.txt")"
else
    ok "ningun fichero de codigo cablea \$HOME/dotfiles"
fi

titulo "2. Los .conf apuntan por ~/.config/hypr"
# Es la ruta que vale se clone el repo donde se clone, porque ese enlace lo crea
# instalar.sh. hyprlang no sabe donde esta su propio fichero y el `source`
# relativo NO funciona (probado: no carga y configerrors sale vacio), asi que
# esta es la unica salida.
n_config=$(grep -rho '\$HOME/\.config/hypr' "$REPO"/hypr/*.conf "$REPO"/hypr/conf/*.conf 2>/dev/null | wc -l)
afirmar "los .conf usan \$HOME/.config/hypr" test "$n_config" -gt 20

for fichero in hyprland.conf hyprlock.conf hypridle.conf; do
    afirmar_no_contiene "$REPO/hypr/$fichero" '^[^#]*\$HOME/dotfiles' \
        "$fichero no cablea la ruta del repo"
done
for fichero in keybinds.conf autostart.conf; do
    afirmar_no_contiene "$REPO/hypr/conf/$fichero" '^[^#]*\$HOME/dotfiles' \
        "$fichero no cablea la ruta del repo"
done

titulo "3. Los scripts averiguan su propia raiz"
# Se copian a otra ruta y se comprueba que siguen sabiendo donde esta el repo.
# Es lo que pasa de verdad cuando se les llama por ~/.config/hypr/scripts/...
COPIA="$(copiar_repo)"
raiz_detectada="$(python3 -c "
import sys; sys.path.insert(0, '$COPIA/hypr/scripts/lib')
import wallpapers as wp
print(wp.RAIZ)" 2>/dev/null)"
afirmar_igual "$COPIA" "$raiz_detectada" \
    "wallpapers.py se situa en la copia, no en el repo original"

raiz_juegos="$(python3 -c "
import sys, os; sys.path.insert(0, '$COPIA/hypr/scripts/lib')
import juegos
print(os.path.dirname(os.path.dirname(juegos.EXCEPCIONES)))" 2>/dev/null)"
afirmar_igual "$COPIA" "$raiz_juegos" "juegos.py encuentra sus excepciones en la copia"

# Y por un ENLACE, que es como se les llama de verdad desde los binds.
ln -sfn "$COPIA/hypr" "$TMP/enlace-hypr"
raiz_enlace="$(python3 -c "
import sys; sys.path.insert(0, '$TMP/enlace-hypr/scripts/lib')
import wallpapers as wp
print(wp.RAIZ)" 2>/dev/null)"
afirmar_igual "$COPIA" "$raiz_enlace" \
    "y tambien llamandolo por un enlace simbolico (realpath, no abspath)"

titulo "4. No toco nada de tu equipo"
afirmar_intacta_la_casa_real

resumen
