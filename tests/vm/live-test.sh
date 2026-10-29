#!/usr/bin/bash
# Live USB test. Two boots of the live ISO in QEMU:
#   1. From the ISO with UEFI, exactly like a USB stick: screenshots of the
#      boot menu and of the live desktop.
#   2. The ISO's own kernel and initramfs with a serial console added, so
#      the system log can be checked: live setup, desktop, signed-in live user.
#
# Usage: live-test.sh LIVE.iso OUTPUT_DIR
set -euo pipefail

iso="$(realpath "$1")"
out="$(realpath -m "$2")"
here="$(dirname "$(realpath "$0")")"
mkdir -p "${out}/screens"
failures=0
check() { # DESCRIPTION COMMAND...
    if "${@:2}"; then echo "PASS: $1"; else echo "FAIL: $1"; failures=$((failures + 1)); fi
}
qmp() { python3 "${here}/qmp.py" "${out}/qmp.sock" "$@"; }
shot() { qmp screenshot "${out}/screens/$1.png" >/dev/null 2>&1 && echo "screenshot: $1" || echo "screenshot failed: $1"; }
stop_vm() { kill "$(cat "${out}/qemu.pid")" 2>/dev/null || true; sleep 3; }
trap stop_vm EXIT

firmware=""
for candidate in /usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/OVMF/OVMF_CODE.fd /usr/share/edk2/ovmf/OVMF_CODE.fd; do
    [[ -f "${candidate}" ]] && firmware="${candidate}" && break
done
[[ -n "${firmware}" ]] || { echo "OVMF firmware not found" >&2; exit 1; }
cp "$(dirname "${firmware}")/$(basename "${firmware}" | sed 's/CODE/VARS/')" "${out}/vars.fd"

common=(-machine "q35,accel=kvm" -cpu max -smp 4 -m 6144 -device virtio-vga -display none
    -netdev "user,id=net0" -device "virtio-net-pci,netdev=net0" -device qemu-xhci -device usb-tablet
    -qmp "unix:${out}/qmp.sock,server=on,wait=off" -daemonize -pidfile "${out}/qemu.pid")

{
    echo "== Boot 1: UEFI from the ISO"
    qemu-system-x86_64 "${common[@]}" \
        -drive "if=pflash,format=raw,readonly=on,file=${firmware}" \
        -drive "if=pflash,format=raw,file=${out}/vars.fd" \
        -drive "file=${iso},media=cdrom,readonly=on"
    # Firmware, boot menu (5 s) and boot screen.
    for frame in $(seq -w 1 15); do
        sleep 3
        shot "01-boot-${frame}"
    done
    for minute in 1 2 3 4; do
        sleep 60
        shot "02-live-desktop-${minute}min"
    done
    stop_vm

    echo "== Boot 2: the ISO's kernel with a serial console"
    xorriso -osirrox on -indev "${iso}" \
        -extract /images/pxeboot/vmlinuz "${out}/vmlinuz" \
        -extract /images/pxeboot/initrd.img "${out}/initrd.img" \
        -extract /boot/grub2/grub.cfg "${out}/grub.cfg" >/dev/null 2>&1
    # The first boot menu entry's arguments, with a serial console added.
    args="$(grep -m1 -E '^\s*linux ' "${out}/grub.cfg" | sed -E 's/^\s*linux \S+ //; s/\b(quiet|rhgb)\b//g')"
    echo "kernel arguments: ${args}"
    qemu-system-x86_64 "${common[@]}" \
        -kernel "${out}/vmlinuz" -initrd "${out}/initrd.img" \
        -append "${args} console=ttyS0,115200 systemd.journald.forward_to_console=1" \
        -drive "file=${iso},media=cdrom,readonly=on" \
        -serial "file:${out}/serial.log"
    start=$(date +%s)
    until grep -q 'New session .* of user liveuser' "${out}/serial.log" 2>/dev/null; do
        (($(date +%s) - start > 600)) && break
        sleep 10
    done
    echo "INFO: live user signed in after $(($(date +%s) - start)) s"
    sleep 90
    shot "03-live-session"
    check "live medium found and mounted" grep -q -E 'dmsquash|LiveOS|live-rootfs|rootfs' "${out}/serial.log"
    check "live system set up (livesys)" grep -q -i 'livesys' "${out}/serial.log"
    check "graphical target reached" grep -q -E 'Reached target (graphical.target|Graphical Interface)' "${out}/serial.log"
    check "live user signed in to the desktop automatically" grep -q 'New session .* of user liveuser' "${out}/serial.log"
    check "Plasma started for the live user" grep -q -E 'plasmashell|plasma-plasmashell' "${out}/serial.log"
    check "Tamarack OS (os-release)" grep -q -i 'Tamarack OS' "${out}/serial.log"
    echo "INFO: failed units"
    grep -E 'Failed to start|FAILED' "${out}/serial.log" | sed 's/^/    /' | head -n 20 || true

    echo
    echo "${failures} failure(s)"
} 2>&1 | tee "${out}/live-checks.txt"
! grep -q '^FAIL' "${out}/live-checks.txt"
