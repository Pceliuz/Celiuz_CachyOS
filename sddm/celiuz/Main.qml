// sddm/celiuz/Main.qml — la pantalla de inicio de sesion.
//
// Es la hermana de hypr/hyprlock.conf y COPIA SU DISENO: una columna pegada al
// borde izquierdo sobre una banda oscura, con el filo amatista marcando su
// canto. Ya no hay tarjeta flotante en el centro — la tuvo, igual que el
// bloqueo, y se quito por lo mismo: la tarjeta se plantaba justo encima del
// personaje del fondo y no dejaba verlo. Asi el fondo se ve entero.
//
// LAS MEDIDAS SON LAS MISMAS, y a proposito. Los numeros de aqui abajo salen de
// hypr/scripts/lib/pantalla.py (`medidas()`, las claves `lock_*`), pensados para
// 1920x1080 y traidos a esta pantalla por el mismo factor. Si cambias la
// proporcion de una de las dos pantallas, la otra se queda desparejada — y no
// falla nada, que es como se separan siempre estas dos.
//
// La diferencia con hyprlock es lo que esta pantalla tiene que hacer de mas:
// dejarte ELEGIR (cuenta, sesion, teclado, apagar) y funcionar ANTES de que
// exista tu sesion. Nada de eso tiene sitio en el bloqueo, asi que se coloca
// donde no estorbe: lo de entrar vive en la banda, y los botones de apagado se
// van abajo a la derecha, lejos del campo de la contrasena.
//
// LO QUE MANDA AQUI: el greeter corre como el usuario `sddm`, no como tu.
// No puede entrar en /home/tu-usuario (esta a 700), asi que ni el video ni la
// paleta se leen de tu carpeta: son una COPIA en /usr/share/sddm/themes/celiuz
// que deja `./instalar.sh --sddm`. Por eso el fondo del arranque no cambia solo
// cuando cambias el del escritorio.
//
// NADA CABLEADO. Ni tu usuario, ni la sesion, ni el idioma, ni el tamano de la
// pantalla: todo sale de los modelos que da SDDM o se mide en caliente. Este
// repo es publico y esta pantalla es la que mas caro sale si falla en el equipo
// de otro: un tema roto deja a la persona fuera de su propio sistema.
//
// Todo lo que se ve se degrada solo:
//   sin video      -> fotograma quieto
//   sin fotograma  -> degradado de la paleta, que no depende de ningun fichero
//   sin una cuenta -> un campo para escribir el nombre, en el hueco del usuario
//   sin permiso para apagar -> el boton no aparece, en vez de fallar al pulsarlo
import QtQuick

