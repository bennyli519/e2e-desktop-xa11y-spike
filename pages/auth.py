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

    # -- post-login depth checks -----------------------------------------
    # The web Playwright suite asserts "full app access" after login
    # (expectFullAppAccess): sessions reachable, settings reachable, and the
    # sign-in email field GONE. We mirror that depth here with role+name
    # selectors (data-testid is invisible to the AX tree, per CLAUDE.md).

    # A logged-out login screen still shows an email field; a logged-in app
    # must NOT. Used to prove we truly left the auth state, not just that some
    # sidebar text appeared.
    LOGIN_FIELD_SELECTORS = [
        "text_field[name='name@company.com']",
        "text_field[name*='email']",
        "text_field[name*='Email']",
        "button[name='Continue']",
    ]

    # Sessions list / Scribe entry point (the main working area).
    SESSIONS_SELECTORS = [
        "button[name='New session']",
        "button[name='Scribe']",
        "link[name='Scribe']",
        "button[name*='Transcribe']",
        "static_text[value='Scribe']",
    ]

    # Settings entry point (sidebar button OR the account/footer menu).
    SETTINGS_SELECTORS = [
        "button[name='Settings']",
        "link[name='Settings']",
        "combo_box[name='Settings']",
        "button[name='Help']",  # Help lives in the same footer cluster
        "combo_box[name='Help']",
        "static_text[value='Settings']",
    ]

    def has_login_field(self) -> bool:
        return self._has_any(self.LOGIN_FIELD_SELECTORS)

    def can_reach_sessions(self) -> bool:
        return self._has_any(self.SESSIONS_SELECTORS)

    def can_reach_settings(self) -> bool:
        return self._has_any(self.SETTINGS_SELECTORS)

    def has_full_app_access(self) -> bool:
        """Mirror the web suite's expectFullAppAccess: sessions + settings
        reachable AND the login field gone."""
        return (
            self.can_reach_sessions()
            and self.can_reach_settings()
            and not self.has_login_field()
        )

    # -- sign out (to force a fresh login run) ----------------------------
    # Verified against the real AX tree (2026-07-09): the account control is a
    # COMBO_BOX at the bottom-left whose name contains the signed-in email:
    #   combo_box name='b\n<email> ... <email>'
    # Pressing it opens a menu with Team (link) / Settings (button) / Log out.
    LOGOUT_ITEM_SELECTORS = [
        "button[name='Log out']",
        "button[name*='Log out']",
        "menu_item[name='Log out']",
        "menu_item[name*='Log out']",
        "link[name='Log out']",
        "link[name*='Log out']",
        "static_text[value='Log out']",
        "static_text[value*='Log out']",
        # casing / wording fallbacks
        "button[name*='Logout']",
        "menu_item[name*='Logout']",
        "button[name*='Sign out']",
    ]

    def _account_menu_selectors(self, email: str | None) -> list[str]:
        """Selectors for the bottom-left account control that opens the menu.

        Confirmed role is combo_box; keep button/static_text as fallbacks and
        always include generic '@'-containing variants.
        """
        sels: list[str] = []
        if email:
            for role in ("combo_box", "button", "static_text"):
                key = "value" if role == "static_text" else "name"
                sels.append(f"{role}[{key}*='{email}']")
        sels += [
            "combo_box[name*='@']",
            "button[name*='@']",
            "static_text[value*='@']",
        ]
        return sels

    def _click_logout_item(self) -> bool:
        return click_first_match(self.app, self.LOGOUT_ITEM_SELECTORS)

    def sign_out(self, email: str | None = None) -> bool:
        """Best-effort sign out so a fresh login can be exercised.

        Opens the bottom-left account menu (combo_box labelled with the email),
        then clicks "Log out". Returns True once the login field is back.

        Pass the signed-in email to target the account control precisely; if
        omitted we fall back to any footer control whose label contains '@'.
        """
        # 1. Logout item might already be visible (menu left open).
        if self._click_logout_item():
            time.sleep(2.0)
            if self.has_login_field():
                return True

        # 2. Open the account menu ONCE, then click Log out. We must not press a
        #    second account selector on failure — the control is a combo_box and
        #    a second press TOGGLES the menu shut. So press the first matching
        #    selector only, then attempt logout (with one settle-and-retry).
        opened = False
        for sel in self._account_menu_selectors(email):
            try:
                loc = self.app.locator(sel)
                if not loc.exists():
                    continue
                loc.press()
                opened = True
                break
            except Exception:
                continue

        if opened:
            for _ in range(3):  # menu (incl. Log out) may mount slightly late
                time.sleep(1.0)
                if self._click_logout_item():
                    time.sleep(2.0)
                    if self.has_login_field():
                        return True
        return self.has_login_field()
