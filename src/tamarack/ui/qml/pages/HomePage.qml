import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Home")

    readonly property var doc: backend.doctor
    readonly property var system: doc.system || ({})
    readonly property var upd: doc.updates || ({})
    readonly property var problems: doc.problems || []

    actions: [
        Kirigami.Action {
            text: qsTr("Refresh")
            icon.name: "view-refresh"
            onTriggered: backend.refreshDoctor()
        }
    ]

    Component.onCompleted: backend.refreshDoctor()

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        RowLayout {
            spacing: Kirigami.Units.largeSpacing * 2
            Layout.fillWidth: true
            Kirigami.Icon {
                source: backend.brand.logo
                implicitWidth: Kirigami.Units.iconSizes.huge
                implicitHeight: Kirigami.Units.iconSizes.huge
            }
            ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                Layout.fillWidth: true
                Kirigami.Heading {
                    text: page.system.name || backend.brand.name
                    level: 1
                }
                Controls.Label {
                    text: backend.brand.tagline
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                Controls.Label {
                    visible: !!page.system.version
                    text: qsTr("Version %1 · based on %2").arg(page.system.version || "").arg(page.system.based_on || "Bazzite")
                    opacity: 0.75
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            }
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: !!page.upd.restart_needed
            type: Kirigami.MessageType.Information
            text: qsTr("An update is ready. Restart whenever it suits you to finish installing it.")
            actions: [
                Kirigami.Action {
                    text: qsTr("Restart now…")
                    icon.name: "system-reboot"
                    onTriggered: restartDialog.open()
                }
            ]
        }

        SectionCard {
            title: page.problems.length === 0 ? qsTr("Everything looks good") : qsTr("Needs your attention")
            iconName: page.problems.length === 0 ? "emblem-ok-symbolic" : "dialog-warning"
            subtitle: page.problems.length === 0 && Object.keys(page.doc).length > 0
                      ? qsTr("No problems were found with updates, graphics drivers or the gaming tools.") : ""

            Repeater {
                model: page.problems
                delegate: RowLayout {
                    required property string modelData
                    Layout.fillWidth: true
                    StatusIcon { status: "attention" }
                    Controls.Label {
                        text: modelData
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }
            Controls.Label {
                visible: Object.keys(page.doc).length === 0
                text: qsTr("Checking your system…")
                opacity: 0.7
            }
        }

        Kirigami.CardsLayout {
            Layout.fillWidth: true
            maximumColumns: 3

            SectionCard {
                title: qsTr("Play")
                iconName: "input-gamepad"
                subtitle: qsTr("Steam, Proton and the gaming tools are built in.")
                Repeater {
                    model: Object.keys(page.doc.gaming || {})
                    delegate: RowLayout {
                        required property string modelData
                        StatusIcon { status: page.doc.gaming[modelData] ? "ok" : "missing" }
                        Controls.Label { text: modelData; Layout.fillWidth: true; elide: Text.ElideRight }
                    }
                }
                Controls.Button {
                    text: qsTr("Open Steam")
                    icon.name: "steam"
                    onClicked: backend.launch("steam")
                }
            }

            SectionCard {
                title: qsTr("Updates")
                iconName: "system-software-update"
                subtitle: page.upd.booted ? qsTr("Running %1 from %2").arg(page.upd.booted.version).arg(page.upd.booted.date) : ""
                Controls.Label {
                    text: page.upd.auto_updates === true ? qsTr("Automatic updates are on. Updates apply at your next restart, never on their own.")
                          : page.upd.auto_updates === false ? qsTr("Automatic updates are off.") : ""
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                Controls.Button {
                    text: qsTr("Updates & Recovery")
                    icon.name: "go-next"
                    onClicked: Controls.ApplicationWindow.window.showPage("updates")
                }
            }

            SectionCard {
                title: qsTr("Default apps")
                iconName: "plasmadiscover"
                subtitle: (page.doc.default_apps || {}).message || ""
                Controls.Button {
                    text: qsTr("Browse the app store")
                    icon.name: "plasmadiscover"
                    onClicked: backend.launch("store")
                }
                Controls.Button {
                    text: qsTr("App bundles")
                    icon.name: "go-next"
                    onClicked: Controls.ApplicationWindow.window.showPage("apps")
                }
            }
        }

        SectionCard {
            title: qsTr("Quick actions")
            Flow {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                Controls.Button {
                    text: qsTr("Change the look")
                    icon.name: "preferences-desktop-theme-global"
                    onClicked: Controls.ApplicationWindow.window.showPage("appearance")
                }
                Controls.Button {
                    text: qsTr("Check if a game works")
                    icon.name: "search"
                    onClicked: Controls.ApplicationWindow.window.showPage("gaming")
                }
                Controls.Button {
                    text: qsTr("Privacy dashboard")
                    icon.name: "preferences-system-privacy"
                    onClicked: Controls.ApplicationWindow.window.showPage("privacy")
                }
                Controls.Button {
                    text: qsTr("System monitor")
                    icon.name: "utilities-system-monitor"
                    onClicked: backend.launch("systemmonitor")
                }
                Controls.Button {
                    text: qsTr("All settings")
                    icon.name: "preferences-system"
                    onClicked: backend.launch("settings")
                }
            }
        }
    }

    Kirigami.PromptDialog {
        id: restartDialog
        title: qsTr("Restart now?")
        subtitle: qsTr("Save your work first. Open apps will close.")
        standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
        onAccepted: backend.restartNow()
    }
}
