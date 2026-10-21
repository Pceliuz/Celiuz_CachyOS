"""
remoto/servidor/celiuz_remoto/estado.py — el estado en tiempo real.

- Pregunta a lib/hardware.py y lib/sensores.py que tiene ESTE equipo, y solo
  manda eso (sin sensor no hay temp; sin GPU dedicada no hay VRAM; sin bateria,
  bateria = null). Se pregunta al arrancar el servicio y no en cada segundo:
  una tarjeta grafica no se cambia con la PC encendida.
- CPU, RAM, disco y red con psutil. Cada segundo por el WebSocket /v0/vivo.

LA GPU, con cuidado, porque medirla puede costar mas que lo que mide:
  - NVIDIA por NVML (la libreria del driver, por ctypes), nunca lanzando
    nvidia-smi una vez por segundo.
  - En un equipo HIBRIDO (dos GPUs: la integrada pinta y la dedicada duerme
    hasta que un juego la pide), la dedicada con la gestion de energia
    dinamica puesta (power/control = auto) NO se mide: cada lectura la
    despertaria o le impediria dormirse, y eso es la bateria del portatil.
    Sale solo «dormida» o no. Con una sola GPU no hace falta el cuidado (es la
    que pinta, esta despierta siempre): la RTX 3050 de la PC tiene tambien
    control = auto, y con la regla sin «hibrido» salia sin numeros.
  - AMD por sysfs (gpu_busy_percent, mem_info_vram_*). Intel integrada: solo el
    nombre (su uso no esta en sysfs).
"""

import ctypes
import datetime as dt
import glob
import os
import time

import psutil

import hardware  # noqa: E402  (hypr/scripts/lib, lo pone en el path __init__)
import sensores  # noqa: E402

GIB = 1024 ** 3
PCI = "/sys/bus/pci/devices"
# Interfaces que no son trafico de verdad, o que lo cuentan dos veces (lo de
# Tailscale ya pasa por la tarjeta fisica).
NO_ES_RED = ("lo", "tailscale", "docker", "veth", "virbr", "br-")


def _leer(ruta):
    try:
        with open(ruta, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return None


def _entero(ruta):
    v = _leer(ruta)
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _gb(bytes_):
    return round(bytes_ / GIB, 1)


# --- NVML -----------------------------------------------------------------

class _Util(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


class _Mem(ctypes.Structure):
    _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong),
                ("used", ctypes.c_ulonglong)]


class Nvml:
    """Lo minimo de NVML. Si la libreria no esta o no arranca, `ok` es False y
    la GPU sale sin numeros: no es un error del servicio."""

    def __init__(self):
        self.ok = False
        self.lib = None
        try:
            self.lib = ctypes.CDLL("libnvidia-ml.so.1")
            self.ok = self.lib.nvmlInit_v2() == 0
        except (OSError, AttributeError):
            self.ok = False

    def medir(self, pci):
        if not self.ok:
            return {}
        disp = ctypes.c_void_p()
        if self.lib.nvmlDeviceGetHandleByPciBusId_v2(pci.encode(), ctypes.byref(disp)) != 0:
            return {}
        salida = {}
        u = _Util()
        if self.lib.nvmlDeviceGetUtilizationRates(disp, ctypes.byref(u)) == 0:
            salida["uso"] = int(u.gpu)
        t = ctypes.c_uint()
        if self.lib.nvmlDeviceGetTemperature(disp, 0, ctypes.byref(t)) == 0:
            salida["temp"] = int(t.value)
        m = _Mem()
        if self.lib.nvmlDeviceGetMemoryInfo(disp, ctypes.byref(m)) == 0 and m.total:
            salida["vram"] = [_gb(m.used), _gb(m.total)]
        return salida

    def cerrar(self):
        if self.ok:
            self.lib.nvmlShutdown()
            self.ok = False


# --- el equipo --------------------------------------------------------------

def _nombre_corto(nombre):
    for basura in ("NVIDIA GeForce ", "NVIDIA ", "AMD Radeon ", "Advanced Micro Devices, Inc. "):
        if nombre.startswith(basura):
            return nombre[len(basura):]
    return nombre


def _energia_dinamica(pci, pci_raiz=PCI):
    return _leer(os.path.join(pci_raiz, pci, "power", "control")) == "auto"


def _despierta(pci, pci_raiz=PCI):
    return _leer(os.path.join(pci_raiz, pci, "power", "runtime_status")) == "active"


