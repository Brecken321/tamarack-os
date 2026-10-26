"""Shared test fixtures. Tests never touch the real system: commands go through FakeRunner."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tamarack.brand import Brand, load_brand_toml
from tamarack.presets import Preset, load_presets
from tamarack.system import FakeRunner

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def brand() -> Brand:
    return load_brand_toml(ROOT / "branding" / "brand.toml")


@pytest.fixture(scope="session")
def presets() -> list[Preset]:
    return load_presets(ROOT / "branding" / "presets")


@pytest.fixture
def runner() -> FakeRunner:
    return FakeRunner()


@pytest.fixture
def node() -> str:
    path = shutil.which("node")
    if path is None:
        pytest.skip("node is not installed; cannot syntax-check generated JavaScript")
    return path
