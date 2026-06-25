# Heidi Desktop E2E Tests (xa11y)

Accessibility-tree-based desktop E2E tests for the Heidi macOS app, using
[xa11y](https://xa11y.dev/). Feature-organised: one spec file per test case.

> **Status: spike.** Core flows proven end-to-end (including the full Auth0
> login across Heidi + Chrome + a system dialog). Structured for the team to
> build on. Read `docs/FINDINGS.md` for the evaluation and every pitfall hit.

## Docs

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

```bash
pytest                                    # all 21 tests
pytest -m smoke                           # just the fast presence checks
pytest tests/devices/                     # one feature
pytest tests/devices/test_reconnect.py    # one case
RECORD_VIDEO=0 pytest                      # skip screen recording (faster)
```

### Choosing which Heidi build to test

**Default: zero config.** The suite launches Heidi with `open -a Heidi`
(LaunchServices finds it wherever it's installed — no hard-coded paths) and
attaches by name. On any machine with Heidi installed, just run `pytest`.

Override only for special cases, via env vars (priority order):

```bash
pytest                                  # default: open -a Heidi + attach by name
HEIDI_DEV=1 pytest                      # attach to a running `pnpm tauri:dev` build
HEIDI_PID=16215 pytest                  # attach to one exact running process
HEIDI_APP_PATH="/Applications/Heidi Prod 2.2.0.app" pytest   # a specific .app
HEIDI_APP_NAME="Heidi(Staging)" pytest  # different app/AX name for open -a + by_name
```

- **`HEIDI_DEV=1`** — for local dev. Start `pnpm tauri:dev` yourself first; the
  suite only attaches (never launches it). Binary path defaults to
  `~/Desktop/heidi/scribe-fe-v2/src-tauri/target/debug/app`, override with
  `SCRIBE_FE_PATH` or `HEIDI_DEV_BIN`.
- **`HEIDI_APP_PATH`** — only needed when you have MULTIPLE same-named Heidi
  builds on one machine and must disambiguate by path.

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
│   └── login.py           #   Auth0 login flow (Heidi → Chrome → back)
├── pages/                 # Page Objects — HOW to operate the UI (selectors live here)
│   ├── sidebar.py
│   ├── scribe.py
│   └── device.py
├── tests/                 # WHAT to test — one spec per case, by feature
│   ├── smoke/             #   app launches, key elements render
│   ├── auth/              #   login
│   ├── navigation/        #   sidebar nav, new session
│   ├── scribe/            #   note input
│   └── devices/           #   device card, serial, firmware, connection, reconnect, disconnect
├── scripts/               # exploration tools (dump the AX tree to discover selectors)
│   ├── dump_page.py
│   └── explore_all.py
└── docs/                  # DESIGN, FINDINGS, CONTRIBUTING
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

| Feature | Tests | Verified |
|---|---|---|
| smoke | 6 | ✅ pass |
| auth (login) | 2 | ✅ pass (full Auth0 flow) |
| navigation | 5 | ✅ pass |
| scribe | 1 | ✅ pass |
| devices | 7 | ⏳ needs a run against real hardware |

Devices tests skip gracefully when no Chronicle device is paired/nearby. To
finish: run `pytest tests/devices/ -v -s`, then refine selectors in
`pages/device.py` against `reports/devices_card.txt`.
