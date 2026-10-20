"""
remoto/servidor/celiuz_remoto/sesion.py — entrar: reto, firma, contraseña y token que caduca.

Fase 1. Pendiente: aqui solo esta lo que tiene que hacer (ver remoto/DISEÑO.md
y remoto/PROTOCOLO.md).

- El telefono firma un reto con su clave (HMAC-SHA256): la clave no viaja.
- La contraseña se compara contra su hash scrypt (hmac.compare_digest).
- Al 5.o fallo el telefono queda bloqueado y se notifica en la PC.
- El token caduca tras 5 min sin uso.
"""
