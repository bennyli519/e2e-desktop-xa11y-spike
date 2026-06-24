"""devices: serial number is shown and parseable on the device card."""
import pytest

from pages import DevicePage

pytestmark = pytest.mark.devices


def test_serial_number_readable(devices: DevicePage):
    if not devices.has_device_card():
        pytest.skip("No paired device")
    serial = devices.get_serial_number()
    assert serial, "Serial number present in tree but could not be parsed"
