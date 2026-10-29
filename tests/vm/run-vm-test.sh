#!/usr/bin/bash
# Single-quoted bash -c snippets run in a subshell on purpose.
# shellcheck disable=SC2016
# Boot a Tamarack OS qcow2 disk image in QEMU/KVM (headless), check it over
# SSH, log in to the desktop with the virtual keyboard and take screenshots.
#
# Usage: run-vm-test.sh DISK.qcow2 SSH_KEY PASSWORD OUTPUT_DIR
# Requires: qemu-system-x86_64, OVMF, ssh, python3. Uses a copy-on-write
# overlay, so the disk image itself is never modified.
set -euo pipefail

disk="$(realpath "$1")"
key="$2"
password="$3"
out="$(realpath -m "$4")"
here="$(dirname "$(realpath "$0")")"
user=tamarack
port=2222
mkdir -p "${out}/screens"

qmp() { python3 "${here}/qmp.py" "${out}/qmp.sock" "$@"; }
shot() {
    # A Shift press first: wakes a dimmed or switched-off display (harmless otherwise).
    qmp key shift_r || true
    sleep 1
    if qmp screenshot "${out}/screens/$1.png"; then echo "screenshot: $1"; else echo "screenshot failed: $1"; fi
}
ssh_vm() {
    # Every remote command is bounded so a hang fails the test with logs
    # instead of running into the job timeout.
    timeout "${SSH_TIMEOUT:-1800}" ssh -i "${key}" -p "${port}" \
        -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -o ConnectTimeout=10 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -o LogLevel=ERROR \
        "${user}@127.0.0.1" "$@"
}
# Run a phase of in-vm-checks.sh, adding its output to LOG (download-checks.txt by default).
in_vm() { # PHASE ARGS... (already quoted for the remote shell)
    ssh_vm "bash /tmp/in-vm-checks.sh '${password}' $*" | tee -a "${out}/${LOG:-download-checks.txt}" || status=1
}
scp_to_vm() {
    scp -i "${key}" -P "${port}" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -o LogLevel=ERROR "$1" "${user}@127.0.0.1:$2"
}

firmware=""
for candidate in /usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/OVMF/OVMF_CODE.fd /usr/share/edk2/ovmf/OVMF_CODE.fd; do
    [[ -f "${candidate}" ]] && firmware="${candidate}" && break
done
[[ -n "${firmware}" ]] || { echo "OVMF firmware not found" >&2; exit 1; }
cp "$(dirname "${firmware}")/$(basename "${firmware}" | sed 's/CODE/VARS/')" "${out}/vars.fd"
qemu-img create -f qcow2 -F qcow2 -b "${disk}" "${out}/overlay.qcow2" >/dev/null

accel="kvm"
[[ -w /dev/kvm ]] || { echo "WARNING: /dev/kvm not writable; falling back to slow TCG emulation"; accel="tcg"; }

qemu-system-x86_64 \
    -machine "q35,accel=${accel}" -cpu max -smp 4 -m 6144 \
    -drive "if=pflash,format=raw,readonly=on,file=${firmware}" \
    -drive "if=pflash,format=raw,file=${out}/vars.fd" \
    -drive "file=${out}/overlay.qcow2,if=virtio,format=qcow2" \
    -device virtio-vga -display none -vnc 127.0.0.1:0 \
    -netdev "user,id=net0,hostfwd=tcp:127.0.0.1:${port}-:22" -device virtio-net-pci,netdev=net0 \
    -device qemu-xhci -device usb-tablet \
    -qmp "unix:${out}/qmp.sock,server=on,wait=off" \
    -serial "file:${out}/serial.log" \
    -daemonize -pidfile "${out}/qemu.pid"
trap 'kill "$(cat "${out}/qemu.pid")" 2>/dev/null || true' EXIT

# The boot screen: a picture every 3 seconds while the system starts.
for frame in $(seq -w 1 15); do
    sleep 3
    qmp screenshot "${out}/screens/00-boot-${frame}.png" >/dev/null 2>&1 || true
done

