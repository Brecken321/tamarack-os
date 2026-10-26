# Hardware support

Tamarack OS uses Bazzite's kernel, firmware and drivers unchanged, so hardware support matches Bazzite's (Fedora 44 base).
Nothing in Tamarack OS promises universal compatibility: devices without Linux drivers, or whose vendors only support
Windows, will not work.

## Graphics

| GPU | Edition | Driver | Notes |
|---|---|---|---|
| AMD Radeon GCN 1.2+ / RDNA 1–4 | Standard | amdgpu (Mesa RADV/radeonsi) | Best-supported option on Linux. Very old GCN 1.0/1.1 cards may use the `radeon` driver; Tamarack Center flags this. |
| Intel HD/UHD/Iris Xe, Arc | Standard | i915 / xe (Mesa ANV/iris) | Arc support depends on the kernel version shipped by Bazzite. |
| NVIDIA GTX 16xx, RTX 20/30/40/50 (Turing+) | NVIDIA | NVIDIA open kernel modules + proprietary userspace | Secure Boot: enroll Universal Blue's key (both editions need it). |
| NVIDIA GTX 9xx/10xx (Maxwell/Pascal) | — | Not built yet | Use upstream `bazzite-nvidia` (legacy driver) for now. |
| Hybrid laptops (Intel/AMD + NVIDIA) | NVIDIA | Both | Desktop on the integrated GPU; Steam can be switched to the NVIDIA GPU (Gaming page). |
| Virtual machines | Either | virtio-gpu / llvmpipe | Desktop works; games will be slow (no GPU acceleration). |

Vulkan (needed by Proton's DXVK/VKD3D) is available on every supported GPU above. DirectX 9–11 → Vulkan via DXVK and
DirectX 12 → Vulkan via VKD3D-Proton are part of Proton. HDR and VRR depend on the GPU, driver, display, cable and
compositor; Plasma 6 exposes both under System Settings > Display when supported.

## Status of physical hardware validation

| Device | Status |
|---|---|
| ASUS TUF Gaming F17 FX706LI (i5-10300H, Intel UHD + GTX 1650 Ti, 8 GB) | **Not yet tested.** Target machine for the first hardware validation pass ([TESTING.md](../TESTING.md#physical-hardware-checklist)). |
| Any other physical PC | **Not yet tested.** |

Results will be recorded here, with date and image version, as people run the checklist. Please contribute results.

## Other devices (expected support, from upstream)

| Category | Expectation | How to check |
|---|---|---|
| Wired Ethernet | Most Intel/Realtek/Killer chips work | Hardware page > Network |
| Wi-Fi | Intel and MediaTek generally excellent; Realtek mostly; some Broadcom need extra firmware | Hardware page > Network |
| Bluetooth | Most built-in and USB adapters | Hardware page > Bluetooth |
| Controllers | Xbox (USB/Bluetooth/xone dongle via Bazzite), PlayStation 4/5, Switch Pro, 8BitDo, Steam Controller | Hardware page > Controllers; Steam Input |
| Racing wheels | Logitech G-series and others with kernel drivers; force feedback varies | Hardware page > Controllers |
| Audio | PipeWire; USB DACs and audio interfaces class-compliant devices work; HDMI/DP audio | Speaker icon / Hardware page |
| Printers/scanners | CUPS + IPP Everywhere (driverless) for most network printers; SANE for scanners | System Settings > Printers |
| Webcams | UVC webcams | Hardware page > Cameras |
| Laptops | Brightness, touchpad gestures, battery, sleep (s2idle/S3 as firmware allows), lid actions, charge limit where exposed | System Settings > Power |
| USB-C docks | Displays/USB/Ethernet on most docks; DisplayLink docks need an extra driver (not included) | — |
| Fingerprint readers | Only devices supported by libfprint | — |
| RGB peripherals | OpenRGB is available from Flathub; vendor apps (iCUE, Synapse) are Windows-only | — |
| Anti-cheat kernel drivers | Not possible on Linux (e.g. Vanguard, some FACEIT/ESEA) | Gaming page checker |

## Filesystems and formats

ext4, Btrfs (default for installs), XFS, exFAT, FAT32 and NTFS (read/write via the kernel ntfs3 driver) are supported.
Archives (zip, 7z, tar, rar via p7zip in Bazzite; Ark for a GUI), PDF (Okular), common images such as JPEG, PNG and
WebP (Gwenview), audio and video (MP3, AAC, FLAC, Opus, H.264, HEVC, AV1) via the codecs Universal Blue includes and the
Flatpak runtimes. Hardware video decoding depends on the GPU and driver. These are expectations from upstream; the
image checks do not yet test every format (see [TESTING.md](../TESTING.md)).
