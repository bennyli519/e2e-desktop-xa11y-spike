"""Shared auth-flow engine for the core desktop login cases.

Mirrors the recording domain's design: the full email+password login flow is
SLOW (it spans the Tauri app AND an external browser, Auth0 round-trip, redirect
polling), so we must NOT re-run it per assertion. TCD001 runs the flow exactly
ONCE via a module-scoped `result` fixture, records each step into a
`LoginResult`, and the individual `test_*` functions each assert ONE step.

That gives the clean per-step checklist Benny wants:

    tests/auth/test_tcd001_login_email_password.py::test_starts_logged_out   PASSED
    ...::test_email_accepted            PASSED
    ...::test_auth0_window_opened       PASSED
    ...::test_password_submitted        PASSED
    ...::test_reached_app               PASSED

This module is NOT collected by pytest (filename doesn't match test_*.py).

The social cases (TCD002 Google, TCD003 Apple) and signup (TCD014) can only be
verified up to the entry point — their OAuth/verification web content lives in
an external browser that does NOT expose its DOM to the accessibility tree, and
they need real interactive credentials / are non-idempotent. So those cases
assert the ENTRY POINT (button present, launches an external flow) and stop
there. See each test file for the explicit scope note.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

import pytest
import xa11y

from lib.login import (
    LoginError,
    _fill_auth0_form_via_input,
    _find_auth0_window,
    find_browser_window,
    get_credentials,
    is_logged_in,
    is_on_login_page,
)
from pages import AuthPage


# ---------------------------------------------------------------------------
# Result container — one per flow, cached for all that flow's assertions.
# ---------------------------------------------------------------------------
@dataclass
class LoginResult:
    started_logged_out: bool = False
    email_accepted: bool = False       # Continue accepted the email
    auth0_window_opened: bool = False  # browser Auth0 window appeared
    password_submitted: bool = False   # password typed + submitted, no crash
    reached_app: bool = False          # sidebar markers visible => logged in
    already_logged_in: bool = False    # session was already authenticated
    # Depth checks (mirror the web suite's expectFullAppAccess) — asserted
    # AFTER reaching the app, so a shallow "some sidebar text appeared" can't
    # pass for a genuine login.
    login_field_gone: bool = False     # sign-in email field is no longer shown
    can_reach_sessions: bool = False   # sessions / Scribe entry point present
    can_reach_settings: bool = False   # settings entry point present
    full_app_access: bool = False      # all three depth checks pass
    error: str | None = None


# Registry the terminal-summary hook reads to print the per-flow table.
FLOW_RESULTS: dict[str, LoginResult] = {}


def run_email_password_login(heidi_app: xa11y.App) -> LoginResult:
    """Run ONE full email+password (TCD001) login flow, step by step.

    Never raises for a flow-level failure: it records what happened into the
    result so each downstream assertion reports its own PASS/FAIL cleanly.

    If the app is already logged in we can't exercise the login screen, so the
    flow marks `already_logged_in` and the step assertions skip. To force a
    real run, sign out first (or clear the persisted Auth0 token).
    """
    res = LoginResult()
    FLOW_RESULTS["TCD001"] = res

    def _capture_depth(page: AuthPage) -> None:
        """Record the expectFullAppAccess-equivalent depth checks.

        Settle briefly first — after the redirect the sidebar can take a
        moment to finish mounting all footer/settings controls.
        """
        for _ in range(10):
            page.app  # noqa: B018 — keep the handle warm
            if page.has_full_app_access():
                break
            time.sleep(1.0)
        res.can_reach_sessions = page.can_reach_sessions()
        res.can_reach_settings = page.can_reach_settings()
        res.login_field_gone = not page.has_login_field()
        res.full_app_access = (
            res.can_reach_sessions
            and res.can_reach_settings
            and res.login_field_gone
        )

    try:
        # Auth tests need a LOGGED-OUT precondition (the login screen). By
        # default we sign out first so the full fresh flow (email -> Auth0 ->
        # password -> redirect) is genuinely exercised — otherwise the
        # persisted token leaves us already logged in and the login STEPS skip,
        # which is a false pass for an OAuth test. Set AUTH_KEEP_SESSION=1 to
        # skip the sign-out (fast iteration / when sign_out selectors need work).
        if os.environ.get("AUTH_KEEP_SESSION") != "1" and is_logged_in(heidi_app):
            AuthPage(heidi_app).sign_out()
            time.sleep(2.0)

        if is_logged_in(heidi_app):
            res.already_logged_in = True
            res.reached_app = True
            _capture_depth(AuthPage(heidi_app))
            return res

        if not is_on_login_page(heidi_app):
            res.error = (
                "App is neither logged in nor on the login page — "
                "cannot run the login flow"
            )
            return res

        res.started_logged_out = True
        page = AuthPage(heidi_app)
        email, password = get_credentials()

        # ── Step 1: email in the Tauri login page ──────────────────────────
        email_field = page.email_field()
        email_field.wait_visible(timeout=15.0)
        try:
            email_field.focus()
        except xa11y.ActionNotSupportedError:
            pass
        email_field.set_value(email)
        time.sleep(0.5)

        sim = xa11y.input_sim()
        continue_btn = heidi_app.locator("button[name='Continue']")
        if continue_btn.exists():
            continue_btn.press()
            time.sleep(1)
            if is_on_login_page(heidi_app):
                # React button ignored AXPress — submit with a real Enter.
                try:
                    email_field.focus()
                except xa11y.ActionNotSupportedError:
                    pass
                sim.press("Enter")
        else:
            sim.press("Enter")

        # ── Step 2: wait for the Auth0 browser window ──────────────────────
        time.sleep(4)
        browser, auth_window = _find_auth0_window(timeout=20.0)
        res.email_accepted = browser is not None
        if browser is None:
            res.error = "Auth0 browser window did not appear within 20s"
            return res
        res.auth0_window_opened = True

        # ── Step 3: password in the browser + "Open Heidi?" confirm ────────
        _fill_auth0_form_via_input(browser, auth_window, email, password)
        res.password_submitted = True

        # ── Step 4: wait for redirect back to the app ──────────────────────
        deadline = time.time() + 90.0
        while time.time() < deadline:
            if is_logged_in(heidi_app):
                res.reached_app = True
                break
            time.sleep(2)
        if not res.reached_app:
            res.error = "App did not reach logged-in state within 90s"
            return res

        # ── Step 5: depth — real app access, not just a sidebar marker ──────
        _capture_depth(page)

    except (LoginError, Exception) as e:  # keep the result usable for reporting
        res.error = repr(e)

    return res


# ---------------------------------------------------------------------------
# Shared helper for the social / signup entry-point cases (TCD002/003/014).
# ---------------------------------------------------------------------------
# Default window-title markers that indicate the external flow actually opened.
GOOGLE_MARKERS = ["accounts.google.com", "sign in - google", "google accounts"]
APPLE_MARKERS = ["appleid.apple.com", "apple account", "sign in with apple"]
SIGNUP_MARKERS = [
    "auth.heidihealth.com",
    "signup",
    "sign up",
    "login/identifier",
    "authorize",
]


def verify_entry_point_launches(
    press_fn,
    markers: list[str],
    timeout: float = 20.0,
) -> tuple[bool, str | None]:
    """Press an entry point, then confirm an external browser window whose
    title matches `markers` actually appeared.

    This is DEEPER than "the button accepted a press": it proves the OAuth /
    signup flow genuinely launched. We can't read the page CONTENT (Chrome's
    web area is invisible to AX) but the window TITLE carries the destination
    URL, which is enough to assert the right flow started.

    Returns (launched, matched_title). `launched` is True only if both the
    press succeeded AND a matching browser window appeared.
    """
    pressed = press_fn()
    if not pressed:
        return False, None
    _app, _win, title = find_browser_window(markers, timeout=timeout)
    return (title is not None), title
