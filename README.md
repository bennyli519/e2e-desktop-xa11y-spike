# Heidi Desktop E2E Tests (xa11y)

Accessibility-tree-based desktop E2E tests for the Heidi macOS app, using
[xa11y](https://xa11y.dev/). Feature-organised: one spec file per test case.

> **Status: spike.** Core flows proven end-to-end (including the full Auth0
> login across Heidi + Chrome + a system dialog). Structured for the team to
> build on. Read `docs/FINDINGS.md` for the evaluation and every pitfall hit.

## Docs

- [`docs/RUNNING.md`](docs/RUNNING.md) — **run guide for QA & CI**: what to
  prepare (BlackHole, permissions, cloud Mac), how to trigger, how to read
  reports, and how to wire CI / release triggers.
- [`docs/DESIGN.md`](docs/DESIGN.md) — architecture, layering, selector strategy.
- [`docs/SPEC_DRIVEN.md`](docs/SPEC_DRIVEN.md) — the two modes (dev verify / E2E
  bundle) and the write-spec-first → develop-until-green workflow.
- [`docs/FINDINGS.md`](docs/FINDINGS.md) — spike evaluation: xa11y vs cua-driver,
  every pitfall + fix, cross-platform outlook, recommendation.
- [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) — how to add tests / Page Objects.
- [`CLAUDE.md`](CLAUDE.md) — full context for an AI assistant picking this up.

---

## Fresh-machine setup (macOS)

Everything you need to go from a clean checkout to a running test.

### 1. Prerequisites

- **macOS** (tested on macOS 26). Windows/Linux possible later — see FINDINGS.
- **Python 3.11+**
- **Heidi app** installed at `/Applications/Heidi.app`
- **Ghostty** terminal (or any terminal you can grant Screen Recording to) —
  see the permission note below.

### 2. Clone & install

```bash
git clone https://github.com/bennyli519/e2e-desktop-xa11y-spike.git
cd e2e-desktop-xa11y-spike

python3 -m venv .venv
source .venv/bin/activate
pip install -e .          # installs xa11y, pytest, pytest-html, pytest-timeout
```

> **The venv must be active for `pytest` to work.** A new terminal starts with a
> clean PATH, so `pytest` → "command not found" until you `source .venv/bin/activate`.
> To auto-activate when you `cd` into the repo, add this to `~/.zshrc`:
>
> ```zsh
> _heidi_e2e_autoenv() {
>   local repo="$HOME/Desktop/heidi/e2e-desktop-xa11y-spike"
>   if [[ "$PWD" == "$repo"* && "$VIRTUAL_ENV" != "$repo/.venv" && -f "$repo/.venv/bin/activate" ]]; then
>     source "$repo/.venv/bin/activate"
>   fi
> }
> autoload -Uz add-zsh-hook && add-zsh-hook chpwd _heidi_e2e_autoenv && _heidi_e2e_autoenv
> ```

### 3. Grant macOS permissions (one-time, critical)

xa11y reads window content through TWO permissions. Grant BOTH to **the terminal
you'll run tests from** (Ghostty), then restart it:

- **System Settings → Privacy & Security → Accessibility** → add Ghostty
- **System Settings → Privacy & Security → Screen & System Audio Recording** →
  add Ghostty

> ⚠️ **This is the #1 gotcha.** On macOS 26 the permission is per app bundle and
> does NOT propagate to child processes spawned by another app. If the tree
> dumps empty (only a menu bar), this is why. Run from Ghostty, not from an
> embedded/agent terminal.

### 4. Credentials (first login only)

```bash
cp .env.e2e.example .env.e2e
# edit .env.e2e and set HEIDI_E2E_PASSWORD=<staging-password>
```

`.env.e2e` is gitignored — never commit it. After the first successful login the
Auth0 token persists in the app, so later runs skip the login flow.

Current test account (in `.env.e2e.example`): `bennyli9612@gmail.com`.

### 5. Run

Always run from **Ghostty** (the terminal that holds the macOS permissions) with
the venv active. Use `pytest` or the explicit interpreter
`.venv/bin/python -m pytest`.

**Run everything / a marker:**

```bash
pytest                              # entire suite
pytest -m smoke                     # only the fast presence checks (marker)
pytest -m "auth or navigation"      # combine markers
pytest -m "not longsession"         # skip the multi-minute recording cases
```

**Run one feature folder:**

```bash
pytest tests/smoke -v -s            # smoke feature
pytest tests/auth -v -s             # login flows (TCD001-003, 014)
pytest tests/scribe -v -s           # ALL Scribe cases, in TCD order (004→016)
pytest tests/remote -v -s           # ALL Chronicle remote-device flows
```

Scribe specs are flat and named `test_tcd0NN_*.py`, so they collect in TCD
order by default. Use markers to run a sub-group:

```bash
pytest tests/scribe -m upload -v -s          # TCD004/005/008 audio+context upload
pytest tests/scribe -m longsession -v -s     # TCD006/007 5-min record
pytest tests/scribe -m pause_resume -v -s    # TCD015/016 pause/resume
pytest tests/scribe -m usb_headset -v -s     # TCD009-012 (skip w/o USB hardware)
pytest tests/remote/device-connection -v -s  # remote flows still use folders
pytest tests/remote/ota-upgrade -v -s
pytest tests/remote/bulk-sync -v -s
```

**Run one file, or one test in a file:**

```bash
pytest tests/scribe/test_tcd004_transcribe_audio_upload.py -v -s
pytest tests/scribe/test_tcd004_transcribe_audio_upload.py::test_note_generated -v -s
```

**Handy flags:**

```bash
pytest -k tcd008                    # any test whose id matches "tcd008"
pytest --collect-only -q tests/scribe   # list what WOULD run (no execution, no AX needed)
RECORD_VIDEO=0 pytest               # skip per-test screen recording (faster)
```

> `-s` streams the live per-flow checklist + print output — keep it on for the
> slow flows (recording, pause/resume, upload) so you can watch progress.

> **Whole-tree `pytest` (no path) currently errors on a pre-existing `_flow`
> name clash** (`tests/recording/_flow.py` vs `tests/auth/_flow.py`). Run by
> feature folder (`pytest tests/scribe`, `pytest tests/remote`, …) to avoid it;
> feature-scoped runs are collision-free. See CLAUDE.md pitfalls.

### Audio setup (recording / upload / pause-resume cases)

Cases that inject audio need BlackHole + the generated clips. One-time:

```bash
sh scripts/setup_audio.sh    # installs/checks BlackHole + generates ALL clips
                             # (consult_*.wav AND the pause/resume two-segment clips)
```

The Scribe upload/pause-resume assets (`consult_*.wav`, `pause_seg_a/b.wav`,
`context_sample.pdf`) live in `assets/` and are referenced repo-relative, so a
fresh clone runs with zero path edits.

### Choosing which Heidi build to test

**Default: zero config.** The suite launches Heidi with `open -a Heidi`
(LaunchServices finds it wherever it's installed — no hard-coded paths) and
attaches by name. On any machine with Heidi installed, just run `pytest`.

On **Windows**, the default path is also zero-config for standard installs: the
suite finds `Heidi.exe` in common install locations such as
`%LOCALAPPDATA%\Heidi\Heidi.exe`, launches it if needed, and attaches to the
process that owns the main window. Screen recording is disabled by default on
Windows because the bundled recorder is macOS-only.

Override only for special cases, via env vars (priority order):

```bash
pytest                                  # default: open -a Heidi + attach by name
HEIDI_DEV=1 pytest                      # attach to a running `pnpm tauri:dev` build
HEIDI_PID=16215 pytest                  # attach to one exact running process
HEIDI_APP_PATH="/Applications/Heidi Prod 2.2.0.app" pytest   # a specific .app
HEIDI_EXE_PATH="C:\Users\you\AppData\Local\Heidi\Heidi.exe" pytest  # Windows
HEIDI_APP_NAME="Heidi(Staging)" pytest  # different app/AX name for open -a + by_name
```

> ⚠️ **`HEIDI_APP_NAME` and `HEIDI_APP_PATH` are a PAIR.** `HEIDI_APP_PATH`
> decides which bundle `open` launches; `HEIDI_APP_NAME` is what `activate` /
> `by_name` use to attach and bring frontmost. Set only one and you get "launch
> bundle A, but attach the other same-named window B". Always set both together.

#### Switching between prod / staging (per-env files)

If this machine has several Heidi builds with **different bundle names**
(e.g. prod is `Heidi`, staging is `Heidi(Staging)`), don't retype the pair each
run — `source` a per-env file that sets both variables together. Two are
committed under `env/`:

| File | NAME | PATH |
|---|---|---|
| `env/prod.env` | `Heidi` | `/Applications/Heidi.app` |
| `env/staging.env` | `Heidi(Staging)` | `/Applications/Heidi(Staging).app` |

```bash
source env/staging.env && pytest tests/scribe   # test staging
source env/prod.env    && pytest tests/scribe   # test prod
```

Add a new build by dropping another file in `env/` with the matching
`export HEIDI_APP_NAME=...` / `export HEIDI_APP_PATH=...` pair.

> These files hold only the app name + path (no secrets). Note `.gitignore`'s
> `*.env` rule excludes them by default — `git add -f env/*.env` if you want to
> share them with the team. Credentials stay in `.env.e2e` (separately ignored).
>
> **Attaching to an already-running build launched from elsewhere** (e.g. a
> `.app` run straight from a mounted `/Volumes/...` DMG, not `/Applications`):
> `open -a` would start the `/Applications` copy instead, so attach by PID —
> `HEIDI_PID=<pid> pytest ...` (find it with `pgrep -fl Heidi`).

PowerShell example for a non-standard Windows install:

```powershell
$env:HEIDI_EXE_PATH = "C:\Users\you\AppData\Local\Heidi\Heidi.exe"
.\.venv\Scripts\python.exe -m pytest
```

### Recording smoke with a virtual audio device

Desktop recording uses the real Tauri audio stack, not Playwright's
`navigator.mediaDevices.getUserMedia` mock. By default the suite selects
`BlackHole 2ch` on macOS and `CABLE Output (VB-Audio Virtual Cable)` on
Windows when those devices are present. Override the device name only when your
local virtual device is named differently:

```bash
HEIDI_E2E_RECORDING_INPUT_DEVICE="BlackHole 2ch" pytest tests/recording/test_30s.py -v -s
```

On Windows, the test plays the flow's audio fixture while recording. Playback
defaults to the first output matching `CABLE Input`; override only if needed:

```powershell
$env:HEIDI_E2E_RECORDING_INPUT_DEVICE = "CABLE Output (VB-Audio Virtual Cable)"
$env:HEIDI_E2E_AUDIO_PLAYBACK_DEVICE = "CABLE Input"
.\.venv\Scripts\python.exe -m pytest tests\recording\test_30s.py -v -s
```

VB-CABLE setup:

1. Install **VB-Audio VB-CABLE** from https://vb-audio.com/Cable/.
2. Run the installer as Administrator and reboot if Windows asks.
3. Confirm Windows has a recording endpoint named
   `CABLE Output (VB-Audio Virtual Cable)`.
4. Route the fixture/player output to a playback endpoint such as
   `CABLE Input (VB-Audio Virtual Cable)` or `CABLE In 16ch (...)`.
5. Set `HEIDI_E2E_RECORDING_INPUT_DEVICE` to the recording endpoint name above.
   Do not select `CABLE Input`/`CABLE In` in Heidi; those are playback outputs.

To inspect the device names available to the test runner:

```powershell
.\.venv\Scripts\python.exe scripts\check_audio_devices.py
```

If your device names differ, set overrides with `$env:` in the current
PowerShell session, or save them in `.env.e2e` so pytest loads them
automatically:

```dotenv
HEIDI_E2E_RECORDING_INPUT_DEVICE="CABLE Output (VB-Audio Virtual Cable)"
HEIDI_E2E_AUDIO_PLAYBACK_DEVICE="CABLE Input (VB-Audio Virtual Cable)"
```

Short and long note-generation runs mirror the web/macOS recording specs:

```powershell
$env:HEIDI_E2E_RECORDING_INPUT_DEVICE = "CABLE Output (VB-Audio Virtual Cable)"
$env:HEIDI_E2E_AUDIO_PLAYBACK_DEVICE = "CABLE Input"

# 30s recording: records consult_30s.wav, then verifies transcript + note content.
.\.venv\Scripts\python.exe -m pytest `
  tests\recording\test_30s.py -v -s

# 1-minute recording: records consult_1min.wav, then verifies transcript + note content.
.\.venv\Scripts\python.exe -m pytest `
  tests\recording\test_1min.py -v -s

# Longer stress runs.
.\.venv\Scripts\python.exe -m pytest `
  tests\recording\test_5min.py tests\recording\test_10min.py -v -s
```

Recording fixtures live in this repo under `assets/consult_*.wav`.

- **`HEIDI_DEV=1`** — for local dev. Start `pnpm tauri:dev` yourself first; the
  suite only attaches (never launches it). Binary path defaults to
  `~/Desktop/heidi/scribe-fe-v2/src-tauri/target/debug/app`, override with
  `SCRIBE_FE_PATH` or `HEIDI_DEV_BIN`.
- **`HEIDI_APP_PATH` / `HEIDI_EXE_PATH`** — only needed when you have MULTIPLE
  same-named Heidi builds on one machine and must disambiguate by path.

**Testing your local dev build** (`pnpm tauri:dev`):

```bash
# terminal 1: in scribe-fe-v2
pnpm tauri:dev

# terminal 2 (Ghostty): in this repo
HEIDI_DEV=1 pytest -m smoke
```

---

## Layout

```
.
├── conftest.py            # root fixtures: heidi_app, dump_tree, per-test video + failure screenshot
├── lib/                   # infrastructure (not Page Objects)
│   ├── helpers.py         #   click_first_match (selector fallback chain)
│   ├── audio.py           #   AudioInjector (BlackHole/VB-CABLE clip injection)
│   └── login.py           #   Auth0 login flow (Heidi → Chrome → back)
├── pages/                 # Page Objects — HOW to operate the UI (selectors live here)
│   ├── sidebar.py
│   ├── scribe.py          #   record/pause/resume, audio + context upload, transcript/note read
│   └── device.py
├── tests/                 # WHAT to test — one spec per case, by feature
│   ├── smoke/             #   app launches, key elements render
│   ├── auth/              #   login (TCD001-003) + signup (TCD014)
│   ├── navigation/        #   sidebar nav, new session
│   ├── recording/         #   30s/1min/5min/10min/15min note-generation POC
│   ├── scribe/            #   Scribe release cases, flat & TCD-ordered
│   │   ├── test_tcd004..005_*  #     audio upload (transcribe/dictate)
│   │   ├── test_tcd006..007_*  #     5-min record
│   │   ├── test_tcd008_*       #     audio + context PDF upload
│   │   ├── test_tcd009..012_*  #     USB headset (skip without hardware)
│   │   ├── test_tcd015..016_*  #     record → pause → resume
│   │   └── _scribe_flow.py / _scribe_cases.py / conftest.py  # shared engine
│   └── remote/            #   Chronicle remote-device flows
│       ├── device-connection/     #   onboarding/reconnect/stress/autoconnect/remote-lost
│       ├── ota-upgrade/
│       ├── remote-session-recording/
│       └── bulk-sync/
├── assets/                # audio clips + context PDF (repo-relative, committed)
├── scripts/               # exploration tools (dump the AX tree to discover selectors)
│   ├── dump_page.py
│   ├── setup_audio.sh     #   one-shot: BlackHole + generate all clips
│   └── make_pause_resume_clips.sh
└── docs/                  # DESIGN, FINDINGS, CONTRIBUTING, RUNNING
```

**Principle:** selectors live in `pages/`, assertions live in `tests/`. UI
changed? Fix the selector once in the Page Object; specs don't change.

## Exploring the UI (to write/fix selectors)

```bash
python scripts/dump_page.py --page Devices   # navigate then dump one page's tree
python scripts/explore_all.py                # walk all pages, dump each to reports/
```

Read the dump, copy the real `role` + `name`. Names come from `aria-label` or
visible text — often NOT what's painted on screen.

## Artifacts (per test run)

- Screen recording → `reports/artifacts/<test>.mp4` (macOS `screencapture -v`)
- Failure screenshot → `reports/artifacts/<test>__FAIL.png` (xa11y)
- Tree dumps → `reports/<label>.txt` (via the `dump_tree` fixture)

`reports/` is gitignored.

## Test status

| Feature | Cases | Verified |
|---|---|---|
| smoke | 6 | ✅ pass |
| auth (login) | TCD001-003, 014 | ✅ pass (full Auth0 flow; OAuth/signup are entry-point-only) |
| navigation | 5 | ✅ pass |
| recording (POC) | 30s/1min/5min/10min/15min | ✅ pass (BlackHole injection) |
| scribe · upload | TCD004/005/008 | ✅ pass on real hardware (97.4% accuracy; incl. context PDF) |
| scribe · recording | TCD006/007 | ✅ pass (5-min transcribe/dictate) |
| scribe · pause-resume | TCD015/016 | ✅ pass (two-segment, no content lost across pause) |
| scribe · usb-headset | TCD009-012 | ⏭️ skip by design (needs real USB hardware) |
| remote · device-connection | onboarding/reconnect/stress/autoconnect/remote-lost | ✅ pass on real Chronicle |
| remote · ota-upgrade | 1 | ⏳ needs a firmware update to exercise |
| remote · remote-session-recording | 1 | ⏭️ skip (input trigger has no AX name yet) |
| remote · bulk-sync | 1 | ⏳ needs pending offline recordings |

Hardware-dependent cases skip gracefully when the precondition (paired Chronicle,
USB headset, pending sync) isn't met — a red only ever means a real regression.
Scribe's 7 automatable cases are all verified green; USB (009-012) stays an
honest skip rather than a low-fidelity BlackHole fake (see CLAUDE.md).
