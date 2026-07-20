"""Shared fixtures for Heidi desktop E2E tests.

IMPORTANT: These tests must run from a terminal that has macOS
"Screen & System Audio Recording" permission (e.g. Ghostty).
Running from Hermes's embedded terminal won't work — the child
process doesn't inherit the permission on macOS 26.
"""
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
import xa11y


def _load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE lines without overriding the caller's env."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file(Path(__file__).resolve().parent / ".env.e2e")

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
        # -f matches against the full argv; pass the pattern as a FIXED string
        # (grep -F semantics via pgrep's -F is not portable, so escape instead)
        # macOS pgrep treats the pattern as an extended regex — a bundle name
        # like "Heidi(Staging)" would have its parens interpreted as a regex
        # group and never match the literal path. re.escape() neutralises that.
        out = subprocess.run(
            ["pgrep", "-f", re.escape(exe_match)],
            capture_output=True, text=True, timeout=5,
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

    # 4. DEFAULT (portable): launch by name, attach by name. Cross-platform:
    #    macOS uses `open -a`, Windows uses Start-Process (see lib.launch_app).
    #    Pass HEIDI_APP_PATH through if set so `open -a` targets the exact
    #    bundle — a bare name can resolve to the wrong same-named "Heidi"
    #    (Parallels Windows wrapper, DMG volume, Xcode iOS build).
    try:
        app = xa11y.App.by_name(APP_NAME, timeout=3.0)
    except (xa11y.TimeoutError, xa11y.SelectorNotMatchedError):
        # Not running — launch it, then attach by name.
        from lib import launch_app
        launch_app(APP_NAME, app_path=HEIDI_APP_PATH)
        try:
            app = xa11y.App.by_name(APP_NAME, timeout=STARTUP_TIMEOUT)
        except (xa11y.TimeoutError, xa11y.SelectorNotMatchedError):
            raise RuntimeError(
                f"Could not launch/attach {APP_NAME!r}. Is Heidi installed and "
                f"(ideally) already running? Set HEIDI_APP_PATH to an explicit "
                f".app (macOS), or HEIDI_APP_NAME to match the app/window name."
            )
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


def pytest_configure(config):
    """Pin ONE timestamped run directory for this whole pytest session.

    Artifacts (videos + failure screenshots) are grouped as:
        reports/artifacts/<RUN_TS>/<test-file>/<artifact>
    one folder per run, one sub-folder per test case (module). Shared via an
    env var so module-scoped recorders in feature conftests use the same dir.
    """
    if not os.environ.get("HEIDI_E2E_RUN_DIR"):
        ts = time.strftime("%Y-%m-%d_%H-%M-%S")
        os.environ["HEIDI_E2E_RUN_DIR"] = str(ARTIFACTS / ts)


def _run_dir() -> Path:
    d = os.environ.get("HEIDI_E2E_RUN_DIR")
    return Path(d) if d else ARTIFACTS


def _safe_name(nodeid: str) -> str:
    """Turn a pytest nodeid into a filesystem-safe stem."""
    return (
        nodeid.replace("::", "__")
        .replace("/", "_")
        .replace("[", "_")
        .replace("]", "")
        .replace(" ", "_")
    )


def _case_dir(nodeid: str) -> Path:
    """Per-test-case artifact folder: <RUN_TS>/<test-file-stem>/ (created)."""
    path_part = nodeid.split("::")[0]           # tests/scribe/test_tcd004_x.py
    stem = Path(path_part).stem                 # test_tcd004_x
    d = _run_dir() / stem
    d.mkdir(parents=True, exist_ok=True)
    return d


def _test_label(nodeid: str) -> str:
    """The test-function portion of a nodeid, safe for a filename."""
    parts = nodeid.split("::")
    label = "__".join(parts[1:]) if len(parts) > 1 else parts[0]
    return _safe_name(label)


def _start_screencapture(video_path: Path):
    """Backward-compat wrapper — see lib.recording.start_screencapture."""
    from lib.recording import start_screencapture
    return start_screencapture(video_path)


def _stop_screencapture(proc) -> None:
    """Backward-compat wrapper — see lib.recording.stop_screencapture."""
    from lib.recording import stop_screencapture
    stop_screencapture(proc)


@pytest.fixture(autouse=True)
def record_test(request):
    """Record a screen video of each test via macOS `screencapture -v`.

    - One .mp4 per test under reports/artifacts/<RUN_TS>/<test-file>/.
    - screencapture is built into macOS (no ffmpeg needed).
    - Requires Screen Recording permission (already needed for xa11y).
    - Set RECORD_VIDEO=0 to disable.
    - Tests marked `flow_video` are SKIPPED here: their real work happens in a
      module-scoped fixture (run-once, assert-many), so per-test recording would
      only capture the ~1s assertion. Those suites record at the MODULE level
      instead (see the feature conftest's module-scoped recorder).
    """
    if not RECORD_VIDEO or sys.platform != "darwin":
        yield
        return
    if request.node.get_closest_marker("flow_video"):
        yield
        return

    nodeid = request.node.nodeid
    video_path = _case_dir(nodeid) / f"{_test_label(nodeid)}.mp4"
    proc = _start_screencapture(video_path)
    try:
        yield
    finally:
        _stop_screencapture(proc)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """On failure, capture a screenshot via xa11y (official-recommended pattern)."""
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        png = _case_dir(item.nodeid) / f"{_test_label(item.nodeid)}__FAIL.png"
        try:
            xa11y.screenshot().save_png(str(png))
        except Exception:
            pass  # capture failure must not mask the test failure
