# Installing Tamarack OS

> Tamarack OS is in early development and has not yet been validated on physical hardware
> (see [TESTING.md](../TESTING.md)). Installing an operating system can erase data. **Back up everything
> you care about to another drive or cloud storage before you start.**

## Check your PC first (Windows)

The readiness check tells you which edition your PC needs and what to take care of before installing: free space,
Secure Boot, BitLocker, Fast Startup. It only reads; it changes nothing and sends nothing anywhere.

1. Save [check-ready.ps1](https://github.com/Brecken321/tamarack-os/raw/main/tools/windows/check-ready.ps1)
   (right-click > *Save link as*) to your Downloads folder.
2. Open PowerShell in that folder (in File Explorer: *File* > *Open Windows PowerShell*, or type `powershell` in the
   address bar) and run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\check-ready.ps1
   ```

## 1. Choose an edition

| Your graphics | Edition | Image |
|---|---|---|
| AMD Radeon, Intel (integrated or Arc) | Standard | `ghcr.io/brecken321/tamarack-os:stable` |
| NVIDIA GTX 16-series, RTX 20/30/40/50 (Turing or newer), including laptops with Intel/AMD + NVIDIA | NVIDIA | `ghcr.io/brecken321/tamarack-os-nvidia:stable` |
| NVIDIA GTX 900 or 1000 series (Maxwell, Pascal) | NVIDIA (older cards) | `ghcr.io/brecken321/tamarack-os-nvidia-legacy:stable` |

Not sure? On Windows, open Device Manager > Display adapters. A laptop that lists both Intel/AMD and NVIDIA
needs the NVIDIA edition.

## 2. Requirements

- 64-bit x86 PC with UEFI firmware (BIOS/legacy boot is not tested)
- 4 GB RAM minimum, 16 GB recommended for modern games
- 64 GB disk minimum, 256 GB+ recommended (games are large); an SSD is strongly recommended
- An 8 GB or larger USB stick for the installer
- Internet during first boot (default apps install from Flathub)

## 3. Get the installer

1. Open the latest successful [Disk images and VM test](https://github.com/Brecken321/tamarack-os/actions/workflows/build-disk.yml)
   run and download the `tamarack-os-iso` or `tamarack-os-nvidia-iso` artifact (about 6–6.5 GB; you need that much free space
   on the PC you download to). You must be signed in to GitHub to download workflow artifacts.
2. Verify the download. In a terminal on Linux/macOS: `sha256sum -c tamarack-os-*.iso.sha256`. On Windows PowerShell:
   `Get-FileHash .\tamarack-os-*.iso -Algorithm SHA256` and compare with the `.sha256` file.
3. Write it to a USB stick with [Fedora Media Writer](https://flathub.org/apps/org.fedoraproject.MediaWriter),
   balenaEtcher, or Rufus (choose **DD image** mode). This erases the USB stick.

## Optional: try it first with the live USB

The live USB starts Tamarack OS straight from the stick, signed in to the desktop, without touching your disks. Use it
to check that the screen, Wi-Fi, sound, keyboard and touchpad work before you install. Everything you do in it lives in
memory and is gone when you shut down.

1. From the same [Disk images and VM test](https://github.com/Brecken321/tamarack-os/actions/workflows/build-disk.yml)
   run, download `tamarack-os-live-iso` or `tamarack-os-nvidia-live-iso` (the NVIDIA one for any PC with an NVIDIA
   card, including Intel + NVIDIA laptops). Verify it and write it to a USB stick as in step 3. It is a different stick
   from the installer, or the same stick rewritten later.
2. **Turn Secure Boot off for now.** The live USB runs Tamarack's own kernel and NVIDIA driver (so you can test the
   real driver), and your PC does not trust their signing key until you install and enroll it. On ASUS laptops: press
   F2 at power-on, F7 for *Advanced Mode*, *Security* > *Secure Boot* > *Secure Boot Control*: **Disabled**, then F10
   to save.
   - **If Windows uses BitLocker or Device Encryption** (common on Windows 11 laptops), changing Secure Boot makes
     Windows ask for the recovery key at its next start. Write the key down first: it is at
     [account.microsoft.com/devices/recoverykey](https://account.microsoft.com/devices/recoverykey), or in Windows run
     `manage-bde -protectors -get C:` as administrator.
3. Boot from the stick (ASUS: Esc or F8 at power-on) and choose **Try Tamarack OS**. If the screen stays black, restart
   and choose **Try Tamarack OS (basic graphics)**.
4. When you are done, shut down, remove the stick, and turn Secure Boot back on if you are not installing yet (some
   games' anti-cheat on Windows requires it).

Good to know: apps and games you install in the live session download into memory, so keep to small ones on a PC with
8 GB of RAM. Updates are off in the live session, and it cannot install Tamarack OS; use the installer for that.

## 4. Before you install

- **Secure Boot** can stay on. Bazzite's kernel and drivers (both editions) are signed with Universal Blue's key, which
  you enroll once: when a blue *MOK management* screen appears after the installer, choose *Enroll MOK* > *Continue* and
  enter the password `universalblue`. If you missed it, run `ujust enroll-secure-boot-key` and restart.
- **BitLocker (Windows)**: if you will dual-boot, suspend BitLocker or have your recovery key ready; firmware boot-order
  changes can trigger a recovery prompt.
- **Fast Startup (Windows)**: turn it off (Control Panel > Power Options > Choose what the power buttons do) so Windows
  fully shuts down and its disks are safe to read from Linux.
- **Laptops**: plug in the charger.

## 5. Install

1. Boot from the USB stick (often F12, F8, Esc or F2 at power-on; ASUS laptops: Esc or F8).
2. The Anaconda installer starts. Choose language and keyboard, then **Installation Destination**:
   - **Whole disk (erases it):** select the disk, choose *Automatic*, and tick *Free up space by removing or shrinking
     existing partitions* only if you are sure.
   - **Dual-boot with Windows:** see below.
   - **Encryption:** tick *Encrypt my data* to protect the disk with a passphrase (LUKS2). You will type it at every boot.
3. Create your user account (tick *Make this user administrator*) and set a password.
4. Review the summary and start the installation. When it finishes, remove the USB stick and restart.

On first login, **Welcome to Tamarack OS** opens: pick a look, review privacy switches, choose optional apps and set up
gaming. Default apps (Firefox and basic viewers) install in the background over the next few minutes.

## Dual-booting with Windows

Dual-boot is possible but **never risk-free**. A mistake in partitioning can destroy Windows or your files.

1. In Windows, open *Disk Management*, right-click the Windows (C:) partition > *Shrink Volume* and free at least 128 GB.
   Leave the space **unallocated**. Do not delete the EFI System Partition or Recovery partitions.
2. In the installer, select the same disk, choose *Custom* (or *Automatic* with "use free space"), and install only into
   the unallocated space. Do **not** reformat the existing EFI partition; Anaconda adds its own boot entry to it.
3. After installation, the boot menu (GRUB) should list Tamarack OS and Windows Boot Manager. If Windows is missing,
   run `ujust regenerate-grub` (a Bazzite recipe) once. If the PC boots straight to Windows, choose Tamarack OS in the
   firmware boot menu or move it up in the firmware boot order.

Installing on a separate physical disk is the safest dual-boot option: Windows' disk is never touched.

## Switching from Bazzite or another Universal Blue image

```bash
sudo bootc switch ghcr.io/brecken321/tamarack-os-nvidia:stable   # or tamarack-os
systemctl reboot
```

Your files, Flatpak apps and settings are kept. To go back: `sudo bootc rollback` (before the next update), or
`sudo bootc switch ghcr.io/ublue-os/bazzite-nvidia-open:stable`.

## Switching editions later

AMD/Intel → NVIDIA (e.g. after installing an NVIDIA card):

```bash
sudo bootc switch ghcr.io/brecken321/tamarack-os-nvidia:stable
```

## Uninstalling

Tamarack OS does not modify other operating systems. To remove it, delete its partitions from Windows Disk Management
(or reinstall another OS over them) and remove the "Fedora"/"Tamarack OS" boot entry with your firmware setup or
`bcdedit`/EasyUEFI on Windows.
