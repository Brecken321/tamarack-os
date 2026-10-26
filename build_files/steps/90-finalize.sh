#!/usr/bin/bash
# Regenerate the initramfs (it embeds os-release and the boot splash), then
# clean up build leftovers so `bootc container lint` passes.
# shellcheck source=/dev/null
source "${CTX}/lib.sh"

mapfile -t kernels < <(find /usr/lib/modules -mindepth 1 -maxdepth 1 -type d -printf '%f\n')
[[ ${#kernels[@]} -eq 1 ]] || die "expected exactly one kernel in /usr/lib/modules, found: ${kernels[*]}"
kver="${kernels[0]}"
log "regenerating initramfs for ${kver}"
/usr/bin/dracut --no-hostonly --kver "${kver}" --reproducible --zstd -v --add ostree --add fido2 \
    -f "/usr/lib/modules/${kver}/initramfs.img"
chmod 0600 "/usr/lib/modules/${kver}/initramfs.img"

# No package caches, temporary files or runtime state in the image.
dnf5 clean all
rm -rf /tmp/* /var/tmp/* || true
find /var/* -maxdepth 0 -type d \! -name cache -exec rm -rf {} \;
mkdir -p /var/tmp
chmod 1777 /var/tmp
rm -rf /boot/* /boot/.* 2>/dev/null || true
