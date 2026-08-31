import QtQuick
import QtQuick.Controls as Controls
import qs.Ui as Ui
import qs.Commons

FocusScope {
    id: root
    required property var backend
    signal dismiss()
    property string page: "picker"
    property int detailIndex: 0
    property string search: ""
    readonly property var view: backend.state
    readonly property bool trial: !!view.trial
    readonly property var rows: view.layouts || []
    readonly property var detail: rows[detailIndex] || null
    readonly property var detailLayout: detail ? backend.catalog.find(l => l.id === detail.layout) : null
    implicitHeight: body.implicitHeight
    activeFocusOnTab: true

    function reset() {
        page = trial ? "trial" : "picker"
        search = ""
        Qt.callLater(function() { root.focusFirst() })
    }
    function focusFirst() {
        if (page === "search") searchField.forceActiveFocus()
        else if (page === "trial") typingField.forceActiveFocus()
        else if (page === "picker" && layoutRepeater.count) layoutRepeater.itemAt(0).forceActiveFocus()
        else backButton.forceActiveFocus()
    }
    function go(where) { page = where; Qt.callLater(function() { root.focusFirst() }) }
    function back() {
        if (trial) { root.dismiss(); return }
        if (page === "picker") root.dismiss()
        else go(page === "editor" || page === "devices" ? "picker" : "editor")
    }
    function ids() { return rows.map(r => r.id) }
    function apply(next, index) { backend.begin(next, view.shortcut, index) }
    function add(layout, variant) {
        let id = layout.id + "/" + variant.id
        if (ids().indexOf(id) >= 0) return
        let next = ids(); next.push(id)
        apply(next, next.length - 1)
    }
    function results() {
        let query = search.toLowerCase().trim()
        let selected = ids()
        let list = []
        backend.catalog.forEach(l => {
            l.variants.forEach(v => {
                if (selected.indexOf(l.id + "/" + v.id) >= 0) return
                if (!query && v.id) return
                if (query && (l.search + " " + v.label.toLowerCase()).indexOf(query) < 0) return
                list.push({layout: l, variant: v})
            })
        })
        return list
    }
    onTrialChanged: {
        typingField.text = ""
        go(trial ? "trial" : "editor")
    }
    onViewChanged: {
        // Shared dropdowns own their displayed value while selecting. A failed
        // trial must put the confirmed value back, even if it did not change.
        shortcut.value = view.shortcut || "custom"
        variant.value = detail ? detail.variant : ""
    }
    onDetailChanged: variant.value = detail ? detail.variant : ""
    Keys.priority: Keys.AfterItem
    Keys.onPressed: function(event) {
        if (event.key === Qt.Key_Escape) { back(); event.accepted = true }
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
        function onCompleted(name) { if (name === "switch" && !root.trial) root.dismiss() }
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
                tooltipText: "Back"
                Accessible.name: "Back"
                onClicked: root.back()
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: root.page === "editor" ? "Layouts" : root.page === "search" ? "Add layout" : root.page === "trial"
                    ? "Try it" : root.page === "devices" ? "Typing keyboard" : "Layout"
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
            visible: root.page === "picker" || root.page === "editor" || root.page === "trial"
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
                    marked: root.page !== "editor" && index === root.view.active
                    suffix: root.page === "editor" ? (index === 0 ? "default ›" : "›") : ""
                    enabled: !root.backend.busy && root.view.revision !== ""
                    onClicked: {
                        if (root.page === "editor") { root.detailIndex = index; root.go("detail") }
                        else root.backend.switchTo(index)
                    }
                }
            }
        }

        Text {
            visible: root.view.problem !== "" && root.page !== "trial"
            width: parent.width
            text: root.view.problem || ""
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            font.family: Style.font.family
            font.pixelSize: Style.font.bodySmall
            color: Color.popups.text
            opacity: 0.7
        }
        LayoutRow {
            visible: root.page === "picker" && !!root.view.device
            width: parent.width
            title: "Edit layouts…"
            enabled: !root.backend.busy && !root.trial
            onClicked: root.go("editor")
        }
        LayoutRow {
            visible: (root.page === "picker" && !root.view.device) || (root.page === "editor" && root.view.devices.length > 1)
            width: parent.width
            title: "Choose keyboard…"
            enabled: !root.backend.busy && !root.trial
            onClicked: root.go("devices")
        }

        Column {
            visible: root.page === "editor"
            width: parent.width
            spacing: Style.spacing.panelGap
            LayoutRow {
                width: parent.width
                title: "+ Add layout"
                enabled: root.rows.length < 4 && !root.view.problem && !root.backend.busy
                onClicked: root.go("search")
            }
            Ui.Dropdown {
                id: shortcut
                width: parent.width
                label: "Switch with"
                value: root.view.shortcut || "custom"
                options: root.view.shortcut === "custom" ? [{value: "custom", label: "Your current shortcut"}].concat(root.backend.shortcuts) : root.backend.shortcuts
                enabled: !root.view.problem && !root.backend.busy
                onChanged: function(value) { root.backend.begin(root.ids(), value, Math.max(0, root.view.active)) }
            }
        }

        Column {
            visible: root.page === "detail"
            width: parent.width
            spacing: Style.spacing.panelGap
            LayoutRow {
                width: parent.width
                title: root.detail ? root.detail.label : ""
                enabled: false
            }
            Ui.Dropdown {
                id: variant
                width: parent.width
                label: "Variant"
                value: root.detail ? root.detail.variant : ""
                options: root.detailLayout ? root.detailLayout.variants.map(v => ({value: v.id, label: v.label})) : []
                enabled: !root.backend.busy && !root.view.problem
                onChanged: function(value) {
                    let next = root.ids(); next[root.detailIndex] = root.detail.layout + "/" + value
                    root.apply(next, root.detailIndex)
                }
            }
            LayoutRow {
                width: parent.width
                title: root.detailIndex === 0 ? "Default at login" : "Use by default"
                marked: root.detailIndex === 0
                enabled: root.detailIndex !== 0 && !root.backend.busy && !root.view.problem
                onClicked: {
                    let next = root.ids(); let selected = next.splice(root.detailIndex, 1)[0]; next.unshift(selected)
                    root.apply(next, 0)
                }
            }
            LayoutRow {
                width: parent.width
                title: "Remove layout"
                enabled: root.rows.length > 1 && !root.backend.busy && !root.view.problem
                onClicked: { let next = root.ids(); next.splice(root.detailIndex, 1); root.apply(next, 0) }
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
                Keys.onEscapePressed: root.back()
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
            visible: root.page === "trial"
            width: parent.width
            spacing: Style.spacing.panelGap
            Text {
                width: parent.width
                text: root.view.trial && root.view.trial.phase === "recovery" ? root.view.trial.error
                    : "Try your letters, accents and switching shortcut."
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                color: Color.popups.text
                font.family: Style.font.family
                font.pixelSize: Style.font.bodySmall
            }
            Ui.TextField {
                id: typingField
                width: parent.width
                placeholderText: "Type here…"
                inputMethodHints: Qt.ImhNoPredictiveText | Qt.ImhNoAutoUppercase
                Accessible.name: "Test typing. This text is never saved."
                Keys.onEscapePressed: root.back()
            }
            Row {
                width: parent.width
                spacing: Style.spacing.controlGap
                Ui.Button {
                    text: "Keep"
                    focusable: true
                    bordered: true
                    enabled: !root.backend.busy && !!root.view.trial && root.view.trial.phase === "testing"
                    onClicked: root.backend.keep()
                }
                Ui.Button {
                    text: "Revert"
                    focusable: true
                    enabled: !root.backend.busy
                    onClicked: root.backend.revert()
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.view.trial ? root.view.trial.remaining + "s to revert" : ""
                    color: Color.popups.text
                    opacity: 0.6
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                }
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
