#!/usr/bin/env python3
"""
hypr/scripts/lib/hardware.py — que hay dentro de ESTE equipo, para enseñar solo
lo que existe.

    hardware.py           el resumen, con el porque de cada cosa
    hardware.py --json    lo mismo, para scripts

Lo usa el overlay del modo gaming (modo-gaming.escribir_mangohud): una GPU
integrada no tiene sensor ni memoria propios, y MangoHud pintaba «0 °C» y
«VRAM 0.0 GiB» en la laptop (2026-10-20). Se pregunta en CALIENTE, cada vez que
se entra al modo: una tarjeta grafica se cambia sin reinstalar (la regla de oro
del CLAUDE.md).

QUE ES «DEDICADA», tarjeta por tarjeta, porque no hay un campo que lo diga:
  - NVIDIA: siempre dedicada.
  - Intel: la integrada vive SIEMPRE en el bus 0 (0000:00:02.0); una Arc va
    por PCIe, en otro bus.
  - AMD: aqui es donde no hay dato limpio. Una APU (Ryzen con graficos) tambien
    va en otro bus y tambien tiene «VRAM» (un trozo de la RAM reservado en la
    BIOS). Lo que solo tiene una dedicada es ventilador o limite de potencia en
    su hwmon (`fan1_input`, `power1_cap`). Es una heuristica, y por eso cada GPU
    lleva su `motivo`: si se equivoca, se ve por que.
Solo se mira si los ficheros EXISTEN, sin leerlos: leer el sensor de una GPU
dormida (la NVIDIA de un portatil hibrido) la despierta.
"""

import glob
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import maquina  # noqa: E402
import sensores  # noqa: E402

DRM = "/sys/class/drm"
NVIDIA_PROC = "/proc/driver/nvidia/gpus"
FABRICANTES = {"0x8086": "Intel", "0x10de": "NVIDIA", "0x1002": "AMD"}


def _leer(ruta):
    try:
        with open(ruta, encoding="utf-8", errors="replace") as fh:
            return fh.read().strip()
    except OSError:
        return None


def _hay(carpeta, *patrones):
    return any(glob.glob(os.path.join(carpeta, "hwmon", "hwmon*", p)) for p in patrones)


def _nombre(pci, fabricante):
    """El modelo, de lspci (o del driver de NVIDIA). Sin ninguno, el fabricante."""
    for info in glob.glob(os.path.join(NVIDIA_PROC, pci, "information")):
        for linea in (_leer(info) or "").splitlines():
            if linea.startswith("Model:"):
                return linea.split(":", 1)[1].strip()
    try:
        r = subprocess.run(["lspci", "-vmm", "-s", pci], capture_output=True,
                           text=True, timeout=2, check=False)
        for linea in r.stdout.splitlines():
            if linea.startswith("Device:"):
                return "%s %s" % (fabricante, linea.split(":", 1)[1].strip())
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "GPU %s" % fabricante


def gpus(drm=None):
    """Una entrada por tarjeta grafica PCI: nombre, fabricante, driver, pci,
    dedicada, temp (tiene sensor propio), vram (tiene memoria propia), motivo."""
    drm = drm or DRM
    lista = []
    for tarjeta in sorted(glob.glob(os.path.join(drm, "card[0-9]*"))):
        if "-" in os.path.basename(tarjeta):
            continue                    # card1-eDP-1 es una salida, no una GPU
        disp = os.path.join(tarjeta, "device")
        vendor = _leer(os.path.join(disp, "vendor"))
        if not vendor:
            continue                    # simpledrm y compañia: sin PCI detras
        fabricante = FABRICANTES.get(vendor, vendor)
        driver = os.path.basename(os.path.realpath(os.path.join(disp, "driver")))
        pci = os.path.basename(os.path.realpath(disp))
        if fabricante == "NVIDIA":
            dedicada, motivo = True, "NVIDIA siempre es una tarjeta aparte"
            temp = vram = True          # su driver no las deja en /sys: NVML
        elif fabricante == "Intel":
            dedicada = not pci.startswith("0000:00:")
            motivo = ("Intel fuera del bus 0: una Arc" if dedicada else
                      "Intel en el bus 0 (%s): la integrada del procesador" % pci)
            temp = _hay(disp, "temp*_input")
            vram = dedicada
        elif fabricante == "AMD":
            dedicada = _hay(disp, "fan*_input", "power*_cap")
            motivo = ("AMD con ventilador o limite de potencia propios" if dedicada else
                      "AMD sin ventilador ni limite de potencia: la de una APU")
            temp = _hay(disp, "temp*_input")
            vram = dedicada and os.path.exists(os.path.join(disp, "mem_info_vram_total"))
        else:
            dedicada, motivo = False, "fabricante desconocido (%s)" % vendor
            temp = _hay(disp, "temp*_input")
            vram = False
        lista.append({"nombre": _nombre(pci, fabricante), "fabricante": fabricante,
                      "driver": driver, "pci": pci, "dedicada": dedicada,
                      "temp": temp, "vram": vram, "motivo": motivo})
    return lista


def detectar(drm=None):
    d = maquina.detalle()
    cpu = sensores.cpu()
    nombre_cpu = None
    for linea in (_leer("/proc/cpuinfo") or "").splitlines():
        if linea.startswith("model name"):
            nombre_cpu = linea.split(":", 1)[1].strip()
            break
    return {
        "tipo": d["tipo"],
        "motivo_tipo": d["motivo"],
        "bateria": d["bateria"],
        "cpu": {"nombre": nombre_cpu, "sensor": cpu["nombre"] if cpu else None},
        "gpus": gpus(drm),
    }


def overlay(hw):
    """Que enseña la barra de FPS con este equipo: {gpu, gpu_nombre, gpu_temp,
    vram, cpu_temp, bateria}."""
    g = hw["gpus"]
    return {
        "gpu": bool(g),
        # Con dos (portatil hibrido) el nombre dice en cual corre el juego.
        "gpu_nombre": len(g) > 1,
        "gpu_temp": any(x["temp"] for x in g),
        "vram": any(x["vram"] for x in g),
        "cpu_temp": bool(hw["cpu"]["sensor"]),
        "bateria": bool(hw["bateria"]),
    }


def _resumen(hw):
    o = overlay(hw)
    print()
    print("    EQUIPO  ·  %s   —   %s" % (hw["tipo"], hw["motivo_tipo"]))
    print()
    print("    CPU   %s" % (hw["cpu"]["nombre"] or "?"))
    print("          sensor de temperatura: %s" % (hw["cpu"]["sensor"] or "no encontrado"))
    for x in hw["gpus"] or [None]:
        if x is None:
            print("    GPU   ninguna que mirar")
            continue
        print("    GPU   %s  [%s, %s]" % (x["nombre"], "dedicada" if x["dedicada"] else "integrada", x["driver"]))
        print("          %s" % x["motivo"])
        print("          temperatura propia: %s   memoria propia: %s"
              % ("si" if x["temp"] else "no", "si" if x["vram"] else "no"))
    print("    BATERIA  %s" % ("si" if hw["bateria"] else "no"))
    print()
    print("    En la barra de FPS:  " + "  ".join(
        "%s %s" % ("✓" if v else "·", k) for k, v in o.items()))
    print()


def main(argv):
    hw = detectar()
    if "--json" in argv:
        print(json.dumps(dict(hw, overlay=overlay(hw)), ensure_ascii=False, indent=2))
    else:
        _resumen(hw)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
