// A single-color icon on a tinted rounded square: the visual mark used for
// sections, tiles and steps, so every area of the Center has its own color.
import QtQuick
import org.kde.kirigami as Kirigami

Rectangle {
    id: badge
    property string iconName: ""
    property color tint: Kirigami.Theme.highlightColor
    property int size: Kirigami.Units.iconSizes.medium + Kirigami.Units.smallSpacing * 2
    // Solid: filled with the tint and a white icon (for emphasis).
    property bool solid: false
    // False for full-color icons such as the logo (shown as they are).
    property bool mask: true

    implicitWidth: size
    implicitHeight: size
    radius: Math.round(size * 0.3)
    color: solid ? tint : Qt.rgba(tint.r, tint.g, tint.b, 0.16)
    Accessible.ignored: true

    Kirigami.Icon {
        anchors.centerIn: parent
        width: Math.round(badge.size * 0.55)
        height: width
        source: badge.iconName
        isMask: badge.mask
        color: badge.mask ? (badge.solid ? "white" : badge.tint) : "transparent"
    }
}
