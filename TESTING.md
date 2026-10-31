# Testing

Tamarack OS is tested in four layers. Everything in layers 1–3 runs automatically in GitHub Actions; layer 4 needs
real hardware and is done by hand with the checklist below.

| Layer | What | Where | Command |
|---|---|---|---|
| 1. Static + unit | ruff, mypy `--strict`, shellcheck, `just --fmt`; 197 pytest tests, including a check that every button, switch, card and action in the QML has a handler; generated JS syntax (`node --check`); desktop-file validation; QML self-test (every page compiled and instantiated against real Kirigami) | Fedora 44 container | `just lint`, `just test` |
| 1b. Center preview and button check | Renders every Tamarack Center page and Welcome step in both themes with example data (KDE platform theme, Breeze, OpenGL), then **clicks every visible button, switch and clickable card, and every control inside the dialogs, sheets and menus they open** (page actions are toolbar buttons; overflow-menu entries are clicked in their menus) and fails if one has no visible effect or raises a QML error, also one printed while the app closes | Fedora 44 container with Xvfb | `tamarack-center --screenshots DIR`, `--check-buttons REPORT` |
| 2. Image content | ~75 checks run *inside* each built image: branding, themes, wallpapers, KDE defaults, privacy defaults, signature policy, services, gaming stack, NVIDIA driver presence, CLI, Tamarack Center QML load | Each image (both editions) | `just check-image main` |
| 3. VM boot and install | bootc-image-builder makes a qcow2; QEMU/KVM boots it (UEFI); checks over SSH; logs into Plasma via the virtual keyboard; opens the start menu; presses the Windows-style shortcuts and checks the right windows open; applies presets; opens every Tamarack Center page; **drives Tamarack Center itself, clicking its switches and buttons (privacy, Game Mode, performance overlay, looks, a custom look, Welcome, automatic updates, Keep this version, Update now) and checking each change in the running system (systemd, NetworkManager, KRunner, Plasma's notifications, power profiles, Plasma's panels and KWin, ostree)**; **downloads an app (Filelight), a game (SuperTux) and a launcher (Heroic) from Flathub as the desktop user and opens each one; installs Claude Code with its official installer and runs it; opens Bazaar (waiting until it has loaded Flathub's apps), Firefox and the Center from their menu entries; lets Steam download its client up to its window; removes an app**; checks that every pinned app and every System Settings page a Center button opens exists; screenshots. Then: installer ISOs, and an unattended Anaconda install onto a blank virtual disk followed by the same checks. Also: an older build updated to the current one, restarted, checked, then rolled back from Tamarack Center (Roll back, Stay on, Roll back, Restart now, with the password typed into polkit's dialog) | GitHub-hosted runner with KVM | `tests/vm/run-vm-test.sh`, `tests/vm/install-test.sh`, `tests/vm/update-test.sh` |
| 3b. Live USB | Builds the live ISO from each published image (Titanoboa), boots it in QEMU with UEFI (screenshots of the boot menu, boot screen and desktop), then boots its kernel with a serial console and checks the live system: medium found, live user set up and signed in automatically, Plasma, Welcome, default apps ready without downloading, half the memory as room for changes, Flathub's app list loads; then opens the app store (screenshot) | GitHub-hosted runner with KVM | `tests/vm/live-test.sh` |
| 3c. Windows readiness check | Edition picks for 20 graphics cards and a full read-only run in Windows PowerShell 5.1 | `windows-latest` runner | `tests/windows/test-check-ready.ps1` |
| 4. Physical hardware | GPU drivers, real games, Wi-Fi/Bluetooth/audio, sleep, displays, controllers, install/dual-boot | A real PC | [Checklist](#physical-hardware-checklist) |

## What each automated layer proves, and what it doesn't

- **Unit tests** prove the logic: preset validation and the exact `kwriteconfig6`/Plasma-script output, WCAG contrast of
  the generated color schemes, deterministic artwork, Steam library parsing, anti-cheat verdict mapping (including that
  *Verified* is never invented), hardware parsing from real-world fixtures, privacy parsing, update-status parsing,
  preset apply/undo against a fake home directory, and that no secrets are committed.
  They do **not** prove KDE behaves as expected; that is layer 3.
- **The button check** proves every control in Tamarack Center reacts when used: a page opens, a dialog appears, a
  request reaches the system layer (install, apply, refresh…), an app or link is started, or a switch flips. It runs
  against example data, so it does **not** prove the request then succeeds on a real system; the VM test covers the
  ones that change the system for real (see below). "Undo last change" is never enabled with the example data, so only
  the VM test clicks it.
- **Image checks** prove the image contains and enables what we claim. They run with no network and no hardware.
- **The VM test** proves the image boots, reaches the desktop, verifies its update signature against the registry, installs
  default apps from Flathub, that presets, the Windows-style shortcuts and Tamarack Center work in a real Plasma session,
  and that apps and games really download from Flathub and open, and Steam downloads its client and reaches sign-in.
  Tamarack Center's settings are changed by clicking them in the running app (found by their accessible names, like a
  screen reader), and each one is checked in the system it changes, not in a settings file: for example Do Not Disturb
  by asking Plasma whether it holds notifications back, blur by asking KWin whether the effect is loaded. Not covered:
  "Steam on the discrete GPU" (needs hybrid graphics), "Sign out", and exporting or importing a look (the system file
  dialog; unit tests cover the file format). A VM
  has no real GPU (software rendering), so it says **nothing** about game performance, NVIDIA drivers, Wi-Fi, Bluetooth,
  audio hardware, sleep or battery, and nothing about downloading games through Steam (that needs an account).
