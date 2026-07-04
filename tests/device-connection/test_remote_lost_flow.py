"""device-connection: remove / 'I've lost my device' flow.

Scenario:
  device page has a linked device
  -> click Remove device
  -> a dialog pops up
  -> (disconnected path) click "I've lost my device"
  -> confirm the data-loss warning ("Yes, remove")
  -> removal succeeds

Note: the exact label is "I've lost my device" and the lost path goes through a
data-loss warning before removing. If the device is connected, the dialog shows
the direct confirm path instead — this test drives the LOST (disconnected) path,
so it disconnects first if needed.

WARNING: this actually unlinks the device. Re-pair afterwards (or run the
onboarding flow). Requires RUN_MANUAL=1 to avoid accidental unlinks.

Run from Ghostty, logged in, Heidi foreground:
    RUN_MANUAL=1 pytest tests/device-connection/test_remote_lost_flow.py -v -s
"""
import time

import pytest
import xa11y

from pages import DevicePage

pytestmark = [pytest.mark.device_connection, pytest.mark.needs_device,
              pytest.mark.slow, pytest.mark.timeout(180)]


def test_remote_lost_flow(devices: DevicePage, require_device, require_manual):
    assert devices.has_paired_device(), "Expected a linked device to start"

    # Drive the LOST path: ensure disconnected so the dialog offers it.
    if devices.is_connected():
        if devices.disconnect():
            devices.wait_disconnected(timeout=30)
        time.sleep(1)

    # WHEN opening the Remove dialog.
    assert devices.click_remove_device(), "Could not open Remove dialog"
    time.sleep(1.5)
    assert devices.remove_dialog_open(), "Remove dialog ('Removing device') not shown"

    # THEN the device-not-nearby step offers 'I've lost my device'.
    if not devices.remove_is_device_not_nearby():
        pytest.skip(
            "Dialog did not show the device-not-nearby step (device may be "
            "connected) — the lost-device entry point wasn't offered"
        )
    assert devices.click_lost_my_device(), "Could not click \"I've lost my device\""
    time.sleep(1)

    # AND the data-loss warning appears.
    assert devices.lost_warning_shown(), (
        "Expected 'You may lose your unsynced sessions' warning"
    )
    assert devices.confirm_lost_remove(), "Could not click 'Yes, remove'"

    # THEN removal succeeds.
    assert devices.wait_remove_success(timeout=90), "Removal did not complete"
    assert devices.remove_succeeded(), "Success screen not shown"
    devices.remove_dismiss()
    time.sleep(2)
    assert devices.has_initial_pairing_card(), (
        "Should revert to the initial pairing card after removal"
    )
