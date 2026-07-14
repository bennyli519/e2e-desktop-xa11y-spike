"""Dump the transcription-mode dropdown menu items after expanding it.

Uses ScribePage._open_mode_menu() (expand the split-button caret), then dumps
the tree + lists every candidate element so we can see the real role/name of
the 'Upload session audio' menu item.

RUN FROM GHOSTTY, logged in, Heidi foreground:
    .venv/bin/python scripts/dump_mode_menu.py
Then paste reports/mode_menu.txt (or the console output) back.
"""
import sys
import time
from pathlib import Path

import xa11y

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import activate_app  # noqa: E402
from lib.login import is_logged_in  # noqa: E402
from pages import ScribePage  # noqa: E402

REPORTS = Path(__file__).resolve().parent.parent / "reports"


def main() -> None:
    app = xa11y.App.by_name("Heidi", timeout=10.0)
    activate_app("Heidi")
    time.sleep(1.5)
    if not is_logged_in(app):
        print("NOT logged in — aborting.")
        sys.exit(1)

    rec = ScribePage(app)
    rec.open()
    time.sleep(1.0)
    # Make sure we're in a session (New session if needed).
    if not app.locator("button[name*='transcription mode menu']").exists():
        rec.new_session()
        time.sleep(1.5)

    print("Expanding the mode menu...")
    ok = rec._open_mode_menu()
    print(f"  _open_mode_menu returned: {ok}")
    time.sleep(0.5)

    # Dump full tree.
    REPORTS.mkdir(exist_ok=True)
    tree = app.dump(max_depth=20)
    (REPORTS / "mode_menu.txt").write_text(tree, encoding="utf-8")
    print(f"  saved reports/mode_menu.txt ({len(tree)} chars)")

    # List every candidate with role + name/value, so the menu item is obvious.
    print("\n--- ALL elements (role: name / value) ---")
    lines = []
    for role in ["menu_item", "list_item", "button", "static_text", "menu",
                 "group", "cell", "link", "radio_button"]:
        try:
            els = app.locator(role).elements()
        except Exception:
            continue
        for el in els:
            name = (getattr(el, "name", "") or "").strip()
            value = (getattr(el, "value", "") or "").strip()
            if not name and not value:
                continue
            line = f"  {role}: name={name!r} value={value[:40]!r}"
            if "upload" in (name + value).lower() or "dictate" in (name + value).lower():
                line += "   <<< MENU ITEM?"
            lines.append(line)
    out = "\n".join(lines)
    print(out)
    (REPORTS / "mode_menu_candidates.txt").write_text(out, encoding="utf-8")
    print("\nsaved reports/mode_menu_candidates.txt")
    print("\nDONE. Paste reports/mode_menu_candidates.txt back.")


if __name__ == "__main__":
    main()
