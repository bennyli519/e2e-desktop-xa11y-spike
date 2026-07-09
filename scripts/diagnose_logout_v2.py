"""Diagnose HOW to open the account menu + reveal 'Log out'.

The account control is a combo_box (name contains the email). Plain .press()
did NOT open the popup (React ignores synthetic AXPress — same as the login
Continue button). This script tries several open strategies and reports which
one makes 'Log out' appear in the AX tree, plus that element's role/name.

Run from Ghostty (Screen Recording), Heidi logged in + foreground:
    cd ~/Desktop/heidi/e2e-desktop-xa11y-spike
    .venv/bin/python3.14 scripts/diagnose_logout_v2.py
"""
import time

import xa11y

EMAIL_SEL = "combo_box[name*='@']"


def app():
    return xa11y.App.by_name("Heidi", timeout=10)


def logout_in_tree(a) -> tuple[bool, str]:
    """Return (found, matching_line) for a 'Log out' element anywhere."""
    tree = a.dump(max_depth=22)
    for line in tree.splitlines():
        if "log out" in line.lower() or "logout" in line.lower():
            return True, line.strip()
    return False, ""


def account_el(a):
    loc = a.locator(EMAIL_SEL)
    if not loc.exists():
        return None
    return loc.element()


def close_menu():
    try:
        xa11y.input_sim().press("Escape")
    except Exception:
        pass
    time.sleep(0.6)


def try_strategy(name, fn):
    a = app()
    close_menu()
    el = account_el(a)
    if el is None:
        print(f"[{name}] account combo_box not found — skipping")
        return False
    try:
        fn(a, el)
    except Exception as e:
        print(f"[{name}] raised {e!r}")
        return False
    time.sleep(1.5)
    found, line = logout_in_tree(a)
    print(f"[{name}] Log out present: {found}" + (f"  -> {line}" if found else ""))
    return found


# First, report the account control's advertised actions.
a = app()
el = account_el(a)
if el is not None:
    try:
        print("account combo_box actions:", el.actions)
    except Exception as e:
        print("could not read actions:", repr(e))
    try:
        print("expanded?", el.expanded)
    except Exception:
        pass
print("=" * 66)

sim = xa11y.input_sim()

strategies = [
    ("press()", lambda a, el: el.press()),
    ("expand()", lambda a, el: el.expand()),
    ("show_menu()", lambda a, el: el.show_menu()),
    ("focus+Enter", lambda a, el: (el.focus(), time.sleep(0.3), sim.press("Enter"))),
    ("focus+Space", lambda a, el: (el.focus(), time.sleep(0.3), sim.press("Space"))),
    ("focus+Down", lambda a, el: (el.focus(), time.sleep(0.3), sim.press("Down"))),
]

winner = None
for name, fn in strategies:
    if try_strategy(name, fn):
        winner = name
        break

print("=" * 66)
if winner:
    print(f"WINNER: {winner} opens the account menu and reveals Log out.")
    # Dump the full menu tree for the winning strategy so we can read the exact
    # Log out role/name and any nesting.
    a = app()
    from pathlib import Path

    out = Path(__file__).resolve().parent.parent / "reports" / "logout_menu_v2.txt"
    out.write_text(a.dump(max_depth=22), encoding="utf-8")
    print(f"full tree for winner written to: {out}")
    print("--- actionable elements now visible ---")

    def enum(e):
        try:
            r, n, v = e.role, e.name or "", getattr(e, "value", "") or ""
        except Exception:
            return
        if r in ("button", "link", "menu_item", "menu_button", "static_text") and (
            "log out" in (n + v).lower()
        ):
            print(f"  {r!r} name={n!r} value={v!r}")
        try:
            for c in e.children():
                enum(c)
        except Exception:
            pass

    enum(a.as_element())
else:
    print("NO strategy revealed Log out. The menu may be a native NSMenu popup "
          "invisible to AX, or needs a real mouse click. Next: try "
          "input_sim().click() on the control's bounds, or inspect "
          "reports/logout_menu_tree.txt.")
