pragma Singleton
import QtQuick
import Quickshell.Io
import Quickshell.Hyprland

QtObject {
    id: root
    property var state: ({layouts: [], configuredLayouts: [], physicalLayouts: [],
        compatibilityMode: "", active: -1, devices: [], device: "", revision: "",
        problem: "", pendingRestart: false})
    property var catalog: []
    property var shortcuts: []
    property string error: ""
    property string eventDevice: ""
    property bool pending: false
    property bool stateFresh: false
    property int nextRequestId: 1
    property var activeRequest: null
    property bool awaitingReadback: false
    property bool actionExpected: false
    property bool actionReplySeen: false
    property bool queryExpected: false
    property bool queryReplySeen: false
    property int queryOwnerId: 0
    readonly property bool busy: action.running || query.running || queryExpected
        || awaitingReadback || activeRequest !== null
    readonly property bool operationActive: activeRequest !== null
    property bool querySucceeded: false
    property bool animationsEnabled: true
    property string helper: decodeURIComponent(Qt.resolvedUrl("backend/keyboard_settings.py").toString().replace(/^file:\/\//, ""))
    readonly property var current: state.active >= 0 && state.active < state.layouts.length ? state.layouts[state.active] : null
    signal actionFinished(var result)
    signal refreshed(bool ok)

    function rowIds(rows) {
        if (!rows || typeof rows.length !== "number") return "-"
        let ids = []
        for (let i = 0; i < rows.length; i++) {
            let identity = rows[i] && rows[i].id !== undefined ? String(rows[i].id) : ""
            if (identity) ids.push(identity)
        }
        return ids.length ? ids.join(",") : "-"
    }
    function identityIds(ids) {
        if (!ids || typeof ids.length !== "number" || !ids.length) return "-"
        return Array.from(ids).map(identity => String(identity)).join(",")
    }
    function traceOperation(request, phase, snapshot, outcome) {
        if (!request) return
        // Support logs intentionally contain only operation metadata and XKB
        // layout IDs. Never add device names or the raw helper request here.
        let visible = snapshot || state
        let parts = ["id=" + request.id, "name=" + request.name, "phase=" + phase,
            "requested=" + identityIds(request.requestedLayouts),
            "runtime=" + rowIds(visible.layouts),
            "configured=" + rowIds(visible.configuredLayouts)]
        if (outcome) parts.push("outcome=" + outcome)
        console.log("keyboard-settings-op " + parts.join(" "))
    }

    function refresh() {
        if (busy) { pending = true; return }
        startQuery(0)
    }
    function startQuery(ownerId) {
        pending = false
        querySucceeded = false
        queryReplySeen = false
        queryOwnerId = ownerId || 0
        query.command = ["python3", helper, "status", JSON.stringify({eventDevice: eventDevice})]
        // The helper persists a verified source across shell reloads. Send an
        // event once; resending an old name would override a later observation.
        eventDevice = ""
        queryExpected = true
        query.running = true
    }
    function request(name, args, revision) {
        if (busy || !stateFresh) {
            if (!stateFresh) error = "Refresh the keyboard state before changing it."
            return 0
        }
        error = ""
        let id = nextRequestId++
        let requestArgs = Object.assign({}, args)
        requestArgs.revision = revision === undefined ? state.revision : revision
        requestArgs.eventDevice = eventDevice
        eventDevice = ""
        let requestedLayouts = []
        if (name === "save" && requestArgs.layouts && typeof requestArgs.layouts.length === "number")
            requestedLayouts = Array.from(requestArgs.layouts)
        else if (name === "switch" && requestArgs.index >= 0 && requestArgs.index < state.layouts.length)
            requestedLayouts = [state.layouts[requestArgs.index].id]
        activeRequest = {id: id, name: name, baseRevision: requestArgs.revision,
            requestedLayouts: requestedLayouts, actionOk: false, actionData: null,
            actionError: ""}
        traceOperation(activeRequest, "request", state)
        actionReplySeen = false
        actionExpected = true
        action.command = ["python3", helper, name, JSON.stringify(requestArgs)]
        action.running = true
        return id
    }
    function switchTo(index, revision) { return request("switch", {index: index}, revision) }
    function save(ids, shortcut, revision, expectedActiveId) {
        let args = {layouts: ids, shortcut: shortcut}
        if (expectedActiveId !== undefined) args.expectedActiveId = expectedActiveId
        return request("save", args, revision)
    }
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
                root.queryReplySeen = true
                root.querySucceeded = value.ok
                if (value.ok) root.state = value.data
            }
        }
        onRunningChanged: if (!running && root.queryExpected) Qt.callLater(root.finishQuery)
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
                root.actionReplySeen = true
                if (root.activeRequest) root.activeRequest = Object.assign({}, root.activeRequest, {
                    actionOk: value.ok, actionData: value.data || null,
                    actionError: value.ok ? "" : (value.error || root.error)
                })
                root.traceOperation(root.activeRequest,
                    value.ok ? "action-ok" : "action-rejected", root.state)
            }
        }
        onRunningChanged: if (!running && root.actionExpected) {
            root.actionExpected = false
            Qt.callLater(root.finishAction)
        }
    }
    function finishAction() {
        if (!activeRequest) return
        if (!actionReplySeen) {
            error = "The keyboard did not respond. Try again."
            activeRequest = Object.assign({}, activeRequest, {actionOk: false, actionError: error})
        }
        awaitingReadback = true
        startQuery(activeRequest.id)
    }
    function finishQuery() {
        queryExpected = false
        let owner = queryOwnerId
        queryOwnerId = 0
        if (!queryReplySeen) {
            error = "The keyboard did not respond. Try again."
            querySucceeded = false
        }
        stateFresh = querySucceeded
        if (!owner && querySucceeded) error = ""
        refreshed(querySucceeded)
        if (owner && activeRequest && activeRequest.id === owner) {
            let request = activeRequest
            let ok = request.actionOk && querySucceeded
            let outcome = ok ? "committed" : (!request.actionOk && querySucceeded ? "rejected" : "unconfirmed")
            let resultError = request.actionOk ? (querySucceeded ? "" : error) : request.actionError
            traceOperation(request, querySucceeded ? "readback-ok" : "readback-failed",
                state, outcome)
            activeRequest = null
            awaitingReadback = false
            actionFinished({id: request.id, name: request.name, ok: ok, outcome: outcome,
                error: resultError, data: request.actionData, baseRevision: request.baseRevision})
        }
        if (pending) Qt.callLater(refresh)
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
