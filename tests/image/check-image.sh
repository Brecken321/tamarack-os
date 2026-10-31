#!/usr/bin/bash
# Single-quoted jq programs and bash -c snippets are intentional here.
# shellcheck disable=SC2016
# Content checks for a built Tamarack OS image. Runs *inside* the image:
#   podman run --rm --network=none -v ./tests/image:/tests:ro IMAGE bash /tests/check-image.sh FLAVOR
# Every check prints PASS/FAIL; the script exits non-zero if any check failed.
set -uo pipefail

flavor="${1:-main}"
failures=0

pass() { echo "PASS: $*"; }
fail() {
    echo "FAIL: $*"
    failures=$((failures + 1))
}
check() {
    # check "description" command...
    local description="$1"
    shift
    if "$@" >/tmp/check.out 2>&1; then
        pass "${description}"
    else
        fail "${description}"
        sed 's/^/    /' /tmp/check.out | tail -n 20
    fi
}
info() {
    # info "description" command...: prints the output, never fails
    echo "INFO: $1"
    "${@:2}" 2>&1 | sed 's/^/    /' | head -n 40
}

# shellcheck source=/dev/null
source /usr/share/tamarack/branding.env

# --- Identity ---------------------------------------------------------------
# shellcheck source=/dev/null
source /usr/lib/os-release
check "os-release NAME is ${BRAND_NAME}" test "${NAME}" = "${BRAND_NAME}"
check "os-release ID is ${BRAND_ID}" test "${ID}" = "${BRAND_ID}"
check "os-release ID_LIKE includes fedora" grep -q '^ID_LIKE=.*fedora' /usr/lib/os-release
check "os-release has a unique IMAGE_ID" grep -q '^IMAGE_ID=' /usr/lib/os-release
check "os-release VERSION is this build's (${VERSION})" test "${VERSION}" = "${IMAGE_VERSION}"
case "${flavor}" in
    nvidia) expected_image="${BRAND_IMAGE_NVIDIA}" ;;
    nvidia-legacy) expected_image="${BRAND_IMAGE_NVIDIA_LEGACY}" ;;
    *) expected_image="${BRAND_IMAGE_MAIN}" ;;
esac
check "image-info.json names ${expected_image}" \
    test "$(jq -r '."image-name"' /usr/share/ublue-os/image-info.json)" = "${expected_image}"
check "image-info.json keeps base-image-name kinoite" \
    test "$(jq -r '."base-image-name"' /usr/share/ublue-os/image-info.json)" = "kinoite"
check "brand.json is valid JSON" jq -e .name /usr/share/tamarack/brand.json

# --- Artwork and themes -------------------------------------------------------
for lnf in "${BRAND_LNF_LIGHT}" "${BRAND_LNF_DARK}" "${BRAND_LNF_HIGH_CONTRAST}"; do
    dir="/usr/share/plasma/look-and-feel/${lnf}"
    check "global theme ${lnf} metadata" jq -e '.KPlugin.Id' "${dir}/metadata.json"
    check "global theme ${lnf} layout script" test -s "${dir}/contents/layouts/org.kde.plasma.desktop-layout.js"
    check "global theme ${lnf} preview" test -s "${dir}/contents/previews/preview.png"
    check "global theme ${lnf} splash" test -s "${dir}/contents/splash/Splash.qml"
done
for scheme in Light Dark HighContrast; do
    check "color scheme ${BRAND_SHORT_NAME}${scheme}" test -s "/usr/share/color-schemes/${BRAND_SHORT_NAME}${scheme}.colors"
done
for wallpaper in $(jq -r '.wallpapers[]' /usr/share/tamarack/brand.json); do
    dir="/usr/share/wallpapers/${wallpaper}"
    check "wallpaper ${wallpaper} metadata" jq -e '.KPlugin.Id' "${dir}/metadata.json"
    check "wallpaper ${wallpaper} light images" test "$(find "${dir}/contents/images" -name '*.jpg' | wc -l)" -ge 5
    check "wallpaper ${wallpaper} dark images" test "$(find "${dir}/contents/images_dark" -name '*.jpg' | wc -l)" -ge 5
