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
17. **Record control is a SPLIT BUTTON, collapsed to ONE AX node.** The green
    Transcribe button + its ChevronDown caret render as a single node named
    `"Transcribe Open transcription mode menu"`. `press()` fires the DEFAULT
    action (starts recording!) — to open the mode menu (Transcribe / Dictate /
    Upload session audio) call `element.expand()`, NOT press. See
    `ScribePage._open_mode_menu()`. Menu items are role `menu_item` with exact
    names (`"Upload session audio"` etc), NOT static_text — `_has_text()` can't
    see them, check `menu_item[name=...]` directly.
18. **Audio upload ends in a native NSOpenPanel** (`dialog "Open"`), which IS
    visible to AX (unlike Chrome web content). Don't click through the file
    list — drive it with `Cmd+Shift+G` ("Go to folder"), type the ABSOLUTE
    path, Return to select, then press `button[name='Open']`. See
    `ScribePage.upload_audio()`. The go-to sheet DROPS the first character(s)
    if you type too soon (`/Users` → `/sers`): wait ~1.8s after the chord,
    clear the field, type a throwaway `/`+Backspace to prime focus, THEN type
    the path char-by-char.
19. **Transcript/note body is ONE big static_text node** (~4-5k chars holds the
    whole dialogue), NOT many small ones. `_body_text()` concatenates sidebar
    "Untitled session" noise and misreads it; read the LONGEST static_text
    instead (`ScribePage._longest_static_text()`, used by transcript_text /
    note_text). Also: on the UPLOAD path the transcript lands LATER than the
    note — wait for note completion, then poll transcript_text() until it's
    stable across 2 reads before scoring (see `run_upload_flow`).
20. **A stale/backgrounded Heidi instance publishes an EMPTY tree even when it
    looks fine.** If `App.by_name` attaches (you get a PID) but
    `locator("button").elements()` is `[]`, the fix is to QUIT AND RELAUNCH
    Heidi (a specific bad instance can wedge). `_reach_fresh_session` force-
    fronts via `open -a Heidi` (un-minimises + raises, more reliable than
    osascript `activate`) and retries login detection 6×2.5s before skipping.
