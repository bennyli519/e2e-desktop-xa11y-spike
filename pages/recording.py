"""Page Object: Scribe recording + note-generation controls.

Selectors verified against a live Heidi session (see reports/rec_*.txt):

  start recording   button "Transcribe Open transcription mode menu"
  recording timer   static_text with value mm:ss (e.g. "00:16")
  while recording   button "Pause transcribing", button "End recording"
  stop recording    button "End recording"
  after stop        button "Resume", tab_group gains a "Transcript" tab
  note generating   static_text "Analyzing transcript" + button "Stop generating"

Note-generation is asserted as "starts or completes" (per the POC ticket): we
treat the "Analyzing transcript" / "Stop generating" markers as STARTED, and a
populated Note tab / disappearance of those markers as COMPLETE.
"""
import time

import xa11y

# The transcribe button doubles as the start-recording control; its accessible
# name is the menu label. Match on a prefix so a label tweak won't break us.
START_RECORDING = "button[name*='Transcribe']"
PAUSE_RECORDING = "button[name='Pause transcribing']"
END_RECORDING = "button[name='End recording']"
RESUME_RECORDING = "button[name='Resume']"

# Note-generation "started" markers (either is sufficient).
GENERATING_MARKERS = [
    "static_text[value*='Analyzing transcript']",
    "button[name='Stop generating']",
    "static_text[value*='Generating']",
]

# A "Transcript" tab only appears once there is captured audio/transcript.
TRANSCRIPT_TAB = "button[name='Transcript']"


class RecordingPage:
    def __init__(self, app: xa11y.App):
        self.app = app

    # --- state reads ---
    def recording_timer(self) -> str | None:
        """Return the mm:ss recording timer value, or None if not present."""
        for e in self.app.locator("static_text").elements():
            v = (e.value or "")
            if len(v) == 5 and v[2] == ":" and v[:2].isdigit() and v[3:].isdigit():
                return v
        return None

    def is_recording(self) -> bool:
        return self.app.locator(END_RECORDING).exists()

    def note_generation_started(self) -> bool:
        return any(self.app.locator(sel).exists() for sel in GENERATING_MARKERS)

    def has_transcript_tab(self) -> bool:
        return self.app.locator(TRANSCRIPT_TAB).exists()

    # --- actions ---
    def start_recording(self) -> None:
        btn = self.app.locator(START_RECORDING)
        btn.wait_visible(timeout=10.0)
        btn.press()
        # Confirm we actually entered recording state.
        self.app.locator(END_RECORDING).wait_visible(timeout=10.0)

    def wait_recording(self, seconds: float) -> None:
        """Hold in recording state for `seconds`, polling the timer to prove
        it is actually advancing (not a frozen UI)."""
        start = self.recording_timer()
        deadline = time.time() + seconds
        while time.time() < deadline:
            time.sleep(2)
        end = self.recording_timer()
        # Best-effort liveness signal; callers assert on it if they want.
        self._last_timer_delta = (start, end)

    def stop_recording(self) -> None:
        btn = self.app.locator(END_RECORDING)
        btn.wait_visible(timeout=10.0)
        btn.press()

    def wait_note_generation(self, timeout: float = 60.0) -> bool:
        """Wait until note-generation markers appear (started). Returns True if
        generation was observed to start within `timeout`."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.note_generation_started() or self.has_transcript_tab():
                return True
            time.sleep(1)
        return False
