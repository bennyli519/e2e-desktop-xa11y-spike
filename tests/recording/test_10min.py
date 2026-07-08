"""Recording flow: 10-minute session (long-session stress).

Records ~8-10 min of a real multi-topic consult (assets/consult_10min.wav) and
proves the session stays stable, the timer keeps advancing, note generation
still fires, and transcription accuracy holds. Same checklist as the shorter
flows. The flow runs ONCE (module-scoped `result` fixture).

A >600s run must be launched with Hermes background=true (foreground caps 600s).
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
from _flow import KEYWORDS_10MIN

pytestmark = [pytest.mark.recording, pytest.mark.slow, pytest.mark.longsession]

result = make_result_fixture(
    flow="10min", seconds=500, clip="consult_10min.wav",
    keywords=KEYWORDS_10MIN, transcript_threshold=0.9,
)


@pytest.mark.timeout(1200)
def test_recording_starts(result):
    check_recording_starts(result)


@pytest.mark.timeout(1200)
def test_timer_advances(result):
    check_timer_advances(result)


@pytest.mark.timeout(1200)
def test_transcription_generated(result):
    check_transcription_generated(result)


@pytest.mark.timeout(1200)
def test_note_generated(result):
    check_note_generated(result)


@pytest.mark.timeout(1200)
def test_transcript_accuracy(result):
    check_transcript_accuracy(result)
