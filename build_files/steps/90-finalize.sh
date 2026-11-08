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

# Since Fedora 45, Fedora's repository files live in /usr/share/dnf5/repos.d.
# bootc-image-builder (installer ISOs) and rpm-ostree read only
# /etc/yum.repos.d, and found no packages at all. Copy Fedora's own files
# there; dnf5 uses the /etc file in place of the one with the same name.
# Bazzite's extra repositories (terra) are left out: the builder reads the
# files as they are and would ignore that Bazzite turned them off.
for repo in /usr/share/dnf5/repos.d/fedora*.repo; do
    [[ -e "${repo}" ]] || continue
    cp -n "${repo}" /etc/yum.repos.d/
    log "repository file in /etc/yum.repos.d: $(basename "${repo}")"
done

# No package caches, temporary files or runtime state in the image.
dnf5 clean all
rm -rf /tmp/* /var/tmp/* || true
find /var/* -maxdepth 0 -type d \! -name cache -exec rm -rf {} \;
mkdir -p /var/tmp
chmod 1777 /var/tmp
find /boot -mindepth 1 -maxdepth 1 -exec rm -rf {} +
