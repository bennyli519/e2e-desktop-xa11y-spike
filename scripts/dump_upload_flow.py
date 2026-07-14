"""Exploration: drive Scribe to the audio-upload dialog and dump the AX trees
we need to automate TCD004/005/008.

WHY: the upload flow ends in a NATIVE macOS file picker (NSOpenPanel) whose
node names can't be guessed reliably — they must be read off a real tree. This
script gets you there and dumps three things:

  1. reports/upload_01_dialog.txt   — the in-webview upload dialog
     (data-testid upload-audio-dialog): the Transcribe/Dictate segmented
     control + the FileDropzone (input testid upload-audio-file-input-input).
  2. reports/upload_02_openpanel.txt — the whole system tree AFTER clicking the
     dropzone, so we can see the native NSOpenPanel window + its controls
     (the path/Go-to field, Open button, etc).
  3. Console prints candidate elements (buttons / text_fields / combo_boxes)
     from both, so you can eyeball names quickly.

RUN FROM GHOSTTY (needs Accessibility + Screen Recording), logged in, Heidi
foreground:

    .venv/bin/python scripts/dump_upload_flow.py

Then paste reports/upload_01_dialog.txt and reports/upload_02_openpanel.txt
back to the assistant. If a step can't find its control it still dumps what it
sees and tells you where it stopped — paste that too.

NOTE: this OPENS a native file dialog. The script tries to leave it open for
the dump, then presses Escape to close it. If it's still open when the script
ends, just press Escape yourself.
"""
import sys
import time
from pathlib import Path

import xa11y

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.login import is_logged_in  # noqa: E402
from pages import ScribePage  # noqa: E402

REPORTS = Path(__file__).resolve().parent.parent / "reports"


def _save(label: str, text: str) -> None:
    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f"{label}.txt"
    out.write_text(text, encoding="utf-8")
    print(f"  -> saved {out} ({len(text)} chars)")


def _dump_app(app: xa11y.App, depth: int = 16) -> str:
    try:
        return app.dump(max_depth=depth)
    except Exception as e:
        return f"<dump failed: {e!r}>"


def _list_candidates(app: xa11y.App, roles=("button", "text_field", "combo_box",
                                            "menu_item", "list_item", "radio_button",
                                            "check_box", "static_text")) -> str:
    lines = []
    for role in roles:
        try:
            els = app.locator(role).elements()
        except Exception:
            continue
        for el in els:
            name = (getattr(el, "name", "") or "").strip()
            value = (getattr(el, "value", "") or "").strip()
            if not name and not value:
                continue
            lines.append(f"  {role}: name={name!r} value={value[:40]!r}")
    return "\n".join(lines)


def _open_upload_dialog(rec: ScribePage) -> bool:
    """Open start-recording menu and click 'Upload session audio'.

    Mirrors ScribePage.select_recording_mode's menu handling but targets the
    upload option. Returns True if the upload dialog appears.
    """
    app = rec.app
    from lib import click_first_match

    # SAFETY: if a recording is somehow already running, end it first so we
    # start from a clean 'Ready when you are' state (a prior failed run may
    # have started transcribing).
    for sel in ["button[name*='End recording']", "button[name*='End transcribing']",
                "button[name*='End dictating']"]:
        loc = app.locator(sel)
        if loc.exists():
            print(f"  (a recording was active — ending it via {sel})")
            try:
                loc.press()
                time.sleep(3.0)
            except Exception:
                pass

    # Open the start-recording dropdown/menu. The caret shares one button with
    # the Transcribe label; its AX name is the COMBINED string
    # 'Transcribe Open transcription mode menu' (confirmed via dump), so match
    # on a SUBSTRING, not equality.
    opened = click_first_match(app, [
        "button[name*='transcription mode menu']",
        "button[name*='mode menu']",
    ])
    if not opened:
        print("  could not open the mode menu via known selectors; dumping anyway")
    time.sleep(1.0)

    # Click the 'Upload session audio' option (name comes from FormattedMessage).
    for role in ["menu_item", "list_item", "button", "static_text"]:
        try:
            els = app.locator(role).elements()
        except Exception:
            continue
        for el in els:
            text = (getattr(el, "name", "") or getattr(el, "value", "") or "").strip()
            if "upload" in text.lower() and "audio" in text.lower():
                try:
                    el.press()
                except Exception:
                    try:
                        xa11y.input_sim().click(el)
                    except Exception:
                        continue
                time.sleep(1.5)
                return _upload_dialog_present(app)
    return _upload_dialog_present(app)


