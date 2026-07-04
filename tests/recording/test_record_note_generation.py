"""recording: the POC true-app E2E scenario (APP-7808).

Two levels of assertion:

1. test_record_stop_note_generation — the ticket's core scenario:
   login -> new session -> record ~30s -> stop -> note generation STARTS.
   Runs with or without audio (structural check only).

2. test_record_transcribes_spoken_content — the true end-to-end proof:
   inject a fixed spoken consult via BlackHole, record, stop, wait for the
   note to COMPLETE, and assert the generated note CONTAINS words from the
   audio (headache / sleep / etc). Requires BlackHole (skips otherwise).

Run from Ghostty (Accessibility + Screen Recording), logged in, Heidi foreground:
    .venv/bin/python3.14 -m pytest tests/recording/ -v -s
    RECORD_SECONDS=600 .venv/bin/python3.14 -m pytest tests/recording/ -v -s  # long
"""
import os

import pytest
import xa11y

from lib.login import is_logged_in
from pages import RecordingPage
from pages.sidebar import Sidebar

pytestmark = [pytest.mark.recording, pytest.mark.slow, pytest.mark.timeout(400)]

# Words spoken in assets/consult_30s.wav — the note/transcript should contain
# several of these if audio was really transcribed. Kept generous so a slightly
# different summarisation still matches.
EXPECTED_KEYWORDS = [
    "headache", "sleep", "morning", "nausea", "photophobia",
    "fatigue", "afternoon", "week",
]


@pytest.fixture()
def fresh_session(heidi_app: xa11y.App) -> RecordingPage:
    """Ensure logged in, open a brand-new Scribe session, return RecordingPage."""
    if not is_logged_in(heidi_app):
        pytest.skip("Not logged in — run tests/auth/test_login.py first")
    sidebar = Sidebar(heidi_app)
    sidebar.reset_to_scribe()
    assert sidebar.new_session(), "Could not start a New session"
    return RecordingPage(heidi_app)


def _seconds() -> float:
    return float(os.environ.get("RECORD_SECONDS", "30"))


def _match_threshold() -> float:
    """Fraction of expected keywords that must appear in the note (0..1).

    Transcription + LLM summarisation are non-deterministic, so we don't require
    every word — just that accuracy clears a bar. Default 0.4 (40%); override
    with TRANSCRIPT_MATCH_THRESHOLD.
    """
    return float(os.environ.get("TRANSCRIPT_MATCH_THRESHOLD", "0.4"))


def test_record_stop_note_generation(fresh_session: RecordingPage, audio_injection):
    """Core ticket scenario: recording works, stop works, generation starts."""
    rec = fresh_session

    rec.start_recording()
    assert rec.is_recording(), "Recording did not start (no 'End recording' control)"

    audio_injection()
    t0 = rec.recording_timer()
    rec.wait_recording(_seconds())
    t1 = rec.recording_timer()

    assert t0 is not None and t1 is not None, f"No timer observed (t0={t0}, t1={t1})"
    assert t1 != t0, f"Recording timer did not advance ({t0} -> {t1})"

    rec.stop_recording()

    started = rec.wait_note_generation(timeout=60.0)
    assert started, (
        "Note generation did not start within 60s after stopping "
        "(no 'Analyzing transcript' / 'Stop generating' / Transcript tab)"
    )


def test_record_transcribes_spoken_content(
    fresh_session: RecordingPage, audio_injection, require_blackhole
):
    """True end-to-end: injected audio -> correct transcribed note content."""
    rec = fresh_session

    rec.start_recording()
    assert rec.is_recording(), "Recording did not start"

    audio_injection()  # feeds assets/consult_30s.wav through BlackHole
    t0 = rec.recording_timer()
    rec.wait_recording(_seconds())
    t1 = rec.recording_timer()
    assert t0 != t1, f"Recording timer did not advance ({t0} -> {t1})"

    rec.stop_recording()
    assert rec.wait_note_generation(timeout=60.0), "Note generation never started"

    # Wait for the note to actually populate with body text.
    completed = rec.wait_note_complete(timeout=180.0)
    note = rec.note_text().lower()

    hits = [w for w in EXPECTED_KEYWORDS if w in note]
    accuracy = len(hits) / len(EXPECTED_KEYWORDS)
    threshold = _match_threshold()
    print(f"transcript accuracy: {accuracy:.0%} "
          f"({len(hits)}/{len(EXPECTED_KEYWORDS)}) hits={hits} "
          f"threshold={threshold:.0%} completed={completed}")

    assert note.strip(), "Note body is empty"
    assert accuracy >= threshold, (
        f"Transcription accuracy {accuracy:.0%} below threshold {threshold:.0%}. "
        f"Matched {hits} of {EXPECTED_KEYWORDS}.\n"
        f"Note text (first 500 chars):\n{note[:500]}"
    )
