"""Diagnose v3: open the account menu with a REAL mouse click on its bounds.

press()/show_menu()/keyboard all failed to reveal 'Log out' in the AX tree.
React portal popovers often only respond to a real mouse click, not synthetic
AXPress. This clicks the account control's bounds centre, then dumps the tree
and reports whether the popup (Team/Settings/Log out) actually appeared.

Run from Ghostty (Screen Recording), Heidi logged in + FOREGROUND:
    cd ~/Desktop/heidi/e2e-desktop-xa11y-spike
    .venv/bin/python3.14 scripts/diagnose_logout_v3.py
"""
import subprocess
import time
from pathlib import Path

import xa11y

EMAIL_SEL = "combo_box[name*='@']"

# Make sure Heidi is frontmost so the click lands in the app, not the terminal.
subprocess.run(["osascript", "-e", 'tell application "Heidi" to activate'],
               capture_output=True)
time.sleep(1.0)

app = xa11y.App.by_name("Heidi", timeout=10)
loc = app.locator(EMAIL_SEL)
if not loc.exists():
    print("account combo_box not found")
    raise SystemExit(1)

el = loc.element()
b = el.bounds
print("account bounds:", b)

# bounds may be an object with x/y/width/height or a tuple — handle both.
def xywh(bounds):
    for attrs in (("x", "y", "width", "height"),):
        if all(hasattr(bounds, a) for a in attrs):
            return bounds.x, bounds.y, bounds.width, bounds.height
    if isinstance(bounds, (list, tuple)) and len(bounds) == 4:
        return bounds
    d = getattr(bounds, "__dict__", {})
    return d.get("x"), d.get("y"), d.get("width"), d.get("height")

x, y, w, h = xywh(b)
cx, cy = int(x + w / 2), int(y + h / 2)
print(f"clicking centre: ({cx}, {cy})")

sim = xa11y.input_sim()
sim.click((cx, cy))
time.sleep(1.5)

tree = app.dump(max_depth=24)
out = Path(__file__).resolve().parent.parent / "reports" / "logout_menu_v3.txt"
out.write_text(tree, encoding="utf-8")
print(f"tree after mouse click written to: {out}")

print("--- lines mentioning log out / team / settings ---")
for line in tree.splitlines():
    low = line.lower()
    if any(k in low for k in ("log out", "logout", "sign out", "team", "settings")):
        print(line)

found = any("log out" in l.lower() or "logout" in l.lower() for l in tree.splitlines())
print("=" * 60)
print(f"Log out present after mouse click: {found}")
if not found:
    print("Still not in the AX tree even with a real click. Conclusion: the "
          "Log out menu item is NOT exposed to accessibility (no role/name). "
          "Fix at source: add aria-label='Log out' in scribe-fe-v2 "
          "(branch test/xa11y-aria-labels).")
