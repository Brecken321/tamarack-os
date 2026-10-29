import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Dialogs as Dialogs
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Appearance")

    property string exportId: ""

    actions: [
        Kirigami.Action {
            text: qsTr("Undo last change")
            icon.name: "edit-undo"
            enabled: backend.backups.length > 0 && !backend.busy
            onTriggered: backend.undoAppearance()
        },
        Kirigami.Action {
            text: qsTr("Reset to default")
            icon.name: "edit-reset"
            enabled: !backend.busy
            onTriggered: resetDialog.open()
        },
        Kirigami.Action {
            text: qsTr("Import…")
            icon.name: "document-import"
            onTriggered: importDialog.open()
        }
    ]

    Component.onCompleted: backend.refreshPresets()

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Presets change the real desktop: theme, taskbar position and style, start menu, animations, fonts, window buttons and more. Your previous setup is saved first, so you can always undo.")
        }

        // CardsLayout sizes rows after the descriptions wrap; a plain grid
        // can squeeze them away.
        Kirigami.CardsLayout {
            Layout.fillWidth: true
            maximumColumns: 3

            Repeater {
                model: backend.presets
                delegate: PresetCard {
                    id: card
                    required property var modelData
                    preset: modelData
                    // Same base width for every card, so the columns come out equal.
                    Layout.preferredWidth: Kirigami.Units.gridUnit * 20

                    actions: [
                        Kirigami.Action {
                            text: card.modelData.current ? qsTr("Re-apply") : qsTr("Apply")
                            icon.name: "dialog-ok-apply"
                            enabled: !backend.busy
                            onTriggered: backend.applyPreset(card.modelData.id)
                        },
                        Kirigami.Action {
                            text: qsTr("Customize…")
                            icon.name: "document-edit"
                            onTriggered: customizeSheet.openFor(card.modelData)
                        },
                        Kirigami.Action {
                            text: qsTr("Export…")
                            icon.name: "document-export"
                            displayHint: Kirigami.DisplayHint.AlwaysHide
                            onTriggered: {
                                page.exportId = card.modelData.id;
                                exportDialog.open();
                            }
                        },
                        Kirigami.Action {
                            text: qsTr("Delete")
                            icon.name: "edit-delete"
                            visible: !card.modelData.builtin
                            displayHint: Kirigami.DisplayHint.AlwaysHide
                            onTriggered: backend.deleteCustomPreset(card.modelData.id)
                        }
                    ]
                }
            }
        }

        SectionCard {
            title: qsTr("Fine-tune in System Settings")
            iconName: "configure"
            tint: Kirigami.Theme.visitedLinkColor
            subtitle: qsTr("Every option is also available in KDE System Settings, where you can change it individually.")
            Flow {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: [
                        { text: qsTr("Colors & accent"), icon: "preferences-desktop-color", kcm: "kcm_colors" },
                        { text: qsTr("Global theme"), icon: "preferences-desktop-theme-global", kcm: "kcm_lookandfeel" },
                        { text: qsTr("Fonts"), icon: "preferences-desktop-font", kcm: "kcm_fonts" },
                        { text: qsTr("Icons"), icon: "preferences-desktop-icons", kcm: "kcm_icons" },
                        { text: qsTr("Cursors"), icon: "preferences-cursors", kcm: "kcm_cursortheme" },
                        { text: qsTr("Wallpaper & desktop"), icon: "preferences-desktop-wallpaper", kcm: "kcm_wallpaper" },
                        { text: qsTr("Window decorations"), icon: "preferences-system-windows-actions", kcm: "kcm_kwindecoration" },
                        { text: qsTr("Desktop effects"), icon: "preferences-desktop-effects", kcm: "kcm_kwin_effects" },
                        { text: qsTr("Animations"), icon: "preferences-desktop-animations", kcm: "kcm_workspace" },
                        { text: qsTr("Virtual desktops"), icon: "preferences-desktop-virtual", kcm: "kcm_kwin_virtualdesktops" },
                        { text: qsTr("Shortcuts"), icon: "preferences-desktop-keyboard-shortcut", kcm: "kcm_keys" }
                    ]
                    delegate: Controls.Button {
                        required property var modelData
                        text: modelData.text
                        icon.name: modelData.icon
                        onClicked: backend.openSettings(modelData.kcm)
                    }
                }
            }
            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                opacity: 0.8
                text: qsTr("To edit the taskbar directly, right-click it and choose “Enter Edit Mode”. Widgets can be added from the desktop's right-click menu.")
            }
        }

        SectionCard {
            title: qsTr("Behavior")
            iconName: "input-mouse"
            tint: Kirigami.Theme.linkColor
            subtitle: qsTr("How the computer reacts: power button and lid, notifications, default apps, input devices and windows.")
            Flow {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: [
                        { text: qsTr("Power button, lid & sleep"), icon: "preferences-system-power-management", kcm: "kcm_powerdevilprofilesconfig" },
                        { text: qsTr("Notifications"), icon: "preferences-desktop-notification-bell", kcm: "kcm_notifications" },
                        { text: qsTr("Default apps"), icon: "preferences-desktop-default-applications", kcm: "kcm_componentchooser" },
                        { text: qsTr("Startup apps"), icon: "system-run", kcm: "kcm_autostart" },
                        { text: qsTr("Window focus & snapping"), icon: "preferences-system-windows-behavior", kcm: "kcm_kwinoptions" },
                        { text: qsTr("Displays"), icon: "preferences-desktop-display", kcm: "kcm_kscreen" },
                        { text: qsTr("Touchpad"), icon: "input-touchpad", kcm: "kcm_touchpad" },
                        { text: qsTr("Mouse"), icon: "input-mouse", kcm: "kcm_mouse" },
                        { text: qsTr("File manager & desktop folders"), icon: "system-file-manager", kcm: "kcm_desktoppaths" }
                    ]
                    delegate: Controls.Button {
                        required property var modelData
                        text: modelData.text
                        icon.name: modelData.icon
                        onClicked: backend.openSettings(modelData.kcm)
                    }
                }
            }
        }
    }

    Kirigami.PromptDialog {
        id: resetDialog
        title: qsTr("Reset appearance?")
        subtitle: qsTr("This applies the default “Clean Modern” look. Only appearance and layout settings change; your files, apps and other preferences are not touched. You can undo it afterwards.")
        standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
        onAccepted: backend.resetAppearance()
    }

    Dialogs.FileDialog {
        id: exportDialog
        title: qsTr("Export preset")
        fileMode: Dialogs.FileDialog.SaveFile
        nameFilters: [qsTr("Tamarack preset (*.json)")]
        defaultSuffix: "json"
        onAccepted: backend.exportPreset(page.exportId, selectedFile.toString())
    }

    Dialogs.FileDialog {
        id: importDialog
        title: qsTr("Import preset")
        fileMode: Dialogs.FileDialog.OpenFile
        nameFilters: [qsTr("Tamarack preset (*.json)")]
        onAccepted: backend.importPreset(selectedFile.toString())
    }

    Kirigami.OverlaySheet {
        id: customizeSheet
        title: qsTr("Customize")

        property var form: ({})
        property string previewUrl: ""
        property string error: ""

        function openFor(preset) {
            form = {
                base: preset.id,
                name: preset.builtin ? qsTr("My %1").arg(preset.name) : preset.name,
                mode: preset.mode, wallpaper: preset.wallpaper, fontSize: preset.fontSize,
                cursorSize: preset.cursorSize, animation: preset.animation, blur: preset.blur,
                location: preset.location, thickness: preset.thickness, floating: preset.floating,
                lengthMode: preset.lengthMode, alignment: preset.alignment, hiding: preset.hiding,
                launcher: preset.launcher, taskManager: preset.taskManager,
                virtualDesktops: preset.virtualDesktops, steamAutostart: preset.steamAutostart
            };
            error = "";
            refresh();
            open();
        }
        function set(key, value) {
            var copy = Object.assign({}, form);
            copy[key] = value;
            form = copy;
            refresh();
        }
        function refresh() {
            previewUrl = backend.previewCustom(form);
        }

        ColumnLayout {
            spacing: Kirigami.Units.largeSpacing
            Layout.preferredWidth: Kirigami.Units.gridUnit * 34

            Image {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: Kirigami.Units.gridUnit * 24
                Layout.preferredHeight: Layout.preferredWidth * 9 / 16
                source: customizeSheet.previewUrl
                fillMode: Image.PreserveAspectFit
                sourceSize.width: 480
                sourceSize.height: 270
                Accessible.name: qsTr("Preview of your custom desktop")
            }

            Kirigami.FormLayout {
                Layout.fillWidth: true

                Controls.TextField {
                    Kirigami.FormData.label: qsTr("Name:")
                    Accessible.name: Kirigami.FormData.label
                    text: customizeSheet.form.name || ""
                    onEditingFinished: customizeSheet.set("name", text)
                }

                Kirigami.Separator { Kirigami.FormData.isSection: true; Kirigami.FormData.label: qsTr("Look") }

                Controls.ComboBox {
                    Kirigami.FormData.label: qsTr("Theme:")
                    Accessible.name: Kirigami.FormData.label
                    textRole: "text"; valueRole: "value"
                    model: [
                        { text: qsTr("Automatic (light by day, dark at night)"), value: "auto" },
                        { text: qsTr("Light"), value: "light" },
                        { text: qsTr("Dark"), value: "dark" },
                        { text: qsTr("High contrast"), value: "high-contrast" }
                    ]
                    currentIndex: Math.max(0, indexOfValue(customizeSheet.form.mode))
                    onActivated: customizeSheet.set("mode", currentValue)
                }
                Controls.ComboBox {
                    Kirigami.FormData.label: qsTr("Wallpaper:")
                    Accessible.name: Kirigami.FormData.label
                    model: ["Tamarack-Ridge", "Tamarack-Dusk", "Tamarack-Mist"]
                    currentIndex: Math.max(0, model.indexOf(customizeSheet.form.wallpaper))
                    onActivated: customizeSheet.set("wallpaper", currentText)
                }
                Controls.SpinBox {
                    Kirigami.FormData.label: qsTr("Text size (pt):")
                    Accessible.name: Kirigami.FormData.label
                    from: 8; to: 20
                    value: customizeSheet.form.fontSize || 10
                    onValueModified: customizeSheet.set("fontSize", value)
                }
                Controls.ComboBox {
                    Kirigami.FormData.label: qsTr("Cursor size:")
                    Accessible.name: Kirigami.FormData.label
                    model: [24, 30, 36, 48]
                    currentIndex: Math.max(0, model.indexOf(customizeSheet.form.cursorSize))
                    onActivated: customizeSheet.set("cursorSize", model[currentIndex])
                }
                Controls.ComboBox {
                    Kirigami.FormData.label: qsTr("Animations:")
                    Accessible.name: Kirigami.FormData.label
                    textRole: "text"; valueRole: "value"
                    model: [
                        { text: qsTr("Off"), value: 0.0 },
                        { text: qsTr("Fast"), value: 0.5 },
                        { text: qsTr("Normal"), value: 1.0 },
                        { text: qsTr("Slow"), value: 2.0 }
                    ]
                    currentIndex: Math.max(0, indexOfValue(customizeSheet.form.animation))
                    onActivated: customizeSheet.set("animation", currentValue)
                }
                Controls.Switch {
                    Kirigami.FormData.label: qsTr("Blur behind panels and menus:")
                    Accessible.name: Kirigami.FormData.label
                    checked: !!customizeSheet.form.blur
                    onToggled: customizeSheet.set("blur", checked)
                }

                Kirigami.Separator { Kirigami.FormData.isSection: true; Kirigami.FormData.label: qsTr("Taskbar") }

                Controls.ComboBox {
                    Kirigami.FormData.label: qsTr("Position:")
                    Accessible.name: Kirigami.FormData.label
                    textRole: "text"; valueRole: "value"
                    model: [
                        { text: qsTr("Bottom"), value: "bottom" }, { text: qsTr("Top"), value: "top" },
                        { text: qsTr("Left"), value: "left" }, { text: qsTr("Right"), value: "right" }
                    ]
                    currentIndex: Math.max(0, indexOfValue(customizeSheet.form.location))
                    onActivated: customizeSheet.set("location", currentValue)
                }
                Controls.SpinBox {
                    Kirigami.FormData.label: qsTr("Size (px):")
                    Accessible.name: Kirigami.FormData.label
                    from: 28; to: 96; stepSize: 2
                    value: customizeSheet.form.thickness || 44
                    onValueModified: customizeSheet.set("thickness", value)
                }
                Controls.ComboBox {
                    Kirigami.FormData.label: qsTr("Style:")
                    Accessible.name: Kirigami.FormData.label
                    textRole: "text"; valueRole: "value"
                    model: [
                        { text: qsTr("Full width"), value: "fill" },
                        { text: qsTr("Dock (fits its content)"), value: "fit" }
                    ]
                    currentIndex: Math.max(0, indexOfValue(customizeSheet.form.lengthMode))
                    onActivated: customizeSheet.set("lengthMode", currentValue)
                }
                Controls.ComboBox {
                    Kirigami.FormData.label: qsTr("Alignment:")
                    Accessible.name: Kirigami.FormData.label
                    textRole: "text"; valueRole: "value"
                    model: [
                        { text: qsTr("Start"), value: "left" }, { text: qsTr("Center"), value: "center" },
                        { text: qsTr("End"), value: "right" }
                    ]
                    currentIndex: Math.max(0, indexOfValue(customizeSheet.form.alignment))
                    onActivated: customizeSheet.set("alignment", currentValue)
                }
                Controls.Switch {
                    Kirigami.FormData.label: qsTr("Floating:")
                    Accessible.name: Kirigami.FormData.label
                    checked: !!customizeSheet.form.floating
                    onToggled: customizeSheet.set("floating", checked)
                }
                Controls.ComboBox {
                    Kirigami.FormData.label: qsTr("Hide:")
                    Accessible.name: Kirigami.FormData.label
                    textRole: "text"; valueRole: "value"
                    model: [
                        { text: qsTr("Always visible"), value: "none" },
                        { text: qsTr("Auto-hide"), value: "autohide" },
                        { text: qsTr("Move out of the way of windows"), value: "dodgewindows" }
                    ]
                    currentIndex: Math.max(0, indexOfValue(customizeSheet.form.hiding))
                    onActivated: customizeSheet.set("hiding", currentValue)
                }
                Controls.ComboBox {
                    Kirigami.FormData.label: qsTr("App launcher:")
                    Accessible.name: Kirigami.FormData.label
                    textRole: "text"; valueRole: "value"
                    model: [
                        { text: qsTr("Start menu"), value: "kickoff" },
                        { text: qsTr("Classic menu"), value: "kicker" },
                        { text: qsTr("Full-screen app grid"), value: "kickerdash" }
                    ]
                    currentIndex: Math.max(0, indexOfValue(customizeSheet.form.launcher))
                    onActivated: customizeSheet.set("launcher", currentValue)
                }
                Controls.ComboBox {
                    Kirigami.FormData.label: qsTr("Running apps:")
                    Accessible.name: Kirigami.FormData.label
                    textRole: "text"; valueRole: "value"
                    model: [
                        { text: qsTr("Icons only"), value: "icontasks" },
                        { text: qsTr("Icons and window titles"), value: "tasks" }
                    ]
                    currentIndex: Math.max(0, indexOfValue(customizeSheet.form.taskManager))
                    onActivated: customizeSheet.set("taskManager", currentValue)
                }

                Kirigami.Separator { Kirigami.FormData.isSection: true; Kirigami.FormData.label: qsTr("Behavior") }

                Controls.SpinBox {
                    Kirigami.FormData.label: qsTr("Virtual desktops:")
                    Accessible.name: Kirigami.FormData.label
                    from: 1; to: 8
                    value: customizeSheet.form.virtualDesktops || 1
                    onValueModified: customizeSheet.set("virtualDesktops", value)
                }
                Controls.Switch {
                    Kirigami.FormData.label: qsTr("Start Steam at login:")
                    Accessible.name: Kirigami.FormData.label
                    checked: !!customizeSheet.form.steamAutostart
                    onToggled: customizeSheet.set("steamAutostart", checked)
                }
            }

            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: customizeSheet.error.length > 0
                type: Kirigami.MessageType.Error
                text: customizeSheet.error
            }
        }

        footer: RowLayout {
            Item { Layout.fillWidth: true }
            Controls.Button {
                text: qsTr("Save")
                icon.name: "document-save"
                onClicked: {
                    customizeSheet.error = backend.saveCustomPreset(customizeSheet.form, false);
                    if (customizeSheet.error.length === 0) customizeSheet.close();
                }
            }
            Controls.Button {
                text: qsTr("Save and apply")
                icon.name: "dialog-ok-apply"
                enabled: !backend.busy
                onClicked: {
                    customizeSheet.error = backend.saveCustomPreset(customizeSheet.form, true);
                    if (customizeSheet.error.length === 0) customizeSheet.close();
                }
            }
        }
    }
}
