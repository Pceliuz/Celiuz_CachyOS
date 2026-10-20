"""
remoto/servidor/celiuz_remoto/dispositivos.py — los telefonos emparejados.

Fase 1. Pendiente: aqui solo esta lo que tiene que hacer (ver remoto/DISEÑO.md
y remoto/PROTOCOLO.md).

- dispositivos.json (0600): id, nombre, sha256 de su clave, hash scrypt de su
  contraseña, permisos, pase_hasta, ultimo_latido, intentos fallidos.
- Revocar quita el telefono entero; «quitar el pase» solo vacia pase_hasta.
"""
