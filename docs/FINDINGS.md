# Spike Findings

Evaluation of [xa11y](https://xa11y.dev/) for Heidi desktop E2E testing.
This is the "should we adopt it, and what will bite you" document.

## TL;DR

**xa11y works and is a clear upgrade over the cua-driver approach.** We drove a
real, hard end-to-end flow — Auth0 login spanning Heidi + Chrome + a system
dialog — entirely through the accessibility tree. The wins are selector
stability (no `element_index`), no daemon, and a Playwright-style API. The main
caveats are macOS 26 permission propagation and that it's a young, single-
maintainer project (v0.9.1, alpha).

Recommendation: **proceed**, but treat it as an evolving dependency — pin the
version, and add `aria-label`s in scribe-fe-v2 to lock selectors down.

## Project health (assessed during spike)

| Signal | Value |
|---|---|
| Version | 0.9.1 (PyPI classifier: alpha) |
| Created | ~3 months before this spike |
| Maintainer | effectively one person (~68% of commits) |
| Activity | very active (68 commits / last 30 days) |
| Issues | 0 open / 45 closed (responsive, or few users) |
| License | MIT |
| Platforms | macOS / Windows / Linux; Python, JS, Rust, CLI |

Risk: bus factor of ~1 and pre-1.0 API churn. Mitigation: pin the version,
keep the abstraction (Page Objects) thin enough to swap the driver if needed.

## xa11y vs cua-driver (the framework we're replacing)

| | cua-driver (old) | xa11y (this spike) |
|---|---|---|
| Targeting | `element_index` (numeric, fragile) | CSS-like selector (stable) |
| Daemon | requires CuaDriver.app running | none |
| Waiting | hand-rolled while/sleep loops | built-in `wait_*()` polling |
| API | custom | Playwright-style Locator |
| Screenshots | via daemon | built-in `screenshot()` |
| macOS 26 perms | works (signed .app w/ its own grant) | needs grant on the runner binary |
| Page Objects | yes (good design — we kept it) | yes (ported the structure) |

The cua-driver suite's **structure** (lib/ + pages/ + feature folders) was good
and we deliberately kept it. What changed is the driver underneath.

## What we proved works

- Reading the Tauri (WKWebView) tree on macOS — full element coverage.
- Sidebar navigation, new session, note input.
- Device page: card, serial number, firmware, connection-state detection.
- **Auto-login across processes**: Heidi email → Continue → Chrome Auth0
  password → "Open Heidi?" protocol dialog → back to the app.
- Per-test video recording + failure screenshots.

## Pitfalls hit (and the fix) — read this before you debug

1. **macOS 26 permission doesn't propagate to child processes.**
   Hermes has Screen Recording, but the python/xa11y it spawns doesn't inherit
   it → empty tree (only menu bar). **Fix:** run from Ghostty, or grant the
   runner binary directly. This is THE first thing to check if the tree is empty.

2. **Chrome web content is invisible to the a11y tree.**
   Unlike Tauri's WKWebView, Chrome doesn't expose its DOM to AX without
   `--force-renderer-accessibility`. **Fix:** for the Auth0 page we matched on
   the **window title** (`auth.heidihealth.com/...`) and drove it with the
   keyboard instead of selectors.

3. **A Chinese IME mangled typed passwords** (`a1` → `啊`).
   **Fix:** force a Latin/ABC keyboard layout via the TIS API (Swift snippet in
   `lib/login.py`) before typing.

4. **Webview text fields drop characters on fast typing** (lost trailing `..`).
   **Fix:** type character-by-character via `InputSim` with a small delay; don't
   trust a single `type_text()` for passwords.

5. **`Cmd+A` leaks a literal 'a'** into the field.
   `chord("a", ["Meta"])` emitted an `a`. **Fix:** clear with repeated
   Backspace, not select-all.

6. **A stale exported env var shadowed `.env.e2e`** and silently used an old
   password. **Fix:** `.env.e2e` is the source of truth; the loader reads the
   file first.

7. **Chrome's "Open Heidi?" protocol dialog** blocked the redirect.
   It IS in Chrome's AX tree (native dialog, unlike web content) but its buttons
   have empty names. **Fix:** find the `window "Open Heidi?"`, press the last
   button (the primary "Open Heidi").

8. **Settings is a full-screen modal** that hides the sidebar.
   Navigating after opening it failed. **Fix:** `Sidebar.reset_to_scribe()`
   closes modals before each navigation test; tests are independent.

9. **Some webview text areas don't echo their value back via AX** (read as
   `'\n'`). **Fix:** assert on `editable`/role when the value isn't reflected,
   rather than on content.

## Cross-platform outlook

The official docs confirm the model is portable; `name`/`role` map across all
three OSes, so aria-label-based selectors are reusable. Specifics:

- **Windows** needs **no permission** (UIA works out of the box) — easier than
  macOS. But: WebView2 is Chromium (different role mapping than WKWebView), all
  windows report as `WindowControlType` (check `IsDialog`), and a phantom
  `0x80040201` error is treated as success by xa11y.
- **Linux**: Chromium/Electron need `--force-renderer-accessibility`; CI needs
  Xvfb + D-Bus + AT-SPI (xa11y ships a `setup-a11y` GitHub Action).
- **Login flow is platform-specific** — the "Open Heidi?" dialog differs per OS;
  this is the one place the docs say platform branching is legitimate.

Verdict: core UI tests should port to Windows/Linux with selector tweaks; the
login flow needs a per-platform implementation.

## Recommended next steps

