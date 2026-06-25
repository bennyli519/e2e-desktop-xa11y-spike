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
# You may have MULTIPLE Heidi builds (prod / staging / installed / dev) that all
# share the same bundle id (com.Heidi.dev) and AX name ("Heidi"). by_name alone
# can't tell them apart, so we select a build by ENV and attach to the matching
# process by PID (matched on its executable path).
#
# Pick the build with HEIDI_ENV. Two kinds of entry:
#   - "path": an installed .app bundle  -> launched with `open -a` if not running
#   - "dev_bin": the `pnpm tauri:dev` debug binary -> attach only, NEVER launched
#     (you start it yourself with `pnpm tauri:dev`; tests just connect to it)
#
# Override the resolved path with HEIDI_APP_PATH, or pin a process with HEIDI_PID.
SCRIBE_FE = os.environ.get(
    "SCRIBE_FE_PATH", str(Path.home() / "Desktop" / "heidi" / "scribe-fe-v2")
)

APP_ENVS: dict[str, dict] = {
    "default": {"path": "/Applications/Heidi.app"},
    "prod": {"path": "/Applications/Heidi Prod 2.2.0.app"},
    "v2": {"path": "/Applications/Heidi 2.app"},
    # dev = `pnpm tauri:dev` debug binary. Attach-only: start it yourself first.
    "dev": {"dev_bin": f"{SCRIBE_FE}/src-tauri/target/debug/app"},
    # add your own: "staging": {"path": "/Applications/Heidi(Staging).app"},
}

HEIDI_ENV = os.environ.get("HEIDI_ENV", "default")
_env_cfg = APP_ENVS.get(HEIDI_ENV, APP_ENVS["default"])

# Resolved targets. APP_PATH = installed .app (launchable). DEV_BIN = debug exe
# (attach-only). HEIDI_APP_PATH overrides whichever applies.
APP_PATH = os.environ.get("HEIDI_APP_PATH") or _env_cfg.get("path")
DEV_BIN = os.environ.get("HEIDI_DEV_BIN") or _env_cfg.get("dev_bin")

APP_NAME = os.environ.get("HEIDI_APP_NAME", "Heidi")
HEIDI_PID = os.environ.get("HEIDI_PID")  # attach to a specific running process
STARTUP_TIMEOUT = float(os.environ.get("HEIDI_STARTUP_TIMEOUT", "30"))
DEFAULT_TIMEOUT = float(os.environ.get("XA11Y_DEFAULT_TIMEOUT", "10"))

# Raise xa11y's global timeout so CI/slow machines don't flake
xa11y.set_default_timeout(DEFAULT_TIMEOUT)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _pid_for_exe(exe_match: str) -> int | None:
    """Return the PID of the MAIN process whose executable path contains
    `exe_match`, or None.

    Matches on the executable path so we connect to the SPECIFIC build, not
    whichever same-named Heidi happens to be running. Filters out helper
    subprocesses (crash reporter, GPU/renderer helpers) which share the path
    but carry extra CLI args — we want the bare-executable main process.
    """
    try:
        out = subprocess.run(
            ["pgrep", "-f", exe_match], capture_output=True, text=True, timeout=5
        ).stdout
    except Exception:
        return None

    candidates: list[int] = []
    for pid_str in out.split():
        if not pid_str.strip().isdigit():
            continue
        pid = int(pid_str)
        try:
            cmd = subprocess.run(
                ["ps", "-p", str(pid), "-o", "command="],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
        except Exception:
            continue
        # Main process runs the bare executable; helpers carry --type=, etc.
        if "--" not in cmd and "--type=" not in cmd:
            candidates.append(pid)

    if candidates:
        return min(candidates)
    pids = [int(p) for p in out.split() if p.strip().isdigit()]
    return min(pids) if pids else None


@pytest.fixture(scope="session")
def heidi_app() -> xa11y.App:
    """Return an xa11y App handle for the selected Heidi build.

    Resolution order:
      1. HEIDI_PID env var -> attach to that exact process.
      2. HEIDI_ENV=dev (or any dev_bin entry) -> attach to the running
         `pnpm tauri:dev` debug binary. ATTACH-ONLY: it is never launched here;
         start it yourself first. Fails with a clear message if not running.
      3. An installed .app (path entry): attach to it if running, else launch
         it with `open -a` and attach to the new PID.

    Attaching by PID (matched on the executable path) is what lets multiple
    identically-named Heidi builds coexist without grabbing the wrong one.
    """
    # 1. Explicit PID override
    if HEIDI_PID:
        app = xa11y.App.by_pid(int(HEIDI_PID), timeout=STARTUP_TIMEOUT)
        app.locator("web_area").wait_visible(timeout=STARTUP_TIMEOUT)
        return app

    # 2. dev binary (pnpm tauri:dev) — attach only, never launch
    if DEV_BIN:
        pid = _pid_for_exe(DEV_BIN)
        if pid is None:
            raise RuntimeError(
                f"HEIDI_ENV={HEIDI_ENV} expects the dev build running, but no "
                f"process matched {DEV_BIN!r}. Start it first:\n"
                f"  cd {SCRIBE_FE} && pnpm tauri:dev\n"
                f"(or set HEIDI_PID to the running dev process)."
            )
        app = xa11y.App.by_pid(pid, timeout=STARTUP_TIMEOUT)
        app.locator("web_area").wait_visible(timeout=STARTUP_TIMEOUT)
        return app

    # 3. Installed .app — attach if running, else launch it
    if not APP_PATH:
        raise RuntimeError(
            f"No target resolved for HEIDI_ENV={HEIDI_ENV!r}. "
            f"Set a valid HEIDI_ENV ({', '.join(APP_ENVS)}), or HEIDI_APP_PATH."
        )
    exe_match = str(Path(APP_PATH) / "Contents" / "MacOS")
    pid = _pid_for_exe(exe_match)
    if pid is None:
        subprocess.Popen(["open", "-a", APP_PATH])
        deadline = time.time() + STARTUP_TIMEOUT
        while time.time() < deadline and pid is None:
            time.sleep(1)
            pid = _pid_for_exe(exe_match)
        if pid is None:
            raise RuntimeError(
                f"Launched {APP_PATH} but no process appeared within "
                f"{STARTUP_TIMEOUT}s (HEIDI_ENV={HEIDI_ENV})"
            )

    app = xa11y.App.by_pid(pid, timeout=STARTUP_TIMEOUT)
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
    reports = Path(__file__).resolve().parent / "reports"
    reports.mkdir(exist_ok=True)

    def _dump(label: str, max_depth: int = 12):
        path = reports / f"{label}.txt"
        path.write_text(heidi_app.dump(max_depth=max_depth))
        return path

    return _dump


# ---------------------------------------------------------------------------
# Recording & screenshots
# ---------------------------------------------------------------------------
ARTIFACTS = Path(__file__).resolve().parent / "reports" / "artifacts"

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
