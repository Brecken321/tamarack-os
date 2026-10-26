// First-run welcome: a short, skippable setup. No account is required.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"

Kirigami.Page {
    id: page
    title: qsTr("Welcome")

    property var chosenBundles: []
    readonly property var stepTitles: [qsTr("Welcome"), qsTr("Look"), qsTr("Privacy"), qsTr("Apps"), qsTr("Gaming"), qsTr("Done")]

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

    ColumnLayout {
        anchors.fill: parent
        spacing: Kirigami.Units.largeSpacing

        Controls.PageIndicator {
            Layout.alignment: Qt.AlignHCenter
            count: steps.count
            currentIndex: steps.currentIndex
            Accessible.name: qsTr("Step %1 of %2: %3").arg(steps.currentIndex + 1).arg(steps.count).arg(page.stepTitles[steps.currentIndex])
        }

        Controls.SwipeView {
            id: steps
            Layout.fillWidth: true
            Layout.fillHeight: true
            interactive: false
            clip: true

            // 1. Hello
            Controls.ScrollView {
                ColumnLayout {
                    width: steps.width
                    spacing: Kirigami.Units.largeSpacing * 2
                    Item { Layout.preferredHeight: Kirigami.Units.gridUnit }
                    Kirigami.Icon {
                        Layout.alignment: Qt.AlignHCenter
                        source: backend.brand.logo
                        implicitWidth: Kirigami.Units.iconSizes.enormous
                        implicitHeight: Kirigami.Units.iconSizes.enormous
                    }
                    Kirigami.Heading {
                        Layout.alignment: Qt.AlignHCenter
                        text: qsTr("Welcome to %1").arg(backend.brand.name)
                        level: 1
                    }
                    Controls.Label {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.maximumWidth: Kirigami.Units.gridUnit * 30
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        text: qsTr("No ads, no account required, and no data collected without asking. The next few steps take about a minute; you can skip any of them and change everything later in %1 Center.").arg(backend.brand.shortName)
                    }
                }
            }

            // 2. Look
            Controls.ScrollView {
                ColumnLayout {
                    width: steps.width
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Heading { text: qsTr("Choose a look"); level: 2 }
                    Controls.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        text: qsTr("Pick a starting point. It applies right away and can be undone.")
                    }
                    Kirigami.CardsLayout {
                        Layout.fillWidth: true
                        maximumColumns: 3
                        Repeater {
                            model: backend.presets.filter(p => p.builtin)
                            delegate: Kirigami.Card {
                                id: lookCard
                                required property var modelData
                                banner.source: modelData.preview
                                banner.title: modelData.name
                                banner.titleIcon: modelData.current ? "emblem-ok-symbolic" : ""
                                contentItem: Controls.Label { text: lookCard.modelData.summary; wrapMode: Text.WordWrap }
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
            }

            // 3. Privacy
            Controls.ScrollView {
                ColumnLayout {
                    width: steps.width
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Heading { text: qsTr("Privacy"); level: 2 }
                    Controls.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        text: qsTr("Optional data sharing is off unless you turn it on. These are the only optional switches; the Privacy page lists everything that uses the internet.")
                    }
                    Repeater {
                        model: [
                            { key: "countme", title: qsTr("Help Fedora count installations"), body: qsTr("Weekly, anonymous, no unique ID. Default: off.") },
                            { key: "connectivity", title: qsTr("Detect Wi-Fi sign-in pages"), body: qsTr("Needed for hotel/airport Wi-Fi login pages. Default: on.") },
                            { key: "recent_files", title: qsTr("Remember recently opened files"), body: qsTr("Stored only on this computer. Default: on.") }
                        ]
                        delegate: RowLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            ColumnLayout {
                                spacing: 0
                                Layout.fillWidth: true
                                Controls.Label { text: modelData.title; font.bold: true }
                                Controls.Label { text: modelData.body; opacity: 0.8; wrapMode: Text.WordWrap; Layout.fillWidth: true }
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
            Controls.ScrollView {
                ColumnLayout {
                    width: steps.width
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Heading { text: qsTr("Add apps (optional)"); level: 2 }
                    Controls.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        text: qsTr("A web browser and basic viewers are set up automatically. Tick any bundles you want; they install in the background after you finish.")
                    }
                    Repeater {
                        model: backend.bundles
                        delegate: Controls.CheckDelegate {
                            required property var modelData
                            Layout.fillWidth: true
                            text: modelData.name + " — " + modelData.description
                            checked: page.chosenBundles.indexOf(modelData.id) !== -1
                            onToggled: page.toggleBundle(modelData.id, checked)
                        }
                    }
                }
            }

            // 5. Gaming
            Controls.ScrollView {
                ColumnLayout {
                    width: steps.width
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Heading { text: qsTr("Gaming"); level: 2 }
                    Controls.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        text: qsTr("Steam and Proton are built in. Sign in to Steam with your existing account to download your games.")
                    }
                    Repeater {
                        model: (backend.hardware.items || []).filter(i => i.category === "Graphics")
                        delegate: RowLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            StatusIcon { status: modelData.status }
                            ColumnLayout {
                                spacing: 0
                                Layout.fillWidth: true
                                Controls.Label { text: modelData.name + (modelData.driver ? " (" + modelData.driver + ")" : ""); font.bold: true; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                Controls.Label { visible: modelData.advice.length > 0; text: modelData.advice; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Kirigami.Theme.neutralTextColor }
                            }
                        }
                    }
                    Controls.CheckDelegate {
                        Layout.fillWidth: true
                        text: qsTr("Also install Proton tools and other game launchers (Heroic for Epic/GOG, Bottles)")
                        checked: page.chosenBundles.indexOf("gaming") !== -1
                        onToggled: page.toggleBundle("gaming", checked)
                    }
                    Controls.Button {
                        text: qsTr("Open Steam to sign in")
                        icon.name: "steam"
                        onClicked: backend.launch("steam")
                    }
                }
            }

            // 6. Done
            Controls.ScrollView {
                ColumnLayout {
                    width: steps.width
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Heading { text: qsTr("You're all set"); level: 2 }
                    Repeater {
                        model: [
                            qsTr("Press the Meta (Windows) key to open the start menu, then just type to search."),
                            qsTr("Drag a window to a screen edge to snap it; Meta + arrow keys do the same."),
                            qsTr("Meta + W shows all windows and virtual desktops."),
                            qsTr("Right-click the taskbar or desktop to customize them."),
                            qsTr("%1 Center (in the start menu) has presets, privacy, hardware checks, game compatibility and updates.").arg(backend.brand.shortName),
                            qsTr("Updates install in the background and apply when you restart. The previous version is always kept.")
                        ]
                        delegate: RowLayout {
                            required property string modelData
                            Layout.fillWidth: true
                            Kirigami.Icon { source: "emblem-information"; implicitWidth: Kirigami.Units.iconSizes.small; implicitHeight: Kirigami.Units.iconSizes.small }
                            Controls.Label { text: modelData; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
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
                enabled: steps.currentIndex > 0
                onClicked: steps.decrementCurrentIndex()
            }
            Controls.Button {
                text: steps.currentIndex === steps.count - 1 ? qsTr("Finish") : qsTr("Next")
                icon.name: steps.currentIndex === steps.count - 1 ? "dialog-ok" : "go-next"
                highlighted: true
                onClicked: steps.currentIndex === steps.count - 1 ? page.finish() : steps.incrementCurrentIndex()
            }
        }
    }
}
