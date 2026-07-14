"""TCD011 - Validate dictate session with short 5 min audio using USB headset
and disconnect mid session.  [PLACEHOLDER — skips; needs manual disconnect]

From the Desktop App 2.5.0 release plan:

    Feature: Dictate with USB headset disconnect mid session
      Given a USB headset is connected and active for input
      When the user starts a short dictate session
      And the USB headset is disconnected mid session
      Then the app should show a clear device error or fallback prompt
      And session behavior should be predictable without crashing

    Execution steps:
      1. Connect USB headset and start short dictate session.
      2. After capture starts, disconnect headset mid session.
      3. Observe in-app warning/error behavior.
      4. Verify app remains stable and recoverable.
      5. Validate whether partial output/session state is handled correctly.

WHY THIS SKIPS:
    Two reasons stack:
      a) needs a REAL USB headset (require_usb_headset), and
      b) needs a HUMAN to physically UNPLUG it mid-session (require_manual,
         gated by RUN_MANUAL=1). There is no reliable software way to yank a
         USB audio device mid-capture on macOS/Windows from the test process.

TODO to make this real (manual-assisted):
    1. Connect headset, set HEIDI_E2E_USB_HEADSET, run with RUN_MANUAL=1.
    2. Start a dictate session; once capture is confirmed, PROMPT the human to
       unplug the headset (input()/console prompt), then assert the app shows a
       device-error / fallback prompt (ScribePage.has_transcript_error or a new
       device-error selector) and does NOT crash (app still attached, tree
       non-empty). Validate partial session state handling.

Run (skips unless USB headset + RUN_MANUAL=1):
    RUN_MANUAL=1 HEIDI_E2E_USB_HEADSET="Jabra ..." \\
      .venv/bin/python -m pytest tests/scribe/usb-headset/test_tcd011_dictate_usb_disconnect.py -v
"""
import pytest

pytestmark = [
    pytest.mark.scribe, pytest.mark.usb_headset,
    pytest.mark.slow, pytest.mark.needs_manual,
]

_TODO = (
    "USB-headset mid-session disconnect (dictate) not yet implemented — needs "
    "a real headset AND a human to unplug it. See this file's docstring TODO."
)


def test_dictate_usb_headset_disconnect_mid_session(
    heidi_app, require_usb_headset, require_manual
):
    """PLACEHOLDER: start a dictate session on a USB headset, unplug it mid
    session, and assert a clear device error/fallback with no crash."""
    pytest.skip(_TODO)
