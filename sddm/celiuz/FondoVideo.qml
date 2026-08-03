// sddm/celiuz/FondoVideo.qml — el fondo en movimiento, y NADA MAS.
//
// POR QUE ESTA SOLO EN SU FICHERO
// -------------------------------
// Es el unico sitio de todo el tema que hace `import QtMultimedia`, y eso es a
// proposito. Un import que falla en QML NO se salta: tumba el fichero ENTERO
// que lo pide. Si esta linea estuviera en Main.qml, un equipo sin
// qt6-multimedia se quedaria sin pantalla de inicio de sesion — pantalla negra,
// sin campo de contrasena y sin manera de entrar salvo por un TTY.
//
// Aislado aqui, lo peor que pasa es que el `Loader` de Main.qml se quede vacio
// y el fondo caiga al fotograma o al degradado. El que clone el repo entra
// igual, aunque no tenga el paquete.
//
// Por lo mismo no se da por hecho que el video exista: si el fichero no esta o
// el codec no se puede decodificar, `reproduciendo` se queda en false y esto no
// pinta nada. Nunca tapa a lo que hay debajo con un rectangulo negro.
import QtQuick
import QtMultimedia

Item {
    id: raiz

    // La ruta la pone Main.qml. Si esta vacia no se intenta nada.
    property url fuente: ""

    // Lo que mira Main.qml para saber si tapar el fotograma de reserva. Solo es
    // cierto cuando hay imagen de verdad en pantalla, no cuando "deberia".
    readonly property bool reproduciendo:
        reproductor.playbackState === MediaPlayer.PlayingState && !fallo

    property bool fallo: false

    VideoOutput {
        id: salida
        anchors.fill: parent
        // Igual que mpvpaper en el escritorio con --panscan=1.0: llena la
        // pantalla aunque la proporcion del video no sea la del monitor, antes
        // que dejar franjas negras arriba y abajo.
        fillMode: VideoOutput.PreserveAspectCrop
    }

    MediaPlayer {
        id: reproductor
        source: raiz.fuente
        videoOutput: salida
        loops: MediaPlayer.Infinite

        // Sin audioOutput no hay sonido. No se pone a proposito: un fondo que
        // suena en la pantalla de inicio de sesion es lo ultimo que quiere
        // nadie, y ademas el greeter corre como el usuario sddm, que no tiene
        // por que tener sesion de audio.

        onErrorOccurred: function(error, cadena) {
            // No hay a quien avisar —esto corre antes de que nadie entre—, asi
            // que el fallo se anota en el diario de sddm y se cae al fotograma.
            console.log("celiuz: no se pudo reproducir el fondo:", cadena)
            raiz.fallo = true
        }

        // El play va aqui y NO en Component.onCompleted. Main.qml carga esto con
        // un Loader asincrono y le pone la ruta en `onLoaded`, que ocurre DESPUES
        // de que el componente este completo: un play() al completarse llegaria
        // con `fuente` todavia vacia y no reproduciria nada. Se midio: el fichero
        // se abria (ffmpeg lo anunciaba en el diario) pero playbackState nunca
        // pasaba a Playing y el fondo se quedaba en el fotograma.
        onSourceChanged: if (source != "") play()
    }
}
