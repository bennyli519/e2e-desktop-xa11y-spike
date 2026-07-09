"""Page Object: the Heidi desktop login / auth screen.

Selectors for the pre-auth screen live here ONLY. The actual Auth0 email +
password drive lives in lib/login.py (it spans the Tauri app AND the external
browser, so it's infrastructure, not a single-screen Page Object). This class
covers what the login screen itself exposes:

  - the email field + Continue button (the email/password entry point)
  - the social sign-in buttons (Google / Apple / Microsoft / SSO / Passkey)
  - the "Sign up" link

Button names come from visible text today (no aria-labels yet), so every
lookup uses a comma-separated fallback chain — the portable xa11y pattern.
"""
import time

import xa11y

from lib import click_first_match


class AuthPage:
    def __init__(self, app: xa11y.App):
        self.app = app

    # -- state ------------------------------------------------------------
    def email_field(self) -> xa11y.Locator:
        return self.app.locator(
            "text_field[name='name@company.com'], "
            "text_field[name*='email'], text_field[name*='Email'], "
            "text_field"
        )

    def has_email_field(self) -> bool:
        try:
            return self.email_field().exists()
        except Exception:
            return False

    def has_continue(self) -> bool:
        return self.app.locator("button[name='Continue']").exists()

    def _has_any(self, selectors: list[str]) -> bool:
        for sel in selectors:
            try:
                if self.app.locator(sel).exists():
                    return True
            except Exception:
                continue
        return False

    # -- social / signup entry points ------------------------------------
    # These open external OAuth flows (Google/Apple/Microsoft) whose web
    # content is NOT exposed to the AX tree, so we can only verify the button
    # is present and (optionally) that pressing it launches a browser window.
    GOOGLE_SELECTORS = [
        "button[name='Google']",
        "button[name*='Google']",
        "button[name*='google']",
        "static_text[value*='Google']",
    ]
    APPLE_SELECTORS = [
        "button[name='Apple']",
        "button[name*='Apple']",
        "button[name*='apple']",
        "static_text[value*='Apple']",
    ]
    SIGNUP_SELECTORS = [
        "link[name='Sign up']",
        "button[name='Sign up']",
        "link[name*='Sign up']",
        "button[name*='Sign up']",
        "static_text[value*='Sign up']",
    ]

    def has_google_button(self) -> bool:
        return self._has_any(self.GOOGLE_SELECTORS)

    def has_apple_button(self) -> bool:
        return self._has_any(self.APPLE_SELECTORS)

    def has_signup_link(self) -> bool:
        return self._has_any(self.SIGNUP_SELECTORS)

    def press_google(self) -> bool:
        return click_first_match(self.app, self.GOOGLE_SELECTORS)

    def press_apple(self) -> bool:
        return click_first_match(self.app, self.APPLE_SELECTORS)

    def press_signup(self) -> bool:
        ok = click_first_match(self.app, self.SIGNUP_SELECTORS)
        if ok:
            time.sleep(1.0)
        return ok
