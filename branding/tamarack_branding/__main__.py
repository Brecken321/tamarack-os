"""Generate every branding artifact into an output tree that mirrors ``/``.

Usage::

    python3 -m tamarack_branding --brand branding/brand.toml \
        --presets branding/presets --out /out [--no-render]

``--no-render`` writes only text/SVG sources (used by unit tests and on
machines without ``rsvg-convert``); the image build always renders.
"""

from __future__ import annotations

import argparse
import json
import logging
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from tamarack import art
from tamarack.brand import Brand, load_brand_toml
from tamarack.presets import LookAndFeelIds, Preset, default_preset, layout_script, load_presets, look_and_feel_defaults

from .colorscheme import all_schemes

log = logging.getLogger("tamarack_branding")

ICON_SIZES = (16, 22, 24, 32, 48, 64, 128, 256, 512)
LAYOUT_FILE = "org.kde.plasma.desktop-layout.js"


class Generator:
    def __init__(self, brand: Brand, presets: list[Preset], presets_dir: Path, out: Path, render: bool) -> None:
        self.brand = brand
        self.presets = presets
        self.presets_dir = presets_dir
        self.out = out
        self.render_enabled = render
        self.lnf = LookAndFeelIds.for_prefix(brand.reverse_dns)
        if render:
            for tool in ("rsvg-convert",):
                if shutil.which(tool) is None:
                    raise SystemExit(f"{tool} is required to render artwork (or pass --no-render)")

    # -- helpers -------------------------------------------------------------
    def write(self, rel: str, content: str | bytes) -> Path:
        path = self.out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
        return path

    def render(self, svg: Path, target: Path, width: int, height: int) -> None:
        """Rasterize ``svg``; ``target`` may be .png or .jpg."""
        if not self.render_enabled:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        png = target if target.suffix == ".png" else target.with_suffix(".tmp.png")
        subprocess.run(
            ["rsvg-convert", "--width", str(width), "--height", str(height), "--output", str(png), str(svg)],
            check=True,
        )
        if target.suffix in (".jpg", ".jpeg"):
            from PIL import Image  # imported lazily: only needed in the build container

            with Image.open(png) as image:
                image.convert("RGB").save(target, "JPEG", quality=90, optimize=True, progressive=True)
            png.unlink()

    # -- artifacts -----------------------------------------------------------
    def brand_files(self) -> None:
        self.write("usr/share/tamarack/brand.json", self.brand.to_json())
        b = self.brand
        accent = b.color("accent")
        env = {
            "BRAND_NAME": b.name,
            "BRAND_SHORT_NAME": b.short_name,
            "BRAND_ID": b.id,
            "BRAND_REVERSE_DNS": b.reverse_dns,
            "BRAND_VENDOR": b.vendor,
            "BRAND_HOME_URL": b.home_url,
            "BRAND_DOCUMENTATION_URL": b.documentation_url,
            "BRAND_SUPPORT_URL": b.support_url,
            "BRAND_BUG_REPORT_URL": b.bug_report_url,
            "BRAND_BASED_ON": b.based_on,
            "BRAND_DEFAULT_HOSTNAME": b.default_hostname,
            "BRAND_LOGO_ICON": b.logo_icon,
            "BRAND_ANSI_COLOR": f"0;38;2;{accent.r};{accent.g};{accent.b}",
            "BRAND_REGISTRY": b.registry,
            "BRAND_IMAGE_MAIN": b.image_main,
            "BRAND_IMAGE_NVIDIA": b.image_nvidia,
            "BRAND_DEFAULT_TAG": b.default_tag,
            "BRAND_LNF_LIGHT": self.lnf.light,
            "BRAND_LNF_DARK": self.lnf.dark,
            "BRAND_LNF_HIGH_CONTRAST": self.lnf.high_contrast,
            "BRAND_CENTER_APP_ID": b.center_app_id,
            "BRAND_DEFAULT_WALLPAPER": b.wallpapers[0],
        }
        lines = ["# Generated from branding/brand.toml. Source this file; do not edit."]
        lines += [f"{key}={shlex.quote(value)}" for key, value in env.items()]
        self.write("usr/share/tamarack/branding.env", "\n".join(lines) + "\n")

    def color_schemes(self) -> None:
        for scheme in all_schemes(self.brand):
            self.write(f"usr/share/color-schemes/{scheme.file_name}.colors", scheme.render())

    def icons(self) -> None:
        logo = art.logo_svg(self.brand)
        names = [self.brand.logo_icon, self.brand.center_app_id]
        for name in names:
            svg = self.write(f"usr/share/icons/hicolor/scalable/apps/{name}.svg", logo)
            for size in ICON_SIZES:
                self.render(svg, self.out / f"usr/share/icons/hicolor/{size}x{size}/apps/{name}.png", size, size)
        mono = self.write(f"usr/share/icons/hicolor/scalable/apps/{self.brand.logo_icon}-mono.svg", art.logo_mono_svg())
        self.render(mono, self.out / f"usr/share/pixmaps/{self.brand.logo_icon}-mono.png", 256, 256)
        self.render(
            self.out / f"usr/share/icons/hicolor/scalable/apps/{self.brand.logo_icon}.svg",
            self.out / f"usr/share/pixmaps/{self.brand.logo_icon}.png",
            256,
            256,
        )

    def boot_watermark(self) -> None:
        svg = self.write("usr/share/tamarack/art/wordmark.svg", art.wordmark_svg(self.brand))
        self.render(svg, self.out / "usr/share/plymouth/themes/spinner/watermark.png", 280, 64)

    def wallpapers(self) -> None:
        for name in self.brand.wallpapers:
            if name not in art.scene_names():
                raise SystemExit(f"brand.toml lists unknown wallpaper {name!r}; known: {art.scene_names()}")
            base = f"usr/share/wallpapers/{name}"
            metadata = {
                "KPlugin": {
                    "Authors": [{"Name": self.brand.vendor}],
                    "Id": name,
                    "License": "CC-BY-SA-4.0",
                    "Name": name.replace("-", " "),
                }
            }
            self.write(f"{base}/metadata.json", json.dumps(metadata, indent=4) + "\n")
            for variant, folder in (("light", "images"), ("dark", "images_dark")):
                for width, height in self.brand.wallpaper_sizes:
                    svg = self.write(
                        f"usr/share/tamarack/art/src/{name}-{variant}-{width}x{height}.svg",
                        art.wallpaper_svg(name, variant, width, height, self.brand.art_seed),
                    )
                    self.render(svg, self.out / f"{base}/contents/{folder}/{width}x{height}.jpg", width, height)
            shot = self.write(
                f"usr/share/tamarack/art/src/{name}-screenshot.svg",
                art.wallpaper_svg(name, "light", 400, 250, self.brand.art_seed),
            )
            self.render(shot, self.out / f"{base}/contents/screenshot.png", 400, 250)

    def look_and_feel(self) -> None:
        default = default_preset(self.presets)
        layout = layout_script(default, self.brand.logo_icon, replace_panels=False)
        wallpaper = self.brand.wallpapers[0]
        light, dark, high_contrast = all_schemes(self.brand)
        packages = [
            (self.lnf.light, light, "breeze", "light"),
            (self.lnf.dark, dark, "breeze-dark", "dark"),
            (self.lnf.high_contrast, high_contrast, "breeze-dark", "high-contrast"),
        ]
        splash_logo = art.logo_svg(self.brand)
        for pkg_id, scheme, icons, mode in packages:
            name, scheme_file = scheme.display_name, scheme.file_name
            base = f"usr/share/plasma/look-and-feel/{pkg_id}"
            metadata = {
                "KPackageStructure": "Plasma/LookAndFeel",
                "KPlugin": {
                    "Authors": [{"Name": self.brand.vendor}],
                    "Description": f"{name} global theme for {self.brand.name}",
                    "Id": pkg_id,
                    "License": "Apache-2.0",
                    "Name": name,
                    "Website": self.brand.home_url,
                },
            }
            self.write(f"{base}/metadata.json", json.dumps(metadata, indent=4) + "\n")
            defaults = look_and_feel_defaults(scheme_file, icons, wallpaper)
            defaults = defaults.replace("Theme=org.kde.breeze.desktop", f"Theme={pkg_id}")
            self.write(f"{base}/contents/defaults", defaults)
            self.write(f"{base}/contents/layouts/{LAYOUT_FILE}", layout)
            self.write(f"{base}/contents/splash/images/logo.svg", splash_logo)
            self.write(f"{base}/contents/splash/Splash.qml", self._splash_qml(mode))
            small = self.write(
                f"usr/share/tamarack/art/src/lnf-{mode}-preview.svg",
                art.preview_svg(self.brand, default, 480, 270, mode),
            )
            self.render(small, self.out / f"{base}/contents/previews/preview.png", 480, 270)
            big = self.write(
                f"usr/share/tamarack/art/src/lnf-{mode}-full.svg",
                art.preview_svg(self.brand, default, 1920, 1080, mode),
            )
            self.render(big, self.out / f"{base}/contents/previews/fullscreenpreview.jpg", 1920, 1080)

    def _splash_qml(self, mode: str) -> str:
        bg = "#000000" if mode == "high-contrast" else self.brand.palette["dark_view"]
        bar = "#FFD600" if mode == "high-contrast" else self.brand.palette["accent"]
        return SPLASH_QML.replace("@BACKGROUND@", bg).replace("@BAR@", bar)

    def presets_data(self) -> None:
        for preset in self.presets:
            shutil.copyfile(
                self.presets_dir / f"{preset.id}.toml", self._ensure(f"usr/share/tamarack/presets/{preset.id}.toml")
            )
            svg = self.write(
                f"usr/share/tamarack/presets/previews/{preset.id}.svg", art.preview_svg(self.brand, preset)
            )
            self.render(svg, self.out / f"usr/share/tamarack/presets/previews/{preset.id}.png", 480, 270)

    def desktop_entries(self) -> None:
        b = self.brand
        center = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={b.short_name} Center\n"
            "GenericName=System Control Center\n"
            f"Comment=Presets, privacy, hardware, games and updates for {b.name}\n"
            "Exec=tamarack-center\n"
            f"Icon={b.center_app_id}\n"
            "Terminal=false\n"
            "Categories=Settings;Qt;KDE;\n"
            "Keywords=privacy;hardware;drivers;games;proton;anticheat;presets;theme;updates;rollback;\n"
            "StartupNotify=true\n"
        )
        welcome = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name=Welcome to {b.name}\n"
            f"Comment=Set up {b.name}: look, privacy, apps and gaming\n"
            "Exec=tamarack-center --welcome\n"
            f"Icon={b.logo_icon}\n"
            "Terminal=false\n"
            "Categories=System;Qt;KDE;\n"
            "Keywords=setup;welcome;first run;tour;\n"
            "StartupNotify=true\n"
        )
        autostart = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name=Welcome to {b.name}\n"
            f"Comment=Shows the {b.short_name} welcome screen once, at your first login\n"
            "Exec=tamarack-center --welcome --first-run-only\n"
            f"Icon={b.logo_icon}\n"
            "Terminal=false\n"
            "OnlyShowIn=KDE;\n"
            "X-KDE-autostart-phase=2\n"
        )
        self.write(f"usr/share/applications/{b.center_app_id}.desktop", center)
        self.write(f"usr/share/applications/{b.reverse_dns}.Welcome.desktop", welcome)
        self.write(f"etc/xdg/autostart/{b.reverse_dns}.Welcome.desktop", autostart)
        # Start menu (Kickoff) favorites for new users, via Fedora's KDE profile.
        favorites = ";".join(
            [
                "preferred://browser",
                "org.kde.dolphin.desktop",
                "steam.desktop",
                "io.github.kolunmi.Bazaar.desktop",
                f"{b.center_app_id}.desktop",
                "systemsettings.desktop",
                "org.kde.konsole.desktop",
                "net.lutris.Lutris.desktop",
            ]
        )
        self.write(
            "usr/share/kde-settings/kde-profile/default/xdg/kicker-extra-favoritesrc",
            f"[General]\nPrepend={favorites};\nIgnoreDefaults=true\n",
        )

    def _ensure(self, rel: str) -> Path:
        path = self.out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def run(self) -> None:
        steps = (
            self.brand_files,
            self.color_schemes,
            self.icons,
            self.boot_watermark,
            self.wallpapers,
            self.look_and_feel,
            self.presets_data,
            self.desktop_entries,
        )
        for step in steps:
            log.info("generating %s", step.__name__)
            step()
        if self.render_enabled:
            # SVG sources of rasterized wallpapers are not needed in the image.
            shutil.rmtree(self.out / "usr/share/tamarack/art/src", ignore_errors=True)


