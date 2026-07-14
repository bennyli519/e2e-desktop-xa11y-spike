"""TCD003 - Login using Apple (Happy Case, Auth, priority: high).

Input:
    An Apple ID (interactive — Apple's sign-in requires a human, 2FA, and
    blocks automation).

Output / acceptance:
    test_apple_entry_present  ☑  the "Apple" sign-in button is on the login
                                 screen
    test_apple_launches       ☑  pressing it kicks off the external Apple
                                 sign-in flow (a browser window opens)

SCOPE NOTE — why this stops at the entry point:
    Same constraint as Google (TCD002): the Apple sign-in page renders in an
    external browser whose web content is invisible to the accessibility tree,
    and Apple ID sign-in requires interactive 2FA. The automatable part is: the
    option exists and launches. Completing the Apple sign-in is MANUAL.

    test_apple_launches is guarded by RUN_MANUAL=1 because pressing it opens a
    real browser / OAuth attempt as a side effect.

Run from Ghostty:
    .venv/bin/python3.14 -m pytest tests/auth/test_tcd003_login_apple.py -v
    RUN_MANUAL=1 .venv/bin/python3.14 -m pytest tests/auth/test_tcd003_login_apple.py -v
"""
import os

import pytest
import xa11y

from _cases import check_entry_point_present, require_login_screen
from _flow import APPLE_MARKERS, verify_entry_point_launches

pytestmark = [pytest.mark.auth]

RUN_MANUAL = os.environ.get("RUN_MANUAL") == "1"


def test_apple_entry_present(heidi_app: xa11y.App):
    page = require_login_screen(heidi_app, "Apple sign-in")
    check_entry_point_present(page.has_apple_button(), "Apple sign-in")


@pytest.mark.skipif(
    not RUN_MANUAL,
    reason="Opens a real Apple sign-in browser window; set RUN_MANUAL=1 to run.",
)
def test_apple_launches(heidi_app: xa11y.App):
    """Pressing Apple should actually open the Apple sign-in page in a browser
    (verified by the browser window title), not merely accept a click."""
    page = require_login_screen(heidi_app, "Apple sign-in")
    launched, title = verify_entry_point_launches(page.press_apple, APPLE_MARKERS)
    assert launched, (
        "Apple sign-in did not open an Apple sign-in browser window "
        f"(last browser title seen: {title!r})"
    )
