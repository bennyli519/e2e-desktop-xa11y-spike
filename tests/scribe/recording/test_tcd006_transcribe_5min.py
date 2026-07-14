"""TCD006 - Transcribe session with short 5 min recording.

From the Desktop App 2.5.0 release plan:

    Feature: Transcribe short recording
      Given the user is logged in and has a 5-minute test recording
      When the user submits the 5-minute recording in transcribe mode
      Then the transcript should complete successfully
      And output should be available in expected time

    Execution steps:
      1. Open transcribe session flow.
      2. Upload/select a 5-minute test recording.
      3. Start transcribe processing.
      4. Validate transcript completeness and timing.
      5. Verify session final state is successful.

Automation note:
    Rather than uploading a file (upload entry point not yet automatable —
    see tests/scribe/upload/), this drives a LIVE 5-minute transcribe session
    with the fixed consult clip injected via the platform virtual audio device
    (BlackHole/VB-CABLE). Same acceptance surface: transcript completeness +
    timing + successful final state. The flow runs ONCE (module-scoped
    `result` fixture); each test asserts one criterion.

Run from Ghostty (needs Accessibility + Screen Recording), logged in, Heidi
foreground. >600s: launch with Hermes background=true.

    .venv/bin/python -m pytest tests/scribe/recording/test_tcd006_transcribe_5min.py -v
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
    flow="tcd006", mode="transcribe", seconds=310, clip="consult_5min.wav",
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
