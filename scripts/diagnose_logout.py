"""Diagnose the sign-out UI: dump the footer account button + the Log out menu.

Run from Ghostty (needs Screen Recording), Heidi logged in and foreground:

    cd ~/Desktop/heidi/e2e-desktop-xa11y-spike
    .venv/bin/python3.14 scripts/diagnose_logout.py

It prints:
  1. any element whose name/value contains '@' (the account button candidates)
  2. the full footer subtree
Then it PRESSES the best account-button candidate and dumps the tree again so
we can see the actual Log out menu item (role + exact name).
"""
import sys
import time

import xa11y

app = xa11y.App.by_name("Heidi", timeout=10)
print("=" * 70)
print("STEP 1 — elements whose name/value contains '@' (account button?)")
print("=" * 70)

# Walk the whole tree, print anything with '@' in name or value.
def walk(el, depth=0):
    try:
        name = el.name or ""
        val = getattr(el, "value", "") or ""
        role = el.role
    except Exception:
        return
    if "@" in name or "@" in val:
        print(f"  role={role!r} name={name!r} value={val!r}")
    try:
        for c in el.children():
            walk(c, depth + 1)
    except Exception:
        pass


root = app.as_element()
walk(root)

print()
print("=" * 70)
print("STEP 2 — full tree dump BEFORE opening the menu (last 120 lines)")
print("=" * 70)
tree_before = app.dump(max_depth=16)
print("\n".join(tree_before.splitlines()[-120:]))

# Try pressing the account button (name contains '@'), then dump again.
print()
print("=" * 70)
print("STEP 3 — press the account button, then dump the Log out menu")
print("=" * 70)
pressed = False
for sel in ["button[name*='@']", "static_text[value*='@']", "combo_box[name*='@']"]:
    try:
        loc = app.locator(sel)
        if loc.exists():
            print(f"pressing: {sel}")
            loc.press()
            pressed = True
            break
    except Exception as e:
        print(f"  {sel} -> {e!r}")

if not pressed:
    print("!! no '@' element was pressable — the account button uses a different"
          " role/name. Inspect STEP 1/2 output above.")
    sys.exit(0)

time.sleep(1.5)
tree_after = app.dump(max_depth=20)

# Write the full post-open tree to a file for inspection.
from pathlib import Path

out = Path(__file__).resolve().parent.parent / "reports" / "logout_menu_tree.txt"
out.parent.mkdir(exist_ok=True)
out.write_text(tree_after, encoding="utf-8")
print(f"full post-open tree written to: {out}")

# Print lines mentioning log out / settings / team so we see the menu items.
print("--- menu-ish lines (log out / logout / settings / team) ---")
for line in tree_after.splitlines():
    low = line.lower()
    if any(k in low for k in ("log out", "logout", "sign out", "settings", "team")):
        print(line)

# Enumerate EVERY actionable element with a non-empty name/value after opening.
print()
print("--- ALL actionable elements (button/link/menu_item) with a label ---")

def enum(el):
    try:
        role = el.role
        name = el.name or ""
        val = getattr(el, "value", "") or ""
    except Exception:
        return
    if role in ("button", "link", "menu_item", "menu_button") and (name or val):
        print(f"  {role!r} name={name!r} value={val!r}")
    try:
        for c in el.children():
            enum(c)
    except Exception:
        pass


enum(app.as_element())

