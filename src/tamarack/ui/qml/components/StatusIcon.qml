// Icon + accessible text for a status level: ok, attention, missing, info.
import QtQuick
import org.kde.kirigami as Kirigami

Kirigami.Icon {
    id: icon
    property string level: "info"

    implicitWidth: Kirigami.Units.iconSizes.smallMedium
    implicitHeight: Kirigami.Units.iconSizes.smallMedium
    source: ({
        "ok": "emblem-ok-symbolic",
        "attention": "emblem-warning",
        "missing": "emblem-error",
        "info": "emblem-information"
    })[level] || "emblem-information"
    color: ({
        "ok": Kirigami.Theme.positiveTextColor,
        "attention": Kirigami.Theme.neutralTextColor,
        "missing": Kirigami.Theme.negativeTextColor
    })[level] || Kirigami.Theme.textColor
    isMask: true

    Accessible.role: Accessible.Graphic
    Accessible.name: ({
        "ok": qsTr("Working"),
        "attention": qsTr("Needs attention"),
        "missing": qsTr("Not found"),
        "info": qsTr("Information")
    })[level] || level
}
