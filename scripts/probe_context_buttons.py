"""Identify the Context tab's paperclip button by STRUCTURE (no coordinates).

For every empty-name button on the Context tab, print:
  - its parent's child roles (to spot the mic, whose sibling is a combo_box)
  - whether it has an image child and that image's name
  - its bounds (for reference only)

This lets us pick a robust semantic selector for the paperclip vs the mic.

RUN FROM GHOSTTY, Heidi frontmost, in a session:
    .venv/bin/python scripts/probe_context_buttons.py
Paste the output back.
"""
import sys
import time
from pathlib import Path

import xa11y

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import activate_app  # noqa: E402
from pages import ScribePage  # noqa: E402


def describe(el, depth=0):
    try:
        role = el.role
    except Exception:
        role = "?"
    name = (getattr(el, "name", "") or "").strip()
    return f"{role}:{name!r}"


def main() -> None:
    app = xa11y.App.by_name("Heidi", timeout=10.0)
    activate_app("Heidi")
    time.sleep(2.0)
    rec = ScribePage(app)
    rec.open_context_tab()
    time.sleep(1.5)

    btns = app.locator("button").elements()
    print(f"total buttons: {len(btns)}\n")
    for i, b in enumerate(btns):
        name = (b.name or "").strip()
        if name:
            continue  # only care about the icon-only (empty-name) buttons
        # parent + siblings
        try:
            parent = b.parent()
            sibs = [describe(c) for c in parent.children()] if parent else []
        except Exception as e:
            sibs = [f"<err {e!r}>"]
        # children (image?)
        try:
            kids = [describe(c) for c in b.children()]
        except Exception:
            kids = []
        try:
            bnds = b.bounds
            bstr = f"x={int(bnds.x)},y={int(bnds.y)},w={int(bnds.width)},h={int(bnds.height)}"
        except Exception:
            bstr = "no-bounds"
        print(f"[{i}] EMPTY button  {bstr}")
        print(f"     children: {kids}")
        print(f"     parent siblings: {sibs}")
        print()


if __name__ == "__main__":
    main()
