"""navigation: clicking sidebar items navigates between pages.

Each test resets to a known baseline (modal closed + Scribe open) via the
`sidebar` fixture, so tests are independent and order-insensitive.
"""
import pytest
import xa11y

from pages import Sidebar

pytestmark = pytest.mark.navigation


@pytest.fixture()
def sidebar(heidi_app: xa11y.App) -> Sidebar:
    sb = Sidebar(heidi_app)
    sb.reset_to_scribe()
    return sb


def test_navigate_to_settings(sidebar: Sidebar, dump_tree):
    assert sidebar.go_to_settings(), "Could not click Settings"
    dump_tree("nav_settings")
    sidebar.close_modal()  # Settings is a full-screen modal — leave clean state


def test_navigate_to_devices(sidebar: Sidebar, dump_tree):
    assert sidebar.go_to_devices(), "Could not click Devices"
    dump_tree("nav_devices")


def test_navigate_to_evidence(sidebar: Sidebar):
    assert sidebar.go_to_evidence(), "Could not click Evidence"


def test_return_to_scribe(sidebar: Sidebar):
    sidebar.go_to_devices()
    assert sidebar.go_to_scribe(), "Could not click Scribe"
    # 'New session' button is always present on Scribe (content-independent)
    sidebar.app.locator("button[name='New session']").wait_visible(timeout=10.0)
