// Compatibility category badge (verified, likely, configuration, issues,
// incompatible, untested). Color is never the only signal: the text names
// the category too.
import QtQuick
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

Controls.Label {
    id: chip
    property string category: "untested"
    property string title: ""

    readonly property color tone: ({
        "verified": Kirigami.Theme.positiveTextColor,
        "likely": Kirigami.Theme.positiveTextColor,
        "configuration": Kirigami.Theme.neutralTextColor,
        "issues": Kirigami.Theme.neutralTextColor,
        "incompatible": Kirigami.Theme.negativeTextColor
    })[category] || Kirigami.Theme.disabledTextColor

    text: title
    font.bold: true
    color: tone
    leftPadding: Kirigami.Units.smallSpacing * 2
    rightPadding: Kirigami.Units.smallSpacing * 2
    topPadding: Kirigami.Units.smallSpacing / 2
    bottomPadding: Kirigami.Units.smallSpacing / 2
    background: Rectangle {
        radius: height / 2
        color: Qt.rgba(chip.tone.r, chip.tone.g, chip.tone.b, 0.14)
        border.color: Qt.rgba(chip.tone.r, chip.tone.g, chip.tone.b, 0.6)
        border.width: 1
    }
    Accessible.name: qsTr("Compatibility: %1").arg(title)
}
