#!/usr/bin/bash
# Single-quoted bash -c snippets run in a subshell on purpose.
# shellcheck disable=SC2016
# Runs inside a booted Tamarack OS VM (over SSH, as the test user).
# Usage: in-vm-checks.sh PASSWORD PHASE [ARGS...]
#   system | session | downloads | remove
#   start NAME DESKTOP_ID          start an app in the desktop session
#   wait NAME WINDOW_TEXT TIMEOUT [PROCESS]
#        wait for the app's window (and, if given, for PROCESS to run too)
#   close NAME
# Prints PASS/FAIL lines and exits non-zero if a required check failed.
set -uo pipefail

password="$1"
phase="$2"
shift 2
failures=0
pass() { echo "PASS: $*"; }
fail() {
    echo "FAIL: $*"
    failures=$((failures + 1))
}
check() {
    local description="$1"
    shift
    if "$@" >/tmp/vmcheck.out 2>&1; then
        pass "${description}"
    else
        fail "${description}"
        sed 's/^/    /' /tmp/vmcheck.out | tail -n 25
    fi
}
info() {
    echo "INFO: $1"
    shift
    "$@" 2>&1 | sed 's/^/    /' | head -n 60
}
as_root() { echo "${password}" | sudo -S -p '' "$@"; }
# The IDs KRunner knows its plugins by (krunnerrc's "<ID>Enabled" keys): the
# ID in a compiled plugin's metadata (else its file name), or a D-Bus plugin's name.
krunner_plugin_ids() {
    python3 -I -c '
import glob, pathlib
from PySide6.QtCore import QPluginLoader
for so in sorted(glob.glob("/usr/lib64/qt6/plugins/kf6/krunner/*.so")):
    meta = QPluginLoader(so).metaData().get("MetaData", {})
    print(meta.get("KPlugin", {}).get("Id") or pathlib.Path(so).stem)
'
    sed -n 's/^X-KDE-PluginInfo-Name=//p' /usr/share/krunner/dbusplugins/*.desktop \
        /var/lib/flatpak/exports/share/krunner/dbusplugins/*.desktop 2>/dev/null
}
export -f krunner_plugin_ids
# The desktop session's environment, for commands that talk to Plasma.
session_env() {
    XDG_RUNTIME_DIR="/run/user/$(id -u)"
    export XDG_RUNTIME_DIR
    export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"
    export WAYLAND_DISPLAY=wayland-0
}
# Run a command as a user service of the desktop session: the same context
# as an app started from the start menu (Tamarack Center's Install button
# runs `flatpak install` from there, authorized by polkit for the session).
# Usage: in_session TIMEOUT COMMAND...
in_session() { timeout "$1" systemd-run --user --quiet --wait --pipe --collect -- "${@:2}"; }
# Captions of open windows whose title or app name contains $1 (KWin's
# window search, the one KRunner uses).
windows_matching() {
    busctl --user --json=short call org.kde.KWin /WindowsRunner org.kde.krunner1 Match s "$1" |
        jq -r '.data[0][] | .[1]'
}
# The command line of a desktop entry (field codes like %U removed).
desktop_exec() {
    local file
    for file in "${HOME}/.local/share/applications/$1" "/var/lib/flatpak/exports/share/applications/$1" \
        "/usr/share/applications/$1"; do
        if [[ -f "${file}" ]]; then
            grep -m1 '^Exec=' "${file}" | cut -d= -f2- | sed -E 's/ %[a-zA-Z]//g'
            return 0
        fi
    done
    return 1
}

if [[ "${phase}" == "system" ]]; then
    # shellcheck source=/dev/null
    source /usr/lib/os-release
    check "booted Tamarack OS (${PRETTY_NAME})" test "${ID}" = "tamarack"
    # Bounded: a start job that never finishes would otherwise block forever.
    check "system finished booting" bash -c 'state=$(timeout 600 systemctl is-system-running --wait); [[ $state == running || $state == degraded ]]'
    info "system state" systemctl is-system-running
    info "pending jobs" systemctl list-jobs --no-pager
    check "no failed system units" bash -c '[[ -z "$(systemctl --failed --no-legend --plain)" ]]'
    info "failed units" systemctl --failed --no-legend --plain
    for unit in $(systemctl --failed --no-legend --plain | awk '{print $1}'); do
        info "log of ${unit}" journalctl -b -u "${unit}" --no-pager -q
    done
    check "graphical target reached" systemctl is-active graphical.target
    check "login manager running" bash -c 'systemctl is-active plasmalogin.service || systemctl is-active sddm.service || systemctl is-active display-manager.service'
    check "rpm-ostree reports a booted deployment" bash -c 'rpm-ostree status --json | jq -e ".deployments[] | select(.booted)"'
    info "rpm-ostree status" rpm-ostree status
    check "bootc status (root)" as_root bootc status
    check "update check verifies signature policy and reaches the registry" as_root bootc upgrade --check
    check "firewall active" systemctl is-active firewalld.service
    check "countme timer is off" bash -c '! systemctl is-enabled rpm-ostree-countme.timer 2>/dev/null | grep -qx enabled'
    check "Steam available" command -v steam
    check "boot screen is the Tamarack theme" bash -c '[[ "$(plymouth-set-default-theme)" == tamarack ]]'
    info "kernel command line" cat /proc/cmdline
    check "Steam Gaming Mode session on the sign-in screen" \
        grep -qx 'Name=Steam Gaming Mode' /usr/share/wayland-sessions/gamescope-session-steam.desktop
    check "Gaming Mode session command available" command -v gamescope-session-plus
    check "Switch to Desktop in Steam is handled" command -v steamos-session-select
    # Every System Settings page a Tamarack Center button opens must exist.
    for kcm in $(grep -rhoE '"kcm_[A-Za-z0-9_-]+"' /usr/lib/tamarack/python/tamarack/ui/qml | tr -d '"' | sort -u); do
        check "System Settings page ${kcm} exists" bash -c "find /usr/lib64/qt6/plugins -name '${kcm}.so' | grep -q ."
    done
    check "tamarack doctor runs" tamarack doctor --quick
    info "tamarack doctor" tamarack doctor
    check "privacy dashboard data" tamarack privacy --json
    # "Show app store results in search" turns KRunner's plugin "bazaarrunner" on and off:
    # krunnerrc's key is the plugin's ID, which need not be its file name.
    info "search (KRunner) plugin IDs" krunner_plugin_ids
    check "the app store search switch's plugin (ID bazaarrunner) exists" bash -c "krunner_plugin_ids | grep -qx bazaarrunner"
    check "anti-cheat check" tamarack games check "Apex Legends"
    # Default apps install from Flathub on first boot; allow time for the download.
    for _ in $(seq 1 60); do
        state="$(jq -r .state /var/lib/tamarack/flatpak-setup.status 2>/dev/null || echo pending)"
        [[ "${state}" == "done" ]] && break
        sleep 10
    done
    check "default apps installed (first-boot setup)" bash -c 'jq -e ".state == \"done\"" /var/lib/tamarack/flatpak-setup.status'
    check "Firefox installed as a Flatpak" flatpak info org.mozilla.firefox
    check "Firefox privacy defaults copied into Firefox config" \
        test -s /var/lib/flatpak/extension/org.mozilla.firefox.systemconfig/x86_64/stable/defaults/pref/tamarack-privacy.js
    info "flatpak apps" flatpak list --app --columns=application
    info "errors this boot" journalctl -b -p err --no-pager -q
fi

if [[ "${phase}" == "session" ]]; then
    session_env
    check "Plasma session is running" pgrep -u "$(id -u)" plasmashell
    lnf="$(kreadconfig6 --file kdeglobals --group KDE --key LookAndFeelPackage)"
    check "Tamarack global theme active (${lnf})" bash -c "[[ '${lnf}' == *tamarack* ]]"
    check "Tamarack color scheme active" bash -c '[[ "$(kreadconfig6 --file kdeglobals --group General --key ColorScheme)" == Tamarack* ]]'
    layout="$(busctl --user call org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell evaluateScript s \
        'var p = panels(); for (var i = 0; i < p.length; ++i) { var w = p[i].widgets(); var t = []; for (var j = 0; j < w.length; ++j) t.push(w[j].type); print(p[i].location + " floating=" + p[i].floating + " " + t.join(",") + "\n"); } var d = desktops()[0]; d.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"]; print("wallpaper=" + d.readConfig("Image") + "\n");' 2>&1)"
    printf '    %s\n' "${layout}"
    check "default panel layout from the Tamarack theme" bash -c "grep -q 'org.kde.plasma.kickoff' <<<'${layout}' && grep -q 'org.kde.plasma.icontasks' <<<'${layout}'"
    check "Tamarack wallpaper on the desktop" bash -c "grep -q 'wallpapers/Tamarack' <<<'${layout}'"
    check "Kickoff uses the Tamarack logo" bash -c "busctl --user call org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell evaluateScript s 'var w = panels()[0].widgets(\"org.kde.plasma.kickoff\")[0]; w.currentConfigGroup = [\"General\"]; print(w.readConfig(\"icon\", \"\"));' | grep -q tamarack"
    # Every app pinned to the taskbar or the start menu's favorites is installed.
    pins="$(busctl --user call org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell evaluateScript s \
        'var t = panels()[0].widgets("org.kde.plasma.icontasks")[0]; t.currentConfigGroup = ["General"]; print(t.readConfig("launchers", ""));' 2>&1)"
    favorites="$(grep -h '^Prepend=' /usr/share/kde-settings/kde-profile/default/xdg/kicker-extra-favoritesrc 2>/dev/null)"
    while read -r entry; do
        check "pinned app ${entry} is installed" bash -c \
            "ls /usr/share/applications/${entry} /var/lib/flatpak/exports/share/applications/${entry} 2>/dev/null | grep -q ."
    done < <(grep -oE '[A-Za-z0-9._-]+\.desktop' <<<"${pins} ${favorites}" | sort -u)
fi

# Real downloads from Flathub: an app, a game and a game launcher, installed
# by the user through Tamarack's installer (what the Center's Install buttons
# run), not by root.
if [[ "${phase}" == "downloads" ]]; then
    session_env
    check "Flathub catalog is reachable" bash -c \
        'flatpak remote-ls --app --columns=application flathub | grep -qx org.supertuxproject.SuperTux'
    check "first boot downloaded Flathub's app catalog" test -d /var/lib/flatpak/appstream/flathub
    for query in filelight:org.kde.filelight supertux:org.supertuxproject.SuperTux; do
        check "app search for \"${query%%:*}\" finds ${query#*:}" bash -c \
            "systemd-run --user --quiet --wait --pipe --collect tamarack apps search ${query%%:*} | grep -q '^${query#*:} '"
    done
    for app in org.kde.filelight org.supertuxproject.SuperTux com.heroicgameslauncher.hgl; do
        start=$(date +%s)
        check "download and install ${app} as the desktop user" in_session 1500 tamarack apps install "${app}"
        echo "INFO: ${app} took $(($(date +%s) - start)) s"
        check "${app} is installed" flatpak info "${app}"
        check "${app} is in the start menu" test -f "/var/lib/flatpak/exports/share/applications/${app}.desktop"
    done
    # Claude Code the way its docs install it: into the home folder, which
    # works with Tamarack's read-only system files.
    check "Claude Code installs with its official installer" bash -c \
        'curl -fsSL https://claude.ai/install.sh | bash >/dev/null 2>&1'
    check "Claude Code runs" bash -c '"${HOME}/.local/bin/claude" --version | grep -q "Claude Code"'
    info "Claude Code version" "${HOME}/.local/bin/claude" --version
    info "installed apps" flatpak list --app --columns=application,name,size
    info "disk use" df -h /var
fi

if [[ "${phase}" == "start" ]]; then
    session_env
    name="$1" desktop_id="$2"
    command="$(desktop_exec "${desktop_id}")"
    check "${desktop_id} has a desktop entry" test -n "${command}"
    echo "INFO: starting ${command}"
    check "${name} started" systemd-run --user --quiet --collect --unit="tamarack-open-${name}" -- bash -c "exec ${command}"
fi

if [[ "${phase}" == "wait" ]]; then
    session_env
    name="$1" text="$2" timeout="$3" process="${4:-}"
    start=$(date +%s)
    found=""
    while (($(date +%s) - start < timeout)); do
        found="$(windows_matching "${text}" 2>/dev/null | head -n 1)"
        if [[ -n "${process}" ]] && ! pgrep -u "$(id -u)" -x "${process}" >/dev/null; then
            found=""
        fi
        [[ -n "${found}" ]] && break
        sleep 5
    done
    check "${name} opened a window matching \"${text}\" (after $(($(date +%s) - start)) s: ${found:-none})" test -n "${found}"
    if [[ -z "${found}" ]]; then
        info "processes for ${name}" pgrep -a -u "$(id -u)" -i -f "${name}"
        info "session log for ${name}" bash -c "journalctl --user -b --no-pager -o short-monotonic | grep -i '${name}' | tail -n 30"
    fi
    if [[ -n "${process}" ]]; then
        check "${process} is running" pgrep -u "$(id -u)" -x "${process}"
    fi
    # Apps started by the test run as a unit; ones opened by a shortcut do not.
    if systemctl --user cat "tamarack-open-${name}" >/dev/null 2>&1; then
        check "${name} is still running" systemctl --user is-active "tamarack-open-${name}"
        info "processes" systemctl --user status "tamarack-open-${name}" --no-pager -n 0
    fi
    info "windows (KWin search for \"window\")" windows_matching window
fi

if [[ "${phase}" == "close" ]]; then
    session_env
    systemctl --user stop "tamarack-open-$1" 2>/dev/null
    # Flatpak runs each app in its own scope, out of reach of the unit above.
    app_id="${2:-}"
    app_id="${app_id%.desktop}"
    if [[ -n "${app_id}" ]] && flatpak info "${app_id}" >/dev/null 2>&1; then
        flatpak kill "${app_id}" 2>/dev/null
    fi
    sleep 2
    pass "closed $1"
fi

# --- Settings, changed in Tamarack Center (center-drive.py) and read back here.
# Whether an on/off setting is on, where it takes effect.
setting_on() {
    case "$1" in
        countme) [[ "$(systemctl is-enabled rpm-ostree-countme.timer 2>/dev/null)" == enabled ]] ;;
        connectivity)
            busctl get-property org.freedesktop.NetworkManager /org/freedesktop/NetworkManager \
                org.freedesktop.NetworkManager ConnectivityCheckEnabled | grep -q true
            ;;
        store_search)
            [[ "$(kreadconfig6 --file krunnerrc --group Plugins --key bazaarrunnerEnabled --default true)" != false ]] ;;
        recent_files)
            [[ "$(kreadconfig6 --file kactivitymanagerd-pluginsrc --group Plugin-org.kde.ActivityManager.Resources.Scoring \
                --key what-to-remember --default 0)" != 2 ]]
            ;;
        # Whether Plasma holds notifications back (the tray's notifications
        # widget announces it), not only what the settings file says.
        dnd)
            busctl --user get-property org.freedesktop.Notifications /org/freedesktop/Notifications \
                org.freedesktop.Notifications Inhibited | grep -q true
            ;;
        steam_overlay) grep -qs 'MANGOHUD=1' "${HOME}/.local/share/applications/steam.desktop" ;;
        auto_updates) [[ "$(systemctl is-enabled uupd.timer 2>/dev/null)" == enabled ]] ;;
        # The running version's entry in `ostree admin status` (marked "*").
        pinned) ostree admin status 2>/dev/null | awk '/^\*/ {b = 1; next} /^  [^ ]/ {b = 0} b' | grep -q 'Pinned: yes' ;;
        welcome_done) test -e "${HOME}/.local/state/tamarack/welcome-done" ;;
        *) return 2 ;;
    esac
}
# The real state of a setting: on/off, or its value.
setting_state() {
    case "$1" in
        power_profile)
            busctl get-property net.hadess.PowerProfiles /net/hadess/PowerProfiles net.hadess.PowerProfiles \
                ActiveProfile | cut -d'"' -f2
            ;;
        power_profiles)
            busctl --json=short get-property net.hadess.PowerProfiles /net/hadess/PowerProfiles \
                net.hadess.PowerProfiles Profiles | jq -r '[.data[].Profile.data] | join(",")'
            ;;
        update_runs) journalctl -b -u uupd.service -o cat 2>/dev/null | grep -c '^Starting ' ;;
        # What the custom look "My Gaming" changes from Gaming ("missing" if there is none).
        custom_look)
            python3 -I -c '
