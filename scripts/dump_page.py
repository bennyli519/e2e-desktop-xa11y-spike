"""Exploration script: dump the AX tree for a given page.

Usage (from Ghostty):
    python scripts/dump_page.py                      # dump current page
    python scripts/dump_page.py --page Devices       # click sidebar, then dump
    python scripts/dump_page.py --page Settings      # click sidebar, then dump
    python scripts/dump_page.py --depth 15           # deeper tree

Saves output to reports/<page>_tree.txt
"""
import argparse
import sys
import time
from pathlib import Path

import xa11y

SIDEBAR_ITEMS = [
    "Scribe", "Evidence", "Tasks", "Comms", "Patients",
    "My Templates", "My Forms", "Templates", "Team",
    "Settings", "Devices", "Dictate history", "Help", "Notifications",
]


def main():
    parser = argparse.ArgumentParser(description="Dump Heidi AX tree")
    parser.add_argument("--page", default=None, help="Sidebar item to click first")
    parser.add_argument("--depth", type=int, default=12, help="Max tree depth")
    parser.add_argument("--app", default="Heidi", help="App name")
    args = parser.parse_args()

    app = xa11y.App.by_name(args.app, timeout=10.0)
    print(f"Connected to {app.name} (pid={app.pid})")

    if args.page:
        print(f"Navigating to: {args.page}")
        # Try multiple selector strategies since Tauri's AX tree varies
        for selector in [
            f"static_text[value='{args.page}']",
            f"link[name='{args.page}']",
            f"button[name='{args.page}']",
            f"static_text[name='{args.page}']",
            f"group[name='{args.page}']",
        ]:
            try:
                loc = app.locator(selector)
                if loc.exists():
                    loc.press()
                    print(f"  Clicked via: {selector}")
                    break
            except Exception:
                continue
        else:
            print(f"  WARNING: could not find sidebar item '{args.page}'")

        time.sleep(2)  # wait for page transition

    # Dump
    tree = app.dump(max_depth=args.depth)
    print(f"\nTree ({len(tree)} chars):\n")
    print(tree)

    # Save to file
    reports = Path(__file__).resolve().parent.parent / "reports"
    reports.mkdir(exist_ok=True)
    label = args.page or "current"
    out = reports / f"{label}_tree.txt"
    out.write_text(tree, encoding="utf-8")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
