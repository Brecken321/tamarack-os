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
scp_to_vm "${here}/in-vm-checks.sh" /tmp/in-vm-checks.sh
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
for preset in gaming classic-desktop minimalist high-contrast; do
    ssh_vm "${session_env}; tamarack preset apply ${preset}" | tee -a "${out}/presets.txt" || status=1
    sleep 12
    shot "04-preset-${preset}"
done
ssh_vm "${session_env}; tamarack preset reset" | tee -a "${out}/presets.txt" || status=1
sleep 12
shot "05-preset-reset"

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
    in_vm close "$1" >/dev/null
    sleep 3
}
open_app filelight Filelight 180 org.kde.filelight.desktop
open_app supertux SuperTux 240 org.supertuxproject.SuperTux.desktop
open_app heroic Heroic 300 com.heroicgameslauncher.hgl.desktop
open_app bazaar Bazaar 240 io.github.kolunmi.Bazaar.desktop
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
in_vm close steam >/dev/null
in_vm remove

# Logs for the report.
ssh_vm "tamarack doctor --json" >"${out}/doctor.json" || true
ssh_vm "journalctl -b --no-pager -o short-monotonic" >"${out}/journal.txt" || true
ssh_vm "journalctl --user -b --no-pager -u 'tamarack-*'; cat ~/.local/state/tamarack/*.log 2>/dev/null" >"${out}/center-logs.txt" || true
ssh_vm "systemd-analyze; systemd-analyze blame | head -n 15; free -m; df -h /var /sysroot; top -bn1 | head -n 20" >"${out}/performance.txt" || true

echo "VM test finished with status ${status}"
exit "${status}"
