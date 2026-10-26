import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Apps")

    actions: [
        Kirigami.Action {
            text: qsTr("Open app store")
            icon.name: "plasmadiscover"
            onTriggered: backend.launch("store")
        },
        Kirigami.Action {
            text: qsTr("Refresh")
            icon.name: "view-refresh"
            onTriggered: backend.refreshBundles()
        }
    ]

    Component.onCompleted: backend.refreshBundles()

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Tamarack OS installs only a browser and a few basic viewers. Add more here or in the app store. Apps come from Flathub and run in a sandbox. Nothing is installed unless you choose it, and an app you remove is never reinstalled behind your back.")
        }

        Kirigami.PlaceholderMessage {
            Layout.fillWidth: true
            visible: backend.bundles.length === 0 && !backend.busy
            icon.name: "plasmadiscover"
            text: qsTr("App bundles are not available")
            explanation: qsTr("Flatpak could not be queried. You can still use the app store.")
        }

        Kirigami.CardsLayout {
            Layout.fillWidth: true
            maximumColumns: 2

            Repeater {
                model: backend.bundles
                delegate: SectionCard {
                    id: bundleCard
                    required property var modelData
                    readonly property var missing: modelData.apps.filter(a => !a.installed).map(a => a.id)

                    title: modelData.name
                    subtitle: modelData.description

                    Repeater {
                        model: bundleCard.modelData.apps
                        delegate: RowLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            StatusIcon { status: modelData.installed ? "ok" : "info" }
                            Controls.Label {
                                text: modelData.id
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            Controls.Label {
                                text: modelData.installed ? qsTr("Installed") : ""
                                opacity: 0.7
                            }
                            Controls.ToolButton {
                                visible: modelData.installed
                                icon.name: "edit-delete"
                                text: qsTr("Remove")
                                display: Controls.AbstractButton.IconOnly
                                enabled: !backend.busy
                                onClicked: backend.uninstallApp(modelData.id)
                                Controls.ToolTip.text: qsTr("Remove %1").arg(modelData.id)
                                Controls.ToolTip.visible: hovered
                                Accessible.name: qsTr("Remove %1").arg(modelData.id)
                            }
                        }
                    }

                    Controls.Button {
                        text: bundleCard.missing.length === 0 ? qsTr("All installed")
                              : qsTr("Install %n app(s)", "", bundleCard.missing.length)
                        icon.name: "download"
                        enabled: bundleCard.missing.length > 0 && !backend.busy
                        onClicked: backend.installApps(bundleCard.missing)
                    }
                }
            }
        }
    }
}
