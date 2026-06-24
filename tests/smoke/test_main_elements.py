"""smoke: key elements render on the main Scribe page."""
import pytest
import xa11y

from pages import ScribePage

pytestmark = pytest.mark.smoke


@pytest.fixture()
def scribe(heidi_app: xa11y.App) -> ScribePage:
    sp = ScribePage(heidi_app)
    sp.open()
    return sp


def test_new_session_button(scribe: ScribePage):
    assert scribe.has_new_session_button()


def test_prep_button(scribe: ScribePage):
    assert scribe.has_prep_button()


def test_note_input_present(scribe: ScribePage):
    assert scribe.note_input().exists()
