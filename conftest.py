"""Shared fixtures for Heidi desktop E2E tests.

IMPORTANT: These tests must run from a terminal that has macOS
"Screen & System Audio Recording" permission (e.g. Ghostty).
Running from Hermes's embedded terminal won't work — the child
process doesn't inherit the permission on macOS 26.
"""
import json
import os
import signal
import shutil
import subprocess
import time
from pathlib import Path

import pytest
import xa11y

# ---------------------------------------------------------------------------
# Config — how to find / launch the Heidi app
# ---------------------------------------------------------------------------
# DEFAULT (portable, zero-config):
#   - macOS: launch with `open -a Heidi` and attach with App.by_name("Heidi").
#   - Windows: find Heidi.exe in common install locations, launch it, then
#     attach to the process that owns the main window.
#
# OPTIONAL overrides (env vars), in priority order:
#   HEIDI_PID=1234         attach to one exact running process (most explicit)
#   HEIDI_DEV=1            attach to the `pnpm tauri:dev` debug binary
#                          (attach-only; you start it yourself). Path comes from
#                          SCRIBE_FE_PATH (default ~/Desktop/heidi/scribe-fe-v2).
#   HEIDI_APP_PATH=/x.app  launch that specific .app bundle or .exe by path.
#   HEIDI_EXE_PATH=C:\x\Heidi.exe
#                          Windows alias for HEIDI_APP_PATH.
#                          Use these when you have MULTIPLE same-named Heidi
#                          builds on one machine and need to disambiguate.
#   HEIDI_APP_NAME=Heidi   the AX/app name used for `open -a` and by_name.
#
# Most people set NOTHING and the default just works.
IS_WINDOWS = os.name == "nt"
APP_NAME = os.environ.get("HEIDI_APP_NAME", "Heidi")
HEIDI_PID = os.environ.get("HEIDI_PID")
HEIDI_DEV = os.environ.get("HEIDI_DEV") == "1"
HEIDI_APP_PATH = os.environ.get("HEIDI_APP_PATH") or os.environ.get("HEIDI_EXE_PATH")
SCRIBE_FE = os.environ.get(
    "SCRIBE_FE_PATH", str(Path.home() / "Desktop" / "heidi" / "scribe-fe-v2")
)
_DEV_BIN_NAME = "app.exe" if IS_WINDOWS else "app"
DEV_BIN = os.environ.get(
    "HEIDI_DEV_BIN",
    str(Path(SCRIBE_FE) / "src-tauri" / "target" / "debug" / _DEV_BIN_NAME),
)

STARTUP_TIMEOUT = float(os.environ.get("HEIDI_STARTUP_TIMEOUT", "30"))
DEFAULT_TIMEOUT = float(os.environ.get("XA11Y_DEFAULT_TIMEOUT", "10"))

