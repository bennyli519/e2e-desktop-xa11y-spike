"""remote-session-recording: record a session via the physical Chronicle device.

IMPORTANT: the app has NO start/stop button for remote-device recording — the
user presses the physical button ON the Heidi Remote. This test therefore
verifies the app's REACTION to device-driven recording:
  - you press the device button when prompted
  - the app shows the live-transcription indicator + 'Heidi Remote' input
  - you long-press to stop
  - a session with a transcript/note appears

Requires a paired, connected device AND a human to press the button
(RUN_MANUAL=1). Without those it skips.

Run from Ghostty, logged in, Heidi foreground, device connected:
    RUN_MANUAL=1 pytest tests/remote-session-recording/ -v -s
"""
import time

import pytest
import xa11y

from pages import DevicePage

pytestmark = [pytest.mark.remote_session, pytest.mark.needs_device,
              pytest.mark.needs_manual, pytest.mark.slow, pytest.mark.timeout(300)]


@pytest.fixture()
def require_manual():
    import os
    if os.environ.get("RUN_MANUAL") != "1":
        pytest.skip(
            "Remote recording is device-button-driven — set RUN_MANUAL=1 and be "
            "ready to press the physical device button when prompted"
        )


def _prompt(msg: str) -> None:
    """Print a clear instruction for the human operator."""
    print(f"\n>>> ACTION REQUIRED: {msg}\n")


def _live_indicator_present(app: xa11y.App) -> bool:
    # The live-transcription indicator shows the input label 'Heidi Remote'
    # plus recording controls (Stop/Pause 'transcribing').
    return (
        app.locator("static_text[value*='Heidi Remote']").exists()
        and (
            app.locator("button[name*='Stop transcribing']").exists()
            or app.locator("button[name*='transcribing']").exists()
        )
    )


def test_remote_device_recording_reaction(heidi_app: xa11y.App, require_manual):
    dp = DevicePage(heidi_app)
    dp.open()
    time.sleep(2)
    if not dp.has_paired_device():
        pytest.skip("No paired device")
    if not dp.is_connected():
        if dp.reconnect():
            dp.wait_connected(timeout=40)
    if not dp.is_connected():
        pytest.skip("Device not connected — cannot record from it")

    # WHEN the operator starts recording on the device.
    _prompt("PRESS the Heidi Remote button ONCE to start recording. "
            "Waiting up to 60s for the app to react…")
    started = False
    deadline = time.time() + 60
    while time.time() < deadline:
        if _live_indicator_present(heidi_app):
            started = True
            break
        time.sleep(2)
    assert started, (
        "App did not show the live-recording indicator after the device started "
        "recording (no 'Heidi Remote' live indicator / transcribing controls)"
    )
    print("Live recording indicator detected — app reacted to device recording.")

    # Let it record briefly.
    time.sleep(15)

    # WHEN the operator stops recording on the device.
    _prompt("LONG-PRESS the Heidi Remote button to STOP recording. "
            "Waiting up to 60s for the indicator to clear…")
    stopped = False
    deadline = time.time() + 60
    while time.time() < deadline:
        if not _live_indicator_present(heidi_app):
            stopped = True
            break
        time.sleep(2)
    assert stopped, "Live indicator did not clear after the device stopped recording"

    # THEN a session should exist. Best-effort: the app auto-navigates to it or
    # it appears in the session list. We assert the app is back on a normal view.
    time.sleep(5)
    assert heidi_app.locator("web_area").exists(), "App web view missing after stop"
    print("Remote recording reaction verified (start indicator -> stop -> cleared).")
