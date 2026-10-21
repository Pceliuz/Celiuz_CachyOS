// La paleta del escritorio para la app. Los valores salen de colores.json, que
// genera hypr/scripts/gen-colores.py: aqui no se escribe ningun hex a mano.
import datos from './colores.json';

export const colores = datos.colores;
export type Color = keyof typeof colores;
