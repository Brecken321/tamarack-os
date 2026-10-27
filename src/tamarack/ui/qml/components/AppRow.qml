// One app from Flathub: its icon, name and summary, and Install, or Open and
// Remove once it is installed.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

RowLayout {
    id: row
    // { id, name, summary (optional), installed, icon (file path or "") }
    property var app: ({})

    spacing: Kirigami.Units.largeSpacing
    Layout.fillWidth: true

    Kirigami.Icon {
        // Flathub's catalog icon; an installed app's own icon otherwise.
        source: row.app.icon ? "file://" + row.app.icon : (row.app.id || "")
        fallback: "application-x-executable"
        implicitWidth: Kirigami.Units.iconSizes.medium
        implicitHeight: Kirigami.Units.iconSizes.medium
        Accessible.ignored: true
    }
    ColumnLayout {
        spacing: 0
        Layout.fillWidth: true
        Controls.Label {
            text: row.app.name || row.app.id || ""
            font.weight: Font.DemiBold
            elide: Text.ElideRight
            Layout.fillWidth: true
        }
        Controls.Label {
            visible: text.length > 0
            text: row.app.summary || (row.app.installed ? qsTr("Installed") : "")
            opacity: 0.7
            elide: Text.ElideRight
            Layout.fillWidth: true
        }
    }
    Controls.Button {
        visible: !row.app.installed
        text: qsTr("Install")
        icon.name: "download"
        enabled: !backend.busy
        onClicked: backend.installApps([row.app.id])
        Accessible.name: qsTr("Install %1").arg(row.app.name)
    }
    Controls.Button {
        visible: !!row.app.installed
        text: qsTr("Open")
        onClicked: backend.openApp(row.app.id)
        Accessible.name: qsTr("Open %1").arg(row.app.name)
    }
    Controls.ToolButton {
        visible: !!row.app.installed
        icon.name: "edit-delete"
        text: qsTr("Remove")
        display: Controls.AbstractButton.IconOnly
        enabled: !backend.busy
        onClicked: backend.uninstallApp(row.app.id)
        Controls.ToolTip.text: qsTr("Remove %1").arg(row.app.name)
        Controls.ToolTip.visible: hovered
        Accessible.name: qsTr("Remove %1").arg(row.app.name)
    }
}
