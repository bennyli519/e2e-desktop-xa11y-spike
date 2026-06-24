# Design

How this test suite is structured and why. Read this before adding tests or
porting the suite to another app.

## Goal

Desktop E2E tests for the Heidi Tauri app that are:

- **Stable** — selectors survive UI tweaks, window resizing, and i18n.
- **Maintainable** — one place to fix a selector; one file per test case.
- **Portable** — the same approach works on macOS / Windows / Linux.
- **Agent-friendly** — an AI agent can discover the UI tree, write a spec, run
  it, and read the result, closing the loop for ticket verification.

## Why xa11y (not cua-driver / Playwright / image diffing)

| Approach | Element targeting | Daemon | Stability |
|---|---|---|---|
| **xa11y** (this) | CSS-like selector on the a11y tree | none | high — selector re-resolves every call |
| cua-driver | `element_index` (numeric) | yes, must run | low — index shifts when tree changes |
| image diffing | pixel coordinates | — | very low — breaks on any visual change |
| Playwright | DOM selectors | — | web only; can't drive a native Tauri shell |

xa11y reads the OS accessibility tree (macOS AXUIElement / Windows UIA / Linux
AT-SPI2) through one unified API modelled on Playwright's Locator. We drive the
**real native app**, not a web page, and target elements by role + name rather
than coordinates.

## Layering

Three layers, strictly separated:

```
lib/      infrastructure        "plumbing"      — login flow, helpers
pages/    Page Objects          "how to act"    — selectors + actions
tests/    specs                 "what to check" — assertions only
```

**The rule:** a selector string appears in exactly one place — a Page Object.
Specs never contain selectors; they call Page Object methods and assert on the
result. When the UI changes, you fix one method in `pages/`, and every spec
that uses it keeps working.

### lib/

- `helpers.py` — `click_first_match(app, selectors)`: tries a list of selectors
  in order, presses the first that exists. This is how a single logical action
  survives role/label differences (see "Selector strategy").
- `login.py` — the Auth0 login flow. It spans three processes (Heidi → Chrome →
  back to Heidi) and is the most platform-specific code in the suite.

### pages/

One class per screen/area. Methods are either:
- **queries** (`has_device_card()`, `is_connected()`) — return bool/data, and
- **actions** (`reconnect()`, `type_note()`, `go_to_devices()`) — drive the UI.

A Page Object may own a sub-Page-Object (e.g. `DevicePage` holds a `Sidebar`).

### tests/

Organised by **feature folder**, **one spec file per test case**:

```
tests/
├── smoke/        app launches, key elements render
├── auth/         login
├── navigation/   sidebar nav, new session
├── scribe/       note input
└── devices/      device card, serial, firmware, connection, reconnect, disconnect
```

Run by feature (`pytest tests/devices/`), by marker (`pytest -m devices`), or a
single case (`pytest tests/devices/test_reconnect.py`). A feature folder can
carry its own `conftest.py` for a shared fixture (see `tests/devices/`).

## Selector strategy

xa11y matches the accessibility tree's `name` (which equals the element's
`aria-label`, or its visible text when there's no aria-label) and `role`.

1. **Be specific.** `button[name='Prep']`, never bare `button`.
2. **Role alternation for portability.** Sidebar item roles are inconsistent
   (button / link / combo_box on macOS, and they differ again on Windows UIA).
   Page Objects use comma-separated alternation, the official xa11y pattern:
   ```python
   "button[name='Devices'], link[name='Devices'], combo_box[name='Devices']"
   ```
3. **Prefer aria-label over visible text.** Today many buttons expose only their
   `<FormattedMessage>` text as the name (`"Reconnect"`), which is i18n- and
   state-dependent (`"Reconnecting…"`). Adding `aria-label`s in scribe-fe-v2
   would give stable, language-independent names — and works on all three
   platforms because `name` maps to aria-label everywhere.
4. **Never use coordinates.** Bounds are physical pixels and vary by display /
   window size / DPI. Use selectors; use `InputSim` coordinate clicks only as a
   last resort for elements the a11y tree can't expose.
5. **Locators, not elements, for actions.** A Locator re-resolves its selector
   on every call, so it stays correct as the tree mutates. Cache an Element only
   when you've already inspected it and want to act on that exact instance.

## Waiting

Use xa11y's `wait_visible()` / `wait_until()` — never `sleep()` for
synchronisation. The process-wide default timeout is raised once in
`conftest.py` (`set_default_timeout`) so CI's cold runners don't flake.

## Artifacts

`conftest.py` wires up, for every test:
- a screen recording → `reports/artifacts/<test>.mp4` (macOS `screencapture -v`,
  stopped via SIGINT — newline-to-stdin does NOT save the file),
- a failure screenshot → `reports/artifacts/<test>__FAIL.png` (xa11y), and
- on-demand tree dumps via the `dump_tree` fixture → `reports/<label>.txt`.

## The hard constraint: macOS 26 permissions

"Screen & System Audio Recording" is granted per app bundle. xa11y needs it to
read window content. **Child processes of the Hermes desktop app do not inherit
it** — so this suite must run from a terminal that holds the permission
(Ghostty), or from CI where the test-runner binary is granted directly (see
xa11y's `setup-a11y` action). On Windows this problem does not exist; UIA works
with no permission.
