"""Auto-login test.

Run from Ghostty (needs Screen Recording permission):
    pytest tests/test_login.py -v -s

Prereq: set the password once via .env.e2e or env var:
    export HEIDI_E2E_PASSWORD='your-staging-password'

This test:
  1. Connects to Heidi (launches if needed)
  2. If already logged in -> passes immediately
  3. If on login page -> drives the full Auth0 flow
  4. Asserts the sidebar (Scribe/Devices) is visible afterward
"""
import pytest
import xa11y

from login import LoginError, is_logged_in, is_on_login_page, perform_login

pytestmark = [pytest.mark.smoke, pytest.mark.slow]


def test_auto_login(heidi_app: xa11y.App, dump_tree):
    # Snapshot whatever state we start in (debugging aid)
    dump_tree("login_initial")

    if is_logged_in(heidi_app):
        # Already authenticated — nothing to do, but verify markers
        assert is_logged_in(heidi_app)
        return

    if not is_on_login_page(heidi_app):
        dump_tree("login_unknown_state")
        pytest.skip(
            "App is neither logged in nor on the login page — "
            "inspect reports/login_unknown_state.txt"
        )

    try:
        perform_login(heidi_app)
    except LoginError as e:
        dump_tree("login_failed")
        pytest.fail(f"Login failed: {e}\nSee reports/login_failed.txt")

    # Verify we landed in the app
    assert is_logged_in(heidi_app), "Login completed but no sidebar markers found"
    dump_tree("login_success")


def test_logged_in_shows_sidebar(heidi_app: xa11y.App):
    """After login, the main navigation should be present."""
    if not is_logged_in(heidi_app):
        pytest.skip("Not logged in — run test_auto_login first")

    # At least one core nav item should be visible
    found = any(
        heidi_app.locator(sel).exists()
        for sel in [
            "static_text[value='Scribe']",
            "static_text[value='Devices']",
            "static_text[value='Patients']",
        ]
    )
    assert found, "No sidebar navigation items found after login"
