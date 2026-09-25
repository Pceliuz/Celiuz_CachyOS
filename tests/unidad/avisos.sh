#!/usr/bin/env bash
# tests/unidad/avisos.sh — el historial de notificaciones.
#
# LO QUE SE VIGILA AQUI ES UNA PROMESA DE PRIVACIDAD, no el formato de la lista.
#
# El trato de este historial es: se graba todo, pero lo grabado vive en un tmpfs
# que se borra al cerrar sesion, y SOLO baja al disco lo que apartes tu, uno a
# uno. Por ahi pasa cualquier cosa que una app decida notificar —un codigo de dos
# factores, el asunto de un correo, el nombre de quien te escribe—, asi que si un
# dia alguien cambia una ruta y el registro entero empieza a caer en ~/.local,
# eso no da ningun error: simplemente deja de cumplirse lo prometido, en
# silencio, y no te enteras hasta que ya esta escrito. Por eso es lo primero.
#
# Lo segundo es el plegado del registro. El fichero es JSONL de solo-anadir: un
# aviso es una linea, y "lo descartaste" es OTRA linea que se pliega encima. Si
# el plegado se rompe, el historial sigue listandose tan normal, solo que
# mintiendo sobre lo que paso con cada aviso.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/../lib/comun.sh"

preparar_entorno

AVISOS="$REPO/hypr/scripts/avisos.py"

python3 - "$AVISOS" > "$TMP/salida.txt" 2>"$TMP/error.txt" <<'PY'
import contextlib, importlib.util, io, json, os, sys
from pathlib import Path

def callando(funcion, *args):
    """Ejecuta algo que DEBE quejarse, y devuelve (codigo, lo que se quejo).

    Los casos de error de este modulo avisan por stderr a proposito. Sin
    recogerlo aqui, la prueba de "el modulo se importa sin quejarse" —que mira
    que stderr venga vacio— fallaria por culpa de un error provocado adrede.
    """
    buzon = io.StringIO()
    with contextlib.redirect_stderr(buzon):
        codigo = funcion(*args)
    return codigo, buzon.getvalue()

ruta = sys.argv[1]
spec = importlib.util.spec_from_file_location("avisos", ruta)
avisos = importlib.util.module_from_spec(spec)
spec.loader.exec_module(avisos)

r = {}

# --- Donde se guarda cada cosa ----------------------------------------------
sesion = avisos.fichero_sesion()
guardados = avisos.fichero_guardados()
r["sesion_en_runtime"] = str(sesion).startswith(os.environ["XDG_RUNTIME_DIR"])
r["guardados_en_datos"] = str(guardados).startswith(os.environ["XDG_DATA_HOME"])
# Y no pueden ser el mismo sitio: si lo fueran, "guardar" no significaria nada
# y el borrado al cerrar sesion se llevaria tambien lo apartado.
r["no_son_el_mismo"] = sesion != guardados

# --- Las hints binarias no entran -------------------------------------------
sucias = {
    "urgency": 2, "category": "device", "sender-pid": 1234,
    "x-canonical-private-synchronous": "hilo", "silencioso": True,
    "escala": 1.5,
    "image-data": [1, 2, 3] * 5000,          # el icono en crudo
    "image_path_bytes": bytearray(b"xxxx"),
}
limpias = avisos.hints_escalares(sucias)
r["quita_el_array"] = "image-data" not in limpias
r["quita_los_bytes"] = "image_path_bytes" not in limpias
r["deja_los_escalares"] = all(k in limpias for k in
    ("urgency", "category", "sender-pid",
     "x-canonical-private-synchronous", "silencioso", "escala"))

# --- Los transitorios no se apuntan -----------------------------------------
# El volumen y el brillo (osd.sh) mandan un aviso por pulsacion con `-e`.
r["transitorio_fuera"] = not avisos.se_apunta({"transient": True})
r["normal_dentro"] = avisos.se_apunta({"urgency": 1}) and avisos.se_apunta({})
r["transient_falso_dentro"] = avisos.se_apunta({"transient": False})

