# Roadmap

Status legend: ✅ done and tested in CI · 🟡 done, needs physical-hardware validation · 🔜 planned · ❌ not planned

## Milestone 1: Buildable, bootable, honest (current)

| Item | Status |
|---|---|
| Custom bootc image on Bazzite KDE, AMD/Intel + NVIDIA editions | ✅ built and checked in CI |
| Central branding (name, palette, wallpapers, logo, splash, color schemes, global themes) | ✅ |
| os-release/image-info rebrand, attribution, installer profile | ✅ |
| Privacy defaults (countme off, Firefox sponsored content & telemetry off) | ✅ image checks |
| Signed images + signature policy for updates | ✅ signing verified in CI (retries Rekor outages); ✅ update to the next build and rollback tested in a VM |
| Seven desktop presets with backup/undo, custom presets, import/export | ✅ unit tests; 🟡 VM screenshots |
| Tamarack Center (home, appearance, apps, gaming, hardware, privacy, updates, help) + Welcome, with "Find a setting" | ✅ QML self-test, every-button check, page previews, VM screenshots |
| App and game search and install from Flathub in Tamarack Center | ✅ VM test downloads and opens an app, a game and a launcher |
| Windows-style desktop: centered Start button, Windows shortcuts | ✅ VM test presses the shortcuts |
| `tamarack` CLI and `ujust tamarack-*` recipes | ✅ |
| Game compatibility center with sourced anti-cheat data, Steam library view, launch logs | ✅ |
| Hybrid-laptop option: Steam on the discrete GPU | 🟡 |
| First-boot default apps (never reinstalls removed apps) | ✅ VM test |
| VM boot test with screenshots in CI | ✅ |
| Steam first-run download to its sign-in window | ✅ VM test (game downloads through Steam need an account: real hardware) |
| Anaconda installer ISOs | ✅ built in CI; ✅ unattended install + first boot tested in a VM; 🟡 interactive installer not automated |
| Documentation set | ✅ |

## Milestone 2: Validated on real hardware

- 🔜 Run the [physical hardware checklist](TESTING.md#physical-hardware-checklist) on the ASUS TUF F17 (Intel + GTX 1650 Ti)
  and at least one AMD desktop; record results in [docs/HARDWARE.md](docs/HARDWARE.md).
- 🔜 Real game tests (a free-to-play title and a Proton title) with MangoHud frame-time captures.
- 🔜 Measure boot time, idle RAM/CPU, and compare with upstream Bazzite on the same machine.

## Milestone 3: Polish

- 🔜 Live ISO (try before installing) using Titanoboa, as Bazzite does.
- 🔜 Legacy NVIDIA edition (GTX 9xx/10xx) based on `bazzite-nvidia`.
- 🔜 Steam Gaming Mode session (Gamescope) entry on desktop editions, with a clear "return to desktop".
- 🔜 Per-game performance profiles (MangoHud/Gamescope presets) in the Gaming page.
- 🔜 Translations for Tamarack Center (strings already use `qsTr`).
- 🔜 Steam Deck Verified / ProtonDB data, only if a source with clear terms of use is available.
- 🔜 Weekly automated refresh of the anti-cheat dataset via pull request.
- 🔜 Plymouth boot splash with Tamarack colors (currently Fedora's spinner with the Tamarack watermark).

## Optional power features (prioritized)

| Feature | Plan |
|---|---|
| Clipboard history with privacy controls | Plasma's Klipper already provides it; expose its "do not store passwords"/history size in Privacy (🔜) |
| Screen capture/recording | Spectacle (built in) and OBS bundle ✅ |
| Local backup scheduler | Déjà Dup in the utilities bundle ✅; a Tamarack-native wizard is 🔜 |
| Advanced tiling | KWin custom tiles (Meta+T) built in ✅; a Krohnkite/Polonium toggle 🔜 |
| VM management / containers | Bazzite's `ujust` virtualization recipes, Distrobox, Podman ✅ upstream |
| Remote desktop | KDE KRdp (System Settings > Remote Desktop) ✅ upstream |
| Automation rules | ❌ not planned until core reliability is proven |

## Not planned

- Writing a kernel, compositor, graphics stack or Windows compatibility layer: upstream projects are better.
- Any form of anti-cheat bypass or DRM circumvention.
- Bundled trialware, sponsored apps or ads.
