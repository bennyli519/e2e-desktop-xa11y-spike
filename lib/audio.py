"""Cross-platform audio injection for recording E2E tests.

The tests are platform-agnostic: same wav clips, same assertions. ONLY the way
audio reaches Heidi's mic differs per OS, and that difference is fully hidden
behind `AudioInjector` here:

- macOS: route the system default I/O to the **BlackHole 2ch** loopback device
  and `afplay` the clip. Heidi records the system default input, so NO in-app
  device selection is needed.
- Windows: play the clip into **VB-CABLE**'s "CABLE Input" via miniaudio
  (scripts/play_audio_to_device.py) and UI-select "CABLE Output" as Heidi's
  recording input. The system default devices are left untouched.

A test just does:

    inj = AudioInjector(heidi_app)
    if inj.prepare():          # picks the platform input, returns availability
        inj.play(clip, secs)   # starts playback for the recording window
    ...
    inj.cleanup()              # stops playback, restores devices

Requires (install once, see scripts/setup_audio.sh):
  - macOS:   BlackHole 2ch + SwitchAudioSource
  - Windows: VB-CABLE + `pip install -e .` (miniaudio)

On a machine without the virtual device, `prepare()` returns False and the
structural checks still run while content checks skip.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

from lib.platform_utils import IS_MAC, IS_WINDOWS

BLACKHOLE_NAME = "BlackHole 2ch"
# The device Heidi RECORDS from, per platform.
MAC_INPUT_DEVICE = os.environ.get("HEIDI_E2E_RECORDING_INPUT_DEVICE", BLACKHOLE_NAME)
WINDOWS_INPUT_DEVICE = os.environ.get(
    "HEIDI_E2E_RECORDING_INPUT_DEVICE", "CABLE Output"
)
# The device we PLAY the clip INTO on Windows (VB-CABLE's playback side).
WINDOWS_PLAYBACK_DEVICE = os.environ.get(
    "HEIDI_E2E_AUDIO_PLAYBACK_DEVICE", "CABLE Input"
)

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _switch_audio_path() -> str | None:
    try:
        out = subprocess.run(
            ["which", "SwitchAudioSource"], capture_output=True, text=True, timeout=5
        ).stdout.strip()
        return out or None
    except Exception:
        return None


def blackhole_available() -> bool:
    """True only if both SwitchAudioSource and the configured virtual device exist."""
    if _switch_audio_path() is None:
        return False
    try:
        out = subprocess.run(
            ["SwitchAudioSource", "-a"], capture_output=True, text=True, timeout=5
        ).stdout
        return MAC_INPUT_DEVICE in out
    except Exception:
        return False


def _get_device(kind: str) -> str | None:
    """Current device for kind in {'input', 'output'}."""
    try:
        return subprocess.run(
            ["SwitchAudioSource", "-c", "-t", kind],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip() or None
    except Exception:
        return None


def _set_device(kind: str, name: str) -> None:
    subprocess.run(
        ["SwitchAudioSource", "-t", kind, "-s", name],
        capture_output=True, text=True, timeout=5,
    )


def _cable_available_windows() -> bool:
    """True if VB-CABLE's playback side is visible to miniaudio."""
    try:
        import miniaudio
    except ImportError:
        return False
    try:
        playbacks = miniaudio.Devices().get_playbacks()
    except Exception:
        return False
    return any(
        WINDOWS_PLAYBACK_DEVICE.lower() in d["name"].lower() for d in playbacks
    )


def virtual_audio_available() -> bool:
    """True if this platform's virtual audio device is installed & usable."""
    if IS_MAC:
        return blackhole_available()
    if IS_WINDOWS:
        return _cable_available_windows()
    return False


def input_device_name() -> str | None:
    """The device Heidi should RECORD from on this platform (None if n/a)."""
    if IS_MAC:
        return MAC_INPUT_DEVICE
    if IS_WINDOWS:
        return WINDOWS_INPUT_DEVICE
    return None


