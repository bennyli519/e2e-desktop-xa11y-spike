"""Page Object: Devices page (Chronicle / Heidi Remote device management).

Selectors are text-based for now (the app has few aria-labels/testids). Labels
are the verified English defaultMessage strings from scribe-fe-v2
(src/features/chronicle/). A follow-up PR will add stable aria-labels; when it
lands, switch the selectors here to name='device-...' forms — specs won't change.

Route: /devices. Page header 'Heidi Remote'. DeviceSection branches:
  paired    -> DeviceCard + HelpSupportCard + RemoveDeviceCard
  not paired -> InitialPairingCard
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

    # --- modal handling -----------------------------------------------------
    def dismiss_modals(self) -> None:
        """Dismiss blocking modals that hide the device card / sidebar.

        Known blockers:
          - Firmware update modal   -> 'Remind me later'
          - "Can't find your Heidi Remote" overlay -> Cmd+R reload
          - Generic / Settings modal -> 'Close'
          - Connection error modal   -> Escape
        """
        sim = xa11y.input_sim()
        if click_first_match(self.app, ["button[name='Remind me later']"]):
            time.sleep(1)
            return
        if self.app.locator(
            "static_text[value*=\"Can't find your Heidi Remote\"]"
        ).exists():
            sim.chord("r", ["Meta"])
            time.sleep(3)
            return
        if self.app.locator("button[name='Close']").exists():
            click_first_match(self.app, ["button[name='Close']"])
            time.sleep(0.8)
            return
        sim.press("Escape")
        time.sleep(0.3)

    # --- pairing state ------------------------------------------------------
    def has_paired_device(self) -> bool:
        """True if a device is linked (DeviceCard shown, not InitialPairingCard)."""
        return (
            self.app.locator("static_text[value*='Serial Number']").exists()
            or self.app.locator("static_text[value='Status:']").exists()
        )

    def has_initial_pairing_card(self) -> bool:
        return self.app.locator(
            "button[name='Connect my Heidi Remote']"
        ).exists()

    # legacy alias (old serial-number based check)
    def has_device_card(self) -> bool:
        return self.has_paired_device()

    # --- connection state ---------------------------------------------------
    def status_badge(self) -> str | None:
        """Return 'Connected' / 'Disconnected' / 'Limited Connection', or None."""
        for label in ("Connected", "Disconnected", "Limited Connection"):
            if self.app.locator(f"static_text[value='{label}']").exists():
                return label
        return None

    def is_connected(self) -> bool:
        return (
            self.app.locator("button[name='Disconnect']").exists()
            or self.status_badge() == "Connected"
        )

    def is_disconnected(self) -> bool:
        return (
            self.app.locator("button[name*='Reconnect']").exists()
            or self.status_badge() == "Disconnected"
        )

    def is_reconnecting(self) -> bool:
        return self.app.locator("button[name*='Reconnecting']").exists()

    def connected_via(self) -> str | None:
        for via in ("Connected via Bluetooth", "Connected via USB"):
            el = self.app.locator(f"static_text[value*='{via}']")
            if el.exists():
                return via
        return None

    # --- device info reads --------------------------------------------------
    def has_serial_number(self) -> bool:
        return self.app.locator("static_text[value*='Serial Number']").exists()

    def get_serial_number(self) -> str | None:
        for el in self.app.locator("static_text").elements():
            val = el.value or ""
            if "Serial Number" in val and ":" in val:
                return val.split(":", 1)[1].strip()
        return None

    def has_firmware_version(self) -> bool:
        return self.app.locator("static_text[value*='Firmware version']").exists()

    def has_battery(self) -> bool:
        return self.app.locator("static_text[value*='Battery']").exists()

    def has_device_state_info(self) -> bool:
        """Connected device shows serial + firmware (battery optional)."""
        return self.has_serial_number() and self.has_firmware_version()

    # --- connection actions -------------------------------------------------
    def reconnect(self) -> bool:
        self.dismiss_modals()
        return click_first_match(
            self.app,
            [
                "button[name='device-reconnect']",  # future aria-label
                "button[name='Reconnect']",
                "button[name*='Reconnect']",
            ],
        )

    def disconnect(self) -> bool:
        return click_first_match(
            self.app,
            ["button[name='device-disconnect']", "button[name='Disconnect']"],
        )

    def wait_connected(self, timeout: float = 30.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_connected():
                return True
            time.sleep(1)
        return False

    def wait_disconnected(self, timeout: float = 30.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_disconnected() and not self.is_reconnecting():
                return True
            time.sleep(1)
        return False

    # --- onboarding (first pairing) -----------------------------------------
    def start_onboarding(self) -> bool:
        """Click 'Connect my Heidi Remote' to open the onboarding modal."""
        return click_first_match(
            self.app, ["button[name='Connect my Heidi Remote']"]
        )

    def onboarding_is_scanning(self) -> bool:
        return self.app.locator(
            "static_text[value*='Searching for devices']"
        ).exists()

    def onboarding_search_again(self) -> bool:
        return click_first_match(self.app, ["button[name='Search again']"])

    def onboarding_pick_device(self, device_name: str) -> bool:
        """Pick a discovered device by its (accessible-name) row button."""
        return click_first_match(self.app, [f"button[name*='{device_name}']"])

    def onboarding_is_connecting(self) -> bool:
        return self.app.locator(
            "static_text[value*='Connecting to device']"
        ).exists()

    def onboarding_is_connected(self) -> bool:
        return self.app.locator(
            "static_text[value*='Successfully connected']"
        ).exists()

    def onboarding_setup_device(self) -> bool:
        return click_first_match(self.app, ["button[name='Setup my device']"])

    def setup_select_default_note(self) -> bool:
        """On the setup wizard default-note step, confirm the template choice."""
        # combobox testTag 'setup-default-note-combobox'; just confirm default
        return click_first_match(self.app, ["button[name='Confirm']"])

    def setup_is_default_note_step(self) -> bool:
        return self.app.locator(
            "static_text[value*='Select your default note']"
        ).exists()

    # --- remove / lost device ----------------------------------------------
    def click_remove_device(self) -> bool:
        """Open the Remove device dialog from the card."""
        return click_first_match(self.app, ["button[name='Remove device']"])

    def remove_dialog_open(self) -> bool:
        return self.app.locator("static_text[value*='Removing device']").exists()

    def remove_confirm(self) -> bool:
        """Connected path: confirm removal (destructive 'Remove device')."""
        return click_first_match(self.app, ["button[name='Remove device']"])

    def remove_is_device_not_nearby(self) -> bool:
        return self.app.locator(
            "static_text[value*='Keep your device close and connected']"
        ).exists()

    def click_lost_my_device(self) -> bool:
        """Disconnected path: choose 'I've lost my device'."""
        return click_first_match(
            self.app,
            [
                "button[name=\"I've lost my device\"]",
                "button[name*='lost my device']",
            ],
        )

    def lost_warning_shown(self) -> bool:
        return self.app.locator(
            "static_text[value*='You may lose your unsynced sessions']"
        ).exists()

    def confirm_lost_remove(self) -> bool:
        """On the data-loss warning, confirm 'Yes, remove'."""
        return click_first_match(self.app, ["button[name='Yes, remove']"])

    def remove_succeeded(self) -> bool:
        return self.app.locator(
            "static_text[value*='successfully removed']"
        ).exists()

    def remove_dismiss(self) -> bool:
        return click_first_match(self.app, ["button[name='Dismiss']"])

    def wait_remove_success(self, timeout: float = 60.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.remove_succeeded():
                return True
            time.sleep(1)
        return False
