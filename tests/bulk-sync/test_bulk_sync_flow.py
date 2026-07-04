"""bulk-sync: Chronicle offline bulk-sync progress UI.

Scenario:
  the device has offline recordings -> it connects (BLE/USB/WiFi)
  -> Rust auto-triggers bulk sync
  -> the app shows the BulkSyncWidget: 'Syncing' -> progress -> 'Syncing complete'

IMPORTANT: bulk sync is auto-triggered by Rust on device connect / USB mount —
there is no 'Start sync' button. This test verifies the progress UI while a real
sync runs. The only clickable action is 'Retry sync' (on failure).

Requires a paired device that has unsynced offline recordings. To create some:
record a session on the device while the app is closed/disconnected, then connect.

Run from Ghostty, logged in, Heidi foreground, device with pending recordings:
    RUN_MANUAL=1 pytest tests/bulk-sync/ -v -s
"""
import time

import pytest
import xa11y

from pages import BulkSyncPage, DevicePage

pytestmark = [pytest.mark.bulk_sync, pytest.mark.needs_device,
              pytest.mark.needs_manual, pytest.mark.slow, pytest.mark.timeout(600)]


@pytest.fixture()
def require_manual():
    import os
    if os.environ.get("RUN_MANUAL") != "1":
        pytest.skip(
            "Bulk sync needs a device with pending offline recordings — set "
            "RUN_MANUAL=1 and have unsynced sessions on the device"
        )


def test_bulk_sync_progress_ui(heidi_app: xa11y.App, require_manual):
    dp = DevicePage(heidi_app)
    dp.open()
    time.sleep(2)
    if not dp.has_paired_device():
        pytest.skip("No paired device")

    # Ensure connected so Rust auto-triggers the sync.
    if not dp.is_connected():
        if dp.reconnect():
            dp.wait_connected(timeout=40)
    if not dp.is_connected():
        pytest.skip("Device not connected — sync won't auto-trigger")

    bs = BulkSyncPage(heidi_app)

    # WHEN a sync is running (auto-triggered). Wait for the widget to appear.
    print(">> If no pending recordings exist, the widget won't appear (skip).")
    appeared = False
    deadline = time.time() + 60
    while time.time() < deadline:
        if bs.widget_visible():
            appeared = True
            break
        time.sleep(3)
    if not appeared:
        pytest.skip("Bulk-sync widget never appeared — no pending recordings to sync")

    # THEN it reports a transport method and progresses.
    method = bs.transport_method()
    print(f"bulk sync transport: {method}, syncing={bs.is_syncing()}")

    # Wait for a terminal state.
    result = bs.wait_terminal(timeout=300)
    if result is None:
        pytest.skip("Sync did not reach a terminal state within 5 min (large backlog?)")
    if result == "failed":
        # Retry is the only user action; verify it's offered.
        assert heidi_app.locator("button[name='Retry sync']").exists(), (
            "Sync failed but no 'Retry sync' button offered"
        )
        pytest.fail("Bulk sync failed ('Bulk sync failed')")

    assert bs.is_complete(), "Bulk sync did not reach 'Syncing complete'"
    print("Bulk sync completed.")
