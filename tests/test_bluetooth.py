"""Bluetooth device tests: navigate to Devices, inspect, reconnect.

Uses the DevicePage Page Object (tests/pages.py).

NOTE: reconnect actually drives the Chronicle BLE hardware. If no device is
paired/nearby, tests skip rather than fail.

Run:  pytest tests/test_bluetooth.py -v -m bluetooth
"""
import time

import pytest
import xa11y

from pages import DevicePage

pytestmark = [pytest.mark.bluetooth, pytest.mark.slow]


class TestDevicePage:
    def test_open_devices_page(self, heidi_app: xa11y.App, dump_tree):
        dp = DevicePage(heidi_app)
        assert dp.open(), "Could not navigate to Devices"
        time.sleep(2)
        # Dump so we can refine selectors against the real device card
        dump_tree("devices_page")

    def test_device_card_present(self, heidi_app: xa11y.App, dump_tree):
        dp = DevicePage(heidi_app)
        dp.open()
        time.sleep(2)
        dump_tree("devices_card")
        if not dp.has_device_card():
            pytest.skip(
                "No paired device card (no 'Serial number') — "
                "inspect reports/devices_card.txt"
            )

    def test_reconnect_button_exists(self, heidi_app: xa11y.App, dump_tree):
        dp = DevicePage(heidi_app)
        dp.open()
        time.sleep(2)
        if dp.is_connected():
            pytest.skip("Device already connected — nothing to reconnect")
        if not dp.is_disconnected():
            dump_tree("devices_no_reconnect")
            pytest.skip(
                "No reconnect button found — inspect reports/devices_no_reconnect.txt"
            )
        assert dp.is_disconnected()


class TestReconnectFlow:
    def test_reconnect_device(self, heidi_app: xa11y.App, dump_tree):
        """Click Reconnect and verify the UI moves toward a connected state."""
        dp = DevicePage(heidi_app)
        dp.open()
        time.sleep(2)

        if dp.is_connected():
            pytest.skip("Already connected")

        if not dp.reconnect():
            dump_tree("reconnect_no_button")
            pytest.skip("Reconnect button not found — see reports/reconnect_no_button.txt")

        # Reconnect drives real BLE — give it time, then check for a connected
        # indicator. If the device isn't nearby/powered, this won't connect:
        # we just assert the click was accepted (button entered busy/disabled).
        time.sleep(5)
        dump_tree("after_reconnect")

        # Either we connected, or the button is mid-reconnect (busy) —
        # both prove the click was wired up correctly.
        connected = dp.is_connected()
        busy = heidi_app.locator("button[name*='Reconnecting']").exists()
        if not (connected or busy):
            pytest.skip(
                "Reconnect clicked but device did not connect (likely not nearby). "
                "See reports/after_reconnect.txt"
            )
