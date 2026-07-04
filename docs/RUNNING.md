# Running the recording E2E — setup, triggering, reports, CI

A practical guide for QA and CI: what to prepare, how to run, how to read
results, and how to wire it into CI / release.

> TL;DR — this is a **true-app, GUI, macOS-only E2E** suite. It drives the real
> Heidi.app through the OS accessibility tree, feeds it real audio, and asserts
> on what appears on screen. That power comes with real environment
> requirements (permissions, an audio loopback, a foreground window). It runs
> great on a **prepared Mac**; it does **not** run on stock GitHub-hosted CI.
> The CI answer is a **self-hosted / cloud Mac runner**.

---

## 1. What you must prepare (one-time)

| # | Requirement | Why | How |
|---|---|---|---|
| 1 | **A real Mac with a GUI login session** | The app must render and be foreground; the AX tree is empty when backgrounded | Any Mac (laptop, mini, or a cloud Mac). Not a headless VM. |
| 2 | **Heidi.app installed** | The system under test | Install the target build to `/Applications/Heidi.app` |
| 3 | **Python venv + deps** | Test runner | `python3 -m venv .venv && source .venv/bin/activate && pip install -e .` |
| 4 | **Accessibility permission** | xa11y reads the AX tree | System Settings → Privacy & Security → Accessibility → enable the **terminal/runner** that launches pytest (e.g. Ghostty) |
| 5 | **Screen & System Audio Recording permission** | xa11y + video capture | Same panel → Screen Recording → enable the same terminal/runner. **Quit & reopen it after granting.** |
| 6 | **BlackHole 2ch** (virtual audio device) | Injects the fixed consult audio into Heidi's mic | `brew install blackhole-2ch` → **reboot** (or `sudo killall coreaudiod`) → verify `system_profiler SPAudioDataType \| grep -i BlackHole` |
| 7 | **SwitchAudioSource** | Switches the default input/output to BlackHole and back | `brew install switchaudio-osx` |
| 8 | **A logged-in Heidi session** | Skips the slow/fragile Auth0 flow for content tests | Log in once manually; the Auth0 token persists. Test account creds live in `.env.e2e` (gitignored) |
| 9 | **Fixed consult audio** | The known input we assert against | `sh scripts/setup_audio.sh` regenerates `assets/consult_{30s,5min,10min}.wav` |

Steps 3, 6, 7, 9 are automated by **`sh scripts/setup_audio.sh`** (it still
needs your password for BlackHole and a reboot afterwards).

### Do I need a cloud host?

- **No, for local/manual runs** — any Mac you can sit at works.
- **Yes, for CI / scheduled runs** — you want a Mac that is *always on, always
  logged in, permissions pre-granted*. Options:
  - A dedicated **Mac mini** in the office (cheapest, most reliable).
  - A **cloud Mac**: AWS EC2 `mac2` instances, MacStadium, Scaleway Apple
    silicon, or Cirrus. Set it up once as described here, register it as a
    self-hosted GitHub Actions runner.

---

## 2. How to run (local / manual)

Always from a terminal that holds the permissions (e.g. **Ghostty**), with
Heidi **logged in and foreground**.

```bash
cd e2e-desktop-xa11y-spike
source .venv/bin/activate
unset HEIDI_E2E_PASSWORD            # let .env.e2e win (pitfall #6)

# Core recording scenario (~30s) + true content check
pytest tests/recording/ -v -s -m "not longsession"

# One case
pytest "tests/recording/test_record_note_generation.py::test_record_transcribes_spoken_content" -v -s

# Long sessions (5 & 10 min real consult audio) — slow
pytest tests/recording/ -v -s -m longsession

# Whole suite
pytest -v
```

Useful knobs (env vars):

| Var | Default | Effect |
|---|---|---|
| `RECORD_SECONDS` | 30 | Duration of the core 30s scenario |
| `TRANSCRIPT_MATCH_THRESHOLD` | 0.9 | Min transcription accuracy (fraction of keywords found). Set `0.6` for a loose smoke run |
| `RECORD_VIDEO` | 1 | Set `0` to skip per-test screen video (faster) |
| `HEIDI_APP_PATH` | — | Point at a specific `.app` build |

> **Don't touch the Heidi window while a test runs.** A backgrounded WKWebView
> stops publishing its AX tree and the run will read empty. On a CI Mac, make
> sure nothing else steals focus.

---

## 3. How QA reads the results

Two artifacts, both already wired in:

### a) A single HTML report (recommended for QA)

`pytest-html` is a dependency. Generate a self-contained report:

