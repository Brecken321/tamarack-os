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
    default property alias content: body.data

    Layout.fillWidth: true

    contentItem: ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        RowLayout {
            visible: card.title.length > 0
            spacing: Kirigami.Units.largeSpacing
            Kirigami.Icon {
                visible: card.iconName.length > 0
                source: card.iconName
                implicitWidth: Kirigami.Units.iconSizes.medium
                implicitHeight: Kirigami.Units.iconSizes.medium
            }
            ColumnLayout {
                spacing: 0
                Layout.fillWidth: true
                Kirigami.Heading {
                    text: card.title
                    level: 3
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                Controls.Label {
                    visible: card.subtitle.length > 0
                    text: card.subtitle
                    wrapMode: Text.WordWrap
                    opacity: 0.8
                    Layout.fillWidth: true
                }
            }
        }

        ColumnLayout {
            id: body
            spacing: Kirigami.Units.smallSpacing
            Layout.fillWidth: true
        }
    }
}
