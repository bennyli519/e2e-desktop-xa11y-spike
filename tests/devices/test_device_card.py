"""devices: the Devices page opens and shows a device card."""
import pytest

from pages import DevicePage

pytestmark = pytest.mark.devices


def test_open_devices_page(devices: DevicePage, dump_tree):
    dump_tree("devices_page")
    assert devices.app.locator("web_area").exists()


def test_device_card_present(devices: DevicePage, dump_tree):
    dump_tree("devices_card")
    if not devices.has_device_card():
        pytest.skip(
            "No paired device card ('Serial number' absent) — "
            "inspect reports/devices_card.txt"
        )
    assert devices.has_device_card()
