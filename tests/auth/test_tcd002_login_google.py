"""TCD002 - Login using Google (Happy Case, Auth, priority: high).

Input:
    A Google account (interactive — Google's consent screen requires a human
    and blocks automation / headless browsers).

Output / acceptance:
    test_google_entry_present  ☑  the "Google" sign-in button is on the login
                                  screen
    test_google_launches       ☑  pressing it kicks off the external Google
                                  OAuth flow (a browser window opens)

SCOPE NOTE — why this stops at the entry point:
    The Google OAuth page renders in an external browser (Chrome) which does
    NOT expose its web content to the macOS accessibility tree (no
    --force-renderer-accessibility). Google also actively blocks automated
    sign-in (bot detection, 2FA/consent). So the automatable, deterministic,
    idempotent part is: the option exists and launches. Completing the Google
    sign-in is a MANUAL step — run this, then finish the browser flow by hand
    to confirm end-to-end.

    test_google_launches is guarded by RUN_MANUAL=1 because pressing it opens a
    real browser window / OAuth attempt as a side effect.

Run from Ghostty:
    .venv/bin/python3.14 -m pytest tests/auth/test_tcd002_login_google.py -v
    RUN_MANUAL=1 .venv/bin/python3.14 -m pytest tests/auth/test_tcd002_login_google.py -v
"""
import os

import pytest
import xa11y

from _cases import check_entry_point_present
from _flow import GOOGLE_MARKERS, verify_entry_point_launches
from lib.login import is_logged_in, is_on_login_page
from pages import AuthPage

pytestmark = [pytest.mark.auth]

RUN_MANUAL = os.environ.get("RUN_MANUAL") == "1"


def _require_login_screen(app: xa11y.App) -> AuthPage:
    if is_logged_in(app):
        pytest.skip("Already logged in — sign out to test the Google entry point")
    if not is_on_login_page(app):
        pytest.skip("Not on the login page — cannot test the Google entry point")
    return AuthPage(app)


def test_google_entry_present(heidi_app: xa11y.App):
    page = _require_login_screen(heidi_app)
    check_entry_point_present(page.has_google_button(), "Google sign-in")


@pytest.mark.skipif(
    not RUN_MANUAL,
    reason="Opens a real Google OAuth browser window; set RUN_MANUAL=1 to run.",
)
def test_google_launches(heidi_app: xa11y.App):
    """Pressing Google should actually open the Google OAuth page in a browser
    (verified by the browser window title), not merely accept a click."""
    page = _require_login_screen(heidi_app)
    launched, title = verify_entry_point_launches(page.press_google, GOOGLE_MARKERS)
    assert launched, (
        "Google sign-in did not open a Google OAuth browser window "
        f"(last browser title seen: {title!r})"
    )
