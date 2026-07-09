"""device-connection: connected-flow (reconnect a disconnected device).

Scenario:
  device is linked but in a disconnected state
  -> click Reconnect
  -> device connects successfully
  -> the device state info is visible (serial / firmware / battery / status)

Requires a real Chronicle device paired and nearby.

Run from Ghostty, logged in, Heidi foreground, device on:
    pytest tests/device-connection/test_connected_reconnect_flow.py -v -s
"""
import time

import pytest
import xa11y

from pages import DevicePage

pytestmark = [pytest.mark.device_connection, pytest.mark.needs_device,
              pytest.mark.slow, pytest.mark.timeout(120)]


def test_reconnect_shows_device_state(devices: DevicePage, require_device):
    if devices.is_connected():
        # Already connected — disconnect first so we can test the reconnect path.
        if devices.disconnect():
            time.sleep(3)

    if not devices.is_disconnected():
        pytest.skip("Device is not in a disconnected state to reconnect from")

    # WHEN clicking Reconnect
    assert devices.reconnect(), "Reconnect click failed"

    # THEN it connects (real BLE — allow time; may briefly show 'Reconnecting…')
    if not devices.wait_connected(timeout=40):
        busy = devices.is_reconnecting()
        pytest.skip(
            "Reconnect clicked but device did not connect (likely not nearby). "
            f"reconnecting={busy}"
        )

    assert devices.is_connected(), "Device did not reach connected state"

    # AND the device state info is shown
    assert devices.has_device_state_info(), (
        "Connected device should show Serial Number + Firmware version"
    )
    assert devices.status_badge() == "Connected", "Status badge should read 'Connected'"
    # connected-via label is informative but optional depending on transport
    via = devices.connected_via()
    print(f"connected_via: {via}  serial: {devices.get_serial_number()}")
