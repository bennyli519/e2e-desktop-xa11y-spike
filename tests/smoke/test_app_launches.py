"""smoke: the app launches and registers with the accessibility API."""
import pytest
import xa11y

pytestmark = pytest.mark.smoke


def test_app_is_running(heidi_app: xa11y.App):
    assert heidi_app.name == "Heidi"
    assert heidi_app.pid is not None


def test_has_window(heidi_app: xa11y.App):
    assert len(heidi_app.children()) > 0, "No top-level AX children — window missing?"


def test_has_web_area(heidi_app: xa11y.App):
    """Tauri renders its UI inside a web_area element."""
    assert heidi_app.locator("web_area").exists()
