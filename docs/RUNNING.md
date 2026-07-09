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
| 9 | **Fixed consult audio** | The known input we assert against | `sh scripts/setup_audio.sh` regenerates `assets/consult_{30s,1min,5min,10min}.wav` |

Steps 3, 6, 7, 9 are automated by **`sh scripts/setup_audio.sh`** (it still
needs your password for BlackHole and a reboot afterwards).

### Fastest path: one-shot bootstrap

`bash scripts/bootstrap.sh` does everything scriptable in one go:
installs the Homebrew audio tooling, creates the venv + installs the package,
generates all consult clips, reloads CoreAudio so BlackHole appears, and
**opens the two System Settings panes** you must toggle by hand.

```bash
bash scripts/bootstrap.sh
```

What it CANNOT do (Apple TCC — no CLI path exists):
- **Grant Accessibility / Screen Recording** — you must click the toggle in the
  panes it opens, then **quit & reopen** the terminal. (For a fleet, push these
  via an **MDM profile** instead of clicking.)
- **Log in to Heidi** — do it once manually; the Auth0 token persists.

Everything else is automated.

### Do I need a cloud host?

- **No, for local/manual runs** — any Mac you can sit at works.
- **Yes, for CI / scheduled runs** — you want a Mac that is *always on, always
  logged in, BlackHole installed*. Options:
  - A dedicated **Mac mini** in the office (cheapest for steady use; a ~$600
    one-time buy often beats a long-running cloud Mac).
  - A **cloud Mac**: AWS EC2 `mac2.metal` (Apple silicon), MacStadium,
    Scaleway, or Cirrus.

#### AWS EC2 Mac — the caveats that bite

EC2 Mac is a fully real macOS box (root, kernel drivers, reboot) so it **can**
run BlackHole — but note:

- **24-hour minimum allocation.** EC2 Mac runs on a Dedicated Host with an
  Apple-mandated 24h minimum before you can release it. You **cannot** spin one
  up for 10 minutes and stop it. Cost is ~$0.65–1.0/hr, so a single allocation
  is ~$16+, and a permanently-on runner is ~$500–650/month.
- **No physical display.** It's headless bare metal. You must set up
  **auto-login + a persistent GUI session** (e.g. via VNC / screen sharing)
  or the AX tree comes back empty (the backgrounded-window pitfall). Keep it
  awake with `caffeinate`.
- **Audio is unverified on EC2.** BlackHole is a pure-software loopback so it
  *should* work without a sound card, but that "headless EC2 Mac can capture
  injected audio and transcribe it" path has **not been proven yet** — validate
  it on one instance before committing to EC2 for CI.

**Recommendation:** if runs are infrequent, an office Mac mini kept awake is
simpler and cheaper. Use EC2 Mac when you want elastic/programmatic
provisioning and can absorb the 24h-minimum cost model — and prove the audio
path on it first.

Once you have the machine (either option): run `bash scripts/bootstrap.sh`,
install + log into Heidi, then register it as a self-hosted GitHub Actions
runner (§5).

---

## 2. How to run (local / manual)

Always from a terminal that holds the permissions (e.g. **Ghostty**), with
Heidi **logged in and foreground**.

```bash
cd e2e-desktop-xa11y-spike
source .venv/bin/activate
unset HEIDI_E2E_PASSWORD            # let .env.e2e win (pitfall #6)

# Smoke: auto-login + 30s recording end-to-end (one invocation, login first)
bash scripts/smoke.sh               # default: login + 30s
bash scripts/smoke.sh --full        # login + all recording flows (30s/1/5/10min)

# One flow at a time (each file = one duration, 5 checks inside)
pytest tests/recording/test_30s.py -v -s      # 30-second flow
pytest tests/recording/test_1min.py -v -s     # 1-minute flow

# Core fast check only (30s) — skips the multi-minute flows
pytest tests/recording/ -v -s -m "not longsession"

# Long sessions (1 / 5 / 10 min real consult audio) — slow
pytest tests/recording/ -v -s -m longsession

# One assertion of one flow
pytest "tests/recording/test_5min.py::test_transcript_accuracy" -v -s

# Whole suite
pytest -v
```

Each duration file runs the recording flow **once** and exposes six separate
tests — `recording_starts`, `timer_advances`, `transcription_generated`,
`note_generated`, `duration_display`, `transcript_accuracy` — so the output is
a per-flow checklist. A demo-friendly ✓/✗ table prints at the end of every run
(see the `RECORDING E2E — FLOW RESULTS` summary).

Useful knobs (env vars):

| Var | Default | Effect |
|---|---|---|
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
  tests_recording_test_5min_..._test_transcript_accuracy.mp4
  tests_recording_test_1min_..._test_..._FAIL.png     # only on failure
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

Two different answers depending on whether you need the **audio** path. Based
on xa11y's official CI guide (https://xa11y.dev/guides/ci/):

### The accessibility permission is NOT the blocker

xa11y ships `xa11y/setup-a11y@v1` (GitHub Actions) and a standalone
`grant_macos_tcc.sh`. On a **hosted** runner they grant the macOS
**Accessibility (TCC)** permission non-interactively — writing the TCC db and
restarting `tccd` (allowed because SIP only protects `/System`). So "reading
the AX tree" works on hosted runners:

- **Windows** — `windows-latest` needs **nothing**; UIA works out of the box.
- **macOS** — `macos-latest` + `setup-a11y` (grant TCC to the python binary).
- **Linux** — `ubuntu-latest` + `setup-a11y` (Xvfb + D-Bus + AT-SPI).

So a **pure-UI** xa11y suite (navigation, buttons, text presence) **can run on
stock GitHub-hosted runners.** Our earlier "not on hosted runners" claim was
too broad — it only applies to the two extras below.

### What still blocks THIS suite on hosted runners

Our recording E2E needs two things the official CI setup does **not** cover:

1. **Real audio input (BlackHole loopback).** Hosted runners have no virtual
   audio device, and installing BlackHole needs sudo + a reboot. Without it
   there's no mic signal → no transcript → nothing to assert.
2. **Screen Recording permission** — only if you keep per-test video
   (`RECORD_VIDEO=1`). `setup-a11y` grants **Accessibility**, not Screen
   Recording. Set `RECORD_VIDEO=0` and this one goes away; xa11y's own
   `screenshot()` for failure shots also depends on it, so drop that too or
   run where it's granted.

**Bottom line:**
- **Pure-UI regression** → hosted runners are fine (`setup-a11y`).
- **This recording/transcription E2E** → still needs a **self-hosted / cloud
  Mac** for the audio loopback (and, if you keep video, Screen Recording). That
  machine keeps BlackHole + a logged-in Heidi, so runs are just "pull + pytest".

The accessibility grant on that self-hosted Mac can be automated too:
```bash
scripts/grant_macos_tcc.sh "$(.venv/bin/python -c 'import sys; print(sys.executable)')"
```
(grants Accessibility to the real interpreter binary — see xa11y's guide).

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

The canonical template is **`docs/ci/recording-e2e.yml.template`** — it grants
Accessibility per-run via `grant_macos_tcc.sh`, sets `RECORD_VIDEO=0` (so no
Screen Recording permission is needed), keeps the display awake with
`caffeinate`, and triggers on manual dispatch / release / schedule. Copy it in
as shown above and edit the runner label / triggers to taste.

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
