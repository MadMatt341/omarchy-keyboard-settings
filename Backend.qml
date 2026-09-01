pragma Singleton
import QtQuick
import Quickshell.Io
import Quickshell.Hyprland

QtObject {
    id: root
    property var state: ({layouts: [], configuredLayouts: [], active: -1, devices: [], device: "", revision: "", problem: "", pendingRestart: false})
    property var catalog: []
    property var shortcuts: []
    property string error: ""
    property string eventDevice: ""
    property bool pending: false
    property bool busy: action.running
    property string actionName: ""
    property bool animationsEnabled: true
    property string helper: decodeURIComponent(Qt.resolvedUrl("backend/keyboard_settings.py").toString().replace(/^file:\/\//, ""))
    readonly property var current: state.active >= 0 && state.active < state.layouts.length ? state.layouts[state.active] : null
    signal completed(string name)

    function refresh() {
        if (query.running || action.running) { pending = true; return }
        pending = false
        query.command = ["python3", helper, "status", JSON.stringify({eventDevice: eventDevice})]
        // The helper persists a verified source across shell reloads. Send an
        // event once; resending an old name would override a later observation.
        eventDevice = ""
        query.running = true
    }
    function request(name, args) {
        if (busy) return
        error = ""
        actionName = name
        args.revision = state.revision
        args.eventDevice = eventDevice
        action.command = ["python3", helper, name, JSON.stringify(args)]
        action.running = true
    }
    function switchTo(index) { request("switch", {index: index}) }
    function save(ids, shortcut) { request("save", {layouts: ids, shortcut: shortcut}) }
    function reply(text) {
        try {
            let value = JSON.parse(text)
            if (!value.ok) error = value.error || "The keyboard did not respond."
            return value
        } catch (_) {
            error = "The keyboard did not respond. Try again."
            return {ok: false}
        }
    }
    Component.onCompleted: { registry.running = true; motion.running = true; refresh() }

    property Process motion: Process {
        command: ["hyprctl", "-j", "getoption", "animations.enabled"]
        stdout: StdioCollector {
            waitForEnd: true
            onStreamFinished: {
                try { root.animationsEnabled = JSON.parse(text).int !== 0 } catch (_) {}
            }
        }
    }

    property Process query: Process {
        stdout: StdioCollector {
            waitForEnd: true
            onStreamFinished: {
                let value = root.reply(text)
                if (value.ok) root.state = value.data
                else root.state = Object.assign({}, root.state, {active: -1, activeLayouts: [], revision: ""})
            }
        }
        onRunningChanged: if (!running && root.pending) Qt.callLater(root.refresh)
    }
    property Process registry: Process {
        command: ["python3", root.helper, "catalog"]
        stdout: StdioCollector {
            waitForEnd: true
            onStreamFinished: {
                let value = root.reply(text)
                if (value.ok) { root.catalog = value.data.layouts; root.shortcuts = value.data.shortcuts }
            }
        }
    }
    property Process action: Process {
        stdout: StdioCollector {
            waitForEnd: true
            onStreamFinished: {
                let value = root.reply(text)
                if (value.ok) root.completed(root.actionName)
            }
        }
        onRunningChanged: if (!running) Qt.callLater(root.refresh)
    }
    property Timer polling: Timer {
        interval: 20000
        running: true
        repeat: true
        onTriggered: root.refresh()
    }
    property Timer eventRefresh: Timer { interval: 40; onTriggered: root.refresh() }
    property Connections events: Connections {
        target: Hyprland
        function onRawEvent(event) {
            if (!event || !event.name) return
            if (event.name === "activelayout") {
                let parts = event.parse ? event.parse(2) : String(event.data || "").split(",")
                let name = String(parts[0] || "")
                // The first event can precede the initial device query. The
                // helper validates membership against its fresh device list.
                if (name && (!root.state.revision || (root.state.deviceNames || []).indexOf(name) >= 0)) root.eventDevice = name
                root.eventRefresh.restart()
            } else if (event.name === "configreloaded") {
                root.eventDevice = ""
                if (!root.motion.running) root.motion.running = true
                root.eventRefresh.restart()
            }
        }
    }
}
