"""One-shot explorer: navigate through Heidi's pages and dump each AX tree.

Run ONCE from Ghostty (logged in):
    python scripts/explore_all.py

Dumps every page to reports/explore_<page>.txt so selectors can be written
without round-tripping. Covers: main/scribe, sidebar, devices, settings,
new-session, and the note input area.
"""
import sys
import time
from pathlib import Path

import xa11y

REPORTS = Path(__file__).resolve().parent.parent / "reports"
REPORTS.mkdir(exist_ok=True)


def dump(app, label, max_depth=14):
    path = REPORTS / f"explore_{label}.txt"
    try:
        tree = app.dump(max_depth=max_depth)
    except Exception as e:
        tree = f"<dump failed: {e}>"
    path.write_text(tree, encoding="utf-8")
    print(f"  saved {label}: {len(tree)} chars -> {path.name}")
    return tree


def click_sidebar(app, label):
    """Try several selectors to click a sidebar item. Returns True if clicked."""
    for sel in [
        f"static_text[value='{label}']",
        f"button[name='{label}']",
        f"link[name='{label}']",
        f"group[name='{label}']",
        f"static_text[name='{label}']",
    ]:
        try:
            loc = app.locator(sel)
            if loc.exists():
                loc.press()
                print(f"  clicked '{label}' via {sel}")
                return True
        except Exception:
            continue
    print(f"  could NOT find sidebar item '{label}'")
    return False


def main():
    app = xa11y.App.by_name("Heidi", timeout=10.0)
    print(f"Connected to Heidi (pid={app.pid})")

    # 0. Whatever we land on first
    dump(app, "00_initial")

    # 1. Scribe (main) page
    click_sidebar(app, "Scribe")
    time.sleep(2)
    dump(app, "01_scribe")

    # 2. Devices page — the important one for bluetooth tests
    if click_sidebar(app, "Devices"):
        time.sleep(3)
        dump(app, "02_devices")

    # 3. Patients
    if click_sidebar(app, "Patients"):
        time.sleep(2)
        dump(app, "03_patients")

    # 4. Settings
    if click_sidebar(app, "Settings"):
        time.sleep(2)
        dump(app, "04_settings")

    # 5. Back to Scribe, then New session
    click_sidebar(app, "Scribe")
    time.sleep(2)
    for sel in ["button[name='New session']", "static_text[value='New session']"]:
        try:
            loc = app.locator(sel)
            if loc.exists():
                loc.press()
                print(f"  clicked New session via {sel}")
                break
        except Exception:
            continue
    time.sleep(2)
    dump(app, "05_new_session")

    print("\nDONE. All trees saved under reports/explore_*.txt")
    print("Share reports/explore_02_devices.txt for the bluetooth selectors.")


if __name__ == "__main__":
    main()
