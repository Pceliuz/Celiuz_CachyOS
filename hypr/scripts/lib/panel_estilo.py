#!/usr/bin/env python3
"""
hypr/scripts/lib/panel_estilo.py — el aspecto comun de los paneles que cuelgan
de la barra (bluetooth-panel.py, wifi-panel.py): medidas y CSS.

Sin GTK a proposito: las pruebas comprueban el CSS sin pantalla, y lo que pide
GTK vive en lib/panel_capa.py.

El CSS sale ENTERO de la paleta que se le da (la de colores.conf, por
dibujo.C): ni un color escrito a mano, que es la trampa de los colores
copiados del CLAUDE.md. La unica excepcion es el negro de la sombra, que no es
de nadie.
"""

ALTO_BARRA = 38      # el de waybar/config.jsonc: el panel arranca justo debajo
ANCHO = 380
SOMBRA = 12          # margen transparente alrededor, para el halo
MARGEN_BORDE = 8
CIERRE_DELAY = 2.5   # segundos con el puntero lejos antes de cerrarse solo


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(int(round(c * 255)) for c in rgb)


def _rgba(rgb, a):
    return "rgba(%d, %d, %d, %.2f)" % (tuple(int(round(c * 255)) for c in rgb) + (a,))


def css_base(C, fuente):
    v = {k: _hex(c) for k, c in C.items()}
    return f"""
    window {{ background-color: transparent; }}
    * {{ font-family: "{fuente}"; color: {v['luz']}; }}
    #marco {{
        background-color: {_rgba(C['abismo'], .97)};
        border: 1px solid {v['amatista']};
        border-radius: 16px;
        box-shadow: 0 0 14px {_rgba(C['violeta'], .65)}, 0 8px 20px {_rgba((0, 0, 0), .7)};
        margin: {SOMBRA}px;
        padding: 14px;
    }}
    #titulo {{ font-size: 16px; font-weight: bold; }}
    #sub, .tenue {{ color: {v['tenue']}; font-size: 12px; }}
    #glifo-cab {{ font-size: 22px; color: {v['neon']}; }}
    #glifo-cab.apagado {{ color: {v['tenue']}; }}
    #raya {{ background-color: {v['apagado']}; min-height: 1px; }}
    .seccion {{ color: {v['tenue']}; font-size: 11px; letter-spacing: 1.5px; }}
    .buscando {{ color: {v['atencion']}; font-size: 11px; letter-spacing: 1px; }}
    .fila {{ border-radius: 10px; padding: 7px; }}
    .fila:hover {{ background-color: {_rgba(C['amatista'], .12)}; }}
    .fila.error {{ border: 1px solid {_rgba(C['alerta'], .5)}; }}
    .uso {{
        border-radius: 12px; padding: 11px;
        border: 1px solid {v['amatista']};
        background-image: linear-gradient(135deg, {_rgba(C['violeta'], .35)}, {_rgba(C['superficie'], .9)});
    }}
    .ico {{
        min-width: 40px; min-height: 40px; border-radius: 10px;
        background-color: {v['superficie']}; color: {v['neon']}; font-size: 21px;
    }}
    .uso .ico {{ background-color: {v['violeta']}; color: {v['luz']};
                 box-shadow: 0 0 10px {_rgba(C['neon'], .6)}; }}
    .cerca .ico {{ color: {v['atencion']}; }}
    .ico.lejos {{ color: {v['tenue']}; }}
    .candado {{ color: {v['tenue']}; font-size: 10px; margin: 0 4px 3px 0; }}
    .nombre {{ font-size: 14px; font-weight: bold; }}
    .detalle {{ color: {v['tenue']}; font-size: 12px; }}
    .dato {{ color: {v['tenue']}; font-size: 12px; }}
    .dato.valor {{ color: {v['luz']}; }}
    .etiqueta {{ font-size: 11px; color: {v['tenue']}; background-color: {v['apagado']};
                 border-radius: 6px; padding: 0 6px; }}
    .marca {{ font-size: 11px; color: {v['atencion']}; background-color: {_rgba(C['atencion'], .15)};
              border-radius: 6px; padding: 0 6px; }}
    .mejor {{ font-size: 11px; color: {v['neon']}; background-color: {_rgba(C['neon'], .15)};
              border-radius: 6px; padding: 0 6px; }}
    .pila {{ color: {v['tenue']}; font-size: 12px; }}
    .error-texto {{ color: {v['alerta']}; font-size: 12px; }}
    .mas-redes {{ color: {v['tenue']}; font-size: 12px; }}
    levelbar trough {{ min-height: 6px; border-radius: 3px; background-color: {v['apagado']};
                       border: none; padding: 0; }}
    levelbar block.filled {{ border-radius: 3px; border: none;
                             background-image: linear-gradient(90deg, {v['violeta']}, {v['neon']}); }}
    levelbar block.empty {{ background: none; border: none; }}
    button {{
        background-image: none; background-color: transparent; box-shadow: none;
        border: 1px solid {v['amatista']}; border-radius: 8px;
        padding: 3px 10px; min-height: 0; font-size: 12px; text-shadow: none;
    }}
    button:hover {{ background-color: {_rgba(C['amatista'], .18)}; }}
    button.lleno {{ background-color: {v['violeta']}; border-color: {v['neon']}; }}
    button.lleno:hover {{ background-color: {v['neon']}; }}
    button.suave {{ border-color: {v['apagado']}; }}
    button.suave label {{ color: {v['tenue']}; }}
    button.suave:hover label {{ color: {v['luz']}; }}
    button.peligro {{ border-color: {v['alerta']}; }}
    button.peligro label {{ color: {v['alerta']}; }}
    button.mas {{ border: none; padding: 2px 6px; }}
    button.mas label {{ color: {v['tenue']}; font-size: 15px; }}
    button.plano {{ border: none; padding: 2px 4px; }}
    button.plano label {{ color: {v['tenue']}; font-size: 12px; }}
    button:disabled {{ opacity: .45; }}
    entry {{
        background-image: none; background-color: {v['superficie']}; color: {v['luz']};
        border: 1px solid {v['amatista']}; border-radius: 8px; padding: 3px 8px;
        min-height: 0; box-shadow: none; caret-color: {v['neon']};
    }}
    entry.error {{ border-color: {v['alerta']}; }}
    entry selection {{ background-color: {v['violeta']}; color: {v['luz']}; }}
    entry image {{ color: {v['tenue']}; }}
    switch {{
        background-image: none; background-color: {v['apagado']}; border: none;
        border-radius: 12px; min-width: 40px; min-height: 22px; box-shadow: none;
    }}
    switch:checked {{ background-color: {v['violeta']};
                      box-shadow: 0 0 8px {_rgba(C['neon'], .55)}; }}
    switch slider {{
        background-image: none; background-color: {v['tenue']}; border: none;
        border-radius: 50%; min-width: 16px; min-height: 16px; margin: 3px; box-shadow: none;
    }}
    switch:checked slider {{ background-color: {v['luz']}; }}
    /* La «I» y la «O» del interruptor son iconos que el tema esconde con
     * color transparente; el `*` de arriba se lo devolvia. */
    switch image {{ color: transparent; }}
    scrollbar {{ background: none; border: none; }}
    scrollbar slider {{ background-color: {v['apagado']}; border: none;
                        min-width: 4px; border-radius: 2px; }}
    scrollbar slider:hover {{ background-color: {v['tenue']}; }}
    #qr {{ background-color: {v['luz']}; border-radius: 8px; padding: 6px; }}
    #opcion {{ font-size: 13px; }}
    #estado {{ font-size: 12px; color: {v['atencion']}; }}
    #estado.error {{ color: {v['alerta']}; }}
    #vacio {{ color: {v['tenue']}; font-size: 12px; padding: 4px 2px; }}
    """
