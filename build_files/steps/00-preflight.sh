#!/usr/bin/bash
# Verify the base image is what every later step assumes: a Bazzite KDE
# desktop image of the right hardware flavor. Fails fast with a clear error.
# shellcheck source=/dev/null
source "${CTX}/lib.sh"
load_brand

info=/usr/share/ublue-os/image-info.json
require_file "${info}" /usr/lib/os-release /usr/bin/plasmashell /usr/bin/kwriteconfig6

upstream_name="$(jq -r '."image-name"' "${info}")"
base_name="$(jq -r '."base-image-name"' "${info}")"
log "upstream image: ${upstream_name} (base ${base_name}), building ${IMAGE_NAME} flavor=${IMAGE_FLAVOR}"

[[ "${base_name}" == "kinoite" ]] || die "expected a KDE (kinoite) Bazzite base, got base-image-name=${base_name}"
[[ "${upstream_name}" == bazzite* ]] || die "expected a Bazzite base image, got ${upstream_name}"
[[ "${upstream_name}" != *deck* ]] || die "Bazzite deck images are not a supported base"

case "${IMAGE_FLAVOR}" in
    main) [[ "${upstream_name}" != *nvidia* ]] || die "flavor 'main' must not use an NVIDIA base" ;;
    nvidia) [[ "${upstream_name}" == *nvidia-open* ]] || die "flavor 'nvidia' requires Bazzite's nvidia-open base" ;;
    nvidia-legacy)
        [[ "${upstream_name}" == *nvidia* && "${upstream_name}" != *nvidia-open* ]] ||
            die "flavor 'nvidia-legacy' requires Bazzite's proprietary-driver NVIDIA base"
        ;;
    *) die "unknown IMAGE_FLAVOR '${IMAGE_FLAVOR}'" ;;
esac

# Keep the upstream identity for diagnostics and attribution screens.
install -d /usr/share/tamarack
cp "${info}" /usr/share/tamarack/upstream-image-info.json