import sys
from pathlib import Path
sys.path.insert(0, "/usr/lib/tamarack/python")
from tamarack import appearance
found = {p.id: p for p in appearance.all_presets(appearance.Paths(Path.home()))}
mine, base = found.get("custom-my-gaming"), found["gaming"]
if mine is None:
    print("missing")
else:
    fields = {"floating": lambda p: p.panel.floating, "blur": lambda p: p.appearance.blur,
              "steam": lambda p: p.behavior.steam_autostart}
    print(",".join(n for n, get in fields.items() if get(mine) != get(base)) or "none")
'
            ;;
        *) if setting_on "$1"; then echo on; else echo off; fi ;;
    esac
}

if [[ "${phase}" == "state" ]]; then
    # Only the value: callers capture it.
    session_env
    setting_state "$1"
    exit 0
fi

if [[ "${phase}" == "expect" ]]; then
    session_env
    key="$1" want="$2" description="${3:-$1}"
    # Some take effect a moment later (Plasma re-reads a changed settings file).
    for _ in 1 2 3 4 5; do
        have="$(setting_state "${key}")"
        [[ "${have}" == "${want}" ]] && break
        sleep 2
    done
    check "${description}: ${want} (the system says ${have})" test "${have}" = "${want}"
fi

if [[ "${phase}" == "drive-start" ]]; then
    session_env
    name="$1"
    shift
    rm -f "/tmp/drive-${name}.log" "/tmp/drive-${name}.rc"
    # As a user service of the desktop session, like an app from the start menu.
    check "Tamarack Center opened for \"${name}\"" systemd-run --user --quiet --collect --unit="tamarack-drive-${name}" \
        -- bash -c "python3 -I /tmp/center-drive.py $(printf '%q ' "$@") >/tmp/drive-${name}.log 2>&1; echo \$? >/tmp/drive-${name}.rc"
