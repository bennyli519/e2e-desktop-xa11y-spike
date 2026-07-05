"""Page Object: Devices page (Chronicle / Heidi Remote device management).

Reconnect/Disconnect button names currently come from the visible
<FormattedMessage> text ('Reconnect' / 'Disconnect' / 'Reconnecting…'), which
is i18n- and state-dependent. Once aria-labels land in scribe-fe-v2, switch
to stable name selectors (e.g. button[name='device-reconnect']).

Modal handling and exact button labels are ported from the cua-driver
framework's DevicePage (Desktop-E2E-Test/pages/device.py).
"""
import time

import xa11y

from lib import click_first_match
from pages.sidebar import Sidebar


class DevicePage:
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
          - Firmware update modal      -> "Remind me later"
          - "Can't find your Heidi Remote" full-page overlay -> Cmd+R reload
          - Generic / Settings modal   -> "Close"
          - Connection error modal     -> Escape
        """
        sim = xa11y.input_sim()

        if click_first_match(self.app, ["button[name='Remind me later']"]):
            time.sleep(1)
            return

        if click_first_match(self.app, ["button[name='Try Again']"]):
            time.sleep(3)
            return

        if self.app.locator(
            "static_text[value*=\"Can't find your Heidi Remote\"]"
        ).exists():
            sim.chord("r", ["Meta"])  # Cmd+R reload
            time.sleep(3)
            return

        if (
            self.app.locator("dialog").exists()
            and self.app.locator("button[name='Close']").exists()
        ):
            click_first_match(self.app, ["button[name='Close']"])
            time.sleep(0.8)
            return

        sim.press("Escape")
        time.sleep(0.3)

    # --- state ---
    def is_connected(self) -> bool:
        return self.app.locator(
            "button[name='Disconnect'], button[name='device-disconnect']"
        ).exists()

    def is_disconnected(self) -> bool:
        return self.app.locator(
            "button[name*='Reconnect'], button[name='device-reconnect']"
        ).exists()

    def has_device_card(self) -> bool:
        return self.app.locator(
            "static_text[value*='Serial number'], "
            "static_text[name*='Serial number']"
        ).exists()

    def get_serial_number(self) -> str | None:
        for el in self.app.locator(
            "static_text[value*='Serial number'], "
            "static_text[name*='Serial number']"
        ).elements():
            val = el.value or el.name or ""
            if "Serial number" in val:
                parts = val.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip()
        return None

    def has_firmware_version(self) -> bool:
        return self.app.locator(
            "static_text[value*='Firmware version'], "
            "static_text[name*='Firmware version']"
        ).exists()

    def has_battery(self) -> bool:
        return self.app.locator(
            "static_text[value*='Battery'], static_text[name*='Battery']"
        ).exists()

    # --- actions ---
    def reconnect(self) -> bool:
        self.dismiss_modals()
        return click_first_match(
            self.app,
            [
                "button[name='device-reconnect']",   # preferred (aria-label)
                "button[name='Reconnect']",
                "button[name*='Reconnect']",          # also matches 'Reconnecting…'
            ],
        )

    def disconnect(self) -> bool:
        return click_first_match(
            self.app,
            [
                "button[name='device-disconnect']",  # preferred (aria-label)
                "button[name='Disconnect']",
            ],
        )
