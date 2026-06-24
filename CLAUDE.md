# CLAUDE.md

Context for an AI assistant working on this repo. Read this first — it captures
everything learned during the spike so you don't re-derive it.

## What this is

A **spike** evaluating [xa11y](https://xa11y.dev/) as the engine for Heidi
desktop E2E tests, intended to replace an older `cua-driver`-based suite. xa11y
drives native desktop apps via the OS accessibility tree (macOS AXUIElement /
Windows UIA / Linux AT-SPI2) with a Playwright-style Locator API. We test the
**Heidi Tauri app** (WKWebView on macOS).

Goal behind it: let an agent verify each ticket's UI behaviour automatically —
discover the tree, write a spec, run it, read the result.

## Current state

- 21 tests, feature-organised. smoke / auth / navigation / scribe all pass.
  devices (7) need a run against real Chronicle BLE hardware (they skip if no
  device is present).
- Auto-login works end-to-end (the hard part — see below).
- Per-test video recording + failure screenshots wired in `conftest.py`.
- Pushed to https://github.com/bennyli519/e2e-desktop-xa11y-spike (branch `master`).

## Environment (as of the spike)

- Python 3.11, xa11y 0.9.1.
- Original spike ran xa11y from `~/.hermes/hermes-agent/venv/bin/` but on a
  fresh machine use a normal `.venv` (`pip install -e .`).
- Heidi installed at `/Applications/Heidi.app`.
- Test account: `bennyli9612@gmail.com` (password in `.env.e2e`, gitignored).
- Reference (old) framework cloned at `/tmp/Desktop-E2E-Test` during the spike
  — the cua-driver suite we ported structure/logic from. Source:
  https://github.com/bennyli519/Desktop-E2E-Test

## THE critical constraint — macOS 26 permissions

xa11y needs both **Accessibility** and **Screen & System Audio Recording**
permissions. On macOS 26 these are granted **per app bundle and do NOT
propagate to child processes** spawned by another app.

- An AI agent running inside the Hermes desktop app **cannot** drive xa11y —
  its child python/xa11y processes don't inherit Hermes's grant. The tree comes
  back empty (menu bar only).
- **Tests must be run by the human from Ghostty** (which holds the permission),
  or in CI where the runner binary is granted directly (xa11y's `setup-a11y`).
- So: as the assistant, you WRITE and FIX the code; the human RUNS it from
  Ghostty and pastes back results / `reports/*.txt` dumps. Don't try to run the
  suite yourself — you'll just get empty trees and waste turns.

## Architecture (keep this layering)

```
lib/      infrastructure   — login flow, helpers (click_first_match)
pages/    Page Objects      — selectors + actions; the ONLY place selectors live
tests/    specs             — assertions only; one file per case, by feature
```

Selector string appears in exactly one place: a Page Object. UI changed → fix
the Page Object method once; specs are untouched.

## Selector rules (hard-won)

- Match on `role` + `name`. `name` = aria-label, or visible text if no
  aria-label.
- Sidebar item roles are INCONSISTENT: Scribe/Settings/Notifications/New session
  are `button`; Evidence/Tasks/Templates/etc are `link`; Devices/Help are
  `combo_box`. Use comma-separated role alternation:
  `"button[name='Devices'], link[name='Devices'], combo_box[name='Devices']"`.
- Today button names come from `<FormattedMessage>` text → i18n/state-dependent
  (`"Reconnect"` vs `"Reconnecting…"`). The right fix is adding `aria-label`s in
  scribe-fe-v2 (branch `test/xa11y-aria-labels` was started for this). Page
  Objects already prefer an aria-label selector first, then fall back to text.
- Never use coordinates. Use `wait_*()`, never `sleep()` for synchronisation.

## Pitfalls already solved (don't rediscover these)

1. **Empty tree** → almost always the macOS 26 permission / wrong terminal.
2. **Chrome web content invisible to AX** (no `--force-renderer-accessibility`)
   → for Auth0 we match the Chrome **window title** and drive via keyboard.
3. **Chinese IME mangles typed text** (`a1`→`啊`) → `lib/login.py` forces an
   ABC/Latin layout via a Swift TIS snippet before typing.
4. **Webviews drop fast-typed chars** → type char-by-char via `InputSim` with a
   small delay; don't trust one `type_text()` for passwords.
5. **`chord("a",["Meta"])` leaks a literal 'a'** → clear with Backspace, not Cmd+A.
6. **Stale exported `HEIDI_E2E_PASSWORD` shadowed `.env.e2e`** → loader reads the
   file first; tell the human to `unset` any exported one.
7. **Chrome "Open Heidi?" protocol dialog** (native, empty button names) → find
   `window "Open Heidi?"`, press the last button.
8. **Settings is a full-screen modal** hiding the sidebar → `Sidebar.reset_to_scribe()`
   closes modals before each nav test.
9. **Some text areas don't echo value via AX** (read `'\n'`) → assert `editable`/
   role instead of content.

## How to work on this repo

- Discover selectors from real dumps, never guess:
  `python scripts/dump_page.py --page <Page>` → read `reports/<page>_tree.txt`.
- Add a test: new `tests/<feature>/test_<case>.py`, use a Page Object, mark with
  the feature marker, assert in the spec. See `docs/CONTRIBUTING.md`.
- Add a Page Object method: put the selector there with a fallback chain.
- When a selector breaks: re-dump, find the real role/name, fix the Page Object.
- The human runs `pytest` from Ghostty and pastes results / dumps back to you.

## Open next steps

1. Run `pytest tests/devices/ -v -s` against real hardware; refine
   `pages/device.py` from `reports/devices_card.txt`.
2. Add `aria-label`s in scribe-fe-v2, then switch Page Object selectors to them.
3. Pin the target Heidi version (installed release vs a build with aria-labels).
4. Wire CI with `xa11y/setup-a11y` once green locally.
5. Expand coverage mirroring the cua-driver matrix (connection, onboarding,
   recording, firmware, sessions).
