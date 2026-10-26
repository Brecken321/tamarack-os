# Release, signing and upgrade process

## Channels and tags

Each image (`tamarack-os`, `tamarack-os-nvidia`) is published to `ghcr.io/brecken321/` with these tags on every
successful build of `main`:

| Tag | Meaning |
|---|---|
| `stable` (and `latest`) | What installed systems follow. |
| `stable-YYYYMMDD`, `YYYYMMDD` | That day's build; use `bootc switch` to pin or go back to a specific day. |
| `stable-<git-sha>` | The exact commit. |

The OS version shown in Tamarack (os-release `IMAGE_VERSION`) is `<Fedora version>.<build date>`, e.g. `44.20261026`;
`/usr/share/ublue-os/image-info.json` also records the upstream Bazzite version and the git commit.

## How a release happens

1. A change lands on `main` (directly or via pull request; PRs build and test both images but never publish).
2. `Build images` runs lint, unit tests and the QML self-test, then builds both images on top of the current
   `bazzite:stable`/`bazzite-nvidia-open:stable`, runs `tests/image/check-image.sh` inside each image, rechunks them,
   pushes all tags, signs the digest with cosign (`SIGNING_SECRET`) and verifies the signature with `cosign.pub`.
3. `Disk images and VM test` boots each new image in QEMU/KVM and runs the system, session and UI checks.
4. A daily scheduled rebuild picks up upstream security fixes even without Tamarack changes.
5. Installer ISOs are produced weekly and on demand (workflow dispatch), only after the VM test passes, and uploaded as
   workflow artifacts with SHA-256 checksums.

Before calling a build "released", review the VM test screenshots and logs (artifacts `vm-results-*`) and run the
[physical hardware checklist](../TESTING.md#physical-hardware-checklist) on at least one machine per edition.

## How users upgrade

- Automatic: `uupd.timer` stages new versions in the background; they apply at the next restart.
- Manual: Tamarack Center > Updates & Recovery > *Update now*, or `ujust update`, or `sudo bootc upgrade`.
- Roll back: boot menu (previous entry) or `sudo bootc rollback`.
- Pin a day's build: `sudo bootc switch ghcr.io/brecken321/tamarack-os:stable-20261026` (switch back to `:stable` later).

## Fedora major version upgrades

Bazzite moves `stable` to a new Fedora release after testing. Tamarack follows automatically on the next build;
preflight (`build_files/steps/00-preflight.sh`) and the image checks catch structural changes. Read Bazzite's release
notes before such a rebuild and run the VM test plus the hardware checklist.

## Signing key management

- Private key: GitHub Actions secret `SIGNING_SECRET` (cosign key without password, as the Universal Blue template
  requires), plus an offline copy kept by the maintainer. Never commit it; `tests/test_config.py` fails if one appears.
- Public key: `cosign.pub` in the repository and `/etc/pki/containers/tamarack-os.pub` in the image.
- Rotation: generate a new key pair, ship an image whose policy trusts **both** public keys, wait until users have
  updated, then switch the CI secret to the new key and later remove the old public key.