echo "Waiting for SSH (up to 15 minutes)…"
start=$(date +%s)
until ssh_vm true 2>/dev/null; do
    if (($(date +%s) - start > 900)); then
        shot "boot-timeout" || true
        echo "VM did not become reachable over SSH; last serial output:"
        tail -n 80 "${out}/serial.log" || true
        exit 1
    fi
    sleep 15
done
echo "SSH up after $(($(date +%s) - start)) s"
echo "boot_seconds=$(($(date +%s) - start))" >"${out}/timings.txt"

status=0
for helper in in-vm-checks.sh center-drive.py desktop-state.py; do
    scp_to_vm "${here}/${helper}" "/tmp/${helper}"
done
ssh_vm "bash /tmp/in-vm-checks.sh '${password}' system" | tee "${out}/system-checks.txt" || status=1

# Desktop: the login screen, then log in through the virtual keyboard.
sleep 20
shot "01-login-screen"
qmp type "${password}"
qmp key ret
sleep 75
shot "02-desktop-first-login"
ssh_vm "bash /tmp/in-vm-checks.sh '${password}' session" | tee "${out}/session-checks.txt" || status=1

session_env='export XDG_RUNTIME_DIR=/run/user/$(id -u) DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus WAYLAND_DISPLAY=wayland-0 QT_QPA_PLATFORM=wayland'
# Nobody touches the keyboard while apps download, so turn off the automatic
# screen lock for this test session (otherwise screenshots show the lock screen).
ssh_vm "${session_env}; kwriteconfig6 --notify --file kscreenlockerrc --group Daemon --key Autolock false" || true
# Close the first-run welcome so the desktop is visible, then exercise presets.
# "[t]amarack" keeps pkill from matching the ssh command line running it.
ssh_vm "pkill -f '[t]amarack-center --welcome'" || true
sleep 5
shot "03-desktop-default-preset"
# The start menu (Meta key), then close it again.
qmp key meta_l
sleep 4
shot "03-start-menu"
qmp key esc
sleep 2
# Each look, then what Plasma and KWin really use compared with it (checked
# inside the desktop session, which reads the same settings files Plasma does).
# Productivity is always light: it shows the taskbar is readable in the light theme.
desktop_is() { # PRESET_ID
    ssh_vm "${session_env}; systemd-run --user --quiet --wait --pipe --collect python3 -I /tmp/desktop-state.py $1" | tee -a "${out}/${LOG:-presets.txt}" || status=1
}
for preset in gaming classic-desktop minimalist productivity high-contrast; do
    ssh_vm "${session_env}; tamarack preset apply ${preset}" | tee -a "${out}/presets.txt" || status=1
    sleep 12
    shot "04-preset-${preset}"
    desktop_is "${preset}"
done
ssh_vm "${session_env}; tamarack preset reset" | tee -a "${out}/presets.txt" || status=1
sleep 12
shot "05-preset-reset"
desktop_is clean-modern

# Windows-style shortcuts open what they say (pressed on the virtual keyboard).
shortcut() { # NAME WINDOW_TEXT PROCESS KEYS...
    local name="$1" text="$2" process="$3"
    shift 3
    qmp key "$@"
    LOG=shortcut-checks.txt in_vm wait "${name}" "'${text}'" 45 "${process}"
    sleep 3
    shot "05-shortcut-${name}"
    ssh_vm "pkill -x '${process}'" || true
    sleep 2
}
shortcut settings "Settings" systemsettings meta_l i
# Process names are cut to 15 characters by the kernel (pgrep -x matches those).
shortcut task-manager "System Monitor" plasma-systemmo ctrl shift esc
shortcut file-manager "Dolphin" dolphin meta_l e
shortcut emoji "Emoji" plasma-emojier meta_l dot
# Search (KRunner) and Task View (the overview) are not app windows.
qmp key meta_l s
sleep 3
shot "05-shortcut-search"
qmp key esc
sleep 2
qmp key meta_l tab
sleep 3
shot "05-shortcut-task-view"
qmp key esc
sleep 2
ssh_vm "grep -E 'Meta\+I|Ctrl\+Shift\+Esc|Meta\+Tab|Meta\+S' ~/.config/kglobalshortcutsrc" |
    sed 's/^/INFO: /' | tee -a "${out}/shortcut-checks.txt" || true

