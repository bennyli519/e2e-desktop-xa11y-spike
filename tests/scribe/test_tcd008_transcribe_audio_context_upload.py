"""TCD008 - Transcribe session with audio upload and context upload.

From the Desktop App 2.5.0 release plan:

    Feature: Transcribe with audio and context upload
      Given the user is logged in with access to context upload
      When the user uploads valid audio and context files
      And starts a transcribe session
      Then the session should complete successfully
      And generated output should include contextual relevance

    Execution steps:
      1. Open transcribe workflow.
      2. Upload audio file.
      3. Upload context material.
      4. Run session and verify output completion.
      5. Confirm context is reflected in output.

Automation (traced from a real AX tree):
    Full flow is now automated:
      * CONTEXT upload — the Context tab's icon-only paperclip button (inside
        `group "Drag and drop files here"`) opens the same native NSOpenPanel;
        driven via ScribePage.upload_context() reusing _drive_open_panel.
        Uploads assets/context_sample.pdf (context accepts .pdf/.doc/.docx/img).
      * AUDIO upload — same as TCD004 (assets/consult_5min.wav, transcribe).
    Order: context is uploaded FIRST (so it's attached when the note
    generates), then audio (which kicks off processing). We assert the context
    upload completed, plus transcript + note complete with content.

    "Context reflected in output" (step 5) is a semantic check we can't assert
    deterministically via AX (the note normalises content); we assert the
    context was successfully ATTACHED, which is the automatable acceptance edge.

Run from Ghostty, logged in, Heidi foreground:
    .venv/bin/python -m pytest tests/scribe/upload/test_tcd008_transcribe_audio_context_upload.py -v -s
"""
import pytest

from _scribe_cases import (
    check_context_reflected_in_note,
    check_context_uploaded,
    check_upload_accepted,
    check_upload_note_generated,
    check_upload_transcript_accuracy,
    check_upload_transcription_generated,
    make_upload_fixture,
)
from _scribe_flow import KEYWORDS_5MIN

pytestmark = [pytest.mark.scribe, pytest.mark.upload, pytest.mark.slow]

# Markers unique to the uploaded context PDF (MCMI-IV report for 'Robert
# Sample'). Used by the SOFT context-reflection check — their presence in the
# note proves the context doc influenced generation. Non-deterministic, so the
# check is report-only.
CONTEXT_MARKERS = [
    "MCMI", "Millon", "Robert Sample", "Personality Disorder",
    "Grossman", "Antisocial", "Previous Clinical Assessment",
]

result = make_upload_fixture(
    flow="tcd008", mode="transcribe", clip="consult_5min.wav",
    keywords=KEYWORDS_5MIN, transcript_threshold=0.6,
    context_clip="context_sample.pdf",
)


@pytest.mark.timeout(600)
def test_context_uploaded(result):
    check_context_uploaded(result)


@pytest.mark.timeout(600)
def test_audio_upload_accepted(result):
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


@pytest.mark.timeout(600)
def test_context_reflected_in_note(result):
    check_context_reflected_in_note(result, CONTEXT_MARKERS)
