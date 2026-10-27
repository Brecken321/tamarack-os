import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"
import "../components/looks.js" as Looks

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Apps")

    actions: [
        Kirigami.Action {
            text: qsTr("Open app store")
            icon.name: "plasmadiscover"
            onTriggered: backend.launch("store")
        },
        Kirigami.Action {
            text: qsTr("Refresh")
            icon.name: "view-refresh"
            onTriggered: backend.refreshBundles()
        }
    ]

    Component.onCompleted: backend.refreshBundles()

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        SectionCard {
            title: qsTr("Find apps and games")
            subtitle: qsTr("Search thousands of apps on Flathub. They run in a sandbox, nothing is installed unless you choose it, and an app you remove is never reinstalled behind your back.")
            iconName: "search"
            tint: Kirigami.Theme.linkColor

            Kirigami.SearchField {
                id: search
                Layout.fillWidth: true
                placeholderText: qsTr("Search Flathub, for example Discord, OBS or SuperTux")
                autoAccept: false
                text: backend.searchQuery
                onAccepted: backend.searchApps(text)
            }
            Repeater {
                model: backend.searchResults
                delegate: AppRow {
                    required property var modelData
                    app: modelData
                }
            }
            Controls.Label {
                visible: backend.searchQuery.length > 0 && backend.searchResults.length === 0 && !backend.busy
                text: qsTr("No apps found for “%1”. Try another name, or the app store.").arg(backend.searchQuery)
                wrapMode: Text.WordWrap
                opacity: 0.8
                Layout.fillWidth: true
            }
        }

        ColumnLayout {
            spacing: 0
            Layout.topMargin: Kirigami.Units.largeSpacing
            Kirigami.Heading {
                text: qsTr("Bundles")
                level: 2
            }
            Controls.Label {
                text: qsTr("Hand-picked sets of apps. Install one app or the whole bundle.")
                opacity: 0.75
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }

        Kirigami.PlaceholderMessage {
            Layout.fillWidth: true
            visible: backend.bundles.length === 0 && !backend.busy
            icon.name: "plasmadiscover"
            text: qsTr("App bundles are not available")
            explanation: qsTr("Flatpak could not be queried. You can still use the app store.")
        }

        GridLayout {
            columns: page.width > Kirigami.Units.gridUnit * 44 ? 2 : 1
            columnSpacing: Kirigami.Units.largeSpacing * 2
            rowSpacing: Kirigami.Units.largeSpacing * 2
            Layout.fillWidth: true

            Repeater {
                model: backend.bundles
                delegate: SectionCard {
                    id: bundleCard
                    required property var modelData
                    readonly property var missing: modelData.apps.filter(a => !a.installed).map(a => a.id)

                    title: modelData.name
                    subtitle: modelData.description
                    iconName: Looks.bundleIcon(modelData.id)
                    tint: Looks.bundleTint(modelData.id, Kirigami.Theme)
                    Layout.preferredWidth: 1
                    Layout.fillHeight: true

                    Repeater {
                        model: bundleCard.modelData.apps
                        delegate: AppRow {
                            required property var modelData
                            app: modelData
                        }
                    }

                    RowLayout {
                        Layout.topMargin: Kirigami.Units.smallSpacing
                        Controls.Label {
                            text: qsTr("%1 of %2 installed").arg(bundleCard.modelData.installed_count).arg(bundleCard.modelData.apps.length)
                            opacity: 0.7
                            Layout.fillWidth: true
                        }
                        Controls.Button {
                            visible: bundleCard.missing.length > 1
                            text: qsTr("Install all %1").arg(bundleCard.missing.length)
                            icon.name: "download"
                            enabled: !backend.busy
                            onClicked: backend.installApps(bundleCard.missing)
                        }
                    }
                }
            }
        }
    }
}
