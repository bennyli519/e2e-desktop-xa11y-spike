"""Recording flow: 1-minute session.

Same checklist as the 30s flow, recording for ~60s with a dedicated 1-minute
consult (assets/consult_1min.wav, ~75s so it fills 60s without looping).
The flow runs ONCE (module-scoped `result` fixture); each test reads its cache.
"""
import pytest

from _cases import (
    check_duration_display,
    check_note_generated,
    check_recording_starts,
    check_timer_advances,
    check_transcript_accuracy,
    check_transcription_generated,
    make_result_fixture,
)
from _flow import KEYWORDS_1MIN

pytestmark = [pytest.mark.recording, pytest.mark.slow, pytest.mark.longsession]

result = make_result_fixture(
    flow="1min", seconds=60, clip="consult_1min.wav",
    keywords=KEYWORDS_1MIN, transcript_threshold=0.9,
)


@pytest.mark.timeout(500)
def test_recording_starts(result):
    check_recording_starts(result)


@pytest.mark.timeout(500)
def test_timer_advances(result):
    check_timer_advances(result)


@pytest.mark.timeout(500)
def test_transcription_generated(result):
    check_transcription_generated(result)


@pytest.mark.timeout(500)
def test_note_generated(result):
    check_note_generated(result)


@pytest.mark.timeout(500)
def test_duration_display(result):
    check_duration_display(result)


@pytest.mark.timeout(500)
def test_transcript_accuracy(result):
    check_transcript_accuracy(result)