SPLASH_QML = """\
// Tamarack OS login splash. Generated by tamarack_branding.
import QtQuick

Rectangle {
    id: root
    color: "@BACKGROUND@"

    // Set by ksplashqml: 1..6 as the session starts up.
    property int stage

    onStageChanged: {
        if (stage === 2) {
            fadeIn.start();
        } else if (stage === 5) {
            fadeOut.start();
        }
    }

    Image {
        id: logo
        anchors.centerIn: parent
        width: Math.round(Math.min(root.width, root.height) * 0.16)
        height: width
        sourceSize.width: width
        sourceSize.height: height
        source: "images/logo.svg"
        opacity: 0
        smooth: true
    }

    Rectangle {
        id: track
        anchors.top: logo.bottom
        anchors.topMargin: logo.height * 0.4
        anchors.horizontalCenter: parent.horizontalCenter
        width: logo.width * 1.4
        height: Math.max(3, Math.round(logo.height * 0.03))
        radius: height / 2
        color: Qt.rgba(1, 1, 1, 0.15)
        opacity: logo.opacity

        Rectangle {
            height: parent.height
            radius: parent.radius
            color: "@BAR@"
            width: parent.width * Math.min(root.stage, 6) / 6
            Behavior on width { NumberAnimation { duration: 250; easing.type: Easing.OutQuad } }
        }
    }

    OpacityAnimator { id: fadeIn; target: logo; from: 0; to: 1; duration: 500; easing.type: Easing.OutQuad }
    OpacityAnimator { id: fadeOut; target: logo; from: 1; to: 0; duration: 300; easing.type: Easing.InQuad }
}
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--brand", type=Path, required=True)
    parser.add_argument("--presets", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--no-render", action="store_true", help="skip rasterizing SVGs")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    brand = load_brand_toml(args.brand)
    presets = load_presets(args.presets)
    Generator(brand, presets, args.presets, args.out, render=not args.no_render).run()
    log.info("branding written to %s", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