# "Sign out to switch" (Gaming page) opens Plasma's sign-out confirmation.
if ssh_vm "${session_env}; busctl --user call org.kde.LogoutPrompt /LogoutPrompt org.kde.LogoutPrompt promptLogout"; then
    echo "PASS: Sign out to switch opens the sign-out confirmation" | tee -a "${out}/shortcut-checks.txt"
else
    echo "FAIL: Sign out to switch: no sign-out confirmation" | tee -a "${out}/shortcut-checks.txt"
    status=1
fi
sleep 4
shot "05-sign-out-prompt"
qmp key esc
sleep 2

# Start the app as a user unit so it gets the Plasma session's environment
# (theme, icons, style) exactly like launching it from the start menu.
for page in home appearance apps gaming privacy hardware updates help; do
    ssh_vm "${session_env}; systemd-run --user --collect --unit=tamarack-center-${page} tamarack-center --page ${page}" ||
        status=1
    sleep 15
    shot "06-center-${page}"
    ssh_vm "${session_env}; systemctl --user stop tamarack-center-${page}" || true
done
ssh_vm "${session_env}; systemd-run --user --collect --unit=tamarack-welcome tamarack-center --welcome" || status=1
sleep 15
shot "07-welcome"
ssh_vm "${session_env}; systemctl --user stop tamarack-welcome" || true

# Settings change the real system. Each one is switched in Tamarack Center by
# clicking its control (and typing the password when polkit asks, like a
# person would), checked where it takes effect, then switched back. Every run
# opens a fresh Center, which must show the state the system is in.
settings() { LOG=settings-checks.txt in_vm "$@"; }
state() { ssh_vm "bash /tmp/in-vm-checks.sh '${password}' state $1"; }
center() { # NAME PASSWORD_PROMPTS PAGE STEP... (see center-drive.py)
    local name="$1" prompts="$2"
    shift 2
    settings drive-start "${name}" "$(printf '%q ' "$@")"
    for _ in $(seq 1 "${prompts}"); do
        # Typed only into the dialog, never into whatever else has the keyboard.
        settings password "${name}" 90 | grep -q '^PASS' || { status=1; continue; }
        shot "10-${name}-password"
        qmp type "${password}"
        qmp key ret
    done
    settings drive-finish "${name}" 600
    shot "10-${name}"
}
# ("setting", not "key": ssh_vm reads ${key}, the SSH key.)
flip() { # SETTING PASSWORD_PROMPTS PAGE SWITCH: on/off, then back
    local setting="$1" prompts="$2" page="$3" control="$4" was now
    was="$(state "${setting}")"
    now="$([[ ${was} == on ]] && echo off || echo on)"
    center "${setting}-${now}" "${prompts}" "${page}" "expect:${control}=${was}" "click:${control}" "expect:${control}=${now}"
    settings expect "${setting}" "${now}" "$(printf %q "${control}")"
    center "${setting}-${was}" "${prompts}" "${page}" "expect:${control}=${now}" "click:${control}" "expect:${control}=${was}"
    settings expect "${setting}" "${was}" "$(printf %q "${control}")"
}
flip countme 1 privacy "Help Fedora count installations"
flip connectivity 0 privacy "Detect Wi-Fi sign-in pages"
flip store_search 0 privacy "Show app store results in search"
flip recent_files 0 privacy "Remember recently opened files"

# Game Mode: the performance power profile and Do Not Disturb (it also opens
# Steam Big Picture, which the test records instead of starting).
profile="$(state power_profile)"
echo "INFO: power profile ${profile:-none} (offered: $(state power_profiles))" | tee -a "${out}/settings-checks.txt"
center game-mode-on 0 gaming "expect:Game Mode=off" "click:Game Mode" "expect:Game Mode=on"
if [[ ",$(state power_profiles)," == *,performance,* ]]; then
    settings expect power_profile performance "'Game Mode: power profile'"
