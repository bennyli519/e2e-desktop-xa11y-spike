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
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip()
    return env


def get_credentials() -> tuple[str, str]:
    # .env.e2e wins over env vars — a stale exported HEIDI_E2E_PASSWORD in the
    # shell silently shadowed the file and corrupted the password during the
    # spike, so the file is the source of truth.
    file_env = _load_env_file()
    email = (
        file_env.get("HEIDI_E2E_EMAIL")
        or os.environ.get("HEIDI_E2E_EMAIL")
        or "benny@heidihealth.com"
    )
    password = file_env.get("HEIDI_E2E_PASSWORD") or os.environ.get("HEIDI_E2E_PASSWORD", "")
    if not password:
        raise LoginError(
            "Missing password. Create .env.e2e with HEIDI_E2E_PASSWORD=***. "
            "Only needed for first login."
        )
    return email, password


def _force_abc_input_source() -> None:
    """Force the active keyboard input source to a Latin/ABC layout.

    A Chinese IME intercepts ASCII keystrokes (e.g. 'a1' -> '啊') and corrupts
    typed passwords. Pick the first available Latin layout via the TIS API.
    """
    import subprocess

    swift = r'''
    import Carbon
    let preferred = [
        "com.apple.keylayout.ABC",
        "com.apple.keylayout.US",
        "com.apple.keylayout.USExtended",
        "com.apple.keylayout.British",
    ]
    guard let cf = TISCreateInputSourceList(nil, false)?.takeRetainedValue(),
          let sources = cf as? [TISInputSource] else { exit(0) }
    func id(_ s: TISInputSource) -> String? {
        guard let ptr = TISGetInputSourceProperty(s, kTISPropertyInputSourceID) else { return nil }
        return Unmanaged<CFString>.fromOpaque(ptr).takeUnretainedValue() as String
    }
    for want in preferred {
        if let s = sources.first(where: { id($0) == want }) {
            TISSelectInputSource(s); exit(0)
        }
    }
    if let s = sources.first(where: { (id($0) ?? "").hasPrefix("com.apple.keylayout.") }) {
        TISSelectInputSource(s)
    }
    '''
    try:
        subprocess.run(["swift", "-"], input=swift, capture_output=True, text=True, timeout=25)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# State detection
# ---------------------------------------------------------------------------
LOGGED_IN_MARKERS = [
    "button[name='Scribe']",
    "button[name='New session']",
    "button[name='Transcribe']",  # Windows / newer naming
    "combo_box[name='Devices']",  # macOS sidebar
    "static_text[value='Scribe']",  # legacy fallback
    "static_text[value='Devices']",
    "static_text[value*='Transcribe']",
]

