"""navigation: creating a new session resets the Scribe view."""
import pytest
import xa11y

from pages import Sidebar

pytestmark = pytest.mark.navigation


@pytest.fixture()
def sidebar(heidi_app: xa11y.App) -> Sidebar:
    sb = Sidebar(heidi_app)
    sb.reset_to_scribe()
    return sb


def test_create_new_session(sidebar: Sidebar):
    assert sidebar.new_session(), "Could not click New session"
    # New session shows the "Ready when you are" empty state
    sidebar.app.locator(
        "heading[value*='Ready when you are'], static_text[value*='Ready when you are']"
    ).wait_visible(timeout=10.0)
