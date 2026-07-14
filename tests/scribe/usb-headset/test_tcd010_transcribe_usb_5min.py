"""TCD010 - Validate transcribe session with short 5 min audio using USB headset.
[PLACEHOLDER — skips without a real USB headset]

From the Desktop App 2.5.0 release plan:

    Feature: Transcribe short audio with USB headset
      Given a USB headset is connected and selected as input
      When the user records/submits a short 5-minute transcribe session using
        USB headset
      Then audio should be captured and processed correctly
      And transcript output should be generated without device errors

    Execution steps:
      1. Connect USB headset and set as input device.
      2. Start short transcribe session (about 5 minutes).
      3. Complete session and submit processing.
      4. Verify transcript completeness and quality.
      5. Confirm no device input errors are shown.

WHY THIS SKIPS:
    Same as TCD009 — needs a REAL USB headset as input device. This is the
    TRANSCRIBE variant. `require_usb_headset` skips cleanly when no external
    input is present.

TODO to make this real:
    Follow TCD009's TODO, running the session in transcribe mode.

Run (skips unless a USB headset is detected):
    HEIDI_E2E_USB_HEADSET="Jabra ..." \\
      .venv/bin/python -m pytest tests/scribe/usb-headset/test_tcd010_transcribe_usb_5min.py -v
"""
import pytest

pytestmark = [pytest.mark.scribe, pytest.mark.usb_headset, pytest.mark.slow]

_TODO = (
    "USB-headset transcribe flow not yet implemented — needs a real external "
    "input device. See TCD009's docstring TODO."
)


def test_transcribe_short_audio_with_usb_headset(heidi_app, require_usb_headset):
    """PLACEHOLDER: with a USB headset selected as input, run a ~5-min
    transcribe session and assert transcript completion with no device errors."""
    pytest.skip(_TODO)
