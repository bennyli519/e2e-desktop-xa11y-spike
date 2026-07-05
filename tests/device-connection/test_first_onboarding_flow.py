"""device-connection: first-onboarding flow.

Scenario (APP device onboarding):
  device page already has a linked device
  -> remove it
  -> scan for devices
  -> connect a device
  -> set up the default note (template)

Requires a real Chronicle device nearby and powered. This drives real BLE, so
it's slow and needs the device present; skips cleanly otherwise. Some steps are
device-timing dependent — generous waits + skip-on-not-found.

Run from Ghostty, logged in, Heidi foreground, device on:
    RUN_MANUAL=1 pytest tests/device-connection/test_first_onboarding_flow.py -v -s
"""
import time

import pytest
import xa11y

from pages import DevicePage

pytestmark = [pytest.mark.device_connection, pytest.mark.needs_device,
              pytest.mark.slow, pytest.mark.timeout(300)]


def test_first_onboarding_flow(devices: DevicePage, require_device, require_manual):
    # GIVEN a linked device — remove it to reach the initial-pairing state.
    assert devices.has_paired_device(), "Expected a linked device to start"

    assert devices.click_remove_device(), "Could not open Remove dialog"
    time.sleep(1)
    # Connected path -> confirm; disconnected path -> lost-device -> force remove.
    if devices.remove_is_device_not_nearby():
        assert devices.click_lost_my_device(), "Could not choose lost-device path"
        time.sleep(1)
        assert devices.lost_warning_shown(), "Data-loss warning not shown"
        assert devices.confirm_lost_remove(), "Could not confirm removal"
    else:
        assert devices.remove_confirm(), "Could not confirm removal"

    assert devices.wait_remove_success(timeout=90), "Device removal did not complete"
    # Success screen (if shown) has a Dismiss; otherwise we're already on the card.
    devices.remove_dismiss()
    time.sleep(2)

    # THEN the initial pairing card appears.
    assert devices.has_initial_pairing_card(), "Initial pairing card not shown after removal"

    # WHEN we start onboarding and scan.
    assert devices.start_onboarding(), "Could not open onboarding modal"
    time.sleep(3)
    if not devices.onboarding_is_scanning():
        pytest.skip("Onboarding did not reach the scan step (prerequisite/permission gate?)")

    # Wait for THIS device to appear in the scan list, then pick it.
    print(">> Make sure the Heidi Remote is ON (press its side button).")
    device_serial = "HV0"  # discovered rows are named 'heidi remote device HV0_...'
    picked = False
    deadline = time.time() + 60
    while time.time() < deadline:
        row = devices.app.locator(f"button[name*='{device_serial}']")
        if row.exists():
            row.press()
            picked = True
            break
        time.sleep(3)
    if not picked:
        pytest.skip("No device discovered during scan — is the device on and nearby?")

    # WHEN connecting completes (a fresh re-pair over BLE can be slow).
    time.sleep(4)
    for _ in range(40):
        if devices.onboarding_is_connected():
            break
        time.sleep(2)
    assert devices.onboarding_is_connected(), "Did not reach 'Successfully connected'"

    # THEN run the setup wizard (default note -> language -> basics -> USB modal).
    assert devices.onboarding_setup_device(), "Could not click 'Setup my device'"
    time.sleep(2)
    devices.complete_onboarding_setup()

    # Onboarding done — verify we now have a paired device.
    devices.open()
    time.sleep(3)
    assert devices.has_paired_device(), "Device not paired after onboarding"
