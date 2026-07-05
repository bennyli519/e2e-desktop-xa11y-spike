"""Page Object: Scribe page (main note-taking view)."""
import re
import time

import xa11y

from lib import click_first_match
from pages.sidebar import Sidebar


class ScribePage:
    def __init__(self, app: xa11y.App):
        self.app = app
        self.sidebar = Sidebar(app)

    def open(self) -> bool:
        self.sidebar.close_modal()
        return self.sidebar.go_to_scribe()

    # --- elements ---
    def note_input(self):
        return self.app.locator("text_area")

    def has_new_session_button(self) -> bool:
        return self.app.locator("button[name='New session']").exists()

    def has_prep_button(self) -> bool:
        return self.app.locator("button[name='Prep']").exists()

    def selected_input_device(self) -> str | None:
        combo = self._input_device_combo()
        return combo.value if combo else None

    def recording_elapsed_seconds(self) -> int | None:
        elapsed: list[int] = []
        for el in self.app.locator("static_text").elements():
            text = el.name or el.value or ""
            match = re.fullmatch(r"(?:(\d{1,2}):)?(\d{2}):(\d{2})", text)
            if not match:
                continue
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2))
            seconds = int(match.group(3))
            elapsed.append(hours * 3600 + minutes * 60 + seconds)
        return max(elapsed) if elapsed else None

    # --- actions ---
    def new_session(self) -> bool:
        self.dismiss_open_overlays()
        ok = self.sidebar.new_session()
        if ok:
            self.app.locator("button[name='Transcribe'], button[name='Dictate']").wait_visible(
                timeout=20.0
            )
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
                    return matches_device(self.selected_input_device())
                except Exception:
                    pass

                try:
                    xa11y.input_sim().click(el)
                    time.sleep(1)
                    return matches_device(self.selected_input_device())
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

    def start_transcribing(self) -> None:
        self.select_recording_mode("Transcribe")
        self.app.locator("button[name='Transcribe']").wait_visible(timeout=20.0)
        self.app.locator("button[name='Transcribe']").press()

        consent = self.app.locator("button[name*='consent']")
        if consent.exists():
            consent.press()

        self.app.locator(
            "button[name*='Pause transcribing'], button[name*='End recording']"
        ).wait_visible(timeout=20.0)

    def start_dictating(self) -> None:
        self.select_recording_mode("Dictate")
        self.app.locator("button[name='Dictate']").wait_visible(timeout=20.0)
        self.app.locator("button[name='Dictate']").press()

        consent = self.app.locator("button[name*='consent']")
        if consent.exists():
            consent.press()

        self.app.locator(
            "button[name*='Pause dictating'], button[name*='End recording']"
        ).wait_visible(timeout=20.0)

    def select_recording_mode(self, mode: str) -> bool:
        if self.app.locator(f"button[name='{mode}']").exists():
            return True

        opened = click_first_match(
            self.app,
            [
                "button[name='Open transcription mode menu']",
                "button[name*='mode menu']",
            ],
        )
        if not opened:
            return False
        time.sleep(0.8)

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
                    return self.app.locator(f"button[name='{mode}']").exists()
                except Exception:
                    try:
                        xa11y.input_sim().click(el)
                        time.sleep(1)
                        return self.app.locator(f"button[name='{mode}']").exists()
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
            ],
        )
        if ok:
            time.sleep(2)
        return ok

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

    def _input_device_combo(self):
        for el in self.app.locator("combo_box").elements():
            if el.value:
                return el
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
