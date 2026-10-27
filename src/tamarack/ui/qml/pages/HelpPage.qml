import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Help & About")

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        SectionCard {
            title: backend.brand.name
            iconName: backend.brand.logo
            iconMask: false
            subtitle: backend.brand.tagline
            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: qsTr("%1. Tamarack OS is an independent project. It is not affiliated with or endorsed by Bazzite, Universal Blue, Fedora, KDE, Valve or Microsoft. Free and open-source software under the Apache 2.0 license; included components keep their own licenses.").arg(backend.brand.basedOn)
            }
            Flow {
                Layout.fillWidth: true
                spacing: Kirigami.Units.largeSpacing
                Kirigami.UrlButton { text: qsTr("Documentation"); url: backend.brand.docsUrl }
                Kirigami.UrlButton { text: qsTr("Troubleshooting"); url: backend.brand.supportUrl }
                Kirigami.UrlButton { text: qsTr("Report a problem"); url: backend.brand.bugUrl }
                Kirigami.UrlButton { text: qsTr("Source code"); url: backend.brand.homeUrl }
            }
        }

        SectionCard {
            title: qsTr("Useful keyboard shortcuts")
            iconName: "input-keyboard"
            tint: Kirigami.Theme.linkColor
            ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                Layout.fillWidth: true
                Repeater {
                    model: [
                        ["Meta", qsTr("Open the start menu")],
                        ["Meta + S, or Meta + type", qsTr("Search apps, files and settings")],
                        ["Meta + Tab / Meta + W", qsTr("Overview of all windows and desktops (Task View)")],
                        ["Meta + I", qsTr("Settings")],
                        ["Meta + ← / → / ↑", qsTr("Snap a window to a side or maximize it")],
                        ["Meta + T", qsTr("Edit custom window tiling layouts")],
                        ["Meta + E", qsTr("Open the file manager")],
                        ["Meta + D", qsTr("Show the desktop")],
                        ["Meta + V", qsTr("Clipboard history")],
                        ["Meta + .", qsTr("Emoji picker")],
                        ["Ctrl + Alt + T", qsTr("Open a terminal")],
                        ["Meta + Shift + S / Print", qsTr("Take a screenshot or screen recording (Spectacle)")],
                        ["Ctrl + Shift + Esc", qsTr("System monitor (Task Manager)")],
                        ["Meta + L", qsTr("Lock the screen")],
                        ["Meta + Ctrl + ← / →", qsTr("Switch virtual desktop")],
                        ["Right Shift + F12 (in games)", qsTr("Toggle the MangoHud performance overlay")]
                    ]
                    delegate: RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.largeSpacing
                        Controls.Label {
                            text: modelData[0]
                            font.bold: true
                            textFormat: Text.PlainText
                            Layout.preferredWidth: Kirigami.Units.gridUnit * 12
                        }
                        Controls.Label {
                            text: modelData[1]
                            wrapMode: Text.WordWrap
                            textFormat: Text.PlainText
                            Layout.fillWidth: true
                        }
                    }
                }
            }
            Controls.Button {
                text: qsTr("Change shortcuts")
                icon.name: "configure-shortcuts"
                onClicked: backend.openSettings("kcm_keys")
            }
        }

        SectionCard {
            title: qsTr("Common questions")
            iconName: "help-contents"
            tint: Kirigami.Theme.positiveTextColor
            Repeater {
                model: [
                    [qsTr("How do I install apps?"), qsTr("Open the app store (Bazaar) from the start menu, or use the Apps page here. Apps come from Flathub. Advanced users can also use Distrobox containers for any Linux package.")],
                    [qsTr("A Windows game won't start."), qsTr("See Gaming > “When a game won't start”. Some online games block Linux through their anti-cheat; the game checker tells you which ones.")],
                    [qsTr("My laptop has two GPUs."), qsTr("The desktop runs on the integrated GPU to save power. Steam games normally use the faster GPU; enable MangoHud (MANGOHUD=1 %command%) to see which GPU a game uses. The troubleshooting guide explains how to force the NVIDIA GPU.")],
                    [qsTr("Secure Boot."), qsTr("The kernel and drivers are signed with Universal Blue's key. With Secure Boot on, enroll it once: accept the blue MOK screen after installing, or run “ujust enroll-secure-boot-key” in a terminal and follow the prompts at the next restart (the password is “universalblue”).")],
                    [qsTr("Can I go back to Windows?"), qsTr("If you installed Tamarack OS next to Windows, pick Windows from the boot menu. Tamarack OS never modifies a Windows installation on its own.")],
                    [qsTr("Where are advanced tools?"), qsTr("Open a terminal and run “ujust” for a menu of maintenance tasks, or “tamarack doctor” for a health report.")]
                ]
                delegate: ColumnLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 0
                    Controls.Label { text: modelData[0]; font.bold: true; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    Controls.Label { text: modelData[1]; wrapMode: Text.WordWrap; Layout.fillWidth: true; Layout.bottomMargin: Kirigami.Units.smallSpacing }
                }
            }
        }

        SectionCard {
            title: qsTr("Accessibility")
            iconName: "preferences-desktop-accessibility"
            tint: Kirigami.Theme.visitedLinkColor
            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: qsTr("Screen reader (Orca), zoom, sticky keys, larger text and reduced motion are in System Settings > Accessibility. The “High Contrast” preset on the Appearance page combines high-contrast colors, larger text and cursor, and no animations.")
            }
            Controls.Button {
                text: qsTr("Accessibility settings")
                icon.name: "preferences-desktop-accessibility"
                onClicked: backend.openSettings("kcm_access")
            }
        }
    }
}