- **The unattended install test** builds an installer ISO with the same builder and image as the release ISOs (plus a
  test kickstart that partitions automatically and creates a throwaway user), installs onto an empty virtual disk with
  Anaconda, then boots the installed system and runs the full VM test on it. It does **not** click through the
  interactive installer that people use, and it does not test encryption or dual-boot.
- **The live USB test** proves the live ISO boots with UEFI from a CD/USB-like drive and reaches a signed-in Tamarack
  desktop with nothing written to a disk. It runs without Secure Boot and without a GPU, so it does **not** prove the
  NVIDIA driver works in the live session, or that a particular PC's firmware boots the stick.
- **The update and rollback test** moves a disk of an older build to the current `:stable` (download, signature check,
  staging), restarts into it, runs the system checks and the update service, then, in Tamarack Center: Roll back,
  Stay on (undoes it), Roll back again and Restart now, checking bootc's state after each, and boots the old version. It covers one update step on the standard edition, not months of updates.

## Results log

Newest first. "CI" entries link to the workflow run that produced them.

<!-- results:start -->

### 2026-10-31: full run, every edition, every layer (CI [run 41169379037](https://github.com/Brecken321/tamarack-os/actions/runs/41169379037), images 44.20261031)

All 14 jobs passed, with **0 failures** in every check file.

