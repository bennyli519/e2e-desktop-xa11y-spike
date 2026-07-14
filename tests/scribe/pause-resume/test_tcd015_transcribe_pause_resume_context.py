"""TCD015 - Transcribe recording: record, pause, resume; context before and
after pause included with no errors.

From the Desktop App 2.5.0 release plan:

    Feature: Transcribe recording pause and resume context continuity
      Given the user is logged in and starts a transcribe recording session
      When the user records audio
      And pauses the recording
      And resumes and continues recording
      Then context from both pre-pause and post-pause segments should be included
      And the session should complete with no errors

    Execution steps:
      1. Start a new transcribe recording session.
      2. Record initial speech segment.
      3. Pause recording for a short interval.
      4. Resume and record a second speech segment.
      5. Complete processing and verify context from both segments is present
         with no errors.

Automation note:
    Two DISTINCT clips are injected either side of the pause (segment A =
    headache/migraine, segment B = diabetes/insulin — see
    scripts/make_pause_resume_clips.sh). Asserting keywords from BOTH sets are
    present in the final transcript proves the pre-pause context survived the
    pause boundary and the post-resume context was captured. The flow runs
    ONCE (module-scoped `result` fixture).

Run from Ghostty, logged in, Heidi foreground:
    .venv/bin/python -m pytest tests/scribe/pause-resume/test_tcd015_transcribe_pause_resume_context.py -v
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
    flow="tcd015", clip_a="pause_seg_a.wav", clip_b="pause_seg_b.wav",
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
def test_pre_pause_context_present(result):
    check_pr_segment_a_present(result)


@pytest.mark.timeout(600)
def test_post_resume_context_present(result):
    check_pr_segment_b_present(result)


@pytest.mark.timeout(600)
def test_no_errors(result):
    check_pr_no_errors(result)
