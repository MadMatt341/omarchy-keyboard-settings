import QtQuick
import QtTest
import Quickshell
import qs.Commons
import qs.Ui as Ui
import "plugin" as Plugin

Scope {
    id: preview
    property int step: 0
    property bool capturesComplete: false
    property var pages: ["picker", "editor", "search", "detail", "trial"]
    TestCase {
        name: "KeyboardPicker"
        when: preview.capturesComplete
        function init() {
            fake.state = Object.assign({}, fake.state, {trial: null, active: 1})
            fake.animationsEnabled = true
            picker.reset()
            wait(20)
        }
        function test_helper_location() {
            verify(Plugin.Backend.helper.startsWith("/"), "The helper must resolve to a real filesystem path")
            console.log("NATIVE_HELPER_PATH_OK", Plugin.Backend.helper)
        }
        function test_flag_uses_the_same_slot() {
            let before = widget.implicitWidth
            fake.switchTo(0)
            wait(200)
            compare(widget.flagPhase, true)
            compare(widget.implicitWidth, before)
            wait(1100)
            compare(widget.flagPhase, false)
            compare(widget.code, "EN")
            fake.animationsEnabled = false
            fake.switchTo(1)
            compare(widget.flagPhase, false)
            compare(widget.implicitWidth, before)
            console.log("NATIVE_FLAG_OK")
        }
        function test_navigation_and_text_input() {
            picker.reset()
            wait(20)
            keyClick(Qt.Key_Tab)
            keyClick(Qt.Key_Tab)
            keyClick(Qt.Key_Return)
            compare(picker.page, "editor")
            keyClick(Qt.Key_Escape)
            compare(picker.page, "picker")
            picker.go("search")
            wait(20)
            keyClick(Qt.Key_J)
            keyClick(Qt.Key_K)
            compare(picker.search, "jk")
            keyClick(Qt.Key_Escape)
            compare(picker.page, "editor")
            console.log("NATIVE_INTERACTION_OK")
        }
    }
    QtObject {
        id: fake
        property var state: ({layouts: [
            {id: "us/", layout: "us", variant: "", label: "English (US)", variantLabel: "Standard", code: "EN", country: "us"},
            {id: "pl/", layout: "pl", variant: "", label: "Polish", variantLabel: "Standard", code: "PL", country: "pl"}],
            active: 1, devices: [], device: "preview", revision: "preview", shortcut: "both-alt", trial: null, problem: ""})
        property var catalog: [
            {id: "us", label: "English (US)", search: "english us", variants: [{id: "", label: "Standard"}, {id: "intl", label: "English (US, intl., with dead keys)"}]},
            {id: "pl", label: "Polish", search: "polish pl", variants: [{id: "", label: "Standard"}]},
            {id: "de", label: "German", search: "german de", variants: [{id: "", label: "Standard"}]},
            {id: "fr", label: "French", search: "french fr", variants: [{id: "", label: "Standard"}]}]
        property var shortcuts: [{value: "both-alt", label: "Both Alt keys"}, {value: "bar", label: "The bar only"}]
        property bool busy: false
        property bool animationsEnabled: true
        readonly property var current: state.layouts[state.active]
        property string error: ""
        signal completed(string name)
        function switchTo(index) { state = Object.assign({}, state, {active: index}); completed("switch") }
        function begin(ids, shortcut, index) { console.log("PREVIEW ONLY", ids, shortcut, index) }
        function keep() { state = Object.assign({}, state, {trial: null}) }
        function revert() { keep() }
        function request(name, args) { console.log("PREVIEW ONLY", name) }
        function refresh() {}
    }
    FloatingWindow {
        id: window
        visible: true
        implicitWidth: 390
        implicitHeight: 580
        color: Color.background
        Plugin.Indicator {
            id: widget
            x: 340
            y: 0
            width: implicitWidth
            height: implicitHeight
            backend: fake
        }
        Ui.BorderSurface {
            id: card
            x: 20
            y: 24
            width: picker.page === "picker" ? 272 : 336
            height: picker.implicitHeight + 28
            color: Color.popups.background
            borderSpec: Border.surfaceSpec("popups", "border", Color.popups.border, 2)
            radius: Style.cornerRadius
            Plugin.Picker {
                id: picker
                x: 14
                y: 14
                width: parent.width - 28
                height: implicitHeight
                backend: fake
            }
        }
    }
    Timer {
        interval: 300
        repeat: true
        running: true
        onTriggered: {
            if (preview.step >= preview.pages.length * 2) {
                console.log("NATIVE_PREVIEW_OK")
                stop()
                preview.capturesComplete = true
                return
            }
            let name = preview.pages[Math.floor(preview.step / 2)]
            if (preview.step % 2 === 0) {
                if (name === "trial") fake.state = Object.assign({}, fake.state, {trial: {token: "preview", phase: "testing", remaining: 42}})
                picker.page = name
                picker.detailIndex = 0
            } else {
                if (picker.implicitHeight > 530 || picker.implicitHeight < 40) throw new Error("Invalid panel height")
                card.grabToImage(function(result) {
                    if (!result.saveToFile(Quickshell.env("KEYBOARD_PREVIEW_OUTPUT") + "/" + name + ".png")) throw new Error("Screenshot failed")
                })
                console.log("NATIVE_PAGE", name, picker.implicitHeight)
            }
            preview.step++
        }
    }
}
