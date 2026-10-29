#!/usr/bin/bash
# Update and rollback test: boot an older Tamarack build, move it to the
# current :stable (download, signature check, staged for the next restart),
# reboot into the new version and check it, including that the update service
# automatic updates and "Update now" use runs cleanly there; then roll back
# with Tamarack Center's "Roll back" (clicked in the desktop) and check that the
# old version boots again.
#
# Usage: update-test.sh OLD_DISK.qcow2 SSH_KEY PASSWORD OUTPUT_DIR NEW_REF NEW_DIGEST
set -euo pipefail

disk="$(realpath "$1")"
key="$2"
password="$3"
out="$(realpath -m "$4")"
new_ref="$5"
new_digest="$6"
here="$(dirname "$(realpath "$0")")"
user=tamarack
port=2222
mkdir -p "${out}/screens"

qmp() { python3 "${here}/qmp.py" "${out}/qmp.sock" "$@"; }
shot() {
    qmp key shift_r || true
    sleep 1
    if qmp screenshot "${out}/screens/$1.png"; then echo "screenshot: $1"; else echo "screenshot failed: $1"; fi
}
ssh_vm() {
    timeout "${SSH_TIMEOUT:-2400}" ssh -i "${key}" -p "${port}" \
        -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -o ConnectTimeout=10 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -o LogLevel=ERROR \
        "${user}@127.0.0.1" "$@"
}
as_root() { ssh_vm "echo '${password}' | sudo -S -p '' $*"; }
booted_digest() { as_root bootc status --json | jq -r '.status.booted.image.imageDigest'; }
wait_ssh() { # LABEL
    local start
    start=$(date +%s)
    until ssh_vm true 2>/dev/null; do
        if (($(date +%s) - start > 900)); then
            shot "$1-timeout"
            echo "FAIL: no SSH after $1"
            tail -n 60 "${out}/serial.log" || true
            exit 1
        fi
        sleep 10
    done
    echo "INFO: SSH up $(($(date +%s) - start)) s after $1"
}
reboot_vm() { # LABEL
    as_root systemctl reboot || true
    # Wait for the old system to go away before waiting for the new one.
    for _ in $(seq 1 60); do ssh_vm true 2>/dev/null || break; sleep 5; done
    wait_ssh "$1"
}
failures=0
check() { # DESCRIPTION COMMAND...
    if "${@:2}"; then echo "PASS: $1"; else echo "FAIL: $1"; failures=$((failures + 1)); fi
}

firmware=""
for candidate in /usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/OVMF/OVMF_CODE.fd /usr/share/edk2/ovmf/OVMF_CODE.fd; do
    [[ -f "${candidate}" ]] && firmware="${candidate}" && break
done
[[ -n "${firmware}" ]] || { echo "OVMF firmware not found" >&2; exit 1; }
cp "$(dirname "${firmware}")/$(basename "${firmware}" | sed 's/CODE/VARS/')" "${out}/vars.fd"
qemu-img create -f qcow2 -F qcow2 -b "${disk}" "${out}/overlay.qcow2" >/dev/null

qemu-system-x86_64 \
    -machine q35,accel=kvm -cpu max -smp 4 -m 6144 \
    -drive "if=pflash,format=raw,readonly=on,file=${firmware}" \
    -drive "if=pflash,format=raw,file=${out}/vars.fd" \
    -drive "file=${out}/overlay.qcow2,if=virtio,format=qcow2" \
    -device virtio-vga -display none \
    -netdev "user,id=net0,hostfwd=tcp:127.0.0.1:${port}-:22" -device virtio-net-pci,netdev=net0 \
    -device qemu-xhci -device usb-tablet \
    -qmp "unix:${out}/qmp.sock,server=on,wait=off" \
    -serial "file:${out}/serial.log" \
    -daemonize -pidfile "${out}/qemu.pid"
trap 'kill "$(cat "${out}/qemu.pid")" 2>/dev/null || true' EXIT

