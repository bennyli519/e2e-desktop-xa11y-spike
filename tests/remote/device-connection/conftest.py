"""Shared fixture for device-connection tests: open the Devices page.

Chronicle flows need a real Heidi Remote paired/nearby. Tests that require a
device call `require_device`; tests that need you to press the physical button
call `require_manual`. Without a device they skip cleanly.
"""
import time

import pytest
import xa11y

from pages import DevicePage


@pytest.fixture()
def devices(heidi_app: xa11y.App) -> DevicePage:
    dp = DevicePage(heidi_app)
    dp.open()
    time.sleep(2)
    return dp


@pytest.fixture()
def require_device(devices: DevicePage):
    """Skip unless a Chronicle device is paired (DeviceCard present)."""
    if not devices.has_paired_device():
        pytest.skip("No paired Chronicle device — connect one to run this flow")


@pytest.fixture()
def require_manual():
    """Marker fixture: this test needs a human to press the physical device
    button. Set RUN_MANUAL=1 to actually run it; otherwise skip."""
    import os
    if os.environ.get("RUN_MANUAL") != "1":
        pytest.skip(
            "Needs manual physical-device interaction — set RUN_MANUAL=1 and "
            "follow the prompts to run"
        )
