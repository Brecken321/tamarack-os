// A sidebar entry: a colored icon, a label (and optional second line), a
// soft highlight on hover and an accent marker on the current page.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Controls.ItemDelegate {
    id: entry
    property string iconName: ""
    property color tint: Kirigami.Theme.highlightColor
    property string subtitle: ""
    property bool current: false

    Layout.fillWidth: true
    hoverEnabled: true
    leftPadding: Kirigami.Units.largeSpacing * 1.5
    rightPadding: Kirigami.Units.largeSpacing
    topPadding: Kirigami.Units.smallSpacing * 1.5
    bottomPadding: Kirigami.Units.smallSpacing * 1.5
    Accessible.role: Accessible.PageTab
    Accessible.name: subtitle.length > 0 ? text + ", " + subtitle : text
    Accessible.selected: current

    background: Rectangle {
        radius: Kirigami.Units.cornerRadius
        color: entry.current ? Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g, Kirigami.Theme.highlightColor.b, 0.16)
             : entry.down ? Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.12)
             : entry.hovered || entry.visualFocus ? Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.06)
             : "transparent"
        Behavior on color {
            ColorAnimation { duration: Kirigami.Units.shortDuration }
        }

        // The current page's marker, like the Windows 11 Settings sidebar.
        Rectangle {
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: 3
            height: entry.current ? parent.height * 0.5 : 0
            radius: width / 2
            color: Kirigami.Theme.highlightColor
            Behavior on height {
                NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic }
            }
        }
    }

    contentItem: RowLayout {
        spacing: Kirigami.Units.largeSpacing * 1.5
        IconBadge {
            iconName: entry.iconName
            tint: entry.tint
            solid: true
            size: Kirigami.Units.iconSizes.smallMedium + Kirigami.Units.smallSpacing * 2
        }
        ColumnLayout {
            spacing: 0
            Layout.fillWidth: true
            Controls.Label {
                text: entry.text
                font.weight: entry.current ? Font.DemiBold : Font.Normal
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
            Controls.Label {
                visible: entry.subtitle.length > 0
                text: entry.subtitle
                font: Kirigami.Theme.smallFont
                opacity: 0.7
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }
    }
}
