"""Page Object: Chronicle OTA firmware-update modal.

Verified labels from scribe-fe-v2 firmware-update-modal/ (react-intl). The modal
is a single global instance; startup and manual entry points enqueue the same UI.
All OTA sub-states (downloading..rebooting) render ONE 'Update in progress' view —
only the percentage changes; there are no per-phase text labels.
"""
import time

import xa11y

from lib import click_first_match


class FirmwarePage:
    def __init__(self, app: xa11y.App):
        self.app = app

    # --- entry points -------------------------------------------------------
    def has_update_banner(self) -> bool:
        return self.app.locator(
            "static_text[value*='New Firmware Update']"
        ).exists()

    def open_from_banner(self) -> bool:
        return click_first_match(self.app, ["button[name='Update']"])

    # --- confirm view -------------------------------------------------------
    def confirm_view_shown(self) -> bool:
        return self.app.locator(
            "static_text[value*='New firmware available']"
        ).exists()

    def upgrade_now(self) -> bool:
        return click_first_match(self.app, ["button[name='Upgrade now']"])

    def remind_me_later(self) -> bool:
        return click_first_match(self.app, ["button[name='Remind me later']"])

    # --- in-progress --------------------------------------------------------
    def in_progress(self) -> bool:
        return self.app.locator(
            "static_text[value*='Update in progress']"
        ).exists()

    def progress_percent(self) -> int | None:
        """Read the {n}% shown in the progress ring, if present."""
        for el in self.app.locator("static_text").elements():
            v = (el.value or "").strip()
            if v.endswith("%") and v[:-1].isdigit():
                return int(v[:-1])
        return None

    # --- terminal states ----------------------------------------------------
    def completed(self) -> bool:
        return self.app.locator(
            "static_text[value*='Successfully updated']"
        ).exists()

    def failed(self) -> bool:
        return self.app.locator(
            "static_text[value*='We ran into some issues']"
        ).exists()

    def done(self) -> bool:
        return click_first_match(self.app, ["button[name='Done']"])

    def try_later(self) -> bool:
        return click_first_match(self.app, ["button[name='Try later']"])

    # --- waits --------------------------------------------------------------
    def wait_terminal(self, timeout: float = 600.0) -> str | None:
        """Wait for completed/failed. Returns 'completed'/'failed'/None."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.completed():
                return "completed"
            if self.failed():
                return "failed"
            time.sleep(2)
        return None