fi
settings expect dnd on "'Game Mode: Do Not Disturb (Plasma holds notifications back)'"
center game-mode-off 0 gaming "expect:Game Mode=on" "click:Game Mode" "expect:Game Mode=off"
settings expect power_profile "${profile}" "'Game Mode off: previous power profile'"
settings expect dnd off "'Game Mode off: Do Not Disturb (Plasma shows notifications again)'"
if [[ "$(state dnd)" == on ]]; then
    # Seen once (standard edition only): record what Plasma has, and whether it is only late.
    sleep 30
    {
        echo "INFO: Do Not Disturb 30 s later: $(state dnd)"
        ssh_vm "cat ~/.config/plasmanotifyrc; ${session_env}; busctl --user introspect org.freedesktop.Notifications \
            /org/freedesktop/Notifications org.freedesktop.Notifications" | sed 's/^/    /'
    } | tee -a "${out}/settings-checks.txt"
fi
# The performance overlay stays on until Steam has been opened below.
overlay="Performance overlay in all Steam games"
center overlay-on 0 gaming "expect:${overlay}=off" "click:${overlay}" "expect:${overlay}=on"
settings expect steam_overlay on "'Steam starts with the performance overlay'"

# Looks, from the Appearance page: apply one, reset to the default, undo.
LOG=settings-checks.txt
center look-gaming 0 appearance "click:Apply@Gaming"
sleep 10
desktop_is gaming
center look-reset 0 appearance "click:Reset to default" "click:OK"
sleep 10
desktop_is clean-modern
center look-undo 0 appearance "click:Undo last change"
sleep 15
desktop_is gaming
# A custom look: three changes in Customize, saved and applied, then deleted.
center look-custom 0 appearance "click:Customize…@Gaming" "click:Floating:" \
    "click:Blur behind panels and menus:" "click:Start Steam at login:" "click:Save and apply"
settings expect custom_look "floating,blur,steam" "'Customize: the saved look has the three changes'"
sleep 10
desktop_is custom-my-gaming
center look-delete 0 appearance "click:More Actions@My Gaming" "click:Delete"
settings expect custom_look missing "'Delete removes the custom look'"
# The first-run Welcome, start to finish, picking a look on the way.
ssh_vm "rm -f ~/.local/state/tamarack/welcome-done"
center welcome 0 --welcome welcome "click:Get started" "click:Use this@Classic Desktop" \
    "click:Next" "click:Next" "click:Next" "click:Next" "click:Finish"
sleep 10
desktop_is classic-desktop
settings expect welcome_done on "'Welcome remembers it was completed'"
unset LOG

# Downloads, for real and without accounts: an app, a game and a game
# launcher from Flathub through Tamarack's installer (what the Install
# buttons run), each opened on the desktop; the Bazaar app store; and Steam's
# own first-run download up to its sign-in window.
ssh_vm "bash /tmp/in-vm-checks.sh '${password}' downloads" | tee "${out}/download-checks.txt" || status=1
open_app() { # NAME WINDOW_TEXT TIMEOUT DESKTOP_ID
    in_vm start "$1" "$4"
    in_vm wait "$1" "'$2'" "$3"
    sleep 10
    shot "08-open-$1"
    in_vm close "$1" "$4" >/dev/null
    sleep 3
}
open_app filelight Filelight 180 org.kde.filelight.desktop
open_app supertux SuperTux 240 org.supertuxproject.SuperTux.desktop
open_app heroic Heroic 300 com.heroicgameslauncher.hgl.desktop
open_app bazaar Bazaar 240 io.github.kolunmi.Bazaar.desktop
open_app firefox Firefox 120 org.mozilla.firefox.desktop
open_app center "Tamarack Center" 60 io.github.brecken321.tamarack.Center.desktop
# Steam: Bazzite's launcher first shows a "Steam is opening for the first
# time" notice and waits for OK; press Enter like a person would, then let
# Steam download its client and wait for its window.
in_vm start steam steam.desktop
sleep 20
shot "08-steam-first-run-notice"
qmp key ret
sleep 5
ssh_vm "pkill -x kdialog && echo 'INFO: closed the first-run notice directly (Enter did not reach it)'" |
    tee -a "${out}/download-checks.txt" || true
