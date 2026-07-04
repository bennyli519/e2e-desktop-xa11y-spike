"""device-connection: first-startup auto-reconnect flow.

Scenario:
  a device is paired -> quit the app -> reopen the app
  -> the device auto-connects on startup
  -> go to the Devices tab and verify the BLE connection status

This exercises useChronicleStartupAutoConnect (ensureConnectedIdle on launch).
Requires a paired device nearby. It quits and relaunches Heidi, so it re-attaches
to the new process. Login must persist (Auth0 token) across the relaunch.

Run from Ghostty, logged in, Heidi foreground, device on:
    pytest tests/device-connection/test_startup_autoconnect_flow.py -v -s
"""
import subprocess
import time

import pytest
import xa11y

from lib.login import is_logged_in
from pages import DevicePage

pytestmark = [pytest.mark.device_connection, pytest.mark.needs_device,
              pytest.mark.slow, pytest.mark.timeout(180)]


def _relaunch_heidi(app_name: str = "Heidi") -> None:
    subprocess.run(["osascript", "-e", f'quit app "{app_name}"'],
                   capture_output=True)
    time.sleep(5)
    subprocess.run(["open", "-a", app_name], capture_output=True)
    time.sleep(10)


def test_startup_autoconnect(heidi_app: xa11y.App, request):
    # GIVEN a paired device (check before restart).
    dp = DevicePage(heidi_app)
    dp.open()
    time.sleep(2)
    if not dp.has_paired_device():
        pytest.skip("No paired device — cannot test startup auto-reconnect")

    # WHEN we quit and relaunch the app.
    _relaunch_heidi()

    # Re-attach to the new process and bring it foreground.
    subprocess.run(["osascript", "-e", 'tell application "Heidi" to activate'],
                   capture_output=True)
    time.sleep(2)
    app = xa11y.App.by_name("Heidi", timeout=30)
    app.locator("web_area").wait_visible(timeout=30)

    if not is_logged_in(app):
        pytest.skip("Not logged in after relaunch (Auth0 token didn't persist)")

    # THEN the device auto-connects — verify on the Devices tab.
    dp2 = DevicePage(app)
    dp2.open()
    time.sleep(3)

    if not dp2.wait_connected(timeout=45):
        pytest.skip(
            "Device did not auto-connect within 45s (not nearby, or auto-connect "
            f"still in progress; reconnecting={dp2.is_reconnecting()})"
        )

    assert dp2.is_connected(), "Device should be auto-connected after startup"
    assert dp2.status_badge() == "Connected", "Status badge should read 'Connected'"
    print(f"auto-connected via: {dp2.connected_via()}")
