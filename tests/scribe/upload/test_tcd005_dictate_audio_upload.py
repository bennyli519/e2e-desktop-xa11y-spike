"""TCD005 - Validate dictate session with audio upload.

From the Desktop App 2.5.0 release plan:

    Feature: Dictate session with audio upload
      Given the user is logged in and has access to Dictate
      When the user uploads a valid audio file
      And starts a dictate session
      Then dictated output should be generated successfully
      And the session should complete without errors

    Execution steps:
      1. Open Dictate workflow.
      2. Upload valid audio.
      3. Start processing.
      4. Verify dictated output quality and completion.
      5. Confirm no UI or processing errors.

Automation (traced from a real AX tree):
    Same upload harness as TCD004 but the 'Upload a recording' dialog's
    segmented control is switched to DICTATE before selecting the file
    (ScribePage.upload_audio(mode='Dictate') -> select_upload_mode('Dictate')).
    Uploads assets/consult_5min.wav and asserts transcript + note complete
    with good accuracy. The flow runs ONCE (module-scoped fixture).

Run from Ghostty, logged in, Heidi foreground:
    .venv/bin/python -m pytest tests/scribe/upload/test_tcd005_dictate_audio_upload.py -v
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
    flow="tcd005", mode="dictate", clip="consult_5min.wav",
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