done
check "logo icon (256px)" test -s "/usr/share/icons/hicolor/256x256/apps/${BRAND_LOGO_ICON}.png"
check "terminal welcome banner names ${BRAND_NAME}" grep -q "^# Welcome to ${BRAND_NAME}\$" /usr/share/ublue-os/motd/template.md
check "boot splash watermark is a PNG" bash -c 'file -b /usr/share/plymouth/themes/spinner/watermark.png | grep -q PNG'
check "preset previews rendered" test "$(find /usr/share/tamarack/presets/previews -name '*.png' | wc -l)" -ge 7
check "Tamarack Center banner artwork rendered" test -s /usr/share/tamarack/art/banner-light.jpg -a -s /usr/share/tamarack/art/banner-dark.jpg
check "boot screen is the Tamarack theme" bash -c '[[ "$(plymouth-set-default-theme)" == tamarack ]]'
check "Tamarack boot screen is in the initramfs" \
    bash -c 'lsinitrd /usr/lib/modules/*/initramfs.img | grep -q "plymouth/themes/tamarack/watermark.png"'
check "SVG sources stripped from image" test ! -d /usr/share/tamarack/art/src

# --- Desktop defaults ---------------------------------------------------------
check "default global theme is ${BRAND_LNF_LIGHT}" \
    test "$(kreadconfig6 --file /etc/xdg/kdeglobals --group KDE --key LookAndFeelPackage)" = "${BRAND_LNF_LIGHT}"
check "automatic light/dark switching on by default" \
    test "$(kreadconfig6 --file /etc/xdg/kdeglobals --group KDE --key AutomaticLookAndFeel)" = "true"
check "Bazzite Portal no longer autostarts" test ! -e /etc/skel/.config/autostart/bazzite-portal.desktop
check "Steam autostart is opt-in" test ! -e /etc/skel/.config/autostart/steam.desktop
check "Tamarack Welcome autostart entry" test -s "/etc/xdg/autostart/${BRAND_REVERSE_DNS}.Welcome.desktop"
check "Bazzite pins update script removed" \
    test ! -e /usr/share/plasma/shells/org.kde.plasma.desktop/contents/updates/bazzite-pins.js
check "default panel template has no Bazzite pins" \
    bash -c '! grep -q yafti /usr/share/plasma/layout-templates/org.kde.plasma.desktop.defaultPanel/contents/layout.js'
for desktop in /usr/share/applications/"${BRAND_REVERSE_DNS}".*.desktop "/etc/xdg/autostart/${BRAND_REVERSE_DNS}.Welcome.desktop"; do
    check "valid desktop entry $(basename "${desktop}")" desktop-file-validate "${desktop}"
done
check "login screen wallpaper configured (main config wins over drop-ins)" \
    bash -c '[[ "$(kreadconfig6 --file /etc/plasmalogin.conf --group Greeter --group Wallpaper --group org.kde.image --group General --key Image)" == file:///usr/share/wallpapers/Tamarack* ]]'

# --- Privacy and security -----------------------------------------------------
check "countme timer not enabled" bash -c '! systemctl is-enabled rpm-ostree-countme.timer 2>/dev/null | grep -qx enabled'
check "Firefox privacy defaults installed" test -s /usr/share/ublue-os/firefox-config/tamarack-privacy.js
check "image signature policy for ${BRAND_REGISTRY}" \
    jq -e --arg r "${BRAND_REGISTRY}" '.transports.docker[$r][0].type == "sigstoreSigned"' /etc/containers/policy.json
check "cosign public key installed" test -s "/etc/pki/containers/${BRAND_IMAGE_MAIN}.pub"
check "sigstore attachments enabled for registry" \
    grep -q "${BRAND_REGISTRY}" "/etc/containers/registries.d/${BRAND_IMAGE_MAIN}.yaml"
