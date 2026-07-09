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
from _flow import SIGNUP_MARKERS, verify_entry_point_launches
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
    """Pressing Sign up should lead into the sign-up flow.

    Depth: either we leave the plain login screen in-app, OR an external
    browser opens the Auth0 sign-up page (title match) — mirrors how the web
    suite proves the IdP flow started. Completing registration (email
    verification via Mailosaur, onboarding) is a MANUAL step beyond this.
    """
    page = _require_login_screen(heidi_app)
    launched, title = verify_entry_point_launches(page.press_signup, SIGNUP_MARKERS)
    left_login_screen = not page.has_login_field()
    assert launched or left_login_screen, (
        "pressing Sign up neither opened the sign-up page in a browser "
        f"(last title: {title!r}) nor moved off the login screen"
    )
