"""Shared fixtures for Heidi desktop E2E tests.

IMPORTANT: These tests must run from a terminal that has macOS
"Screen & System Audio Recording" permission (e.g. Ghostty).
Running from Hermes's embedded terminal won't work — the child
process doesn't inherit the permission on macOS 26.
"""
import json
import os
import subprocess
import time
from pathlib import Path

import pytest
import xa11y

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
APP_NAME = os.environ.get("HEIDI_APP_NAME", "Heidi")
APP_PATH = os.environ.get("HEIDI_APP_PATH", "/Applications/Heidi.app")
STARTUP_TIMEOUT = float(os.environ.get("HEIDI_STARTUP_TIMEOUT", "30"))
DEFAULT_TIMEOUT = float(os.environ.get("XA11Y_DEFAULT_TIMEOUT", "10"))

# Raise xa11y's global timeout so CI/slow machines don't flake
xa11y.set_default_timeout(DEFAULT_TIMEOUT)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def heidi_app() -> xa11y.App:
    """Return an xa11y App handle for Heidi, launching it if needed."""
    try:
        app = xa11y.App.by_name(APP_NAME, timeout=3.0)
    except xa11y.TimeoutError:
        subprocess.Popen(["open", "-a", APP_PATH])
        app = xa11y.App.by_name(APP_NAME, timeout=STARTUP_TIMEOUT)

    # Wait until the web_area inside the window is rendered
    app.locator("web_area").wait_visible(timeout=STARTUP_TIMEOUT)
    return app


@pytest.fixture(autouse=True)
def _ensure_app_alive(heidi_app: xa11y.App):
    """Sanity-check before every test that the app is still there."""
    assert heidi_app.pid is not None


@pytest.fixture()
def dump_tree(heidi_app: xa11y.App):
    """Helper: returns a callable that dumps the current AX tree to a file.

    Usage inside a test:
        dump_tree("after_click_devices")   # saved to reports/after_click_devices.txt
    """
    reports = Path(__file__).resolve().parent.parent / "reports"
    reports.mkdir(exist_ok=True)

    def _dump(label: str, max_depth: int = 12):
        path = reports / f"{label}.txt"
        path.write_text(heidi_app.dump(max_depth=max_depth))
        return path

    return _dump
