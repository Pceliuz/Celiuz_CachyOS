// sddm/celiuz/Main.qml — la pantalla de inicio de sesion.
//
// Es la hermana de hypr/hyprlock.conf: misma tarjeta violeta, mismo titulo,
// mismo reloj grande y el mismo velo sobre el fondo. La diferencia es que
// hyprlock solo pide una contrasena y esto ademas tiene que dejarte ELEGIR
// —cuenta, sesion, apagar el equipo— y funcionar antes de que exista tu sesion.
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
//   sin una cuenta -> el campo de siempre, escribiendo el nombre a mano
//   sin permiso para apagar -> el boton no aparece, en vez de fallar al pulsarlo
import QtQuick

Rectangle {
    id: raiz
    color: paleta.negro

    // La paleta, generada desde hypr/conf/colores.conf por gen-colores.py.
    Colores { id: paleta }

    // --- Escala ---------------------------------------------------------------
    // El mismo criterio que hypr/scripts/lib/pantalla.py: todo esta pensado para
    // 1920x1080 y se reduce con un factor. La diferencia es que aqui no hace
    // falta generar nada ni medir por fuera — QML sabe el tamano de la pantalla
    // y se reajusta solo si cambias de monitor.
    readonly property real f: Math.min(width / 1920, height / 1080)
    function px(v) { return Math.max(1, Math.round(v * raiz.f)) }

    // --- Ajustes de theme.conf ------------------------------------------------
    // config.loQueSea devuelve "" cuando la clave no esta, asi que cada uno lleva
    // su valor por defecto detras. El que clone el repo cambia el titulo por el
    // suyo sin tocar una linea de QML.
    readonly property string titulo:      config.titulo      || "彼岸花"
    readonly property string fuente:      config.fuente      || "MesloLGS Nerd Font"
    readonly property string fuenteTit:   config.fuenteTitulo || "Noto Sans CJK TC"
    readonly property real   veloAlfa:    parseFloat(config.veloOpacidad || "0.36")
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

    // El velo, igual que en hyprlock: sin el, un fondo claro se come el texto.
    // Va en un rectangulo aparte y no como opacidad de la tarjeta porque
    // `opacity` en QML se hereda a los hijos, y atenuaria tambien el reloj.
    Rectangle {
        anchors.fill: parent
        color: paleta.abismo
        opacity: raiz.veloAlfa
    }

    // =========================================================================
    //  EL EQUIPO, arriba a la izquierda
    // =========================================================================
    Text {
        x: raiz.px(40); y: raiz.px(30)
        text: sddm.hostName
        color: paleta.tenue
        font.family: raiz.fuente
        font.pixelSize: raiz.px(13)
    }

    // =========================================================================
    //  LA TARJETA
    // =========================================================================
    Column {
        anchors.centerIn: parent
        spacing: raiz.px(22)

        Item {
            width: tarjeta.width
            height: tarjeta.height
            anchors.horizontalCenter: parent.horizontalCenter

            // El halo. hyprlock lo hace con shadow_passes; aqui se imita con
            // tres rectangulos detras, cada uno mas grande y mas transparente.
            // Se hace a mano y no con QtQuick.Effects a proposito: ese modulo es
            // otra dependencia que puede faltar, y por un halo no merece la pena
            // arriesgar la pantalla entera.
            Repeater {
                model: 3
                Rectangle {
                    anchors.centerIn: parent
                    width:  tarjeta.width  + raiz.px(6 + index * 7)
                    height: tarjeta.height + raiz.px(6 + index * 7)
                    radius: tarjeta.radius + raiz.px(3 + index * 3)
                    color: "transparent"
                    border.width: raiz.px(2)
                    border.color: paleta.amatista
                    opacity: 0.20 - index * 0.055
                }
            }

            Rectangle {
                id: tarjeta
                width: raiz.px(420)
                height: contenido.height + raiz.px(52)
                radius: raiz.px(18)
                // $superficie al 86%, el mismo valor que la tarjeta del bloqueo.
                color: Qt.rgba(paleta.superficie.r, paleta.superficie.g,
                               paleta.superficie.b, 0.86)
                border.width: raiz.px(2)
                border.color: paleta.amatista

                Column {
                    id: contenido
                    anchors.centerIn: parent
                    width: parent.width - raiz.px(44)
                    spacing: raiz.px(6)

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: raiz.titulo
                        color: paleta.luz
                        font.family: raiz.fuenteTit
                        font.pixelSize: raiz.px(26)
                    }

                    // La cuenta. Con una sola es una etiqueta; con varias, la
                    // fila de abajo, y esta se calla para no decir lo mismo dos
                    // veces.
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        visible: !raiz.verCuentas
                        text: raiz.usuario
                        color: paleta.amatista
                        font.family: raiz.fuente
                        font.bold: true
                        font.pixelSize: raiz.px(13)
                    }

                    Item { width: 1; height: raiz.px(10) }

                    Text {
                        id: reloj
                        anchors.horizontalCenter: parent.horizontalCenter
                        color: paleta.luz
                        font.family: raiz.fuente
                        font.bold: true
                        font.pixelSize: raiz.px(54)
                    }

                    // La fecha, en el idioma DEL SISTEMA. Ni una palabra de
                    // esto va escrita: `Qt.formatDate` con el locale por defecto
                    // usa /etc/locale.conf, que es lo que ve el greeter. Cablear
                    // un idioma aqui seria el mismo fallo que ya costo una tarde
                    // en hyprlock y en el reloj de la barra.
                    Text {
                        id: fecha
                        anchors.horizontalCenter: parent.horizontalCenter
                        color: paleta.tenue
                        font.family: raiz.fuente
                        font.pixelSize: raiz.px(12)
                    }

                    Item { width: 1; height: raiz.px(4); visible: raiz.verCuentas }

                    // Las cuentas, una fila de nombres. Se usa un Repeater sobre
                    // el modelo en vez de sacar los nombres a una lista propia:
                    // los roles de un modelo de SDDM solo se leen DENTRO del
                    // delegado, y dar la vuelta a eso con Instantiator seria
                    // maquinaria de mas para tres nombres.
                    Flow {
                        visible: raiz.verCuentas
                        width: parent.width
                        spacing: raiz.px(14)
                        anchors.horizontalCenter: parent.horizontalCenter

                        Repeater {
                            model: userModel
                            delegate: Text {
                                readonly property bool elegido: model.name === raiz.usuario
                                text: model.realName || model.name
                                color: elegido ? paleta.luz : paleta.tenue
                                font.family: raiz.fuente
                                font.bold: elegido
                                font.pixelSize: raiz.px(13)

                                // SDDM solo recuerda la ultima cuenta que entro,
                                // y en un equipo recien instalado no ha entrado
                                // ninguna: `userModel.lastUser` viene vacio. Sin
                                // esto, la primera vez la pantalla pediria la
                                // contrasena de nadie y no dejaria pasar. El
                                // primer delegado que se crea rellena el hueco.
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
                }
            }
        }

        // --- La cuenta, cuando no hay ninguna que ofrecer ---------------------
        // Pasa en un sistema donde los usuarios estan ocultos para el greeter, o
        // en uno recien instalado. Sin este campo la pantalla seria un callejon
        // sin salida: pediria la contrasena de un usuario vacio y no dejaria
        // entrar nunca, sin decir por que.
        Rectangle {
            visible: raiz.nCuentas === 0
            anchors.horizontalCenter: parent.horizontalCenter
            width: raiz.px(420)
            height: raiz.px(46)
            radius: raiz.px(14)
            color: Qt.rgba(paleta.superficie.r, paleta.superficie.g,
                           paleta.superficie.b, 0.86)
            border.width: raiz.px(2)
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

        // --- La contrasena ----------------------------------------------------
        // Debajo de la tarjeta y en su propia caja, como en el bloqueo. El borde
        // es el que avisa: amatista en reposo, ambar comprobando, rojo si fallas.
        Rectangle {
            id: caja
            anchors.horizontalCenter: parent.horizontalCenter
            width: raiz.px(420)
            height: raiz.px(46)
            radius: raiz.px(14)
            color: Qt.rgba(paleta.superficie.r, paleta.superficie.g,
                           paleta.superficie.b, 0.86)
            border.width: raiz.px(2)
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

        // Un solo renglon para todo lo que hay que decir: el fallo, el aviso de
        // mayusculas o nada. Ocupa sitio siempre (`height` fijo) para que la
        // tarjeta no de un salto cuando aparece.
        Item {
            anchors.horizontalCenter: parent.horizontalCenter
            width: caja.width
            height: raiz.px(18)

            Text {
                anchors.centerIn: parent
                text: raiz.mensaje !== "" ? raiz.mensaje
                    : keyboard.capsLock  ? "bloq mayús activado"
                                         : ""
                color: raiz.mensaje !== "" ? paleta.alerta : paleta.atencion
                font.family: raiz.fuente
                font.pixelSize: raiz.px(12)
            }
        }
    }

    // =========================================================================
    //  EL PIE — sesion y teclado a la izquierda, apagado a la derecha
    // =========================================================================

    Row {
        x: raiz.px(40)
        anchors.bottom: parent.bottom
        anchors.bottomMargin: raiz.px(28)
        spacing: raiz.px(18)

        // La sesion. Se listan todas y se marca la elegida; con una sola, la
        // fila entera se calla, que es lo normal en un equipo con un escritorio.
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
                    font.pixelSize: raiz.px(12)

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
            font.pixelSize: raiz.px(12)

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: keyboard.currentLayout =
                    (keyboard.currentLayout + 1) % keyboard.layouts.length
            }
        }
    }

    Row {
        anchors.right: parent.right
        anchors.rightMargin: raiz.px(40)
        anchors.bottom: parent.bottom
        anchors.bottomMargin: raiz.px(28)
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
                font.pixelSize: raiz.px(12)

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
