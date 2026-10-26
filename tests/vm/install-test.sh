#!/usr/bin/bash
# Unattended install test: boot an installer ISO (built with a test kickstart
# that partitions automatically and creates a throwaway user), install onto
# an empty virtual disk, then boot the installed system and check it.
#
# Usage: install-test.sh INSTALLER.iso SSH_KEY PASSWORD OUTPUT_DIR
set -euo pipefail

iso="$(realpath "$1")"
key="$2"
password="$3"
out="$(realpath -m "$4")"
here="$(dirname "$(realpath "$0")")"
mkdir -p "${out}/screens"

firmware=""
for candidate in /usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/OVMF/OVMF_CODE.fd /usr/share/edk2/ovmf/OVMF_CODE.fd; do
    [[ -f "${candidate}" ]] && firmware="${candidate}" && break
done
[[ -n "${firmware}" ]] || { echo "OVMF firmware not found" >&2; exit 1; }
cp "$(dirname "${firmware}")/$(basename "${firmware}" | sed 's/CODE/VARS/')" "${out}/vars.fd"
qemu-img create -f qcow2 "${out}/installed.qcow2" 64G >/dev/null

echo "Installing from ISO (up to 60 minutes)…"
qemu-system-x86_64 \
    -machine q35,accel=kvm -cpu max -smp 4 -m 6144 \
    -drive "if=pflash,format=raw,readonly=on,file=${firmware}" \
    -drive "if=pflash,format=raw,file=${out}/vars.fd" \
    -drive "file=${out}/installed.qcow2,if=virtio,format=qcow2" \
    -drive "file=${iso},media=cdrom,readonly=on" \
    -device virtio-vga -display none \
    -netdev user,id=net0 -device virtio-net-pci,netdev=net0 \
    -qmp "unix:${out}/install-qmp.sock,server=on,wait=off" \
    -no-reboot -daemonize -pidfile "${out}/install.pid"

start=$(date +%s)
shot=0
while kill -0 "$(cat "${out}/install.pid")" 2>/dev/null; do
    if (($(date +%s) - start > 3600)); then
        python3 "${here}/qmp.py" "${out}/install-qmp.sock" screenshot "${out}/screens/install-timeout.png" || true
        kill "$(cat "${out}/install.pid")" || true
        echo "Installation did not finish within 60 minutes" >&2
        exit 1
    fi
    # A screenshot every 2 minutes documents installer progress.
    if (((($(date +%s) - start) / 120) >= shot)); then
        python3 "${here}/qmp.py" "${out}/install-qmp.sock" screenshot \
            "$(printf '%s/screens/install-%02d.png' "${out}" "${shot}")" 2>/dev/null || true
        shot=$((shot + 1))
    fi
    sleep 10
done
echo "Installer finished after $(($(date +%s) - start)) s (VM powered off at reboot)"
echo "install_seconds=$(($(date +%s) - start))" >"${out}/install-timings.txt"

# Boot the installed disk with the regular VM test (system + session checks).
bash "${here}/run-vm-test.sh" "${out}/installed.qcow2" "${key}" "${password}" "${out}/installed-boot"