fi

if [[ "${phase}" == "password" ]]; then
    # polkit's password dialog, as a person sees it after clicking.
    session_env
    name="$1" timeout="$2"
    start=$(date +%s)
    caption=""
    while (($(date +%s) - start < timeout)) && [[ ! -e "/tmp/drive-${name}.rc" ]]; do
        caption="$( (windows_matching Authentication; windows_matching polkit) 2>/dev/null | head -n 1)"
        [[ -n "${caption}" ]] && break
        sleep 2
    done
    check "\"${name}\" asks for the password (after $(($(date +%s) - start)) s: ${caption:-no dialog})" test -n "${caption}"
    if [[ -n "${caption}" ]]; then
        # Give it the keyboard, as a click on it would.
        script="/tmp/activate-${name}.js"
        printf 'for (const w of workspace.windowList()) { if (w.caption === %s) workspace.activeWindow = w; }\n' \
            "$(jq -Rn --arg c "${caption}" '$c')" >"${script}"
        id="$(busctl --user call org.kde.KWin /Scripting org.kde.kwin.Scripting loadScript ss "${script}" "activate-${name}" | awk '{print $2}')"
        busctl --user call org.kde.KWin "/Scripting/Script${id}" org.kde.kwin.Script run >/dev/null 2>&1
        sleep 1
        busctl --user call org.kde.KWin /Scripting org.kde.kwin.Scripting unloadScript s "activate-${name}" >/dev/null 2>&1
    fi
fi

if [[ "${phase}" == "drive-finish" ]]; then
    session_env
    name="$1" timeout="$2"
    start=$(date +%s)
    while [[ ! -e "/tmp/drive-${name}.rc" ]] && (($(date +%s) - start < timeout)); do sleep 3; done
    cat "/tmp/drive-${name}.log" 2>/dev/null
    check "Tamarack Center did \"${name}\" without problems" test "$(cat "/tmp/drive-${name}.rc" 2>/dev/null)" = 0
    systemctl --user stop "tamarack-drive-${name}" 2>/dev/null
fi

if [[ "${phase}" == "remove" ]]; then
    session_env
    check "remove Filelight as the desktop user" in_session 600 tamarack apps remove org.kde.filelight
    check "Filelight is gone" bash -c '! flatpak info org.kde.filelight'
    check "Filelight left the start menu" test ! -e /var/lib/flatpak/exports/share/applications/org.kde.filelight.desktop
fi

echo
echo "${failures} failure(s) in phase ${phase}"
[[ ${failures} -eq 0 ]]
