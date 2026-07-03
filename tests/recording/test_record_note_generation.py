"""recording: the POC true-app E2E scenario (APP-7808).

Scenario (from the Linear ticket):
    login (session fixture) -> start recording -> wait ~30s -> stop
    -> validate note generation starts or completes.

Audio is injected via BlackHole (see conftest.audio_injection) so Heidi hears
a fixed spoken consult and produces a transcript. Assertions are structural
(non-empty / expected markers), not exact-text matches, per the agreed scope.

Run from Ghostty (needs Accessibility + Screen Recording), logged in:
    .venv/bin/python3.14 -m pytest tests/recording/ -v -s
    RECORD_SECONDS=600 .venv/bin/python3.14 -m pytest tests/recording/ -v -s  # long
"""
import pytest
import xa11y

from lib.login import is_logged_in
from pages import RecordingPage, ScribePage
from pages.sidebar import Sidebar

pytestmark = [pytest.mark.recording, pytest.mark.slow, pytest.mark.timeout(300)]


@pytest.fixture()
def fresh_session(heidi_app: xa11y.App) -> RecordingPage:
    """Ensure logged in, open a brand-new Scribe session, return RecordingPage."""
    if not is_logged_in(heidi_app):
        pytest.skip("Not logged in — run tests/auth/test_login.py first")
    sidebar = Sidebar(heidi_app)
    sidebar.reset_to_scribe()
    assert sidebar.new_session(), "Could not start a New session"
    return RecordingPage(heidi_app)


def test_record_stop_note_generation(fresh_session: RecordingPage, audio_injection):
    rec = fresh_session

    # WHEN: start recording and feed audio for the configured duration
    rec.start_recording()
    assert rec.is_recording(), "Recording did not start (no 'End recording' control)"

    audio_injection()  # begins looping the fixed clip through BlackHole
    t0 = rec.recording_timer()
    rec.wait_recording(_seconds())
    t1 = rec.recording_timer()

    # timer should have advanced — proves the session was really recording
    assert t0 is not None and t1 is not None, f"No timer observed (t0={t0}, t1={t1})"
    assert t1 != t0, f"Recording timer did not advance ({t0} -> {t1})"

    # WHEN: stop the recording
    rec.stop_recording()

    # THEN: note generation starts (Analyzing transcript / Stop generating) or
    # a Transcript tab appears — either satisfies "starts or completes".
    started = rec.wait_note_generation(timeout=60.0)
    assert started, (
        "Note generation did not start within 60s after stopping "
        "(no 'Analyzing transcript' / 'Stop generating' / Transcript tab)"
    )


def _seconds() -> float:
    import os
    return float(os.environ.get("RECORD_SECONDS", "30"))