LOGIN_PAGE_MARKERS = [
    "text_field[name='name@company.com']",
    "text_field[name*='email']",
    "text_field[name*='Email']",
    "text_field[value*='email']",
    "text_field[value*='Email']",
    "button[name='Continue']",
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
    try:
        email_field.focus()
    except xa11y.ActionNotSupportedError:
        pass
    email_field.set_value(email)  # set_value is more reliable than type_text
    time.sleep(0.5)

    # Click the Continue button (confirmed present in the login tree).
    # Fall back to a real Enter keystroke if the React button ignores AXPress.
    continue_btn = app.locator("button[name='Continue']")
    sim = xa11y.input_sim()
    if continue_btn.exists():
        continue_btn.press()
        time.sleep(1)
        # If still on the login page, the React button didn't fire — use Enter
        if is_on_login_page(app):
            try:
                email_field.focus()
            except xa11y.ActionNotSupportedError:
                pass
            sim.press("Enter")
    else:
        sim.press("Enter")

    # ── Step 2: wait for the Auth0 browser window ──────────────────────────
    time.sleep(4)  # let the browser open + Auth0 load

    browser, auth_window = _find_auth0_window(timeout=20.0)
    if browser is None:
        raise LoginError("Auth0 browser window did not appear within 20s")

    # ── Step 3: password in the browser ────────────────────────────────────
    # NOTE: Chrome does NOT expose web content to the AX tree (no
    # --force-renderer-accessibility), so we can't locate the password field
    # via selectors. We drive it with keyboard + coordinate clicks instead.
    _fill_auth0_form_via_input(browser, auth_window, email, password)

    # ── Step 4: wait for redirect back to the app ──────────────────────────
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_logged_in(app):
            return
        time.sleep(2)

    raise LoginError("App did not reach logged-in state within timeout")


def _find_auth0_window(timeout: float) -> tuple[xa11y.App | None, "xa11y.Element | None"]:
    """Find the browser app + window showing the Auth0 login.

    Chrome doesn't expose web content to AX, but the WINDOW TITLE is visible
    and contains the Auth0 URL (auth.heidihealth.com/.../login/password).
    We match on that.
    """
    markers = ["auth.heidihealth.com", "login/password", "login/identifier", "heidihealth"]
    browser_names = ["Google Chrome", "Safari", "Arc", "Microsoft Edge", "Firefox"]

    deadline = time.time() + timeout
    while time.time() < deadline:
        candidates: list[xa11y.App] = []
        for name in browser_names:
            try:
                candidates.append(xa11y.App.by_name(name, timeout=0.5))
            except (xa11y.TimeoutError, xa11y.SelectorNotMatchedError):
                continue
        try:
            for app in xa11y.App.list():
                app_title = (app.name or "").lower()
                if any(m in app_title for m in markers) or any(
                    name.lower() in app_title for name in browser_names
                ):
                    candidates.append(app)
        except Exception:
            pass

        seen: set[int] = set()
        for app in candidates:
            if app.pid in seen:
                continue
            seen.add(app.pid)
            title = (app.name or "").lower()
            if any(m in title for m in markers):
                return app, app.as_element()
            try:
                for win in app.children():
                    title = (win.name or "").lower()
                    if any(m in title for m in markers):
                        return app, win
            except Exception:
                continue
        time.sleep(1)
    return None, None


def _fill_auth0_form_via_input(
    browser: xa11y.App,
    auth_window: "xa11y.Element",
    email: str,
    password: str,
) -> None:
    """Fill the Auth0 password form using the keyboard only (no coordinates).

    Chrome's web content is invisible to AX, so we can't locate the password
    field by selector. But Auth0's password page AUTO-FOCUSES the password
    input, so typing into the focused field works — and it's resolution- and
    window-size-independent.

    Proven approach (from the spike):
      1. Activate the browser.
      2. Force a Latin/ABC input source (a Chinese IME mangles 'a1' -> '啊').
      3. Clear the field with Backspace (NOT Cmd+A — chord('a',['Meta']) leaks
         a literal 'a' into the field).
      4. Type the password CHAR BY CHAR via InputSim (low-level CGEvent).
      5. Press Enter.
    """
    if os.name == "nt":
        _fill_auth0_form_windows(browser, password)
        return

    import subprocess

    sim = xa11y.input_sim()

    # 1. Bring the browser to the foreground so keystrokes land in the page
    subprocess.run(
        ["osascript", "-e", f'tell application "{browser.name}" to activate'],
        capture_output=True,
    )
    time.sleep(1.5)

    # 2. Force a Latin layout so the IME doesn't intercept ASCII keystrokes
    _force_abc_input_source()
    time.sleep(0.5)

    # 3. Clear the field with Backspace (the password field is auto-focused).
    #    Do NOT use Cmd+A here — it leaks a literal 'a' character.
    for _ in range(40):
        sim.press("Backspace")
        time.sleep(0.02)
    time.sleep(0.3)

    # 4. Type char-by-char via InputSim — verbatim, no drops/reorders.
    for ch in password:
        sim.type_text(ch)
        time.sleep(0.08)
    time.sleep(0.5)

    # 5. Submit
    sim.press("Enter")

    # 6. Handle Chrome's "Open Heidi?" protocol-handler dialog.
    #    This native dialog IS in Chrome's AX tree (unlike web content), but
    #    its buttons have empty names. The two buttons are [Cancel, Open Heidi];
    #    the 2nd is "Open Heidi". Click it to bounce back into the app.
    _confirm_open_app_dialog(browser, timeout=15.0)
    time.sleep(2)


def _fill_auth0_form_windows(browser: xa11y.App, password: str) -> None:
    """Fill Auth0 in Chrome/Edge on Windows via UIA-exposed controls."""
    sim = xa11y.input_sim()
    password_field = browser.locator("text_field[name*='Password']")
    password_field.wait_visible(timeout=15.0)
    try:
        password_field.focus()
    except xa11y.ActionNotSupportedError:
        pass
    password_field.set_value(password)
    time.sleep(0.3)

    continue_btn = browser.locator("button[name='Continue']")
    if continue_btn.exists():
        continue_btn.press()
    else:
        sim.press("Enter")

    _confirm_open_app_dialog(browser, timeout=15.0)
    time.sleep(2)


def _confirm_open_app_dialog(browser: xa11y.App, timeout: float = 15.0) -> bool:
    """Click 'Open Heidi' on Chrome's protocol-handler confirmation dialog.

    The dialog appears as a window titled 'Open Heidi?' with two unnamed
    buttons [Cancel, Open Heidi]. We press the 2nd button. Returns True if a
    dialog was found and clicked.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            for win in browser.children():
                title = (win.name or "").lower()
                if "open" in title and "heidi" in title:
                    # Buttons live under this window; the 2nd is "Open Heidi".
                    win_loc = browser.locator("window[name*='Open']")
                    buttons = win_loc.descendant("button").elements()
                    if len(buttons) >= 2:
                        buttons[-1].press()   # last button = primary "Open Heidi"
                        return True
                    if buttons:
                        buttons[0].press()
                        return True
        except Exception:
            pass
        time.sleep(0.5)
    return False
