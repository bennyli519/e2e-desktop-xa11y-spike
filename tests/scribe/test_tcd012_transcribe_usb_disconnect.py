"""TCD012 - Validate transcribe session with short 5 min audio using USB headset
and disconnect mid session.  [PLACEHOLDER — skips; needs manual disconnect]

From the Desktop App 2.5.0 release plan:

    Feature: Transcribe with USB headset disconnect mid session
      Given a USB headset is connected and active for input
      When the user starts a short transcribe session
      And the USB headset is disconnected mid session
      Then the app should show a clear device error or fallback prompt
      And session behavior should remain stable and predictable

    Execution steps:
      1. Connect USB headset and start short transcribe session.
      2. Disconnect headset during active capture.
      3. Observe warning/error and recovery behavior.
      4. Verify app stability and no crash.
      5. Validate partial transcript/session state handling.

WHY THIS SKIPS:
    Same as TCD011 — needs a REAL USB headset (require_usb_headset) AND a human
    to physically unplug it mid-session (require_manual, RUN_MANUAL=1). This is
    the TRANSCRIBE variant.

TODO to make this real:
    Follow TCD011's manual-assisted TODO, running the session in transcribe
    mode and asserting transcript/session state handling around the disconnect.

Run (skips unless USB headset + RUN_MANUAL=1):
    RUN_MANUAL=1 HEIDI_E2E_USB_HEADSET="Jabra ..." \\
      .venv/bin/python -m pytest tests/scribe/usb-headset/test_tcd012_transcribe_usb_disconnect.py -v
"""
import pytest

pytestmark = [
    pytest.mark.scribe, pytest.mark.usb_headset,
    pytest.mark.slow, pytest.mark.needs_manual,
]

_TODO = (
    "USB-headset mid-session disconnect (transcribe) not yet implemented — "
    "needs a real headset AND a human to unplug it. See TCD011's docstring TODO."
)


def test_transcribe_usb_headset_disconnect_mid_session(
    heidi_app, require_usb_headset, require_manual
):
    """PLACEHOLDER: start a transcribe session on a USB headset, unplug it mid
    session, and assert a clear device error/fallback with no crash."""
    pytest.skip(_TODO)
