import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Hardware")

    readonly property var items: backend.hardware.items || []
    readonly property var categories: {
        var seen = [];
        for (var i = 0; i < items.length; ++i) {
            if (seen.indexOf(items[i].category) === -1) seen.push(items[i].category);
        }
        return seen;
    }

    actions: [
        Kirigami.Action {
            text: qsTr("Refresh")
            icon.name: "view-refresh"
            onTriggered: backend.refreshHardware()
        },
        Kirigami.Action {
            text: qsTr("Copy report")
            icon.name: "edit-copy"
            tooltip: qsTr("Copy a text report to paste into a help request")
            onTriggered: {
                var lines = [];
                for (var i = 0; i < page.items.length; ++i) {
                    var it = page.items[i];
                    lines.push("[" + it.status + "] " + it.category + ": " + it.name + (it.driver ? " (driver " + it.driver + ")" : "")
                               + (it.detail ? " - " + it.detail : ""));
                }
                reportArea.text = lines.join("\n");
                reportArea.selectAll();
                reportArea.copy();
                Controls.ApplicationWindow.window.showPassiveNotification(qsTr("Hardware report copied to the clipboard."));
            }
        },
        Kirigami.Action {
            text: qsTr("Detailed info")
            icon.name: "hwinfo"
            onTriggered: backend.openSettings("kcm_about-distro")
        }
    ]

    Component.onCompleted: backend.refreshHardware()

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("What Tamarack OS detected and which driver each device uses. Items marked “Needs attention” explain what to do.")
        }

        Kirigami.PlaceholderMessage {
            Layout.fillWidth: true
            visible: page.items.length === 0
            icon.name: "computer"
            text: backend.busy ? qsTr("Detecting hardware…") : qsTr("No hardware information yet")
        }

        Repeater {
            model: page.categories
            delegate: SectionCard {
                id: group
                required property string modelData
                title: modelData

                Repeater {
                    model: page.items.filter(it => it.category === group.modelData)
                    delegate: RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.largeSpacing
                        StatusIcon {
                            status: modelData.status
                            Layout.alignment: Qt.AlignTop
                        }
                        ColumnLayout {
                            spacing: 0
                            Layout.fillWidth: true
                            Controls.Label {
                                text: modelData.name + (modelData.driver ? "  ·  " + qsTr("driver: %1").arg(modelData.driver) : "")
                                font.bold: modelData.status !== "info"
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                            Controls.Label {
                                visible: modelData.detail.length > 0
                                text: modelData.detail
                                wrapMode: Text.WordWrap
                                opacity: 0.8
                                Layout.fillWidth: true
                            }
                            Controls.Label {
                                visible: modelData.advice.length > 0
                                text: modelData.advice
                                wrapMode: Text.WordWrap
                                color: Kirigami.Theme.neutralTextColor
                                Layout.fillWidth: true
                            }
                        }
                    }
                }
            }
        }

        // Off-screen helper used only to put the report on the clipboard.
        Controls.TextArea {
            id: reportArea
            visible: false
        }
    }
}
