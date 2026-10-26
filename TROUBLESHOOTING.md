# Troubleshooting

Start with **Tamarack Center > Home**: it lists anything that needs attention. In a terminal,
`tamarack doctor` prints the same report and `tamarack hardware` shows every device and driver.
When asking for help, include the output of `tamarack doctor` (Hardware page > *Copy report* gives a
shareable text version).

## The computer doesn't start after an update

1. Restart and open the boot menu: keep tapping **Esc** (or hold **Shift**) as the computer starts.
2. Choose the **second** Tamarack OS entry. That is the previous version, unchanged.
3. Once logged in, open Tamarack Center > Updates & Recovery > **Roll back** (or run `sudo bootc rollback`) so the
   previous version stays the default, then report the problem.

Your personal files are never part of a system update or rollback. To keep a known-good version forever, use
**Keep this version** (`sudo ostree admin pin booted`).

## Black screen or no graphics after installing (NVIDIA)

- **Secure Boot is on and the NVIDIA key is not enrolled.** Boot, switch to a text console with Ctrl+Alt+F3 if needed,
  log in and run `ujust enroll-secure-boot-key`. At the next restart a blue *MOK management* screen appears: choose
  *Enroll MOK* > *Continue* > enter the password `universalblue`.
- **Wrong edition.** `tamarack hardware` shows the GPU and driver. NVIDIA GPUs need the NVIDIA edition:
  `sudo bootc switch ghcr.io/brecken321/tamarack-os-nvidia:stable`.
- **GTX 10-series or older NVIDIA GPU.** These need NVIDIA's legacy driver, which Tamarack OS does not build yet. Use
  upstream Bazzite's `bazzite-nvidia` image for now.

## Hybrid laptops (Intel/AMD + NVIDIA): games run slowly

The desktop runs on the integrated GPU to save battery, and apps inherit it. To use the NVIDIA GPU:

- **Everything Steam launches:** Tamarack Center > Gaming > *Hybrid graphics* > turn on *Run Steam and its games on the
  discrete GPU* (or `tamarack games dgpu on`), then quit Steam fully and reopen it. This uses more battery while Steam is open.
- **One game:** in Steam, right-click the game > *Properties* > *Launch options*:
  `__NV_PRIME_RENDER_OFFLOAD=1 __VK_LAYER_NV_optimus=NVIDIA_only __GLX_VENDOR_LIBRARY_NAME=nvidia %command%`
- **Other apps:** right-click the app in the start menu > *Run using discrete graphics card* (when offered).
- **Check it worked:** add `MANGOHUD=1` to the launch options; the overlay shows the GPU in use.

ASUS laptops: performance/quiet fan profiles are under the battery icon (power profiles) and the battery charge limit is
in System Settings > Power Management, provided the firmware exposes them to Linux.

## A game won't start or crashes

1. Check it first: Tamarack Center > Gaming > *Will this game work?* (or `tamarack games check "Game"`).
   Online games whose anti-cheat blocks Linux **cannot** be fixed on the Linux side. Tamarack OS will never try to bypass
   anti-cheat (that risks a ban).
2. In Steam: right-click the game > *Properties* > *Compatibility* > *Force the use of a specific Steam Play compatibility
   tool* and try **Proton Experimental**, then the newest numbered Proton. For some games, Proton-GE (install via
   ProtonPlus from the Gaming page) works better.
3. Capture a log: set launch options to `PROTON_LOG=1 %command%`, start the game once, and the log appears as
   `~/steam-<appid>.log`. Tamarack Center shows it next to the game.
4. Look up the game on [ProtonDB](https://www.protondb.com/) for community fixes.
5. Not enough disk space and missing Vulkan are common causes: `tamarack doctor` checks both.

## Games from Epic, GOG, EA, Ubisoft, Battle.net

Install **Heroic** (Epic, GOG, Amazon) or use **Lutris** (preinstalled) from the Gaming page or app store. Bottles runs
other Windows programs. Some launchers change often; check ProtonDB/Lutris pages for the current status.

## Controller not detected

- USB: unplug and replug, then Tamarack Center > Hardware > Refresh. Controllers appear under *Controllers*.
- Bluetooth: pair it in System Settings > Bluetooth. Xbox controllers may need a firmware update from Windows/Xbox first.
- In Steam: Settings > Controller, enable support for your controller type. Steam Input remaps most controllers.

## No sound or wrong output device

Click the speaker icon in the taskbar and pick the output. HDMI/DisplayPort audio appears as a separate device.
For headsets with separate chat/game channels, choose the device in the game or Discord as well. `tamarack hardware`
lists sound cards; if none appear, report the output of `lspci -nnk` and `aplay -l`.

## Wi-Fi or Bluetooth missing

`tamarack hardware` shows whether a driver is loaded. Some adapters (notably certain Broadcom and very new Realtek chips)
lack Linux drivers or need firmware not included in Fedora; a supported USB adapter is the reliable fix. Check that
airplane mode and any hardware switch are off.

## Updates fail

- **Low disk space:** an update needs room for a second copy of changed files. Free 10 GB or more.
- **No network / registry unreachable:** try again later; GitHub Container Registry outages happen.
- **Signature errors** (`signature verification failed`) mean the downloaded image was not signed with the Tamarack key.
  Do not override this; report it.
- See history in Tamarack Center > Updates & Recovery or `journalctl -u uupd.service`.

## An app I removed came back / an app didn't install

The first-boot setup installs each default app only once and never reinstalls removed apps
(`/var/lib/tamarack/flatpak-setup.record`). If default apps are missing, check `systemctl status tamarack-flatpak-setup`
and `journalctl -u tamarack-flatpak-setup` (it retries every 5 minutes until it has internet).

## The desktop looks wrong after changing presets

Tamarack Center > Appearance > **Undo last change** restores the previous configuration
(`tamarack preset undo`), or **Reset to default** applies Clean Modern. Only appearance and layout files are touched.
Backups are in `~/.local/state/tamarack/appearance-backups/`.

## Installation problems

- **Installer doesn't boot from USB:** rewrite the USB in DD mode, try another USB port (USB 2 ports are more compatible),
  and make sure UEFI boot is enabled.
- **Installer can't see the disk:** on some laptops, set the SATA/NVMe mode from *RAID/Intel RST* to *AHCI* in the firmware
  setup. Do this only after confirming Windows has AHCI drivers (changing it can stop Windows from booting).
- **Windows missing from the boot menu:** run `ujust regenerate-grub`.

## Getting help

Open an issue at https://github.com/Brecken321/tamarack-os/issues with the `tamarack doctor` output. Problems that also
happen on upstream Bazzite are best reported to Bazzite. Please mention that you use Tamarack OS, a derivative.
