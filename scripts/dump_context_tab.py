"""Dump the Context tab to find the paperclip file-upload button's AX node.

The context uploader is an icon-only button (Paperclip, testid
'context-file-upload-button'); its AX name is unknown. Run this on a session
with the Context tab available, to see what role/name it carries.

RUN FROM GHOSTTY, Heidi frontmost, in a session:
    .venv/bin/python scripts/dump_context_tab.py
Paste the console output (especially the button list) back.
"""
import sys
import time
from pathlib import Path

import xa11y

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import activate_app  # noqa: E402
from pages import ScribePage  # noqa: E402

REPORTS = Path(__file__).resolve().parent.parent / "reports"


def main() -> None:
    app = xa11y.App.by_name("Heidi", timeout=10.0)
    activate_app("Heidi")
    time.sleep(2.0)

    rec = ScribePage(app)
    rec.open_context_tab()
    time.sleep(1.5)

    REPORTS.mkdir(exist_ok=True)
    tree = app.dump(max_depth=25)
    (REPORTS / "context_tab.txt").write_text(tree, encoding="utf-8")
    print(f"saved reports/context_tab.txt ({len(tree)} chars)")

    print("\n=== ALL buttons (name) ===")
    lines = []
    for role in ["button", "text_area", "text_field", "combo_box", "image"]:
        try:
            els = app.locator(role).elements()
        except Exception:
            continue
        for el in els:
            name = (getattr(el, "name", "") or "").strip()
            value = (getattr(el, "value", "") or "").strip()
            desc = (getattr(el, "description", "") or "").strip()
            if not (name or value or desc):
                # icon-only buttons may have NO name — still list them with role
                if role == "button":
                    lines.append(f"  {role}: <no name> desc={desc!r}")
                continue
            lines.append(f"  {role}: name={name!r} value={value[:30]!r} desc={desc!r}")
    out = "\n".join(lines)
    print(out)
    (REPORTS / "context_tab_buttons.txt").write_text(out, encoding="utf-8")
    print("\nsaved reports/context_tab_buttons.txt")
    print("Look for the Paperclip / attach / upload button (may have no name).")


if __name__ == "__main__":
    main()
