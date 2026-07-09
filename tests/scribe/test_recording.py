"""scribe: desktop recording smoke test.

For virtual-audio runs, set:
    HEIDI_E2E_RECORDING_INPUT_DEVICE="BlackHole 2ch"
    HEIDI_E2E_AUDIO_FIXTURE="/path/to/sample.wav"

The fixture playback must already be routed into that virtual input device.
On macOS this is commonly BlackHole; on Windows use an equivalent virtual
audio cable device.
"""
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

import pytest
import xa11y

from pages import ScribePage

pytestmark = [pytest.mark.scribe, pytest.mark.slow]


@pytest.fixture()
def scribe(heidi_app: xa11y.App) -> ScribePage:
    sp = ScribePage(heidi_app)
    sp.new_session()
    return sp


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _fixture_root() -> Path:
    configured = os.environ.get("HEIDI_E2E_FIXTURE_ROOT")
    if configured:
        return Path(configured).expanduser()

    scribe_fe = os.environ.get("SCRIBE_FE_PATH")
    candidates = []
    if scribe_fe:
        candidates.append(Path(scribe_fe).expanduser())
    candidates.append(_repo_root().parent / "scribe-fe-v2")

    for candidate in candidates:
        root = candidate / "packages" / "e2e-utils" / "test-files"
        if root.exists():
            return root

    return candidates[0] / "packages" / "e2e-utils" / "test-files"


def _fixture_path(env_name: str, default_name: str) -> Path:
    configured = os.environ.get(env_name)
    if configured:
        return Path(configured).expanduser()
    return _fixture_root() / default_name


def _default_recording_input_device() -> str | None:
    configured = os.environ.get("HEIDI_E2E_RECORDING_INPUT_DEVICE")
    if configured:
        return configured

    if os.name == "nt":
        script = r"""
        Get-PnpDevice -Class AudioEndpoint -ErrorAction SilentlyContinue |
          Where-Object {
            $_.InstanceId -like 'SWD\MMDEVAPI\{0.0.1.*' -and
            $_.FriendlyName -like '*CABLE Output*'
          } |
          Select-Object -First 1 -ExpandProperty FriendlyName
        """
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            return "CABLE Output"
        name = result.stdout.strip()
        return name or "CABLE Output"

    if sys.platform == "darwin":
        return "BlackHole 2ch"

    return None


def _start_audio_fixture_playback(fixture: Path | None = None) -> subprocess.Popen | None:
    if fixture is None:
        configured = os.environ.get("HEIDI_E2E_AUDIO_FIXTURE")
        fixture = Path(configured).expanduser() if configured else None
    if not fixture:
        return None

    path = Path(fixture).expanduser()
    if not path.exists():
        pytest.fail(f"HEIDI_E2E_AUDIO_FIXTURE does not exist: {path}")

    command = os.environ.get("HEIDI_E2E_AUDIO_PLAY_CMD")
    if command:
        return subprocess.Popen(command.format(file=str(path)), shell=True)

    if os.name == "nt":
        device = os.environ.get("HEIDI_E2E_AUDIO_PLAYBACK_DEVICE", "CABLE Input")
        return subprocess.Popen(
            [
                sys.executable,
                str(_repo_root() / "scripts" / "play_audio_to_device.py"),
                str(path),
                "--device",
                device,
            ]
        )

    if sys.platform == "darwin":
        return subprocess.Popen(["afplay", str(path)])

    if os.name == "nt" and path.suffix.lower() == ".wav":
        quoted = str(path).replace("'", "''")
        return subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                (
                    "$player = New-Object System.Media.SoundPlayer "
                    f"'{quoted}'; $player.PlaySync()"
                ),
            ]
        )

    pytest.skip(
        "Set HEIDI_E2E_AUDIO_PLAY_CMD to play non-wav fixtures on this platform"
    )


def _terminate_playback(playback: subprocess.Popen | None) -> None:
    if playback and playback.poll() is None:
        playback.terminate()
        try:
            playback.wait(timeout=5)
        except subprocess.TimeoutExpired:
            playback.kill()


def _select_configured_input_device(scribe: ScribePage, dump_tree) -> None:
    target_device = _default_recording_input_device()
    if target_device and not scribe.select_input_device(target_device):
        dump_tree("recording_input_device_missing", max_depth=60)
        pytest.fail(
            f"Configured input device {target_device!r} was not available. "
            "Check BlackHole/VB-CABLE virtual audio setup."
        )


