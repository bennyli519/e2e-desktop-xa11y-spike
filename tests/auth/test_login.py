"""auth: automated Auth0 login flow.

Run from Ghostty (needs Screen Recording permission):
    pytest tests/auth/ -v -s

Prereq: password in .env.e2e (HEIDI_E2E_PASSWORD=...). Only needed for the
first login — the Auth0 token persists afterwards.

Flow: Heidi email -> Continue -> Chrome Auth0 password -> "Open Heidi?" -> app.
"""
import pytest
import xa11y

from lib.login import LoginError, is_logged_in, is_on_login_page, perform_login

# Full Auth0 flow (swift IME setup + char-by-char password + redirect polling)
# routinely exceeds the global 120s timeout on a cold first login. Give this
# case its own budget; it's a no-op once the Auth0 token persists.
pytestmark = [pytest.mark.auth, pytest.mark.slow, pytest.mark.timeout(300)]


def test_auto_login(heidi_app: xa11y.App, dump_tree):
    dump_tree("login_initial")

    if is_logged_in(heidi_app):
        assert is_logged_in(heidi_app)  # already authenticated
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

    assert is_logged_in(heidi_app), "Login completed but no sidebar markers found"
    dump_tree("login_success")


def test_logged_in_shows_sidebar(heidi_app: xa11y.App):
    if not is_logged_in(heidi_app):
        pytest.skip("Not logged in — run test_auto_login first")

    found = any(
        heidi_app.locator(sel).exists()
        for sel in [
            "button[name='Scribe']",
            "combo_box[name='Devices']",
            "static_text[value='Patients']",
        ]
    )
    assert found, "No sidebar navigation items found after login"
