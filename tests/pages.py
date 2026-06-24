"""Page Objects for Heidi desktop E2E tests.

Centralises selectors so tests don't hardcode them. When the UI changes,
fix the selector here once instead of in every test.

Selector notes (from real AX tree dumps):
  - Sidebar items have INCONSISTENT roles: Scribe/Settings/Notifications are
    `button`, Evidence/Tasks/Templates are `link`, Devices/Help are `combo_box`.
  - We use comma-separated role alternation (official xa11y portable pattern)
    so a single selector survives role differences across platforms/versions.
  - `name` comes from aria-label / visible text. Prefer aria-label once added.
"""
import time

import xa11y


def _click_first_match(app: xa11y.App, selectors: list[str], label: str) -> bool:
    """Try each selector in order; press the first that exists."""
    for sel in selectors:
        try:
            loc = app.locator(sel)
            if loc.exists():
                loc.press()
                return True
        except Exception:
            continue
    return False


class Sidebar:
    """Left navigation rail. Item roles vary, so each nav method uses a
    role-alternation selector."""

    def __init__(self, app: xa11y.App):
        self.app = app

    def _nav(self, name: str) -> bool:
        # role-agnostic: matches button OR link OR combo_box with this name
        selectors = [
            f"button[name='{name}'], link[name='{name}'], combo_box[name='{name}']",
            f"static_text[value='{name}']",  # last-resort fallback
        ]
        ok = _click_first_match(self.app, selectors, name)
        if ok:
            time.sleep(1.5)  # allow page transition
        return ok

    def go_to_scribe(self) -> bool:
        return self._nav("Scribe")

    def go_to_devices(self) -> bool:
        return self._nav("Devices")

    def go_to_patients(self) -> bool:
        return self._nav("Patients")

    def go_to_settings(self) -> bool:
        return self._nav("Settings")

    def go_to_evidence(self) -> bool:
        return self._nav("Evidence")

    def go_to_tasks(self) -> bool:
        return self._nav("Tasks")

    def new_session(self) -> bool:
        ok = _click_first_match(
            self.app,
            [
                "button[name='New session']",
                "static_text[value='New session']",
            ],
            "New session",
        )
        if ok:
            time.sleep(1.5)
        return ok

    def close_modal(self) -> bool:
        """Close a blocking modal (e.g. Settings opens full-screen with a
        'Close' button and hides the sidebar). Safe no-op if none is open."""
        closed = False
        for _ in range(3):
            if not self.app.locator("button[name='Close']").exists():
                break
            if _click_first_match(self.app, ["button[name='Close']"], "Close"):
                closed = True
                time.sleep(0.8)
        return closed

    def reset_to_scribe(self) -> None:
        """Return to a known baseline: close any modal, then open Scribe."""
        self.close_modal()
        # Press Escape too, in case a non-Close popover is open
        try:
            xa11y.input_sim().press("Escape")
        except Exception:
            pass
        time.sleep(0.3)
        self.go_to_scribe()


class DevicePage:
    """The Devices page (Chronicle / Heidi Remote device management).

    Reconnect/Disconnect button names currently come from the visible
    <FormattedMessage> text ('Reconnect' / 'Disconnect' / 'Reconnecting…'),
    which is i18n- and state-dependent. Once aria-labels are added in
    scribe-fe-v2, switch these to stable name selectors.

    Modal handling and exact button labels are ported from the cua-driver
    framework's DevicePage (tests/Desktop-E2E-Test/pages/device.py).
    """

    def __init__(self, app: xa11y.App):
        self.app = app
        self.sidebar = Sidebar(app)

    def open(self) -> bool:
        self.dismiss_modals()
        return self.sidebar.go_to_devices()

    # --- modal handling ---
    def dismiss_modals(self) -> None:
        """Dismiss blocking modals that hide the device card / sidebar.

        Known blockers (from cua-driver experience):
          - Firmware update modal -> "Remind me later"
          - Connection error modal -> Escape
          - "Can't find your Heidi Remote" full-page overlay -> Cmd+R reload
          - Generic Settings-style modal -> "Close"
        """
        sim = xa11y.input_sim()

        # Firmware update: "Remind me later"
        if _click_first_match(self.app, ["button[name='Remind me later']"], "Remind"):
            time.sleep(1)
            return

        # "Can't find your Heidi Remote" full-page overlay -> reload webview
        if self.app.locator("static_text[value*=\"Can't find your Heidi Remote\"]").exists():
            sim.chord("r", ["Meta"])  # Cmd+R reload
            time.sleep(3)
            return

        # Generic close / escape for any other modal
        if self.app.locator("button[name='Close']").exists():
            _click_first_match(self.app, ["button[name='Close']"], "Close")
            time.sleep(0.8)
            return
        # Connection-error modal: Escape
        sim.press("Escape")
        time.sleep(0.3)

    # --- state ---
    def is_connected(self) -> bool:
        # "Disconnect" button only shows when connected
        return self.app.locator(
            "button[name='Disconnect'], button[name='device-disconnect']"
        ).exists()

    def is_disconnected(self) -> bool:
        return self.app.locator(
            "button[name*='Reconnect'], button[name='device-reconnect']"
        ).exists()

    def has_device_card(self) -> bool:
        # Serial number line is always present on a paired device card
        return self.app.locator("static_text[value*='Serial number']").exists()

    def get_serial_number(self) -> str | None:
        for el in self.app.locator("static_text[value*='Serial number']").elements():
            val = el.value or ""
            if "Serial number" in val:
                # format: "Serial number: HV0..."
                parts = val.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip()
        return None

    def has_firmware_version(self) -> bool:
        return self.app.locator("static_text[value*='Firmware version']").exists()

    def has_battery(self) -> bool:
        return self.app.locator("static_text[value*='Battery']").exists()

    # --- actions ---
    def reconnect(self) -> bool:
        self.dismiss_modals()
        return _click_first_match(
            self.app,
            [
                "button[name='device-reconnect']",       # preferred (aria-label)
                "button[name='Reconnect']",
                "button[name*='Reconnect']",             # also matches 'Reconnecting…'
            ],
            "Reconnect",
        )

    def disconnect(self) -> bool:
        return _click_first_match(
            self.app,
            [
                "button[name='device-disconnect']",      # preferred (aria-label)
                "button[name='Disconnect']",
            ],
            "Disconnect",
        )
