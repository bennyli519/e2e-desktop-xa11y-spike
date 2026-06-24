"""Smoke tests: verify Heidi app launches and key UI elements exist.

These tests only assert element presence — no clicks or typing.
Run first to confirm xa11y can see the Heidi accessibility tree.
"""
import pytest
import xa11y

pytestmark = pytest.mark.smoke


class TestAppBasics:
    def test_app_is_running(self, heidi_app: xa11y.App):
        assert heidi_app.name == "Heidi"
        assert heidi_app.pid is not None

    def test_has_window(self, heidi_app: xa11y.App):
        children = heidi_app.children()
        assert len(children) > 0, "No top-level AX children — window missing?"

    def test_has_web_area(self, heidi_app: xa11y.App):
        """Tauri renders in a web_area element."""
        wa = heidi_app.locator("web_area")
        assert wa.exists()


class TestMainPageElements:
    """Check key elements on the default Scribe page."""

    def test_heidi_title(self, heidi_app: xa11y.App):
        title = heidi_app.locator("static_text[value*='Heidi']")
        title.wait_visible(timeout=10.0)

    def test_transcribe_text(self, heidi_app: xa11y.App):
        t = heidi_app.locator("static_text[value*='Transcribe or add context']")
        t.wait_visible(timeout=10.0)

    def test_prep_button(self, heidi_app: xa11y.App):
        heidi_app.locator("button[name='Prep']").wait_visible(timeout=10.0)

    def test_text_area(self, heidi_app: xa11y.App):
        heidi_app.locator("text_area").wait_visible(timeout=10.0)
