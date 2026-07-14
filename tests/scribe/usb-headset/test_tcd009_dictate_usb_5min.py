"""TCD009 - Validate dictate session with short 5 min audio using USB headset.
[PLACEHOLDER — skips without a real USB headset]

From the Desktop App 2.5.0 release plan:

    Feature: Dictate short audio with USB headset
      Given a USB headset is connected and selected as input
      When the user records/submits a short 5-minute dictate using USB headset
      Then the audio should be captured and processed correctly
      And dictated output should be generated without device errors

    Execution steps:
      1. Connect USB headset and set as input device.
      2. Start short dictate session (about 5 minutes).
      3. Complete session and submit processing.
      4. Verify audio quality and successful output.
      5. Confirm no device-switch or permission errors.

WHY THIS SKIPS:
    Needs a REAL USB headset connected as the input device — we can't inject a
    physical USB audio device in CI, and the whole point of the case is to
    exercise real external-device capture (not the BlackHole loopback the other
    recording cases use). The `require_usb_headset` fixture skips cleanly when
    no external input is present.

TODO to make this real (on a machine with a USB headset):
    1. Connect the headset. Set HEIDI_E2E_USB_HEADSET=<device name> so the
       guard and ScribePage.select_input_device target it precisely.
    2. Build the flow: select the headset as Heidi's input
       (ScribePage.select_input_device), start a dictate session, play the
       5-min consult clip THROUGH the headset (physically, or via a loopback
       cable), stop, and assert transcript/note completion + no device errors.
    3. Replace the body below with those steps (reuse _scribe_flow patterns).

Run (skips unless a USB headset is detected):
    HEIDI_E2E_USB_HEADSET="Jabra ..." \\
      .venv/bin/python -m pytest tests/scribe/usb-headset/test_tcd009_dictate_usb_5min.py -v
"""
import pytest

pytestmark = [pytest.mark.scribe, pytest.mark.usb_headset, pytest.mark.slow]

_TODO = (
    "USB-headset dictate flow not yet implemented — needs a real external "
    "input device. See this file's docstring TODO."
)


def test_dictate_short_audio_with_usb_headset(heidi_app, require_usb_headset):
    """PLACEHOLDER: with a USB headset selected as input, run a ~5-min dictate
    session and assert successful output with no device errors."""
    pytest.skip(_TODO)
