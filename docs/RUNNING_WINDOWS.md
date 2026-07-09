# Running on Windows (cross-platform notes)

xa11y drives native apps via the OS accessibility layer: **macOS AXUIElement**
or **Windows UI Automation (UIA)**. The specs and Page Objects are the same on
both OSes; only the OS glue differs (isolated in `lib/platform_utils.py`).

## Windows is actually simpler than macOS

| | macOS | Windows |
|---|---|---|
| Permissions | needs Accessibility **and** Screen Recording (TCC) | **none** — UIA works out of the box |
| Foreground requirement | app MUST be frontmost (backgrounded WKWebView blanks the AX tree) | UIA reads background windows too — activation is best-effort |
| Terminal | must run from a permission-holding terminal (Ghostty) | any terminal / PowerShell |

## What runs on Windows

- ✅ **Pure UI tests** (smoke / navigation / scribe) — drive Windows Heidi via UIA.
- ✅ **Device connection flows** — if a Chronicle device is reachable over BLE
  from the Windows machine.
- ⏭️ **Recording tests** (`tests/recording/`) — skip: audio injection uses macOS
  BlackHole. A Windows equivalent (VB-CABLE) is future work.
- ⏭️ **Per-test screen video** — skipped on non-macOS (uses macOS `screencapture`).

## Setup (in the Parallels Windows VM)

```powershell
# 1. Install Python 3.11+ (once)
winget install Python.Python.3.12

# 2. Clone the repo
git clone https://github.com/bennyli519/e2e-desktop-xa11y-spike
cd e2e-desktop-xa11y-spike

# 3. venv + deps
python -m venv .venv
.venv\Scripts\activate
pip install -e .

# 4. Create .env.e2e with test creds (copy from .env.e2e.example)
copy .env.e2e.example .env.e2e
notepad .env.e2e   # fill in HEIDI_E2E_EMAIL / HEIDI_E2E_PASSWORD
```

Install + launch **Heidi for Windows** and log in once (Auth0 token persists).

## First milestone: prove xa11y can see Heidi

Before running tests, confirm xa11y attaches and dumps a tree (this is the
cross-platform proof):

```powershell
.venv\Scripts\activate
python scripts\dump_page.py --page scribe
type reports\scribe_tree.txt
```

If you get a real tree (not a 20-char stub), UIA is working. Note: the Windows
UIA **role names differ** from macOS (WebView2 is Chromium, not WKWebView), so
some selectors in the Page Objects may need re-tuning against a Windows dump —
that's expected. Re-dump, find the real role/name, fix the Page Object.

## Run the smoke tests

```powershell
.venv\Scripts\activate
python -m pytest tests\smoke -v -s
```

## Known cross-platform gotchas

- **Heidi app/window name**: `App.by_name("Heidi")` must match the Windows
  window/process name. If it differs, set `HEIDI_APP_NAME`.
- **Selector drift**: WebView2 (Chromium) exposes different UIA roles than macOS
  WKWebView. Expect to re-tune selectors from a real Windows dump — the layered
  design means you only touch Page Objects, not specs.
- **No BlackHole on Windows**: recording tests skip. VB-CABLE + a Windows audio
  backend in `lib/audio.py` would be the port (future work).
