# Desktop preset format

Presets live in `branding/presets/<id>.toml` (installed to `/usr/share/tamarack/presets/`). User presets created or
imported in Tamarack Center are JSON files in `~/.local/share/tamarack/presets/` with the same fields
(`{"format": "tamarack-desktop-preset", "version": 1, "preset": {...}}`).
Every field is validated by `tamarack.presets.parse_preset`; invalid files are rejected with a message naming the field.

```toml
id = "gaming"                 # file name must match; letters, digits, '-'
name = "Gaming"
summary = "One sentence shown in Tamarack Center."
default = false               # exactly one built-in preset is the default

[appearance]
mode = "dark"                 # light | dark | auto (light by day, dark at night) | high-contrast
wallpaper = "Tamarack-Dusk"   # a wallpaper package in /usr/share/wallpapers
font_size = 10                # points; 10 = KDE default (keys are removed, restoring defaults)
cursor_size = 24              # 24 | 30 | 36 | 48 | 60 | 72
animation_duration = 0.5      # KDE factor: 0 (off), 0.125, 0.25, 0.5, 1 (normal), 2, 4, 8
blur = false                  # KWin blur effect
titlebar_buttons_left = ""    # Breeze codes: M menu, S all desktops, H help, I minimize,
titlebar_buttons_right = "IAX" # A maximize, X close, F keep above, B keep below, N app menu, L shade

[panel]
location = "bottom"           # top | bottom | left | right
thickness = 46                # pixels
floating = true
length_mode = "fill"          # fill (full width) | fit (dock)
alignment = "center"          # left | center | right
hiding = "none"               # none | autohide | dodgewindows | windowsgobelow
opacity = "adaptive"          # adaptive | opaque | translucent
launcher = "kickoff"          # kickoff (start menu) | kicker (classic menu) | kickerdash (app grid)
task_manager = "icontasks"    # icontasks (icons only) | tasks (icons + window titles)
widgets = ["launcher", "spacer", "tasks", "spacer", "tray", "clock", "showdesktop"]
                              # exactly one launcher and one tasks; also: pager, spacer, separator
pins = ["applications:steam.desktop", "preferred://browser"]
                              # pins for apps that are not installed are skipped when applying

[desktop]
virtual_desktops = 1          # 1–20
virtual_desktop_rows = 1      # ≤ virtual_desktops

[behavior]
quick_tiling = true           # drag windows to screen edges to tile/maximize
dnd_when_fullscreen = true    # Do Not Disturb while a fullscreen app is focused
steam_autostart = false       # start Steam minimized at login
```

## What applying a preset does

1. Backs up `kdeglobals`, `kwinrc`, `kcminputrc`, `plasmarc`, `plasmashellrc`,
   `plasma-org.kde.plasma.desktop-appletsrc`, `kscreenlockerrc`, `plasmanotifyrc`, `ksplashrc` and `kdedefaults/` to
   `~/.local/state/tamarack/appearance-backups/` (last 10 kept).
2. `plasma-apply-lookandfeel --apply <Tamarack Light|Dark|High Contrast>` (with `-k` for automatic mode).
3. `kwriteconfig6 --notify` for fonts, cursor size, animation speed, blur, title-bar buttons, tiling, Do Not Disturb,
   lock-screen wallpaper and the automatic light/dark pair.
4. A Plasma desktop script (`org.kde.PlasmaShell.evaluateScript`) replaces the panels and sets the wallpaper:
   `tamarack preset script <id>` prints it.
5. Virtual desktops through KWin's D-Bus API, Steam autostart, then `qdbus6 org.kde.KWin /KWin reconfigure`.

Undo (`tamarack preset undo`) restores the backed-up files and restarts the Plasma shell.
