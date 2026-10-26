#!/usr/bin/bash
# Install generated branding, static system files and the Tamarack tools.
# shellcheck source=/dev/null
source "${CTX}/lib.sh"
load_brand

cp -a "${CTX}/generated/." /
cp -a "${CTX}/system_files/." /

# Python package (standard library + PySide6 only), byte-compiled for speed.
install -d /usr/lib/tamarack/python
cp -a "${CTX}/src/tamarack" /usr/lib/tamarack/python/
find /usr/lib/tamarack/python -type d -name __pycache__ -prune -exec rm -rf {} +
python3 -m compileall -q /usr/lib/tamarack/python

# Game anti-cheat dataset snapshot (AreWeAntiCheatYet, MIT licensed).
install -D -m 0644 "${CTX}/data/awacy/games.json" /usr/share/tamarack/games/awacy-games.json
install -D -m 0644 "${CTX}/data/awacy/source.json" /usr/share/tamarack/games/awacy-source.json
install -D -m 0644 "${CTX}/data/awacy/LICENSE" /usr/share/licenses/tamarack/AreWeAntiCheatYet-LICENSE
install -D -m 0644 "${CTX}/LICENSE" /usr/share/licenses/tamarack/LICENSE

# Git on Windows does not preserve exec bits reliably; set them explicitly.
chmod 0755 /usr/bin/tamarack /usr/bin/tamarack-center /usr/libexec/tamarack/*

# Desktop entries must point at icons and binaries that exist.
for desktop in /usr/share/applications/"${BRAND_REVERSE_DNS}".*.desktop; do
    desktop-file-validate "${desktop}" || die "invalid desktop file ${desktop}"
done
