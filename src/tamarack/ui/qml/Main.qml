// Tamarack Center main window.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root

    title: backend.welcomeMode ? qsTr("Welcome to %1").arg(backend.brand.name)
                               : qsTr("%1 Center").arg(backend.brand.shortName)
    width: Kirigami.Units.gridUnit * 62
    height: Kirigami.Units.gridUnit * 42
    minimumWidth: Kirigami.Units.gridUnit * 22
    minimumHeight: Kirigami.Units.gridUnit * 20

    readonly property var pageFiles: ({
        "home": "pages/HomePage.qml",
        "appearance": "pages/AppearancePage.qml",
        "apps": "pages/AppsPage.qml",
        "gaming": "pages/GamingPage.qml",
        "hardware": "pages/HardwarePage.qml",
        "privacy": "pages/PrivacyPage.qml",
        "updates": "pages/UpdatesPage.qml",
        "help": "pages/HelpPage.qml",
        "welcome": "pages/WelcomePage.qml"
    })
    property string currentPage: ""

    function showPage(name) {
        if (!(name in pageFiles)) {
            name = "home";
        }
        currentPage = name;
        pageStack.clear();
        pageStack.push(Qt.resolvedUrl(pageFiles[name]));
    }

    // The navigation sidebar exists only outside the first-run Welcome flow.
    Component {
        id: drawerComponent

        Kirigami.GlobalDrawer {
            title: qsTr("%1 Center").arg(backend.brand.shortName)
            titleIcon: backend.brand.logo
            isMenu: false
            modal: !root.wideScreen

            actions: [
                Kirigami.Action {
                    text: qsTr("Home")
                    icon.name: "go-home"
                    checked: root.currentPage === "home"
                    onTriggered: root.showPage("home")
                },
                Kirigami.Action {
                    text: qsTr("Appearance")
                    icon.name: "preferences-desktop-theme-global"
                    checked: root.currentPage === "appearance"
                    onTriggered: root.showPage("appearance")
                },
                Kirigami.Action {
                    text: qsTr("Apps")
                    icon.name: "plasmadiscover"
                    checked: root.currentPage === "apps"
                    onTriggered: root.showPage("apps")
                },
                Kirigami.Action {
                    text: qsTr("Gaming")
                    icon.name: "input-gamepad"
                    checked: root.currentPage === "gaming"
                    onTriggered: root.showPage("gaming")
                },
                Kirigami.Action {
                    text: qsTr("Hardware")
                    icon.name: "computer"
                    checked: root.currentPage === "hardware"
                    onTriggered: root.showPage("hardware")
                },
                Kirigami.Action {
                    text: qsTr("Privacy")
                    icon.name: "preferences-system-privacy"
                    checked: root.currentPage === "privacy"
                    onTriggered: root.showPage("privacy")
                },
                Kirigami.Action {
                    text: qsTr("Updates & Recovery")
                    icon.name: "system-software-update"
                    checked: root.currentPage === "updates"
                    onTriggered: root.showPage("updates")
                },
                Kirigami.Action {
                    text: qsTr("Help & About")
                    icon.name: "help-about"
                    checked: root.currentPage === "help"
                    onTriggered: root.showPage("help")
                }
            ]
        }
    }

    footer: Controls.ToolBar {
        visible: backend.busy
        position: Controls.ToolBar.Footer
        RowLayout {
            anchors.fill: parent
            Controls.BusyIndicator {
                running: backend.busy
                Layout.preferredHeight: Kirigami.Units.iconSizes.medium
                Layout.preferredWidth: Kirigami.Units.iconSizes.medium
            }
            Controls.Label {
                text: backend.busyText + "…"
                Layout.fillWidth: true
                elide: Text.ElideRight
                Accessible.role: Accessible.StatusBar
            }
        }
    }

    Connections {
        target: backend
        function onNotify(message, kind) {
            root.showPassiveNotification(message, kind === "error" || kind === "warning" ? "long" : "short");
        }
    }

    Component.onCompleted: {
        if (!backend.welcomeMode) {
            globalDrawer = drawerComponent.createObject(root);
        }
        showPage(initialPage);
    }
}
