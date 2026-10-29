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
    readonly property var tools: doc.gaming || ({})
    readonly property int toolsReady: Object.keys(tools).filter(k => tools[k]).length
    readonly property bool checked: Object.keys(doc).length > 0
    readonly property bool wide: width > Kirigami.Units.gridUnit * 40

    function go(name) {
        Controls.ApplicationWindow.window.showPage(name);
    }

    actions: [
        Kirigami.Action {
            text: qsTr("Refresh")
            icon.name: "view-refresh"
            onTriggered: backend.refreshDoctor()
        }
    ]

    Component.onCompleted: backend.refreshDoctor()

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        HeroBanner {
            title: page.system.name || backend.brand.name
            subtitle: backend.brand.tagline

            Pill {
                visible: !!page.system.version
                text: qsTr("Version %1").arg(page.system.version || "")
                tint: "white"
                fill: 0.2
            }
            Pill {
                visible: page.checked
                text: page.problems.length === 0 ? qsTr("Everything looks good")
                      : page.problems.length === 1 ? qsTr("1 thing needs attention")
                      : qsTr("%1 things need attention").arg(page.problems.length)
                iconName: page.problems.length === 0 ? "checkmark" : "dialog-warning"
                tint: "white"
                fill: 0.2
            }
            Pill {
                visible: !page.checked
                text: qsTr("Checking your system…")
                tint: "white"
                fill: 0.2
            }
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: !!page.upd.restart_needed
            type: Kirigami.MessageType.Information
            text: page.upd.staged ? qsTr("An update is ready. Restart whenever it suits you to finish installing it.")
                                  : qsTr("%1 starts at the next restart.").arg(page.upd.next_boot ? page.upd.next_boot.version : "")
            actions: [
                Kirigami.Action {
                    text: qsTr("Restart now…")
                    icon.name: "system-reboot"
                    onTriggered: restartDialog.open()
                }
            ]
        }

        SectionCard {
            visible: page.problems.length > 0
            title: qsTr("Needs your attention")
            iconName: "dialog-warning"
            tint: Kirigami.Theme.neutralTextColor

            Repeater {
                model: page.problems
                delegate: RowLayout {
                    required property string modelData
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing
                    StatusIcon {
                        level: "attention"
                        Layout.alignment: Qt.AlignTop
                    }
                    Controls.Label {
                        text: modelData
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }
            Controls.Button {
                text: qsTr("Hardware details")
                icon.name: "computer"
                onClicked: page.go("hardware")
            }
        }

        GridLayout {
            columns: page.wide ? 2 : 1
            columnSpacing: Kirigami.Units.largeSpacing * 2
            rowSpacing: Kirigami.Units.largeSpacing * 2
            Layout.fillWidth: true

            SectionCard {
                title: qsTr("Play")
                subtitle: qsTr("Steam, Proton and the gaming tools are built in.")
                iconName: "input-gamepad"
                tint: Kirigami.Theme.neutralTextColor
                Layout.preferredWidth: 1
                Layout.fillHeight: true

                RowLayout {
                    visible: Object.keys(page.tools).length > 0
                    spacing: Kirigami.Units.smallSpacing
                    StatusIcon { level: page.toolsReady === Object.keys(page.tools).length ? "ok" : "attention" }
                    Controls.Label {
                        text: qsTr("%1 of %2 gaming tools ready").arg(page.toolsReady).arg(Object.keys(page.tools).length)
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }
                }
                RowLayout {
                    spacing: Kirigami.Units.smallSpacing
                    PrimaryButton {
                        text: qsTr("Open Steam")
                        icon.name: "media-playback-start"
                        onClicked: backend.launch("steam")
                    }
                    Controls.Button {
                        text: qsTr("Gaming tools")
                        onClicked: page.go("gaming")
                    }
                }
            }

            SectionCard {
                title: qsTr("Updates")
                subtitle: page.upd.booted ? qsTr("Running %1, released %2").arg(page.upd.booted.version).arg(page.upd.booted.date) : ""
                iconName: "system-software-update"
                Layout.preferredWidth: 1
                Layout.fillHeight: true

                Controls.Label {
                    text: page.upd.auto_updates === true ? qsTr("Automatic updates are on. They apply when you restart, never on their own.")
                          : page.upd.auto_updates === false ? qsTr("Automatic updates are off.") : ""
                    visible: text.length > 0
                    wrapMode: Text.WordWrap
                    opacity: 0.85
                    Layout.fillWidth: true
                }
                Controls.Button {
                    text: qsTr("Updates && Recovery")
                    onClicked: page.go("updates")
                }
            }

            SectionCard {
                title: qsTr("Apps and games")
                subtitle: (page.doc.default_apps || {}).message || qsTr("Thousands of apps from Flathub, installed in a sandbox.")
                iconName: "download"
                tint: Kirigami.Theme.linkColor
                Layout.preferredWidth: 1
                Layout.fillHeight: true

                RowLayout {
                    spacing: Kirigami.Units.smallSpacing
                    Controls.Button {
                        text: qsTr("Find apps")
                        icon.name: "search"
                        onClicked: page.go("apps")
                    }
                    Controls.Button {
                        text: qsTr("App store")
                        onClicked: backend.launch("store")
                    }
                }
            }

            SectionCard {
                title: qsTr("Privacy")
                subtitle: qsTr("No ads and no advertising ID. See everything that uses the internet and decide what is shared.")
                iconName: "security-high"
                tint: Kirigami.Theme.visitedLinkColor
                Layout.preferredWidth: 1
                Layout.fillHeight: true

                Controls.Button {
                    text: qsTr("Privacy dashboard")
                    onClicked: page.go("privacy")
                }
            }
        }

        Kirigami.Heading {
            text: qsTr("Quick actions")
            level: 2
            Layout.topMargin: Kirigami.Units.largeSpacing
        }

        GridLayout {
            columns: page.width > Kirigami.Units.gridUnit * 52 ? 3 : page.wide ? 2 : 1
            columnSpacing: Kirigami.Units.largeSpacing * 2
            rowSpacing: Kirigami.Units.largeSpacing * 2
            Layout.fillWidth: true

            Repeater {
                model: [
                    { title: qsTr("Change the look"), text: qsTr("Presets, colors and taskbar"), icon: "draw-brush", tint: Kirigami.Theme.visitedLinkColor, page: "appearance" },
                    { title: qsTr("Will this game work?"), text: qsTr("Check anti-cheat support"), icon: "input-gamepad", tint: Kirigami.Theme.neutralTextColor, page: "gaming" },
                    { title: qsTr("Hardware and drivers"), text: qsTr("Graphics, Wi-Fi, audio, battery"), icon: "computer", tint: Kirigami.Theme.linkColor, page: "hardware" },
                    { title: qsTr("System monitor"), text: qsTr("What is using your computer"), icon: "office-chart-line", tint: Kirigami.Theme.positiveTextColor, launch: "systemmonitor" },
                    { title: qsTr("All settings"), text: qsTr("Displays, sound, network, accounts"), icon: "configure", tint: Kirigami.Theme.highlightColor, launch: "settings" },
                    { title: qsTr("Help and tips"), text: qsTr("Shortcuts and where to get help"), icon: "help-about", tint: Kirigami.Theme.linkColor, page: "help" }
                ]
                delegate: ActionTile {
                    required property var modelData
                    title: modelData.title
                    description: modelData.text
                    iconName: modelData.icon
                    tint: modelData.tint
                    Layout.preferredWidth: 1
                    Layout.fillHeight: true
                    onClicked: modelData.page ? page.go(modelData.page) : backend.launch(modelData.launch)
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
