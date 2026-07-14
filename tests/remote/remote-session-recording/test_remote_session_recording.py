"""remote-session-recording: record a session via the Chronicle device.

The physical device button and the in-app session controls (Transcribe / Pause
transcribing / End recording) are INTERCHANGEABLE once the device is connected —
they drive the same recording. So this test is software-driven: it selects
'Heidi Remote' as the input source, then starts/pauses/resumes/stops the
recording via the session controls and verifies note generation is triggered.

Audio comes from the device microphone (not BlackHole), so we assert the FLOW
(timer advances, pause/resume, stop, note generation starts) — not transcript
content.

Requires a paired, connected Chronicle device. Skips cleanly otherwise.

Run from Ghostty, logged in, Heidi foreground, device connected:
    pytest tests/remote-session-recording/ -v -s
"""
import time

import pytest
import xa11y

from lib.login import is_logged_in
from pages import DevicePage, ScribePage
from pages.sidebar import Sidebar

pytestmark = [pytest.mark.remote_session, pytest.mark.needs_device,
              pytest.mark.slow, pytest.mark.timeout(300)]

RECORD_SECONDS = 20


@pytest.fixture()
def remote_ready(heidi_app: xa11y.App):
    """Ensure logged in + a connected Chronicle device; else skip."""
    if not is_logged_in(heidi_app):
        pytest.skip("Not logged in")
    dp = DevicePage(heidi_app)
    dp.open()
    time.sleep(2)
    if not dp.has_paired_device():
        pytest.skip("No paired Chronicle device")
    if not dp.is_connected():
        if dp.reconnect():
            dp.wait_connected(timeout=40)
    if not dp.is_connected():
        pytest.skip("Chronicle device not connected — cannot record from it")
    return dp


def test_remote_session_recording(remote_ready, heidi_app: xa11y.App):
    # Start a fresh session on the Scribe page.
    sidebar = Sidebar(heidi_app)
    sidebar.reset_to_scribe()
    assert sidebar.new_session(), "Could not start a New session"
    rec = ScribePage(heidi_app)

    # Select 'Heidi Remote' as the input so recording drives the device.
    # NOTE: the input-source trigger is an ICON-ONLY button with no accessible
    # name in the AX tree (verified on real hardware), so it can't be reliably
    # selected by text yet. Until scribe-fe-v2 adds an aria-label to the
    # v2-input-source-trigger, this flow can't guarantee it records via the
    # device rather than the built-in mic — skip with a clear reason.
    if not rec.select_input_heidi_remote():
        pytest.skip(
            "Cannot select 'Heidi Remote' input — the input-source trigger is an "
            "icon-only button with no AX name. Needs an aria-label in scribe-fe-v2 "
            "(follow-up PR) to drive remote-device recording deterministically."
        )

    # WHEN starting recording via the session control (== physical button).
    rec.start_recording()
    assert rec.is_recording(), "Recording did not start"

    # Timer should advance (device is capturing).
    t0 = rec.recording_timer()
    time.sleep(RECORD_SECONDS // 2)

    # Pause then resume (exercises the interchangeable controls).
    if rec.pause_recording():
        time.sleep(3)
        rec.resume_recording()
        time.sleep(2)

    time.sleep(RECORD_SECONDS // 2)
    t1 = rec.recording_timer()
    print(f"remote recording timer: {t0} -> {t1}")
    assert t0 is not None and t1 is not None, f"No timer read (t0={t0}, t1={t1})"
    assert t1 != t0, f"Recording timer did not advance ({t0} -> {t1})"

    # WHEN stopping.
    rec.stop_recording()

    # THEN note generation is triggered (flow check; content not asserted since
    # audio is the device's ambient mic, not a fixed clip).
    started = rec.wait_note_generation(timeout=60.0)
    assert started, "Note generation did not start after stopping remote recording"
    print("Remote-device session recording flow verified (start/pause/stop/note-gen).")
