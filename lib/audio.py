"""Audio injection for recording E2E tests via a BlackHole loopback device.

Heidi only produces a transcript when it hears real audio on the system mic.
We feed it a fixed, known clip by:

  1. Routing the system INPUT (and output) to the BlackHole virtual device.
     Audio played to BlackHole's output loops back to its input, so whatever
     we `afplay` becomes the microphone signal Heidi records.
  2. Playing the clip in the background while the recording runs.
  3. Restoring the user's original devices afterwards (critical — otherwise
     the machine is left with no real audio I/O).

Requires (install once, see scripts/setup_audio.sh):
  - BlackHole 2ch      (brew install blackhole-2ch, needs reboot)
  - SwitchAudioSource  (brew install switchaudio-osx)

macOS-only. On CI or a machine without BlackHole, `blackhole_available()`
returns False and recording tests should skip rather than corrupt audio state.
"""
import subprocess
import time
from pathlib import Path

BLACKHOLE_NAME = "BlackHole 2ch"


def _switch_audio_path() -> str | None:
    try:
        out = subprocess.run(
            ["which", "SwitchAudioSource"], capture_output=True, text=True, timeout=5
        ).stdout.strip()
        return out or None
    except Exception:
        return None


def blackhole_available() -> bool:
    """True only if both SwitchAudioSource and the BlackHole device exist."""
    if _switch_audio_path() is None:
        return False
    try:
        out = subprocess.run(
            ["SwitchAudioSource", "-a"], capture_output=True, text=True, timeout=5
        ).stdout
        return BLACKHOLE_NAME in out
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


class AudioRouter:
    """Context manager: route I/O to BlackHole, restore originals on exit."""

    def __init__(self) -> None:
        self._orig_input: str | None = None
        self._orig_output: str | None = None

    def __enter__(self) -> "AudioRouter":
        self._orig_input = _get_device("input")
        self._orig_output = _get_device("output")
        _set_device("input", BLACKHOLE_NAME)
        _set_device("output", BLACKHOLE_NAME)
        time.sleep(0.5)  # let CoreAudio settle on the new default devices
        return self

    def __exit__(self, *exc) -> None:
        # Always restore, even if the test blew up mid-recording.
        if self._orig_input:
            _set_device("input", self._orig_input)
        if self._orig_output:
            _set_device("output", self._orig_output)


def play_clip(path: str | Path, min_seconds: float) -> subprocess.Popen:
    """Play `path` on a loop until at least `min_seconds` have elapsed.

    Returns the running afplay Popen wrapped in a tiny supervisor so the caller
    can stop it early. We loop the clip because a fixed file may be shorter than
    the requested recording duration.
    """
    path = str(path)
    # A shell loop keeps replaying the clip; the recording controls total time.
    proc = subprocess.Popen(
        ["/bin/sh", "-c", f'end=$(($(date +%s)+{int(min_seconds)+2})); '
                          f'while [ $(date +%s) -lt $end ]; do afplay "{path}"; done'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return proc


def stop_clip(proc: subprocess.Popen) -> None:
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    # afplay children may outlive the sh wrapper; sweep them.
    subprocess.run(["pkill", "-f", "afplay"], capture_output=True)
