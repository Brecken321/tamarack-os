// Tamarack Center main window.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "components"

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
    // Counts page loads (choosing the current page again reloads it).
    property int pageLoads: 0

    readonly property var colors: backend.brand.palette
    // The sidebar, in order.
    readonly property var navigation: [
        { page: "home", text: qsTr("Home"), icon: "go-home", tint: colors.section_home },
        { page: "appearance", text: qsTr("Appearance"), icon: "draw-brush", tint: colors.section_appearance },
        { page: "apps", text: qsTr("Apps"), icon: "download", tint: colors.section_apps },
        { page: "gaming", text: qsTr("Gaming"), icon: "input-gamepad", tint: colors.section_gaming },
        { page: "hardware", text: qsTr("Hardware"), icon: "computer", tint: colors.section_hardware },
        { page: "privacy", text: qsTr("Privacy"), icon: "security-high", tint: colors.section_privacy },
        { page: "updates", text: qsTr("Updates & Recovery"), icon: "system-software-update", tint: colors.section_updates },
        { page: "help", text: qsTr("Help & About"), icon: "help-about", tint: colors.section_help }
    ]
    // What "Find a setting" searches: this app's pages and the System
    // Settings pages people look for most, by the words they use.
    readonly property var settingsIndex: [
        { text: qsTr("Desktop look and presets"), words: "theme preset style taskbar panel start menu dark light mode wallpaper look windows", page: "appearance" },
        { text: qsTr("Undo a look change"), words: "undo restore previous appearance reset default", page: "appearance" },
        { text: qsTr("Install apps and games"), words: "install apps games software store flathub download search bundle program", page: "apps" },
        { text: qsTr("Remove apps"), words: "uninstall remove delete apps programs", page: "apps" },
        { text: qsTr("Game Mode and performance overlay"), words: "game mode gaming performance fps overlay mangohud steam big picture controller", page: "gaming" },
        { text: qsTr("Will this game work?"), words: "anti-cheat anticheat compatibility proton game works multiplayer online", page: "gaming" },
        { text: qsTr("Run games on the discrete GPU"), words: "nvidia gpu graphics card hybrid discrete battery dgpu", page: "gaming" },
        { text: qsTr("Drivers and hardware status"), words: "driver drivers hardware graphics gpu nvidia amd intel cpu memory ram storage disk battery wifi audio", page: "hardware" },
        { text: qsTr("Data sharing and privacy"), words: "privacy data sharing telemetry tracking ads countme connectivity recent files", page: "privacy" },
        { text: qsTr("App permissions"), words: "permissions camera microphone location files sandbox flatpak access", page: "privacy" },
        { text: qsTr("Apps that start automatically"), words: "autostart startup login boot apps background", page: "privacy" },
        { text: qsTr("Automatic updates"), words: "update updates upgrade automatic security patch version", page: "updates" },
        { text: qsTr("Go back to the previous version"), words: "rollback roll back previous version restore broken recovery boot", page: "updates" },
        { text: qsTr("Keyboard shortcuts and accessibility"), words: "shortcuts keyboard hotkeys accessibility screen reader help about bug report", page: "help" },
        { text: qsTr("Display, resolution and scaling"), words: "display screen monitor resolution scale scaling refresh rate hz orientation multiple monitors", kcm: "kcm_kscreen" },
        { text: qsTr("Night light"), words: "night light blue light warm color temperature eyes", kcm: "kcm_nightlight" },
        { text: qsTr("Sound and volume"), words: "sound audio volume speakers headphones microphone output input", kcm: "kcm_pulseaudio" },
        { text: qsTr("Bluetooth"), words: "bluetooth pair headphones controller wireless devices", kcm: "kcm_bluetooth" },
        { text: qsTr("Wi-Fi and network"), words: "wifi wi-fi wireless network internet ethernet vpn hotspot", kcm: "kcm_networkmanagement" },
        { text: qsTr("Mouse"), words: "mouse pointer speed acceleration buttons scroll", kcm: "kcm_mouse" },
        { text: qsTr("Touchpad"), words: "touchpad trackpad tap scroll gestures laptop", kcm: "kcm_touchpad" },
        { text: qsTr("Keyboard and layouts"), words: "keyboard layout language typing repeat numlock", kcm: "kcm_keyboard" },
        { text: qsTr("Shortcuts"), words: "shortcuts hotkeys keys key bindings", kcm: "kcm_keys" },
        { text: qsTr("Power, sleep and battery"), words: "power sleep suspend hibernate battery lid screen off energy", kcm: "kcm_powerdevilprofilesconfig" },
        { text: qsTr("Users and password"), words: "user account password picture login name", kcm: "kcm_users" },
        { text: qsTr("Date and time"), words: "date time clock timezone time zone", kcm: "kcm_clock" },
        { text: qsTr("Language and region"), words: "language region locale format currency units translation", kcm: "kcm_regionandlang" },
        { text: qsTr("Notifications"), words: "notifications do not disturb alerts popups", kcm: "kcm_notifications" },
        { text: qsTr("Default apps"), words: "default apps browser email file manager terminal open with", kcm: "kcm_componentchooser" },
        { text: qsTr("Fonts"), words: "font fonts text size", kcm: "kcm_fonts" },
        { text: qsTr("Colors and accent color"), words: "colors color scheme accent dark light", kcm: "kcm_colors" },
        { text: qsTr("Screen locking"), words: "lock screen locking password screensaver idle", kcm: "kcm_screenlocker" },
        { text: qsTr("Virtual desktops"), words: "virtual desktops workspaces multiple desktops", kcm: "kcm_kwin_virtualdesktops" },
        { text: qsTr("Game controllers"), words: "controller gamepad joystick xbox playstation", kcm: "kcm_gamecontroller" },
        { text: qsTr("About this computer"), words: "about system information specs version computer name", kcm: "kcm_about-distro" }
    ]

    function showPage(name) {
        if (!(name in pageFiles)) {
            name = "home";
        }
        currentPage = name;
        pageLoads += 1;
        pageStack.clear();
        var page = pageStack.push(Qt.resolvedUrl(pageFiles[name]));
        if (page) {
            pageFade.target = page;
            pageFade.restart();
        }
    }

    function findSettings(text) {
        var words = text.toLowerCase().split(/\s+/).filter(w => w.length > 0);
        if (words.length === 0) return [];
        return settingsIndex.filter(entry => {
            var haystack = (entry.text + " " + entry.words).toLowerCase();
            return words.every(w => haystack.indexOf(w) !== -1);
        }).slice(0, 8);
    }

    function openSetting(entry) {
        if (entry.page) {
            showPage(entry.page);
        } else {
            backend.openSettings(entry.kcm);
        }
    }

    // New pages fade in instead of appearing at once (instant when the
    // desktop's animations are turned off).
    NumberAnimation {
        id: pageFade
        property: "opacity"
        from: 0
        to: 1
        duration: Kirigami.Units.longDuration
        easing.type: Easing.OutCubic
    }

    // The navigation sidebar exists only outside the first-run Welcome flow.
    Component {
        id: drawerComponent

        Kirigami.GlobalDrawer {
            id: drawer
            title: qsTr("%1 Center").arg(backend.brand.shortName)
            titleIcon: backend.brand.logo
            isMenu: false
            modal: !root.wideScreen

            readonly property var results: root.findSettings(finder.text)

            // Everything sits in topContent, so it starts right under the
            // title (the drawer's own action list stays empty).
            topContent: [
                Kirigami.SearchField {
                    id: finder
                    Layout.fillWidth: true
                    Layout.leftMargin: Kirigami.Units.smallSpacing
                    Layout.rightMargin: Kirigami.Units.smallSpacing
                    Layout.bottomMargin: Kirigami.Units.largeSpacing
                    placeholderText: qsTr("Find a setting")
                    // Enter opens the best match.
                    autoAccept: false
                    onAccepted: if (drawer.results.length > 0) root.openSetting(drawer.results[0])
                    Accessible.name: qsTr("Find a setting")
                },
                ColumnLayout {
                    spacing: Kirigami.Units.smallSpacing / 2
                    Layout.fillWidth: true

                    Repeater {
                        model: finder.text.length === 0 ? root.navigation : []
                        delegate: NavItem {
                            required property var modelData
                            text: modelData.text
                            iconName: modelData.icon
                            tint: modelData.tint
                            current: root.currentPage === modelData.page
                            onClicked: {
                                root.showPage(modelData.page);
                                if (drawer.modal) drawer.close();
                            }
                        }
                    }

                    Repeater {
                        model: drawer.results
                        delegate: NavItem {
                            required property var modelData
                            readonly property var section: root.navigation.filter(n => n.page === modelData.page)[0]
                            text: modelData.text
                            subtitle: section ? qsTr("%1 Center · %2").arg(backend.brand.shortName).arg(section.text) : qsTr("System Settings")
                            iconName: section ? section.icon : "configure"
                            tint: section ? section.tint : root.colors.section_help
                            onClicked: {
                                root.openSetting(modelData);
                                finder.text = "";
                                if (drawer.modal) drawer.close();
                            }
                        }
                    }

                    Controls.Label {
                        visible: finder.text.length > 0 && drawer.results.length === 0
                        text: qsTr("No setting matches “%1”.").arg(finder.text)
                        wrapMode: Text.WordWrap
                        opacity: 0.7
                        Layout.fillWidth: true
                        Layout.margins: Kirigami.Units.largeSpacing
                    }
                    Controls.Button {
                        visible: finder.text.length > 0 && drawer.results.length === 0
                        text: qsTr("Search all System Settings")
                        icon.name: "configure"
                        onClicked: backend.openSettings("kcm_landingpage")
                        Layout.leftMargin: Kirigami.Units.largeSpacing
                    }
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
