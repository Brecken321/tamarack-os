# Security

## Reporting a vulnerability

Please report security problems **privately** through GitHub's
[private vulnerability reporting](https://github.com/Brecken321/tamarack-os/security/advisories/new) for this repository.
Include affected image(s) and version (`tamarack doctor`), steps to reproduce and impact. Do not open a public issue for
an unfixed vulnerability. We aim to acknowledge reports within 7 days.

Vulnerabilities in upstream components (kernel, Mesa, KDE, Steam, Fedora packages, Bazzite tooling) should also be
reported to those projects; Tamarack picks up their fixes automatically through daily rebuilds.

## Security model

| Area | How it works |
|---|---|
| Updates | Images are built in GitHub Actions from this public repository, pushed to `ghcr.io/brecken321`, and signed with cosign. `/etc/containers/policy.json` requires a valid signature (`sigstoreSigned`, key `/etc/pki/containers/tamarack-os.pub`) for images from that namespace, so updates from an unsigned or tampered image are rejected. CI verifies each signature after signing. |
| Upstream fixes | CI rebuilds daily from `bazzite:stable`, so kernel and package security fixes reach users without Tamarack changes. |
| Rollback | The previous OS version is kept; a bad update can be undone from the boot menu. |
| System integrity | `/usr` is read-only at runtime (bootc/ostree). |
| Privileges | Tamarack Center and the CLI run as the user. Privileged actions (updates, rollback, enabling services, system Flatpak installs) go through polkit (`pkexec`/Flatpak's own authorization), one action at a time. Nothing in the desktop runs as root. |
| Network | firewalld is enabled at boot and the SSH server is not enabled by default (both verified by the image checks). The Privacy page lists every listening port. |
| Apps | Flatpak apps run sandboxed with portal-mediated access; permissions are visible and editable (Privacy page, System Settings > Application Permissions). |
| Secure Boot | Supported on both editions. Bazzite's kernel and kernel modules (including NVIDIA's) are signed with Universal Blue's key, which must be enrolled once: accept the blue *MOK* screen after installation, or run `ujust enroll-secure-boot-key` (password `universalblue`). Tamarack never asks you to disable Secure Boot. |
| Disk encryption | LUKS2 full-disk encryption is offered by the installer. |
| Secrets | No credentials are stored by Tamarack tools. The image-signing private key exists only as a GitHub Actions secret and offline with the maintainer; CI tests fail if a private key is ever committed. |

## Supply chain

- Base images: `ghcr.io/ublue-os/bazzite` / `bazzite-nvidia-open` (`stable` tag), themselves signed by Universal Blue.
- Build-stage image: `quay.io/fedora/fedora:44` (for rendering artwork only; nothing from it runs on user systems).
- GitHub Actions are pinned to commit SHAs (taken from Universal Blue's image template).
- Tamarack adds only packages from Fedora's repositories (`python3-pyside6`, `pciutils`, `usbutils`, `glx-utils`, `smartmontools`).
- Data: the AreWeAntiCheatYet dataset is vendored in `data/awacy/` with its source commit recorded.
- Flatpak apps come from Flathub; app IDs offered by Tamarack are checked to exist.

## Known limitations

- The first `bootc switch` from another image to Tamarack cannot verify Tamarack's signature, because the old system
  does not have the key yet; it relies on TLS to ghcr.io. Signature enforcement applies from the first Tamarack boot.
- Images are signed with a project key, not keyless Sigstore identities. Key rotation would require an image update that
  ships the new public key before switching signers.
- Games' anti-cheat and DRM are closed-source and run with the game's privileges.
