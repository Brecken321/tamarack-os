// Icon + accessible text for a status: ok, attention, missing, info.
import QtQuick
import org.kde.kirigami as Kirigami

Kirigami.Icon {
    id: icon
    property string status: "info"

    implicitWidth: Kirigami.Units.iconSizes.smallMedium
    implicitHeight: Kirigami.Units.iconSizes.smallMedium
    source: ({
        "ok": "emblem-ok-symbolic",
        "attention": "emblem-warning",
        "missing": "emblem-error",
        "info": "emblem-information"
    })[status] || "emblem-information"
    color: ({
        "ok": Kirigami.Theme.positiveTextColor,
        "attention": Kirigami.Theme.neutralTextColor,
        "missing": Kirigami.Theme.negativeTextColor
    })[status] || Kirigami.Theme.textColor
    isMask: true

    Accessible.role: Accessible.Graphic
    Accessible.name: ({
        "ok": qsTr("Working"),
        "attention": qsTr("Needs attention"),
        "missing": qsTr("Not found"),
        "info": qsTr("Information")
    })[status] || status
}
