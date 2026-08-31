import QtQuick
import QtQuick.Controls as Controls
import QtTest
import Quickshell
import qs.Commons
import qs.Ui as Ui
import "plugin" as Plugin

Scope {
    id: preview
    property int step: 0
    property bool capturesComplete: false
    property var pages: ["picker", "editor", "search"]
    TestCase {
        name: "KeyboardPicker"
        when: preview.capturesComplete
        function init() {
            fake.state = Object.assign({}, fake.state, {configuredLayouts: fake.baseLayouts, configuredShortcut: "both-alt",
                pendingRestart: false, active: 1, activeLayouts: [], problem: "", devices: [], device: "preview", revision: "preview"})
            fake.error = ""
            fake.saves = []
            fake.animationsEnabled = true
            picker.reset()
            wait(20)
        }
        function cleanup() {
            if (qtest_results.failed) console.log("NATIVE_TEST_FAILED", qtest_results.functionName, qtest_results.dataTag)
        }
        function cleanupTestCase() {
            console.log("NATIVE_TEST_TOTALS", qtest_results.passCount, qtest_results.failCount)
        }
        function test_helper_location() {
            verify(Plugin.Backend.helper.startsWith("/"), "The helper must resolve to a real filesystem path")
            console.log("NATIVE_HELPER_PATH_OK", Plugin.Backend.helper)
        }
        function visibleButtons(item) {
            let buttons = []
            for (let child of item.children) {
                if (!child.visible) continue
                if (child instanceof Ui.Button) buttons.push(child)
                buttons = buttons.concat(visibleButtons(child))
            }
            return buttons
        }
        function test_menu_tooltips_data() {
            return preview.pages.concat(["devices"]).map(page => ({tag: page, page: page}))
        }
        function test_edit_layouts_separator() {
            let separator = findChild(picker, "editLayoutsSeparator")
            verify(separator)
            compare(separator.visible, true)
            compare(separator.height, 1)
            compare(separator.width, picker.width)
            compare(separator.activeFocusOnTab, false)
            let buttons = visibleButtons(picker)
            compare(buttons.length, 3)
            compare(buttons[2].title, "Edit layouts…")
            let above = buttons[1].mapToItem(picker, 0, buttons[1].height).y
            let line = separator.mapToItem(picker, 0, 0).y
            let below = buttons[2].mapToItem(picker, 0, 0).y
            verify(line - above >= Style.spacing.rowGap)
            verify(below - line - separator.height >= Style.spacing.rowGap)
            for (let page of preview.pages.concat(["devices"]).filter(page => page !== "picker")) {
                picker.go(page)
                wait(20)
                compare(separator.visible, false)
            }
            fake.state = Object.assign({}, fake.state, {device: ""})
            picker.go("picker")
            wait(20)
            compare(separator.visible, false)
            console.log("NATIVE_SEPARATOR_OK")
        }
        function test_direct_editing() {
            picker.go("editor")
            wait(20)
            let remove = findChild(picker, "removeLayout1")
            verify(remove)
            compare(remove.text, "×")
            compare(remove.enabled, true)
            mouseClick(remove)
            tryCompare(fake, "saveCount", 1)
            compare(fake.saves[0].layouts.join(","), "us/")
            compare(fake.saves[0].shortcut, "both-alt")
            let warning = findChild(picker, "pendingRestart")
            compare(warning.visible, true)
            compare(warning.text, "Saved. Sign out or reboot to apply layout edits.")
            let captured = false
            card.grabToImage(function(result) {
                verify(result.saveToFile(Quickshell.env("KEYBOARD_PREVIEW_OUTPUT") + "/editor-saved.png"))
                captured = true
            })
            tryVerify(() => captured)
            console.log("NATIVE_DIRECT_EDIT_OK")
        }
        function test_menu_tooltips(data) {
            fake.state = Object.assign({}, fake.state, {
                devices: [{id: "preview", label: "Typing keyboard", certain: true},
                          {id: "second", label: "Second keyboard", certain: true}]
            })
            picker.go(data.page)
            wait(20)
            let buttons = visibleButtons(picker)
            verify(buttons.length > 0, "The page must contain controls to test")
            if (data.page === "picker") compare(buttons.length, 3)
            for (let button of buttons) {
                compare(button.tooltipText, "")
                let tooltip = Array.from(button.data).find(child => child instanceof Controls.ToolTip)
                verify(tooltip, "Each button must use the shared tooltip")
                if (button.enabled) {
                    mouseMove(button, button.width / 2, button.height / 2)
                    wait(500)
                    verify(button.hot, "Hover highlighting must still work")
                }
                compare(tooltip.visible, false)
            }
            mouseMove(widget, widget.width / 2, widget.height / 2)
            verify(widget.tooltipHovered)
            compare(widget.tooltipText, "Polish")
            console.log("NATIVE_TOOLTIPS_OK", data.page)
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
        function test_unresolved_layouts_are_explained() {
            let message = "The typing interfaces report different or unknown layouts. Select a layout above to synchronize them."
            fake.state = Object.assign({}, fake.state, {active: -1, activeLayouts: fake.state.layouts, problem: message})
            wait(20)
            compare(widget.code, "EN/PL")
            compare(widget.tooltipText, message)
            compare(widget.Accessible.name, message)
            verify(widget.implicitWidth >= 34)
            compare(widget.flagPhase, false)
            let captured = 0
            card.grabToImage(function(result) {
                verify(result.saveToFile(Quickshell.env("KEYBOARD_PREVIEW_OUTPUT") + "/unresolved-picker.png"))
                captured++
            })
            widget.grabToImage(function(result) {
                verify(result.saveToFile(Quickshell.env("KEYBOARD_PREVIEW_OUTPUT") + "/unresolved-indicator.png"))
                captured++
            })
            tryVerify(() => captured === 2)
            fake.state = Object.assign({}, fake.state, {activeLayouts: [], problem: ""})
            fake.error = "The desktop did not respond."
            compare(widget.code, "?")
            compare(widget.tooltipText, fake.error)
            console.log("NATIVE_UNRESOLVED_OK")
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
        property var baseLayouts: [
            {id: "us/", layout: "us", variant: "", label: "English (US)", variantLabel: "Standard", code: "EN", country: "us"},
            {id: "pl/", layout: "pl", variant: "", label: "Polish", variantLabel: "Standard", code: "PL", country: "pl"}]
        property var state: ({layouts: baseLayouts, configuredLayouts: baseLayouts, configuredShortcut: "both-alt",
            pendingRestart: false, active: 1, devices: [], device: "preview", revision: "preview", shortcut: "both-alt", problem: ""})
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
        property var saves: []
        readonly property int saveCount: saves.length
        signal completed(string name)
        function switchTo(index) { state = Object.assign({}, state, {active: index}); completed("switch") }
        function save(ids, shortcut) {
            saves = saves.concat([{layouts: ids.slice(), shortcut: shortcut}])
            let all = baseLayouts.concat([{id: "de/", layout: "de", variant: "", label: "German", variantLabel: "Standard", code: "DE", country: "de"}])
            state = Object.assign({}, state, {configuredLayouts: ids.map(id => all.find(row => row.id === id)),
                configuredShortcut: shortcut, pendingRestart: true})
            completed("save")
        }
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
                picker.page = name
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
