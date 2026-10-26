# Contributing

## Repository layout

| Path | What it is |
|---|---|
| `Containerfile` | Image definition: branding render stage → build context → layered on Bazzite |
| `build_files/build.sh`, `build_files/steps/NN-*.sh` | Build steps run inside the image, in order |
| `system_files/` | Files copied as-is into the image root (`/usr`, `/etc`) |
| `branding/brand.toml` | **Single source** for name, IDs, URLs, palette, wallpapers |
| `branding/presets/*.toml` | Desktop presets ([docs/PRESETS.md](docs/PRESETS.md)) |
| `branding/tamarack_branding/` | Build-time generator: color schemes, global themes, icons, wallpapers, desktop entries |
| `src/tamarack/` | Python package used by the CLI, Tamarack Center and the generator |
| `src/tamarack/ui/` | Tamarack Center (PySide6 + Kirigami QML) |
| `data/awacy/` | Vendored AreWeAntiCheatYet snapshot + source metadata |
| `disk_config/` | bootc-image-builder configs (installer ISO, VM disk) |
| `tests/` | Unit tests (`pytest`), image checks (`tests/image`), VM boot test (`tests/vm`) |
| `.github/workflows/` | CI: build/test/publish images; disk images + VM boot test + ISOs |

## Development setup

Any OS with Python 3.11+ can run the unit tests and the branding generator:

```bash
python3 -m pip install pytest mypy ruff
just test
just lint                   # ruff, mypy --strict, shellcheck, just --fmt
just branding               # render branding sources into output/branding (no rasterizing)
```

Building images needs Linux with podman (`just build main`). The UI needs PySide6 and KDE Kirigami
(on Fedora: `dnf install python3-pyside6 kf6-kirigami kf6-qqc2-desktop-style`); then
`PYTHONPATH=src python3 -m tamarack.ui.app` runs Tamarack Center from the checkout, and
`QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 -m tamarack.ui.app --self-test` compiles every QML file.

## Rules of the road

- **No ads, no tracking, no dark patterns.** Nothing promotional, nothing that reinstalls removed software, optional data
  collection off by default.
- **Reuse upstream.** If Bazzite, Universal Blue, Fedora or KDE already provides a feature, configure it rather than
  rebuilding it. Do not modify the kernel.
- **No fake functionality.** Every button must do something real, or not exist. Mark planned features in ROADMAP.md.
- **Honest data.** Compatibility, privacy and hardware statements must come from a named source or be marked unknown.
- **Tests come with changes.** Parsers get fixture-based tests; system interaction goes through `tamarack.system.Runner`
  so tests use `FakeRunner`. QML changes must pass the self-test. Image changes should add a check to
  `tests/image/check-image.sh`.
- **Typed, explicit Python.** `mypy --strict`, no silent `except: pass`, structured logging via `logging`.
- **Shell:** `set -euo pipefail`, shellcheck clean, no `curl | bash`.
- **Brand neutrality in code.** User-visible names, colors and URLs come from `branding/brand.toml`.

## Pull requests

CI builds both images for every pull request and runs all checks, but only pushes to `main` publish images. Describe what
you tested and on which hardware; update [TESTING.md](TESTING.md) and [docs/HARDWARE.md](docs/HARDWARE.md) with real results.
Commits should be focused, with messages explaining *why*.