Rectangle {
    id: raiz
    color: paleta.negro

    // La paleta, generada desde hypr/conf/colores.conf por gen-colores.py.
    Colores { id: paleta }

    // --- Escala ---------------------------------------------------------------
    // EL MISMO CRITERIO QUE hypr/scripts/lib/pantalla.py, hasta en los topes:
    // todo esta pensado para 1920x1080, se toma el MENOR de los dos lados (si se
    // tomara el ancho, una pantalla apaisada de portatil dejaria el bloque mas
    // alto que el hueco) y se sujeta entre 0.62 y 2.20. El suelo existe para que
    // el reloj no quede ilegible en una pantalla pequena.
    //
    // La ventaja sobre el bloqueo es que aqui no hay que generar nada: QML sabe
    // el tamano de la pantalla y se reajusta solo al cambiar de monitor.
    readonly property real f: Math.max(0.62, Math.min(2.20,
        Math.min(width / 1920, height / 1080)))

    // px() para TAMANOS y pxs() para DESPLAZAMIENTOS. No es lo mismo y confundirlos
    // se ve raro sin dar ningun error: px() tiene un suelo de 1 —un ancho de cero
    // es un elemento invisible—, y ese mismo suelo aplicado a un desplazamiento
    // NEGATIVO lo convierte en +1, o sea que manda hacia arriba lo que tenia que
    // ir hacia abajo. La mitad de las posiciones de esta pantalla son negativas.
    function px(v)  { return Math.max(1, Math.round(v * raiz.f)) }
    function pxs(v) { return Math.round(v * raiz.f) }

    // --- Las medidas de la columna, las mismas que las del bloqueo -------------
    // El tope del 42% no es adorno, y viene medido en el bloqueo: como el factor
    // tiene suelo, en una pantalla estrecha px(660) devuelve mas de lo que cabe y
    // la banda se come la pantalla entera. En 1366 y en 1920 no cambia nada.
    readonly property int bandaW: Math.min(px(660), Math.floor(width * 0.42))
    readonly property int colX:   px(92)
    // El ancho del campo, sujeto para que no se salga de la banda. En las
    // pantallas de verdad manda px(420) y esto no hace nada; en una diminuta
    // evita que el campo asome por el filo.
    readonly property int campoW: Math.min(px(420), bandaW - 2 * colX)
    readonly property int campoH: px(56)
    readonly property int redondeo: Math.max(8, px(14))

    // Las `_y` son desplazamientos desde el CENTRO vertical, y —como en
    // hyprlock— el POSITIVO va hacia ARRIBA. QML crece hacia abajo, asi que la
    // conversion se hace en un solo sitio: `centro()`.
    function centro(desp, alto) { return height / 2 - pxs(desp) - alto / 2 }

    // --- Ajustes de theme.conf ------------------------------------------------
    // config.loQueSea devuelve "" cuando la clave no esta, asi que cada uno lleva
    // su valor por defecto detras. El que clone el repo cambia el titulo por el
    // suyo sin tocar una linea de QML.
    readonly property string titulo:      config.titulo      || "彼岸花"
    readonly property string fuente:      config.fuente      || "MesloLGS Nerd Font"
    readonly property string fuenteTit:   config.fuenteTitulo || "Noto Sans CJK TC"
    readonly property real   veloAlfa:    parseFloat(config.veloOpacidad || "0.30")
    readonly property bool   cuentasFijas: (config.mostrarCuentasSiempre || "false") === "true"

    // El formato de la fecha. Los NOMBRES de dia y mes salen en el idioma del
    // sistema; lo unico escrito aqui es el "de" que los une, y por eso se puede
    // cambiar: en un equipo en ingles "Monday · 03 de August" no tiene sentido.
    readonly property string formatoFecha: config.formatoFecha || "dddd · dd 'de' MMMM"

    // --- Estado ---------------------------------------------------------------
    property string usuario: userModel.lastUser || ""
    property int    sesion:  sessionModel.lastIndex
    property bool   comprobando: false
    property string mensaje: ""

    // `count` no lo expone cualquier modelo; si faltara, se asume una sola.
    readonly property int nCuentas:  userModel.count    !== undefined ? userModel.count    : 1
    readonly property int nSesiones: sessionModel.count !== undefined ? sessionModel.count : 1

    // La lista de cuentas solo estorba cuando hay una. Se ensena si hay mas de
    // una o si en theme.conf pediste verla siempre.
    readonly property bool verCuentas: cuentasFijas || nCuentas > 1

    // =========================================================================
    //  EL FONDO, en tres escalones de menos a mas exigente
    // =========================================================================

    // 1. El suelo. No depende de NINGUN fichero: aunque el equipo no tenga
    //    video, ni imagen, ni el paquete de multimedia, esto siempre se dibuja.
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: paleta.abismo }
            GradientStop { position: 1.0; color: paleta.negro }
        }
    }

    // 2. El fotograma. `visible` mira el estado real de la carga: si el fichero
    //    no esta, Image se queda en Error y esto no tapa al degradado.
    Image {
        id: imagenFondo
        anchors.fill: parent
        source: "fondo.jpg"
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        cache: false
        visible: status === Image.Ready
    }

    // 3. El video. Va por Loader a proposito: asi un fallo al cargarlo —o la
    //    falta de qt6-multimedia, que tumbaria el fichero entero que lo importa—
    //    se queda en este rincon en vez de dejar la pantalla sin dibujar.
    Loader {
        id: cargaVideo
        anchors.fill: parent
        source: "FondoVideo.qml"
        asynchronous: true
        onStatusChanged: if (status === Loader.Error)
            console.log("celiuz: sin soporte de video (falta qt6-multimedia?); "
                        + "se usa el fotograma")
        onLoaded: item.fuente = "fondo.mp4"
        visible: status === Loader.Ready && item && item.reproduciendo
    }

    // El velo, el mismo que en hyprlock (`$abismo` al 30%): sin el, un fondo
    // claro se come el texto. Va en un rectangulo aparte y no como opacidad de la
    // banda porque `opacity` en QML se hereda a los hijos, y atenuaria tambien el
    // reloj.
    Rectangle {
        anchors.fill: parent
        color: paleta.abismo
        opacity: raiz.veloAlfa
    }

    // =========================================================================
    //  LA BANDA DE LA IZQUIERDA
    // =========================================================================
    // El fondo de toda la columna. `$abismo` al 55%, esquina viva y alto
    // completo, igual que el `shape` del bloqueo.
    Rectangle {
        id: banda
        x: 0; y: 0
        width: raiz.bandaW
        height: parent.height
        color: Qt.rgba(paleta.abismo.r, paleta.abismo.g, paleta.abismo.b, 0.55)
    }

    // El filo amatista del canto derecho. Son 2 pixeles SIN escalar, igual que en
    // hyprlock (alli el `shape` lleva un `size = 2, 100%` literal): un filo de un
    // pixel desaparece y uno escalado a 4K se convierte en una franja.
    Rectangle {
        x: banda.width - 2
        y: 0
        width: 2
        height: parent.height
        color: Qt.rgba(paleta.amatista.r, paleta.amatista.g, paleta.amatista.b, 0.30)
    }

    // =========================================================================
    //  EL EQUIPO, arriba del todo dentro de la banda
    // =========================================================================
    Text {
        x: raiz.colX
        y: raiz.px(40)
        text: sddm.hostName
        color: paleta.tenue
        font.family: raiz.fuente
        font.pixelSize: raiz.px(13)
    }

    // =========================================================================
    //  LA COLUMNA — cada pieza en el mismo sitio que en el bloqueo
    // =========================================================================
    // El titulo y el usuario van CENTRADOS EN LA BANDA; el resto alineado a la
    // izquierda, en el margen `colX`. Es exactamente el reparto de hyprlock, solo
    // que aqui centrar es `banda.width / 2` y no hace falta el desplazamiento
    // negativo que allí calcula pantalla.py (`lock_col_centro`): eso existe
    // porque hyprlang centra en la PANTALLA y luego suma, y QML no tiene esa
    // limitacion.

    // --- El titulo, en +215 ---------------------------------------------------
    // 彼岸花 (higanbana) sale de theme.conf, asi que quien clone el repo pone el
    // suyo sin tocar QML. La fuente cae en Noto Sans CJK para los kanji.
    Item {
        x: 0
        width: banda.width
        y: raiz.centro(215, height)
        height: tituloTxt.height

        // La sombra del bloqueo (`shadow_passes`) no tiene equivalente en QML sin
        // QtQuick.Effects, y ese modulo es otra dependencia que puede faltar — por
        // un relieve no se arriesga la pantalla entera. Se imita con una copia
        // detras, desplazada y en el color de sombra de la paleta.
        Text {
            anchors.centerIn: parent
            anchors.horizontalCenterOffset: raiz.px(2)
            anchors.verticalCenterOffset: raiz.px(2)
            text: raiz.titulo
            color: paleta.abismo
            opacity: 0.8
            font.family: raiz.fuenteTit
            font.pixelSize: raiz.px(50)
        }

        Text {
            id: tituloTxt
            anchors.centerIn: parent
            text: raiz.titulo
            color: paleta.amatista
            font.family: raiz.fuenteTit
            font.pixelSize: raiz.px(50)
        }
    }

    // --- El usuario, en +150 --------------------------------------------------
    // Este hueco tiene tres caras, y son excluyentes:
    //   una cuenta   -> su nombre, centrado en la banda (como el $USER del bloqueo)
    //   varias       -> la lista, para elegir
    //   ninguna      -> un campo para escribirlo, porque si no la pantalla seria
    //                   un callejon sin salida: pediria la contrasena de un
    //                   usuario vacio y no dejaria entrar nunca, sin decir por que.
    Item {
        x: 0
        width: banda.width
        y: raiz.centro(150, height)
        height: raiz.px(46)

        // Una sola cuenta: solo el nombre.
        Text {
            anchors.centerIn: parent
            visible: !raiz.verCuentas && raiz.nCuentas > 0
            text: raiz.usuario
            color: paleta.tenue
            font.family: raiz.fuente
            font.bold: true
            font.pixelSize: raiz.px(21)
        }

        // Varias: la lista de nombres. Se usa un Repeater sobre el modelo en vez
        // de sacar los nombres a una lista propia: los roles de un modelo de SDDM
        // solo se leen DENTRO del delegado, y dar la vuelta a eso con Instantiator
        // seria maquinaria de mas para tres nombres.
        Flow {
            anchors.centerIn: parent
            visible: raiz.verCuentas
            width: banda.width - 2 * raiz.colX
            spacing: raiz.px(14)

            Repeater {
                model: userModel
                delegate: Text {
                    readonly property bool elegido: model.name === raiz.usuario
                    text: model.realName || model.name
                    color: elegido ? paleta.luz : paleta.tenue
                    font.family: raiz.fuente
                    font.bold: elegido
                    font.pixelSize: raiz.px(17)

                    // SDDM solo recuerda la ultima cuenta que entro, y en un
                    // equipo recien instalado no ha entrado ninguna:
                    // `userModel.lastUser` viene vacio. Sin esto, la primera vez
                    // la pantalla pediria la contrasena de nadie y no dejaria
                    // pasar. El primer delegado que se crea rellena el hueco.
                    Component.onCompleted:
                        if (raiz.usuario === "") raiz.usuario = model.name

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            raiz.usuario = model.name
                            raiz.mensaje = ""
                            campo.text = ""
                            campo.forceActiveFocus()
                        }
                    }
                }
            }
        }

        // Ninguna: se escribe a mano. Alineado a la izquierda y del ancho del
        // campo de la contrasena, para que los dos formen una sola columna.
        Rectangle {
            visible: raiz.nCuentas === 0
            x: raiz.colX
            anchors.verticalCenter: parent.verticalCenter
            width: raiz.campoW
            height: raiz.px(46)
            radius: raiz.redondeo
            color: Qt.rgba(paleta.superficie.r, paleta.superficie.g,
                           paleta.superficie.b, 0.86)
            border.width: 2
            border.color: paleta.apagado

            TextInput {
                id: campoUsuario
                anchors.fill: parent
                anchors.leftMargin: raiz.px(18)
                anchors.rightMargin: raiz.px(18)
                verticalAlignment: TextInput.AlignVCenter
                horizontalAlignment: TextInput.AlignHCenter
                color: paleta.luz
                font.family: raiz.fuente
                font.pixelSize: raiz.px(15)
                selectByMouse: true

                onTextChanged: raiz.usuario = text
                onAccepted: campo.forceActiveFocus()

                Text {
                    anchors.centerIn: parent
                    visible: campoUsuario.text.length === 0
                    text: "usuario"
                    color: paleta.tenue
                    font.family: raiz.fuente
                    font.pixelSize: raiz.px(15)
                }
            }
        }
    }

    // --- El reloj, en +34 -----------------------------------------------------
    // Lo que se lee de lejos, y por eso es lo mas grande de la pantalla.
    Item {
        x: raiz.colX
        y: raiz.centro(34, height)
        width: banda.width - raiz.colX
        height: reloj.height

        Text {
            x: raiz.px(2); y: raiz.px(2)
            text: reloj.text
            color: paleta.abismo
            opacity: 0.8
            font.family: raiz.fuente
            font.bold: true
            font.pixelSize: raiz.px(110)
        }

        Text {
            id: reloj
            color: paleta.luz
            font.family: raiz.fuente
            font.bold: true
            font.pixelSize: raiz.px(110)
        }
    }

    // --- La fecha, en -72 -----------------------------------------------------
    // En el idioma DEL SISTEMA. Ni una palabra va escrita aqui: ver refrescarHora().
    Text {
        id: fecha
        x: raiz.colX
        y: raiz.centro(-72, height)
        color: paleta.tenue
        font.family: raiz.fuente
        font.pixelSize: raiz.px(18)
    }

    // --- La contrasena, en -157 -----------------------------------------------
    // El borde es el que avisa, igual que en el bloqueo: amatista en reposo,
    // ambar mientras comprueba, rojo si fallas.
    Rectangle {
        id: caja
        x: raiz.colX
        y: raiz.centro(-157, height)
        width: raiz.campoW
        height: raiz.campoH
        radius: raiz.redondeo
        // `$superficie` al 86%, el mismo relleno que el input-field del bloqueo.
        color: Qt.rgba(paleta.superficie.r, paleta.superficie.g,
                       paleta.superficie.b, 0.86)
        border.width: 2
        border.color: raiz.mensaje !== "" ? paleta.alerta
                    : raiz.comprobando    ? paleta.atencion
                                          : paleta.amatista

        TextInput {
            id: campo
            anchors.fill: parent
            anchors.leftMargin: raiz.px(18)
            anchors.rightMargin: raiz.px(18)
            verticalAlignment: TextInput.AlignVCenter
            horizontalAlignment: TextInput.AlignHCenter
            echoMode: TextInput.Password
            passwordCharacter: "●"
            passwordMaskDelay: 0
            color: paleta.luz
            font.family: raiz.fuente
            font.pixelSize: raiz.px(15)
            selectByMouse: true
            enabled: !raiz.comprobando

            onAccepted: raiz.entrar()
            onTextChanged: if (raiz.mensaje !== "") raiz.mensaje = ""

            Text {
                anchors.centerIn: parent
                visible: campo.text.length === 0
                text: "contraseña"
                color: paleta.tenue
                font.family: raiz.fuente
                font.pixelSize: raiz.px(15)
            }
        }
    }

    // --- El renglon de avisos, en -249 ----------------------------------------
    // El hueco donde el bloqueo pone su fila de datos (bateria, teclado, red).
    // Aqui hace falta para otra cosa: el fallo o el aviso de mayusculas. Ocupa
    // sitio siempre, para que nada de la columna de un salto cuando aparece.
    Text {
        x: raiz.colX
        y: raiz.centro(-249, height)
        text: raiz.mensaje !== "" ? raiz.mensaje
            : keyboard.capsLock  ? "bloq mayús activado"
                                 : ""
        color: raiz.mensaje !== "" ? paleta.alerta : paleta.atencion
        font.family: raiz.fuente
        font.pixelSize: raiz.px(17)
    }

    // =========================================================================
    //  EL PIE DE LA BANDA — sesion y teclado
    // =========================================================================
    // Abajo del todo dentro de la columna, en su mismo margen. Las dos filas se
    // callan solas cuando no hay nada que elegir, que es lo normal en un equipo
    // con un escritorio y un teclado.
    Row {
        x: raiz.colX
        anchors.bottom: parent.bottom
        anchors.bottomMargin: raiz.px(40)
        spacing: raiz.px(18)

        // La sesion. Se listan todas y se marca la elegida.
        Row {
            visible: raiz.nSesiones > 1
            spacing: raiz.px(12)

            Repeater {
                model: sessionModel
                delegate: Text {
                    readonly property bool elegida: index === raiz.sesion
                    text: model.name
                    color: elegida ? paleta.amatista : paleta.tenue
                    font.family: raiz.fuente
                    font.bold: elegida
                    font.pixelSize: raiz.px(13)

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: raiz.sesion = index
                    }
                }
            }
        }

        // La distribucion de teclado. Con una sola no se ensena: solo estorba.
        // Con dos importa, y mucho, porque es lo que decide que sale al escribir
        // la contrasena — y aqui no puedes verla para comprobarlo.
        Text {
            visible: keyboard.enabled && keyboard.layouts.length > 1
            text: keyboard.layouts[keyboard.currentLayout].shortName
            color: paleta.tenue
            font.family: raiz.fuente
            font.pixelSize: raiz.px(13)

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: keyboard.currentLayout =
                    (keyboard.currentLayout + 1) % keyboard.layouts.length
            }
        }
    }

    // =========================================================================
    //  EL APAGADO — abajo a la derecha, FUERA de la banda
    // =========================================================================
    // Lo unico que no vive en la columna, y por dos razones: no cabria sin
    // apretarla, y conviene que lo que apaga el equipo quede lejos del campo
    // donde escribes la contrasena.
    Row {
        anchors.right: parent.right
        anchors.rightMargin: raiz.px(40)
        anchors.bottom: parent.bottom
        anchors.bottomMargin: raiz.px(40)
        spacing: raiz.px(20)

        // Cada boton aparece SOLO si el sistema deja hacerlo. Un boton que
        // existe y no funciona es peor que no tenerlo: en una pantalla de inicio
        // de sesion no hay donde enterarse de por que no paso nada.
        Repeater {
            model: [
                { texto: "Suspender", puede: sddm.canSuspend  },
                { texto: "Reiniciar", puede: sddm.canReboot   },
                { texto: "Apagar",    puede: sddm.canPowerOff }
            ]
            delegate: Text {
                visible: modelData.puede
                text: modelData.texto
                color: zona.containsMouse ? paleta.luz : paleta.tenue
                font.family: raiz.fuente
                font.pixelSize: raiz.px(13)

                MouseArea {
                    id: zona
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (modelData.texto === "Suspender") sddm.suspend()
                        else if (modelData.texto === "Reiniciar") sddm.reboot()
                        else sddm.powerOff()
                    }
                }
            }
        }
    }

    // =========================================================================
    //  RELOJ Y ENTRADA
    // =========================================================================

    function refrescarHora() {
        var ahora = new Date()
        reloj.text = Qt.formatTime(ahora, "HH:mm")

        // OJO, QUE ESTO TIENE TRAMPA. `Qt.formatDate(fecha, "dddd")` NO respeta
        // el idioma del sistema: con un formato propio usa siempre los nombres
        // en ingles. Se midio dentro del propio greeter, enseñando las dos cosas
        // juntas en pantalla: `Qt.locale().name` decia "es_MX" y la misma linea
        // salia "Monday · 03 de August". O sea que el locale estaba bien y el
        // que no lo miraba era el formateador.
        //
        // La unica forma de que use el idioma es pasarselo a mano, y eso solo lo
        // admite toLocaleDateString. Si aqui vuelve a aparecer un Qt.formatDate
        // con nombres de dia o de mes, el fallo vuelve — y en ingles, no vacio,
        // que es de los que se cuelan hasta produccion.
        fecha.text = ahora.toLocaleDateString(Qt.locale(), raiz.formatoFecha)
    }

    function entrar() {
        if (comprobando || usuario === "") return
        mensaje = ""
        comprobando = true
        sddm.login(usuario, campo.text, sesion)
    }

    Timer {
        interval: 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: raiz.refrescarHora()
    }

    Connections {
        target: sddm

        function onLoginSucceeded() {
            raiz.comprobando = false
            raiz.mensaje = ""
        }

        // No se dice QUE fallo (si el usuario no existe o si la contrasena no
        // vale): eso se lo estarias contando tambien a quien no deberia estar
        // delante. Es lo mismo que hace hyprlock.
        function onLoginFailed() {
            raiz.comprobando = false
            raiz.mensaje = "contraseña incorrecta"
            campo.text = ""
            campo.forceActiveFocus()
        }
    }

    Component.onCompleted: {
        refrescarHora()
        campo.forceActiveFocus()
    }
}
