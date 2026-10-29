#!/usr/bin/bash
# Product identity: os-release, image-info.json (read by Universal Blue's
# update/rebase tools), installer profile, terminal logo.
# shellcheck source=/dev/null
source "${CTX}/lib.sh"
load_brand

fedora_version="$(rpm -E %fedora)"
build_date="$(date -u +%Y%m%d)"
version="${VERSION:-${fedora_version}.${build_date}}"
upstream_name="$(jq -r '."image-name"' /usr/share/tamarack/upstream-image-info.json)"
upstream_version="$(jq -r '."version" // "unknown"' /usr/share/tamarack/upstream-image-info.json)"

# --- os-release -----------------------------------------------------------
set_os_release NAME "${BRAND_NAME}"
set_os_release PRETTY_NAME "${BRAND_NAME}"
set_os_release ID "${BRAND_ID}"
# Tools that look for Fedora/Bazzite compatibility keep working.
set_os_release ID_LIKE "bazzite fedora"
set_os_release VARIANT_ID "${IMAGE_NAME}"
# VERSION is what apps print as the system version (bug reports, system info);
# otherwise it keeps the base image's, e.g. "44.20261026.0 (Kinoite)".
set_os_release VERSION "${version}"
set_os_release VERSION_ID "${fedora_version}"
set_os_release HOME_URL "${BRAND_HOME_URL}"
set_os_release DOCUMENTATION_URL "${BRAND_DOCUMENTATION_URL}"
set_os_release SUPPORT_URL "${BRAND_SUPPORT_URL}"
set_os_release BUG_REPORT_URL "${BRAND_BUG_REPORT_URL}"
set_os_release LOGO "${BRAND_LOGO_ICON}"
set_os_release ANSI_COLOR "${BRAND_ANSI_COLOR}"
set_os_release DEFAULT_HOSTNAME "${BRAND_DEFAULT_HOSTNAME}"
set_os_release CPE_NAME "cpe:/o:${BRAND_ID}:${BRAND_ID}:${fedora_version}"
set_os_release BUILD_ID "${version}"
set_os_release BOOTLOADER_NAME "${BRAND_NAME} ${version}"
# IMAGE_ID decides whether a hibernation image may be resumed, so it must be
# unique per build. The initramfs is regenerated in a later step.
set_os_release IMAGE_ID "${IMAGE_NAME}-${version}"
set_os_release IMAGE_VERSION "${version}"
echo "${BRAND_NAME} release ${fedora_version}" >/etc/system-release

# grub2-switch-to-blscfg derives the EFI directory from ID; the signed
# shim/grub live in EFI/fedora regardless of our ID.
if [[ -f /usr/sbin/grub2-switch-to-blscfg ]]; then
    sed -i 's/^EFIDIR=.*/EFIDIR="fedora"/' /usr/sbin/grub2-switch-to-blscfg
fi

# --- image-info.json --------------------------------------------------------
# Bazzite/Universal Blue scripts (ujust, flatpak manager, update tools) read
# this file. Keep base-image-name "kinoite" so KDE-specific helpers work.
jq -n \
    --arg name "${IMAGE_NAME}" \
    --arg vendor "${IMAGE_VENDOR}" \
    --arg ref "ostree-image-signed:docker://${BRAND_REGISTRY}/${IMAGE_NAME}" \
    --arg tag "${IMAGE_TAG}" \
    --arg fedora "${fedora_version}" \
    --arg version "${version}" \
    --arg upstream "${upstream_name}" \
    --arg upstream_version "${upstream_version}" \
    --arg base "${BASE_IMAGE}" \
    --arg sha "${GIT_SHA:-unknown}" \
    '{
        "image-name": $name,
        "image-vendor": $vendor,
        "image-ref": $ref,
        "image-tag": $tag,
        "image-branch": "stable",
        "base-image-name": "kinoite",
        "fedora-version": $fedora,
        "version": $version,
        "version-pretty": ("Tamarack " + $version),
        "upstream-image": $upstream,
        "upstream-version": $upstream_version,
        "upstream-ref": $base,
        "git-sha": $sha
    }' >/usr/share/ublue-os/image-info.json

# --- Installer profile (used by Anaconda when installing from a live ISO) -----
install -d /etc/anaconda/profile.d
sed -e "s/@ID@/${BRAND_ID}/g" /usr/share/tamarack/templates/anaconda-profile.conf \
    >"/etc/anaconda/profile.d/${BRAND_ID}.conf"

# --- Boot screen (Plymouth) ---------------------------------------------------
# Plymouth's two-step engine with the system spinner's animation and its
# password-prompt images (for encrypted disks), on Tamarack's background with
# the Tamarack logo. The initramfs, which carries the theme, is regenerated in
# 90-finalize.sh.
theme_dir=/usr/share/plymouth/themes/tamarack
spinner_dir=/usr/share/plymouth/themes/spinner
require_file "${theme_dir}/watermark.png" "${spinner_dir}/spinner.plymouth"
for image in "${spinner_dir}"/*.png; do
    [[ "$(basename "${image}")" == watermark.png ]] || cp "${image}" "${theme_dir}/"
done
python3 - "${spinner_dir}/spinner.plymouth" "${theme_dir}/tamarack.plymouth" "${BRAND_NAME}" \
    "$(jq -r .palette.dark_view /usr/share/tamarack/brand.json)" \
    "$(jq -r .palette.accent /usr/share/tamarack/brand.json)" <<'EOF'
import configparser
import sys

source, target, name, background, accent = sys.argv[1:]
theme = configparser.ConfigParser(interpolation=None)
theme.optionxform = str  # keys are case-sensitive
theme.read(source)
for section in ("Plymouth Theme", "two-step"):
    if section not in theme:
        theme[section] = {}
theme["Plymouth Theme"].update(Name=name, Description=f"{name} boot screen", ModuleName="two-step")
color = lambda value: "0x" + value.lstrip("#").lower()  # noqa: E731
theme["two-step"].update(
    ImageDir="/usr/share/plymouth/themes/tamarack",
    UseFirmwareBackground="false",
    BackgroundStartColor=color(background),
    BackgroundEndColor=color(background),
    ProgressBarForegroundColor=color(accent),
    WatermarkHorizontalAlignment=".5",
    WatermarkVerticalAlignment=".42",
    HorizontalAlignment=".5",
    VerticalAlignment=".75",
)
with open(target, "w", encoding="utf-8") as fh:
    theme.write(fh, space_around_delimiters=False)
EOF
sed 's/^/    /' "${theme_dir}/tamarack.plymouth"
plymouth-set-default-theme tamarack
log "boot screen: $(plymouth-set-default-theme)"

# --- Terminal fetch logo ------------------------------------------------------
fastfetch_cfg=/usr/share/ublue-os/bazzite/fastfetch.jsonc
if [[ -f "${fastfetch_cfg}" ]]; then
    # Tamarack logo in green ($1) with an amber top ($2).
    sed -i \
        -e 's|"source": *"/usr/share/ublue-os/bazzite/logo.txt"|"source": "/usr/share/tamarack/logo.txt"|' \
        -e 's|"1": *"[0-9;]*"|"1": "32"|' \
        -e 's|"2": *"[0-9;]*"|"2": "33"|' \
        "${fastfetch_cfg}"
    grep -q '/usr/share/tamarack/logo.txt' "${fastfetch_cfg}" ||
        log "warning: fastfetch config layout changed upstream; terminal logo not rebranded"
fi

log "branded as ${BRAND_NAME} ${version} (${IMAGE_NAME}, upstream ${upstream_name} ${upstream_version})"
