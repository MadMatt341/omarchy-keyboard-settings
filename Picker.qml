import QtQuick
import QtQuick.Controls as Controls
import qs.Ui as Ui
import qs.Commons

FocusScope {
    id: root
    required property var backend
    signal dismiss()
    property string page: "picker"
    property string search: ""
    property var stagedRemoval: null
    readonly property var view: backend.state
    readonly property var rows: view.layouts || []
    readonly property var editorRows: view.configuredLayouts && view.configuredLayouts.length ? view.configuredLayouts : rows
    readonly property string editorShortcut: view.configuredShortcut || view.shortcut || "custom"
    readonly property string editorDefault: editorRows.length ? editorRows[0].id : ""
    readonly property var defaultOptions: editorRows.map(row => ({
        value: row.id,
        label: row.label + (row.variant ? " — " + row.variantLabel : "")
    }))
    readonly property bool editingBusy: backend.busy || stagedRemoval !== null
    implicitHeight: body.implicitHeight
    activeFocusOnTab: true

    function reset() {
        page = "picker"
        search = ""
        Qt.callLater(function() { root.focusFirst() })
    }
    function focusFirst() {
        if (page === "search") searchField.forceActiveFocus()
        else if (page === "picker" && layoutRepeater.count) layoutRepeater.itemAt(0).forceActiveFocus()
        else backButton.forceActiveFocus()
    }
    function go(where) { page = where; Qt.callLater(function() { root.focusFirst() }) }
    function back() {
        if (page === "picker") root.dismiss()
        else go(page === "editor" || page === "devices" ? "picker" : "editor")
    }
    function ids() { return editorRows.map(row => row.id) }
    function save(next, shortcutValue) {
        if (!stagedRemoval) backend.save(next, shortcutValue || editorShortcut)
    }
    function remove(index) {
        if (editorRows.length <= 1 || stagedRemoval) return
        let next = ids()
        let removed = next[index]
        next.splice(index, 1)
        let active = view.active >= 0 && view.active < rows.length ? rows[view.active].id : ""
        if (removed !== active) {
            save(next, editorShortcut)
            return
        }

        // Make an active removal two separate compositor operations. A fresh
        // status readback gives the shell time to consume the ordinary layout
        // switch before the later save replaces the live keymap.
        let adjacent = index < editorRows.length - 1 ? index + 1 : index - 1
        let survivor = editorRows[adjacent].id
        let liveIndex = rows.findIndex(row => row.id === survivor)
        if (liveIndex < 0) {
            backend.error = "Switch to a layout that will remain before removing this one."
            return
        }
        stagedRemoval = {phase: "switching", layouts: next,
            shortcut: editorShortcut, survivor: survivor}
        backend.switchTo(liveIndex)
    }
    function makeDefault(id) {
        let next = ids()
        let index = next.indexOf(id)
        if (index <= 0) return
        let selected = next.splice(index, 1)[0]
        next.unshift(selected)
        save(next, editorShortcut)
    }
    function add(layout, variant) {
        let id = layout.id + "/" + variant.id
        if (ids().indexOf(id) >= 0) return
        let next = ids()
        next.push(id)
        save(next, editorShortcut)
        go("editor")
    }
    function results() {
        let query = search.toLowerCase().trim()
        let selected = ids()
        let list = []
        backend.catalog.forEach(layout => {
            layout.variants.forEach(variant => {
                if (selected.indexOf(layout.id + "/" + variant.id) >= 0) return
                if (!query && variant.id) return
                if (query && (layout.search + " " + variant.label.toLowerCase()).indexOf(query) < 0) return
                list.push({layout: layout, variant: variant})
            })
        })
        return list
    }
    onViewChanged: {
        // Shared dropdowns own their value while selecting. Resynchronize
        // after the derived editor state has followed a fresh helper reply.
        Qt.callLater(function() {
            defaultLayout.value = root.editorDefault
            shortcut.value = root.editorShortcut
        })
    }
    Keys.priority: Keys.AfterItem
    Keys.onPressed: function(event) {
        if (event.key === Qt.Key_Escape) { root.dismiss(); event.accepted = true }
        else if (event.key === Qt.Key_Down || event.key === Qt.Key_Up) {
            let item = root.Window.window ? root.Window.window.activeFocusItem : null
            if (item) {
                let next = item.nextItemInFocusChain(event.key === Qt.Key_Down)
                if (next) next.forceActiveFocus()
                event.accepted = true
            }
        }
    }
    Connections {
        target: root.backend
        function onCompleted(name) {
            if (name !== "switch") return
            if (!root.stagedRemoval) {
                root.dismiss()
                return
            }
            root.stagedRemoval = Object.assign({}, root.stagedRemoval, {phase: "waiting"})
        }
        function onRefreshed(ok) {
            if (!root.stagedRemoval || root.stagedRemoval.phase !== "waiting") return
            let active = root.view.active >= 0 && root.view.active < root.rows.length
                ? root.rows[root.view.active].id : ""
            if (!ok || active !== root.stagedRemoval.survivor || root.view.problem) {
                if (!root.backend.error)
                    root.backend.error = "The surviving layout was not confirmed. Nothing was removed."
                root.stagedRemoval = null
                return
            }
            let removal = root.stagedRemoval
            root.stagedRemoval = null
            root.backend.save(removal.layouts, removal.shortcut)
        }
    }

    Flickable {
        id: scroll
        anchors.fill: parent
        contentHeight: body.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Controls.ScrollBar.vertical: Controls.ScrollBar {}
        Column {
            id: body
            width: parent.width
            spacing: Style.spacing.rowGap

            Row {
                visible: root.page !== "picker"
                width: parent.width
                height: Style.spacing.controlHeight
                spacing: Style.spacing.controlGap
                Ui.Button {
                    id: backButton
                    text: "←"
                    focusable: true
                    width: Style.spacing.controlHeight
                    height: parent.height
                    Accessible.name: "Back"
                    onClicked: root.back()
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.page === "editor" ? "Layouts" : root.page === "search" ? "Add layout" : "Typing keyboard"
                    textFormat: Text.PlainText
                    font.family: Style.font.family
                    font.pixelSize: Style.font.body
                    color: Color.popups.text
                }
            }

            Text {
                visible: root.backend.error !== ""
                width: parent.width
                text: root.backend.error
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                font.family: Style.font.family
                font.pixelSize: Style.font.bodySmall
                color: Color.popups.text
            }

            Column {
                visible: root.page === "picker"
                width: parent.width
                spacing: Style.spacing.rowGap
                Repeater {
                    id: layoutRepeater
                    model: root.rows
                    LayoutRow {
                        required property var modelData
                        required property int index
                        width: body.width
                        title: modelData.label
                        subtitle: modelData.variant ? modelData.variantLabel : ""
                        marked: index === root.view.active
                        enabled: !root.backend.busy && root.view.revision !== ""
                        onClicked: root.backend.switchTo(index)
                    }
                }
            }

            Text {
                visible: root.view.problem !== ""
                width: parent.width
                text: root.view.problem || ""
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                font.family: Style.font.family
                font.pixelSize: Style.font.bodySmall
                color: Color.popups.text
                opacity: 0.7
            }
            Ui.PanelSeparator {
                objectName: "editLayoutsSeparator"
                visible: root.page === "picker" && !!root.view.device
                foreground: Color.popups.text
            }
            LayoutRow {
                visible: root.page === "picker" && !!root.view.device
                width: parent.width
                title: "Edit layouts…"
                enabled: !root.backend.busy
                onClicked: root.go("editor")
            }
            LayoutRow {
                visible: (root.page === "picker" && !root.view.device) || (root.page === "editor" && root.view.devices.length > 1)
                width: parent.width
                title: "Choose keyboard…"
                enabled: !root.backend.busy
                onClicked: root.go("devices")
            }

            Column {
                visible: root.page === "editor"
                width: parent.width
                spacing: Style.spacing.rowGap
                Repeater {
                    id: editorRepeater
                    model: root.editorRows
                    Item {
                        required property var modelData
                        required property int index
                        width: body.width
                        height: Math.max(Style.spacing.controlHeight, editorLabels.implicitHeight + Style.spacing.controlPaddingY * 2)
                        Column {
                            id: editorLabels
                            anchors.left: parent.left
                            anchors.right: removeButton.visible ? removeButton.left : parent.right
                            anchors.rightMargin: removeButton.visible ? Style.spacing.controlGap : 0
                            anchors.verticalCenter: parent.verticalCenter
                            Text {
                                width: parent.width
                                text: modelData.label
                                textFormat: Text.PlainText
                                elide: Text.ElideRight
                                font.family: Style.font.family
                                font.pixelSize: Style.font.body
                                color: Color.popups.text
                            }
                            Text {
                                width: parent.width
                                visible: !!modelData.variant
                                text: modelData.variant ? modelData.variantLabel : ""
                                textFormat: Text.PlainText
                                elide: Text.ElideRight
                                font.family: Style.font.family
                                font.pixelSize: Style.font.caption
                                color: Color.popups.text
                                opacity: 0.65
                            }
                        }
                        Ui.Button {
                            id: removeButton
                            objectName: "removeLayout" + index
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            text: "×"
                            focusable: true
                            visible: root.editorRows.length > 1
                            width: visible ? Style.spacing.controlHeight : 0
                            height: Style.spacing.controlHeight
                            foreground: Color.popups.text
                            enabled: visible && !root.editingBusy && !root.view.problem
                            Accessible.name: "Remove " + modelData.label
                            onClicked: root.remove(index)
                        }
                    }
                }
                LayoutRow {
                    objectName: "addLayout"
                    width: parent.width
                    title: "+ Add layout"
                    enabled: root.editorRows.length < 4 && !root.view.problem && !root.editingBusy
                    onClicked: root.go("search")
                }
                Ui.Dropdown {
                    id: defaultLayout
                    objectName: "defaultLayout"
                    width: parent.width
                    label: "Default at login"
                    value: root.editorDefault
                    options: root.defaultOptions
                    visible: root.editorRows.length > 1
                    enabled: !root.view.problem && !root.editingBusy
                    onChanged: function(value) { root.makeDefault(value) }
                }
                Ui.Dropdown {
                    id: shortcut
                    width: parent.width
                    label: "Switch with"
                    value: root.editorShortcut
                    options: root.editorShortcut === "custom" ? [{value: "custom", label: "Your current shortcut"}].concat(root.backend.shortcuts) : root.backend.shortcuts
                    enabled: !root.view.problem && !root.editingBusy
                    onChanged: function(value) { root.save(root.ids(), value) }
                }
                Text {
                    objectName: "pendingRestart"
                    visible: root.view.pendingRestart || false
                    width: parent.width
                    text: "Saved and active layouts differ. Your next edit will apply this list immediately."
                    textFormat: Text.PlainText
                    wrapMode: Text.Wrap
                    font.family: Style.font.family
                    font.pixelSize: Style.font.bodySmall
                    color: Color.popups.text
                    opacity: 0.7
                }
            }

            Column {
                visible: root.page === "search"
                width: parent.width
                spacing: Style.spacing.rowGap
                Ui.TextField {
                    id: searchField
                    width: parent.width
                    placeholderText: "Search layouts and variants"
                    text: root.search
                    onTextEdited: root.search = text
                    onAccepted: if (searchResults.count) searchResults.currentItem.clicked()
                    Keys.onDownPressed: { searchResults.forceActiveFocus(); searchResults.currentIndex = 0 }
                    Keys.onEscapePressed: root.dismiss()
                    Accessible.name: "Search layouts and variants"
                }
                ListView {
                    id: searchResults
                    width: parent.width
                    height: Style.space(280)
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    model: root.results()
                    spacing: Style.spacing.rowGap
                    currentIndex: 0
                    keyNavigationEnabled: true
                    Controls.ScrollBar.vertical: Controls.ScrollBar {}
                    Keys.onReturnPressed: if (currentItem) currentItem.clicked()
                    Keys.onEnterPressed: if (currentItem) currentItem.clicked()
                    delegate: LayoutRow {
                        required property var modelData
                        required property int index
                        width: searchResults.width
                        title: modelData.layout.label
                        subtitle: modelData.variant.id ? modelData.variant.label : ""
                        hasCursor: searchResults.activeFocus && index === searchResults.currentIndex
                        enabled: !root.backend.busy
                        onClicked: root.add(modelData.layout, modelData.variant)
                    }
                }
                Text {
                    visible: searchResults.count === 0
                    text: "No layouts found"
                    color: Color.popups.text
                    font.family: Style.font.family
                    font.pixelSize: Style.font.bodySmall
                }
            }

            Column {
                width: parent.width
                visible: root.page === "devices"
                spacing: Style.spacing.rowGap
                Repeater {
                    model: root.view.devices
                    LayoutRow {
                        required property var modelData
                        width: body.width
                        title: modelData.label
                        subtitle: modelData.certain ? "" : "Cannot identify safely"
                        marked: modelData.id === root.view.device
                        enabled: modelData.certain && !root.backend.busy
                        onClicked: { root.backend.request("choose", {device: modelData.id}); root.go("picker") }
                    }
                }
            }
        }
    }
}
