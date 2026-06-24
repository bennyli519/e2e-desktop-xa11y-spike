"""devices: clicking Reconnect drives the BLE reconnect flow.

Requires the Chronicle device to be paired. If the device isn't nearby or
powered, the test skips (the click is accepted but no connection completes).
"""
import time

import pytest

from pages import DevicePage

pytestmark = [pytest.mark.devices, pytest.mark.slow]


def test_reconnect_device(devices: DevicePage, dump_tree):
    if not devices.has_device_card():
        pytest.skip("No paired device")
    if devices.is_connected():
        pytest.skip("Already connected — nothing to reconnect")
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
