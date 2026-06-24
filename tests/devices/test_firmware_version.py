"""devices: firmware version is shown on the device card."""
import pytest

from pages import DevicePage

pytestmark = pytest.mark.devices


def test_firmware_version_shown(devices: DevicePage):
    if not devices.has_device_card():
        pytest.skip("No paired device")
    assert devices.has_firmware_version(), "Firmware version not shown on card"