{
    wait_ssh "first boot"
    old_digest="$(booted_digest)"
    echo "INFO: old version $(as_root bootc status --json | jq -r '.status.booted.image.version') (${old_digest})"
    check "the old build is not already the current one" test "${old_digest}" != "${new_digest}"

    # Let first-boot work finish: the update service postpones itself on a busy system.
    as_root timeout 900 systemctl is-system-running --wait >/dev/null || true
    for _ in $(seq 1 60); do
        [[ "$(ssh_vm "jq -r .state /var/lib/tamarack/flatpak-setup.status 2>/dev/null")" == "done" ]] && break
        sleep 10
    done

    # Move to :stable, where installed systems get their updates. This downloads
    # the new version, checks its signature and stages it for the next restart.
    start=$(date +%s)
    check "download and stage ${new_ref}" as_root bootc switch --transport registry "${new_ref}"
    echo "INFO: download and staging took $(($(date +%s) - start)) s"
    staged="$(as_root bootc status --json | jq -r '.status.staged.image.imageDigest // empty')"
    check "the new version is staged for the next restart (${staged:-nothing})" test "${staged}" = "${new_digest}"
    ssh_vm "tamarack updates status --json" >"${out}/status-before-restart.json" || true
    check "tamarack updates status: restart needed" jq -e '.restart_needed == true' "${out}/status-before-restart.json"

    reboot_vm "update"
    check "booted the new version" test "$(booted_digest)" = "${new_digest}"
    check "the old version is kept for rollback" \
        test "$(as_root bootc status --json | jq -r '.status.rollback.image.imageDigest')" = "${old_digest}"
    for helper in in-vm-checks.sh center-drive.py; do
        scp -i "${key}" -P "${port}" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR \
            "${here}/${helper}" "${user}@127.0.0.1:/tmp/${helper}"
    done
    if ssh_vm "bash /tmp/in-vm-checks.sh '${password}' system" >"${out}/updated-system-checks.txt"; then
        echo "PASS: all system checks on the updated system"
    else
        echo "FAIL: system checks on the updated system"
        failures=$((failures + 1))
    fi
    grep -E '^(PASS|FAIL)' "${out}/updated-system-checks.txt" | sed 's/^/    /'
    # The update service that automatic updates and "Update now" start: it
    # must find the system up to date and finish without errors.
    if as_root systemctl cat uupd.service >/dev/null 2>&1; then
        check "update service (uupd) runs cleanly on the updated system" as_root timeout 2400 systemctl start uupd.service
        as_root journalctl -u uupd.service -b --no-pager -o cat | grep -E 'msg|update' | tail -n 15 | sed 's/^/    /'
        check "update service found no newer version"             test -z "$(as_root bootc status --json | jq -r '.status.staged.image.imageDigest // empty')"
    fi
    sleep 30
    shot "updated-login-screen"

    # Roll back the way a person would: sign in, Tamarack Center > Updates >
    # "Roll back…" > OK, and the password in polkit's dialog.
    qmp type "${password}"
    qmp key ret
    sleep 75
    shot "updated-desktop"
    in_vm() { ssh_vm "bash /tmp/in-vm-checks.sh '${password}' $*" || failures=$((failures + 1)); }
    in_vm drive-start rollback updates "$(printf '%q ' 'click:Roll back…' 'click:OK')"
    in_vm password rollback 90
    shot "rollback-password"
    qmp type "${password}"
    qmp key ret
    in_vm drive-finish rollback 600
    shot "rollback-clicked"
    check "the previous version starts at the next restart" \
        test "$(as_root bootc status --json | jq -r '.status.rollbackQueued')" = true
    reboot_vm "rollback"
    check "booted the previous version again" test "$(booted_digest)" = "${old_digest}"
    check "system finished booting after rollback" \
        as_root bash -c "'state=\$(timeout 600 systemctl is-system-running --wait); [[ \$state == running || \$state == degraded ]]'"
    check "graphical login after rollback" as_root systemctl is-active graphical.target
    check "no failed units after rollback" as_root bash -c "'[[ -z \$(systemctl --failed --no-legend --plain) ]]'"
    sleep 30
    shot "rollback-login-screen"

    echo
    echo "${failures} failure(s)"
} 2>&1 | tee "${out}/update-checks.txt"
! grep -q '^FAIL' "${out}/update-checks.txt"
