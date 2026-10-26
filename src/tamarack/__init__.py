"""Tamarack OS system tools.

The package is split in two layers:

* Pure logic (presets, colors, parsers for hardware/privacy/update data,
  game compatibility lookups) that has no runtime dependencies beyond the
  Python standard library and is fully unit tested.
* Thin integration layers (``system``, ``kconfig``, ``ui``) that call real
  system tools (kwriteconfig6, bootc, flatpak, systemctl, ...) through a
  single injectable command runner, so tests can substitute fakes.
"""

__version__ = "0.1.0"