def test_transcribe_recording_starts_and_stops(scribe: ScribePage, dump_tree):
    _select_configured_input_device(scribe, dump_tree)

    playback = None
    try:
        playback = _start_audio_fixture_playback()
        scribe.start_transcribing()

        assert scribe.wait_recording_elapsed(5), (
            "Recording timer did not advance to 5 seconds"
        )
        dump_tree("recording_started", max_depth=40)

        assert scribe.end_recording(), "Could not end recording"
        dump_tree("recording_ended", max_depth=40)
    finally:
        _terminate_playback(playback)


@pytest.mark.timeout(420)
def test_transcribe_short_audio_generates_note(scribe: ScribePage, dump_tree):
    _select_configured_input_device(scribe, dump_tree)

    fixture = _fixture_path("HEIDI_E2E_SHORT_AUDIO_FIXTURE", "test.wav")
    record_seconds = int(os.environ.get("HEIDI_E2E_SHORT_RECORDING_SECONDS", "45"))

    playback = None
    try:
        playback = _start_audio_fixture_playback(fixture)
        time.sleep(1)
        scribe.start_transcribing()

        assert scribe.wait_recording_elapsed(record_seconds, timeout=record_seconds + 30), (
            f"Recording timer did not advance to {record_seconds} seconds"
        )
        dump_tree("short_recording_started", max_depth=40)

        assert scribe.end_recording(), "Could not end short recording"
    finally:
        _terminate_playback(playback)

    assert scribe.click_create_note_if_available(), "Could not start note generation"
    scribe.select_hp_template_if_available()
    assert scribe.wait_until_generation_idle(timeout=240), "Note generation stayed busy"
    assert not scribe.has_transcript_error(), "Transcript/note generation showed an error"

    dump_tree("short_note_generated", max_depth=55)
    assert scribe.wait_for_note_content(timeout=120), "Generated note content was empty"
    assert scribe.wait_for_transcript_content(timeout=60), "Transcript content was empty"


@pytest.mark.timeout(420)
def test_dictate_short_audio_generates_note(scribe: ScribePage, dump_tree):
    _select_configured_input_device(scribe, dump_tree)

    fixture = _fixture_path("HEIDI_E2E_DICTATION_AUDIO_FIXTURE", "test.wav")
    record_seconds = int(os.environ.get("HEIDI_E2E_DICTATION_RECORDING_SECONDS", "45"))

    playback = None
    try:
        playback = _start_audio_fixture_playback(fixture)
        time.sleep(1)
        scribe.start_dictating()

        assert scribe.wait_recording_elapsed(record_seconds, timeout=record_seconds + 30), (
            f"Dictation timer did not advance to {record_seconds} seconds"
        )
        dump_tree("dictation_recording_started", max_depth=40)

        assert scribe.end_recording(), "Could not end dictation recording"
    finally:
        _terminate_playback(playback)

    assert scribe.click_create_note_if_available(), "Could not start dictation note generation"
    scribe.select_hp_template_if_available()
    assert scribe.wait_until_generation_idle(timeout=240), "Dictation note generation stayed busy"
    assert not scribe.has_transcript_error(), "Dictation transcript/note generation showed an error"

    dump_tree("dictation_note_generated", max_depth=55)
    assert scribe.wait_for_note_content(timeout=120), "Dictation generated note content was empty"
    assert scribe.wait_for_transcript_content(timeout=120), "Dictation transcript content was empty"


@pytest.mark.long
@pytest.mark.timeout(45 * 60)
def test_transcribe_long_audio_generates_note(scribe: ScribePage, dump_tree):
    if os.environ.get("HEIDI_E2E_RUN_LONG_RECORDING") != "1":
        pytest.skip("Set HEIDI_E2E_RUN_LONG_RECORDING=1 to run the 25-minute case")

    _select_configured_input_device(scribe, dump_tree)

    fixture = _fixture_path("HEIDI_E2E_LONG_AUDIO_FIXTURE", "longscribe.mp3")
    playback = None
    try:
        playback = _start_audio_fixture_playback(fixture)
        time.sleep(1)
        scribe.start_transcribing()

        playback.wait(timeout=35 * 60)
        assert scribe.wait_recording_elapsed(20 * 60, timeout=30), (
            "Long recording timer did not reach 20 minutes"
        )
        dump_tree("long_recording_completed", max_depth=40)

        assert scribe.end_recording(), "Could not end long recording"
    finally:
        _terminate_playback(playback)

    assert scribe.click_create_note_if_available(), "Could not start long-note generation"
    scribe.select_hp_template_if_available()
    assert scribe.wait_until_generation_idle(timeout=300), "Long-note generation stayed busy"
    assert not scribe.has_transcript_error(), "Long transcript/note generation showed an error"

    dump_tree("long_note_generated", max_depth=55)
    assert scribe.wait_for_note_content(timeout=180), "Long generated note content was empty"
    assert scribe.wait_for_transcript_content(timeout=120), "Long transcript content was empty"
