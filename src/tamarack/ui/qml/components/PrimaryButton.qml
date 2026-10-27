// The main action on a screen, filled with the accent color so it stands
// out from the other buttons.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Controls.Button {
    id: control

    readonly property color fillColor: Kirigami.Theme.highlightColor

    leftPadding: Kirigami.Units.largeSpacing * 2
    rightPadding: Kirigami.Units.largeSpacing * 2
    topPadding: Kirigami.Units.largeSpacing
    bottomPadding: Kirigami.Units.largeSpacing

    contentItem: RowLayout {
        spacing: Kirigami.Units.smallSpacing
        Kirigami.Icon {
            visible: control.icon.name.length > 0
            source: control.icon.name
            isMask: true
            color: Kirigami.Theme.highlightedTextColor
            implicitWidth: Kirigami.Units.iconSizes.small
            implicitHeight: Kirigami.Units.iconSizes.small
        }
        Controls.Label {
            text: control.text
            color: Kirigami.Theme.highlightedTextColor
            font.weight: Font.DemiBold
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
        }
    }

    background: Rectangle {
        implicitWidth: Kirigami.Units.gridUnit * 5
        implicitHeight: Kirigami.Units.gridUnit * 2
        radius: Kirigami.Units.cornerRadius
        opacity: control.enabled ? 1 : 0.45
        color: control.down ? Qt.darker(control.fillColor, 1.2)
             : control.hovered ? Qt.lighter(control.fillColor, 1.12) : control.fillColor
        border.width: control.visualFocus ? 2 : 0
        border.color: Qt.lighter(control.fillColor, 1.5)
    }
}
