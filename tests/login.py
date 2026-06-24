"""Auto-login for Heidi desktop app using xa11y.

Auth0 flow (mirrors the cua-driver version but uses xa11y selectors):
  1. Type email in the Tauri login page
  2. Press Enter -> Auth0 opens in the default browser (Chrome)
  3. Find the browser's Auth0 window via system-root search, type password
  4. Submit -> redirect back to the Tauri app
  5. Wait until the sidebar (Scribe/Devices) appears

Credentials come from .env.e2e or environment variables:
  HEIDI_E2E_EMAIL     (default: benny@heidihealth.com)
  HEIDI_E2E_PASSWORD  (required for first login)

After the first login the Auth0 token persists, so later runs skip this.
"""
import os
import time
from pathlib import Path

import xa11y


class LoginError(Exception):
    pass


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------
def _load_env_file() -> dict[str, str]:
    """Read .env.e2e (gitignored) into a dict."""
    env: dict[str, str] = {}
    env_file = Path(__file__).resolve().parent.parent / ".env.e2e"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip()
    return env


def get_credentials() -> tuple[str, str]:
    file_env = _load_env_file()
    email = os.environ.get("HEIDI_E2E_EMAIL") or file_env.get("HEIDI_E2E_EMAIL") or "benny@heidihealth.com"
    password = os.environ.get("HEIDI_E2E_PASSWORD") or file_env.get("HEIDI_E2E_PASSWORD", "")
    if not password:
        raise LoginError(
            "Missing password. Set HEIDI_E2E_PASSWORD env var or create "
            ".env.e2e with HEIDI_E2E_PASSWORD=***. Only needed for first login."
        )
    return email, password


# ---------------------------------------------------------------------------
# State detection
# ---------------------------------------------------------------------------
LOGGED_IN_MARKERS = [
    "static_text[value='Scribe']",
    "static_text[value='Devices']",
    "static_text[value*='Transcribe']",
]

LOGIN_PAGE_MARKERS = [
    "text_field",                       # email input
    "static_text[value*='Log in']",
    "static_text[value*='Sign in']",
    "static_text[value*='email']",
]


def is_logged_in(app: xa11y.App) -> bool:
    for sel in LOGGED_IN_MARKERS:
        if app.locator(sel).exists():
            return True
    return False


def is_on_login_page(app: xa11y.App) -> bool:
    for sel in LOGIN_PAGE_MARKERS:
        if app.locator(sel).exists():
            return True
    return False


# ---------------------------------------------------------------------------
# Login flow
# ---------------------------------------------------------------------------
def perform_login(app: xa11y.App, timeout: float = 90.0) -> None:
    """Drive the full Auth0 login across Tauri + browser. No-op if already in."""
    if is_logged_in(app):
        return

    email, password = get_credentials()

    # ── Step 1: email in the Tauri login page ──────────────────────────────
    email_field = app.locator("text_field")
    email_field.wait_visible(timeout=15.0)
    email_field.press()           # focus
    email_field.set_value(email)  # set_value is more reliable than type_text
    time.sleep(0.5)

    # The Continue button is React-driven; pressing Enter is most reliable.
    # Use InputSim for a real Enter keystroke into the focused field.
    sim = xa11y.input_sim()
    sim.press("Enter")

    # ── Step 2: wait for the Auth0 browser window ──────────────────────────
    time.sleep(4)  # let the browser open + Auth0 load

    auth0 = _find_auth0_app(timeout=20.0)
    if auth0 is None:
        raise LoginError("Auth0 browser window did not appear within 20s")

    # ── Step 3: password in the browser ────────────────────────────────────
    _fill_auth0_form(auth0, email, password)

    # ── Step 4: wait for redirect back to the app ──────────────────────────
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_logged_in(app):
            return
        time.sleep(2)

    raise LoginError("App did not reach logged-in state within timeout")


def _find_auth0_app(timeout: float) -> xa11y.App | None:
    """Find the browser app showing Auth0 by searching for password/email fields.

    Auth0 typically opens in the default browser. We look for any app (other
    than Heidi) that exposes a secure text field or an Auth0-looking form.
    """
    deadline = time.time() + timeout
    browser_names = ["Google Chrome", "Safari", "Arc", "Microsoft Edge", "Firefox"]
    while time.time() < deadline:
        for name in browser_names:
            try:
                candidate = xa11y.App.by_name(name, timeout=1.0)
            except xa11y.TimeoutError:
                continue
            # Does it currently show a login-ish form?
            for sel in [
                "secure_text_field",
                "text_field[name*='assword']",
                "static_text[value*='Auth0']",
                "static_text[value*='heidi']",
                "static_text[value*='Log']",
            ]:
                if candidate.locator(sel).exists():
                    return candidate
        time.sleep(1)
    return None


def _fill_auth0_form(browser: xa11y.App, email: str, password: str) -> None:
    """Handle Auth0's email-then-password (or direct password) form."""
    sim = xa11y.input_sim()

    # Optional email step (Auth0 sometimes re-asks)
    pw_field = browser.locator("secure_text_field")
    if not pw_field.exists():
        email_field = browser.locator("text_field")
        if email_field.exists():
            email_field.press()
            email_field.set_value(email)
            time.sleep(0.3)
            _click_submit(browser) or sim.press("Enter")
            time.sleep(3)

    # Password step
    pw_field = browser.locator("secure_text_field")
    if not pw_field.exists():
        # try by label
        pw_field = browser.locator("text_field[name*='assword']")
    pw_field.wait_visible(timeout=10.0)
    pw_field.press()
    pw_field.set_value(password)
    time.sleep(0.3)

    if not _click_submit(browser):
        sim.press("Enter")

    # Optional consent screen
    time.sleep(3)
    for label in ["Accept", "Allow", "Continue"]:
        consent = browser.locator(f"button[name='{label}']")
        if consent.exists():
            consent.press()
            time.sleep(2)
            break


def _click_submit(browser: xa11y.App) -> bool:
    """Click a Continue/Log In/Sign In button. Returns True if one was found."""
    for label in ["Continue", "Log In", "Sign In", "Log in", "Sign in"]:
        btn = browser.locator(f"button[name='{label}']")
        if btn.exists():
            btn.press()
            return True
    return False
