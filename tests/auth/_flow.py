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

import time
from dataclasses import dataclass

import pytest
import xa11y

from lib.login import (
    LoginError,
    _find_auth0_window,
    _fill_auth0_form_via_input,
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

    try:
        if is_logged_in(heidi_app):
            res.already_logged_in = True
            res.reached_app = True
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

    except (LoginError, Exception) as e:  # keep the result usable for reporting
        res.error = repr(e)

    return res
