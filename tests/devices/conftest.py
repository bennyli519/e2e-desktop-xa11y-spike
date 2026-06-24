"""Shared fixture for device tests: open the Devices page from a clean state."""
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
