"""Recording flow: 5-minute session (long-session stress).

Records ~5 min of a real multi-topic consult (assets/consult_5min.wav) and
proves the session stays stable, the timer keeps advancing, note generation
still fires, and transcription accuracy holds. Same checklist as the shorter
flows. The flow runs ONCE (module-scoped `result` fixture).

A >600s run must be launched with Hermes background=true (foreground caps 600s).
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
from _flow import KEYWORDS_5MIN

pytestmark = [pytest.mark.recording, pytest.mark.slow, pytest.mark.longsession]

result = make_result_fixture(
    flow="5min", seconds=310, clip="consult_5min.wav",
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
