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
    devices.remove_dismiss()
    time.sleep(2)

    # THEN the initial pairing card appears.
    assert devices.has_initial_pairing_card(), "Initial pairing card not shown after removal"

    # WHEN we start onboarding and scan.
    assert devices.start_onboarding(), "Could not open onboarding modal"
    time.sleep(3)
    if not devices.onboarding_is_scanning():
        pytest.skip("Onboarding did not reach the scan step (prerequisite/permission gate?)")

    # Wait for a device to appear, then pick it. Requires the physical device on.
    print(">> Make sure the Heidi Remote is ON (press its side button).")
    picked = False
    deadline = time.time() + 60
    while time.time() < deadline:
        # device rows are Button nodes named by the device name; try a broad grab
        rows = devices.app.locator("button").elements()
        for r in rows:
            name = (r.name or "")
            if name and name not in (
                "Search again", "Don't see your device?", "Back", "Close",
            ) and "Heidi" not in name and len(name) > 2:
                # heuristic: a discovered device row
                try:
                    r.press()
                    picked = True
                    break
                except Exception:
                    continue
        if picked:
            break
        time.sleep(3)
    if not picked:
        pytest.skip("No device discovered during scan — is the device on and nearby?")

    # WHEN connecting completes.
    time.sleep(4)
    if not devices.onboarding_is_connected():
        # connecting can take a while over BLE
        for _ in range(20):
            if devices.onboarding_is_connected():
                break
            time.sleep(2)
    assert devices.onboarding_is_connected(), "Did not reach 'Successfully connected'"

    # THEN set up the default note (template).
    assert devices.onboarding_setup_device(), "Could not click 'Setup my device'"
    time.sleep(2)
    if devices.setup_is_default_note_step():
        assert devices.setup_select_default_note(), "Could not confirm default note"
        time.sleep(2)

    # Onboarding done — verify we now have a paired, connected device.
    assert devices.has_paired_device(), "Device not paired after onboarding"
