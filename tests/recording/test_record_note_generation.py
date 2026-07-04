"""recording: the POC true-app E2E scenario (APP-7808) + long-session cases.

Tests:

1. test_record_stop_note_generation — the ticket's core scenario:
   login -> new session -> record ~30s -> stop -> note generation STARTS.
   Runs with or without audio (structural check only).

2. test_record_transcribes_spoken_content — true end-to-end (30s):
   inject a fixed spoken consult via BlackHole, record, stop, wait for the note
   to complete, assert transcription accuracy >= threshold. Requires BlackHole.

3. test_record_5min_session / test_record_10min_session — long-session stress:
   same true-e2e flow but recording for 5 / 10 minutes (clip loops to fill the
   duration). Proves the session stays stable, the timer keeps advancing, and
   note generation still works after a long capture.

Run from Ghostty (Accessibility + Screen Recording), logged in, Heidi foreground:
    .venv/bin/python3.14 -m pytest tests/recording/ -v -s
    .venv/bin/python3.14 -m pytest tests/recording/ -v -s -m "not longsession"  # skip long
    .venv/bin/python3.14 -m pytest tests/recording/ -v -s -k 5min              # just 5min
"""
import os

import pytest
import xa11y

from lib.login import is_logged_in
from pages import RecordingPage
from pages.sidebar import Sidebar

pytestmark = [pytest.mark.recording, pytest.mark.slow]

# Words spoken in assets/consult_30s.wav — the note should contain several of
# these if audio was really transcribed. Generous so summarisation variance
# still matches.
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
    Default 0.4; override with TRANSCRIPT_MATCH_THRESHOLD."""
    return float(os.environ.get("TRANSCRIPT_MATCH_THRESHOLD", "0.4"))


def _timer_to_seconds(mmss: str | None) -> int | None:
    if not mmss or ":" not in mmss:
        return None
    try:
        m, s = mmss.split(":")
        return int(m) * 60 + int(s)
    except ValueError:
        return None


def _run_transcription_case(rec: RecordingPage, audio_injection, seconds: float):
    """Shared flow: start -> inject audio -> record `seconds` (sampling the
    timer) -> stop -> wait for note -> assert accuracy. Returns (accuracy, note).
    """
    rec.start_recording()
    assert rec.is_recording(), "Recording did not start"

    audio_injection(seconds)  # loops the fixed clip to fill the duration
    samples = rec.wait_recording(seconds, sample_every=60.0)
    print(f"timer samples (elapsed_s, mm:ss): {samples}")

    # Timer must advance and roughly track wall-clock (stability over long runs).
    first = _timer_to_seconds(samples[0][1])
    last = _timer_to_seconds(samples[-1][1])
    assert first is not None and last is not None, f"No timer read: {samples}"
    assert last > first, f"Recording timer did not advance ({first} -> {last})"
    # allow generous slack (startup lag, sampling granularity)
    assert last >= seconds * 0.7, (
        f"Timer {last}s well below expected ~{seconds:.0f}s — session may have "
        f"stalled. samples={samples}"
    )

    rec.stop_recording()
    assert rec.wait_note_generation(timeout=90.0), "Note generation never started"
    completed = rec.wait_note_complete(timeout=240.0)
    note = rec.note_text().lower()

    hits = [w for w in EXPECTED_KEYWORDS if w in note]
    accuracy = len(hits) / len(EXPECTED_KEYWORDS)
    threshold = _match_threshold()
    print(f"transcript accuracy: {accuracy:.0%} ({len(hits)}/{len(EXPECTED_KEYWORDS)}) "
          f"hits={hits} threshold={threshold:.0%} completed={completed}")

    assert note.strip(), "Note body is empty"
    assert accuracy >= threshold, (
        f"Transcription accuracy {accuracy:.0%} below threshold {threshold:.0%}. "
        f"Matched {hits} of {EXPECTED_KEYWORDS}.\nNote (first 500):\n{note[:500]}"
    )
    return accuracy, note


# --- core ticket scenario ---------------------------------------------------

@pytest.mark.timeout(400)
def test_record_stop_note_generation(fresh_session: RecordingPage, audio_injection):
    """Core ticket scenario: recording works, stop works, generation starts."""
    rec = fresh_session
    rec.start_recording()
    assert rec.is_recording(), "Recording did not start (no 'End recording')"

    audio_injection()
    samples = rec.wait_recording(_seconds())
    first = _timer_to_seconds(samples[0][1])
    last = _timer_to_seconds(samples[-1][1])
    assert first is not None and last is not None, f"No timer: {samples}"
    assert last > first, f"Recording timer did not advance ({first} -> {last})"

    rec.stop_recording()
    assert rec.wait_note_generation(timeout=60.0), (
        "Note generation did not start within 60s after stopping"
    )


@pytest.mark.timeout(400)
def test_record_transcribes_spoken_content(
    fresh_session: RecordingPage, audio_injection, require_blackhole
):
    """True end-to-end (30s): injected audio -> correct transcribed content."""
    _run_transcription_case(fresh_session, audio_injection, _seconds())


# --- long-session stress cases ----------------------------------------------

@pytest.mark.longsession
@pytest.mark.timeout(700)  # 5 min record + generation + slack
def test_record_5min_session(
    fresh_session: RecordingPage, audio_injection, require_blackhole
):
    """5-minute long session: stable capture + note generation + accuracy."""
    _run_transcription_case(fresh_session, audio_injection, 300)


@pytest.mark.longsession
@pytest.mark.timeout(1200)  # 10 min record + generation + slack
def test_record_10min_session(
    fresh_session: RecordingPage, audio_injection, require_blackhole
):
    """10-minute long session: stable capture + note generation + accuracy."""
    _run_transcription_case(fresh_session, audio_injection, 600)
