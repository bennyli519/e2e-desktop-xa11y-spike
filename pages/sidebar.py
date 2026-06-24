"""Page Object: left sidebar navigation rail.

Sidebar item roles are INCONSISTENT in the AX tree (verified from dumps):
  - button:    Scribe, Settings, Notifications, New session
  - link:      Evidence, Tasks, My Templates, My Forms, Templates, Team,
               Dictate history
  - combo_box: Devices, Help

So every nav method uses a comma-separated role-alternation selector (the
official xa11y portable pattern) to survive role differences.
"""
import time

import xa11y

from lib import click_first_match


class Sidebar:
    def __init__(self, app: xa11y.App):
        self.app = app

    def _nav(self, name: str) -> bool:
        selectors = [
            f"button[name='{name}'], link[name='{name}'], combo_box[name='{name}']",
            f"static_text[value='{name}']",  # last-resort fallback
        ]
        ok = click_first_match(self.app, selectors)
        if ok:
            time.sleep(1.5)  # allow page transition
        return ok

    def go_to_scribe(self) -> bool:
        return self._nav("Scribe")

    def go_to_devices(self) -> bool:
        return self._nav("Devices")

    def go_to_patients(self) -> bool:
        return self._nav("Patients")

    def go_to_settings(self) -> bool:
        return self._nav("Settings")

    def go_to_evidence(self) -> bool:
        return self._nav("Evidence")

    def go_to_tasks(self) -> bool:
        return self._nav("Tasks")

    def new_session(self) -> bool:
        ok = click_first_match(
            self.app,
            ["button[name='New session']", "static_text[value='New session']"],
        )
        if ok:
            time.sleep(1.5)
        return ok

    def close_modal(self) -> bool:
        """Close a blocking modal (e.g. Settings opens full-screen with a
        'Close' button that hides the sidebar). Safe no-op if none is open."""
        closed = False
        for _ in range(3):
            if not self.app.locator("button[name='Close']").exists():
                break
            if click_first_match(self.app, ["button[name='Close']"]):
                closed = True
                time.sleep(0.8)
        return closed

    def reset_to_scribe(self) -> None:
        """Return to a known baseline: close any modal, then open Scribe."""
        self.close_modal()
        try:
            xa11y.input_sim().press("Escape")
        except Exception:
            pass
        time.sleep(0.3)
        self.go_to_scribe()
