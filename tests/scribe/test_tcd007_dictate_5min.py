"""TCD007 - Dictate session with short 5 min recording.

From the Desktop App 2.5.0 release plan:

    Feature: Dictate short recording
      Given the user is logged in and has a 5-minute test recording
      When the user submits the 5-minute recording in dictate mode
      Then dictated output should complete successfully
      And output should be available in expected time

    Execution steps:
      1. Open dictate session flow.
      2. Upload/select a 5-minute test recording.
      3. Start dictate processing.
      4. Validate dictated output and completion.
      5. Verify there are no processing errors.

Automation note:
    Same live-injection approach as TCD006 but in DICTATE mode
    (rec.start_dictating()). Dictation transcribes speech verbatim, so the
    transcript accuracy check applies as-is. The flow runs ONCE (module-scoped
    `result` fixture); each test asserts one criterion.

Run from Ghostty (needs Accessibility + Screen Recording), logged in, Heidi
foreground. >600s: launch with Hermes background=true.

    .venv/bin/python -m pytest tests/scribe/recording/test_tcd007_dictate_5min.py -v
"""
import pytest

from _scribe_cases import (
    check_duration_display,
    check_note_generated,
    check_recording_starts,
    check_timer_advances,
    check_transcript_accuracy,
    check_transcription_generated,
    make_recording_fixture,
)
from _scribe_flow import KEYWORDS_5MIN

pytestmark = [pytest.mark.scribe, pytest.mark.slow, pytest.mark.longsession]

result = make_recording_fixture(
    flow="tcd007", mode="dictate", seconds=310, clip="consult_5min.wav",
    keywords=KEYWORDS_5MIN, transcript_threshold=0.9,
)


@pytest.mark.timeout(900)
def test_recording_starts(result):
    check_recording_starts(result)


@pytest.mark.timeout(900)
def test_timer_advances(result):
    check_timer_advances(result)


@pytest.mark.timeout(900)
def test_transcription_generated(result):
    check_transcription_generated(result)


@pytest.mark.timeout(900)
def test_note_generated(result):
    check_note_generated(result)


@pytest.mark.timeout(900)
def test_duration_display(result):
    check_duration_display(result)


@pytest.mark.timeout(900)
def test_transcript_accuracy(result):
    check_transcript_accuracy(result)
