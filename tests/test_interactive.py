"""Interactive tests: sidebar navigation, text input, button clicks.

NOTE: Selectors here are based on the initial Ghostty tree dump.
The Tauri web_area AX tree can vary — if a test fails, run:
    python scripts/dump_page.py --page <PageName>
to inspect the actual element names/values, then fix selectors.
"""
import time

import pytest
import xa11y

pytestmark = pytest.mark.interactive


class TestSidebarNavigation:
    """Click sidebar items and verify view changes."""

    @pytest.mark.parametrize("page", ["Patients", "Settings", "Devices"])
    def test_navigate_to_page(self, heidi_app: xa11y.App, dump_tree, page: str):
        # Dump before for debugging
        dump_tree(f"before_{page}")

        # Try clicking the sidebar item
        loc = heidi_app.locator(f"static_text[value='{page}']")
        loc.wait_visible(timeout=10.0)
        loc.press()
        time.sleep(2)

        # Dump after for debugging
        dump_tree(f"after_{page}")

    def test_return_to_scribe(self, heidi_app: xa11y.App):
        loc = heidi_app.locator("static_text[value='Scribe']")
        loc.wait_visible(timeout=10.0)
        loc.press()
        time.sleep(1)

        heidi_app.locator("static_text[value*='Transcribe']").wait_visible(timeout=10.0)


class TestNewSession:
    def test_create_new_session(self, heidi_app: xa11y.App):
        # Navigate to Scribe first
        heidi_app.locator("static_text[value='Scribe']").press()
        time.sleep(1)

        new_btn = heidi_app.locator("button[name='New session']")
        if not new_btn.exists():
            # Might be a static_text inside a clickable group
            new_btn = heidi_app.locator("static_text[value='New session']")

        new_btn.wait_visible(timeout=10.0)
        new_btn.press()
        time.sleep(1)

        heidi_app.locator("heading[value*='Ready when you are']").wait_visible(timeout=10.0)


class TestTextInput:
    def test_type_in_note_area(self, heidi_app: xa11y.App):
        # Ensure on Scribe page
        heidi_app.locator("static_text[value='Scribe']").press()
        time.sleep(1)

        textarea = heidi_app.locator("text_area")
        textarea.wait_visible(timeout=10.0)
        textarea.press()
        textarea.type_text("Test input from xa11y E2E")
        time.sleep(1)

        # Verify text was entered
        elem = textarea.element()
        assert elem.value and "xa11y" in elem.value, f"Expected typed text, got: {elem.value}"

        # Clean up
        textarea.set_value("")
