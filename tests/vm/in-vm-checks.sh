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
    # Every System Settings page a Tamarack Center button opens must exist.
    for kcm in $(grep -rhoE '"kcm_[A-Za-z0-9_-]+"' /usr/lib/tamarack/python/tamarack/ui/qml | tr -d '"' | sort -u); do
        check "System Settings page ${kcm} exists" bash -c "find /usr/lib64/qt6/plugins -name '${kcm}.so' | grep -q ."
    done
    check "tamarack doctor runs" tamarack doctor --quick
    info "tamarack doctor" tamarack doctor
    check "privacy dashboard data" tamarack privacy --json
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

if [[ "${phase}" == "remove" ]]; then
    session_env
    check "remove Filelight as the desktop user" in_session 600 tamarack apps remove org.kde.filelight
    check "Filelight is gone" bash -c '! flatpak info org.kde.filelight'
    check "Filelight left the start menu" test ! -e /var/lib/flatpak/exports/share/applications/org.kde.filelight.desktop
fi

echo
echo "${failures} failure(s) in phase ${phase}"
[[ ${failures} -eq 0 ]]
