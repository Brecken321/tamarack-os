#!/usr/bin/bash
# Single-quoted bash -c snippets run in a subshell on purpose.
# shellcheck disable=SC2016
# Runs inside a booted Tamarack OS VM (over SSH, as the test user).
# Usage: in-vm-checks.sh PASSWORD PHASE   (PHASE: system | session)
# Prints PASS/FAIL lines and exits non-zero if a required check failed.
set -uo pipefail

password="$1"
phase="$2"
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

if [[ "${phase}" == "system" ]]; then
    # shellcheck source=/dev/null
    source /usr/lib/os-release
    check "booted Tamarack OS (${PRETTY_NAME})" test "${ID}" = "tamarack"
    check "system finished booting" bash -c 'state=$(systemctl is-system-running --wait); [[ $state == running || $state == degraded ]]'
    info "system state" systemctl is-system-running
    check "no failed system units" bash -c '[[ -z "$(systemctl --failed --no-legend --plain)" ]]'
    info "failed units" systemctl --failed --no-legend --plain
    check "graphical target reached" systemctl is-active graphical.target
    check "login manager running" bash -c 'systemctl is-active plasmalogin.service || systemctl is-active sddm.service || systemctl is-active display-manager.service'
    check "rpm-ostree reports a booted deployment" bash -c 'rpm-ostree status --json | jq -e ".deployments[] | select(.booted)"'
    info "rpm-ostree status" rpm-ostree status
    check "bootc status (root)" as_root bootc status
    check "update check verifies signature policy and reaches the registry" as_root bootc upgrade --check
    check "firewall active" systemctl is-active firewalld.service
    check "countme timer is off" bash -c '! systemctl is-enabled rpm-ostree-countme.timer 2>/dev/null | grep -qx enabled'
    check "Steam available" command -v steam
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
    XDG_RUNTIME_DIR="/run/user/$(id -u)"
    export XDG_RUNTIME_DIR
    export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"
    export WAYLAND_DISPLAY=wayland-0
    check "Plasma session is running" pgrep -u "$(id -u)" plasmashell
    lnf="$(kreadconfig6 --file kdeglobals --group KDE --key LookAndFeelPackage)"
    check "Tamarack global theme active (${lnf})" bash -c "[[ '${lnf}' == *tamarack* ]]"
    check "Tamarack color scheme active" bash -c '[[ "$(kreadconfig6 --file kdeglobals --group General --key ColorScheme)" == Tamarack* ]]'
    layout="$(qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript \
        'var p = panels(); for (var i = 0; i < p.length; ++i) { var w = p[i].widgets(); var t = []; for (var j = 0; j < w.length; ++j) t.push(w[j].type); print(p[i].location + " floating=" + p[i].floating + " " + t.join(",") + "\n"); } var d = desktops()[0]; d.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"]; print("wallpaper=" + d.readConfig("Image") + "\n");' 2>&1)"
    printf '    %s\n' "${layout}"
    check "default panel layout from the Tamarack theme" bash -c "grep -q 'org.kde.plasma.kickoff' <<<'${layout}' && grep -q 'org.kde.plasma.icontasks' <<<'${layout}'"
    check "Tamarack wallpaper on the desktop" bash -c "grep -q 'wallpapers/Tamarack' <<<'${layout}'"
    check "Kickoff uses the Tamarack logo" bash -c "qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript 'var w = panels()[0].widgets(\"org.kde.plasma.kickoff\")[0]; w.currentConfigGroup = [\"General\"]; print(w.readConfig(\"icon\", \"\"));' | grep -q tamarack"
fi

echo
echo "${failures} failure(s) in phase ${phase}"
[[ ${failures} -eq 0 ]]