1. Add `aria-label`s to key interactive elements in scribe-fe-v2 (branch
   `test/xa11y-aria-labels`), then switch Page Object selectors to them.
2. Decide the target app/version (installed release vs a built artifact with
   aria-labels) and pin it.
3. Wire CI with `xa11y/setup-a11y` once the suite is green locally.
4. Expand coverage feature-by-feature, mirroring the cua-driver suite's matrix
   (connection, onboarding, recording, firmware, sessions).

---

## POC: recording → note generation (Linear APP-7808)

A focused POC to answer "can xa11y drive the real recording + note-generation
flow end-to-end", for comparison against the WDIO true-app POC.

### Scenario proven

`login → new session → start recording → wait ~30s → stop → note generation`

Ran green locally, **two levels**:

- `test_record_stop_note_generation` — core ticket scenario (structural): the
  recording timer advances, stop works, and note generation starts.
- `test_record_transcribes_spoken_content` — **true end-to-end**: a fixed spoken
  consult is injected via BlackHole, and the generated note is asserted to
  CONTAIN the spoken content. Both PASS (2 passed in 120s).

**Proof the audio→transcript loop actually works.** Injecting
`assets/consult_30s.wav` ("...persistent headache for about two weeks...
waking up around three in the morning... no nausea...") produced a SOAP note
containing:

> - Persistent headache for approximately two weeks, predominantly occurring in the afternoon
> - Sleep disturbance with early morning awakening at 3am and difficulty returning to sleep
> - No nausea reported / Associated photophobia present

i.e. the spoken words came back as correct, structured note content — verified
by asserting the note text contains ≥2 of the spoken keywords.

### Selectors discovered (all stable role+name, no coordinates)

| Control | Selector | Notes |
|---|---|---|
| Start recording | `button[name*='Transcribe']` | full name: "Transcribe Open transcription mode menu"; doubles as start |
| Recording timer | `static_text` value `mm:ss` | polled to prove liveness (00:00 → 00:16) |
| While recording | `button[name='Pause transcribing']`, `button[name='End recording']` | only present mid-recording |
| Stop | `button[name='End recording']` | |
| Note generation started | `static_text[value*='Analyzing transcript']`, `button[name='Stop generating']` | appears immediately after stop |
| Transcript available | `button[name='Transcript']` (new tab) | tab_group gains this after capture |

Discovered by walking the flow with `scripts/probe_recording.py` and reading
`reports/rec_*.txt` — never guessed.

### Note-generation assertion (scope: "starts or completes")

Per the ticket we assert generation **starts** (the "Analyzing transcript" /
"Stop generating" markers, or the Transcript tab appearing) rather than
matching exact note text. Structural, non-empty checks — robust to content
variation.

### Audio injection (BlackHole)

Heidi only transcribes real mic audio. `lib/audio.py` + `tests/recording/
conftest.py` route the system mic to a **BlackHole 2ch** loopback and loop a
fixed `say`-generated consult clip (`assets/consult_30s.wav`) for the recording
duration, then restore the original devices. If BlackHole isn't installed the
fixture degrades to a no-op so the UI flow still runs (the flow reached note
generation even with silent audio in testing).

Setup: `scripts/setup_audio.sh` (installs `blackhole-2ch` + `switchaudio-osx`,
regenerates the clip). **BlackHole needs sudo + a reboot** to register as a
device — the one real setup-friction point.

### Configurable duration

`RECORD_SECONDS` env var controls recording length: default 30 (ticket),
`RECORD_SECONDS=600` for a 10-minute long-session run. One code path, any
duration. `test_record_note_generation.py` carries `timeout(300)` so a long run
isn't killed by the global 120s cap.

### POC assessment vs ticket criteria

| Criterion | Result |
|---|---|
| xa11y drives the real app | ✅ launched/attached and drove the full flow |
| Attempts login → record → stop → note-gen | ✅ all four stages exercised, green |
| No secrets committed/logged | ✅ password in gitignored `.env.e2e`; nothing logged |
| Findings sufficient vs WDIO | ✅ selectors, runtime, flake, setup captured below |

- **Setup friction:** low, except BlackHole's sudo+reboot. Everything else is
  `pip install -e .` + macOS permissions.
- **Selector/API ergonomics:** excellent — the recording controls have clean,
  stable accessible names; Playwright-style `wait_visible` removed all sleeps
  from the control logic.
- **Runtime:** ~30s for the 30s scenario (dominated by the recording wait
  itself), negligible framework overhead.
- **Flake risk:** two real hazards found. (1) The AX tree momentarily collapses
  to a stub during the new-session view transition (observed: 54-char tree) —
  poll `web_area` visible before acting; the Page Object `wait_visible` guards
  cover this. (2) **The AX tree is EMPTY whenever the Heidi window is not
  foreground** (backgrounded WKWebView stops publishing AX) — the runner must
  keep Heidi frontmost; the harness calls `osascript ... activate` before runs.
- **BlackHole setup gotcha:** after `brew install blackhole-2ch` the device may
  not appear until coreaudiod is reloaded — `sudo killall coreaudiod` (needs a
  real terminal for the password; SIP blocks the non-sudo `launchctl kickstart`).
  Verify with `system_profiler SPAudioDataType | grep -i BlackHole`.
- **Debuggability:** stage dumps (`reports/rec_*.txt`) + per-test video +
  failure screenshots make it easy to see exactly where a run diverged.

**Recommendation: adopt** for recording E2E. The flow is fully drivable via
stable selectors; the only nontrivial dependency is the BlackHole audio harness,
which is a one-time setup and cleanly isolated in `lib/audio.py`.

