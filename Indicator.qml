import QtQuick
import qs.Ui as Ui
import qs.Commons

Ui.WidgetButton {
    id: root
    required property var backend
    property bool animate: true
    property string previousPair: ""
    property bool flagPhase: false
    readonly property string code: backend.current ? backend.current.code : "--"
    readonly property string country: backend.current ? backend.current.country : ""
    readonly property string flag: /^[a-z]{2}$/.test(country)
        ? String.fromCodePoint(0x1f1e6 + country.charCodeAt(0) - 97, 0x1f1e6 + country.charCodeAt(1) - 97) : ""
    readonly property string pair: backend.current ? backend.current.id : ""
    readonly property bool motion: animate && backend.animationsEnabled
    onPairChanged: {
        flagTimer.stop()
        flagPhase = !!previousPair && !!pair && flag !== "" && motion
        if (flagPhase) flagTimer.restart()
        previousPair = pair
    }
    onMotionChanged: if (!motion) { flagTimer.stop(); flagPhase = false }
    text: code
    fontSize: Style.font.caption
    labelVisible: false
    hasVisualContent: true
    fixedWidth: bar && bar.vertical ? bar.barSize : Style.space(34)
    tooltipText: backend.current ? backend.current.label + (backend.current.variant ? " · " + backend.current.variantLabel : "") : "Keyboard settings"
    Accessible.role: Accessible.Button
    Accessible.name: tooltipText
    Timer { id: flagTimer; interval: 1050; onTriggered: root.flagPhase = false }
    Text {
        anchors.centerIn: parent
        text: root.code
        textFormat: Text.PlainText
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
        color: root.foreground
        opacity: root.flagPhase ? 0 : 1
        Behavior on opacity {
            enabled: root.motion
            NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
        }
    }
    Text {
        anchors.centerIn: parent
        text: root.flag
        textFormat: Text.PlainText
        font.family: "Noto Color Emoji"
        font.pixelSize: Style.space(16)
        opacity: root.flagPhase ? 1 : 0
        Behavior on opacity {
            enabled: root.motion
            NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
        }
    }
}
