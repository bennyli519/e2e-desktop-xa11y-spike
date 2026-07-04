"""Page Object: Chronicle bulk-sync progress UI.

Verified labels from scribe-fe-v2 src/components/bulk-sync/. Bulk sync is
auto-triggered by Rust (device connect / USB mount); the only clickable actions
are 'Retry sync' (on failure) and the transport switches. This PO reads the
BulkSyncWidget + detail card state; it does not start a sync.
"""
import time

import xa11y

from lib import click_first_match


class BulkSyncPage:
    def __init__(self, app: xa11y.App):
        self.app = app

    def widget_visible(self) -> bool:
        return self.app.locator("static_text[value='Syncing']").exists() or any(
            self.app.locator(f"static_text[value*='{t}']").exists()
            for t in ("Syncing sessions", "Syncing complete",
                      "Syncing Interrupted", "Bulk sync failed")
        )

    def transport_method(self) -> str | None:
        for method in ("USB-C", "Wi-Fi", "Bluetooth"):
            if self.app.locator(
                f"static_text[value*='Transferring via {method}']"
            ).exists():
                return method
        return None

    def is_syncing(self) -> bool:
        return (
            self.app.locator("static_text[value='Syncing']").exists()
            or self.app.locator("static_text[value*='Syncing sessions']").exists()
        )

    def is_complete(self) -> bool:
        return self.app.locator(
            "static_text[value*='Syncing complete']"
        ).exists()

    def is_interrupted(self) -> bool:
        return self.app.locator(
            "static_text[value*='Syncing Interrupted']"
        ).exists()

    def is_failed(self) -> bool:
        return self.app.locator("static_text[value*='Bulk sync failed']").exists()

    def retry_sync(self) -> bool:
        return click_first_match(self.app, ["button[name='Retry sync']"])

    def wait_terminal(self, timeout: float = 300.0) -> str | None:
        """Wait for complete/failed. Returns state string or None on timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_complete():
                return "complete"
            if self.is_failed():
                return "failed"
            time.sleep(2)
        return None
