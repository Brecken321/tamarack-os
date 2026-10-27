// A titled card used to group content on every page.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.AbstractCard {
    id: card
    property string title: ""
    property string subtitle: ""
    property string iconName: ""
    property color tint: Kirigami.Theme.highlightColor
    property bool iconMask: true
    default property alias content: body.data

    Layout.fillWidth: true
    padding: Kirigami.Units.largeSpacing * 2

    contentItem: ColumnLayout {
        // No layout spacing: the filler at the end must not add a gap.
        spacing: 0

        RowLayout {
            visible: card.title.length > 0
            spacing: Kirigami.Units.largeSpacing * 1.5
            Layout.bottomMargin: Kirigami.Units.largeSpacing * 1.5
            IconBadge {
                visible: card.iconName.length > 0
                iconName: card.iconName
                tint: card.tint
                mask: card.iconMask
                Layout.alignment: Qt.AlignTop
            }
            ColumnLayout {
                spacing: Kirigami.Units.smallSpacing / 2
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                Kirigami.Heading {
                    text: card.title
                    level: 3
                    font.weight: Font.DemiBold
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                Controls.Label {
                    visible: card.subtitle.length > 0
                    text: card.subtitle
                    wrapMode: Text.WordWrap
                    opacity: 0.75
                    Layout.fillWidth: true
                }
            }
        }

        ColumnLayout {
            id: body
            spacing: Kirigami.Units.largeSpacing
            Layout.fillWidth: true
        }

        // Cards in a grid row are stretched to the tallest one; this keeps
        // the content at the top instead of spread down the card.
        Item {
            Layout.fillHeight: true
        }
    }
}