# --- El plegado del registro -------------------------------------------------
def linea(d):
    with sesion.open("a", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")

linea({"tipo": "aviso", "n": 1, "epoch": 100.0, "hora": "2026-08-07T10:00:00",
       "app": "Celiuz", "resumen": "Primero", "cuerpo": "uno", "urgencia": "normal"})
linea({"tipo": "aviso", "n": 2, "epoch": 200.0, "hora": "2026-08-07T11:00:00",
       "app": "Celiuz", "resumen": "Segundo", "cuerpo": "dos", "urgencia": "critica"})
linea({"tipo": "cierre", "n": 1, "cierre": "la descartaste"})
linea({"tipo": "accion", "n": 2, "pulsada": "default"})
# Una linea a medias, de una caida a mitad de escritura: no puede tumbar la
# lectura del historial entero.
with sesion.open("a", encoding="utf-8") as f:
    f.write('{"tipo": "aviso", "n": 3, "resu\n')

lista = avisos.avisos()
r["lee_los_dos"] = len(lista) == 2
r["linea_rota_no_tumba"] = len(lista) == 2
r["pliega_el_cierre"] = lista[0].get("cierre") == "la descartaste"
r["pliega_la_accion"] = lista[1].get("pulsada") == "default"
r["conserva_el_cuerpo"] = lista[0].get("cuerpo") == "uno"
r["orden_por_numero"] = [a["n"] for a in lista] == [1, 2]

# --- Guardar, no repetir, olvidar -------------------------------------------
r["guardar_va"] = avisos.guardar(2, "hablarlo manana") == 0
r["guardar_dos_veces_no_duplica"] = (avisos.guardar(2) == 0
                                     and len(avisos._lineas(guardados)) == 1)
codigo, queja = callando(avisos.guardar, 99)
r["guardar_lo_que_no_hay_falla"] = codigo == 1
r["guardar_lo_que_no_hay_avisa"] = "99" in queja
r["la_nota_se_guarda"] = avisos._lineas(guardados)[0].get("nota") == "hablarlo manana"

avisos.guardar(1)
r["dos_guardados"] = len(avisos._lineas(guardados)) == 2
r["olvidar_va"] = avisos.olvidar(1) == 0
quedan = avisos._lineas(guardados)
# Lo importante de olvidar no es que quite uno, es que NO se lleve por delante
# el resto: el fichero se reescribe entero.
r["olvidar_deja_el_otro"] = len(quedan) == 1 and quedan[0]["resumen"] == "Primero"
codigo, queja = callando(avisos.olvidar, 7)
r["olvidar_fuera_de_rango"] = codigo == 1
r["olvidar_fuera_de_rango_avisa"] = "7" in queja

# --- Guardar NO toca el historial de la sesion ------------------------------
# Y al reves: el registro volatil es la fuente, no se muta al apartar cosas.
r["sesion_intacta"] = len(avisos.avisos()) == 2

# --- El cuerpo se recorta ----------------------------------------------------
r["hay_tope_de_cuerpo"] = avisos.MAXIMO_CUERPO > 0

for k, v in r.items():
    print(f"{k}={1 if v else 0}")
PY

leer() { grep -m1 "^$1=" "$TMP/salida.txt" 2>/dev/null | cut -d= -f2; }

afirmar "el modulo se importa sin quejarse" test ! -s "$TMP/error.txt"

titulo "1. Lo volatil es volatil, y lo guardado es aparte"
afirmar_igual "1" "$(leer sesion_en_runtime)"  "el historial de la sesion vive en XDG_RUNTIME_DIR"
afirmar_igual "1" "$(leer guardados_en_datos)" "lo apartado vive en XDG_DATA_HOME"
afirmar_igual "1" "$(leer no_son_el_mismo)"    "no son el mismo fichero"

titulo "2. Ni un icono en crudo dentro del registro"
afirmar_igual "1" "$(leer quita_el_array)"      "una hint con la imagen en pixeles se descarta"
afirmar_igual "1" "$(leer quita_los_bytes)"     "y una hint de bytes tambien"
afirmar_igual "1" "$(leer deja_los_escalares)"  "las hints utiles siguen estando"

titulo "2b. Lo transitorio (volumen, brillo) no llena el historial"
afirmar_igual "1" "$(leer transitorio_fuera)"      "un aviso con transient no se apunta"
afirmar_igual "1" "$(leer normal_dentro)"          "uno normal si"
afirmar_igual "1" "$(leer transient_falso_dentro)" "y transient=false cuenta como normal"

titulo "3. El registro se pliega bien, y una linea rota no lo tumba"
afirmar_igual "1" "$(leer lee_los_dos)"         "lee los avisos apuntados"
afirmar_igual "1" "$(leer linea_rota_no_tumba)" "una linea a medias no se lleva el historial"
afirmar_igual "1" "$(leer pliega_el_cierre)"    "«la descartaste» se pliega sobre su aviso"
afirmar_igual "1" "$(leer pliega_la_accion)"    "la accion pulsada se pliega sobre el suyo"
afirmar_igual "1" "$(leer conserva_el_cuerpo)"  "plegar no borra lo que ya habia"
afirmar_igual "1" "$(leer orden_por_numero)"    "salen en el orden en que llegaron"

titulo "4. Guardar y olvidar"
afirmar_igual "1" "$(leer guardar_va)"                    "guardar un aviso funciona"
afirmar_igual "1" "$(leer la_nota_se_guarda)"             "la nota se guarda con el"
afirmar_igual "1" "$(leer guardar_dos_veces_no_duplica)"  "guardarlo dos veces no lo duplica"
afirmar_igual "1" "$(leer guardar_lo_que_no_hay_falla)"   "guardar un numero que no existe falla"
afirmar_igual "1" "$(leer guardar_lo_que_no_hay_avisa)"   "y dice cual era el numero"
afirmar_igual "1" "$(leer dos_guardados)"                 "se pueden guardar varios"
afirmar_igual "1" "$(leer olvidar_va)"                    "olvidar funciona"
afirmar_igual "1" "$(leer olvidar_deja_el_otro)"          "olvidar uno NO se lleva a los demas"
afirmar_igual "1" "$(leer olvidar_fuera_de_rango)"        "olvidar un numero que no existe falla"
afirmar_igual "1" "$(leer olvidar_fuera_de_rango_avisa)"  "y tambien dice cual era"
afirmar_igual "1" "$(leer sesion_intacta)"                "guardar no toca el historial de la sesion"
afirmar_igual "1" "$(leer hay_tope_de_cuerpo)"            "hay un tope para el cuerpo de un aviso"

titulo "5. No toco nada de tu equipo"
afirmar_intacta_la_casa_real

resumen
