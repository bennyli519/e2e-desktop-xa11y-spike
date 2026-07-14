"""TCD004 - Validate transcribe session with audio upload.

From the Desktop App 2.5.0 release plan:

    Feature: Transcribe session with audio upload
      Given the user is logged in and has access to Scribe
      When the user uploads a valid audio file
      And starts a transcribe session
      Then the transcript should be generated successfully
      And the session output should be available without errors

    Execution steps:
      1. Open Scribe and choose transcribe workflow.
      2. Upload a valid audio file.
      3. Start processing.
      4. Verify transcript and generated output are complete.
      5. Confirm no failures appear in UI.

Automation (traced from a real AX tree — see reports/upload_*.txt):
    ScribePage.upload_audio() opens the 'Upload a recording' dialog via the
    Transcribe caret menu ('Transcribe Open transcription mode menu' ->
    'Upload session audio'), leaves the segmented control on Transcribe, clicks
    the dropzone, then drives the NATIVE macOS Open panel (dialog 'Open') via
    Cmd+Shift+G to type the absolute clip path and confirm. We upload the fixed
    consult clip (assets/consult_5min.wav) and assert transcript + note
    complete with good accuracy. The flow runs ONCE (module-scoped fixture).

Run from Ghostty (needs Accessibility + Screen Recording), logged in, Heidi
foreground:
    .venv/bin/python -m pytest tests/scribe/upload/test_tcd004_transcribe_audio_upload.py -v
"""
import pytest

from _scribe_cases import (
    check_upload_accepted,
    check_upload_note_generated,
    check_upload_transcript_accuracy,
    check_upload_transcription_generated,
    make_upload_fixture,
)
from _scribe_flow import KEYWORDS_5MIN

pytestmark = [pytest.mark.scribe, pytest.mark.upload, pytest.mark.slow]

result = make_upload_fixture(
    flow="tcd004", mode="transcribe", clip="consult_5min.wav",
    keywords=KEYWORDS_5MIN, transcript_threshold=0.6,
)


@pytest.mark.timeout(600)
def test_upload_accepted(result):
    check_upload_accepted(result)


@pytest.mark.timeout(600)
def test_transcription_generated(result):
    check_upload_transcription_generated(result)


@pytest.mark.timeout(600)
def test_note_generated(result):
    check_upload_note_generated(result)


@pytest.mark.timeout(600)
def test_transcript_accuracy(result):
    check_upload_transcript_accuracy(result)
