#!/usr/bin/bash
# Build a disk image or installer ISO from a published bootc image with
# bootc-image-builder (run directly, so any config file can be passed).
#
# Usage: build-disk.sh TYPE CONFIG.toml IMAGE_REF OUTPUT_DIR
#   TYPE: qcow2 | raw | anaconda-iso
# Prints the path of the produced file on the last line of output.
set -euo pipefail

type="$1"
config="$(realpath "$2")"
ref="$3"
out="$(realpath -m "$4")"
builder="${BIB_IMAGE:-quay.io/centos-bootc/bootc-image-builder:latest}"
mkdir -p "${out}"

# Registries sometimes answer "503 The server is busy" for a while.
pull() {
    for wait in 30 90 0; do
        sudo podman pull "$1" && return 0
        ((wait)) || return 1
        echo "pull of $1 failed; trying again in ${wait} s" >&2
        sleep "${wait}"
    done
}
# bootc-image-builder reads the image from the host's (root) container storage.
pull "${ref}"
pull "${builder}"
sudo podman run --rm --privileged --pull=never \
    --security-opt label=type:unconfined_t \
    -v "${config}:/config.toml:ro" \
    -v "${out}:/output" \
    -v /var/lib/containers/storage:/var/lib/containers/storage \
    "${builder}" \
    --type "${type}" --rootfs btrfs --use-librepo=True \
    "${ref}"
sudo chown -R "$(id -u):$(id -g)" "${out}"

case "${type}" in
    anaconda-iso) result="$(find "${out}" -name '*.iso' -print -quit)" ;;
    *) result="$(find "${out}" -name "disk.${type}" -print -quit)" ;;
esac
[[ -n "${result}" ]] || { echo "no ${type} output found in ${out}" >&2; exit 1; }
ls -lh "${result}"
echo "${result}"
