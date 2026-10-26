"""`tamarack` command-line interface.

Every graphical feature in Tamarack Center is also available here, so
power users and support instructions can work without the GUI.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__, appearance, apps, doctor, games, gaming, hardware, logs, privacy, steam, updates
from .brand import RUNTIME_BRAND_JSON, Brand, load_runtime_brand
from .presets import default_preset, layout_script
from .system import Runner, SubprocessRunner


def _print_json(data: Any) -> None:
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def _brand() -> Brand:
    if not RUNTIME_BRAND_JSON.exists():
        raise SystemExit(f"{RUNTIME_BRAND_JSON} not found: is this a Tamarack OS system?")
    return load_runtime_brand()


def cmd_doctor(args: argparse.Namespace, runner: Runner) -> int:
    data = doctor.report(runner, include_hardware=not args.quick)
    if args.json:
        _print_json(data)
        return 0
    system = data["system"]
    print(f"{system['name']} {system['version']}  ({system['image']}, based on {system['based_on'] or 'unknown'})")
    print(f"Kernel {system['kernel']}  session {system['session'] or 'none'}")
    upd = data["updates"]
    booted = upd.get("booted") or {}
    print(f"\nRunning version: {booted.get('version', 'unknown')} ({booted.get('date', '')})")
    if upd.get("staged"):
        print(f"Update ready: {upd['staged']['version']} (restart to finish)")
    if upd.get("rollback"):
        print(f"Rollback available: {upd['rollback']['version']}")
    auto = upd.get("auto_updates")
    print(f"Automatic updates: {'on' if auto else 'off' if auto is False else 'unknown'}")
    print("\nGaming tools:")
    for name, present in data["gaming"].items():
        print(f"  {'yes' if present else 'NO '}  {name}")
    print(f"\nDefault apps: {data['default_apps'].get('message', '')}")
    if data["problems"]:
        print("\nNeeds attention:")
        for problem in data["problems"]:
            print(f"  - {problem}")
    else:
        print("\nNo problems found.")
    return 0


def cmd_hardware(args: argparse.Namespace, runner: Runner) -> int:
    report = hardware.collect(runner)
    if args.json:
        _print_json(report.to_dict())
        return 0
    category = None
    for item in report.items:
        if item.category != category:
            category = item.category
            print(f"\n{category}")
        driver = f" [driver: {item.driver}]" if item.driver else ""
        print(f"  {item.status.upper():9} {item.name}{driver}")
        if item.detail:
            print(f"            {item.detail}")
        if item.advice:
            print(f"            -> {item.advice}")
    return 0


def cmd_privacy(args: argparse.Namespace, runner: Runner) -> int:
    if args.set:
        name, _, value = args.set.partition("=")
        if value not in ("on", "off"):
            raise SystemExit("use --set NAME=on|off")
        result = privacy.set_toggle(runner, name, value == "on")
        print("done" if result.ok else f"failed: {result.error_summary()}")
        return 0 if result.ok else 1
    report = privacy.collect(runner)
    if args.json:
        _print_json(report.to_dict())
        return 0
    print("Optional data sharing:")
    for key, value in report.toggles.items():
        print(f"  {key:16} {'on' if value else 'off' if value is False else 'unknown'}")
    print("\nNetwork listeners (reachable from other devices):")
    exposed = [x for x in report.listeners if not privacy.is_loopback(x.address)]
    for item in exposed or []:
        print(f"  {item.protocol} {item.address}:{item.port} {item.process}")
    if not exposed:
        print("  none")
    print("\nApps with sensitive access:")
    for app in report.apps:
        flags = [
            n for n, v in (("camera", app.camera), ("microphone", app.microphone), ("location", app.location)) if v
        ]
        print(f"  {app.app_id}: files={app.files}; {', '.join(flags) or 'no camera/mic/location'}")
    return 0


def cmd_preset(args: argparse.Namespace, runner: Runner) -> int:
    paths = appearance.Paths(Path.home())
    presets = appearance.all_presets(paths)
    if args.action == "list":
        current = appearance.current_preset(paths)
        for preset in presets:
            marker = "*" if preset.id == current else " "
            print(f"{marker} {preset.id:16} {preset.name} - {preset.summary}")
        return 0
    if args.action in ("apply", "reset"):
        if args.action == "reset":
            preset = default_preset(presets)
        else:
            if not args.name:
                raise SystemExit("usage: tamarack preset apply NAME")
            preset = appearance.find_preset(presets, args.name)
        result = appearance.apply(preset, _brand(), runner, paths)
    elif args.action == "undo":
        result = appearance.restore(paths, runner)
    elif args.action == "export":
        if not args.name or not args.file:
            raise SystemExit("usage: tamarack preset export NAME FILE")
        data = appearance.export_preset_data(appearance.find_preset(presets, args.name))
        Path(args.file).write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"exported {args.name} to {args.file}")
        return 0
    elif args.action == "import":
        if not args.name:
            raise SystemExit("usage: tamarack preset import FILE")
        preset = appearance.import_preset_data(json.loads(Path(args.name).read_text(encoding="utf-8")))
        target = appearance.save_user_preset(paths, preset)
        print(f"imported preset '{preset.name}' ({preset.id}) to {target}")
        return 0
    elif args.action == "script":
        print(layout_script(appearance.find_preset(presets, args.name), _brand().logo_icon))
        return 0
    else:
        raise SystemExit(f"unknown action {args.action}")
    for step in result.steps:
        print(f"  {'ok  ' if step.ok else 'FAIL'} {step.step}{': ' + step.detail if step.detail else ''}")
    print(f"Backup saved; undo with: tamarack preset undo ({Path(result.backup).name})")
    return 0 if result.ok else 1


def cmd_games(args: argparse.Namespace, runner: Runner) -> int:
    db = games.AntiCheatDatabase.load()
    if args.action == "check":
        verdicts = games.check(db, " ".join(args.query))
        if args.json:
            _print_json([v.to_dict() for v in verdicts])
            return 0
        for v in verdicts:
            print(f"{v.game}: {v.title}")
            print(f"  {v.explanation}")
            if v.anticheats:
                print(f"  Anti-cheat: {', '.join(v.anticheats)}")
            if v.source:
                print(f"  Source: {v.source} ({v.source_url}), last changed {v.last_changed or 'unknown'}")
            for label, url in v.links.items():
                print(f"  {label}: {url}")
            print()
        return 0
    if args.action == "library":
        install = steam.scan(Path.home())
        if install is None:
            print("Steam has not been set up for this user yet (open Steam once).")
            return 0
        rows = []
        for game in install.games:
            v = games.verdict(db.by_steam_id(game.appid), db.info, name=game.name, steam_id=game.appid)
            rows.append(
                {
                    "appid": game.appid,
                    "name": game.name,
                    "compat_tool": game.compat_tool,
                    "category": v.category,
                    "title": v.title,
                }
            )
        if args.json:
            _print_json({"steam": install.to_dict(), "games": rows})
            return 0
        for row in rows:
            print(f"  {row['title']:22} {row['name']} (app {row['appid']}, {row['compat_tool'] or 'default tool'})")
        print(f"\nProton versions: {', '.join(install.proton_versions + install.custom_tools) or 'none yet'}")
        return 0
    if args.action in ("dgpu", "overlay", "mode"):
        paths = appearance.Paths(Path.home())
        choice = args.query[0] if args.query else "status"
        if choice not in ("status", "on", "off"):
            raise SystemExit(f"usage: tamarack games {args.action} [status|on|off]")
        if args.action == "mode":
            if choice != "status":
                for res in gaming.set_game_mode(runner, paths.state, choice == "on"):
                    if not res.ok:
                        print(f"warning: {res.error_summary()}", file=sys.stderr)
            print("on" if gaming.game_mode_active(paths.state) else "off")
            return 0
        feature = "discrete_gpu" if args.action == "dgpu" else "overlay"
        if choice != "status":
            env = gaming.offload_env(hardware.collect(runner).gpus) if feature == "discrete_gpu" else None
            gaming.set_feature(paths.data, feature, choice == "on", env)
            if (paths.autostart / "steam.desktop").exists():
                appearance.set_steam_autostart(paths, True)
            print("Quit and reopen Steam to apply.")
        print("on" if gaming.is_enabled(paths.data, feature) else "off")
        return 0
    if args.action == "data":
        info = db.info
        print(
            f"{info.name} ({info.license}) {info.url}\n  commit {info.commit or 'unknown'} from "
            f"{info.commit_date or 'unknown'}\n  {len(db.entries)} games, file {info.path}"
        )
        return 0
    raise SystemExit(f"unknown action {args.action}")


def cmd_updates(args: argparse.Namespace, runner: Runner) -> int:
    if args.action == "status":
        _print_json(updates.status(runner).to_dict())
        return 0
    if args.action == "history":
        _print_json(updates.history(runner))
        return 0
    actions = {"now": updates.update_now, "rollback": updates.rollback, "pin": updates.pin_current}
    result = actions[args.action](runner)
    print("done" if result.ok else f"failed: {result.error_summary()}")
    if args.action == "rollback" and result.ok:
        print("The previous version will be used after the next restart.")
    return 0 if result.ok else 1


def cmd_apps(args: argparse.Namespace, runner: Runner) -> int:
    if args.action == "bundles":
        data = apps.bundles_with_state(runner)
        if args.json:
            _print_json(data)
            return 0
        for bundle in data:
            print(f"{bundle['id']:14} {bundle['name']} ({bundle['installed_count']}/{len(bundle['apps'])} installed)")
            print(f"               {bundle['description']}")
        return 0
    if args.action == "install":
        bundles = {b.id: b for b in apps.load_bundles()}
        ids: list[str] = []
        for name in args.names:
            ids.extend(bundles[name].apps if name in bundles else [name])
        result = apps.install(runner, ids)
        print("installed" if result.ok else f"failed: {result.error_summary()}")
        return 0 if result.ok else 1
    raise SystemExit(f"unknown action {args.action}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tamarack", description="Tamarack OS system tool")
    parser.add_argument("--version", action="version", version=f"tamarack {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging to stderr")
    sub = parser.add_subparsers(dest="command", required=True)

    d = sub.add_parser("doctor", help="system health summary")
    d.add_argument("--json", action="store_true")
    d.add_argument("--quick", action="store_true", help="skip hardware probing")
    d.set_defaults(func=cmd_doctor)

    h = sub.add_parser("hardware", help="detected hardware and drivers")
    h.add_argument("--json", action="store_true")
    h.set_defaults(func=cmd_hardware)

    pr = sub.add_parser("privacy", help="privacy dashboard")
    pr.add_argument("--json", action="store_true")
    pr.add_argument("--set", metavar="NAME=on|off", help=f"change: {', '.join(privacy.TOGGLES)}")
    pr.set_defaults(func=cmd_privacy)

    ps = sub.add_parser("preset", help="desktop presets")
    ps.add_argument("action", choices=["list", "apply", "undo", "reset", "export", "import", "script"])
    ps.add_argument("name", nargs="?")
    ps.add_argument("file", nargs="?")
    ps.set_defaults(func=cmd_preset)

    g = sub.add_parser("games", help="game compatibility (anti-cheat) and Steam library")
    g.add_argument("action", choices=["check", "library", "data", "dgpu", "overlay", "mode"])
    g.add_argument("query", nargs="*")
    g.add_argument("--json", action="store_true")
    g.set_defaults(func=cmd_games)

    u = sub.add_parser("updates", help="OS updates and rollback")
    u.add_argument("action", choices=["status", "history", "now", "rollback", "pin"])
    u.add_argument("--json", action="store_true")
    u.set_defaults(func=cmd_updates)

    a = sub.add_parser("apps", help="optional app bundles")
    a.add_argument("action", choices=["bundles", "install"])
    a.add_argument("names", nargs="*")
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=cmd_apps)
    return parser


def main(argv: list[str] | None = None, runner: Runner | None = None) -> int:
    args = build_parser().parse_args(argv)
    logs.setup(verbose=args.verbose)
    try:
        return int(args.func(args, runner or SubprocessRunner()))
    except KeyError as exc:
        print(f"error: {exc.args[0]}", file=sys.stderr)
        return 2
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
