# Testing

Tamarack OS is tested in four layers. Everything in layers 1–3 runs automatically in GitHub Actions; layer 4 needs
real hardware and is done by hand with the checklist below.

| Layer | What | Where | Command |
|---|---|---|---|
| 1. Static + unit | ruff, mypy `--strict`, shellcheck, `just --fmt`; 135+ pytest tests; generated JS syntax (`node --check`); desktop-file validation; QML self-test (every page compiled and instantiated against real Kirigami) | Fedora 44 container | `just lint`, `just test` |
| 2. Image content | ~75 checks run *inside* each built image: branding, themes, wallpapers, KDE defaults, privacy defaults, signature policy, services, gaming stack, NVIDIA driver presence, CLI, Tamarack Center QML load | Each image (both editions) | `just check-image main` |
| 3. VM boot | bootc-image-builder makes a qcow2; QEMU/KVM boots it (UEFI); checks over SSH; logs into Plasma via the virtual keyboard; applies presets; opens every Tamarack Center page; screenshots | GitHub-hosted runner with KVM | `tests/vm/run-vm-test.sh` |
| 4. Physical hardware | GPU drivers, real games, Wi-Fi/Bluetooth/audio, sleep, displays, controllers, install/dual-boot | A real PC | [Checklist](#physical-hardware-checklist) |

## What each automated layer proves, and what it doesn't

- **Unit tests** prove the logic: preset validation and the exact `kwriteconfig6`/Plasma-script output, WCAG contrast of
  the generated color schemes, deterministic artwork, Steam library parsing, anti-cheat verdict mapping (including that
  *Verified* is never invented), hardware parsing from real-world fixtures, privacy parsing, update-status parsing,
  preset apply/undo against a fake home directory, and that no secrets are committed.
  They do **not** prove KDE behaves as expected; that is layer 3.
- **Image checks** prove the image contains and enables what we claim. They run with no network and no hardware.
- **The VM test** proves the image boots, reaches the desktop, verifies its update signature against the registry, installs
  default apps from Flathub, and that presets and Tamarack Center work in a real Plasma session. A VM has no real GPU
  (software rendering), so it says **nothing** about game performance, NVIDIA drivers, Wi-Fi, Bluetooth, audio hardware,
  sleep or battery.
- **Installer ISOs** are built in CI, but an end-to-end install from the ISO is not yet automated.

## Results log

Newest first. "CI" entries link to the workflow run that produced them.

<!-- results:start -->

### 2026-10-27: VM boot test, second round (CI [run 40446510853](https://github.com/Brecken321/tamarack-os/actions/runs/40446510853), images 44.20261027)

| Check | Standard | NVIDIA |
|---|---|---|
| Boot to SSH / systemd "startup finished" | ✅ 16.6 s to graphical target | ✅ ~20.5 s |
| No failed units | ✅ | ❌ `nvidia-cdi-refresh` failed (no NVIDIA GPU in the VM): **fixed** with a skip-without-GPU drop-in |
| Update check verifies the image signature against the registry | ✅ | ✅ |
| `bootloader-update.service` | ✅ (fixed by keeping image labels through rechunking) | ✅ |
| Default apps, Firefox privacy prefs, firewall, countme off | ✅ | ✅ |
| Plasma session: theme, color scheme, panel layout, wallpaper, Tamarack launcher icon | ✅ | ✅ |
| Presets applied over the live session (Gaming, Classic, Minimalist, High Contrast, reset) | ✅ all 30 steps | ✅ all 30 steps |
| Tamarack Center pages render in the session (screenshots) | ✅ | ✅ |
| Login screen shows the Tamarack wallpaper | ✅ | ✅ |
| Memory in use with Plasma + Tamarack Center open (6 GB VM) | ~1.8 GB | — |

Screenshot review led to: app names instead of Flatpak ids on the Apps page, aligned shortcut list on Help.

### 2026-10-27: first VM boot test (CI [run 40435677118](https://github.com/Brecken321/tamarack-os/actions/runs/40435677118), images from 2026-10-26)

Both editions, qcow2 disk, QEMU/KVM, UEFI, 4 vCPU, 6 GB RAM, virtio-gpu (no GPU acceleration).

| Check | Standard | NVIDIA |
|---|---|---|
| Boot to SSH | ✅ 109 s | ✅ 153 s |
| Tamarack OS identity, graphical target, login manager running | ✅ | ✅ |
| First-boot default apps from Flathub (Firefox etc.), Firefox privacy prefs in place | ✅ | ✅ |
| Firewall active, countme off, Steam present, `tamarack doctor/privacy/games` work | ✅ | ✅ |
| Log in through the virtual keyboard, Plasma session, Tamarack global theme + color scheme | ✅ | ✅ |
| Desktop: Tamarack wallpaper, Clean Modern taskbar with Tamarack launcher and pins, Welcome opens (screenshots) | ✅ | ✅ |
| No failed units | ❌ `bootloader-update.service` failed (under investigation) | ❌ same |
| Update check (`bootc upgrade --check`) verifies the signature | ❌ `:stable` digest was unsigned: **fixed** (sign every pushed digest, verify every tag) | ❌ same |
| Session layout checks | ❌ used `qdbus6`, absent on Fedora 44: **fixed** (presets now use `busctl`) | ❌ same |
| Login screen wallpaper | ❌ still Bazzite's: **fixed** (`/etc/plasmalogin.conf` outranks vendor drop-ins) | ❌ same |
| Welcome hides the navigation sidebar | ❌ sidebar shown greyed out: **fixed** | ❌ same |

The image content checks added after this run also caught two dead System Settings links (`kcm_flatpak` was renamed
`kcm_app-permissions` upstream; the firewall page needed `plasma-firewall-firewalld`), both fixed.

### 2026-10-26: image builds (CI [run 40416438687](https://github.com/Brecken321/tamarack-os/actions/runs/40416438687))

Both editions built on `bazzite:stable` / `bazzite-nvidia-open:stable` (Fedora 44, kernel 7.2.11-ogc), all image content
checks passed (branding, themes, privacy defaults, signature policy, firewall on, SSH off, Steam/Gamescope/MangoHud/Lutris,
32-bit Vulkan, NVIDIA module presence/absence per edition, CLI, Tamarack Center QML load).

<!-- results:end -->

## Not tested yet

- Any physical machine (including the target ASUS TUF F17 with GTX 1650 Ti).
- Real games, Steam sign-in and downloads, controller input, frame pacing, VRR/HDR, multi-monitor.
- Installing from the ISO (Anaconda), disk encryption, dual-boot with Windows.
- Secure Boot with NVIDIA key enrollment.
- Sleep/resume, battery life, Wi-Fi, Bluetooth, printers, webcams.
- Update from one Tamarack build to the next on a real install (the VM verifies the update *check*, not a full upgrade).

## Physical hardware checklist

Run on a spare disk or after a full backup. Record the edition, image version (`tamarack doctor` first line), date and
results in [docs/HARDWARE.md](docs/HARDWARE.md) via a pull request or issue.

**Install**
- [ ] ISO boots from USB in UEFI mode (Secure Boot on, if supported by the PC).
- [ ] Installer detects disks; automatic partitioning; optional encryption passphrase works at boot.
- [ ] Dual-boot only: Windows still boots; both appear in the boot menu.
- [ ] First boot reaches the login screen; Welcome opens after login; default apps appear within ~10 minutes.

**Graphics (NVIDIA edition)**
- [ ] `ujust enroll-secure-boot-key` → MOK enrollment → after reboot `tamarack hardware` shows `driver: nvidia`.
- [ ] `nvidia-smi` works. Hybrid laptops: Hardware page shows *Hybrid graphics*.
- [ ] Hybrid: turn on *Run Steam on the discrete GPU*, restart Steam, a game shows the NVIDIA GPU in MangoHud.

**Graphics (standard edition)**
- [ ] `tamarack hardware` shows amdgpu/i915/xe and a Vulkan device (not llvmpipe).

**Gaming**
- [ ] Steam installs updates, signs in, downloads a free game (e.g. *Team Fortress 2* or *Counter-Strike 2*'s offline mode, or any owned game).
- [ ] A Windows-only game runs with Proton (Properties > Compatibility).
- [ ] `MANGOHUD=1 %command%` shows the overlay; note average FPS and 1% lows; compare with Windows if available.
- [ ] Controller works in Steam Big Picture (USB and Bluetooth).
- [ ] Gaming page: the game appears with a rating; the launch log appears after `PROTON_LOG=1 %command%`.
- [ ] Fullscreen game: no desktop notifications pop up.

**Desktop**
- [ ] Each preset applies cleanly; *Undo last change* restores the previous look; *Reset to default* works.
- [ ] Custom preset: save, export, delete, import.
- [ ] Display settings: resolution, refresh rate, scaling; multi-monitor if available; VRR/HDR toggles if supported.
- [ ] Night light, brightness keys, volume keys, keyboard backlight (laptops).
- [ ] File manager: copy a large folder to a USB drive (progress shown), open a ZIP, preview images/PDF/video.

**Hardware**
- [ ] Wi-Fi connects; Ethernet; Bluetooth headset/controller pair; speakers, headphone jack, HDMI audio, microphone.
- [ ] Webcam in a browser test page.
- [ ] Laptop: battery %, charge limit (if offered), lid close → sleep → resume works, touchpad gestures.
- [ ] Printer (if available).

**Updates and recovery**
- [ ] Updates page shows the version; *Update now* runs; after restart the new version is booted.
- [ ] *Roll back* → restart → previous version is booted; personal files unchanged.
- [ ] Boot menu: the previous entry boots.

**Performance (record numbers)**
- [ ] `systemd-analyze` boot time; idle RAM (`free -m` after login settles); idle CPU (`top`).
- [ ] Same measurements on upstream Bazzite (same machine) for comparison.
