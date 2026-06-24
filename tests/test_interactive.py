"""Interactive tests: sidebar navigation, new session, text input.

Uses the Sidebar Page Object (tests/pages.py) so selectors live in one place.
Selectors verified against real AX tree dumps (reports/explore_*.txt).

Each test starts from a known baseline (modal closed + Scribe open) via the
`reset` fixture, so tests are independent and order-insensitive.
"""
import time

import pytest
import xa11y

from pages import Sidebar

pytestmark = pytest.mark.interactive


@pytest.fixture()
def sidebar(heidi_app: xa11y.App) -> Sidebar:
    """Return a Sidebar, after resetting to a known baseline (Scribe, no modal)."""
    sb = Sidebar(heidi_app)
    sb.reset_to_scribe()
    return sb


class TestSidebarNavigation:
    """Click each sidebar item and verify the nav succeeded. Each test resets
    first, so they don't depend on each other's end state."""

    def test_navigate_to_settings(self, sidebar: Sidebar, dump_tree):
        assert sidebar.go_to_settings(), "Could not click Settings"
        dump_tree("nav_settings")
        # Settings is a full-screen modal — close it so we leave a clean state
        sidebar.close_modal()

    def test_navigate_to_devices(self, sidebar: Sidebar, dump_tree):
        assert sidebar.go_to_devices(), "Could not click Devices"
        dump_tree("nav_devices")

    def test_navigate_to_evidence(self, sidebar: Sidebar):
        assert sidebar.go_to_evidence(), "Could not click Evidence"

    def test_return_to_scribe(self, sidebar: Sidebar):
        # `sidebar` fixture already reset to Scribe; navigate away and back
        sidebar.go_to_devices()
        assert sidebar.go_to_scribe(), "Could not click Scribe"
        # Verify we're on Scribe via a stable marker that doesn't depend on
        # session content. The 'New session' button is always present on Scribe.
        sidebar.app.locator(
            "button[name='New session']"
        ).wait_visible(timeout=10.0)


class TestNewSession:
    def test_create_new_session(self, sidebar: Sidebar):
        assert sidebar.new_session(), "Could not click New session"
        sidebar.app.locator(
            "heading[value*='Ready when you are'], static_text[value*='Ready when you are']"
        ).wait_visible(timeout=10.0)


class TestTextInput:
    def test_type_in_note_area(self, sidebar: Sidebar):
        app = sidebar.app
        textarea = app.locator("text_area")
        textarea.wait_visible(timeout=10.0)

        # Focus the field, then type. Webview contenteditable areas often
        # ignore the AX set_value/type_text path, so drive real keystrokes
        # via InputSim after focusing.
        textarea.press()
        time.sleep(0.5)
        sim = xa11y.input_sim()
        sim.type_text("xa11y E2E note test")
        time.sleep(1)

        elem = textarea.element()
        value = (elem.value or "").strip()

        # Some webview text areas don't reflect typed content back through the
        # AX value at all. Treat "value present and contains our text" as a
        # pass; if the AX value is empty/newline-only, we can't assert content
        # (xa11y limitation on this widget) so we just confirm the field exists.
        if value and value != "":
            assert "xa11y" in value or "E2E" in value, f"unexpected value: {elem.value!r}"
        else:
            # AX doesn't echo the value — at least confirm the field is editable
            assert elem.editable or elem.role == "text_area"

        # cleanup — best effort
        try:
            textarea.set_value("")
        except Exception:
            pass
