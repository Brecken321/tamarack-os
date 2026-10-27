// A card with an icon, a title and a short explanation. Clickable unless
// `interactive` is false (then it is just a feature description).
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.AbstractCard {
    id: tile
    property string title: ""
    property string description: ""
    property string iconName: ""
    property color tint: Kirigami.Theme.highlightColor
    property bool interactive: true

    showClickFeedback: interactive
    hoverEnabled: interactive
    padding: Kirigami.Units.largeSpacing * 1.5
    Layout.fillWidth: true
    Accessible.name: title
    Accessible.description: description
    Accessible.role: interactive ? Accessible.Button : Accessible.StaticText

    contentItem: RowLayout {
        spacing: Kirigami.Units.largeSpacing * 1.5
        IconBadge {
            iconName: tile.iconName
            tint: tile.tint
            Layout.alignment: Qt.AlignTop
        }
        ColumnLayout {
            spacing: Kirigami.Units.smallSpacing / 2
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            Controls.Label {
                text: tile.title
                font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Controls.Label {
                visible: tile.description.length > 0
                text: tile.description
                opacity: 0.72
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }
        Kirigami.Icon {
            visible: tile.interactive
            source: "go-next"
            opacity: 0.45
            implicitWidth: Kirigami.Units.iconSizes.small
            implicitHeight: Kirigami.Units.iconSizes.small
            Layout.alignment: Qt.AlignVCenter
        }
    }
}
