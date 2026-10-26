#!/usr/bin/bash
# Privacy defaults. Optional data collection is off unless the user opts in
# (Tamarack Center > Privacy). Network use that keeps the system working
# (updates, time sync, app downloads) is untouched; see docs/PRIVACY.md.
# shellcheck source=/dev/null
source "${CTX}/lib.sh"

# Fedora "countme": an anonymous weekly ping to Fedora mirrors used to count
# installs. It carries no unique ID, but it is optional, so it starts off.
if systemctl list-unit-files rpm-ostree-countme.timer 2>/dev/null | grep -q rpm-ostree-countme.timer; then
    systemctl disable rpm-ostree-countme.timer
    # Static enablement shipped in /usr is not undone by `disable`.
    find /usr/lib/systemd/system -path '*.wants/rpm-ostree-countme.timer' -delete
    log "disabled rpm-ostree-countme.timer (opt-in via Tamarack Center)"
fi
if [[ -f /etc/dnf/dnf.conf ]] && ! grep -q '^countme=' /etc/dnf/dnf.conf; then
    echo 'countme=False' >>/etc/dnf/dnf.conf
fi

# Crash reporting: Fedora Atomic KDE does not ship ABRT, but if a base image
# ever adds it, do not let it run (and upload) without consent.
for unit in abrtd.service abrt-journal-core.service abrt-oops.service; do
    if systemctl list-unit-files "${unit}" 2>/dev/null | grep -q "${unit}"; then
        systemctl disable "${unit}"
        log "disabled ${unit}"
    fi
done

# Firefox (installed as a Flatpak on first boot): no sponsored content or
# telemetry by default. These are default prefs, not locked: users can turn
# anything back on in Firefox settings. Bazzite's flatpak manager copies this
# directory into Firefox's system config extension.
require_file /usr/share/ublue-os/firefox-config
cp /usr/share/tamarack/firefox/tamarack-privacy.js /usr/share/ublue-os/firefox-config/

# Location lookups in the installer are off (also set in the Anaconda profile).
log "privacy defaults applied"