def _upload_dialog_present(app: xa11y.App) -> bool:
    # The dialog title is "Upload recording" (t('audio.uploadRecording')).
    needles = ["Upload recording", "Click or drag", "supported formats",
               "Transcribe", "Dictate"]
    for role in ["static_text", "button", "radio_button"]:
        try:
            els = app.locator(role).elements()
        except Exception:
            continue
        for el in els:
            text = (getattr(el, "name", "") or getattr(el, "value", "") or "")
            if any(n.lower() in text.lower() for n in needles):
                return True
    return False


def _click_dropzone(app: xa11y.App) -> None:
    """Click the FileDropzone to trigger the native file picker."""
    from lib import click_first_match
    clicked = click_first_match(app, [
        "button[name*='Click or drag']",
        "static_text[value*='Click or drag']",
        "group[name*='upload']",
    ])
    if not clicked:
        # Try clicking any element whose text invites upload.
        for role in ["button", "static_text", "group"]:
            try:
                els = app.locator(role).elements()
            except Exception:
                continue
            for el in els:
                text = (getattr(el, "name", "") or getattr(el, "value", "") or "")
                if "click or drag" in text.lower() or "upload" in text.lower():
                    try:
                        el.press()
                        return
                    except Exception:
                        try:
                            xa11y.input_sim().click(el)
                            return
                        except Exception:
                            continue


def _dump_system_root(depth: int = 14) -> str:
    """Dump every top-level app/window so we can see the native NSOpenPanel.

    The open panel belongs to Heidi but renders as a separate sheet/window; we
    walk App.list() and dump each app's tree so it's captured wherever it lands.
    """
    chunks = []
    try:
        apps = xa11y.App.list()
    except Exception as e:
        return f"<App.list failed: {e!r}>"
    for app in apps:
        name = (app.name or "").strip()
        if not name:
            continue
        # Focus on Heidi + anything that looks like a panel/dialog host.
        chunks.append(f"===== APP: {name} (pid={app.pid}) =====")
        chunks.append(_dump_app(app, depth=depth))
        chunks.append("")
    return "\n".join(chunks)


def main() -> None:
    app = xa11y.App.by_name("Heidi", timeout=10.0)
    print(f"Connected to {app.name} (pid={app.pid})")

    if not is_logged_in(app):
        print("NOT logged in — run tests/auth/test_login.py first. Aborting.")
        sys.exit(1)

    rec = ScribePage(app)
    print("Making sure we're on the Scribe page (using the CURRENT session)...")
    try:
        rec.open()
    except Exception as e:
        print(f"  rec.open() raised (continuing anyway): {e!r}")
    time.sleep(1.0)

    # We do NOT force a new session — the caret + upload option exist on the
    # current session too, and the green Transcribe button has an EMPTY AX name
    # in some states (that's why new_session()'s wait timed out). Dump the whole
    # session tree FIRST so we can see the real node names regardless of what
    # the click helpers below manage to hit.
    print("Dumping the current session tree (baseline)...")
    _save("upload_00_session", _dump_app(app))
    print("\n--- candidate elements on the session page (find the caret) ---")
    base_cands = _list_candidates(app)
    print(base_cands)
    _save("upload_00_session_candidates", base_cands)

    print("\nOpening the 'Upload session audio' dialog...")
    ok = _open_upload_dialog(rec)
    print(f"  upload dialog present: {ok}")

    print("Dumping the in-webview upload dialog tree...")
    _save("upload_01_dialog", _dump_app(app))
    print("\n--- candidate elements in the upload dialog ---")
    cands = _list_candidates(app)
    print(cands)
    _save("upload_01_dialog_candidates", cands)

    print("\nClicking the dropzone to trigger the NATIVE file picker...")
    _click_dropzone(app)
    time.sleep(2.5)

    print("Dumping the system root (to capture the native NSOpenPanel)...")
    root = _dump_system_root()
    _save("upload_02_openpanel", root)
    print("\n--- candidate elements across all apps (look for the open panel) ---")
    # Re-list candidates from Heidi specifically (panel is usually under Heidi).
    print(_list_candidates(app))

    print("\nClosing the file picker (Escape)...")
    try:
        xa11y.input_sim().press("Escape")
    except Exception:
        pass

    print("\nDONE. Paste these back to the assistant:")
    print("  reports/upload_01_dialog.txt")
    print("  reports/upload_01_dialog_candidates.txt")
    print("  reports/upload_02_openpanel.txt")


if __name__ == "__main__":
    main()
