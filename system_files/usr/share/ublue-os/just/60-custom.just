# vim: set ft=make :
# Tamarack OS recipes for `ujust`. Universal Blue imports this file
# (60-custom.just is reserved for images built on top of Universal Blue).

# Open Tamarack Center (presets, privacy, hardware, games, updates)
[group('Tamarack')]
tamarack-center:
    tamarack-center

# Show a system health report: updates, drivers, gaming stack, privacy
[group('Tamarack')]
tamarack-doctor:
    tamarack doctor

# List desktop presets, or apply one: ujust tamarack-preset gaming
[group('Tamarack')]
tamarack-preset PRESET="":
    #!/usr/bin/bash
    set -euo pipefail
    if [[ -z "{{ PRESET }}" ]]; then
        tamarack preset list
    else
        tamarack preset apply "{{ PRESET }}"
    fi

# Check a game's anti-cheat / Linux status: ujust tamarack-game "Elden Ring"
[group('Tamarack')]
tamarack-game NAME:
    tamarack games check "{{ NAME }}"
