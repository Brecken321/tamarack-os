#!/usr/bin/bash
# Packages Tamarack adds on top of Bazzite. Keep this list short: every
# package here must be needed by a Tamarack feature (see docs/ARCHITECTURE.md).
# shellcheck source=/dev/null
source "${CTX}/lib.sh"

packages=(
    # Tamarack Center UI (Qt 6 / QML with KDE Kirigami, already in Plasma).
    python3-pyside6
    # KDE's own settings pages the Privacy page links to: per-app Flatpak
    # permissions and the firewall (firewalld backend).
    flatpak-kcm
    plasma-firewall-firewalld
    # Hardware diagnostics in Tamarack Center (`tamarack hardware`).
    pciutils
    usbutils
    glx-utils
    smartmontools
)

dnf5 -y install --setopt=install_weak_deps=False "${packages[@]}"

# Fail early if the UI stack cannot be imported.
python3 -c 'import PySide6.QtQml, PySide6.QtGui; print("PySide6", PySide6.__version__)'

# Nothing we add may leave extra repositories enabled in the final image.
if dnf5 repolist --enabled 2>/dev/null | grep -qi copr; then
    log "note: COPR repositories enabled by the base image:"
    dnf5 repolist --enabled | grep -i copr || true
fi
