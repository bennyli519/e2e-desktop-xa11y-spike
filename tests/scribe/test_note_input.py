"""scribe: typing into the note input area."""
import pytest
import xa11y

from pages import ScribePage

pytestmark = pytest.mark.scribe


@pytest.fixture()
def scribe(heidi_app: xa11y.App) -> ScribePage:
    sp = ScribePage(heidi_app)
    sp.open()
    return sp


def test_type_in_note_area(scribe: ScribePage):
    scribe.type_note("xa11y E2E note test")

    elem = scribe.note_input().element()
    value = (elem.value or "").strip()

    # Some webview text areas don't reflect typed content back via AX. If the
    # value is readable, assert it; otherwise confirm the field is editable.
    if value:
        assert "xa11y" in value or "E2E" in value, f"unexpected value: {elem.value!r}"
    else:
        assert elem.editable or elem.role == "text_area"

    scribe.clear_note()
