"""Sign-out helpers for Heidi desktop E2E.

The account menu (bottom-left email combo_box → Team/Settings/Log out) is a
React portal popover that is INVISIBLE to the accessibility tree — pressing the
combo_box via AX doesn't open it, and even a real mouse click produces no AX
nodes for the menu (verified 2026-07-09, reports/logout_menu_v3.txt). So we
cannot drive Log out through the UI yet (until scribe-fe-v2 adds aria-labels /
exposes the menu — branch test/xa11y-aria-labels).

The robust, portable alternative is to clear the persisted Auth0 token and
relaunch the app. Staging/dev builds persist the refresh token to
`dev-auth-cache.json` under the app's Application Support dir; deleting it +
relaunching brings the app back to the login screen. This mirrors what
`dispatch.auth.logout()` does (clears the token) without touching the UI.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

_APP_SUPPORT = Path.home() / "Library" / "Application Support"

# Bundle-id dirs that may hold a dev-auth-cache.json, in priority order.
# staging first (the spike's default build), then plain dev.
_TOKEN_CACHE_DIRS = [
    "com.Heidi.dev.staging",
    "com.Heidi.dev",
]
_TOKEN_CACHE_NAME = "dev-auth-cache.json"

# App bundle names to relaunch after clearing the token, in priority order.
_APP_NAMES = ["Heidi(Staging)", "Heidi"]


def find_token_caches() -> list[Path]:
    """Return existing dev-auth-cache.json paths (staging + dev)."""
    found = []
    for d in _TOKEN_CACHE_DIRS:
        p = _APP_SUPPORT / d / _TOKEN_CACHE_NAME
        if p.exists():
            found.append(p)
    return found


def clear_token_caches() -> list[Path]:
    """Delete every dev-auth-cache.json found. Returns the paths removed."""
    removed = []
    for p in find_token_caches():
        try:
            p.unlink()
            removed.append(p)
        except Exception:
            pass
    return removed


def _running_heidi_pids() -> list[int]:
    try:
        out = subprocess.run(
            ["pgrep", "-f", "Heidi(Staging).app/Contents/MacOS"],
            capture_output=True, text=True, timeout=5,
        ).stdout
    except Exception:
        return []
    return [int(p) for p in out.split() if p.strip().isdigit()]


def relaunch_app(app_name: str | None = None) -> None:
    """Quit Heidi (best-effort) and relaunch it via `open -a`."""
    names = [app_name] if app_name else _APP_NAMES
    # Ask the app to quit gracefully first.
    for n in names:
        subprocess.run(["osascript", "-e", f'tell application "{n}" to quit'],
                       capture_output=True)
    time.sleep(3.0)
    # Relaunch the first name that exists as an app bundle.
    for n in names:
        if (Path("/Applications") / f"{n}.app").exists():
            subprocess.run(["open", "-a", n], capture_output=True)
            return
    # Fall back to the first name regardless.
    subprocess.run(["open", "-a", names[0]], capture_output=True)


def force_logout_via_token(app_name: str | None = None) -> bool:
    """Clear the persisted Auth0 token and relaunch so the app is logged out.

    Returns True if at least one token cache was removed (i.e. we expect the
    relaunched app to show the login screen). The caller should re-attach to
    the app and wait for the login field.
    """
    removed = clear_token_caches()
    relaunch_app(app_name)
    return bool(removed)
