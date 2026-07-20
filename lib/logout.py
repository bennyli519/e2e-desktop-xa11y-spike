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

import os
import re
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


def _configured_app_names() -> list[str]:
    """App bundle names to quit/relaunch, most-specific first.

    Honours HEIDI_APP_NAME (set by env/prod.env, env/staging.env, or the CLI)
    so logout targets the build actually under test, then falls back to the
    known family names so a bare run still works.
    """
    configured = os.environ.get("HEIDI_APP_NAME")
    names = [configured] if configured else []
    for fallback in ("Heidi(Staging)", "Heidi"):
        if fallback not in names:
            names.append(fallback)
    return names


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
    """PIDs of any running configured/known Heidi build.

    Matches the configured build first (HEIDI_APP_NAME / HEIDI_APP_PATH), then
    the known family names. pgrep -f treats the pattern as a regex, so bundle
    names with parens (e.g. "Heidi(Staging)") must be re.escape()'d or the
    literal path never matches.
    """
    patterns: list[str] = []
    app_path = os.environ.get("HEIDI_APP_PATH")
    if app_path:
        patterns.append(str(Path(app_path) / "Contents" / "MacOS"))
    for name in _configured_app_names():
        patterns.append(f"{name}.app/Contents/MacOS")

    pids: list[int] = []
    for pat in patterns:
        try:
            out = subprocess.run(
                ["pgrep", "-f", re.escape(pat)],
                capture_output=True, text=True, timeout=5,
            ).stdout
        except Exception:
            continue
        for p in out.split():
            if p.strip().isdigit() and int(p) not in pids:
                pids.append(int(p))
    return pids


def relaunch_app(app_name: str | None = None) -> None:
    """Quit Heidi (best-effort) and relaunch it via `open -a`."""
    names = [app_name] if app_name else _configured_app_names()
    # Ask the app to quit gracefully first.
    for n in names:
        subprocess.run(["osascript", "-e", f'tell application "{n}" to quit'],
                       capture_output=True)
    time.sleep(3.0)
    # Prefer an explicit bundle path if one is configured.
    app_path = os.environ.get("HEIDI_APP_PATH")
    if not app_name and app_path and Path(app_path).exists():
        subprocess.run(["open", "-a", app_path], capture_output=True)
        return
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
