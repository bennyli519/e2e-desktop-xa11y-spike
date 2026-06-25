# Spec-Driven Development with these tests

Two modes, one shared spec + Page Object layer. The goal: **define the
acceptance test first, then develop until it passes.**

```
                 same specs + pages/
                 ┌───────────────────┐
   Mode 1  ──────┤  tests/  pages/    ├────── Mode 2
  Dev Verify     └───────────────────┘     E2E with Bundle
  pnpm tauri:dev                            built .app / CI
  HEIDI_DEV=1                             (default) / HEIDI_APP_PATH
```

## Mode 1 — Dev Verify (drive AI development)

Fast inner loop while building a feature. The spec is written FIRST and is
allowed to fail (red); you develop until it's green.

```
1. Ticket: "Add a Reconnect button on the device card; clicking it reconnects."
2. Write the spec describing the expected behaviour  ── it FAILS (red).
3. Develop the feature in scribe-fe-v2.
4. Hot-reload runs automatically (pnpm tauri:dev).
5. Re-run the spec:  HEIDI_DEV=1 pytest tests/devices/test_reconnect.py
6. Repeat 3–5 until GREEN.
7. The spec stays in the repo as a permanent regression test.
```

Setup:

```bash
# terminal 1 — in scribe-fe-v2
pnpm tauri:dev

# terminal 2 — Ghostty, in this repo
HEIDI_DEV=1 pytest tests/<feature>/ -v -s
```

Why `HEIDI_DEV=1`: it attaches to the running `pnpm tauri:dev` debug binary
by PID (never launches it). See README "Choosing which Heidi build to test".

### Working with an AI assistant

The assistant can't run xa11y itself (macOS 26 permission doesn't reach Hermes
child processes — see CLAUDE.md). So the loop is:

- **You** describe the ticket + acceptance criteria.
- **AI** writes the spec (red), then implements the feature in scribe-fe-v2.
- **You** run `HEIDI_DEV=1 pytest ...` in Ghostty and paste back the result
  (and `reports/artifacts/*.mp4` / `reports/*.txt` on failure).
- **AI** reads the failure, fixes, repeats — until green.

## Mode 2 — E2E with Bundle (release gate)

Full regression against a built, signed `.app`. Specs are already green; this
is the gate before shipping.

```bash
# build the app (in scribe-fe-v2)
pnpm tauri:build-staging          # or build-production

# run the full suite against it
pytest                            # default: open -a Heidi (installed app)
# or point at the freshly built bundle:
HEIDI_APP_PATH="/path/to/Built.app" pytest
```

In CI: use xa11y's `setup-a11y` action to grant the runner permission, build
the app, then `pytest`. Green = shippable.

## Writing a spec (the acceptance test)

One spec file per ticket/case, under the matching `tests/<feature>/` folder.
Use a Page Object for all interaction; assert the expected behaviour.

```python
# tests/devices/test_reconnect.py
"""TICKET-123: clicking Reconnect on a disconnected device reconnects it."""
import time
import pytest
from pages import DevicePage

pytestmark = [pytest.mark.devices, pytest.mark.slow]


def test_reconnect_device(devices: DevicePage):
    # GIVEN a paired, disconnected device
    if not devices.has_device_card():
        pytest.skip("No paired device")
    if devices.is_connected():
        pytest.skip("Already connected")

    # WHEN the user clicks Reconnect
    assert devices.reconnect(), "Reconnect click failed"

    # THEN the device moves to a connected (or reconnecting) state
    time.sleep(6)
    assert devices.is_connected() or \
        devices.app.locator("button[name*='Reconnecting']").exists()
```

If the feature doesn't exist yet, the spec fails — that's the red you develop
against. Encode the acceptance criteria as the assertions.

### If a selector doesn't exist yet

When you're writing the spec before the UI exists, you can't dump a tree. Two
options:
1. Write the spec against the **intended** selector (e.g.
   `button[name='device-reconnect']`) and have the dev add a matching
   `aria-label` — this is the recommended path (stable selector + a11y).
2. Or write it loosely (`button[name*='Reconnect']`) and tighten later.

## Tips for spec-driven flow

- **Encode acceptance criteria as assertions**, not the implementation. Assert
  "device shows Connected", not "the 5th button was clicked".
- **Prefer `aria-label`** for any new element so the selector is stable across
  i18n/state and the spec doesn't break when copy changes.
- **One ticket → one spec file** keeps the red/green signal focused.
- **Keep the spec after it's green** — it's now a regression test for free.
- **Skip on missing preconditions** (no device, not logged in) so a spec fails
  only on a real behaviour regression, not environment.

## Upgrading to BDD later (optional)

If product/QA want to author acceptance criteria in plain language, layer
`pytest-bdd` on top: `.feature` files (Given/When/Then) bind to step functions
that call the **same Page Objects**. No rewrite of `pages/` needed — the
Gherkin sits above it. This mirrors the web suite's Playwright + Cucumber setup.
Defer until the pytest flow is proven.
