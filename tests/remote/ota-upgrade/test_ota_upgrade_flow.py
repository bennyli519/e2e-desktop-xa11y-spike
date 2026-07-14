"""ota-upgrade: Chronicle OTA firmware update flow.

Scenario:
  a firmware update is available for the connected device
  -> open the update modal (banner 'Update' or startup prompt)
  -> confirm ('Upgrade now')
  -> observe in-progress (percentage advances)
  -> reaches completed ('Successfully updated') -> 'Done'

Requires a real device that actually has an available firmware update. If no
update is offered, the test skips. OTA over BLE is slow (minutes) and reboots
the device — run deliberately.

WARNING: this flashes firmware. Guarded by RUN_MANUAL=1.

Run from Ghostty, logged in, Heidi foreground, device on with an update pending:
    RUN_MANUAL=1 pytest tests/ota-upgrade/test_ota_upgrade_flow.py -v -s
"""
import time

import pytest
import xa11y

from pages import DevicePage, FirmwarePage

pytestmark = [pytest.mark.ota, pytest.mark.needs_device, pytest.mark.needs_manual,
              pytest.mark.slow, pytest.mark.timeout(900)]


@pytest.fixture()
def devices(heidi_app: xa11y.App) -> DevicePage:
    dp = DevicePage(heidi_app)
    dp.open()
    time.sleep(2)
    return dp


@pytest.fixture()
def require_manual():
    import os
    if os.environ.get("RUN_MANUAL") != "1":
        pytest.skip("OTA flashes firmware — set RUN_MANUAL=1 to run")


def test_ota_upgrade_flow(devices: DevicePage, require_manual):
    if not devices.has_paired_device():
        pytest.skip("No paired device")

    fw = FirmwarePage(devices.app)

    # Open the modal: prefer the device-settings banner; else it may already be up.
    if fw.has_update_banner():
        assert fw.open_from_banner(), "Could not open firmware modal from banner"
        time.sleep(2)
    if not fw.confirm_view_shown():
        pytest.skip(
            "No firmware update available (confirm view not shown) — nothing to upgrade"
        )

    # WHEN confirming the upgrade.
    assert fw.upgrade_now(), "Could not click 'Upgrade now'"
    time.sleep(3)
    assert fw.in_progress(), "OTA did not enter 'Update in progress'"

    # Observe progress advancing (percentage should move at least once).
    p0 = fw.progress_percent()
    time.sleep(20)
    p1 = fw.progress_percent()
    print(f"OTA progress: {p0}% -> {p1}%")

    # THEN it reaches a terminal state (completed hopefully).
    result = fw.wait_terminal(timeout=600)
    assert result is not None, "OTA did not reach a terminal state within 10 min"
    if result == "failed":
        fw.try_later()
        pytest.fail("OTA reported failure ('We ran into some issues')")

    assert fw.completed(), "OTA did not complete successfully"
    assert fw.done(), "Could not dismiss the completed modal"
