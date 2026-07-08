"""Recording flow: 30-second session.

new session -> start transcribe -> record ~30s -> stop -> note generation.
Each assertion below is a separate test so the result reads as a checklist:

    test_recording_starts        ☑  recording actually started
    test_timer_advances          ☑  timer moved forward (no stall)
    test_transcription_generated ☑  a transcript was produced
    test_note_generated          ☑  a note was generated (non-empty)
    test_transcript_accuracy     ☑  transcript matches spoken words >= threshold

The flow runs ONCE (module-scoped `result` fixture); the tests read its cache.
"""
import pytest

from _cases import (
    check_note_generated,
    check_recording_starts,
    check_timer_advances,
    check_transcript_accuracy,
    check_transcription_generated,
    make_result_fixture,
)
from _flow import KEYWORDS_30S

pytestmark = [pytest.mark.recording, pytest.mark.slow]

result = make_result_fixture(
    flow="30s", seconds=30, clip="consult_30s.wav",
    keywords=KEYWORDS_30S, transcript_threshold=0.9,
)


@pytest.mark.timeout(400)
def test_recording_starts(result):
    check_recording_starts(result)


@pytest.mark.timeout(400)
def test_timer_advances(result):
    check_timer_advances(result)


@pytest.mark.timeout(400)
def test_transcription_generated(result):
    check_transcription_generated(result)


@pytest.mark.timeout(400)
def test_note_generated(result):
    check_note_generated(result)


@pytest.mark.timeout(400)
def test_transcript_accuracy(result):
    check_transcript_accuracy(result)
