// GENERADO POR hypr/scripts/gen-colores.py — NO EDITAR A MANO.
//
// La fuente de verdad es hypr/conf/colores.conf, la misma que usan
// Hyprland, hyprlock, la barra y las notificaciones. Si cambias un
// color ahi, vuelve a lanzar el generador y reinstala el tema con
//     ./instalar.sh --sddm
// porque el tema que se ve al arrancar es una COPIA en /usr/share.
//
// El alfa va DELANTE (#AARRGGBB): QML no usa el mismo orden que los
// .conf de hyprlang. Los colores opacos salen sin alfa a proposito.
import QtQuick

QtObject {
    readonly property color negro: "#000000"
    readonly property color abismo: "#0d0418"
    readonly property color superficie: "#1a0830"
    readonly property color apagado: "#2d1b4e"
    readonly property color violeta: "#6a00f4"
    readonly property color amatista: "#b16cff"
    readonly property color neon: "#c77dff"
    readonly property color luz: "#e4c7ff"
    readonly property color tenue: "#8a7aa8"
    readonly property color alerta: "#eb6f92"           // rojo  — algo va mal, mirame ya
    readonly property color atencion: "#f6c177"         // ambar — en marcha, espera
    readonly property color glow_activo: "#ccc77dff"
    readonly property color halo: "#aa6a00f4"
    readonly property color sombra: "#cc000000"
}
