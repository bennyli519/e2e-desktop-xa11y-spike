"""TICKET-XXX: <one-line description of the behaviour being verified>.

Spec-driven: write this FIRST (it will fail), then develop until green.
See docs/SPEC_DRIVEN.md.

Copy this file into the matching feature folder and rename, e.g.:
    tests/devices/test_<behaviour>.py
    tests/scribe/test_<behaviour>.py

Run while developing:
    HEIDI_ENV=dev pytest tests/<feature>/test_<behaviour>.py -v -s
"""
import pytest
import xa11y

# Pick the Page Object(s) your behaviour touches.
from pages import DevicePage, ScribePage, Sidebar  # noqa: F401

# Mark with the feature + 'slow' if it waits on hardware/animation.
pytestmark = pytest.mark.devices  # change to: smoke | auth | navigation | scribe | devices


def test_behaviour(heidi_app: xa11y.App):
    # GIVEN — set up a known precondition (and skip if it can't be met)
    page = DevicePage(heidi_app)
    page.open()
    # if not page.has_device_card():
    #     pytest.skip("No paired device")

    # WHEN — perform the user action via a Page Object method
    # assert page.reconnect(), "action failed"

    # THEN — assert the expected behaviour (the acceptance criterion)
    # assert page.is_connected()
    raise NotImplementedError("Fill in GIVEN/WHEN/THEN, then delete this line.")
