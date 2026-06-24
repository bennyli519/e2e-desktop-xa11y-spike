# Contributing

How to add tests and Page Objects. Keep the layering: **selectors in
`pages/`, assertions in `tests/`.**

## Before anything: run from Ghostty

xa11y needs macOS "Screen & System Audio Recording" permission, which doesn't
propagate from Hermes to child processes. Run all commands from Ghostty (or a
terminal that holds the permission). If the tree dumps empty, this is why.

## Discover the UI first — never guess selectors

```bash
python scripts/dump_page.py --page Devices   # navigate then dump one page
python scripts/explore_all.py                # walk all pages, dump each to reports/
```

Read the dump and copy the real `role` + `name`. Names come from `aria-label`
or visible text — they are often NOT what's painted on screen.

## Add a test case (one spec file)

1. Pick or create the feature folder under `tests/` (e.g. `tests/devices/`).
2. Create `test_<case>.py`. One logical case per file.
3. Use a Page Object for all UI interaction; assert in the spec.
4. Mark it with the feature marker.

```python
# tests/devices/test_battery.py
"""devices: battery level is shown when the device is connected."""
import pytest
from pages import DevicePage

pytestmark = pytest.mark.devices


def test_battery_shown(devices: DevicePage):          # `devices` fixture from tests/devices/conftest.py
    if not devices.has_device_card():
        pytest.skip("No paired device")
    if not devices.is_connected():
        pytest.skip("Battery only shown when connected")
    assert devices.has_battery()
```

Register new markers in `pyproject.toml` under `[tool.pytest.ini_options]`.

## Add a Page Object method

Put the selector here, not in the spec. Use role alternation for portability,
and a fallback chain via `click_first_match`.

```python
# pages/device.py
def open_firmware_update(self) -> bool:
    return click_first_match(self.app, [
        "button[name='device-update-firmware']",   # preferred: aria-label
        "button[name='Update']",                    # fallback: visible text
    ])
```

Queries return data/bool; actions drive the UI and return success.

## Add a whole new page

1. Create `pages/<page>.py` with a class holding `self.app` (and a `Sidebar`
   if it needs navigation).
2. Export it in `pages/__init__.py`.
3. Add a `tests/<feature>/` folder; optionally a local `conftest.py` with a
   fixture that opens the page from a clean state (see `tests/devices/conftest.py`).

## Conventions

- **Wait, don't sleep** for synchronisation: `loc.wait_visible()`,
  `loc.wait_until(...)`. Reserve `time.sleep` for letting an animation settle.
- **Tests are independent** — reset to a known state in a fixture
  (`Sidebar.reset_to_scribe()`), don't rely on another test's end state.
- **Skip, don't fail, on missing hardware** — if a BLE device isn't present,
  `pytest.skip(...)` with a pointer to the relevant `reports/*.txt` dump.
- **Typing into webviews**: focus, then `InputSim.type_text`. For secrets or
  fields that drop characters, type char-by-char with a small delay.
- **Debugging**: call the `dump_tree("label")` fixture to snapshot the tree to
  `reports/label.txt`; check `reports/artifacts/<test>__FAIL.png` after a fail.

## Running

```bash
pytest                                    # all
pytest -m devices                         # by marker
pytest tests/devices/                     # by folder
pytest tests/devices/test_reconnect.py    # one case
pytest -k reconnect                       # by name substring
RECORD_VIDEO=0 pytest                      # skip recording (faster)
```

## When a selector breaks

1. Re-dump the page: `python scripts/dump_page.py --page <Page>`.
2. Find the element's real `role`/`name` in `reports/<page>_tree.txt`.
3. Fix the selector in the Page Object **once** — specs don't change.
