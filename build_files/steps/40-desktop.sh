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

# Windows shortcuts that Plasma lacks (it already has Win, Win+E, Win+D, Win+L,
# Win+V, Win+arrows and Win+Shift+S). kglobalaccel reads only the user's own
# kglobalshortcutsrc, so these are defaults for new accounts; anyone can
# change them in System Settings > Shortcuts.
skel_shortcuts=/etc/skel/.config/kglobalshortcutsrc
mkdir -p "$(dirname "${skel_shortcuts}")"
[[ -f "${skel_shortcuts}" ]] && log "extending existing ${skel_shortcuts}"
# Win+I: Settings.
kw "${skel_shortcuts}" --group services --group systemsettings.desktop --key _launch "Meta+I"
# Ctrl+Shift+Esc: the task manager (System Monitor); Plasma's Ctrl+Esc stays.
kw "${skel_shortcuts}" --group services --group org.kde.plasma-systemmonitor.desktop --key _launch $'Ctrl+Esc\tCtrl+Shift+Esc'
# Win+S: search, next to Plasma's Alt+Space.
kw "${skel_shortcuts}" --group services --group org.kde.krunner.desktop --key _launch $'Alt+Space\tAlt+F2\tSearch\tMeta+S'
# Win+Tab: the overview of windows and desktops (Task View). Plasma uses
# Win+Tab to cycle Activities, which most people never set up.
kw "${skel_shortcuts}" --group kwin --key Overview $'Meta+W\tMeta+Tab,Meta+W,Toggle Overview'
kw "${skel_shortcuts}" --group plasmashell --key "next activity" "none,Meta+Tab,Walk through activities"
kw "${skel_shortcuts}" --group plasmashell --key "previous activity" "none,Meta+Shift+Tab,Walk backwards through activities"
sed 's/^/    /' "${skel_shortcuts}"

# Steam Gaming Mode on the sign-in screen's session menu. In Steam, "Switch to
# Desktop" ends it (steamos-session-select) and returns to the sign-in screen.
sessions=/usr/share/wayland-sessions
require_file "${sessions}/gamescope-session-steam.desktop"
sed -i \
    -e 's/^Name=.*/Name=Steam Gaming Mode/' \
    -e 's/^Comment=.*/Comment=Full-screen Steam, like a console. Use Switch to Desktop in Steam to come back./' \
    "${sessions}/gamescope-session-steam.desktop"
# A second, generic entry for the same session would only confuse the menu.
rm -f "${sessions}/gamescope-session.desktop"
grep -H -E '^(Name|Exec)=' "${sessions}"/*.desktop | sed 's/^/    /'

# Quiet notifications while a game or video is fullscreen.
kw /etc/xdg/plasmanotifyrc --group DoNotDisturb --key WhenFullscreen true

# Login screen (Plasma Login Manager on Fedora 44; SDDM fallback if present).
# /etc/plasmalogin.conf is the highest-priority source: drop-ins in
# /usr/lib/plasmalogin/plasmalogin.conf.d are merged after /etc/plasmalogin.conf.d
# and would override a drop-in of ours there.
for conf in /etc/plasmalogin.conf /etc/plasmalogin.conf.d/* /usr/lib/plasmalogin/plasmalogin.conf.d/*; do
    [[ -f "${conf}" ]] && log "login manager config present: ${conf}" && sed 's/^/    /' "${conf}"
done
kw /etc/plasmalogin.conf --group Greeter --key WallpaperPluginId org.kde.image
kw /etc/plasmalogin.conf --group Greeter --group Wallpaper --group org.kde.image --group General --key Image "${wallpaper}"
kw /etc/plasmalogin.conf --group Greeter --group Wallpaper --group org.kde.image --group General \
    --key PreviewImage "${wallpaper}"
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
