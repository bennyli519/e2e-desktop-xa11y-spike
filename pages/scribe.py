"""Page Object: Scribe page (main note-taking view)."""
import time

import xa11y

from lib import click_first_match
from pages.sidebar import Sidebar


class ScribePage:
    def __init__(self, app: xa11y.App):
        self.app = app
        self.sidebar = Sidebar(app)

    def open(self) -> bool:
        self.sidebar.close_modal()
        return self.sidebar.go_to_scribe()

    # --- elements ---
    def note_input(self):
        return self.app.locator("text_area")

    def has_new_session_button(self) -> bool:
        return self.app.locator("button[name='New session']").exists()

    def has_prep_button(self) -> bool:
        return self.app.locator("button[name='Prep']").exists()

    # --- actions ---
    def type_note(self, text: str) -> None:
        """Focus the note area and type via real keystrokes (webview-safe)."""
        ta = self.note_input()
        ta.wait_visible(timeout=10.0)
        ta.press()
        time.sleep(0.5)
        xa11y.input_sim().type_text(text)
        time.sleep(1)

    def clear_note(self) -> None:
        try:
            self.note_input().set_value("")
        except Exception:
            pass