class Muestreador:
    def __init__(self, hw=None, nvml=None, pci_raiz=PCI, casa=None):
        self.hw = hw if hw is not None else hardware.detectar()
        self.pci_raiz = pci_raiz
        self.casa = casa or os.path.expanduser("~")
        self.sensor_cpu = sensores.cpu()
        self.hibrido = len(self.hw["gpus"]) > 1
        hay_nvidia = any(g["fabricante"] == "NVIDIA" for g in self.hw["gpus"])
        # En un hibrido NVML no se arranca nunca: abrirla ya despierta la tarjeta.
        self.nvml = nvml if nvml is not None else (
            Nvml() if hay_nvidia and not self.hibrido else None)
        self._red_antes = None
        psutil.cpu_percent(interval=None)   # la primera lectura siempre da 0

    def equipo(self):
        return {
            "nombre": os.uname().nodename,
            "tipo": self.hw["tipo"],
            "cpu": self.hw["cpu"]["nombre"],
            "gpus": [g["nombre"] for g in self.hw["gpus"]],
            "ram": _gb(psutil.virtual_memory().total),
            "bateria": bool(self.hw["bateria"]),
        }

    def _temp_cpu(self):
        s = self.sensor_cpu
        if not s:
            return None
        for ruta in glob.glob(os.path.join(s["ruta"], "hwmon*", s["entrada"])):
            v = _entero(ruta)
            if v is not None:
                return round(v / 1000)
        return None

    def _gpu(self, g):
        salida = {"nombre": _nombre_corto(g["nombre"])}
        pci = g["pci"]
        if self.hibrido and g["dedicada"] and _energia_dinamica(pci, self.pci_raiz):
            # Ver la cabecera: medirla seria despertarla.
            salida["dormida"] = not _despierta(pci, self.pci_raiz)
            return salida
        if g["fabricante"] == "NVIDIA" and self.nvml is not None:
            salida.update(self.nvml.medir(pci))
        elif g["fabricante"] == "AMD":
            disp = os.path.join(self.pci_raiz, pci)
            uso = _entero(os.path.join(disp, "gpu_busy_percent"))
            if uso is not None:
                salida["uso"] = uso
            if g["temp"]:
                for ruta in sorted(glob.glob(os.path.join(disp, "hwmon", "hwmon*", "temp1_input"))):
                    v = _entero(ruta)
                    if v is not None:
                        salida["temp"] = round(v / 1000)
                        break
            if g["vram"]:
                usada = _entero(os.path.join(disp, "mem_info_vram_used"))
                total = _entero(os.path.join(disp, "mem_info_vram_total"))
                if usada is not None and total:
                    salida["vram"] = [_gb(usada), _gb(total)]
        return salida

    def _red(self):
        ahora = psutil.net_io_counters(pernic=True)
        t = time.monotonic()
        baj = sub = 0
        for nombre, c in ahora.items():
            if nombre.startswith(NO_ES_RED):
                continue
            baj += c.bytes_recv
            sub += c.bytes_sent
        antes, self._red_antes = self._red_antes, (t, baj, sub)
        if antes is None or t <= antes[0]:
            return {"bajada": 0, "subida": 0}
        dt_ = t - antes[0]
        return {"bajada": max(0, int((baj - antes[1]) / dt_)),
                "subida": max(0, int((sub - antes[2]) / dt_))}

    def _bateria(self):
        if not self.hw["bateria"]:
            return None
        b = psutil.sensors_battery()
        if b is None:
            return None
        return {"nivel": round(b.percent), "cargando": bool(b.power_plugged)}

    def tomar(self):
        mem = psutil.virtual_memory()
        disco = psutil.disk_usage(self.casa)
        cpu = {"uso": round(psutil.cpu_percent(interval=None))}
        temp = self._temp_cpu()
        if temp is not None:
            cpu["temp"] = temp
        return {
            "cpu": cpu,
            "gpu": [self._gpu(g) for g in self.hw["gpus"]],
            "ram": [_gb(mem.total - mem.available), _gb(mem.total)],
            "disco": [round(disco.used / GIB), round(disco.total / GIB)],
            "red": self._red(),
            "bateria": self._bateria(),
            "encendida_desde": dt.datetime.fromtimestamp(psutil.boot_time()).astimezone()
                                 .isoformat(timespec="seconds"),
        }

    def cerrar(self):
        if self.nvml is not None:
            self.nvml.cerrar()
