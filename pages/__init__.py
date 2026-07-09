"""pages package: Page Objects (how to operate the UI)."""
from pages.auth import AuthPage
from pages.bulk_sync import BulkSyncPage
from pages.device import DevicePage
from pages.firmware import FirmwarePage
from pages.scribe import ScribePage
from pages.sidebar import Sidebar

__all__ = [
    "AuthPage",
    "Sidebar",
    "ScribePage",
    "DevicePage",
    "FirmwarePage",
    "BulkSyncPage",
]
