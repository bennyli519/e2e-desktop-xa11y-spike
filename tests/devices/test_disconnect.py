"""devices: clicking Disconnect returns the card to a disconnected state."""
import time

import pytest

from pages import DevicePage

pytestmark = [pytest.mark.devices, pytest.mark.slow]


def test_disconnect_device(devices: DevicePage):
    if not devices.has_device_card():
        pytest.skip("No paired device")
    if not devices.is_connected():
        pytest.skip("Not connected — nothing to disconnect")

    assert devices.disconnect(), "Disconnect click failed"
    time.sleep(3)
    assert devices.is_disconnected(), "Reconnect button did not reappear after disconnect"
