"""TCD016 - Transcribe recording: record, pause, resume; transcription before
and after pause included with no errors.

From the Desktop App 2.5.0 release plan:

    Feature: Transcribe recording pause and resume transcription continuity
      Given the user is logged in and starts a transcribe recording session
      When the user records audio
      And pauses the recording
      And resumes and continues recording
      Then transcription from both pre-pause and post-pause segments should be
        included
      And the session should complete with no errors

    Execution steps:
      1. Start transcribe recording and speak first segment.
      2. Pause recording.
      3. Resume and speak second segment.
      4. Finish session and generate transcript.
      5. Confirm transcript contains both segments accurately and no errors.

Automation note:
    Same record->pause->resume harness as TCD015, but the acceptance focus is
    the VERBATIM TRANSCRIPT continuity across the pause boundary: the final
    transcript must contain the distinct keywords from segment A (pre-pause)
    AND segment B (post-resume) with no dropped text and no error banner.
    The flow runs ONCE (module-scoped `result` fixture).

Run from Ghostty, logged in, Heidi foreground:
    .venv/bin/python -m pytest tests/scribe/pause-resume/test_tcd016_transcribe_pause_resume_transcript.py -v
"""
import pytest

from _scribe_cases import (
    check_pr_no_errors,
    check_pr_paused,
    check_pr_recording_starts,
    check_pr_resumed,
    check_pr_segment_a_present,
    check_pr_segment_b_present,
    make_pause_resume_fixture,
)
from _scribe_flow import KEYWORDS_PAUSE_SEG_A, KEYWORDS_PAUSE_SEG_B

pytestmark = [pytest.mark.scribe, pytest.mark.slow]

result = make_pause_resume_fixture(
    flow="tcd016", clip_a="pause_seg_a.wav", clip_b="pause_seg_b.wav",
    keywords_a=KEYWORDS_PAUSE_SEG_A, keywords_b=KEYWORDS_PAUSE_SEG_B,
    seg_seconds=40.0, mode="transcribe",
)


@pytest.mark.timeout(600)
def test_recording_starts(result):
    check_pr_recording_starts(result)


@pytest.mark.timeout(600)
def test_pauses(result):
    check_pr_paused(result)


@pytest.mark.timeout(600)
def test_resumes(result):
    check_pr_resumed(result)


@pytest.mark.timeout(600)
def test_pre_pause_transcription_present(result):
    check_pr_segment_a_present(result)


@pytest.mark.timeout(600)
def test_post_resume_transcription_present(result):
    check_pr_segment_b_present(result)


@pytest.mark.timeout(600)
def test_no_errors(result):
    check_pr_no_errors(result)
