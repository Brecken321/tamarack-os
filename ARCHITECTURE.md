# Architecture

## Decision: a custom bootc image on Bazzite (KDE)

Tamarack OS is an OCI container image that boots (a [bootc](https://bootc-dev.github.io/) image),
built `FROM ghcr.io/ublue-os/bazzite` with the official
[Universal Blue image template](https://github.com/ublue-os/image-template) workflow.

### Options considered

| Base | Gaming stack | Updates & rollback | Hardware/drivers | Effort to maintain | Verdict |
|---|---|---|---|---|---|
| **Bazzite KDE (bootc)** | Steam, Proton, Gamescope, MangoHud, Lutris, umu and 32-bit Vulkan already integrated and used by a large community | Atomic image updates, previous version always kept, boot-menu rollback | Bazzite's own kernel builds; NVIDIA open-module variant with signed kernel modules; firmware | Low: we inherit upstream fixes daily and only maintain our layer | **Chosen** |
| Fedora KDE (Kinoite / fedora-bootc) | Must add RPM Fusion, Steam, Gamescope, NVIDIA akmods, codecs ourselves | Same atomic model | Fedora kernel; NVIDIA needs our own signed kmod pipeline | High: we would re-implement most of Bazzite | Rejected for now |
| Fedora KDE (traditional dnf) | As above | No image rollback; dnf history only | As above | Medium; mutable systems drift | Rejected (weaker recovery story) |
| Ubuntu/Kubuntu, Arch/CachyOS | Good | Snapshot tools exist but are not the default model | Good | Our own image tooling would be needed | Rejected (no maintained bootc pipeline) |

Bazzite's own documentation recommends custom images via the image template, which keeps a clean path
for upstream security fixes: every Tamarack build re-pulls `bazzite:stable` (CI rebuilds daily).

### Trade-offs we accept

- **Bazzite's choices come with it.** Kernel, Mesa, Steam packaging and their release cadence are upstream's.
  Tamarack layers changes on top and never modifies the kernel.
- **Image-based OS.** System packages are not installed with `dnf` on the running system. Apps come from
  Flatpak (Flathub); command-line/dev tools from Distrobox/Homebrew (both preinstalled by Bazzite).
  `rpm-ostree install` layering is possible but discouraged, as upstream also advises.
- **Two hardware variants** instead of one: `tamarack-os` (AMD/Intel, Mesa) and `tamarack-os-nvidia`
  (NVIDIA open kernel modules; GTX 16-series/RTX, i.e. Turing and newer). Older NVIDIA GPUs
  (GTX 9xx/10xx) are not covered yet (see [ROADMAP.md](ROADMAP.md)).

## Layers

```
┌───────────────────────────────────────────────────────────────┐
│ Tamarack layer (this repository)                              │
│  branding · KDE defaults & presets · Tamarack Center · CLI    │
│  privacy defaults · first-boot apps · signing policy          │
├───────────────────────────────────────────────────────────────┤
│ Bazzite: gaming kernel, Steam/Proton/Gamescope/MangoHud,      │
│  NVIDIA kmods, ujust recipes, uupd updater, Bazaar app store  │
├───────────────────────────────────────────────────────────────┤
│ Universal Blue main: codecs, hardware support, signing        │
├───────────────────────────────────────────────────────────────┤
│ Fedora Atomic KDE (Kinoite) 44 · KDE Plasma 6 · bootc/ostree  │
└───────────────────────────────────────────────────────────────┘
```

## Build pipeline

```
branding/brand.toml ─┐
branding/presets/*.toml ─┤  Stage 1 (fedora:44): python3 -m tamarack_branding
src/tamarack/art.py ─┘   → wallpapers (JPEG, 6 sizes × light/dark), logo PNGs,
                           Plymouth watermark, color schemes, global themes,
                           layout scripts, desktop entries, brand.json
Stage 2 (scratch): build context = build_files + system_files + src + data + cosign.pub
Stage 3 (FROM bazzite[-nvidia-open]:stable): build_files/steps/NN-*.sh
   00 preflight   verify the base (Bazzite, KDE, right GPU flavor)
   10 files       install generated + static files, Python package, datasets
   20 branding    os-release, image-info.json, installer profile, terminal logo
   30 packages    PySide6 (Center UI) + diagnostics tools; nothing else
   40 desktop     KDE defaults, login/lock screen, remove Bazzite portal autostart
   50 privacy     countme off, Firefox ad/telemetry defaults
   60 services    first-boot app service, image signature policy
   90 finalize    regenerate initramfs, clean /var and caches
   bootc container lint
```

CI (`.github/workflows/build.yml`): lint + unit tests + QML self-test → build both variants →
run `tests/image/check-image.sh` inside each image → rechunk (smaller update downloads) → push to
GHCR → sign with cosign → verify the signature. Pull requests build and test but never publish.

Disk images (`.github/workflows/build-disk.yml`): after each published build, bootc-image-builder
creates a qcow2 for each variant with a throwaway test user, QEMU/KVM boots it, and
`tests/vm/` checks the running system over SSH, logs into Plasma through the virtual keyboard,
applies presets, opens Tamarack Center and takes screenshots. Installer ISOs (Anaconda,
`disk_config/iso-*.toml`) are built after the VM test passes.

## Runtime components

| Component | Location | Purpose |
|---|---|---|
| `tamarack` CLI | `/usr/bin/tamarack` → `src/tamarack/cli.py` | doctor, hardware, privacy, presets, games, updates, apps |
| Tamarack Center | `/usr/bin/tamarack-center` → `src/tamarack/ui/` | Kirigami (Qt Quick) GUI over the same modules; first-run Welcome |
| Global themes | `/usr/share/plasma/look-and-feel/io.github.brecken321.tamarack.{light,dark,highcontrast}.desktop` | Plasma-native themes incl. default panel layout and splash |
| Presets | `/usr/share/tamarack/presets/*.toml` | Desktop setups applied with Plasma scripting + kwriteconfig6 |
| First-boot apps | `tamarack-flatpak-setup.service` | Installs Firefox and basic viewers once; never reinstalls removed apps |
| Privacy catalog | `/usr/share/tamarack/privacy/catalog.toml` | What uses the network and why; service explanations |
| Anti-cheat data | `/usr/share/tamarack/games/awacy-games.json` | AreWeAntiCheatYet snapshot (MIT) with source/commit metadata |
| ujust recipes | `/usr/share/ublue-os/just/60-custom.just` | `ujust tamarack-*` shortcuts |
| Signature policy | `/etc/containers/policy.json`, `/etc/pki/containers/tamarack-os.pub` | Updates must be signed with the project key |

### Design rules for Tamarack code

- One injectable command runner (`tamarack.system.Runner`); no shell strings, explicit timeouts,
  structured JSON logging. Tests use `FakeRunner`; nothing in the test suite touches the host.
- Pure parsers for every external format (lspci, vulkaninfo, VDF, rpm-ostree JSON, ss, flatpak
  metadata) with fixture-based tests.
- The UI never blocks: slow work runs on a thread pool and results return through queued signals.
- Privileged actions go through polkit (`pkexec`) one at a time; no part of the desktop runs as root.
- Presets only touch appearance/layout files and are backed up first; undo restores them.
- Every claim shown to users (compatibility verdicts, privacy statements) comes from data with a
  named source, or is explicitly marked as unknown.

## Customization surface

Tamarack does not duplicate KDE System Settings. Presets are a fast way to change many real settings
at once; individual settings stay in System Settings (the Appearance page links to each module).
Advanced users can edit configuration files as on any KDE system.

## Update and recovery model

- `uupd.timer` (from Bazzite) downloads OS, Flatpak and Distrobox updates in the background.
  The OS update is staged and takes effect at the next restart; nothing restarts automatically.
- The previous deployment is kept; the boot menu and `bootc rollback` switch back to it.
  Users can pin a known-good deployment (`ostree admin pin`).
- `/etc` changes are merged three-way across updates; `/home` and `/var` are never replaced.
- Images are signed; the policy rejects unsigned images from our registry namespace.
