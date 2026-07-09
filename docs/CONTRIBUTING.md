# Contributing

How to add tests and Page Objects. Keep the layering: **selectors in
`pages/`, assertions in `tests/`.**

## TL;DR — how you write a new test case

You do **not** pull the DOM or read scribe-fe-v2's React source for selectors.
xa11y drives the app through the OS **accessibility (AX) tree**, so selectors
come from *dumping the running app*, not from the codebase. The loop:

```
1. Run the app        → open Heidi (or `pnpm tauri:dev` for Mode 1), log in
2. Dump the AX tree   → python scripts/dump_page.py --page <Page>
3. Read the dump      → reports/<Page>_tree.txt → copy real role + name
4. Put selector in a Page Object   (pages/<page>.py) — the ONLY place selectors live
5. Write the spec     (tests/<feature>/test_<case>.py) — assertions only
6. Run from Ghostty   → .venv/bin/python3.14 -m pytest tests/<feature>/test_<case>.py -v -s
7. Iterate to green; the spec stays as a permanent regression test
```

"Latest DOM" = the **live AX tree of the running app**, refreshed with
`dump_page.py`. If a selector breaks after a UI change, re-dump and fix the
Page Object once — specs don't change.

For the **spec-first / develop-until-green** workflow (write the failing spec
before the feature exists), see `docs/SPEC_DRIVEN.md`.

## Adding a new test case — step by step

**Prereq: run from Ghostty.** xa11y needs macOS "Screen & System Audio
Recording" permission, which doesn't propagate from Hermes to child processes.
Run every command below from Ghostty (or a terminal that holds the permission),
with Heidi **logged in and foreground**. If the tree dumps empty, this is why.

**1. Discover the UI — never guess selectors.**

```bash
python scripts/dump_page.py --page Devices   # navigate to a page, then dump it
python scripts/explore_all.py                # walk every page, dump each to reports/
```

Open `reports/<Page>_tree.txt` and copy the real `role` + `name`. Names come
from `aria-label` or visible text — they are often NOT what's painted on screen
(e.g. an icon button may have `name='Audio input'`, a menu button may read
`name='Transcribe Open transcription mode menu'`).

**2. Pick the feature folder** under `tests/` (e.g. `tests/scribe/`,
`tests/device-connection/`). One logical case per file. Create it from the
template so the GIVEN/WHEN/THEN shape is consistent:

```bash
cp templates/test_TICKET_template.py tests/scribe/test_my_case.py
```

**3. Put every selector in a Page Object** (`pages/<page>.py`), never in the
spec. Use role alternation for portability and a fallback chain:

```python
# pages/scribe.py — selector appears here exactly once
def open_firmware_update(self) -> bool:
    return click_first_match(self.app, [
        "button[name='device-update-firmware']",   # preferred: aria-label
        "button[name='Update']",                    # fallback: visible text
    ])
```

Queries return data/bool; actions drive the UI and return success.

**4. Write the spec** (`tests/<feature>/test_<case>.py`) — assertions only.
Encode the acceptance criteria, skip (don't fail) on missing preconditions:

```python
"""scribe: starting a session shows the recording timer."""
import pytest
from pages import ScribePage

pytestmark = [pytest.mark.scribe, pytest.mark.slow]


def test_timer_appears(heidi_app):
    scribe = ScribePage(heidi_app)
    # GIVEN a fresh session
    scribe.new_session()
    # WHEN recording starts
    scribe.start_transcribing()
    # THEN the mm:ss timer is visible
    assert scribe.recording_timer() is not None
```

**5. Register any new marker** in `pyproject.toml` under
`[tool.pytest.ini_options]` `markers`.

**6. Run it from Ghostty and iterate to green:**

```bash
.venv/bin/python3.14 -m pytest tests/scribe/test_my_case.py -v -s
```

> Use the project venv (`.venv/bin/python3.14`), never bare `pytest` — bare
> `pytest` can resolve to the wrong interpreter and give confusing empty-tree
> or "no tests" errors.

### Advanced: many assertions over ONE expensive flow

When a single flow is slow (e.g. a multi-minute recording) but you want one
visible ✓/✗ per acceptance criterion, don't re-run the flow per assertion. Run
it once in a **module-scoped fixture**, cache the result, and have each `test_*`
read the cache. See `tests/recording/` (`_flow.py` runs once → `_cases.py`
assertions → `test_30s.py` etc. exposes one test per check). This gives a
checklist-style report without paying the flow cost N times.

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
