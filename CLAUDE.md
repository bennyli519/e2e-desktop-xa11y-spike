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

- smoke / auth / navigation / scribe all pass.
- **Recording POC (APP-7808):** `tests/recording/` drives login → new session →
  record → stop → note generation, with real audio injected via BlackHole and a
  transcript-accuracy check (verbatim Transcript tab, `TRANSCRIPT_MATCH_THRESHOLD`
  default 0.9). 30s/5min/10min cases all green locally (100%/100%/92%).
  See `docs/RUNNING.md` for setup/CI and `scripts/bootstrap.sh` for one-shot prep.
- **Device flows restructured** into one-flow-per-file:
  `tests/device-connection/` (first-onboarding, connected-reconnect,
  reconnect-stress ×10, startup-autoconnect, remote-lost), `tests/ota-upgrade/`,
  `tests/remote-session-recording/`, `tests/bulk-sync/`. Selectors traced from
  scribe-fe-v2 source (text-match now, aria-labels later). **Verified on real
  hardware (HV0_251106_000003):** first-onboarding, connected-reconnect,
  reconnect-stress (100%), startup-autoconnect, remote-lost all PASS. Remote
  session recording skips (input-trigger has no AX name); ota/bulk-sync need
  a firmware update / pending offline recordings to exercise.
- Device tests skip cleanly when no device is paired (`require_device` fixture).
  Destructive ones (remove/onboarding/ota) are guarded by `RUN_MANUAL=1`.
- Auto-login works end-to-end (the hard part — see below).
- Per-test video recording + failure screenshots wired in `conftest.py`.
- Pushed to https://github.com/bennyli519/e2e-desktop-xa11y-spike; recording +
  device work is on branch `poc/scribe-recording-flows` (PR #1).

## Environment (as of the spike)

- Python 3.11, xa11y 0.9.1.
- Original spike ran xa11y from `~/.hermes/hermes-agent/venv/bin/` but on a
  fresh machine use a normal `.venv` (`pip install -e .`).
- Heidi installed at `/Applications/Heidi.app`.
- Test account: `bennyli9612@gmail.com` (password in `.env.e2e`, gitignored).

## Test-account strategy (decided) — fixed account + per-run reset, NOT re-register

Every run uses ONE fixed test account (above) and resets STATE at the start of
each flow, rather than registering a fresh account each run. Rationale:
- Sign-up needs email verification + a brand-new unused inbox every run (else
  "email already registered"); its form is in the Auth0 browser (invisible to
  AX); Auth0 rate-limits automated sign-ups.
- A fresh account is EMPTY — no org/templates/team/paired device/pending
  recordings — so Scribe/Evidence/device/bulk-sync cases have no data to test
  and produce false skips/fails.
- What we actually want is a CLEAN STATE, not a new account: each flow opens a
  fresh session and cleans up dangling state (see recording's
  `_reach_fresh_session`, which Ends a leftover recording first). Add a per-domain
  `reset` fixture where isolation is needed; delete test data afterwards.
- Registration (TCD014) is tested as its OWN standalone case, NOT as a
  precondition for other tests.
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
10. **Heidi window backgrounded → EMPTY AX tree.** A non-foreground WKWebView
    stops publishing its AX tree (you get a 20-char stub). Keep Heidi frontmost;
    the recording harness runs `osascript -e 'tell application "Heidi" to
    activate'` before acting.
    - **This also fails across Spaces:** a window on a NON-ACTIVE Mission Control
      Space reads empty too (`count of windows` = 0). Putting Heidi on its own
      Desktop and working elsewhere does NOT work — Heidi must be on the ACTIVE
      Space AND frontmost. Run device tests with Heidi + terminal on one Space
      and don't switch away for the duration.
    - **Mid-flow focus steal is the #1 device-test flake:** a long flow (remove
      ~1.5 min) fails if any window (e.g. an editor) grabs focus partway. The
      device `wait_*()` helpers re-activate Heidi each poll (`_activate_heidi()`
      in pages/device.py) to self-heal, but still avoid stealing focus.
11. **BlackHole device missing after install** → reload CoreAudio with
    `sudo killall coreaudiod` (SIP blocks the non-sudo `launchctl kickstart`);
    verify with `system_profiler SPAudioDataType | grep -i BlackHole`.
12. **Device-card label/value are SEPARATE sibling static_text nodes**, not
    "Label: value" in one node (e.g. `"Serial Number"` then `"HV0_..."`;
    `"Connected via "` then `"Bluetooth"`; `"Battery"` then `"100"`). Read the
    label node, then grab the adjacent value node — don't split on `:`.
13. **Device removal has no distinct success screen on the lost path** — the app
    reverts straight to the initial pairing card. `wait_remove_success()` accepts
    either the success text OR `has_initial_pairing_card()`.
14. **Fresh re-pair over BLE is slow** — after removing a device, reconnecting in
    onboarding can take >40s to reach "Successfully connected". Poll up to ~80s.
15. **Onboarding setup wizard = multiple screens**, verified real order:
    default-note `Confirm` → language `Confirm` → Onboarding Basics (`Next`×3 →
    `Done`) → Enable USB-C modal (`Dismiss`). `DevicePage.complete_onboarding_setup()`
    clicks whatever advance button is present until none remain.
16. **Input-source trigger is icon-only (no AX name)** — can't select "Heidi
    Remote" as the recording input by text yet. remote-session recording skips
    until scribe-fe-v2 adds an aria-label to `v2-input-source-trigger`.

## How to work on this repo

- **Skill:** for the full add-a-test workflow, load `.claude/skills/e2e-test-authoring/`.
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

## Spec-driven workflow (the intended use)

Two modes, shared specs + Page Objects (see `docs/SPEC_DRIVEN.md`):

- **Mode 1 — Dev Verify**: write a spec FIRST (it fails), then develop the
  feature until green. `HEIDI_DEV=1` attaches to `pnpm tauri:dev`. This is
  how the AI loop should run: AI writes spec + feature code, human runs
  `HEIDI_DEV=1 pytest tests/<feature>/` in Ghostty, pastes results back.
- **Mode 2 — E2E with Bundle**: full regression against a built `.app`
  (`default / HEIDI_APP_PATH` or `HEIDI_APP_PATH`), the release gate / CI.

New ticket → copy `templates/test_TICKET_template.py` into the right
`tests/<feature>/` folder, encode the acceptance criteria as GIVEN/WHEN/THEN
assertions, develop until green, keep it as a regression test.

## App launch / selection

**Default is portable & zero-config**: `open -a Heidi` (LaunchServices finds it
anywhere — no hard-coded paths) + attach by name. `pytest` just works on any
machine with Heidi installed.

Env-var overrides (priority order), all optional:
- `HEIDI_PID=<pid>` — attach to one exact process.
- `HEIDI_DEV=1` — attach to a running `pnpm tauri:dev` debug binary (attach-only;
  path from `SCRIBE_FE_PATH`/`HEIDI_DEV_BIN`). For local dev (Mode 1).
- `HEIDI_APP_PATH=/x.app` — launch a specific .app by path; only needed to
  disambiguate MULTIPLE same-named builds on one machine.
- `HEIDI_APP_NAME=Heidi(Staging)` — different AX/app name for open -a + by_name.

`HEIDI_DEV=1` is the Mode 1 (dev verify) selector; default/HEIDI_APP_PATH is
Mode 2 (bundle). PID-matching (executable-path) is only used in the dev and
explicit-path branches, to skip helper subprocesses.
