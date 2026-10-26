# Licenses and attribution

## Tamarack OS

Everything in this repository that was written for Tamarack OS (build scripts, configuration, the `tamarack` Python
package, Tamarack Center, presets, color schemes, generated artwork) is licensed under the
[Apache License 2.0](LICENSE). The wallpapers and logo are generated procedurally by `src/tamarack/art.py`; the
wallpaper packages declare CC-BY-SA-4.0 in their metadata to match KDE wallpaper conventions, and the artwork is
also available under Apache-2.0 as part of this repository.

The repository structure, Justfile recipes and CI workflow are adapted from
[ublue-os/image-template](https://github.com/ublue-os/image-template) (Apache-2.0). The Anaconda installer profile is
adapted from [Bazzite](https://github.com/ublue-os/bazzite) (Apache-2.0).

## Bundled data

| Data | Source | License |
|---|---|---|
| `data/awacy/games.json` (anti-cheat compatibility) | [AreWeAntiCheatYet](https://github.com/AreWeAntiCheatYet/AreWeAntiCheatYet), commit recorded in `data/awacy/source.json` | MIT, © 2021 Starz0r, Curve ([license](data/awacy/LICENSE)), installed as `/usr/share/licenses/tamarack/AreWeAntiCheatYet-LICENSE` |

## The operating system

A Tamarack OS image contains thousands of packages from Fedora Linux, RPM Fusion, Terra, Universal Blue and Bazzite,
each under its own license (GPL, LGPL, MIT, BSD, Apache, MPL and others). Their license texts are installed under
`/usr/share/licenses/` and package metadata (`rpm -qi <package>`) names each license. Proprietary components included
by the base image, such as Steam (Valve) and the NVIDIA driver (NVIDIA edition), are distributed under their vendors'
terms; Tamarack OS does not modify them.

Flatpak apps installed on first boot or by the user come from Flathub under their own licenses.

## Trademarks

Tamarack OS is an independent project. Bazzite, Universal Blue, Fedora, KDE, Plasma, Steam, Proton, NVIDIA, AMD, Intel,
Windows and other names are trademarks of their respective owners. Their use here is only to describe compatibility
and origin and does not imply endorsement. Tamarack OS replaces Fedora's and Bazzite's visible branding
(`os-release`, boot splash, logos, wallpapers) with its own, as derivative distributions are expected to do;
upstream tools that keep their names (for example `ujust` recipes mentioning Bazzite) remain attributed to their authors.