| | Standard | NVIDIA | NVIDIA (older cards) |
|---|---|---|---|
| VM test (534 checks, 298 clicking through Tamarack Center) | ✅ 10.6 s to graphical | ✅ 20.0 s | ✅ 15.0 s |
| Installer ISO, unattended install onto a blank disk, then the same 534 checks | ✅ installed in 8.0 min | ✅ 8.5 min | ✅ 8.7 min |
| Live USB (10 checks, app store screenshot with Flathub's apps) | ✅ | ✅ | ✅ |
| Claude Code (2.1.314) installs with its official installer and runs, on the test disk and the installed system | ✅ | ✅ | ✅ |
| Steam reaches **Sign in to Steam** | ✅ 103 s | ✅ 111 s | ✅ 108 s |
| Memory in use with Plasma open (6 GB VM; after the tests' downloads on installed systems) | 2.0–2.4 GB | 2.1–2.6 GB | 2.1–2.5 GB |

Update and rollback (standard): 44.20261030 → 44.20261031 in 105 s, restart, all 58 system checks, then Roll back,
Stay on, Roll back and Restart now in Tamarack Center, which booted the old version: 43 checks, ✅ 0 failures.

The app store screenshots of the freshly installed systems showed "Refreshing": the test closed the store about 17 s
after opening it, before its first load of Flathub's catalog had finished. The VM test now waits for the store to finish
loading (a check) before its screenshot.

ISOs from this run (SHA-256):

| File | SHA-256 |
|---|---|
| `tamarack-os-20261031-x86_64.iso` | `acd91c0c6ecdb3292ac69c9edf8a3093f0c0a549a8999fd95cef6c477f672b08` |
| `tamarack-os-nvidia-20261031-x86_64.iso` | `741de83619d6ae71dbeb9f453aa0078146d4ed82211702e90fdf6c115289cafe` |
| `tamarack-os-nvidia-legacy-20261031-x86_64.iso` | `28e8b47275591b69fef46b550cc237f7eb93589b5e826e1a6897260beff13e32` |
| `tamarack-os-live-20261031-x86_64.iso` | `f15ad761e0ada9d1f1b64f099114e8e78e17932b77838a326c8bbcb0bc5baea7` |
| `tamarack-os-nvidia-live-20261031-x86_64.iso` | `e9cb3323a3374c11c08020b84d135462b7c4c63d55b43d66231822cee62059a6` |
| `tamarack-os-nvidia-legacy-live-20261031-x86_64.iso` | `76d982239776882c310dc5b7f9f4f8893ebdaba8217e6d015070ed50e38bf89b` |

### 2026-10-30: live USB in VirtualBox on the ASUS laptop; app store fixed in the live session (CI [run 41166974289](https://github.com/Brecken321/tamarack-os/actions/runs/41166974289))

The NVIDIA live ISO of 2026-10-29 (SHA-256 checked) was started in VirtualBox 7.2.22 on the ASUS TUF F17 under
Windows 11: 3 GB of memory and 4 cores for the VM, UEFI, no virtual disk. It reached the signed-in desktop with Welcome
in about 2 minutes. With only 8 GB in the laptop it was slow, and the VM can't use the GPU. Claude Code (2.1.314)
installed with its official installer and ran in the live session.

Problems found there, and fixed:
- **The app store showed no apps.** The live session keeps every change in memory, in /run, which systemd sizes at
  20% of the memory: 588 MB in that VM. Steam's first-run download (485 MB) filled it, and Flathub's app list could no
  longer be written. The live session now gives half the memory to changes.
- **The screen locked** after a few idle minutes, and nothing said that the live user's password is empty. The live
  session no longer locks (an empty password with Enter unlocks older live USBs; INSTALL.md says so).
- **The terminal banner said "Welcome to Bazzite".** It now names Tamarack OS, and an image check covers it.

The live USB test now checks both and opens the store:

| | Standard | NVIDIA | NVIDIA (older cards) |
|---|---|---|---|
| Live USB checks (10) | ✅ 0 failures | ✅ 0 failures | ✅ 0 failures |
| Room for changes in a 6 GB VM (was about 1.2 GB) | 2.9 GB | 2.9 GB | 2.9 GB |
| Flathub's app list in the live session | 3,528 apps | 3,528 apps | 3,528 apps |
| App store (Bazaar) opens with Flathub's apps (screenshot) | ✅ | ✅ | ✅ |

In the 3 GB VirtualBox VM the store still showed only empty sections, even right after a fresh start. It said it was
showing "a cached version of Flathub": with the laptop out of free memory, its requests to Flathub did not complete.
In the CI VM, on the same live system, the store works.

### 2026-10-29: every Tamarack Center setting clicked and checked in the running system (CI [run 40983747229](https://github.com/Brecken321/tamarack-os/actions/runs/40983747229) and [run 40985807096](https://github.com/Brecken321/tamarack-os/actions/runs/40985807096), button check [run 40976164677](https://github.com/Brecken321/tamarack-os/actions/runs/40976164677), images 44.20261030)

| | Standard | NVIDIA | NVIDIA (older cards) |
|---|---|---|---|
| VM test (532 checks, 298 of them clicking through Tamarack Center) | ✅ 0 failures, 12.4 s to graphical | ✅ 0 failures, 15.0 s | ✅ 0 failures, 18.8 s |
| Steam reaches **Sign in to Steam** | ✅ 102 s | ✅ 98 s | ✅ 112 s |
| Memory in use with Plasma open (6 GB VM) | 2.0 GB | 2.0 GB | 2.1 GB |
| Update 44.20261029 → 44.20261030, then rollback from Tamarack Center (43 checks) | ✅ 0 failures | not run | not run |

What the VM test clicked in Tamarack Center on each edition, and where it checked the result:

| Clicked | Checked in |
|---|---|
| Help Fedora count installations, on and off (polkit asks for the password) | the `rpm-ostree-countme` timer |
| Detect Wi-Fi sign-in pages, off and on | NetworkManager's connectivity check |
| Show app store results in search, off and on | the plugins KRunner has loaded |
| Remember recently opened files, off and on | the activity manager's settings file |
| Game Mode on, then off | the active power profile (performance, then balanced again); Plasma's notification server, which holds notifications back and then shows them again |
| Performance overlay in all Steam games, on and off | Steam's launcher, and the environment of a running Steam (`MANGOHUD=1`) |
| Apply a look, Reset to default, Undo last change | the desktop: theme, panels, KWin effects, compared with each look |
| Customize… on Gaming: floating panel, blur, start Steam at login, Save and apply | the saved look has those three changes, and the desktop matches it |
| More Actions → Delete on that look | the look's file is gone |
| Welcome, from the first step to Finish | the desktop matches the chosen look; Welcome is marked as completed |
| Automatic updates, off and on | the `uupd` timer |
| Keep this version | the running version is pinned in ostree |
| Update now | the update service ran |
| Roll back, Stay on, Roll back, Restart now (update test) | bootc's queued rollback after each click; the computer restarted into the old version |

Tamarack Center logged no QML errors on any edition, including while closing.

The button check now also clicks every control inside the dialogs, sheets and menus that buttons open: 301 controls in
Tamarack Center and 30 in Welcome, 0 failures (232 before).

Found and fixed:
- **Game Mode never turned on Do Not Disturb.** It wrote the end time as an ISO date; KConfig reads dates only as
  `Y,M,D,h,m,s` and ignored it. Reading the settings file would have passed; asking Plasma caught it.
- **KDE settings sometimes took effect only after a restart of the app.** `kwriteconfig6 --notify` can exit before
  its D-Bus change notice is sent. It showed as Do Not Disturb staying on after Game Mode was turned off, in two runs
  and on different editions each time. Every KDE setting Tamarack writes (looks, the two search and history switches, Game Mode) now
  sends the notice again with `busctl`, which waits until it is delivered.
- **After Roll back there was no way back without restarting.** bootc only queues a rollback, and nothing said so.
  The Updates page now says "*version* starts at the next restart", with **Restart now…** and **Stay on *version***
  (which cancels it), and disables Roll back meanwhile. Home, `tamarack doctor` and `tamarack updates status` say it too.
- **Closing Tamarack Center printed hundreds of QML errors** (361 in one run): Python freed the backend while pages
  still used it. The backend now belongs to the QML engine, so it is freed last.
- The 17 fields of the Customize sheet had no accessible names, so screen readers said nothing about them.
- Look previews used an SVG filter (film grain) that Qt cannot draw; previews leave it out.
- Test fixes: the button check had skipped controls inside dialogs and controls that moved when an earlier click added
  one above them. The check for "Automatic" looks now accepts KDE's switch to dark at night. A busy container registry
  (503) no longer breaks the VM run, and a failed disk build now fails its step instead of the test that follows.

### 2026-10-29: boot screen, Steam Gaming Mode, older-NVIDIA edition, live USB (CI [run 40800886139](https://github.com/Brecken321/tamarack-os/actions/runs/40800886139), [run 40801940564](https://github.com/Brecken321/tamarack-os/actions/runs/40801940564) and [run 40807543348](https://github.com/Brecken321/tamarack-os/actions/runs/40807543348), images 44.20261029)

| | Standard | NVIDIA | NVIDIA (older cards) |
|---|---|---|---|
| VM boot test (131 checks, now including the boot screen theme and the Gaming Mode session) | ✅ 0 failures, 18.1 s to graphical | ✅ 0 failures, 31.3 s | ✅ 0 failures, 30.0 s |
| Downloads: Filelight, SuperTux, Heroic | ✅ 3 s, 52 s, 26 s | ✅ 4 s, 52 s, 30 s | ✅ 3 s, 42 s, 27 s |
| Steam reaches **Sign in to Steam** | ✅ 106 s | ✅ 116 s | ✅ 112 s |
| Memory in use with Plasma open (6 GB VM) | 1.9 GB | 2.2 GB | 2.2 GB |
| Unattended install from ISO, then the same 131 checks | ✅ 0 failures, installed in 8.0 min | ✅ 0 failures, 8.4 min | ✅ 0 failures, 7.9 min |
| Live USB: UEFI boot menu, boot screen, signed-in desktop with Welcome (8 checks) | ✅ signed in 30 s after boot | ✅ 30 s | ✅ 40 s |

**Older-NVIDIA edition** (new): built on `bazzite-nvidia` with NVIDIA's closed 580 driver (the build refuses a base with
the open modules), and the VM test passes like the other editions. The driver itself needs a real GTX 750/900/1000-series
card.

**Steam Gaming Mode** (new): the session is on the sign-in screen and its command is installed (image and VM checks).
The VM test also signs in to it: without a GPU Gamescope cannot start, and the session returns to the sign-in screen
instead of leaving a black screen. Playing in Gaming Mode needs real hardware.

**Boot screen** (new): the Tamarack theme is the default and is inside the initramfs (image and VM checks). The VM test
boots with a text console, so the screen itself is seen in the live USB's boot screenshots: firmware logo, spinner and the
Tamarack OS logo.

**Live USB** (new): the first run failed one check because systemd 258 quotes names in its sign-in log line; the test
was fixed, and a GRUB "boot success" timer that cannot work on a live medium was turned off. The older-NVIDIA live USB
was added afterwards and passes the same checks.

ISOs from run 40807543348 (SHA-256):

| File | Size | SHA-256 |
|---|---|---|
| `tamarack-os-20261029-x86_64.iso` | 5.8 GB | `ccd4e38ff6e67e1c9968a66939052eb17f7040a78049aebdb8bb22cdc8961575` |
| `tamarack-os-nvidia-20261029-x86_64.iso` | 6.3 GB | `0367abe063da5949aa20a7a141152ce9cfed21c85edf9dc5b83e6d45302b22b0` |
| `tamarack-os-nvidia-legacy-20261029-x86_64.iso` | 6.4 GB | `aa039e76df32639a50ccae915d6b32700c9be5775118f500b916aaa1a29044c5` |
| `tamarack-os-live-20261029-x86_64.iso` | 6.1 GB | `7b7a3bae76c4348f298a2c0f48911f0ab700c7b86c3035b82696b8d445f2aa7c` |
| `tamarack-os-nvidia-live-20261029-x86_64.iso` | 6.5 GB | `9b560e5f6e563e6c60b1cf45e120d04a42a6b480f007be7a5a95e11b4877d6e6` |
| `tamarack-os-nvidia-legacy-live-20261029-x86_64.iso` | 6.6 GB | `8cd50df5adb560e8990e2f2b8558eddf1d6bad62ab88c8033f07defee1b45e4f` |

**Found in the logs:** apps that print the system version showed the base image's `44.20261026.0 (Kinoite)`, because
os-release `VERSION` was never set. It is now this build's version, with an image check.

**Update and rollback**: 44.20261028 → current `:stable` in 173 s, restart, all checks, `uupd` clean, rollback: ✅.

**Windows readiness check** (new): passes on `windows-latest` and, run on the ASUS TUF F17, picks the NVIDIA edition
for its GTX 1650 Ti.

### 2026-10-28: update and rollback, accessible names, signing outage fix (CI [run 40763643090](https://github.com/Brecken321/tamarack-os/actions/runs/40763643090) and [run 40775071019](https://github.com/Brecken321/tamarack-os/actions/runs/40775071019), images 44.20261028)

| | Standard | NVIDIA |
|---|---|---|
| VM boot test (126 checks) | ✅ 0 failures, 20.5 s to graphical | ✅ 0 failures, 31.3 s |
| Unattended install from ISO (8 min), then the same 126 checks | ✅ 0 failures | ✅ 0 failures |
| Light-theme taskbar (Productivity and Minimalist presets): solid and readable (screenshots) | ✅ | ✅ |

**Update and rollback (new test, standard edition).** A disk of yesterday's build (44.20261027) moved to the current
`:stable`:
1. It downloaded the new version, verified its signature and staged it in 157 s. `tamarack updates status` reported
   a restart was needed.
2. After a restart it booted the new version, kept the old one for rollback, passed all 53 system checks, and the update
   service (`uupd`, which automatic updates and "Update now" use) ran cleanly and found nothing newer.
3. `bootc rollback` (what "Roll back" runs) and a restart booted the old version again, with the graphical login and no
   failed units.

The update was a `bootc switch` to `:stable`. On an installed system `uupd` stages an update the same way, through
`bootc upgrade`.

**Button check** now also requires an accessible name (what a screen reader announces) on every control: all 232
controls have one and all still work. Page previews also render in a 640 px window; the layouts reflow to one column.

**Signing outage.** The scheduled build of 2026-10-28 pushed the standard image and then failed to sign it, because
Sigstore's transparency log returned 502. `:stable` then pointed at an unsigned image, which installed systems refuse.
Signing now retries and, if the log stays down, signs without a log entry. Verification uses only the public key. The next
build re-published signed images, and both editions verify.

Release ISOs from run 40763643090: `tamarack-os-20261028-x86_64.iso`, 5.8 GB, SHA-256
`1fd1bad99e09c6f3c4dbddaf081f4312b4a6dc0fda4ccc424d6fa8803e872b6e`; `tamarack-os-nvidia-20261028-x86_64.iso`, 6.4 GB,
SHA-256 `6579065042659129750976381fa7b93572b2d653bd96f01ad04dd9332a560e29`.

### 2026-10-27: redesigned Center, every button checked, real downloads, Windows-style desktop (CI [run 40584857350](https://github.com/Brecken321/tamarack-os/actions/runs/40584857350), images 44.20261027)

All six jobs passed. Every system below ran the same 126 checks with **0 failures**: both editions booted from a disk
image, and both installed by Anaconda from their ISO onto a blank disk.

| | Standard | NVIDIA |
|---|---|---|
| Boot to SSH / systemd to graphical target | 102 s / 12.1 s | 152 s / 21.2 s |
| Unattended install from ISO, then boot to SSH | 8 min 1 s, 111 s | 8 min 40 s, 131 s |
| Memory in use with Plasma open (6 GB VM) | 1.6 GB | 1.7 GB |
| First boot downloads Flathub's app catalog; Center app search finds Filelight and SuperTux | ✅ | ✅ |
| Download and install as the desktop user, through Tamarack's installer: Filelight (app), SuperTux (game), Heroic (Epic/GOG launcher) | ✅ 2 s, 52 s, 25 s | ✅ 3 s, 60 s, 28 s |
| Each one opens its window (SuperTux reaches its title screen) | ✅ | ✅ |
| Bazaar app store, Firefox and Tamarack Center open from their menu entries | ✅ | ✅ |
| Steam: first-run notice, client download, **Sign in to Steam** window | ✅ 110 s | ✅ 111 s |
| Remove an app as the user; it leaves the start menu | ✅ | ✅ |
| Win+I, Ctrl+Shift+Esc, Win+E, Win+. open Settings, System Monitor, Dolphin, the emoji picker; Win+S and Win+Tab open search and the overview (screenshots) | ✅ | ✅ |
| Every System Settings page a Center button opens (36) exists; every pinned app is installed | ✅ | ✅ |

Release ISOs from this run: `tamarack-os-20261027-x86_64.iso`, 5.8 GB, SHA-256
`3abc16f5bcb8879bb3f65680cbc287819d90e37557dea8a9f10a79375ff8e4e6`; `tamarack-os-nvidia-20261027-x86_64.iso`, 6.4 GB,
SHA-256 `ad7dc0f50434e69310998693655f089abdb3c15cc060df7744d13055bc8c803b`.

The new button check (Center preview workflow) clicks all 232 controls in Tamarack Center and the Welcome flow. Its first run
found that **every Install button and the preset Customize preview did nothing**: PySide6 hands QML arrays and objects to
Python as `QJSValue`. Earlier VM tests installed apps through the `tamarack` CLI, so they never caught it. Fixed, with a
regression test; all 232 controls now pass.

Found and fixed while getting here:
- App search had no catalog. Flatpak fetches it only on demand, and only from the desktop session; first-boot setup now
  downloads it.
- Bazzite's Steam launcher waits for OK on a first-run notice. The test presses Enter, as a person would.
- The screen locked during the long downloads. Auto-lock is now off for the test session.
- Closing an app's test unit did not close Flatpak apps. The test now uses `flatpak kill`.
- Daytime screenshots showed the clock and tray almost invisible: a see-through taskbar over the wallpaper's dark treeline,
  with the light theme's dark text. Presets that use the light theme now have a solid taskbar, enforced by a unit test.
  The follow-up VM run ([run 40610646614](https://github.com/Brecken321/tamarack-os/actions/runs/40610646614), images
  44.20261028) passed all 126 checks on both editions, but it ran at night, so it shows the dark theme (taskbar solid and
  readable). From now on the VM test also applies the always-light Productivity preset, so every run screenshots a
  light taskbar.
- Preset cards lost their descriptions with the VM's font metrics. They are back on Kirigami's `CardsLayout`.

### 2026-10-27: installer ISOs and unattended install (CI [run 40467069805](https://github.com/Brecken321/tamarack-os/actions/runs/40467069805), images 44.20261027)

All six jobs passed: boot test, release ISO and unattended install test for both editions.

| | Standard | NVIDIA |
|---|---|---|
| Release ISO | `tamarack-os-20261027-x86_64.iso`, 5.8 GB, SHA-256 `0b5807ae41f55e220883c0b801b1d36485c753084bf649a586317f8a54ed4df1` | `tamarack-os-nvidia-20261027-x86_64.iso`, 6.4 GB, SHA-256 `2184a139db1e00ca28487f3a500e689c1d562c7b268d0d3ede728707962d6b00` |
| Anaconda install onto a blank 64 GB virtual disk (automatic Btrfs partitioning) | ✅ 8 min 11 s | ✅ 8 min 41 s |
| Installed system: boot to SSH / systemd to graphical target | ✅ 92 s / 12.5 s | ✅ 132 s / 16.8 s |
| Installed system tracks the signed registry image (`ostree-image-signed:docker://ghcr.io/brecken321/…:stable`); update check verifies the signature | ✅ | ✅ |
| No failed units (including `bootloader-update.service` on an Anaconda install) | ✅ | ✅ |
| Graphical login screen, Plasma session, presets, Tamarack Center, first-boot apps (all 23 VM checks) | ✅ | ✅ |

The previous run ([40460863771](https://github.com/Brecken321/tamarack-os/actions/runs/40460863771)) found that after a
**text-mode** install Anaconda makes the installed system boot to a text console (`multi-user.target`). Fixed for every
ISO with `xconfig --startxonboot`, so a fallback to the text installer can no longer leave users without a desktop. That
run also confirmed the NVIDIA CDI fix (no failed units on either edition). One earlier run
([40451568833](https://github.com/Brecken321/tamarack-os/actions/runs/40451568833)) lost its NVIDIA runner mid-test with no
logs; the VM test now bounds every wait so a hang fails with logs instead.

The test ISO differs from the release ISO only in its kickstart (automatic partitioning and a throwaway user instead of
the interactive screens). The interactive graphical installer has not been clicked through in CI.

### 2026-10-27: VM boot test, second round (CI [run 40446510853](https://github.com/Brecken321/tamarack-os/actions/runs/40446510853), images 44.20261027)

| Check | Standard | NVIDIA |
|---|---|---|
| Boot to SSH / systemd "startup finished" | ✅ 16.6 s to graphical target | ✅ ~20.5 s |
| No failed units | ✅ | ❌ `nvidia-cdi-refresh` failed (no NVIDIA GPU in the VM): **fixed** with a skip-without-GPU drop-in |
| Update check verifies the image signature against the registry | ✅ | ✅ |
| `bootloader-update.service` | ✅ (fixed by keeping image labels through rechunking) | ✅ |
| Default apps, Firefox privacy prefs, firewall, countme off | ✅ | ✅ |
| Plasma session: theme, color scheme, panel layout, wallpaper, Tamarack launcher icon | ✅ | ✅ |
| Presets applied over the live session (Gaming, Classic, Minimalist, High Contrast, reset) | ✅ all 30 steps | ✅ all 30 steps |
| Tamarack Center pages render in the session (screenshots) | ✅ | ✅ |
| Login screen shows the Tamarack wallpaper | ✅ | ✅ |
| Memory in use with Plasma + Tamarack Center open (6 GB VM) | ~1.8 GB | — |

Screenshot review led to: app names instead of Flatpak ids on the Apps page, aligned shortcut list on Help.

### 2026-10-27: first VM boot test (CI [run 40435677118](https://github.com/Brecken321/tamarack-os/actions/runs/40435677118), images from 2026-10-26)

Both editions, qcow2 disk, QEMU/KVM, UEFI, 4 vCPU, 6 GB RAM, virtio-gpu (no GPU acceleration).

| Check | Standard | NVIDIA |
|---|---|---|
| Boot to SSH | ✅ 109 s | ✅ 153 s |
| Tamarack OS identity, graphical target, login manager running | ✅ | ✅ |
| First-boot default apps from Flathub (Firefox etc.), Firefox privacy prefs in place | ✅ | ✅ |
| Firewall active, countme off, Steam present, `tamarack doctor/privacy/games` work | ✅ | ✅ |
| Log in through the virtual keyboard, Plasma session, Tamarack global theme + color scheme | ✅ | ✅ |
| Desktop: Tamarack wallpaper, Clean Modern taskbar with Tamarack launcher and pins, Welcome opens (screenshots) | ✅ | ✅ |
| No failed units | ❌ `bootloader-update.service` failed (under investigation) | ❌ same |
| Update check (`bootc upgrade --check`) verifies the signature | ❌ `:stable` digest was unsigned: **fixed** (sign every pushed digest, verify every tag) | ❌ same |
| Session layout checks | ❌ used `qdbus6`, absent on Fedora 44: **fixed** (presets now use `busctl`) | ❌ same |
| Login screen wallpaper | ❌ still Bazzite's: **fixed** (`/etc/plasmalogin.conf` outranks vendor drop-ins) | ❌ same |
| Welcome hides the navigation sidebar | ❌ sidebar shown greyed out: **fixed** | ❌ same |

The image content checks added after this run also caught two dead System Settings links (`kcm_flatpak` was renamed
`kcm_app-permissions` upstream; the firewall page needed `plasma-firewall-firewalld`), both fixed.

### 2026-10-26: image builds (CI [run 40416438687](https://github.com/Brecken321/tamarack-os/actions/runs/40416438687))

Both editions built on `bazzite:stable` / `bazzite-nvidia-open:stable` (Fedora 44, kernel 7.2.11-ogc), all image content
checks passed (branding, themes, privacy defaults, signature policy, firewall on, SSH off, Steam/Gamescope/MangoHud/Lutris,
32-bit Vulkan, NVIDIA module presence/absence per edition, CLI, Tamarack Center QML load).

<!-- results:end -->

## Not tested yet

- Any physical machine (including the target ASUS TUF F17 with GTX 1650 Ti).
- Steam sign-in and downloading games through Steam (needs an account), game performance, controller input, frame
  pacing, VRR/HDR, multi-monitor. (Downloading and opening a free game from Flathub, and Steam's own first-run download
  up to its sign-in window, are tested in the VM.)
- The interactive (graphical) installer screens, installing from a USB stick on a real PC, disk encryption, dual-boot
  with Windows. (The unattended install into a VM is tested.)
- Secure Boot with NVIDIA key enrollment.
- The live USB on a real PC (firmware boot, Wi-Fi, the NVIDIA driver in the live session).
- Steam Gaming Mode with a real GPU (in the VM Gamescope cannot start and the session falls back to the sign-in screen).
- Sleep/resume, battery life, Wi-Fi, Bluetooth, printers, webcams.
- Updating and rolling back on a real install over many builds. One update from the previous day's build, with
  rollback, is tested in a VM.

## Physical hardware checklist

Run on a spare disk or after a full backup. Record the edition, image version (`tamarack doctor` first line), date and
results in [docs/HARDWARE.md](docs/HARDWARE.md) via a pull request or issue.

**Install**
- [ ] ISO boots from USB in UEFI mode (Secure Boot on, if supported by the PC).
- [ ] Installer detects disks; automatic partitioning; optional encryption passphrase works at boot.
- [ ] Dual-boot only: Windows still boots; both appear in the boot menu.
- [ ] First boot reaches the login screen; Welcome opens after login; default apps appear within ~10 minutes.

**Graphics (NVIDIA edition)**
- [ ] `ujust enroll-secure-boot-key` → MOK enrollment → after reboot `tamarack hardware` shows `driver: nvidia`.
- [ ] `nvidia-smi` works. Hybrid laptops: Hardware page shows *Hybrid graphics*.
- [ ] Hybrid: turn on *Run Steam on the discrete GPU*, restart Steam, a game shows the NVIDIA GPU in MangoHud.

**Graphics (standard edition)**
- [ ] `tamarack hardware` shows amdgpu/i915/xe and a Vulkan device (not llvmpipe).

**Gaming**
- [ ] Steam installs updates, signs in, downloads a free game (e.g. *Team Fortress 2* or *Counter-Strike 2*'s offline mode, or any owned game).
- [ ] A Windows-only game runs with Proton (Properties > Compatibility).
- [ ] `MANGOHUD=1 %command%` shows the overlay; note average FPS and 1% lows; compare with Windows if available.
- [ ] Controller works in Steam Big Picture (USB and Bluetooth).
- [ ] Gaming page: the game appears with a rating; the launch log appears after `PROTON_LOG=1 %command%`.
- [ ] Fullscreen game: no desktop notifications pop up.

**Desktop**
- [ ] Each preset applies cleanly; *Undo last change* restores the previous look; *Reset to default* works.
- [ ] Custom preset: save, export, delete, import.
- [ ] Display settings: resolution, refresh rate, scaling; multi-monitor if available; VRR/HDR toggles if supported.
- [ ] Night light, brightness keys, volume keys, keyboard backlight (laptops).
- [ ] File manager: copy a large folder to a USB drive (progress shown), open a ZIP, preview images/PDF/video.

**Hardware**
- [ ] Wi-Fi connects; Ethernet; Bluetooth headset/controller pair; speakers, headphone jack, HDMI audio, microphone.
- [ ] Webcam in a browser test page.
- [ ] Laptop: battery %, charge limit (if offered), lid close → sleep → resume works, touchpad gestures.
- [ ] Printer (if available).

**Updates and recovery**
- [ ] Updates page shows the version; *Update now* runs; after restart the new version is booted.
- [ ] *Roll back* → restart → previous version is booted; personal files unchanged.
- [ ] Boot menu: the previous entry boots.

**Performance (record numbers)**
- [ ] `systemd-analyze` boot time; idle RAM (`free -m` after login settles); idle CPU (`top`).
- [ ] Same measurements on upstream Bazzite (same machine) for comparison.
