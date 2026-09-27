#!/usr/bin/env bash
# tests/unidad/sonido.sh — el menú rápido agrupa bien el sonido en juego, chat
# y música, y no toca lo que no es de ninguno.
#
# LO QUE VIGILA:
#  - El flujo del navegador se reconoce por su BINARIO y no por el PID de su
#    ventana: medido el 2026-09-25, lo abre un subproceso de Brave.
#  - Lo de Wine/Proton es del juego aunque su PID no sea el de la ventana.
#  - Una app añadida por el usuario cuenta como música.
#  - Los avisos del sistema y demás no caen en ningún grupo: el menú no les
#    cambia el volumen.
#  - Solo cuentan los flujos de SALIDA (el micrófono de otro programa no).
# Con un pw-dump inventado: nada de esto mira el PipeWire de verdad.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

salida="$(python3 - "$REPO/hypr/scripts/lib" <<'PY' 2>&1
import sys
sys.path.insert(0, sys.argv[1])
import sonido
def nodo(i, clase, nombre, binario, pid, vol=None):
    props = {"media.class": clase, "application.name": nombre,
             "application.process.binary": binario, "application.process.id": pid}
    info = {"props": props}
    if vol is not None:
        info["params"] = {"Props": [{"channelVolumes": [vol, vol]}]}
    return {"id": i, "type": "PipeWire:Interface:Node", "info": info}
dump = [
    nodo(1, "Stream/Output/Audio", "Brave", "brave", 77605, 0.512),
    nodo(2, "Stream/Output/Audio", "God of War", "wine64-preloader", 9999, 1.0),
    nodo(9, "Stream/Output/Audio", "Soulframe.exe", "", 8888),
    nodo(3, "Stream/Output/Audio", "Glassy Music", "glassy-music", 555, 0.125),
    nodo(4, "Stream/Output/Audio", "Avisos", "canberra-gtk-play", 777),
    nodo(5, "Stream/Input/Audio", "Grabadora", "brave", 77605),
    nodo(6, "Audio/Sink", "Altavoces", "", 0),
    nodo(7, "Stream/Output/Audio", "Juego nativo", "juego-nativo", 4242),
    {"id": 8, "type": "PipeWire:Interface:Port", "info": {"props": {}}},
]
g = sonido.grupos([4242], chat_extra=["brave"], musica_extra=["glassy music"], dump=dump)
for k in ("juego", "chat", "musica"):
    print(k, ",".join(str(f["id"]) for f in g[k]))
print("vol_brave", round(g["chat"][0]["volumen"], 2))
todos = {f["id"] for v in g.values() for f in v}
print("sin_grupo", ",".join(str(i) for i in (4, 5, 6) if i not in todos))
print("flujos", len(sonido.flujos(dump)))
PY
)"
codigo=$?
afirmar "sale con 0" test "$codigo" -eq 0
printf '%s\n' "$salida" > "$TMP/salida"
dato() { sed -n "s/^$1 //p" "$TMP/salida"; }
afirmar_igual "2,9,7" "$(dato juego)" "juego: el de Wine, el del árbol del juego y un .exe"
afirmar_igual "1" "$(dato chat)" "chat: el navegador, por su binario"
afirmar_igual "3" "$(dato musica)" "música: la app del usuario"
afirmar_igual "0.8" "$(dato vol_brave)" "el volumen en la escala de wpctl (cúbica)"
afirmar_igual "4,5,6" "$(dato sin_grupo)" "avisos, micrófonos y salidas fuera de todo grupo"
afirmar_igual "6" "$(dato flujos)" "solo cuenta flujos de salida"

afirmar_intacta_la_casa_real
resumen
