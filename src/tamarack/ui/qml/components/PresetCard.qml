// A desktop preset: its preview, name, a "Current" marker and summary. The
// title sits under the preview, not on it, because previews range from very
// light to very dark. Callers add the actions.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.Card {
    id: card
    property var preset: ({})

    banner.source: preset.preview || ""
    Accessible.name: preset.name || ""
    Accessible.description: preset.summary || ""

    contentItem: ColumnLayout {
        spacing: Kirigami.Units.smallSpacing
        RowLayout {
            spacing: Kirigami.Units.smallSpacing
            Layout.fillWidth: true
            Kirigami.Heading {
                text: card.preset.name || ""
                level: 3
                font.weight: Font.DemiBold
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
            Pill {
                visible: !!card.preset.current
                text: qsTr("Current")
                iconName: "checkmark"
            }
        }
        Controls.Label {
            text: card.preset.summary || ""
            wrapMode: Text.WordWrap
            opacity: 0.8
            Layout.fillWidth: true
        }
        // Cards in a row share its height: keep the text at the top.
        Item {
            Layout.fillHeight: true
        }
    }
}
