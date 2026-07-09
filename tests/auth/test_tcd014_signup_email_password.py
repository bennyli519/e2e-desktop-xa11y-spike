"""TCD014 - Sign up using email and password (Happy Case, Auth, priority: high).

Input:
    A NEW, previously-unregistered email + a password, plus email-verification
    (interactive — requires access to the inbox to confirm).

Output / acceptance:
    test_signup_entry_present  ☑  the "Sign up" link/button is on the login
                                  screen
    test_signup_navigates      ☑  pressing it moves off the login screen toward
                                  the sign-up flow

SCOPE NOTE — why this stops at the entry point:
    Sign-up is NON-IDEMPOTENT (each run would need a brand-new unused email) and
    completing it requires email verification via an external inbox — neither is
    safe to automate in a repeatable regression suite. The signup form itself
    also renders through the Auth0 browser flow (web content invisible to AX).
    So the automatable, repeatable part is: the entry point exists and leads
    into the sign-up flow. Completing registration is a MANUAL step.

    test_signup_navigates is guarded by RUN_MANUAL=1 because it navigates away
    from the login screen (a side effect for other tests in a shared session).

Run from Ghostty:
    .venv/bin/python3.14 -m pytest tests/auth/test_tcd014_signup_email_password.py -v
    RUN_MANUAL=1 .venv/bin/python3.14 -m pytest tests/auth/test_tcd014_signup_email_password.py -v
"""
import os

import pytest
import xa11y

from _cases import check_entry_point_present
from lib.login import is_logged_in, is_on_login_page
from pages import AuthPage

pytestmark = [pytest.mark.auth]

RUN_MANUAL = os.environ.get("RUN_MANUAL") == "1"


def _require_login_screen(app: xa11y.App) -> AuthPage:
    if is_logged_in(app):
        pytest.skip("Already logged in — sign out to test the Sign up entry point")
    if not is_on_login_page(app):
        pytest.skip("Not on the login page — cannot test the Sign up entry point")
    return AuthPage(app)


def test_signup_entry_present(heidi_app: xa11y.App):
    page = _require_login_screen(heidi_app)
    check_entry_point_present(page.has_signup_link(), "Sign up")


@pytest.mark.skipif(
    not RUN_MANUAL,
    reason="Navigates away from the login screen; set RUN_MANUAL=1 to run.",
)
def test_signup_navigates(heidi_app: xa11y.App):
    page = _require_login_screen(heidi_app)
    assert page.press_signup(), "Sign up did not accept the press action"
    # After pressing, we should no longer be sitting on the plain login screen.
    assert not page.has_continue() or not is_on_login_page(heidi_app), (
        "pressing Sign up did not move off the login screen"
    )
