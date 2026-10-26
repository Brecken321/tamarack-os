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
    qmp screenshot "${out}/screens/$1.png" && echo "screenshot: $1"
}
ssh_vm() {
    ssh -i "${key}" -p "${port}" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -o ConnectTimeout=10 -o LogLevel=ERROR "${user}@127.0.0.1" "$@"
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
# Close the first-run welcome so the desktop is visible, then exercise presets.
ssh_vm "${session_env}; pkill -f 'tamarack-center --welcome' || true"
sleep 5
shot "03-desktop-default-preset"
for preset in gaming classic-desktop minimalist high-contrast; do
    ssh_vm "${session_env}; tamarack preset apply ${preset}" | tee -a "${out}/presets.txt" || status=1
    sleep 12
    shot "04-preset-${preset}"
done
ssh_vm "${session_env}; tamarack preset reset" | tee -a "${out}/presets.txt" || status=1
sleep 12
shot "05-preset-reset"

for page in home appearance gaming privacy hardware updates; do
    ssh_vm "${session_env}; (setsid tamarack-center --page ${page} >/tmp/center-${page}.log 2>&1 &)"
    sleep 15
    shot "06-center-${page}"
    ssh_vm "pkill -f 'tamarack-center --page ${page}' || true"
done
ssh_vm "${session_env}; (setsid tamarack-center --welcome >/tmp/center-welcome.log 2>&1 &)"
sleep 15
shot "07-welcome"

# Logs for the report.
ssh_vm "tamarack doctor --json" >"${out}/doctor.json" || true
ssh_vm "journalctl -b --no-pager -o short-monotonic" >"${out}/journal.txt" || true
ssh_vm "cat /tmp/center-*.log ~/.local/state/tamarack/*.log 2>/dev/null" >"${out}/center-logs.txt" || true
ssh_vm "systemd-analyze; systemd-analyze blame | head -n 25; free -m; df -h /" >"${out}/performance.txt" || true

echo "VM test finished with status ${status}"
exit "${status}"
