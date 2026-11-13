import subprocess, re, sys

# Solo lectura: saca del diario del kernel las marcas PM: para ver la forma
# exacta de las entradas y salidas de suspender/hibernar (no suponerlas).
for boot in ('0', '-1', '-2'):
    r = subprocess.run(['journalctl', '-b', boot, '-k', '--no-pager'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        continue
    print(f'=== arranque {boot} ===')
    for linea in r.stdout.splitlines():
        if 'PM:' in linea and ('entry' in linea or 'exit' in linea or 'restore' in linea
                               or 'hibernat' in linea):
            print(linea)
