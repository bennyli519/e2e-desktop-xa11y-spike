"""TCD001 - Login with Email and Password (Happy Case, Auth, priority: high).

Input:
    HEIDI_E2E_EMAIL + HEIDI_E2E_PASSWORD from .env.e2e (test account).

Output / acceptance (verified as a per-step checklist):
    test_starts_logged_out    ☑  app opens on the login screen
    test_email_accepted       ☑  entering the email + Continue advances the flow
    test_auth0_window_opened  ☑  the Auth0 login opens in the browser
    test_password_submitted   ☑  the password is entered and submitted
    test_reached_app          ☑  redirect lands back in the app (sidebar shown)
    test_login_field_gone     ☑  the sign-in email field is gone (truly authed)
    test_can_reach_sessions   ☑  the sessions / Scribe working area is reachable
    test_can_reach_settings   ☑  settings / account is reachable
    test_full_app_access      ☑  consolidated depth gate (== web expectFullAppAccess)

The last four are DEPTH checks mirroring the web Playwright suite's
`expectFullAppAccess` — a genuine login means real app access, not just that
some sidebar text appeared.

The flow runs ONCE (module-scoped `result` fixture); each test reads its cache.

Note: after the first successful login the Auth0 token persists, so a re-run
finds the app already logged in and the login-screen steps SKIP (only
test_reached_app still asserts the end state). To force a full run, sign out /
clear the persisted token first.

Run from Ghostty (needs Screen Recording permission), first login needs the
password in .env.e2e:
    .venv/bin/python3.14 -m pytest tests/auth/test_tcd001_login_email_password.py -v -s
"""
import pytest

from _cases import (
    check_auth0_window_opened,
    check_can_reach_sessions,
    check_can_reach_settings,
    check_email_accepted,
    check_full_app_access,
    check_login_field_gone,
    check_password_submitted,
    check_reached_app,
    check_starts_logged_out,
    make_login_result_fixture,
)

pytestmark = [pytest.mark.auth, pytest.mark.slow, pytest.mark.timeout(300)]

result = make_login_result_fixture()


def test_starts_logged_out(result):
    check_starts_logged_out(result)


def test_email_accepted(result):
    check_email_accepted(result)


def test_auth0_window_opened(result):
    check_auth0_window_opened(result)


def test_password_submitted(result):
    check_password_submitted(result)


def test_reached_app(result):
    check_reached_app(result)


def test_login_field_gone(result):
    check_login_field_gone(result)


def test_can_reach_sessions(result):
    check_can_reach_sessions(result)


def test_can_reach_settings(result):
    check_can_reach_settings(result)


def test_full_app_access(result):
    check_full_app_access(result)
