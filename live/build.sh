#!/usr/bin/bash
# Turn a Tamarack OS image into a live system: boot from USB, sign in to the
# desktop automatically, try everything, install nothing. Runs inside
# `podman build` (see Containerfile); Titanoboa then packs the result into an
# ISO following the container-native ISO contract (iso.yaml, kernel and
# initramfs in /usr/lib/modules, EFI files in /boot/efi).
#
# The kernel stays the image's own, so the NVIDIA driver works in the live
# session. That kernel is signed with Universal Blue's key, which a computer
# does not trust before installing, so the live USB starts with Secure Boot
# turned off (docs/INSTALL.md).
set -euo pipefail

label="Tamarack-Live"
log() { echo "[tamarack-live] $*"; }

kernel="$(find /usr/lib/modules -mindepth 1 -maxdepth 1 -type d -printf '%f\n')"
[[ "$(wc -l <<<"${kernel}")" -eq 1 ]] || { echo "expected one kernel, found: ${kernel}" >&2; exit 1; }

# Live boot support, the live user with automatic sign-in, and the CD boot
# loader for UEFI.
dnf5 -y install --setopt=install_weak_deps=False dracut-live livesys-scripts grub2-efi-x64-cdboot

log "initramfs with live boot support for ${kernel}"
DRACUT_NO_XATTR=1 dracut --force --zstd --reproducible --no-hostonly \
    --add "dmsquash-live dmsquash-live-autooverlay" \
    "/usr/lib/modules/${kernel}/initramfs.img" "${kernel}"

sed -i 's/^livesys_session=.*/livesys_session=kde/' /etc/sysconfig/livesys
systemctl enable livesys.service livesys-late.service
# Sign in to the desktop automatically as livesys's "liveuser".
printf '\n[Autologin]\nUser=liveuser\nSession=plasma.desktop\n' >>/etc/plasmalogin.conf

# The default apps (Firefox and the viewers) ship inside the live image, so a
# live session does not download them into memory at every start.
mkdir -p "$(realpath /root)"
mount -o remount,rw /proc/sys # bubblewrap writes max_user_namespaces
flatpak remote-add --system --if-not-exists flathub /etc/flatpak/remotes.d/flathub.flatpakrepo
grep -vE '^[[:space:]]*(#|$)' /usr/share/tamarack/flatpaks/base.list |
    xargs flatpak install --system --noninteractive flathub
flatpak update --system --appstream --noninteractive flathub

# Nothing in a live session updates, installs to disk or changes the boot
# setup: updates, update checks, boot health checks and hardware setup (which
# writes kernel arguments) are off. Same list as Bazzite's live media.
for unit in uupd.timer rpm-ostreed-automatic.timer rpm-ostree-countme.service \
    bootloader-update.service greenboot-set-rollback-trigger.service greenboot-healthcheck.service \
    bazzite-hardware-setup.service ublue-hardware-setup.service ublue-system-setup.service \
    bazzite-flatpak-manager.service ublue-flatpak-manager.service flatpak-add-fedora-repos.service \
    brew-setup.service brew-update.timer brew-upgrade.timer ublue-guest-user.service check-sb-key.service; do
    if systemctl list-unit-files "${unit}" >/dev/null 2>&1; then
        systemctl disable "${unit}" && log "off in the live session: ${unit}"
    fi
done
# grub-boot-success marks a successful boot in GRUB's environment block, which
# a live USB does not have.
for unit in podman-auto-update.timer bazzite-user-setup.service ublue-user-setup.service grub-boot-success.timer; do
    if systemctl --global list-unit-files "${unit}" >/dev/null 2>&1; then
        systemctl --global disable "${unit}" && log "off in the live session: ${unit} (user)"
    fi
done
rm -f /etc/profile.d/verify_motd.sh

# The live root file system keeps changes in memory under /run, which is
# small. Apps installed while trying it out unpack in /var/tmp: give it room.
rm -rf /var/tmp
mkdir /var/tmp
cat >/etc/systemd/system/var-tmp.mount <<'EOF'
[Unit]
Description=Larger temporary space for the live session

[Mount]
What=tmpfs
Where=/var/tmp
Type=tmpfs
Options=size=50%%,nr_inodes=1m

[Install]
WantedBy=local-fs.target
EOF
systemctl enable var-tmp.mount
rm -f /etc/localtime
systemd-firstboot --timezone UTC

# UEFI boot files where Titanoboa expects them (shim, GRUB and the CD GRUB).
mkdir -p /boot/efi
cp -a /usr/lib/efi/*/*/EFI /boot/efi/
# Booted from removable media, shim would start its fallback tool (which
# writes boot entries) instead of GRUB. As on Bazzite's live media.
vendor="$(find /boot/efi/EFI -mindepth 1 -maxdepth 1 -type d ! -name BOOT -printf '%f\n' | head -n 1)"
cp "/boot/efi/EFI/${vendor}/grubx64.efi" /boot/efi/EFI/BOOT/fbx64.efi
find /boot/efi -name '*.efi' | sort
[[ -n "$(find /boot/efi -name 'gcdx64.efi' -print -quit)" ]] || { echo "no CD boot loader (gcdx64.efi)" >&2; exit 1; }

# Boot menu. The image's own kernel arguments (e.g. the NVIDIA driver's) come
# from bootc's kargs.d, which only installed systems apply, so copy them here.
kargs="$(python3 - <<'EOF'
import pathlib, tomllib
args = []
for path in sorted(pathlib.Path("/usr/lib/bootc/kargs.d").glob("*.toml")):
    data = tomllib.loads(path.read_text())
    arches = data.get("match-architectures")
    if arches and "x86_64" not in arches:
        continue
    args += [a for a in data.get("kargs", []) if a not in args]
print(" ".join(args))
EOF
)"
log "kernel arguments from the image: ${kargs:-none}"
base="quiet rhgb root=live:CDLABEL=${label} rd.live.image enforcing=0 ${kargs}"
mkdir -p /usr/lib/bootc-image-builder
cat >/usr/lib/bootc-image-builder/iso.yaml <<EOF
label: "${label}"
grub2:
  default: 0
  timeout: 5
  entries:
    - name: "Try Tamarack OS"
      linux: "/images/pxeboot/vmlinuz ${base}"
      initrd: "/images/pxeboot/initrd.img"
    - name: "Try Tamarack OS (basic graphics)"
      linux: "/images/pxeboot/vmlinuz ${base} nomodeset"
      initrd: "/images/pxeboot/initrd.img"
EOF
sed 's/^/    /' /usr/lib/bootc-image-builder/iso.yaml

dnf5 clean all
rm -rf /var/tmp/* /tmp/* || true
