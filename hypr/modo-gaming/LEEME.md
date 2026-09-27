# Videos del modo gaming

Pon aquí los tuyos y el modo gaming los usa solo, sin configurar nada:

- `inicio.mp4` (o `.webm`, `.mkv`, `.mov`): suena al entrar, y detrás se prepara todo.
- `final.mp4`: suena al salir, y detrás vuelve cada ventana a su sitio.

Se saltan con Enter, Esc, espacio, un clic o A / Start en el mando.

Esta carpeta **no se versiona** (mira su `.gitignore`): un vídeo bajado de
internet casi nunca se puede redistribuir, y el repo es público. Si prefieres
tenerlos en otro sitio, apúntalos en `~/.config/celiuz/modo-gaming.json`:

```json
{ "video_entrada": "~/Vídeos/inicio.mp4", "video_salida": "~/Vídeos/final.mp4" }
```
