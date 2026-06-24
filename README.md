# Heidi Desktop E2E Tests (xa11y spike)

Accessibility-tree-based desktop E2E tests for the Heidi app using [xa11y](https://xa11y.dev/).

## Prerequisites

- macOS 26+ with **Screen & System Audio Recording** permission granted to your terminal (Ghostty)
- Heidi app installed at `/Applications/Heidi.app`
- Python 3.11+

> **⚠️ Must run from Ghostty (or another terminal with Screen Recording permission).**
> Hermes's embedded terminal doesn't inherit the permission — the AX tree will be empty.

## Setup

```bash
cd ~/Desktop/heidi/e2e-desktop-xa11y-spike
pip install -e .
```

## Running tests

```bash
# All tests
pytest

# Smoke only (render checks)
pytest -m smoke

# Interactive tests (clicks, typing)
pytest -m interactive

# Bluetooth device tests
pytest -m bluetooth
```

## Exploring the UI tree

Before writing new tests, dump the AX tree to discover selectors:

```bash
# Current page
python scripts/dump_page.py

# Navigate to a page first
python scripts/dump_page.py --page Devices
python scripts/dump_page.py --page Settings
python scripts/dump_page.py --page Patients
```

Tree dumps are saved to `reports/` for inspection.

## Writing tests

```python
def test_example(heidi_app: xa11y.App, dump_tree):
    # Navigate
    heidi_app.locator("static_text[value='Settings']").press()

    # Wait for element
    heidi_app.locator("heading[value*='Settings']").wait_visible(timeout=10.0)

    # Assert
    assert heidi_app.locator("button[name='Save']").exists()

    # Debug: dump tree to reports/
    dump_tree("settings_page")
```

## Selector reference

| Pattern | Meaning |
|---|---|
| `button[name='OK']` | Button named exactly "OK" |
| `static_text[value*='hello']` | Text containing "hello" |
| `text_area` | Any text area |
| `heading[value*='Ready']` | Heading containing "Ready" |
| `group[name='Notifications']` | Named group |

## Known issues

- Tauri's WKWebView AX tree can be inconsistent — element names/values may vary
- Some elements only have `value` set, not `name`
- `static_text` elements often use `value` for visible text, `name` is empty
- Run `dump_page.py` whenever selectors break to re-discover the tree
