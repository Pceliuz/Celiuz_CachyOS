import subprocess

r = subprocess.run(["bash", "tests/unidad/grabar.sh"], capture_output=True, text=True, timeout=180)
print("=== CODIGO:", r.returncode)
print("=== STDOUT ===")
print(r.stdout)
print("=== STDERR ===")
print(r.stderr)
