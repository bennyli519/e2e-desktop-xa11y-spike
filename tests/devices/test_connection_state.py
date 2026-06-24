"""devices: the card shows a connection-state button (Reconnect or Disconnect)."""
import pytest

from pages import DevicePage

pytestmark = pytest.mark.devices


def test_shows_a_connection_button(devices: DevicePage, dump_tree):
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
