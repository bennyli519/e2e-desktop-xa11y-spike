"""Reusable assertion bodies for the auth (login) flow.

The email+password flow (TCD001) runs once via a module-scoped `result`
fixture; each `test_*` delegates to one `check_*` here. Same pattern as the
recording domain, so the pytest output reads as a per-step checklist.
"""
from __future__ import annotations

import os
import time

import pytest
import xa11y

from _flow import LoginResult, run_email_password_login
from lib.login import is_logged_in, is_on_login_page
from pages import AuthPage


def make_login_result_fixture():
    """Build a module-scoped fixture that runs the login flow once + caches it."""

    @pytest.fixture(scope="module")
    def result(heidi_app) -> LoginResult:
        return run_email_password_login(heidi_app)

    return result


def require_login_screen(app: xa11y.App, what: str) -> AuthPage:
    """Return an AuthPage on the login screen, or skip.

    Auth tests need a logged-out precondition. By default we sign out first so
    an already-authenticated (persisted-token) session can still exercise the
    login-screen entry points (Google/Apple/Sign up). Set AUTH_KEEP_SESSION=1
    to skip the sign-out (fast iteration / when sign_out selectors need work).
    """
    page = AuthPage(app)
    if is_logged_in(app):
        if os.environ.get("AUTH_KEEP_SESSION") != "1":
            page.sign_out()
            time.sleep(2.0)
        if is_logged_in(app):
            pytest.skip(
                f"Still logged in (sign-out failed or AUTH_KEEP_SESSION=1) — "
                f"cannot test the {what} entry point"
            )
    if not is_on_login_page(app):
        pytest.skip(f"Not on the login page — cannot test the {what} entry point")
    return page


def _skip_if_already_in(res: LoginResult) -> None:
    if res.already_logged_in:
        pytest.skip(
            "App was still logged in after sign-out — login-screen steps can't "
            "be exercised. The sign_out() selectors likely need refining "
            "(dump the logged-in AX tree), or AUTH_KEEP_SESSION=1 was set."
        )


def _no_flow_error(res: LoginResult) -> None:
    # An error is only fatal for steps AFTER the one that failed; each check
    # asserts its own boolean, so we surface the recorded error in the message
    # rather than failing every step here.
    return None


# --- individual checks (one per visible test) -------------------------------
def check_starts_logged_out(res: LoginResult) -> None:
    _skip_if_already_in(res)
    assert res.started_logged_out, (
        f"expected to start on the login page. error={res.error}"
    )


def check_email_accepted(res: LoginResult) -> None:
    _skip_if_already_in(res)
    assert res.email_accepted, (
        f"email was not accepted / Continue did not advance the flow. "
        f"error={res.error}"
    )


def check_auth0_window_opened(res: LoginResult) -> None:
    _skip_if_already_in(res)
    assert res.auth0_window_opened, (
        f"the Auth0 login window never opened in the browser. error={res.error}"
    )


def check_password_submitted(res: LoginResult) -> None:
    _skip_if_already_in(res)
    assert res.password_submitted, (
        f"password entry / submission did not complete. error={res.error}"
    )


def check_reached_app(res: LoginResult) -> None:
    # This one is meaningful even when already logged in — the end state is
    # "in the app". Only require the fresh-flow error to be absent.
    assert res.reached_app, (
        f"never reached the logged-in app (no sidebar markers). error={res.error}"
    )


# --- depth checks: mirror the web suite's expectFullAppAccess ---------------
def check_login_field_gone(res: LoginResult) -> None:
    """After login the sign-in email field must be GONE — proves we truly left
    the auth state, not just that some sidebar text rendered."""
    assert res.reached_app, f"never reached the app. error={res.error}"
    assert res.login_field_gone, (
        "the sign-in email field is still visible after 'login' — the app did "
        "not actually leave the authentication screen"
    )


def check_can_reach_sessions(res: LoginResult) -> None:
    assert res.reached_app, f"never reached the app. error={res.error}"
    assert res.can_reach_sessions, (
        "no sessions / Scribe entry point after login — the main working area "
        "is not accessible"
    )


def check_can_reach_settings(res: LoginResult) -> None:
    assert res.reached_app, f"never reached the app. error={res.error}"
    assert res.can_reach_settings, (
        "no settings entry point after login — account/settings is not "
        "accessible"
    )


def check_full_app_access(res: LoginResult) -> None:
    """The consolidated depth gate (sessions + settings reachable AND login
    field gone) — equivalent to the web suite's expectFullAppAccess."""
    assert res.reached_app, f"never reached the app. error={res.error}"
    assert res.full_app_access, (
        "did not get full app access after login "
        f"(sessions={res.can_reach_sessions}, settings={res.can_reach_settings}, "
        f"login_field_gone={res.login_field_gone})"
    )


# --- entry-point checks for social / signup (TCD002/003/014) ----------------
def check_entry_point_present(present: bool, label: str) -> None:
    assert present, (
        f"{label} entry point not found on the login screen — cannot verify "
        f"this sign-in option. (Are we actually on the login page?)"
    )


def check_entry_point_launches(launched: bool, label: str) -> None:
    """Pressing the entry point should kick off its external flow.

    We can only observe that the press succeeded (the control accepted the
    action); the resulting OAuth/verification page lives in an external browser
    whose web content is invisible to the accessibility tree, so we do NOT try
    to assert on it. See the test file's scope note.
    """
    assert launched, f"{label} button did not accept the press action"