class AudioRouter:
    """macOS context manager: route default I/O to BlackHole, restore on exit."""

    def __init__(self) -> None:
        self._orig_input: str | None = None
        self._orig_output: str | None = None

    def __enter__(self) -> "AudioRouter":
        self._orig_input = _get_device("input")
        self._orig_output = _get_device("output")
        _set_device("input", MAC_INPUT_DEVICE)
        _set_device("output", MAC_INPUT_DEVICE)
        time.sleep(0.5)  # let CoreAudio settle on the new default devices
        return self

    def __exit__(self, *exc) -> None:
        # Always restore, even if the test blew up mid-recording.
        if self._orig_input:
            _set_device("input", self._orig_input)
        if self._orig_output:
            _set_device("output", self._orig_output)


def play_clip(path: str | Path, min_seconds: float) -> subprocess.Popen:
    """Play `path` (looping to fill `min_seconds`) into the platform's virtual
    audio device. macOS: afplay to the BlackHole-routed default output. Windows:
    miniaudio into CABLE Input via scripts/play_audio_to_device.py.

    Returns the running Popen so the caller can stop it early.
    """
    path = str(path)
    if IS_WINDOWS:
        # play_audio_to_device plays once; wrap in a loop to fill the window.
        script = str(_REPO_ROOT / "scripts" / "play_audio_to_device.py")
        end = f"(Get-Date).AddSeconds({int(min_seconds) + 2})"
        cmd = (
            f"while ((Get-Date) -lt {end}) {{ "
            f"& '{sys.executable}' '{script}' '{path}' "
            f"--device '{WINDOWS_PLAYBACK_DEVICE}' }}"
        )
        return subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", cmd],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    # macOS (and any afplay-capable posix): loop afplay in a shell.
    return subprocess.Popen(
        ["/bin/sh", "-c", f'end=$(($(date +%s)+{int(min_seconds)+2})); '
                          f'while [ $(date +%s) -lt $end ]; do afplay "{path}"; done'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def stop_clip(proc: subprocess.Popen) -> None:
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    # Playback children may outlive the wrapper; sweep them.
    if IS_WINDOWS:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process "
             "| Where-Object {$_.CommandLine -like '*play_audio_to_device.py*'} "
             "| ForEach-Object { "
             "Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue "
             "}"],
            capture_output=True,
        )
    else:
        subprocess.run(["pkill", "-f", "afplay"], capture_output=True)


class AudioInjector:
    """Platform-agnostic audio injection for a recording test.

    Wraps the per-OS mechanism so specs are identical on macOS and Windows:

        inj = AudioInjector(app)
        injected = inj.prepare()      # route + select input; False if unavailable
        inj.play(clip, seconds)       # start playback for the recording window
        ...
        inj.cleanup()                 # stop playback, restore devices

    `prepare()` returns True only if the virtual audio device exists AND (on
    Windows) Heidi's input could be selected. When it returns False the caller
    should treat the run as structural-only (no content assertions).
    """

    def __init__(self, app=None) -> None:
        self.app = app
        self._router: "AudioRouter | None" = None
        self._proc: "subprocess.Popen | None" = None
        self.injected = False

    def prepare(self) -> bool:
        if not virtual_audio_available():
            return False
        if IS_MAC:
            # Route system default I/O to BlackHole; Heidi records the default
            # input, so no in-app device picker needed.
            self._router = AudioRouter()
            self._router.__enter__()
            self.injected = True
            return True
        if IS_WINDOWS:
            # Leave system devices alone; tell Heidi to record CABLE Output.
            if self.app is not None:
                from pages import ScribePage
                if not ScribePage(self.app).select_input_device(WINDOWS_INPUT_DEVICE):
                    return False
            self.injected = True
            return True
        return False

    def play(self, clip: str | Path, seconds: float) -> None:
        self._proc = play_clip(clip, seconds)

    def cleanup(self) -> None:
        if self._proc is not None:
            stop_clip(self._proc)
            self._proc = None
        if self._router is not None:
            self._router.__exit__(None, None, None)
            self._router = None

