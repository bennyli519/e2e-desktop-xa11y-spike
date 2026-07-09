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
        return self._body_text()

    def note_text(self) -> str:
        self.open_tab("Note")
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
            self.app.locator(
                "button[name='Transcribe'], button[name='Dictate']"
            ).wait_visible(timeout=20.0)
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

    def start_recording(self) -> None:
        self.start_transcribing()

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
            ],
        )

    def resume_recording(self) -> bool:
        return click_first_match(
            self.app,
            [
                "button[name='Resume']",
                "button[name='Resume transcribing']",
                "button[name='Resume dictating']",
                "button[name*='Resume transcribing']",
                "button[name*='Resume dictating']",
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
            ],
        )
        if ok:
            time.sleep(2)
        return ok

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
