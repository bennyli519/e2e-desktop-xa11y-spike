"""Probe the recording controls in the Scribe session view.

The start/stop-recording controls only appear after a session is opened, so a
plain page dump misses them. This script walks the flow and dumps the tree at
each stage so we can read the real role/name for each control:

    stage 1  reports/rec_00_scribe.txt      — Scribe landing (after login)
    stage 2  reports/rec_01_new_session.txt — after clicking "New session"
    stage 3  reports/rec_02_recording.txt   — after starting recording (if found)

Run from Ghostty (needs Screen Recording permission), logged in:
    .venv/bin/python3.14 scripts/probe_recording.py
"""
import sys
import time
from pathlib import Path

import xa11y

REPORTS = Path(__file__).resolve().parent.parent / "reports"
REPORTS.mkdir(exist_ok=True)


def dump(app: xa11y.App, label: str, depth: int = 16) -> None:
    tree = app.dump(max_depth=depth)
    (REPORTS / f"{label}.txt").write_text(tree)
    print(f"  saved reports/{label}.txt ({len(tree)} chars)")


def click_first(app: xa11y.App, selectors: list[str]) -> str | None:
    for sel in selectors:
        try:
            loc = app.locator(sel)
            if loc.exists():
                loc.press()
                return sel
        except Exception:
            continue
    return None


def main() -> int:
    app = xa11y.App.by_name("Heidi", timeout=10.0)
    print(f"Connected to {app.name} (pid={app.pid})")

    print("stage 1: Scribe landing")
    dump(app, "rec_00_scribe")

    print("stage 2: click 'New session'")
    hit = click_first(app, [
        "button[name='New session']",
        "static_text[value='New session']",
    ])
    print(f"  new session via: {hit!r}")
    time.sleep(3)
    dump(app, "rec_01_new_session")

    print("stage 3: look for a start-recording control")
    # Candidate names seen in Heidi builds; we don't press unknown coords.
    # Report which candidates EXIST so we can pick the real selector.
    candidates = [
        "button[name='Start']",
        "button[name='Record']",
        "button[name='Start recording']",
        "button[name='Resume']",
        "button[name='Transcribe']",
        "button[name*='Transcribe']",
        "button[name*='recording']",
        "button[name*='Record']",
        "combo_box[name*='transcription']",
    ]
    print("  existing recording-control candidates:")
    for sel in candidates:
        try:
            if app.locator(sel).exists():
                print(f"    FOUND: {sel}")
        except Exception:
            pass

    hit = click_first(app, [
        "button[name='Start']",
        "button[name='Start recording']",
        "button[name='Record']",
    ])
    if hit:
        print(f"  started recording via: {hit!r}")
        time.sleep(4)
        dump(app, "rec_02_recording")
    else:
        print("  no obvious start button pressed — inspect rec_01_new_session.txt")

    print("\nDone. Paste the reports back or let the assistant read them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
