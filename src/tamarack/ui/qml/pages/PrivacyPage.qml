import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Privacy")

    readonly property var report: backend.privacy
    readonly property var toggles: report.toggles || ({})
    readonly property var exposed: (report.listeners || []).filter(l => !(l.address.startsWith("127.") || l.address === "::1"))

    actions: [
        Kirigami.Action {
            text: qsTr("Refresh")
            icon.name: "view-refresh"
            onTriggered: backend.refreshPrivacy()
        }
    ]

    Component.onCompleted: backend.refreshPrivacy()

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Tamarack OS has no ads, no advertising ID and no hidden tracking. Some parts of the system still need the internet; everything that does is listed below with a way to turn it off where possible.")
        }

        SectionCard {
            title: qsTr("Your choices")
            iconName: "security-high"
            tint: Kirigami.Theme.visitedLinkColor

            Repeater {
                model: [
                    { key: "countme", title: qsTr("Help Fedora count installations"), body: qsTr("A weekly request with your OS version and no unique ID. Off by default.") },
                    { key: "connectivity", title: qsTr("Detect Wi-Fi sign-in pages"), body: qsTr("Periodically loads a small file from fedoraproject.org so hotel and airport Wi-Fi login pages open automatically.") },
                    { key: "store_search", title: qsTr("Show app store results in search"), body: qsTr("The launcher suggests installable apps from the local Flathub catalog. Nothing you type is sent anywhere.") },
                    { key: "recent_files", title: qsTr("Remember recently opened files"), body: qsTr("Lets the start menu and file dialogs show recent files. Stored only on this computer.") }
                ]
                delegate: RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    ColumnLayout {
                        spacing: 0
                        Layout.fillWidth: true
                        Controls.Label { text: modelData.title; font.bold: true; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                        Controls.Label { text: modelData.body; wrapMode: Text.WordWrap; opacity: 0.8; Layout.fillWidth: true }
                    }
                    Controls.Switch {
                        checked: page.toggles[modelData.key] === true
                        enabled: page.toggles[modelData.key] !== null && page.toggles[modelData.key] !== undefined && !backend.busy
                        onToggled: backend.setPrivacyToggle(modelData.key, checked)
                        Accessible.name: modelData.title
                    }
                }
            }
            Controls.Button {
                text: qsTr("Recent files settings")
                icon.name: "document-open-recent"
                onClicked: backend.openSettings("kcm_recentFiles")
            }
        }

        SectionCard {
            title: qsTr("App permissions")
            iconName: "preferences-security"
            tint: Kirigami.Theme.linkColor
            subtitle: qsTr("Store apps (Flatpak) run in a sandbox. Apps that ship with the OS are not sandboxed and can access what your account can.")

            Repeater {
                model: page.report.apps || []
                delegate: RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Icon {
                        source: modelData.icon ? "file://" + modelData.icon : modelData.app_id
                        fallback: "application-x-executable"
                        implicitWidth: Kirigami.Units.iconSizes.smallMedium
                        implicitHeight: Kirigami.Units.iconSizes.smallMedium
                        Accessible.ignored: true
                    }
                    ColumnLayout {
                        spacing: 0
                        Layout.fillWidth: true
                        Controls.Label {
                            text: modelData.name || modelData.app_id
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        Controls.Label {
                            text: modelData.files
                            opacity: 0.7
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }
                    Repeater {
                        model: [
                            { on: modelData.camera, label: qsTr("Camera"), icon: "camera-web" },
                            { on: modelData.microphone, label: qsTr("Microphone/audio"), icon: "audio-input-microphone" },
                            { on: modelData.location, label: qsTr("Location"), icon: "mark-location" },
                            { on: modelData.network, label: qsTr("Internet"), icon: "network-wired" }
                        ].filter(p => p.on)
                        delegate: Kirigami.Icon {
                            required property var modelData
                            source: modelData.icon
                            implicitWidth: Kirigami.Units.iconSizes.small
                            implicitHeight: Kirigami.Units.iconSizes.small
                            Accessible.name: modelData.label
                            Controls.ToolTip.text: modelData.label
                            Controls.ToolTip.visible: hover.hovered
                            HoverHandler { id: hover }
                        }
                    }
                }
            }
            Controls.Button {
                text: qsTr("Change app permissions")
                icon.name: "configure"
                onClicked: backend.openSettings("kcm_app-permissions")
            }
        }

        SectionCard {
            title: qsTr("Apps that start automatically")
            iconName: "system-run"
            tint: Kirigami.Theme.positiveTextColor
            Repeater {
                model: page.report.autostart || []
                delegate: RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    StatusIcon { level: modelData.enabled ? "ok" : "info" }
                    Controls.Label { text: modelData.name; Layout.fillWidth: true; elide: Text.ElideRight }
                    Controls.Label { text: modelData.enabled ? qsTr("On") : qsTr("Off"); opacity: 0.75 }
                }
            }
            Controls.Button {
                text: qsTr("Manage startup apps")
                icon.name: "configure"
                onClicked: backend.openSettings("kcm_autostart")
            }
        }

        SectionCard {
            title: qsTr("What connects to the internet, and why")
            iconName: "network-connect"
            tint: Kirigami.Theme.linkColor
            Repeater {
                model: page.report.network_catalog || []
                delegate: ColumnLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 0
                    Controls.Label { text: modelData.name + "  ·  " + modelData.who; font.bold: true; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    Controls.Label { text: modelData.what; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    Controls.Label {
                        text: (modelData.optional ? qsTr("Optional. ") : qsTr("Required. ")) + qsTr("Why: %1").arg(modelData.why) + (modelData.control ? "  " + qsTr("Control: %1").arg(modelData.control) : "")
                        wrapMode: Text.WordWrap
                        opacity: 0.75
                        Layout.fillWidth: true
                        Layout.bottomMargin: Kirigami.Units.smallSpacing
                    }
                }
            }
        }

        SectionCard {
            title: qsTr("Open network ports")
            iconName: "network-server"
            tint: Kirigami.Theme.neutralTextColor
            subtitle: page.exposed.length === 0 ? qsTr("No program is accepting connections from other devices. The firewall is on.")
                                                : qsTr("These programs accept connections from other devices (the firewall may still block them):")
            Repeater {
                model: page.exposed
                delegate: Controls.Label {
                    required property var modelData
                    text: "%1 %2:%3  %4".arg(modelData.protocol).arg(modelData.address).arg(modelData.port).arg(modelData.process)
                    font.family: "monospace"
                }
            }
            Controls.Button {
                text: qsTr("Firewall settings")
                icon.name: "security-high"
                onClicked: backend.openSettings("kcm_firewall")
            }
        }

        SectionCard {
            title: qsTr("Background services")
            iconName: "system-run"
            tint: Kirigami.Theme.visitedLinkColor
            subtitle: qsTr("Enabled system services. Ones Tamarack knows about are explained; others show their technical name.")
            Repeater {
                model: (page.report.services || []).filter(s => s.known)
                delegate: ColumnLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 0
                    Controls.Label { text: modelData.name + "  (" + modelData.unit + ")"; font.bold: true; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    Controls.Label {
                        text: modelData.purpose + (modelData.safe_to_disable === true ? "  " + qsTr("Safe to turn off.") : modelData.safe_to_disable === false ? "  " + qsTr("Needed for the system to work properly.") : "")
                        wrapMode: Text.WordWrap
                        opacity: 0.8
                        Layout.fillWidth: true
                    }
                }
            }
            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                opacity: 0.7
                text: qsTr("Other enabled services: %1").arg((page.report.services || []).filter(s => !s.known).map(s => s.unit).join(", "))
            }
        }
    }
}
