import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Updates & Recovery")

    readonly property var st: backend.updates
    readonly property var booted: st.booted || null
    readonly property var staged: st.staged || null
    readonly property var previous: st.rollback || null

    actions: [
        Kirigami.Action {
            text: qsTr("Update now")
            icon.name: "system-software-update"
            enabled: !backend.busy && !(page.st.low_space)
            onTriggered: backend.updateNow()
        },
        Kirigami.Action {
            text: qsTr("Refresh")
            icon.name: "view-refresh"
            onTriggered: backend.refreshUpdates()
        }
    ]

    Component.onCompleted: backend.refreshUpdates()

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: !!page.st.low_space
            type: Kirigami.MessageType.Warning
            text: qsTr("Less than 10 GB is free on the system drive. Free up space before updating; an update needs room for a complete second copy of changed system files.")
        }

        Repeater {
            model: page.st.errors || []
            delegate: Kirigami.InlineMessage {
                required property string modelData
                Layout.fillWidth: true
                visible: true
                type: Kirigami.MessageType.Error
                text: modelData
            }
        }

        SectionCard {
            title: page.booted && page.booted.version ? qsTr("You're running %1").arg(page.booted.version) : qsTr("Current version")
            iconName: "system-software-update"
            subtitle: page.booted ? qsTr("Released %1 · %2").arg(page.booted.date).arg(page.booted.image) : ""

            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: qsTr("Updates download a complete new version of the system next to the one you are using. Nothing changes until you restart, and the previous version stays available in case something goes wrong. Your files and settings are kept.")
            }

            RowLayout {
                Controls.Label {
                    text: qsTr("Automatic updates")
                    Layout.fillWidth: true
                }
                Controls.Switch {
                    checked: page.st.auto_updates === true
                    enabled: page.st.auto_updates !== null && page.st.auto_updates !== undefined && !backend.busy
                    onToggled: backend.setAutoUpdates(checked)
                    Accessible.name: qsTr("Automatic updates")
                }
            }
            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                opacity: 0.75
                text: qsTr("Automatic updates download in the background and apply at your next restart. The computer never restarts on its own.")
            }
        }

        SectionCard {
            visible: page.staged !== null
            title: qsTr("Update ready: %1").arg(page.staged ? page.staged.version : "")
            iconName: "system-reboot"
            tint: Kirigami.Theme.neutralTextColor
            subtitle: qsTr("Restart whenever it suits you to start using it.")
            Controls.Button {
                text: qsTr("Restart now…")
                icon.name: "system-reboot"
                onClicked: restartDialog.open()
            }
        }

        SectionCard {
            title: qsTr("Go back to the previous version")
            iconName: "edit-undo"
            tint: Kirigami.Theme.linkColor
            subtitle: page.previous ? (page.previous.version ? qsTr("Previous version: %1 (%2)").arg(page.previous.version).arg(page.previous.date)
                                                             : qsTr("Previous version from %1").arg(page.previous.date))
                                    : qsTr("No previous version is available yet.")
            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: qsTr("If an update causes problems, roll back to the version you had before. Rollback switches the operating system only: it does not undo changes to your personal files, and apps from the app store keep their current versions.")
            }
            RowLayout {
                Controls.Button {
                    text: qsTr("Roll back…")
                    icon.name: "edit-undo"
                    enabled: page.previous !== null && !backend.busy
                    onClicked: rollbackDialog.open()
                }
                Controls.Button {
                    text: qsTr("Keep this version")
                    icon.name: "window-pin"
                    enabled: !backend.busy && page.booted !== null
                    onClicked: backend.pinCurrent()
                    Controls.ToolTip.text: qsTr("Pin the running version so it is never removed by later updates.")
                    Controls.ToolTip.visible: hovered
                }
            }
        }

        SectionCard {
            title: qsTr("If the computer won't start")
            iconName: "tools-wizard"
            tint: Kirigami.Theme.negativeTextColor
            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                textFormat: Text.StyledText
                text: qsTr("Turn the computer on and keep tapping <b>Esc</b> (or hold <b>Shift</b>) to show the boot menu. Choose the second entry to start the previous version, then use “Roll back” here to keep it. Full steps are in the troubleshooting guide.")
            }
            Kirigami.UrlButton {
                text: qsTr("Troubleshooting guide")
                url: backend.brand.supportUrl
            }
        }

        SectionCard {
            title: qsTr("Update history")
            iconName: "view-history"
            tint: Kirigami.Theme.visitedLinkColor
            Repeater {
                model: (page.st.history || []).slice().reverse()
                delegate: RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    StatusIcon { level: modelData.result === "success" ? "ok" : "missing" }
                    Controls.Label { text: modelData.time; Layout.preferredWidth: Kirigami.Units.gridUnit * 10 }
                    Controls.Label { text: modelData.message; elide: Text.ElideRight; Layout.fillWidth: true }
                }
            }
            Controls.Label {
                visible: (page.st.history || []).length === 0
                text: qsTr("No automatic update runs recorded in the last 90 days.")
                opacity: 0.7
            }
        }

        SectionCard {
            title: qsTr("Back up your files")
            iconName: "backup"
            tint: Kirigami.Theme.positiveTextColor
            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: qsTr("System rollback protects the operating system, not your documents. Use a backup app to keep copies of your files on another drive or in the cloud.")
            }
            Controls.Button {
                text: qsTr("Install Déjà Dup Backups")
                icon.name: "download"
                enabled: !backend.busy
                onClicked: backend.installApps(["org.gnome.DejaDup"])
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

    Kirigami.PromptDialog {
        id: rollbackDialog
        title: qsTr("Roll back to %1?").arg(page.previous ? page.previous.version : "")
        subtitle: qsTr("The previous system version will start the next time you restart. Your personal files are not changed. You can update again later.")
        standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
        onAccepted: backend.rollback()
    }
}