# Raise xa11y's global timeout so CI/slow machines don't flake
xa11y.set_default_timeout(DEFAULT_TIMEOUT)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _pid_for_exe(exe_match: str) -> int | None:
    """Return the PID of the MAIN process whose executable path contains
    `exe_match`, or None. Filters out helper subprocesses (crash reporter,
    GPU/renderer helpers) that share the path but carry extra CLI args.
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
        if "--" not in cmd and "--type=" not in cmd:
            candidates.append(pid)

    if candidates:
        return min(candidates)
    pids = [int(p) for p in out.split() if p.strip().isdigit()]
    return min(pids) if pids else None


def _windows_ps(script: str, extra_env: dict[str, str] | None = None) -> list[str]:
    """Run a tiny PowerShell query and return non-empty output lines."""
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    try:
        out = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=8,
            env=env,
        ).stdout
    except Exception:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _windows_main_pid_for_exe(exe_path: str) -> int | None:
    """Return the running process PID for this exe that owns a main window."""
    script = r"""
    $target = [System.IO.Path]::GetFullPath($env:HEIDI_EXE_PATH).ToLowerInvariant()
    Get-Process -ErrorAction SilentlyContinue |
      Where-Object {
        $_.Path -and
        ([System.IO.Path]::GetFullPath($_.Path).ToLowerInvariant() -eq $target) -and
        $_.MainWindowHandle -ne 0
      } |
      Sort-Object Id |
      Select-Object -First 1 -ExpandProperty Id
    """
    for line in _windows_ps(script, {"HEIDI_EXE_PATH": str(Path(exe_path))}):
        if line.isdigit():
            return int(line)
    return None


def _windows_main_pid_for_name(process_name: str) -> int | None:
    """Return the PID for a running app by process name, excluding helpers."""
    name = Path(process_name).stem
    script = r"""
    Get-Process -Name $env:HEIDI_PROCESS_NAME -ErrorAction SilentlyContinue |
      Where-Object { $_.MainWindowHandle -ne 0 } |
      Sort-Object Id |
      Select-Object -First 1 -ExpandProperty Id
    """
    for line in _windows_ps(script, {"HEIDI_PROCESS_NAME": name}):
        if line.isdigit():
            return int(line)
    return None


def _windows_find_heidi_exe() -> str | None:
    """Find a standard Heidi Windows install without hard-coding one machine."""
    if HEIDI_APP_PATH:
        path = Path(HEIDI_APP_PATH).expanduser()
        if not path.exists() or not path.is_file():
            raise RuntimeError(
                f"Configured Heidi path does not exist: {path}. "
                "Set HEIDI_APP_PATH or HEIDI_EXE_PATH to the full Heidi.exe path."
            )
        return str(path)

    exe_names = []
    app_stem = Path(APP_NAME).stem
    if app_stem:
        exe_names.append(f"{app_stem}.exe")
    if "Heidi.exe" not in exe_names:
        exe_names.append("Heidi.exe")

    roots = [
        os.environ.get("LOCALAPPDATA"),
        str(Path(os.environ["LOCALAPPDATA"]) / "Programs")
        if os.environ.get("LOCALAPPDATA")
        else None,
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
    ]
    candidates: list[Path] = []
    for root in [Path(r) for r in roots if r]:
        for exe_name in exe_names:
            stem = Path(exe_name).stem
            candidates.extend(
                [
                    root / stem / exe_name,
                    root / "Heidi" / exe_name,
                ]
            )

    for exe_name in exe_names:
        found = shutil.which(exe_name)
        if found:
            candidates.append(Path(found))

    for path in candidates:
        if path.exists() and path.is_file():
            return str(path)
    return None


def _windows_launch_or_attach() -> xa11y.App:
    """Launch/attach Heidi on Windows and return an App handle."""
    if HEIDI_DEV:
        pid = _windows_main_pid_for_exe(DEV_BIN)
        if pid is None:
            raise RuntimeError(
                f"HEIDI_DEV=1 but no windowed process matched {DEV_BIN!r}. "
                f"Start it first:\n  cd {SCRIBE_FE} && pnpm tauri:dev"
            )
        return _attach_ready(xa11y.App.by_pid(pid, timeout=STARTUP_TIMEOUT))

    app_path = _windows_find_heidi_exe()
    if app_path:
        pid = _windows_main_pid_for_exe(app_path)
        if pid is None:
            subprocess.Popen(
                [app_path],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            deadline = time.time() + STARTUP_TIMEOUT
            while time.time() < deadline and pid is None:
                time.sleep(1)
                pid = _windows_main_pid_for_exe(app_path)
        if pid is None:
            raise RuntimeError(
                f"Launched {app_path!r} but no main Heidi window appeared within "
                f"{STARTUP_TIMEOUT}s"
            )
        return _attach_ready(xa11y.App.by_pid(pid, timeout=STARTUP_TIMEOUT))

    pid = _windows_main_pid_for_name(APP_NAME)
    if pid is None:
        raise RuntimeError(
            "Could not find Heidi on Windows. Install Heidi in the default "
            "location, add Heidi.exe to PATH, or set HEIDI_APP_PATH/"
            "HEIDI_EXE_PATH to the full Heidi.exe path."
        )
    return _attach_ready(xa11y.App.by_pid(pid, timeout=STARTUP_TIMEOUT))


def _attach_ready(app: xa11y.App) -> xa11y.App:
    """Wait until the web_area is rendered, then return the app."""
    app.locator("web_area").wait_visible(timeout=STARTUP_TIMEOUT)
    return app


@pytest.fixture(scope="session")
def heidi_app() -> xa11y.App:
    """Return an xa11y App handle for Heidi.

    Default behaviour is fully portable: `open -a Heidi` to launch (if needed),
    then attach by name. Override via env vars for special cases — see the
    Config block above.
    """
    # 1. Explicit PID — attach to exactly that process.
    if HEIDI_PID:
        return _attach_ready(xa11y.App.by_pid(int(HEIDI_PID), timeout=STARTUP_TIMEOUT))

    if IS_WINDOWS:
        return _windows_launch_or_attach()

    # 2. Dev binary (pnpm tauri:dev) — attach only, never launched here.
    if HEIDI_DEV:
        pid = _pid_for_exe(DEV_BIN)
        if pid is None:
            raise RuntimeError(
                f"HEIDI_DEV=1 but no process matched {DEV_BIN!r}. Start it first:\n"
                f"  cd {SCRIBE_FE} && pnpm tauri:dev"
            )
        return _attach_ready(xa11y.App.by_pid(pid, timeout=STARTUP_TIMEOUT))

    # 3. Explicit .app path — launch THAT bundle, attach by its PID. For
    #    disambiguating multiple same-named builds on one machine.
    if HEIDI_APP_PATH:
        exe_match = str(Path(HEIDI_APP_PATH) / "Contents" / "MacOS")
        pid = _pid_for_exe(exe_match)
        if pid is None:
            subprocess.Popen(["open", "-a", HEIDI_APP_PATH])
            deadline = time.time() + STARTUP_TIMEOUT
            while time.time() < deadline and pid is None:
                time.sleep(1)
                pid = _pid_for_exe(exe_match)
            if pid is None:
                raise RuntimeError(
                    f"Launched {HEIDI_APP_PATH} but no process appeared within "
                    f"{STARTUP_TIMEOUT}s"
                )
        return _attach_ready(xa11y.App.by_pid(pid, timeout=STARTUP_TIMEOUT))

    # 4. DEFAULT (portable): launch by name via LaunchServices, attach by name.
    try:
        app = xa11y.App.by_name(APP_NAME, timeout=3.0)
    except (xa11y.TimeoutError, xa11y.SelectorNotMatchedError):
        # Not running — `open -a` resolves the app wherever it's installed.
        result = subprocess.run(
            ["open", "-a", APP_NAME], capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Could not launch {APP_NAME!r} with `open -a` "
                f"({result.stderr.strip()}). Is it installed? "
                f"Set HEIDI_APP_PATH to an explicit .app, or HEIDI_APP_NAME."
            )
        app = xa11y.App.by_name(APP_NAME, timeout=STARTUP_TIMEOUT)
    return _attach_ready(app)


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
        path.write_text(heidi_app.dump(max_depth=max_depth), encoding="utf-8")
        return path

    return _dump


# ---------------------------------------------------------------------------
# Recording & screenshots
# ---------------------------------------------------------------------------
ARTIFACTS = Path(__file__).resolve().parent / "reports" / "artifacts"

# Toggle recording with RECORD_VIDEO=0 to skip (faster local runs).
_DEFAULT_RECORD_VIDEO = "0" if IS_WINDOWS else "1"
RECORD_VIDEO = os.environ.get("RECORD_VIDEO", _DEFAULT_RECORD_VIDEO) != "0"


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
