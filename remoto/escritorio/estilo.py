"""
remoto/escritorio/estilo.py — el CSS de la ventana de Celiuz Remoto.

Sin GTK, como lib/panel_estilo.py, para que las pruebas lo miren sin pantalla.
Sale ENTERO de la paleta que se le da (la de colores.conf, por dibujo.C): ni
un color escrito a mano. Las medidas y la disposicion son las de la maqueta de
la pantalla 9 (https://claude.ai/artifact/BGqHdnHe5W2Xu7LNuVwYUd).

El verde de «hecho» de la maqueta no esta en la paleta del escritorio; se
toma dibujo.VERDE, que es el que ya usan las otras pantallas para lo mismo.
"""


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(int(round(c * 255)) for c in rgb)


def _rgba(rgb, a):
    return "rgba(%d, %d, %d, %.2f)" % (tuple(int(round(c * 255)) for c in rgb) + (a,))


def css(C, fuente, verde):
    v = {k: _hex(c) for k, c in C.items()}
    vd = _hex(verde)
    return f"""
    * {{ font-family: "{fuente}"; color: {v['luz']}; }}
    window, #fondo {{ background-color: {v['abismo']}; }}
    #nav {{ background-color: {_rgba(C['superficie'], .55)};
            border-right: 1px solid {v['apagado']}; padding: 24px 14px; }}
    #marca {{ font-size: 18px; font-weight: bold; padding: 0 10px 18px 10px; }}
    .pestana {{ background-image: none; background-color: transparent; border: none;
                box-shadow: none; border-radius: 10px; min-height: 44px; padding: 0 12px; }}
    .pestana label {{ color: {v['tenue']}; font-size: 14px; }}
    .pestana:hover {{ background-color: {_rgba(C['amatista'], .10)}; }}
    .pestana.activa {{ background-color: {v['apagado']}; }}
    .pestana.activa label {{ color: {v['luz']}; font-weight: bold; }}
    .tarjeta {{ background-color: {v['superficie']}; border: 1px solid {v['apagado']};
                border-radius: 16px; padding: 18px 20px; }}
    .tarjeta.chica {{ border-radius: 14px; padding: 14px 16px; }}
    .tarjeta.robo {{ background-color: {_rgba(C['alerta'], .08)};
                       border-color: {_rgba(C['alerta'], .45)}; }}
    #servicio {{ border-radius: 12px; padding: 12px; }}
    h1, .h1 {{ font-size: 22px; font-weight: bold; }}
    .h2 {{ font-size: 16px; font-weight: bold; }}
    .tenue {{ color: {v['tenue']}; font-size: 14px; }}
    .chico {{ font-size: 12px; }}
    .tenue.chico {{ font-size: 12px; }}
    .mono {{ font-family: monospace; }}
    .fuerte {{ font-weight: bold; }}
    .ok {{ color: {vd}; }}
    .atencion {{ color: {v['atencion']}; }}
    .rojo {{ color: {v['alerta']}; }}
    .alerta-titulo {{ color: {v['luz']}; font-weight: bold; font-size: 14px; }}
    .paso {{ min-width: 26px; min-height: 26px; border-radius: 13px;
             background-color: {v['apagado']}; font-size: 13px; font-weight: bold; }}
    .paso.hecho {{ background-color: {_rgba(verde, .16)}; color: {vd}; }}
    .paso.falta {{ background-color: {_rgba(C['atencion'], .16)}; color: {v['atencion']}; }}
    .paso-texto {{ font-size: 14px; }}
    .paso-texto.actual {{ font-weight: bold; }}
    label.etiqueta {{ font-size: 12px; color: {v['tenue']}; }}
    entry {{ background-image: none; background-color: {v['abismo']}; color: {v['luz']};
             border: 1px solid {v['apagado']}; border-radius: 10px; min-height: 44px;
             padding: 0 12px; box-shadow: none; caret-color: {v['neon']}; }}
    entry:focus {{ border-color: {v['amatista']}; }}
    entry.error {{ border-color: {v['alerta']}; }}
    entry selection {{ background-color: {v['violeta']}; color: {v['luz']}; }}
    checkbutton label {{ font-size: 14px; }}
    checkbutton check {{ background-image: none; background-color: {v['abismo']};
                         border: 1px solid {v['amatista']}; border-radius: 5px;
                         min-width: 18px; min-height: 18px; }}
    checkbutton check:checked {{ background-color: {v['violeta']}; color: {v['luz']}; }}
    button {{ background-image: none; background-color: transparent; box-shadow: none;
              text-shadow: none; border: 1px solid {v['apagado']}; border-radius: 14px;
              min-height: 0; padding: 0 20px; }}
    button label {{ font-size: 14px; font-weight: bold; }}
    button:hover {{ background-color: {_rgba(C['amatista'], .12)}; }}
    button.grande {{ min-height: 50px; }}
    button.lleno {{ background-color: {v['amatista']}; border-color: {v['amatista']}; }}
    button.lleno label {{ color: {v['abismo']}; }}
    button.lleno:hover {{ background-color: {v['neon']}; }}
    button.peligro {{ border-color: {_rgba(C['alerta'], .5)}; border-radius: 9px;
                      min-height: 34px; padding: 0 12px; }}
    button.peligro label {{ color: {v['alerta']}; font-size: 12px; }}
    button.peligro:hover {{ background-color: {_rgba(C['alerta'], .12)}; }}
    button.discreto {{ border-radius: 9px; min-height: 34px; padding: 0 12px; }}
    button.discreto label {{ font-size: 12px; }}
    button:disabled {{ opacity: .4; }}
    switch {{ background-image: none; background-color: {v['apagado']}; border: none;
              border-radius: 13px; min-width: 46px; min-height: 26px; box-shadow: none; }}
    switch:checked {{ background-color: {v['violeta']}; box-shadow: 0 0 8px {_rgba(C['neon'], .55)}; }}
    switch slider {{ background-image: none; background-color: {v['tenue']}; border: none;
                     border-radius: 50%; min-width: 20px; min-height: 20px; margin: 3px; box-shadow: none; }}
    switch:checked slider {{ background-color: {v['luz']}; }}
    /* La «I» y la «O» del interruptor son iconos que el tema esconde con color
     * transparente; el `*` de arriba se lo devolvia (trampa del CLAUDE.md). */
    switch image {{ color: transparent; }}
    combobox button {{ border-radius: 10px; min-height: 36px; padding: 0 10px; }}
    levelbar trough {{ min-height: 5px; border-radius: 3px; background-color: {v['apagado']};
                       border: none; padding: 0; }}
    levelbar block.filled {{ border-radius: 3px; border: none; background-color: {v['amatista']}; }}
    levelbar block.filled.bajo {{ background-color: {v['atencion']}; }}
    levelbar block.empty {{ background: none; border: none; }}
    #estado-op {{ font-size: 13px; color: {v['atencion']}; }}
    #estado-op.error {{ color: {v['alerta']}; }}
    #estado-op.ok {{ color: {vd}; }}
    .registro-hora {{ color: {v['tenue']}; font-size: 12px; font-family: monospace; }}
    .registro-texto {{ font-size: 13px; }}
    list, row {{ background-color: transparent; }}
    row {{ padding: 6px 4px; border-bottom: 1px solid {_rgba(C['apagado'], .6)}; }}
    scrollbar {{ background: none; border: none; }}
    scrollbar slider {{ background-color: {v['apagado']}; border: none; min-width: 4px;
                        border-radius: 2px; }}
    button.link {{ border: none; padding: 0; min-height: 0; }}
    button.link label, link, .enlace {{ color: {v['neon']}; font-weight: normal; }}
    """
