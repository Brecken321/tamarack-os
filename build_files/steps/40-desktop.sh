#!/usr/bin/bash
# KDE Plasma defaults for new users: Tamarack global themes (light/dark by
# time of day), layout, start menu favorites, login and lock screen.
# Existing users keep their settings; nothing here edits home directories.
# shellcheck source=/dev/null
source "${CTX}/lib.sh"
load_brand

kw() { kwriteconfig6 --file "$1" "${@:2}"; }

# Global theme defaults. Plasma applies LookAndFeelPackage (or the light/dark
# pair when AutomaticLookAndFeel is on) at the first login of every user.
kw /etc/xdg/kdeglobals --group KDE --key LookAndFeelPackage "${BRAND_LNF_LIGHT}"
kw /etc/xdg/kdeglobals --group KDE --key DefaultLightLookAndFeel "${BRAND_LNF_LIGHT}"
kw /etc/xdg/kdeglobals --group KDE --key DefaultDarkLookAndFeel "${BRAND_LNF_DARK}"
kw /etc/xdg/kdeglobals --group KDE --key AutomaticLookAndFeel true
kw /etc/xdg/kdeglobals --group General --key ColorScheme "${BRAND_SHORT_NAME}Light"

# Lock screen wallpaper.
wallpaper="file:///usr/share/wallpapers/${BRAND_DEFAULT_WALLPAPER}/"
kw /etc/xdg/kscreenlockerrc --group Greeter --group Wallpaper --group org.kde.image --group General \
    --key Image "${wallpaper}"
kw /etc/xdg/kscreenlockerrc --group Greeter --group Wallpaper --group org.kde.image --group General \
    --key PreviewImage "${wallpaper}"

# Quiet notifications while a game or video is fullscreen.
kw /etc/xdg/plasmanotifyrc --group DoNotDisturb --key WhenFullscreen true

# Login screen (Plasma Login Manager on Fedora 44; SDDM fallback if present).
install -d /etc/plasmalogin.conf.d
cat >/etc/plasmalogin.conf.d/10-tamarack.conf <<EOF
[Greeter]
WallpaperPluginId=org.kde.image

[Greeter][Wallpaper][org.kde.image][General]
Image=${wallpaper}
PreviewImage=${wallpaper}
EOF
if [[ -d /usr/share/sddm/themes/breeze ]]; then
    image="/usr/share/wallpapers/${BRAND_DEFAULT_WALLPAPER}/contents/images/3840x2160.jpg"
    require_file "${image}"
    printf '[General]\nbackground=%s\n' "${image}" >/usr/share/sddm/themes/breeze/theme.conf.user
fi

# Bazzite pins its welcome app ("Bazzite Portal") through a one-time Plasma
# update script and by appending to the default panel template. Tamarack's
# layout sets its own pins, so remove the script and restore the template.
rm -f /usr/share/plasma/shells/org.kde.plasma.desktop/contents/updates/bazzite-pins.js
template=/usr/share/plasma/layout-templates/org.kde.plasma.desktop.defaultPanel/contents/layout.js
if [[ -f "${template}" ]] && grep -q 'yafti' "${template}"; then
    python3 /usr/libexec/tamarack/strip-bazzite-pins "${template}"
fi

# First-run: Tamarack Welcome replaces the Bazzite Portal autostart. The
# portal stays installed and can still be opened from the app menu.
rm -f /etc/skel/.config/autostart/bazzite-portal.desktop
# Steam autostart becomes a choice (Gaming preset / Welcome) instead of a default.
rm -f /etc/skel/.config/autostart/steam.desktop

# Fedora ships a one-time script that rewrites the start menu icon; log it so
# CI output shows whether it can override the Tamarack launcher icon.
for script in /usr/share/plasma/shells/org.kde.plasma.desktop/contents/updates/*.js; do
    log "plasma update script present: ${script}"
done

# Menu entries for Tamarack must be valid.
require_file "/usr/share/plasma/look-and-feel/${BRAND_LNF_LIGHT}/contents/layouts/org.kde.plasma.desktop-layout.js"
require_file "/usr/share/color-schemes/${BRAND_SHORT_NAME}Light.colors" "/usr/share/color-schemes/${BRAND_SHORT_NAME}Dark.colors"
