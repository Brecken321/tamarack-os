// Numbered steps with titles for the Welcome flow: done steps show a check,
// the current one is filled with the accent color.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

RowLayout {
    id: indicator
    property var titles: []
    property int current: 0

    spacing: Kirigami.Units.smallSpacing
    Accessible.role: Accessible.ProgressBar
    Accessible.name: qsTr("Step %1 of %2: %3").arg(current + 1).arg(titles.length).arg(titles[current] || "")

    Repeater {
        model: indicator.titles
        delegate: RowLayout {
            id: step
            required property int index
            required property string modelData
            readonly property bool done: index < indicator.current
            readonly property bool active: index === indicator.current
            spacing: Kirigami.Units.smallSpacing

            // Line from the previous step.
            Rectangle {
                visible: step.index > 0
                implicitWidth: Kirigami.Units.gridUnit
                implicitHeight: 2
                radius: 1
                color: step.done || step.active ? Kirigami.Theme.highlightColor : Kirigami.Theme.disabledTextColor
                opacity: step.done || step.active ? 1 : 0.4
            }
            Rectangle {
                implicitWidth: Kirigami.Units.gridUnit * 1.4
                implicitHeight: implicitWidth
                radius: width / 2
                color: step.done || step.active ? Kirigami.Theme.highlightColor : "transparent"
                border.width: step.done || step.active ? 0 : 1
                border.color: Kirigami.Theme.disabledTextColor
                Controls.Label {
                    anchors.centerIn: parent
                    visible: !step.done
                    text: step.index + 1
                    font.weight: Font.DemiBold
                    color: step.active ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.disabledTextColor
                }
                Kirigami.Icon {
                    anchors.centerIn: parent
                    visible: step.done
                    source: "checkmark"
                    isMask: true
                    color: Kirigami.Theme.highlightedTextColor
                    width: Kirigami.Units.iconSizes.small
                    height: width
                }
            }
            Controls.Label {
                text: step.modelData
                font.weight: step.active ? Font.DemiBold : Font.Normal
                opacity: step.active || step.done ? 1 : 0.6
            }
        }
    }
}
