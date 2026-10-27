// A small rounded label: a version, a status or a "Current" marker.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Rectangle {
    id: pill
    property string text: ""
    property string iconName: ""
    property color tint: Kirigami.Theme.highlightColor
    // How strongly the tint fills the background (0 = outline only).
    property real fill: 0.16

    implicitWidth: row.implicitWidth + Kirigami.Units.largeSpacing * 2
    implicitHeight: row.implicitHeight + Kirigami.Units.smallSpacing * 1.5
    radius: height / 2
    color: Qt.rgba(tint.r, tint.g, tint.b, fill)
    border.width: fill === 0 ? 1 : 0
    border.color: Qt.rgba(tint.r, tint.g, tint.b, 0.6)
    Accessible.role: Accessible.StaticText
    Accessible.name: text

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: Kirigami.Units.smallSpacing
        Kirigami.Icon {
            visible: pill.iconName.length > 0
            source: pill.iconName
            isMask: true
            color: pill.tint
            implicitWidth: Kirigami.Units.iconSizes.small
            implicitHeight: Kirigami.Units.iconSizes.small
        }
        Controls.Label {
            text: pill.text
            color: pill.tint
            font.weight: Font.DemiBold
        }
    }
}