check "firewalld present" bash -c 'rpm -q firewalld'
check "firewall enabled at boot" systemctl is-enabled firewalld.service
check "SSH server not enabled by default" bash -c '! systemctl is-enabled sshd.service 2>/dev/null | grep -qx enabled'
check "no private signing key shipped" bash -c '! find / -xdev -name cosign.key -print -quit 2>/dev/null | grep -q .'

# --- Services -----------------------------------------------------------------
check "tamarack-flatpak-setup.service enabled" systemctl is-enabled tamarack-flatpak-setup.service
check "flatpak base list present" test -s /usr/share/tamarack/flatpaks/base.list

# --- Gaming stack (from Bazzite) ---------------------------------------------
for cmd in steam gamescope mangohud lutris; do
    check "gaming tool available: ${cmd}" bash -c "command -v ${cmd}"
done
check "Steam Gaming Mode session on the sign-in screen" \
    grep -qx 'Name=Steam Gaming Mode' /usr/share/wayland-sessions/gamescope-session-steam.desktop
check "Gaming Mode session command available" command -v gamescope-session-plus
check "Switch to Desktop in Steam is handled" command -v steamos-session-select
check "Vulkan loader present" bash -c 'ldconfig -p | grep -q libvulkan.so.1'
check "32-bit Vulkan loader present (needed by Steam/Proton)" test -e /usr/lib/libvulkan.so.1
if [[ "${flavor}" == nvidia* ]]; then
    info "NVIDIA driver packages" bash -c 'rpm -qa | grep -iE "^(nvidia|kmod-nvidia)" | sort'
    check "NVIDIA kernel module packaged" bash -c 'find /usr/lib/modules -name "nvidia*.ko*" | grep -q .'
    check "NVIDIA userspace driver present" bash -c 'rpm -qa | grep -qiE "^nvidia-driver|^xorg-x11-drv-nvidia"'
    check "CDI refresh skips cleanly without an NVIDIA GPU" \
        bash -c 'systemctl cat nvidia-cdi-refresh.service | grep -q "0x10de"'
else
    check "no NVIDIA kernel module in main flavor" bash -c '! find /usr/lib/modules -name "nvidia.ko*" | grep -q .'
fi

# --- Tamarack tools -----------------------------------------------------------
check "tamarack CLI runs" tamarack --version
check "tamarack preset list" tamarack preset list
check "tamarack doctor works offline" tamarack doctor --json
check "anti-cheat dataset bundled" jq -e 'length > 100' /usr/share/tamarack/games/awacy-games.json
check "PySide6 + Kirigami QML available" python3 -c 'import PySide6.QtQml'
check "Tamarack Center QML loads (offscreen)" env QT_QPA_PLATFORM=offscreen tamarack-center --self-test
# Every System Settings page Tamarack Center links to must exist (no dead buttons).
mapfile -t kcms < <(grep -rhoE 'kcm_[A-Za-z0-9_-]+' /usr/lib/tamarack/python/tamarack/ui/qml | sort -u)
for kcm in "${kcms[@]}"; do
    check "System Settings module ${kcm} exists"         bash -c "find /usr/lib64/qt6/plugins -name '${kcm}.so' -print -quit | grep -q . || find /usr/share/applications /usr/share/kservices6 -name '${kcm}.desktop' -print -quit 2>/dev/null | grep -q ."
done

# --- Boot ---------------------------------------------------------------------
check "bootc install defaults to a Btrfs root" \
    bash -c 'bootc install print-configuration | grep -q btrfs'
check "exactly one kernel with an initramfs" \
    bash -c 'test "$(find /usr/lib/modules -mindepth 2 -maxdepth 2 -name initramfs.img | wc -l)" -eq 1'

echo
if [[ ${failures} -gt 0 ]]; then
    echo "${failures} check(s) failed"
    exit 1
fi
echo "All image checks passed"
