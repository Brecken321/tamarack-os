// A wide banner with Tamarack artwork behind the logo and a title. Extra
// items (pills, buttons) go in a row under the subtitle.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Item {
    id: hero
    property string title: ""
    property string subtitle: ""
    default property alias extra: extraRow.data

    readonly property bool darkTheme: Kirigami.ColorUtils.brightnessForColor(Kirigami.Theme.backgroundColor) === Kirigami.ColorUtils.Dark
    readonly property string art: darkTheme ? backend.brand.banner.dark : backend.brand.banner.light
    readonly property real cornerRadius: Kirigami.Units.cornerRadius * 2

    Layout.fillWidth: true
    implicitHeight: Math.max(Kirigami.Units.gridUnit * 9, content.implicitHeight + Kirigami.Units.gridUnit * 3)

    // Brand color behind the artwork (and instead of it, if it is missing).
    Rectangle {
        anchors.fill: parent
        radius: hero.cornerRadius
        color: backend.brand.accent
    }
    Kirigami.ShadowedImage {
        anchors.fill: parent
        visible: hero.art.length > 0
        source: hero.art
        fillMode: Image.PreserveAspectCrop
        sourceSize.width: 1920
        radius: hero.cornerRadius
        color: "transparent"
    }
    // Keeps white text readable on light and dark artwork.
    Rectangle {
        anchors.fill: parent
        radius: hero.cornerRadius
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: Qt.rgba(0, 0, 0, 0.62) }
            GradientStop { position: 0.6; color: Qt.rgba(0, 0, 0, 0.25) }
            GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, 0.0) }
        }
    }

    RowLayout {
        id: content
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: Kirigami.Units.gridUnit * 1.5
        anchors.rightMargin: Kirigami.Units.gridUnit * 1.5
        spacing: Kirigami.Units.gridUnit

        Kirigami.Icon {
            source: backend.brand.logo
            implicitWidth: Kirigami.Units.iconSizes.huge
            implicitHeight: Kirigami.Units.iconSizes.huge
            Layout.alignment: Qt.AlignVCenter
        }
        ColumnLayout {
            spacing: Kirigami.Units.smallSpacing
            Layout.fillWidth: true
            Kirigami.Heading {
                text: hero.title
                level: 1
                color: "white"
                font.weight: Font.Bold
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Controls.Label {
                visible: hero.subtitle.length > 0
                text: hero.subtitle
                color: "white"
                opacity: 0.92
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Flow {
                id: extraRow
                spacing: Kirigami.Units.smallSpacing
                visible: children.length > 0
                Layout.fillWidth: true
                Layout.topMargin: Kirigami.Units.smallSpacing
            }
        }
    }
}
