---
name: e2e-test-authoring
description: >-
  Author, run, and debug Heidi desktop E2E tests in this xa11y repo. Use when
  adding a new test case or flow, finding/fixing selectors, writing Page
  Objects, or when a test dumps an empty AX tree or a selector breaks. Covers
  the dump→Page Object→spec→run loop, the macOS Screen-Recording permission
  pitfall, and the spec-driven (write-failing-spec-first) workflow.
---

# Heidi desktop E2E test authoring (xa11y)

This repo tests the **Heidi Tauri desktop app** via [xa11y](https://xa11y.dev/),
which drives native apps through the OS accessibility (AX) tree with a
Playwright-style Locator API. Selectors come from **dumping the running app**,
NOT from reading scribe-fe-v2's React source or any DOM.

## The one rule that surprises people

You never "pull the latest DOM". You dump the **live AX tree of the running
Heidi app** and read the real `role` + `name` off it. Element names come from
`aria-label` or visible text — often not the words painted on screen.

## Hard prerequisite: run from a permissioned terminal

xa11y needs macOS **Screen & System Audio Recording** permission. On macOS 26+
this is per-binary and does **not** propagate to child processes. So:

- Run everything from **Ghostty** (or Terminal.app) that holds the permission.
- An AI assistant running inside Hermes **cannot** run the tests — its child
  python/xa11y get an empty tree (menu bar only, ~20 chars). The assistant
  WRITES code; the human RUNS it from Ghostty and pastes results back.
- Heidi must be **logged in and foreground** (a backgrounded WKWebView blanks
  its AX tree; a window on a non-active Space reads empty too).

If a dump comes back empty, it's almost always this — not a code bug.

## Architecture (keep the layering)

```
lib/      infrastructure  — login, helpers (click_first_match), audio injection
pages/    Page Objects     — selectors + actions; the ONLY place selectors live
tests/    specs            — assertions only; one file per case, grouped by feature
```

A selector string appears in exactly ONE place: a Page Object method. UI
changed → fix that method once; specs stay untouched.

## Adding a new test case — the loop

1. **Run the app.** `open -a Heidi` (Mode 2, installed build) or
   `pnpm tauri:dev` in scribe-fe-v2 + `HEIDI_DEV=1` (Mode 1, dev build). Log in.

2. **Dump the AX tree** to discover selectors:
   ```bash
   python scripts/dump_page.py --page Devices   # navigate to a page then dump
   python scripts/explore_all.py                # walk all pages → reports/*.txt
   ```
   Read `reports/<Page>_tree.txt`, copy the real `role[name='...']`.

3. **Put the selector in a Page Object** (`pages/<page>.py`). Prefer an
   `aria-label` selector, fall back to visible text, via `click_first_match`:
   ```python
   def open_firmware_update(self) -> bool:
       return click_first_match(self.app, [
           "button[name='device-update-firmware']",  # preferred: aria-label
           "button[name='Update']",                   # fallback: visible text
       ])
   ```
   Queries return data/bool; actions drive the UI and return success.

4. **Write the spec** from the template (assertions only, GIVEN/WHEN/THEN):
   ```bash
   cp templates/test_TICKET_template.py tests/<feature>/test_<case>.py
   ```
   Skip (don't fail) on missing preconditions (no device, not logged in) so a
   red only ever means a real behaviour regression.

5. **Register any new marker** in `pyproject.toml` `[tool.pytest.ini_options]`.

6. **Run from Ghostty, iterate to green:**
   ```bash
   .venv/bin/python3.14 -m pytest tests/<feature>/test_<case>.py -v -s
   ```
   Use the project venv, NEVER bare `pytest` (bare pytest can grab the wrong
   interpreter → confusing empty-tree / "no tests ran" errors).

The green spec stays as a permanent regression test.

## Spec-driven variant (feature doesn't exist yet)

Write the spec FIRST against the *intended* selector (have the dev add a
matching `aria-label`), let it fail red, develop until green. Full workflow in
`docs/SPEC_DRIVEN.md`. AI writes spec + feature; human runs
`HEIDI_DEV=1 pytest ...` in Ghostty and pastes results.

## Many assertions over one slow flow

For an expensive flow (multi-minute recording) where you want one visible ✓/✗
per acceptance criterion: run the flow ONCE in a module-scoped fixture, cache
the result, and have each `test_*` read the cache. Pattern lives in
`tests/recording/`: `_flow.py` (runs once) → `_cases.py` (shared assertions) →
`test_30s.py` / `test_1min.py` / … (one test per check). Don't re-run the flow
per assertion.

## Cross-platform audio (recording tests)

Recording specs are platform-agnostic — same wav clips, same assertions on
macOS and Windows. Only injection differs, hidden in `lib/audio.py`'s
`AudioInjector`: macOS routes system I/O to **BlackHole** + `afplay`; Windows
plays into **VB-CABLE** and UI-selects "CABLE Output". Regenerate clips with
`scripts/setup_audio.sh`. Windows needs `pip install -e ".[windows]"` (miniaudio).

## When a selector breaks

1. Re-dump the page: `python scripts/dump_page.py --page <Page>`.
2. Find the element's real `role`/`name` in `reports/<page>_tree.txt`.
3. Fix the selector in the Page Object **once** — specs don't change.

## Conventions

- **Wait, don't sleep**: `loc.wait_visible()` / `wait_until(...)`. Reserve
  `time.sleep` for letting an animation settle.
- **Tests are independent** — reset to a known state in a fixture
  (`Sidebar.reset_to_scribe()`), never rely on another test's end state.
- **aria-label is the stable selector** — `data-testid` is invisible to the AX
  tree. Add `aria-label` in scribe-fe-v2 for new elements you need to target.
- **Typing into webviews**: focus, then `InputSim.type_text`; for secrets or
  fields that drop chars, type char-by-char with a small delay.
- **Debugging**: use the `dump_tree("label")` fixture to snapshot the tree to
  `reports/label.txt`; check `reports/artifacts/<test>__FAIL.png` after a fail.

## Reference docs in this repo

- `docs/CONTRIBUTING.md` — the same flow in prose + Page Object / new-page guides
- `docs/SPEC_DRIVEN.md` — the two run modes + write-spec-first loop
- `docs/RUNNING.md` / `docs/RUNNING_WINDOWS.md` — full setup, CI, cross-platform
- `CLAUDE.md` — repo context, the permission constraint, solved pitfalls
