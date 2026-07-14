"""Page Object: Scribe page (main note-taking view)."""
import re
import time

import xa11y

from lib import click_first_match
from pages.sidebar import Sidebar

GENERATING_MARKERS = [
    "static_text[value*='Analyzing transcript']",
    "button[name='Stop generating']",
    "static_text[value*='Generating']",
]

GENERATION_DONE_ABSENT = [
    "button[name='Stop generating']",
    "static_text[value*='Analyzing transcript']",
]


class ScribePage:
    def __init__(self, app: xa11y.App):
        self.app = app
        self.sidebar = Sidebar(app)

    def open(self) -> bool:
        self.sidebar.close_modal()
        return self.sidebar.go_to_scribe()

    def open_context_tab(self) -> None:
        """Switch to the Context tab, where the note/context text_area lives.

        The Scribe view has a Context/Note tab_group. The context text_area
        (placeholder "Add any additional context…") only renders when the
        Context tab is active; the Note tab shows a "Ready when you are"
        placeholder with no text_area.
        """
        ctx = self.app.locator("button[name='Context']")
        if ctx.exists():
            ctx.press()
            time.sleep(1.0)

    # --- elements ---
    def note_input(self):
        return self.app.locator("text_area")

    def has_new_session_button(self) -> bool:
        return self.app.locator("button[name='New session']").exists()

    def has_prep_button(self) -> bool:
        return self.app.locator("button[name='Prepare']").exists()

    def selected_input_device(self) -> str | None:
        combo = self._input_device_combo()
        if combo is None:
            return None
        return combo.value or combo.name

    def recording_elapsed_seconds(self) -> int | None:
        elapsed = [
            seconds
            for _, seconds in self._timer_texts()
        ]
        return max(elapsed) if elapsed else None

    def recording_timer(self) -> str | None:
        timers = self._timer_texts()
        if not timers:
            return None
        return max(timers, key=lambda item: item[1])[0]

    def is_recording(self) -> bool:
        return any(
            self.app.locator(selector).exists()
            for selector in [
                "button[name='End recording']",
                "button[name='End transcribing']",
                "button[name='End dictating']",
                "button[name*='End recording']",
                "button[name*='End transcribing']",
                "button[name*='End dictating']",
            ]
        )

    def duration_display(self) -> str | None:
        return self.recording_timer()

    def note_generation_started(self) -> bool:
        return any(self.app.locator(sel).exists() for sel in GENERATING_MARKERS)

    def note_generation_done(self) -> bool:
        still_going = any(
            self.app.locator(sel).exists() for sel in GENERATION_DONE_ABSENT
        )
        return (not still_going) and bool(self.note_text().strip())

    def has_transcript_tab(self) -> bool:
        return self.app.locator("button[name='Transcript']").exists()

    def open_tab(self, name: str) -> bool:
        return self._activate_tab(name)

    def transcript_text(self) -> str:
        self.open_tab("Transcript")
        # The generated transcript renders as ONE large static_text node (traced:
        # a single ~4-5k char node holds the whole Doctor/Patient dialogue). Grab
        # the LONGEST static_text — that's the transcript body — instead of
        # _body_text(), which concatenates sidebar 'Untitled session' noise.
        longest = self._longest_static_text()
        if longest and len(longest) >= 100:
            return longest
        return self._body_text()

    def _longest_static_text(self) -> str:
        best = ""
        try:
            for el in self.app.locator("static_text").elements():
                txt = (el.value or el.name or "").strip()
                if len(txt) > len(best):
                    best = txt
        except Exception:
            pass
        return best

    def note_text(self) -> str:
        self.open_tab("Note")
        # Same idea as transcript: the note body is the longest static_text.
        longest = self._longest_static_text()
        if longest and len(longest) >= 100:
            return longest
        return self._body_text()

    def _timer_texts(self) -> list[tuple[str, int]]:
        timers: list[tuple[str, int]] = []
        for el in self.app.locator("static_text").elements():
            text = el.name or el.value or ""
            match = re.fullmatch(r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})", text)
            if not match:
                continue
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2))
            seconds = int(match.group(3))
            timers.append((text, hours * 3600 + minutes * 60 + seconds))
        return timers

    # --- actions ---
    def new_session(self) -> bool:
        self.dismiss_open_overlays()
        ok = self.sidebar.new_session()
        if ok:
            # Wait for ANY session-view marker. The record control is a combined
            # caret button whose AX name is 'Transcribe Open transcription mode
            # menu' (so exact name='Transcribe' no longer matches); the Context/
            # Note tabs are the most stable markers. Try each selector until one
            # goes visible rather than a single (fragile) combined string.
            markers = [
                "button[name*='transcription mode menu']",
                "button[name='Transcribe']",
                "button[name='Dictate']",
                "button[name='Context']",
                "button[name='Note']",
            ]
            deadline = time.time() + 20.0
            seen = False
            while time.time() < deadline and not seen:
                for sel in markers:
                    if self.app.locator(sel).exists():
                        seen = True
                        break
                if not seen:
                    time.sleep(0.5)
            self.dismiss_open_overlays()
        return ok

    def dismiss_open_overlays(self) -> None:
        try:
            xa11y.input_sim().press("Escape")
            time.sleep(0.3)
        except Exception:
            pass

    def type_note(self, text: str) -> None:
        """Focus the note area and type via real keystrokes (webview-safe)."""
        ta = self.note_input()
        ta.wait_visible(timeout=10.0)
        ta.press()
        time.sleep(0.5)
        xa11y.input_sim().type_text(text)
        time.sleep(1)

    def clear_note(self) -> None:
        try:
            self.note_input().set_value("")
        except Exception:
            pass

    def select_input_device(self, device_name: str) -> bool:
        def matches_device(text: str | None) -> bool:
            if not text:
                return False
            return device_name.lower() in text.lower()

        selected = self.selected_input_device()
        if matches_device(selected):
            return True

        combo = self._input_device_combo()
        if combo is None:
            self.dismiss_open_overlays()
            combo = self._input_device_combo()
        if combo is None:
            return False

        try:
            combo.expand()
        except Exception:
            try:
                combo.press()
            except Exception:
                return False
        time.sleep(0.8)

        for role in ["list_item", "menu_item", "option", "button", "static_text"]:
            try:
                elements = self.app.locator(role).elements()
            except Exception:
                continue
            for el in elements:
                if not (
                    matches_device(el.name)
                    or matches_device(el.value)
                ):
                    continue
                try:
                    el.press()
                    time.sleep(1)
                    selected = self.selected_input_device()
                    return selected is None or matches_device(selected)
                except Exception:
                    pass

                try:
                    xa11y.input_sim().click(el)
                    time.sleep(1)
                    selected = self.selected_input_device()
                    return selected is None or matches_device(selected)
                except Exception:
                    continue

        selectors = [
            f"list_item[name*='{device_name}']",
            f"button[name*='{device_name}']",
            f"static_text[name*='{device_name}']",
            f"static_text[value*='{device_name}']",
        ]
        clicked = click_first_match(self.app, selectors)
        time.sleep(1)
        return clicked and matches_device(self.selected_input_device())

    def select_input_heidi_remote(self) -> bool:
        return self.select_input_device("Heidi Remote")

    def start_transcribing(self) -> None:
        # The record control is a split button whose AX name is the combined
        # 'Transcribe Open transcription mode menu'. Pressing it fires the
        # DEFAULT action = start recording in the currently-selected mode.
        # Default mode is Transcribe, so we can press it directly. Match on a
        # substring since the exact name is the combined string.
        self._press_record_split_button("Transcribe")
        consent = self.app.locator("button[name*='consent']")
        if consent.exists():
            consent.press()
        self.app.locator(
            "button[name*='Pause transcribing'], button[name*='End recording'], "
            "button[name*='End transcribing']"
        ).wait_visible(timeout=20.0)

    def start_dictating(self) -> None:
        # Switch the split button's mode to Dictate first (via the caret menu),
        # then press it to start. select_recording_mode picks the menu item.
        self.select_recording_mode("Dictate")
        self._press_record_split_button("Dictate")
        consent = self.app.locator("button[name*='consent']")
        if consent.exists():
            consent.press()
        self.app.locator(
            "button[name*='Pause dictating'], button[name*='End recording'], "
            "button[name*='End dictating']"
        ).wait_visible(timeout=20.0)

    def _press_record_split_button(self, mode: str) -> None:
        """Press the main record split-button to START recording.

        Its AX name is 'Transcribe Open transcription mode menu' (or the Dictate
        equivalent). We match on a substring of the mode label and press the
        node — press() fires the button's DEFAULT action (start recording),
        which is what we want here (unlike opening the mode menu, which needs
        expand()).
        """
        for sel in (
            f"button[name^='{mode}']",
            f"button[name*='{mode}']",
            f"button[name='{mode}']",
        ):
            loc = self.app.locator(sel)
            if loc.exists():
                loc.wait_visible(timeout=20.0)
                loc.press()
                return
        # Last resort: the generic mode-menu split button.
        loc = self.app.locator("button[name*='transcription mode menu']")
        loc.wait_visible(timeout=20.0)
        loc.press()

    def start_recording(self) -> None:
        self.start_transcribing()

    def select_recording_mode(self, mode: str) -> bool:
        """Ensure the split button's mode is `mode` (Transcribe/Dictate).

        The split button's AX name STARTS WITH the current mode (e.g.
        'Transcribe Open transcription mode menu'), so if it already starts with
        the requested mode we're done. Otherwise open the caret menu (expand)
        and click the mode's menu_item.
        """
        # Already in this mode? The split-button name starts with the mode.
        for b in self.app.locator("button").elements():
            name = (b.name or "").strip()
            if name.startswith(mode) and "transcription mode menu" in name:
                return True

        if not self._open_mode_menu():
            return False
        time.sleep(0.5)

        # Click the mode's menu_item (role=menu_item, exact name).
        item = self.app.locator(f"menu_item[name='{mode}']")
        if item.exists():
            try:
                item.press()
                time.sleep(1)
                return True
            except Exception:
                try:
                    xa11y.input_sim().click(item.elements()[0])
                    time.sleep(1)
                    return True
                except Exception:
                    pass
        # Fallback: scan roles for the mode label.
        for role in ["menu_item", "list_item", "button", "static_text"]:
            try:
                elements = self.app.locator(role).elements()
            except Exception:
                continue
            for el in elements:
                if (el.name or el.value or "").strip() != mode:
                    continue
                try:
                    el.press()
                    time.sleep(1)
                    return True
                except Exception:
                    try:
                        xa11y.input_sim().click(el)
                        time.sleep(1)
                        return True
                    except Exception:
                        continue
        return False

    def wait_recording_elapsed(self, min_seconds: int, timeout: float = 30.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            elapsed = self.recording_elapsed_seconds()
            if elapsed is not None and elapsed >= min_seconds:
                return True
            time.sleep(1)
        return False

    def wait_recording(self, seconds: float, sample_every: float = 30.0) -> list:
        samples: list = []
        start = time.time()
        samples.append((0.0, self.recording_timer()))
        next_sample = sample_every
        while True:
            elapsed = time.time() - start
            if elapsed >= seconds:
                break
            time.sleep(2)
            if elapsed >= next_sample:
                samples.append((round(elapsed), self.recording_timer()))
                next_sample += sample_every
        samples.append((round(time.time() - start), self.recording_timer()))
        return samples

    def pause_recording(self) -> bool:
        return click_first_match(
            self.app,
            [
                "button[name='Pause transcribing']",
                "button[name='Pause dictating']",
                "button[name*='Pause transcribing']",
                "button[name*='Pause dictating']",
                "button[name*='Pause recording']",
                "button[name*='Pause']",
            ],
        )

    def resume_recording(self) -> bool:
        return click_first_match(
            self.app,
            [
                # Traced from a real tree: after pausing, the control is named
                # 'Resume recording' (not 'Resume transcribing/dictating').
                "button[name='Resume recording']",
                "button[name*='Resume recording']",
                "button[name='Resume']",
                "button[name='Resume transcribing']",
                "button[name='Resume dictating']",
                "button[name*='Resume transcribing']",
                "button[name*='Resume dictating']",
                "button[name*='Resume']",
            ],
        )

    def end_recording(self) -> bool:
        ok = click_first_match(
            self.app,
            [
                "button[name='End recording']",
                "button[name='End transcribing']",
                "button[name='End dictating']",
                "button[name*='End recording']",
                "button[name*='End transcribing']",
                "button[name*='End dictating']",
                # When PAUSED the end control is named 'End session'.
                "button[name='End session']",
                "button[name*='End session']",
            ],
        )
        if ok:
            time.sleep(2)
        return ok

    # --- audio upload (TCD004/005/008) ---------------------------------
    def open_upload_dialog(self) -> bool:
        """Open the 'Upload a recording' dialog via the Transcribe caret menu.

        The record control is a SPLIT BUTTON: a main 'Transcribe' action plus a
        separate ChevronDown caret (aria-label 'Open transcription mode menu').
        In the AX tree the two DOM buttons collapse into ONE node named
        'Transcribe Open transcription mode menu'. Calling press() on it fires
        the DEFAULT action (start transcribing) instead of opening the menu, so
        we must click the caret specifically — the RIGHT edge of the node's
        bounds — via InputSim coordinates.

        Returns True once the dialog (group 'Upload a recording') is present.
        """
        if self._upload_dialog_present():
            return True

        # The caret only shows in the main record view — if we're on the Context
        # tab (e.g. right after a context upload), switch to Note first so the
        # 'Transcribe Open transcription mode menu' button is present.
        if not self.app.locator("button[name*='transcription mode menu']").exists():
            self.open_tab("Note")
            time.sleep(1.0)

        if not self._open_mode_menu():
            return False
        time.sleep(1.0)

        # Click the 'Upload session audio' menu item (role=menu_item, exact name
        # confirmed via dump). Try the direct selector first, then a text scan.
        item = self.app.locator("menu_item[name='Upload session audio']")
        if item.exists():
            try:
                item.press()
                time.sleep(1.5)
                if self._upload_dialog_present():
                    return True
            except Exception:
                try:
                    xa11y.input_sim().click(item.elements()[0])
                    time.sleep(1.5)
                    if self._upload_dialog_present():
                        return True
                except Exception:
                    pass

        for role in ["menu_item", "list_item", "button", "static_text"]:
            try:
                elements = self.app.locator(role).elements()
            except Exception:
                continue
            for el in elements:
                text = (el.name or el.value or "").strip().lower()
                if "upload" in text and "audio" in text:
                    try:
                        el.press()
                    except Exception:
                        try:
                            xa11y.input_sim().click(el)
                        except Exception:
                            continue
                    time.sleep(1.5)
                    if self._upload_dialog_present():
                        return True
        return self._upload_dialog_present()

    def _mode_menu_open(self) -> bool:
        """True if the transcription-mode dropdown is currently open.

        The items are `menu_item` role (not static_text), so _has_text can't see
        them — check the menu item / menu container directly.
        """
        for sel in (
            "menu_item[name='Upload session audio']",
            "menu_item[name='Dictate']",
            "menu[name*='transcription mode']",
        ):
            if self.app.locator(sel).exists():
                return True
        return False

    def _open_mode_menu(self) -> bool:
        """Open the transcription-mode dropdown.

        The split-button node collapses main+caret into one AX node. We try, in
        order: (1) expand() — the semantic 'open menu' action; (2) a coordinate
        click on the RIGHT edge of the node (where the ChevronDown caret sits),
        avoiding the default Transcribe action at the centre; (3) press() as a
        last resort. Success = the menu's `menu_item`s become visible.
        """
        if self._mode_menu_open():
            return True

        btns = []
        for sel in ("button[name*='transcription mode menu']",
                    "button[name*='mode menu']"):
            try:
                btns = self.app.locator(sel).elements()
            except Exception:
                btns = []
            if btns:
                break
        if not btns:
            return False

        btn = btns[0]
        sim = xa11y.input_sim()

        # (1) Semantic expand.
        try:
            btn.expand()
            time.sleep(0.8)
            if self._mode_menu_open():
                return True
        except Exception:
            pass

        # (2) Coordinate click on the caret (right edge, vertically centred).
        try:
            b = btn.bounds
            if b is not None:
                x = int(b.x + b.width - 10)
                y = int(b.y + b.height / 2)
                sim.click((x, y))
                time.sleep(0.8)
                if self._mode_menu_open():
                    return True
        except Exception:
            pass

        # (3) Last resort: press the node (may fire the default action).
        try:
            btn.press()
            time.sleep(0.8)
            return self._mode_menu_open()
        except Exception:
            return False

    def _upload_dialog_present(self) -> bool:
        if self.app.locator("group[name='Upload a recording']").exists():
            return True
        # Fallback: match the dropzone/label text.
        return self._has_text(["Click or drag file to this area", "Upload a recording"])

    def select_upload_mode(self, mode: str) -> bool:
        """Pick the Transcribe/Dictate segmented control INSIDE the upload
        dialog. `mode` is 'Transcribe' or 'Dictate' (rendered as radio_buttons).
        """
        target = mode.strip().capitalize()
        for sel in (f"radio_button[name='{target}']", f"button[name='{target}']"):
            loc = self.app.locator(sel)
            if loc.exists():
                try:
                    loc.press()
                    time.sleep(0.5)
                    return True
                except Exception:
                    try:
                        xa11y.input_sim().click(loc.elements()[0])
                        time.sleep(0.5)
                        return True
                    except Exception:
                        pass
        return False

    def upload_audio(self, file_path, mode: str = "Transcribe") -> bool:
        """Upload an audio file through the 'Upload a recording' dialog.

        Steps (all traced from a real AX tree):
          1. open the dialog (caret -> 'Upload session audio')
          2. select the Transcribe/Dictate segmented control
          3. click the dropzone button -> native NSOpenPanel (dialog 'Open')
          4. in the panel, use Cmd+Shift+G ('Go to folder') to type the
             ABSOLUTE path, Enter to resolve it, Enter again / click 'Open'
             to confirm. This avoids clicking through the file list and is
             resolution-independent.

        Returns True if the panel was driven and dismissed (upload started).
        The caller then waits for note generation as usual.
        """
        from pathlib import Path as _Path

        file_path = str(_Path(file_path).expanduser().resolve())

        if not self.open_upload_dialog():
            return False
        # Default dialog mode is Transcribe; only switch if Dictate requested.
        if mode.strip().lower() == "dictate":
            self.select_upload_mode("Dictate")

        # Click the dropzone to trigger the native picker. The dropzone is a
        # button just before the 'Click or drag...' static_text.
        clicked = self._click_dropzone()
        if not clicked:
            return False

        return self._drive_open_panel(file_path)

    def _drive_open_panel(self, file_path: str) -> bool:
        """Drive the native macOS Open panel to select `file_path`.

        Shared by audio upload and context upload. Assumes the panel is about to
        appear (or already visible). Uses Cmd+Shift+G ('Go to folder') to type
        the ABSOLUTE path, which avoids clicking the file list and is
        resolution-independent. Returns True once the panel is dismissed.
        """
        from pathlib import Path as _Path
        file_path = str(_Path(file_path).expanduser().resolve())

        panel = self.app.locator("dialog[name='Open']")
        try:
            panel.wait_visible(timeout=10.0)
        except Exception:
            return False

        sim = xa11y.input_sim()
        # Cmd+Shift+G opens the 'Go to the folder' path sheet.
        sim.chord("g", ["Meta", "Shift"])
        # The sheet needs a moment to appear AND grab focus — typing too soon
        # drops the first character(s) (we saw '/Users' arrive as '/sers').
        time.sleep(1.8)

        # Clear the field, prime focus with a throwaway '/'+Backspace so the
        # first REAL char isn't dropped, then type the path char-by-char.
        for _ in range(80):
            sim.press("Backspace")
        time.sleep(0.2)
        sim.type_text("/")
        time.sleep(0.1)
        sim.press("Backspace")
        time.sleep(0.1)
        for ch in file_path:
            sim.type_text(ch)
            time.sleep(0.02)
        time.sleep(0.5)

        # First Return submits the go-to sheet -> selects the file, enabling Open.
        sim.press("Return")
        time.sleep(1.5)

        def _open_button():
            for sel in ("dialog[name='Open'] button[name='Open']",
                        "button[name='Open']"):
                loc = self.app.locator(sel)
                if loc.exists():
                    try:
                        return loc.elements()[0]
                    except Exception:
                        return None
            return None

        confirmed = False
        deadline = time.time() + 8.0
        while time.time() < deadline:
            btn = _open_button()
            if btn is not None:
                try:
                    if getattr(btn, "enabled", True):
                        btn.press()
                        confirmed = True
                        break
                except Exception:
                    pass
            sim.press("Return")
            time.sleep(1.0)

        if not confirmed and not self.app.locator("dialog[name='Open']").exists():
            confirmed = True

        time.sleep(1.5)
        return confirmed or not self.app.locator("dialog[name='Open']").exists()

    def upload_context(self, file_path) -> bool:
        """Upload a CONTEXT file via the Context tab's paperclip button.

        Traced from scribe-fe-v2: the control is an icon-only button
        (Paperclip) with data-testid 'context-file-upload-button'. Clicking it
        opens the same native NSOpenPanel as audio upload, so we reuse
        _drive_open_panel. Returns True once the panel is dismissed.
        """
        from pathlib import Path as _Path
        file_path = str(_Path(file_path).expanduser().resolve())

        # Switch to the Context tab (where the uploader lives).
        self.open_context_tab()
        time.sleep(1.0)

        # The paperclip upload button is icon-only (NO AX name). Traced from a
        # real tree it lives inside the context editor group
        # `group "Drag and drop files here"`, as the button right after the
        # context text_area. Click that button.
        if not self._click_context_paperclip():
            return False

        return self._drive_open_panel(file_path)

    def _click_context_paperclip(self) -> bool:
        """Click the Context tab's icon-only paperclip (📎) upload button.

        It has NO AX name, so we identify it STRUCTURALLY (no coordinates):

          - The context editor's buttons live in a container whose children
            include the context `text_area`. The paperclip + 'add patient'
            buttons are siblings of that text_area.
          - The MICROPHONE button (which must NOT be clicked — it starts
            dictation) lives in a different group whose siblings include a
            `combo_box` (its mode dropdown) and NO text_area.

        So the safe candidate set = empty-name buttons whose PARENT's children
        include a text_area but NOT a combo_box. That excludes the mic entirely.
        Among those we skip tiny (<20px) placeholder nodes. Both remaining
        candidates (paperclip + add-patient) are harmless to click — neither
        starts dictation — so we click each until the native Open panel appears.
        """
        try:
            all_btns = self.app.locator("button").elements()
        except Exception:
            return False

        def _sibling_roles(btn):
            try:
                parent = btn.parent()
                if not parent:
                    return []
                return [c.role for c in parent.children()]
            except Exception:
                return []

        candidates = []
        for b in all_btns:
            if (b.name or "").strip():
                continue  # icon-only buttons only
            roles = _sibling_roles(b)
            # Must be in the context-editor group (has a text_area sibling) and
            # NOT in the mic group (which has a combo_box sibling).
            if "text_area" not in roles or "combo_box" in roles:
                continue
            bounds = getattr(b, "bounds", None)
            if bounds is not None and (bounds.width < 20 or bounds.height < 20):
                continue  # skip 2x2 placeholder nodes
            candidates.append(b)

        # Click candidates (all dictation-safe) until the Open panel appears.
        for btn in candidates:
            try:
                btn.press()
            except Exception:
                try:
                    xa11y.input_sim().click(btn)
                except Exception:
                    continue
            time.sleep(1.5)
            if self.app.locator("dialog[name='Open']").exists():
                return True

        return self.app.locator("dialog[name='Open']").exists()

    def _click_dropzone(self) -> bool:
        """Click the FileDropzone button inside the upload dialog."""
        # The dropzone is an (empty-name) button adjacent to the
        # 'Click or drag file to this area to upload' static_text. Find that
        # text, then click the nearest preceding button in the dialog subtree.
        dialog = self.app.locator("group[name='Upload a recording']")
        if dialog.exists():
            try:
                buttons = dialog.descendant("button").elements()
            except Exception:
                buttons = []
            # The Close button also lives here; pick the first non-Close button.
            for btn in buttons:
                if (btn.name or "").strip() != "Close":
                    try:
                        btn.press()
                        time.sleep(1.0)
                        return True
                    except Exception:
                        try:
                            xa11y.input_sim().click(btn)
                            time.sleep(1.0)
                            return True
                        except Exception:
                            continue
        # Fallback: click the label text directly.
        return click_first_match(
            self.app,
            [
                "static_text[value*='Click or drag file']",
                "button[name*='Click or drag']",
            ],
        )

    def stop_recording(self) -> None:
        if not self.end_recording():
            raise AssertionError("Could not find an End recording control")

    def wait_note_generation(self, timeout: float = 60.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.note_generation_started() or self.has_transcript_tab():
                return True
            time.sleep(1)
        return False

    def wait_note_complete(self, timeout: float = 150.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.note_generation_done():
                return True
            time.sleep(3)
        return False

    def click_create_note_if_available(self) -> bool:
        if self.is_generating_note():
            return True

        for _ in range(15):
            if self.is_generating_note():
                return True
            for el in self.app.locator("button").elements():
                if (el.name or "") != "Create":
                    continue
                try:
                    el.press()
                    time.sleep(1)
                    return True
                except Exception:
                    try:
                        xa11y.input_sim().click(el)
                        time.sleep(1)
                        return True
                    except Exception:
                        continue
            time.sleep(1)
        return False

    def select_hp_template_if_available(self) -> bool:
        selectors = [
            "text_field[name*='Search']",
            "text_field[name*='template']",
            "text_field[name*='Template']",
        ]
        search = None
        for selector in selectors:
            loc = self.app.locator(selector)
            if loc.exists():
                search = loc
                break
        if search is None:
            return False

        try:
            search.set_value("H&P")
            time.sleep(1)
        except Exception:
            pass

        for role in ["button", "list_item", "static_text"]:
            for el in self.app.locator(role).elements():
                text = el.name or el.value or ""
                if "H&P" not in text and "History" not in text:
                    continue
                try:
                    el.press()
                    time.sleep(1)
                    return True
                except Exception:
                    try:
                        xa11y.input_sim().click(el)
                        time.sleep(1)
                        return True
                    except Exception:
                        continue
        return False

    def is_generating_note(self) -> bool:
        needles = [
            "Analyzing transcript",
            "Stop generating",
            "Generating",
            "Creating your note",
        ]
        return self._has_text(needles)

    def has_transcript_error(self) -> bool:
        needles = [
            "Error generating transcript",
            "Something went wrong while creating your transcript",
            "Note generation was interrupted",
        ]
        return self._has_text(needles)

    def wait_until_generation_idle(self, timeout: float = 180.0) -> bool:
        deadline = time.time() + timeout
        saw_generating = False
        while time.time() < deadline:
            if self.is_generating_note():
                saw_generating = True
                time.sleep(2)
                continue
            if saw_generating:
                time.sleep(2)
            return True
        return False

    def wait_for_note_content(self, min_chars: int = 80, timeout: float = 180.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            self._activate_tab("Note")
            if self.has_transcript_error():
                return False
            if len(self.visible_clinical_text()) >= min_chars:
                return True
            time.sleep(2)
        return False

    def wait_for_transcript_content(self, min_chars: int = 40, timeout: float = 120.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            self._activate_tab("Transcript")
            if self.has_transcript_error():
                return False
            if len(self.visible_clinical_text()) >= min_chars:
                return True
            time.sleep(2)
        return False

    def visible_clinical_text(self) -> str:
        ignored = {
            "Heidi",
            "Scribe",
            "Evidence",
            "Tasks",
            "Patients",
            "My Library",
            "Community",
            "Team",
            "Settings",
            "Devices",
            "Dictate history",
            "Help",
            "Notifications",
            "Transcript",
            "Context",
            "Note",
            "Ready when you are",
            "Transcribe to create a note",
            "Review your note before use to ensure it accurately represents the visit",
        }
        chunks: list[str] = []
        for el in self.app.locator("static_text").elements():
            text = (el.name or el.value or "").strip()
            if not text or text in ignored:
                continue
            if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", text):
                continue
            if "@" in text or text.startswith("+"):
                continue
            chunks.append(text)
        return "\n".join(chunks)

    def _body_text(self) -> str:
        parts: list[str] = []
        for el in self.app.locator("static_text").elements():
            text = (el.name or el.value or "").strip()
            if len(text) < 15:
                continue
            if "Medical knowledge only" in text:
                continue
            if "Skip to" in text:
                continue
            parts.append(text)
        return "\n".join(parts)

    def _input_device_combo(self):
        candidates = []
        for el in self.app.locator("combo_box").elements():
            if (el.name or "") == "Add patient identifier":
                continue
            if el.value:
                return el
            candidates.append(el)
        if candidates:
            return sorted(candidates, key=lambda el: (el.bounds.y, el.bounds.x))[0]
        return None

    def _activate_tab(self, tab_name: str) -> bool:
        for role in ["button", "tab"]:
            for el in self.app.locator(role).elements():
                if (el.name or "") != tab_name:
                    continue
                try:
                    el.press()
                    time.sleep(0.5)
                    return True
                except Exception:
                    try:
                        xa11y.input_sim().click(el)
                        time.sleep(0.5)
                        return True
                    except Exception:
                        continue
        return False

    def _has_text(self, needles: list[str]) -> bool:
        for role in ["static_text", "button", "alert"]:
            try:
                elements = self.app.locator(role).elements()
            except Exception:
                continue
            for el in elements:
                text = el.name or el.value or ""
                lowered = text.lower()
                if any(needle.lower() in lowered for needle in needles):
                    return True
        return False