```bash
pytest tests/recording/ -v \
  --html=reports/report.html --self-contained-html
```

Open `reports/report.html` — one page with pass/fail, timings, captured stdout
(the printed `transcript accuracy: 96% (36/38) …` line is right there), and the
assertion messages on failure.

### b) Video + screenshot per test

`tests/conftest.py` records **one `.mp4` per test** and a **screenshot on
failure** to `reports/artifacts/`:

```
reports/artifacts/
  tests_recording_..._test_record_5min_session.mp4
  tests_recording_..._test_..._FAIL.png     # only on failure
```

QA can watch exactly what happened. These are the fastest way to triage a flake.

### Making reports easy to browse (no local setup for QA)

Pick one:

1. **CI artifacts** — upload `reports/` as a workflow artifact; QA downloads the
   zip from the run page. Simplest.
2. **GitHub Pages** — publish `reports/report.html` (+ artifacts) to Pages after
   each run; QA just opens a URL. Nicest for non-technical QA.
3. **Allure** (optional upgrade) — richer history/trends; add `allure-pytest`
   and host the generated site. Only worth it if you want dashboards.

See §5 for the workflow snippet that produces + publishes these.

---

## 4. Can this go in CI?

**Not on stock GitHub-hosted macOS runners.** They can't (easily) grant the
TCC **Screen Recording** permission non-interactively, have no audio loopback,
and run the app without a real foreground display. Those are exactly what this
suite needs.

**Yes on a self-hosted / cloud Mac runner** that you prepare once (§1). That
machine keeps the permissions, BlackHole, and a logged-in Heidi, so CI runs are
just "pull + pytest".

---

## 5. Triggering from CI / on release

Register the prepared Mac as a **self-hosted runner** (repo → Settings →
Actions → Runners), labelled e.g. `macos-e2e`. Then copy the ready-made
workflow template into place:

```bash
mkdir -p .github/workflows
cp docs/ci/recording-e2e.yml.template .github/workflows/recording-e2e.yml
git add .github/workflows/recording-e2e.yml   # needs a token with `workflow` scope
```

The template (`docs/ci/recording-e2e.yml.template`):
```yaml
name: recording-e2e
on:
  workflow_dispatch:          # manual "Run workflow" button
  release:
    types: [published]        # every published release
  schedule:
    - cron: "0 16 * * 1-5"    # nightly-ish, weekdays 16:00 UTC

jobs:
  e2e:
    runs-on: [self-hosted, macos, macos-e2e]   # your prepared Mac
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4

      - name: Install deps
        run: |
          python3 -m venv .venv
          ./.venv/bin/pip install -e .

      - name: Ensure audio + Heidi ready
        run: |
          system_profiler SPAudioDataType | grep -i BlackHole
          # (Heidi is pre-installed + logged in on this runner)

      - name: Run recording E2E
        env:
          TRANSCRIPT_MATCH_THRESHOLD: "0.9"
        run: |
          ./.venv/bin/python -m pytest tests/recording/ -v \
            -m "not longsession" \
            --html=reports/report.html --self-contained-html

      - name: Upload report + media
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: recording-e2e-report
          path: reports/
```

Notes:
- **Triggers covered:** manual (`workflow_dispatch`), **every release**
  (`release: published`), and a nightly schedule. Keep whichever you want.
- **Long sessions** (5/10 min) are heavy — run them on the schedule or a
  separate manual workflow (`-m longsession`), not on every release.
- **Permissions on the runner** must be granted to whatever process the runner
  service launches (grant the runner binary itself, or run the runner from a
  Terminal that has the grants). This is the one-time gotcha.
- **Screen must be awake / not locked** — disable screensaver and auto-lock on
  the runner Mac (`caffeinate` in a launchd job, or a "never sleep" power
  setting), otherwise the app backgrounds and the AX tree goes empty.
- To publish to **GitHub Pages** instead of artifacts, swap the last step for a
  Pages deploy of `reports/`.

---

## 6. Quick pre-flight checklist

Before a run (local or CI), confirm:

```bash
# permissions holder is the terminal you're about to run from (Ghostty/runner)
system_profiler SPAudioDataType | grep -i BlackHole   # BlackHole present
SwitchAudioSource -a | grep -i BlackHole              # switchable
ls assets/consult_5min.wav assets/consult_10min.wav   # audio present
# Heidi is open, logged in (you can see the Scribe sidebar), and foreground
```

If the AX tree reads empty: it's almost always (1) wrong terminal / missing
Screen Recording grant, or (2) Heidi not foreground. See `CLAUDE.md` pitfalls.