21. **Recording control names CHANGE across pause/resume states** (traced live):
    - while recording: `"Pause transcribing"` + `"End recording"`
    - while PAUSED:     `"Resume recording"` + `"End session"`
    So `resume_recording()` must match `"Resume recording"` (NOT "Resume
    transcribing/dictating"), and `end_recording()` must ALSO accept
    `"End session"` for the paused state. To START recording, press the split
    button directly (`_press_record_split_button`, substring/prefix match on
    "Transcribe"/"Dictate") — its default action starts capture. For Dictate,
    `select_recording_mode("Dictate")` opens the caret menu (expand) and clicks
    the `menu_item` first, then press starts it.
22. **Context tab has a paperclip 📎 AND a microphone 🎙 — both icon-only (no AX
    name). NEVER click the mic — it starts dictation and breaks the session.**
    Identify the paperclip STRUCTURALLY, not by coordinates: it lives in a group
    whose children include the context `text_area`; the mic lives in a group
    whose siblings include a `combo_box` (its mode dropdown). So the safe
    candidate set = empty-name buttons whose parent's children include a
    `text_area` but NOT a `combo_box` (skip <20px placeholder nodes). Both
    remaining candidates (paperclip + add-patient 👤+) are click-safe. See
    `ScribePage._click_context_paperclip()`. Context upload reuses the same
    NSOpenPanel driver as audio (`_drive_open_panel`). Context files accept
    `.pdf/.doc/.docx/.png/.jpg`; upload the context FIRST, then switch back to
    the Note view (the Transcribe caret isn't present on the Context tab) before
    uploading audio.
23. **Test assets MUST be repo-relative, never absolute** (so others can clone &
    run). Resolve via `ASSETS = Path(__file__).resolve().parent…/ "assets"`;
    specs pass only a FILENAME. Convert to absolute only at the very last step
    when feeding macOS NSOpenPanel's Cmd+Shift+G field (which requires abs).
    `scripts/setup_audio.sh` generates every clip incl. the pause/resume two-
    segment clips (calls `make_pause_resume_clips.sh`) so a fresh clone is
    one-command ready.
24. **Pause/resume validation needs TWO DISTINCT audio segments** (TCD015/016).
    Segment A = headache/migraine keywords, Segment B = diabetes/insulin — so
    asserting both keyword sets appear in the final transcript proves nothing
    was lost across the pause boundary. A single reused clip can't distinguish
    "segment B recorded" from "segment B dropped". Generated by
    `scripts/make_pause_resume_clips.sh` (`say`, no AX perms needed).
25. **Record-MODE state leaks BETWEEN tests and changes the Context-tab layout.**
    A prior case left in Dictate mode (e.g. TCD007 dictate) makes the NEXT
    case's Context tab render in a dictate layout where the paperclip upload
    button is unreachable — so TCD008 context upload passes when run ALONE but
    fails right after TCD007. Fresh session ≠ fresh mode: opening a new session
    does NOT reset the split button to Transcribe. Fix: `run_upload_flow` calls
    `rec.select_recording_mode("Transcribe")` before touching the Context tab.
    General rule: any flow whose UI depends on record mode must SET the mode it
    needs at the start, never assume the default — mode persists across sessions.
26. **Artifacts are grouped per-run, per-case** (2026-07):
    `reports/artifacts/<RUN_TS>/<test-file-stem>/` holds that case's `flow.mp4`
    (+ per-test `.mp4` for non-flow suites) and `<test>__FAIL.png`. The run dir
    is pinned once in `pytest_configure` via `HEIDI_E2E_RUN_DIR` so module-scoped
    recorders (feature conftest) and the per-test recorder share it.
    **Run-once-assert-many suites (Scribe) MUST record at MODULE scope, not
    per-test.** The flow runs once in a module-scoped `result` fixture; each
    `test_*` only reads the cached result (~1s), so per-test `screencapture`
    only ever captured a 1-second clip of an assertion. Those tests carry the
    `flow_video` marker → the root `record_test` fixture skips them, and
    `_run_with_recording` (in `_scribe_cases.py`) wraps the actual flow call so
    one meaningful `flow.mp4` covers the whole multi-minute flow. `screencapture
    -v` only finalises the .mp4 on SIGINT (`_stop_screencapture`); the mdls/
    Finder "00:00" duration is a missing-moov quirk — the file plays fine.
27. **NEVER launch/activate Heidi by the NAME "Heidi" — always by PID or full
    bundle PATH.** This machine has DOZENS of bundles named `Heidi` registered
    in LaunchServices: every DMG volume (`/Volumes/Heidi*/Heidi.app`), Xcode iOS
    build products, Daemon-container placeholders, AND a **Parallels Windows
    wrapper** (`~/Applications (Parallels)/{…}/Heidi.app`). `open -a Heidi`,
    `tell application "Heidi" to activate/quit`, and `path to application
    "Heidi"` all resolve by NAME through LaunchServices and pick the WRONG one —
    verified: `path to application "Heidi"` → the Parallels wrapper; even bundle
    id `com.Heidi.dev` → `Heidi 2.5.0.app`. Only the prod name `Heidi` collides
    with Parallels; `Heidi(Staging)` doesn't, which is why staging "worked" and
    prod opened the VM app. **Rules:** activate by attached pid
    (`activate_app(pid=app.pid)` → System Events `unix id`, unambiguous); launch
    by `HEIDI_APP_PATH` full path (`open -a /Applications/Heidi(Staging).app`);
    quit by pid. Name is last-resort fallback only. Fixed in `platform_utils`
    (`activate_app(pid=)`, `launch_app(app_path=)`), `conftest` launch, `logout`
    quit, `pages/device._activate_heidi(app)`, and scribe `_reach_fresh_session`.
28. **`_reach_fresh_session` `open -a "Heidi"` spawned a NEW app instance every
    flow.** The old `_force_front()` ran `open -a "Heidi"` on each of its 6
    login-retry loops AND once per module-scoped `result` fixture — so a single
    `pytest tests/scribe` run stacked up multiple Heidi windows (and the bare
    name opened prod/Parallels, not the attached staging). Because the app is
    ALREADY running + attached by the time a flow starts, fronting must NEVER
    launch: use `open -a $HEIDI_APP_PATH` (exact bundle, un-minimises without
    spawning a second copy of a *different* build) + `activate_app(pid=app.pid)`.
    If you see several Heidi windows pile up during a run, look for a bare
    `open -a`/`launch_app` on a hot path.
29. **pgrep -f treats its pattern as a REGEX.** A bundle path with parens like
    `Heidi(Staging).app/Contents/MacOS` never matches the literal process path
    (the `(Staging)` is read as a regex group), so launch-polling times out with
    "Launched … but no process appeared". Always `re.escape()` the pattern
    before `pgrep -f` (fixed in `conftest._pid_for_exe` and `logout`).

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

**Default is portable & zero-config** for a clean machine: `open -a Heidi` +
attach by name. BUT on a machine with MULTIPLE same-named `Heidi` bundles
(this one — see pitfall #27: DMG volumes, Xcode iOS builds, a Parallels Windows
wrapper) the bare name resolves to the WRONG app. There, always drive selection
by PID or full bundle PATH — `source env/staging.env` / `source env/prod.env`
set `HEIDI_APP_NAME` + `HEIDI_APP_PATH` as a pair so launch/attach lock onto the
exact build.

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