in_vm wait steam Steam 1200 steamwebhelper
sleep 15
shot "08-open-steam"
# Steam was started from its start menu entry with the overlay switch on.
if ssh_vm 'tr "\0" "\n" </proc/"$(pgrep -u "$(id -u)" -x steam | head -n 1)"/environ | grep -qx MANGOHUD=1'; then
    echo "PASS: Steam runs with the performance overlay (MANGOHUD=1)" | tee -a "${out}/settings-checks.txt"
else
    echo "FAIL: Steam runs with the performance overlay (MANGOHUD=1)" | tee -a "${out}/settings-checks.txt"
    status=1
fi
in_vm close steam >/dev/null
in_vm remove
center overlay-off 0 gaming "expect:${overlay}=on" "click:${overlay}" "expect:${overlay}=off"
settings expect steam_overlay off "'Steam starts without the performance overlay'"

# Updates page: automatic updates, keeping this version, and Update now.
flip auto_updates 1 updates "Automatic updates"
center keep-version 1 updates "click:Keep this version"
settings expect pinned on "'Keep this version: the running version is pinned'"
ssh_vm "echo '${password}' | sudo -S -p '' ostree admin pin --unpin 0" >/dev/null || true
runs="$(state update_runs)"
center update-now 1 updates "click:Update now"
settings expect update_runs "$((runs + 1))" "'Update now starts the update service'"
ssh_vm "echo '${password}' | sudo -S -p '' timeout 1800 bash -c 'while [[ \$(systemctl show -p ActiveState --value uupd.service) == activating ]]; do sleep 10; done'; systemctl show -p Result uupd.service" |
    sed 's/^/INFO: update service after Update now: /' | tee -a "${out}/settings-checks.txt" || true
# QML errors in any of those Tamarack Center runs, also while it closed
# (after each run's own report).
qml_errors="$(ssh_vm "journalctl --user -b --no-pager -o cat -u 'tamarack-drive-*'; cat /tmp/drive-*.log" |
    grep -E 'qml:[0-9]+: (TypeError|ReferenceError)' | sort | uniq -c | sort -rn || true)"
if [[ -z "${qml_errors}" ]]; then
    echo "PASS: Tamarack Center logged no QML errors, also while closing" | tee -a "${out}/settings-checks.txt"
else
    { echo "FAIL: Tamarack Center logged QML errors:"; head -n 20 <<<"${qml_errors}" | sed 's/^/    /'; } |
        tee -a "${out}/settings-checks.txt"
    status=1
fi

# Steam Gaming Mode itself: sign in to it automatically and see what happens.
# gamescope needs a real GPU, so in a VM this is recorded, not required.
ssh_vm "printf '[Autologin]\nUser=${user}\nSession=gamescope-session-steam.desktop\n' >/tmp/gaming-autologin.conf &&
    echo '${password}' | sudo -S -p '' bash -c 'cat /tmp/gaming-autologin.conf >>/etc/plasmalogin.conf && systemctl restart plasmalogin'" ||
    true
sleep 90
shot "09-steam-gaming-mode"
{
    echo "INFO: Steam Gaming Mode in the VM (needs a real GPU; not a test failure):"
    ssh_vm "pgrep -a -u ${user} -f 'gamescope|steam' | cut -c1-160; loginctl list-sessions --no-legend" | sed 's/^/    /' || true
} | tee -a "${out}/shortcut-checks.txt"

# Logs for the report.
ssh_vm "tamarack doctor --json" >"${out}/doctor.json" || true
ssh_vm "journalctl -b --no-pager -o short-monotonic" >"${out}/journal.txt" || true
ssh_vm "journalctl --user -b --no-pager -u 'tamarack-*'; cat ~/.local/state/tamarack/*.log 2>/dev/null" >"${out}/center-logs.txt" || true
ssh_vm "systemd-analyze; systemd-analyze blame | head -n 15; free -m; df -h /var /sysroot; top -bn1 | head -n 20" >"${out}/performance.txt" || true

echo "VM test finished with status ${status}"
exit "${status}"
