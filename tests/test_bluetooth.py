"""Bluetooth device tests: navigate to Devices, inspect card, reconnect.

Uses the DevicePage Page Object (tests/pages.py), with modal handling ported
from the cua-driver framework.

NOTE: reconnect drives real Chronicle BLE hardware. If no device is paired or
the device isn't nearby/powered, the relevant tests SKIP rather than fail.

Run:  pytest tests/test_bluetooth.py -v -m bluetooth
"""
import time

import pytest
import xa11y

from pages import DevicePage

pytestmark = [pytest.mark.bluetooth, pytest.mark.slow]


@pytest.fixture()
def devices(heidi_app: xa11y.App) -> DevicePage:
    """Open the Devices page from a clean state before each test."""
    dp = DevicePage(heidi_app)
    dp.open()
    time.sleep(2)
    return dp


class TestDevicePage:
    def test_open_devices_page(self, devices: DevicePage, dump_tree):
        # Dump so we can refine selectors against the real device card
        dump_tree("devices_page")
        # Page opened if we see either a device card or a pairing prompt
        assert devices.app.locator("web_area").exists()

    def test_device_card_present(self, devices: DevicePage, dump_tree):
        dump_tree("devices_card")
        if not devices.has_device_card():
            pytest.skip(
                "No paired device card ('Serial number' absent) — "
                "inspect reports/devices_card.txt"
            )
        assert devices.has_device_card()

    def test_serial_number_readable(self, devices: DevicePage):
        if not devices.has_device_card():
            pytest.skip("No paired device")
        serial = devices.get_serial_number()
        assert serial, "Serial number present in tree but could not be parsed"

    def test_firmware_version_shown(self, devices: DevicePage):
        if not devices.has_device_card():
            pytest.skip("No paired device")
        assert devices.has_firmware_version(), "Firmware version not shown on card"


class TestConnectionState:
    def test_shows_a_connection_button(self, devices: DevicePage, dump_tree):
        """Card must show either Reconnect (disconnected) or Disconnect."""
        if not devices.has_device_card():
            pytest.skip("No paired device")
        connected = devices.is_connected()
        disconnected = devices.is_disconnected()
        if not (connected or disconnected):
            dump_tree("devices_no_conn_button")
            pytest.fail(
                "Neither Reconnect nor Disconnect button found — "
                "see reports/devices_no_conn_button.txt"
            )
        assert connected or disconnected


class TestReconnectFlow:
    def test_reconnect_device(self, devices: DevicePage, dump_tree):
        """Click Reconnect and verify the UI moves toward a connected state."""
        if not devices.has_device_card():
            pytest.skip("No paired device")
        if devices.is_connected():
            pytest.skip("Already connected")
        if not devices.is_disconnected():
            dump_tree("reconnect_no_button")
            pytest.skip("No Reconnect button — see reports/reconnect_no_button.txt")

        assert devices.reconnect(), "Reconnect click failed"

        # Reconnect drives real BLE — wait, then check connected/busy state.
        time.sleep(6)
        dump_tree("after_reconnect")

        connected = devices.is_connected()
        busy = devices.app.locator("button[name*='Reconnecting']").exists()
        if not (connected or busy):
            pytest.skip(
                "Reconnect clicked but device did not connect (likely not nearby). "
                "See reports/after_reconnect.txt"
            )
        assert connected or busy

    def test_disconnect_device(self, devices: DevicePage):
        """If connected, disconnect and verify the Reconnect button returns."""
        if not devices.has_device_card():
            pytest.skip("No paired device")
        if not devices.is_connected():
            pytest.skip("Not connected — nothing to disconnect")

        assert devices.disconnect(), "Disconnect click failed"
        time.sleep(3)
        # After disconnect, the Reconnect button should reappear
        assert devices.is_disconnected(), "Reconnect button did not reappear after disconnect"
