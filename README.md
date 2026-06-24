# Heidi Desktop E2E Tests (xa11y)

Accessibility-tree-based desktop E2E tests for the Heidi app, using
[xa11y](https://xa11y.dev/). Feature-organised: one spec file per test case.

## ⚠️ Must run from Ghostty

macOS 26 grants "Screen & System Audio Recording" per app bundle. xa11y reads
window content through that permission, and **child processes of Hermes don't
inherit it** — so run from a terminal that has the permission (Ghostty).

## Layout

```
.
├── conftest.py            # root fixtures: heidi_app, dump_tree, per-test video + failure screenshot
├── lib/                   # infrastructure (not Page Objects)
│   ├── helpers.py         #   click_first_match (selector fallback chain)
│   └── login.py           #   Auth0 login flow
├── pages/                 # Page Objects — HOW to operate the UI
│   ├── sidebar.py
│   ├── scribe.py
│   └── device.py
└── tests/                 # WHAT to test — one spec file per case, by feature
    ├── smoke/             #   app launches, key elements render
    ├── auth/              #   login
    ├── navigation/        #   sidebar nav, new session
    ├── scribe/            #   note input
    └── devices/           #   device card, serial, firmware, connect, reconnect, disconnect
```

**Principle:** selectors live in `pages/`, assertions live in `tests/`. When
the UI changes, fix the selector once in the Page Object — specs don't change.

## Setup

```bash
pip install -e .                       # or: pip install xa11y pytest pytest-html pytest-timeout
cp .env.e2e.example .env.e2e           # then fill in HEIDI_E2E_PASSWORD (first login only)
```

## Running

```bash
pytest                                 # everything
pytest -m smoke                        # by marker: smoke | auth | navigation | scribe | devices | slow
pytest tests/devices/                  # by feature folder
pytest tests/devices/test_reconnect.py # a single case
RECORD_VIDEO=0 pytest                   # skip screen recording (faster)
```

## Artifacts

- Per-test screen recording: `reports/artifacts/<test>.mp4` (macOS `screencapture -v`)
- Failure screenshot: `reports/artifacts/<test>__FAIL.png` (xa11y `screenshot()`)
- Tree dumps for debugging: `reports/<label>.txt` (via the `dump_tree` fixture)

## Selectors & portability

xa11y matches the accessibility tree's `name` (= `aria-label` or visible text)
and `role`. Notes from real tree dumps:

- Sidebar item roles are inconsistent (button / link / combo_box) — Page
  Objects use comma-separated role alternation, the official portable pattern.
- Button names currently come from visible `<FormattedMessage>` text, so they
  are i18n- and state-dependent. Adding `aria-label`s in scribe-fe-v2 would
  make selectors stable across language and state (and works on Windows/Linux
  too, since `name` maps to aria-label on all three platforms).

## Exploration

```bash
python scripts/dump_page.py --page Devices   # dump one page's tree
python scripts/explore_all.py                # walk all pages, dump each
```
