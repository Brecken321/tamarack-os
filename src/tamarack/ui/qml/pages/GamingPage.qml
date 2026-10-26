import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Gaming")

    property string logText: ""
    property string logGame: ""

    actions: [
        Kirigami.Action {
            text: qsTr("Big Picture mode")
            icon.name: "input-gamepad"
            tooltip: qsTr("Controller-friendly Steam interface. Exit it to return to the desktop.")
            onTriggered: Qt.openUrlExternally("steam://open/bigpicture")
        },
        Kirigami.Action {
            text: qsTr("Open Steam")
            icon.name: "steam"
            onTriggered: backend.launch("steam")
        }
    ]

    Component.onCompleted: {
        backend.refreshLibrary();
        if (!backend.hardware.gpus) backend.refreshHardware();
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        SectionCard {
            title: qsTr("Will this game work?")
            iconName: "search"
            subtitle: qsTr("Search by name or Steam app ID. Answers come from the %1 anti-cheat database (%2 games, updated %3). Single-player games without anti-cheat usually work through Proton.")
                        .arg(backend.datasetInfo.name || "AreWeAntiCheatYet")
                        .arg(backend.datasetInfo.games || "?")
                        .arg((backend.datasetInfo.date || "").slice(0, 10))

            Kirigami.SearchField {
                id: search
                Layout.fillWidth: true
                placeholderText: qsTr("Game name, e.g. Elden Ring or Apex Legends")
                onAccepted: backend.checkGame(text)
                Accessible.name: qsTr("Search for a game")
            }

            Repeater {
                model: backend.gameResults
                delegate: Kirigami.AbstractCard {
                    id: result
                    required property var modelData
                    Layout.fillWidth: true
                    contentItem: ColumnLayout {
                        spacing: Kirigami.Units.smallSpacing
                        RowLayout {
                            Kirigami.Heading {
                                text: result.modelData.game
                                level: 4
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                            }
                            CategoryChip {
                                category: result.modelData.category
                                title: result.modelData.title
                            }
                        }
                        Controls.Label {
                            text: result.modelData.explanation
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                        Controls.Label {
                            visible: result.modelData.anticheats.length > 0
                            text: qsTr("Anti-cheat: %1").arg(result.modelData.anticheats.join(", "))
                            opacity: 0.8
                        }
                        Repeater {
                            model: result.modelData.notes
                            delegate: Controls.Label {
                                required property var modelData
                                text: "• " + modelData[0]
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                                opacity: 0.85
                            }
                        }
                        Controls.Label {
                            visible: !!result.modelData.source
                            text: qsTr("Source: %1, last changed %2").arg(result.modelData.source).arg((result.modelData.last_changed || "unknown").slice(0, 10))
                            opacity: 0.6
                            font: Kirigami.Theme.smallFont
                        }
                        Flow {
                            Layout.fillWidth: true
                            spacing: Kirigami.Units.smallSpacing
                            Repeater {
                                model: Object.keys(result.modelData.links)
                                delegate: Kirigami.UrlButton {
                                    required property string modelData
                                    text: modelData
                                    url: result.modelData.links[modelData]
                                }
                            }
                        }
                    }
                }
            }
        }

        SectionCard {
            visible: backend.hybridGraphics
            title: qsTr("Hybrid graphics")
            iconName: "video-card"
            subtitle: qsTr("This computer has an integrated and a discrete GPU. By default the desktop and apps use the integrated one to save battery.")
            RowLayout {
                Layout.fillWidth: true
                Controls.Label {
                    text: qsTr("Run Steam and its games on the discrete GPU")
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                Controls.Switch {
                    checked: backend.steamOnDiscreteGpu
                    onToggled: backend.setSteamOnDiscreteGpu(checked)
                    Accessible.name: qsTr("Run Steam and its games on the discrete GPU")
                }
            }
            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                opacity: 0.8
                text: qsTr("Uses more battery while Steam is open. To choose per game instead, leave this off and right-click a game in Steam > Properties > Launch options.")
            }
        }

        SectionCard {
            title: qsTr("Your Steam library")
            iconName: "steam"

            Kirigami.PlaceholderMessage {
                Layout.fillWidth: true
                visible: backend.library.found === false
                icon.name: "steam"
                text: qsTr("Steam isn't set up yet")
                explanation: qsTr("Open Steam and sign in. Your games will show up here with their compatibility status.")
                helpfulAction: Kirigami.Action {
                    text: qsTr("Open Steam")
                    icon.name: "steam"
                    onTriggered: backend.launch("steam")
                }
            }

            Controls.Label {
                visible: !!backend.library.found
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: qsTr("Proton versions installed: %1").arg(((backend.library.proton_versions || []).concat(backend.library.custom_tools || [])).join(", ") || qsTr("none yet (Steam downloads Proton when you first play a Windows game)"))
            }

            Repeater {
                model: backend.library.rows || []
                delegate: RowLayout {
                    id: gameRow
                    required property var modelData
                    Layout.fillWidth: true
                    ColumnLayout {
                        spacing: 0
                        Layout.fillWidth: true
                        Controls.Label {
                            text: gameRow.modelData.name
                            font.bold: true
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        Controls.Label {
                            text: gameRow.modelData.compatTool ? qsTr("Runs with %1").arg(gameRow.modelData.compatTool) : qsTr("Uses Steam's default compatibility tool")
                            opacity: 0.7
                            font: Kirigami.Theme.smallFont
                        }
                    }
                    CategoryChip {
                        category: gameRow.modelData.category
                        title: gameRow.modelData.title
                        Controls.ToolTip.text: gameRow.modelData.explanation
                        Controls.ToolTip.visible: chipHover.hovered
                        HoverHandler { id: chipHover }
                    }
                    Controls.ToolButton {
                        visible: !!gameRow.modelData.protonLog
                        icon.name: "text-x-log"
                        text: qsTr("Show launch log")
                        display: Controls.AbstractButton.IconOnly
                        onClicked: {
                            page.logGame = gameRow.modelData.name;
                            page.logText = backend.protonLogTail(gameRow.modelData.appid);
                            logSheet.open();
                        }
                        Controls.ToolTip.text: text
                        Controls.ToolTip.visible: hovered
                    }
                    Controls.Button {
                        text: qsTr("Play")
                        icon.name: "media-playback-start"
                        enabled: gameRow.modelData.installed
                        onClicked: Qt.openUrlExternally("steam://rungameid/" + gameRow.modelData.appid)
                        Accessible.name: qsTr("Play %1").arg(gameRow.modelData.name)
                    }
                }
            }
        }

        SectionCard {
            title: qsTr("When a game won't start")
            iconName: "tools-report-bug"
            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                textFormat: Text.StyledText
                text: qsTr("1. Check the game above: some online games block Linux on purpose.<br>2. In Steam, right-click the game > Properties > Compatibility and try “Proton Experimental” or another version.<br>3. To capture a log, set the launch options to <b>PROTON_LOG=1 %command%</b>, start the game once, then come back here. The log button appears next to the game.<br>4. For an FPS counter and frame times, use <b>MANGOHUD=1 %command%</b> (Right Shift + F12 toggles it).")
            }
            Flow {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                Controls.Button {
                    text: qsTr("Install Proton tools (ProtonPlus, Protontricks)")
                    icon.name: "download"
                    enabled: !backend.busy
                    onClicked: backend.installApps(["com.vysp3r.ProtonPlus", "com.github.Matoking.protontricks"])
                }
                Controls.Button {
                    text: qsTr("Open Lutris (Epic, GOG, other stores)")
                    icon.name: "lutris"
                    onClicked: backend.launch("lutris")
                }
            }
        }

        SectionCard {
            title: qsTr("What the ratings mean")
            iconName: "help-about"
            Repeater {
                model: [
                    { c: "verified", t: qsTr("Verified working"), d: qsTr("Valve tested it on Steam Deck/SteamOS. Look for the badge on the game's Steam store page.") },
                    { c: "likely", t: qsTr("Likely working"), d: qsTr("Its anti-cheat is reported to work on Linux.") },
                    { c: "configuration", t: qsTr("Requires configuration"), d: qsTr("Works after a change like another Proton version.") },
                    { c: "issues", t: qsTr("Known issues"), d: qsTr("Parts of the game, often online play, may not work yet.") },
                    { c: "incompatible", t: qsTr("Incompatible"), d: qsTr("Online play is blocked or broken on Linux; it needs Windows. Tamarack OS will never try to bypass anti-cheat.") },
                    { c: "untested", t: qsTr("Not yet tested"), d: qsTr("Not in our data; check ProtonDB community reports.") }
                ]
                delegate: RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    CategoryChip { category: modelData.c; title: modelData.t; Layout.preferredWidth: Kirigami.Units.gridUnit * 10 }
                    Controls.Label { text: modelData.d; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                }
            }
        }
    }

    Kirigami.OverlaySheet {
        id: logSheet
        title: qsTr("Launch log: %1").arg(page.logGame)
        Controls.TextArea {
            implicitWidth: Kirigami.Units.gridUnit * 36
            implicitHeight: Kirigami.Units.gridUnit * 20
            readOnly: true
            wrapMode: TextEdit.Wrap
            font.family: "monospace"
            text: page.logText
        }
    }
}
