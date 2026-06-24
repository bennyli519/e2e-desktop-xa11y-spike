"""Bluetooth device tests: navigate to Devices, find and reconnect.

These tests interact with real hardware (Chronicle BLE device).
Run with: pytest tests/test_bluetooth.py -v -m bluetooth

Prerequisite: dump the Devices page tree first to get exact selectors:
    python scripts/dump_page.py --page Devices
"""
import time

import pytest
import xa11y

pytestmark = [pytest.mark.bluetooth, pytest.mark.slow]


class TestDevicePage:
    """Navigate to Devices tab and inspect available devices."""

    def test_navigate_to_devices(self, heidi_app: xa11y.App, dump_tree):
        loc = heidi_app.locator("static_text[value='Devices']")
        loc.wait_visible(timeout=10.0)
        loc.press()
        time.sleep(3)

        # Dump the tree so we can discover exact element selectors
        path = dump_tree("devices_page", max_depth=15)
        print(f"Tree dumped to {path} — inspect to find reconnect button selectors")

    def test_find_device_in_list(self, heidi_app: xa11y.App, dump_tree):
        """Look for the Chronicle/Heidi Remote device in the device list."""
        # Navigate to Devices
        heidi_app.locator("static_text[value='Devices']").press()
        time.sleep(3)

        dump_tree("devices_find_device", max_depth=15)

        # Try common selectors for the device entry
        # These will need adjustment after inspecting the actual tree
        device_selectors = [
            "static_text[value*='Chronicle']",
            "static_text[value*='Heidi Remote']",
            "static_text[value*='HV0']",
            "static_text[value*='260325']",
            "group[name*='device']",
            "button[name*='Reconnect']",
            "button[name*='Connect']",
        ]

        found = None
        for sel in device_selectors:
            loc = heidi_app.locator(sel)
            if loc.exists():
                found = sel
                elem = loc.element()
                print(f"Found device element: {sel} -> role={elem.role} name={elem.name}")
                break

        if found is None:
            pytest.skip(
                "Could not find device element — inspect reports/devices_find_device.txt "
                "and update selectors"
            )

    def test_click_reconnect(self, heidi_app: xa11y.App, dump_tree):
        """Click the reconnect/connect button for the device."""
        heidi_app.locator("static_text[value='Devices']").press()
        time.sleep(3)

        # TODO: Update these selectors after inspecting the tree dump
        # The reconnect button might be:
        #   button[name='Reconnect']
        #   button[name='Connect']
        #   link[name='Reconnect']
        #   static_text[value='Reconnect']
        reconnect_selectors = [
            "button[name*='econnect']",
            "button[name*='onnect']",
            "link[name*='econnect']",
            "static_text[value*='Reconnect']",
            "static_text[value*='Connect']",
        ]

        for sel in reconnect_selectors:
            loc = heidi_app.locator(sel)
            if loc.exists():
                print(f"Clicking reconnect via: {sel}")
                loc.press()
                time.sleep(5)

                # Dump post-reconnect state
                dump_tree("after_reconnect", max_depth=15)
                return

        dump_tree("devices_no_reconnect_found", max_depth=15)
        pytest.skip(
            "Reconnect button not found — inspect reports/devices_no_reconnect_found.txt"
        )
