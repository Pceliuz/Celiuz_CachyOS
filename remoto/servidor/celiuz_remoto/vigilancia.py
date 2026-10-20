"""
remoto/servidor/celiuz_remoto/vigilancia.py — el interruptor por silencio del celular.

Fase 2. Pendiente: aqui solo esta lo que tiene que hacer (ver remoto/DISEÑO.md
y remoto/PROTOCOLO.md).

- Cada latido reinicia la cuenta atras: 2 h, o 1 h si llego «me estan apagando».
- Al llegar a cero, pregunta a presencia.py: con alguien delante no apaga y
  notifica; sin nadie, apaga.
- Varios telefonos: al que calla se le quita el pase; si callan todos, apaga.
"""
