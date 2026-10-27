// First-run welcome: a short, skippable setup. No account is required.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"
import "../components/looks.js" as Looks

Kirigami.Page {
    id: page
    title: qsTr("Welcome")
    globalToolBarStyle: Kirigami.ApplicationHeaderStyle.None
    padding: 0

    property var chosenBundles: []
    readonly property var stepTitles: [qsTr("Welcome"), qsTr("Look"), qsTr("Privacy"), qsTr("Apps"), qsTr("Gaming"), qsTr("Done")]
    readonly property bool wide: width > Kirigami.Units.gridUnit * 40
    readonly property bool darkTheme: Kirigami.ColorUtils.brightnessForColor(Kirigami.Theme.backgroundColor) === Kirigami.ColorUtils.Dark

    function toggleBundle(id, on) {
        var copy = chosenBundles.filter(b => b !== id);
        if (on) copy.push(id);
        chosenBundles = copy;
    }
    function finish() {
        var ids = [];
        for (var i = 0; i < backend.bundles.length; ++i) {
            var b = backend.bundles[i];
            if (chosenBundles.indexOf(b.id) !== -1) {
                ids = ids.concat(b.apps.filter(a => !a.installed).map(a => a.id));
            }
        }
        if (ids.length > 0) backend.installApps(ids);
        backend.finishWelcome();
    }

    Component.onCompleted: {
        backend.refreshPresets();
        backend.refreshPrivacy();
        backend.refreshBundles();
        backend.refreshHardware();
        backend.refreshUpdates();
    }

    // One scrollable step with page margins.
    component Step: Controls.ScrollView {
        id: stepView
        default property alias content: column.data
        contentWidth: availableWidth
        contentHeight: column.implicitHeight + Kirigami.Units.gridUnit * 2

        ColumnLayout {
            id: column
            x: Kirigami.Units.gridUnit * 2
            y: Kirigami.Units.gridUnit
            width: stepView.availableWidth - Kirigami.Units.gridUnit * 4
            spacing: Kirigami.Units.largeSpacing * 2
        }
    }

    component StepHeading: ColumnLayout {
        id: heading
        property string title
        property string text
        spacing: Kirigami.Units.smallSpacing
        Layout.fillWidth: true
        Kirigami.Heading {
            text: heading.title
            level: 1
            font.weight: Font.DemiBold
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        Controls.Label {
            text: heading.text
            visible: text.length > 0
            wrapMode: Text.WordWrap
            opacity: 0.8
            Layout.fillWidth: true
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        StepIndicator {
            titles: page.stepTitles
            current: steps.currentIndex
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: Kirigami.Units.gridUnit
            Layout.bottomMargin: Kirigami.Units.gridUnit
        }
        Kirigami.Separator {
            Layout.fillWidth: true
        }

        Controls.SwipeView {
            id: steps
            objectName: "welcomeSteps"
            Layout.fillWidth: true
            Layout.fillHeight: true
            interactive: false
            clip: true

            // 1. Hello
            Step {
                Item {
                    id: banner
                    readonly property real cornerRadius: Kirigami.Units.cornerRadius * 2
                    Layout.fillWidth: true
                    implicitHeight: Kirigami.Units.gridUnit * 13

                    Rectangle {
                        anchors.fill: parent
                        radius: banner.cornerRadius
                        color: backend.brand.accent
                    }
                    Kirigami.ShadowedImage {
                        anchors.fill: parent
                        source: page.darkTheme ? backend.brand.banner.dark : backend.brand.banner.light
                        visible: source.toString().length > 0
                        fillMode: Image.PreserveAspectCrop
                        sourceSize.width: 1920
                        radius: banner.cornerRadius
                        color: "transparent"
                    }
                    Rectangle {
                        anchors.fill: parent
                        radius: banner.cornerRadius
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: Qt.rgba(0, 0, 0, 0.2) }
                            GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, 0.6) }
                        }
                    }
                    ColumnLayout {
                        anchors.centerIn: parent
                        width: parent.width - Kirigami.Units.gridUnit * 4
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            source: backend.brand.logo
                            implicitWidth: Kirigami.Units.iconSizes.huge * 1.5
                            implicitHeight: implicitWidth
                            Layout.alignment: Qt.AlignHCenter
                        }
                        Kirigami.Heading {
                            text: qsTr("Welcome to %1").arg(backend.brand.name)
                            level: 1
                            font.pointSize: Kirigami.Theme.defaultFont.pointSize * 2
                            font.weight: Font.Bold
                            color: "white"
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                        Controls.Label {
                            text: backend.brand.tagline
                            color: "white"
                            opacity: 0.92
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                }

                GridLayout {
                    columns: page.wide ? 2 : 1
                    columnSpacing: Kirigami.Units.largeSpacing * 2
                    rowSpacing: Kirigami.Units.largeSpacing * 2
                    Layout.fillWidth: true

                    Repeater {
                        model: [
                            { title: qsTr("No ads, no tracking"), text: qsTr("No advertising ID and no data collected without asking."), icon: "security-high", tint: Kirigami.Theme.visitedLinkColor },
                            { title: qsTr("Ready to play"), text: qsTr("Steam, Proton and game launchers are built in."), icon: "input-gamepad", tint: Kirigami.Theme.neutralTextColor },
                            { title: qsTr("Safe updates"), text: qsTr("Updates install in the background and the previous version is always kept."), icon: "system-software-update", tint: Kirigami.Theme.highlightColor },
                            { title: qsTr("Make it yours"), text: qsTr("Pick a look now and change it any time."), icon: "draw-brush", tint: Kirigami.Theme.linkColor }
                        ]
                        delegate: ActionTile {
                            required property var modelData
                            interactive: false
                            title: modelData.title
                            description: modelData.text
                            iconName: modelData.icon
                            tint: modelData.tint
                            Layout.preferredWidth: 1
                            Layout.fillHeight: true
                        }
                    }
                }

                Controls.Label {
                    text: qsTr("Setup takes about a minute. You can skip any step and change everything later in %1 Center.").arg(backend.brand.shortName)
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    opacity: 0.75
                    Layout.fillWidth: true
                }
            }

            // 2. Look
            Step {
                StepHeading {
                    title: qsTr("Choose a look")
                    text: qsTr("Pick a starting point. It applies right away and can be undone.")
                }
                Kirigami.CardsLayout {
                    Layout.fillWidth: true
                    maximumColumns: 3
                    Repeater {
                        model: backend.presets.filter(p => p.builtin)
                        delegate: PresetCard {
                            id: lookCard
                            required property var modelData
                            preset: modelData
                            // Same base width for every card, so the columns come out equal.
                            Layout.preferredWidth: Kirigami.Units.gridUnit * 20
                            actions: [
                                Kirigami.Action {
                                    text: lookCard.modelData.current ? qsTr("Selected") : qsTr("Use this")
                                    icon.name: "dialog-ok-apply"
                                    enabled: !backend.busy && !lookCard.modelData.current
                                    onTriggered: backend.applyPreset(lookCard.modelData.id)
                                }
                            ]
                        }
                    }
                }
            }

            // 3. Privacy
            Step {
                StepHeading {
                    title: qsTr("Privacy")
                    text: qsTr("Optional data sharing is off unless you turn it on. These are the only optional switches; the Privacy page lists everything that uses the internet.")
                }
                SectionCard {
                    title: qsTr("Your choices")
                    iconName: "security-high"
                    tint: Kirigami.Theme.visitedLinkColor
                    Repeater {
                        model: [
                            { key: "countme", title: qsTr("Help Fedora count installations"), body: qsTr("Weekly, anonymous, no unique ID. Default: off.") },
                            { key: "connectivity", title: qsTr("Detect Wi-Fi sign-in pages"), body: qsTr("Needed for hotel and airport Wi-Fi login pages. Default: on.") },
                            { key: "recent_files", title: qsTr("Remember recently opened files"), body: qsTr("Stored only on this computer. Default: on.") }
                        ]
                        delegate: RowLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: Kirigami.Units.largeSpacing
                            ColumnLayout {
                                spacing: 0
                                Layout.fillWidth: true
                                Controls.Label { text: modelData.title; font.weight: Font.DemiBold; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                Controls.Label { text: modelData.body; opacity: 0.75; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                            }
                            Controls.Switch {
                                checked: (backend.privacy.toggles || {})[modelData.key] === true
                                enabled: !backend.busy
                                onToggled: backend.setPrivacyToggle(modelData.key, checked)
                                Accessible.name: modelData.title
                            }
                        }
                    }
                }
            }

            // 4. Apps
            Step {
                StepHeading {
                    title: qsTr("Add apps")
                    text: qsTr("A web browser and basic viewers are set up automatically. Pick any bundles you want; they install in the background after you finish. This is optional.")
                }
                GridLayout {
                    columns: page.wide ? 2 : 1
                    columnSpacing: Kirigami.Units.largeSpacing * 2
                    rowSpacing: Kirigami.Units.largeSpacing * 2
                    Layout.fillWidth: true
                    Repeater {
                        model: backend.bundles
                        delegate: Kirigami.AbstractCard {
                            id: bundleTile
                            required property var modelData
                            readonly property bool chosen: page.chosenBundles.indexOf(modelData.id) !== -1
                            showClickFeedback: true
                            padding: Kirigami.Units.largeSpacing * 1.5
                            Layout.preferredWidth: 1
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Accessible.role: Accessible.CheckBox
                            Accessible.name: modelData.name
                            Accessible.checked: chosen
                            onClicked: page.toggleBundle(modelData.id, !chosen)

                            contentItem: RowLayout {
                                spacing: Kirigami.Units.largeSpacing * 1.5
                                IconBadge {
                                    iconName: Looks.bundleIcon(bundleTile.modelData.id)
                                    tint: Looks.bundleTint(bundleTile.modelData.id, Kirigami.Theme)
                                    Layout.alignment: Qt.AlignTop
                                }
                                ColumnLayout {
                                    spacing: Kirigami.Units.smallSpacing
                                    Layout.fillWidth: true
                                    Controls.Label {
                                        text: bundleTile.modelData.name
                                        font.weight: Font.DemiBold
                                        wrapMode: Text.WordWrap
                                        Layout.fillWidth: true
                                    }
                                    Controls.Label {
                                        text: bundleTile.modelData.description
                                        opacity: 0.72
                                        wrapMode: Text.WordWrap
                                        Layout.fillWidth: true
                                    }
                                    Row {
                                        spacing: Kirigami.Units.smallSpacing
                                        Repeater {
                                            model: bundleTile.modelData.apps
                                            delegate: Kirigami.Icon {
                                                required property var modelData
                                                source: modelData.icon ? "file://" + modelData.icon : modelData.id
                                                fallback: "application-x-executable"
                                                width: Kirigami.Units.iconSizes.smallMedium
                                                height: width
                                            }
                                        }
                                    }
                                }
                                Controls.CheckBox {
                                    checked: bundleTile.chosen
                                    onToggled: page.toggleBundle(bundleTile.modelData.id, checked)
                                    Layout.alignment: Qt.AlignTop
                                    Accessible.name: bundleTile.modelData.name
                                }
                            }
                        }
                    }
                }
            }

            // 5. Gaming
            Step {
                StepHeading {
                    title: qsTr("Gaming")
                    text: qsTr("Steam and Proton are built in. Sign in to Steam with your existing account to download your games.")
                }
                SectionCard {
                    title: qsTr("Your graphics")
                    iconName: "computer"
                    tint: Kirigami.Theme.linkColor
                    Repeater {
                        model: (backend.hardware.items || []).filter(i => i.category === "Graphics")
                        delegate: RowLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: Kirigami.Units.largeSpacing
                            StatusIcon { level: modelData.status; Layout.alignment: Qt.AlignTop }
                            ColumnLayout {
                                spacing: 0
                                Layout.fillWidth: true
                                Controls.Label { text: modelData.name + (modelData.driver ? " (" + modelData.driver + ")" : ""); font.weight: Font.DemiBold; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                Controls.Label { visible: modelData.advice.length > 0; text: modelData.advice; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Kirigami.Theme.neutralTextColor }
                            }
                        }
                    }
                    Controls.Label {
                        visible: (backend.hardware.items || []).length === 0
                        text: qsTr("Detecting graphics…")
                        opacity: 0.7
                    }
                }
                SectionCard {
                    title: qsTr("Options")
                    iconName: "input-gamepad"
                    tint: Kirigami.Theme.neutralTextColor
                    Controls.SwitchDelegate {
                        Layout.fillWidth: true
                        visible: backend.hybridGraphics
                        text: qsTr("Run Steam and its games on the discrete GPU (uses more battery)")
                        checked: backend.steamOnDiscreteGpu
                        onToggled: backend.setSteamOnDiscreteGpu(checked)
                    }
                    Controls.CheckDelegate {
                        Layout.fillWidth: true
                        text: qsTr("Also install Proton tools and other game launchers (Heroic for Epic and GOG, Bottles)")
                        checked: page.chosenBundles.indexOf("gaming") !== -1
                        onToggled: page.toggleBundle("gaming", checked)
                    }
                    Controls.Button {
                        text: qsTr("Open Steam to sign in")
                        icon.name: "media-playback-start"
                        onClicked: backend.launch("steam")
                    }
                }
            }

            // 6. Done
            Step {
                IconBadge {
                    iconName: "checkmark"
                    solid: true
                    size: Kirigami.Units.gridUnit * 4
                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: Kirigami.Units.gridUnit
                }
                Kirigami.Heading {
                    text: qsTr("You're all set")
                    level: 1
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                }
                Controls.Label {
                    visible: page.chosenBundles.length > 0
                    text: qsTr("Your apps install in the background after you click Finish.")
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    opacity: 0.8
                    Layout.fillWidth: true
                }
                SectionCard {
                    title: qsTr("A few tips")
                    iconName: "help-about"
                    Repeater {
                        model: [
                            { icon: "search", text: qsTr("Press the Meta (Windows) key to open the start menu, then just type to search.") },
                            { icon: "input-keyboard", text: qsTr("Drag a window to a screen edge to snap it; Meta + arrow keys do the same.") },
                            { icon: "view-list-icons", text: qsTr("Meta + W shows all windows and virtual desktops.") },
                            { icon: "configure", text: qsTr("Right-click the taskbar or desktop to customize them.") },
                            { icon: "help-about", text: qsTr("%1 Center (in the start menu) has presets, privacy, hardware checks, game compatibility and updates.").arg(backend.brand.shortName) },
                            { icon: "system-software-update", text: qsTr("Updates install in the background and apply when you restart. The previous version is always kept.") }
                        ]
                        delegate: RowLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: Kirigami.Units.largeSpacing
                            IconBadge {
                                iconName: modelData.icon
                                size: Kirigami.Units.iconSizes.medium
                            }
                            Controls.Label {
                                text: modelData.text
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                        }
                    }
                }
            }
        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.largeSpacing * 2
            spacing: Kirigami.Units.largeSpacing
            Controls.Button {
                text: qsTr("Skip setup")
                flat: true
                visible: steps.currentIndex < steps.count - 1
                onClicked: page.finish()
            }
            Item { Layout.fillWidth: true }
            Controls.Button {
                text: qsTr("Back")
                icon.name: "go-previous"
                visible: steps.currentIndex > 0
                onClicked: steps.decrementCurrentIndex()
            }
            PrimaryButton {
                text: steps.currentIndex === steps.count - 1 ? qsTr("Finish") : steps.currentIndex === 0 ? qsTr("Get started") : qsTr("Next")
                icon.name: steps.currentIndex === steps.count - 1 ? "dialog-ok" : "go-next"
                onClicked: steps.currentIndex === steps.count - 1 ? page.finish() : steps.incrementCurrentIndex()
            }
        }
    }
}
