# Privacy

Tamarack OS contains **no advertising, no advertising identifier and no Tamarack telemetry**: Tamarack itself collects
nothing. Some parts of the system need the internet to work, and some optional features of upstream software can send
data. This page lists all of them we know of; the same list is shown in Tamarack Center > Privacy
(source: [`system_files/usr/share/tamarack/privacy/catalog.toml`](../system_files/usr/share/tamarack/privacy/catalog.toml)).

We do not claim the system sends *no* data: system updates, app downloads and time synchronization necessarily contact
servers, which see your IP address.

## What connects to the internet

| What | Who | What is sent / why | Default | How to control |
|---|---|---|---|---|
| OS updates | GitHub Container Registry (ghcr.io) | Downloads new OS images; GitHub sees your IP and which image | On (background, applied at restart) | Tamarack Center > Updates |
| App downloads/updates | Flathub | Downloads apps; Flathub counts downloads per app (no account) | When installing/updating | — |
| Fedora install counting ("countme") | Fedora mirrors | Weekly request with OS version and an age bucket; no unique ID | **Off** | Tamarack Center > Privacy |
| Connectivity check | fedoraproject.org | Periodic fetch of a static file to detect Wi-Fi login pages | On | Tamarack Center > Privacy |
| Time sync | NTP pool servers | Time requests (needed for HTTPS) | On | Not recommended to disable |
| Firmware updates | fwupd.org (LVFS) | Downloads firmware metadata | When checking | System Settings / `fwupdmgr` |
| App store | Flathub API | Catalog download; launcher search uses the local catalog | When the store runs | Privacy > store results in search |
| Steam | Valve | Only when you use Steam (sign-in, downloads, optional hardware survey that asks first) | Off until you open Steam | Steam settings |
| Firefox | Mozilla | Safe Browsing, updates of add-ons/certificates. **Sponsored content, telemetry, studies and recommendations are off by default** | See left | Firefox settings |

## Defaults Tamarack changes

- `rpm-ostree-countme.timer` disabled; `countme=False` in `/etc/dnf/dnf.conf`.
- ABRT crash reporting disabled if a base image ever includes it (Fedora Atomic KDE does not ship it).
- Firefox default preferences (`/usr/share/tamarack/firefox/tamarack-privacy.js`, copied into Firefox's system
  configuration): no sponsored top sites or stories, no sponsored address-bar suggestions, no extension/feature
  recommendations, telemetry/health report/studies/Normandy off, private attribution off. These are defaults, not
  locks: change them in Firefox.
- The installer's geolocation lookup is disabled in Tamarack's Anaconda profile.
- KDE's own user-feedback telemetry is opt-in upstream (off by default); Tamarack leaves it off.

## What you can see in Tamarack Center > Privacy

- Optional data sharing switches (countme, connectivity check, store results in search, recent-files history).
- For every Flatpak app: camera, microphone/audio, location, internet and file access. System apps that ship with the OS
  are not sandboxed and can access what your account can.
- Apps that start automatically (system-wide and yours), with a link to manage them.
- Programs listening for network connections from other devices.
- Enabled background services, explained where known.
- This network list.

## Notifications from the system

Tamarack OS sends no promotional notifications. Two kinds of system notices exist:

- **Change notices inherited from Bazzite** ("Bazzite Announcements" in the startup list): short messages stored in
  the image (`/usr/share/ublue-os/announcements/`), shown only when a change affects something you use (for example
  a tool moving out of the base image). They are never downloaded, can be dismissed for good with "Don't show me
  this again", and can be turned off in System Settings > Autostart.
- **Tamarack Welcome** opens once, at your first login.

## Accounts

No online account is needed to install or use Tamarack OS. Steam, Discord and similar apps need their own accounts only
when you choose to use them; Tamarack never sees or stores those credentials.
