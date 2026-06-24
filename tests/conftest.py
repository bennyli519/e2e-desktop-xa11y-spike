"""Shared fixtures for Heidi desktop E2E tests.

IMPORTANT: These tests must run from a terminal that has macOS
"Screen & System Audio Recording" permission (e.g. Ghostty).
Running from Hermes's embedded terminal won't work — the child
process doesn't inherit the permission on macOS 26.
"""
import json
import os
import signal
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


# ---------------------------------------------------------------------------
# Recording & screenshots
# ---------------------------------------------------------------------------
ARTIFACTS = Path(__file__).resolve().parent.parent / "reports" / "artifacts"

# Toggle recording with RECORD_VIDEO=0 to skip (faster local runs).
RECORD_VIDEO = os.environ.get("RECORD_VIDEO", "1") != "0"


def _safe_name(nodeid: str) -> str:
    """Turn a pytest nodeid into a filesystem-safe stem."""
    return (
        nodeid.replace("::", "__")
        .replace("/", "_")
        .replace("[", "_")
        .replace("]", "")
        .replace(" ", "_")
    )


@pytest.fixture(autouse=True)
def record_test(request):
    """Record a screen video of each test via macOS `screencapture -v`.

    - One .mp4 per test under reports/artifacts/.
    - screencapture is built into macOS (no ffmpeg needed).
    - Requires Screen Recording permission (already needed for xa11y).
    - Set RECORD_VIDEO=0 to disable.
    """
    if not RECORD_VIDEO:
        yield
        return

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    stem = _safe_name(request.node.nodeid)
    video_path = ARTIFACTS / f"{stem}.mp4"

    # -v: video, -x: no sound, -C: capture cursor. Records the full screen.
    # NOTE: screencapture -v only writes the file when stopped via SIGINT
    # (Ctrl-C). Sending newline to stdin does NOT save it — must signal.
    if video_path.exists():
        video_path.unlink()
    proc = subprocess.Popen(
        ["screencapture", "-v", "-x", "-C", str(video_path)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.0)  # let the recorder spin up

    try:
        yield
    finally:
        # Stop with SIGINT so screencapture flushes and writes the .mp4.
        try:
            proc.send_signal(signal.SIGINT)
            proc.wait(timeout=15)
        except Exception:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """On failure, capture a screenshot via xa11y (official-recommended pattern)."""
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        stem = _safe_name(item.nodeid)
        try:
            xa11y.screenshot().save_png(str(ARTIFACTS / f"{stem}__FAIL.png"))
        except Exception:
            pass  # capture failure must not mask the test failure
