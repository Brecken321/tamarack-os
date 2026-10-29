"""Consistency checks across build configuration files."""

import re
import subprocess
import tomllib
from pathlib import Path

import pytest

from tamarack.brand import Brand

ROOT = Path(__file__).resolve().parents[1]


def _env() -> dict[str, str]:
    values = {}
    for line in (ROOT / "image.env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value.strip('"')
    return values


def test_image_names_match_branding(brand: Brand) -> None:
    env = _env()
    assert env["IMAGE_MAIN"] == brand.image_main
    assert env["IMAGE_NVIDIA"] == brand.image_nvidia
    assert env["IMAGE_NVIDIA_LEGACY"] == brand.image_nvidia_legacy
    assert env["IMAGE_REGISTRY"] == brand.registry
    assert env["DEFAULT_TAG"] == brand.default_tag
    assert env["BASE_MAIN"].startswith("ghcr.io/ublue-os/bazzite:")
    assert env["BASE_NVIDIA"].startswith("ghcr.io/ublue-os/bazzite-nvidia-open:")
    assert env["BASE_NVIDIA_LEGACY"].startswith("ghcr.io/ublue-os/bazzite-nvidia:")


def test_iso_configs_point_at_published_images(brand: Brand) -> None:
    for flavor, image in (
        ("main", brand.image_main),
        ("nvidia", brand.image_nvidia),
        ("nvidia-legacy", brand.image_nvidia_legacy),
    ):
        text = (ROOT / f"disk_config/iso-{flavor}.toml").read_text(encoding="utf-8")
        tomllib.loads(text)
        assert f"{brand.registry}/{image}:{brand.default_tag}" in text


def test_containerfile_args_are_used() -> None:
    containerfile = (ROOT / "Containerfile").read_text(encoding="utf-8")
    args = set(re.findall(r"^ARG (\w+)", containerfile, re.MULTILINE))
    scripts = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "build_files").rglob("*.sh"))
    for arg in args - {"BASE_IMAGE"}:
        assert f"${{{arg}" in scripts or f"${arg}" in scripts, f"ARG {arg} is never used by the build steps"


def test_build_steps_are_numbered_and_strict() -> None:
    steps = sorted((ROOT / "build_files/steps").glob("*.sh"))
    assert steps and all(re.match(r"\d\d-[a-z-]+\.sh$", s.name) for s in steps)
    build = (ROOT / "build_files/build.sh").read_text(encoding="utf-8")
    assert "set -euo pipefail" in build and "bash -euo pipefail" in build


def test_no_secrets_in_repository() -> None:
    assert not (ROOT / "cosign.key").exists()
    pub = (ROOT / "cosign.pub").read_text(encoding="utf-8")
    assert pub.startswith("-----BEGIN PUBLIC KEY-----")
    # Built at runtime so neither this file nor its bytecode matches the search.
    private_marker = " ".join(["BEGIN", "ENCRYPTED", "SIGSTORE", "PRIVATE", "KEY"])
    try:
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git is not available")
    for name in tracked.stdout.splitlines():
        path = ROOT / name
        if not path.is_file() or path.suffix in (".png", ".jpg", ".json"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert private_marker not in text, path
        assert not re.search(r"gh[pousr]_[A-Za-z0-9]{30,}", text), path


def test_workflows_cover_every_flavor() -> None:
    workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
    assert "flavor: [main, nvidia, nvidia-legacy]" in workflow
    disk = (ROOT / ".github/workflows/build-disk.yml").read_text(encoding="utf-8")
    assert disk.count("flavor: [main, nvidia, nvidia-legacy]") == 3
    assert "github.event_name != 'pull_request'" in workflow  # PRs never publish
