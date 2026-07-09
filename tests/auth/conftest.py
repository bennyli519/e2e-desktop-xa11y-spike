"""auth domain: shared config + demo-friendly reporting.

This domain covers the core desktop login test cases (from the Desktop App
Release template, "Main functionalities" → Auth):

    test_tcd001_login_email_password.py  TCD001  full email+password login
    test_tcd002_login_google.py          TCD002  Google sign-in (entry point)
    test_tcd003_login_apple.py           TCD003  Apple sign-in  (entry point)
    test_tcd014_signup_email_password.py TCD014  Sign up        (entry point)

TCD001 runs the full flow ONCE (module-scoped `result` fixture) and exposes one
visible test per step (starts-logged-out / email-accepted / auth0-window-opened
/ password-submitted / reached-app) so the pytest output reads as a checklist.

TCD002/003/014 depend on external OAuth / email verification that can't be
driven through the accessibility tree, so they assert the ENTRY POINT only
(button present + launches); the launch/navigate steps are RUN_MANUAL=1 gated.

Run from Ghostty (needs Accessibility + Screen Recording), Heidi foreground:

    .venv/bin/python3.14 -m pytest tests/auth/ -v          # all auth cases
    .venv/bin/python3.14 -m pytest tests/auth/test_tcd001_login_email_password.py -v

An HTML report is written to reports/report.html by default (see pyproject).
"""
from __future__ import annotations

from _flow import FLOW_RESULTS, LoginResult

_CHECK = "\u2713"   # ✓
_CROSS = "\u2717"   # ✗
_DASH = "\u2014"    # —

_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def _flow_lines(res: LoginResult) -> list[tuple[str, bool | None, str]]:
    """(label, ok, detail) rows for the TCD001 login flow."""
    if res.already_logged_in:
        return [
            ("reached app", res.reached_app, "already logged in (steps skipped)"),
            ("login field gone", res.login_field_gone, ""),
            ("can reach sessions", res.can_reach_sessions, ""),
            ("can reach settings", res.can_reach_settings, ""),
            ("full app access", res.full_app_access,
             "" if res.full_app_access else "depth gate"),
        ]
    if res.error and not res.started_logged_out:
        return [("flow could not start", False, res.error[:60])]

    return [
        ("starts logged out", res.started_logged_out, ""),
        ("email accepted", res.email_accepted, ""),
        ("auth0 window opened", res.auth0_window_opened, ""),
        ("password submitted", res.password_submitted, ""),
        ("reached app", res.reached_app,
         res.error[:60] if (res.error and not res.reached_app) else ""),
        ("login field gone", res.login_field_gone, ""),
        ("can reach sessions", res.can_reach_sessions, ""),
        ("can reach settings", res.can_reach_settings, ""),
        ("full app access", res.full_app_access,
         "" if res.full_app_access else "depth gate"),
    ]


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print a demo-friendly checklist for the TCD001 login flow."""
    res = FLOW_RESULTS.get("TCD001")
    if res is None:
        return

    tr = terminalreporter
    tr.write_line("")
    tr.write_line(f"{_BOLD}{'=' * 66}{_RESET}")
    tr.write_line(f"{_BOLD}  AUTH E2E — TCD001 LOGIN FLOW{_RESET}")
    tr.write_line(f"{_BOLD}{'=' * 66}{_RESET}")

    rows = _flow_lines(res)
    flow_ok = all(ok for _, ok, _ in rows if ok is not None)
    head_colour = _GREEN if flow_ok else _RED
    head_mark = _CHECK if flow_ok else _CROSS
    tr.write_line("")
    tr.write_line(
        f"{head_colour}{_BOLD}{head_mark} email + password login{_RESET}"
    )
    for label, ok, detail in rows:
        if ok is None:
            mark, colour = _DASH, _YELLOW
        elif ok:
            mark, colour = _CHECK, _GREEN
        else:
            mark, colour = _CROSS, _RED
        line = f"    {colour}{mark}{_RESET} {label:<24}"
        if detail:
            line += f" {_DIM}{detail}{_RESET}"
        tr.write_line(line)

    tr.write_line("")
    tr.write_line(f"{_BOLD}{'=' * 66}{_RESET}")
    tr.write_line(
        f"  {_DIM}legend:{_RESET} {_GREEN}{_CHECK} pass{_RESET}  "
        f"{_RED}{_CROSS} fail{_RESET}  "
        f"{_YELLOW}{_DASH} skipped (already logged in / n/a){_RESET}"
    )
    tr.write_line(f"{_BOLD}{'=' * 66}{_RESET}")
    tr.write_line("")
