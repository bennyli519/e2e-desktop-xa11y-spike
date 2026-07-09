"""Shared recording-flow engine for the per-duration E2E cases.

Design (why it's shaped like this):

The recording flows are SLOW (a 10-min case records for ~8 min of real audio).
We must NOT re-run the flow once per assertion. So each test *file* runs the
flow exactly ONCE via a module-scoped `result` fixture, caches everything into a
`RecordingResult`, and the individual `test_*` functions each assert ONE fact
against that cached result.

That gives the clean per-assertion pytest output Benny wants:

    tests/recording/test_30s.py::test_recording_starts        PASSED
    tests/recording/test_30s.py::test_timer_advances          PASSED
    tests/recording/test_30s.py::test_transcription_generated PASSED
    tests/recording/test_30s.py::test_note_generated          PASSED
    tests/recording/test_30s.py::test_transcript_accuracy     PASSED
    tests/recording/test_30s.py::test_note_generated_nonempty PASSED

Each line is one checkmark. The terminal-summary hook (see conftest.py) then
prints a per-flow ☑/✗ table for demos.

This module is NOT collected by pytest (filename doesn't match test_*.py).
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import xa11y

from lib import audio
from lib.login import is_logged_in
from pages import RecordingPage
from pages.sidebar import Sidebar

ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"

# ---------------------------------------------------------------------------
# Keyword pools (spoken content per clip) — used for transcript accuracy.
# ---------------------------------------------------------------------------
KEYWORDS_30S = [
    "headache", "sleep", "morning", "nausea", "photophobia",
    "fatigue", "afternoon", "week",
]

# consult_1min.txt covers headache + sleep + stress + BP in one minute.
KEYWORDS_1MIN = [
    "headache", "forehead", "afternoon", "evening", "light", "sensitivity",
    "nausea", "tired", "sleep", "waking", "morning", "exhausted", "coffee",
    "stressed", "anxious", "chest", "heart", "breath", "pressure",
    "amlodipine", "caffeine", "weeks",
]

KEYWORDS_5MIN = [
    "headache", "forehead", "afternoon", "evening", "light", "sensitivity",
    "sleep", "waking", "morning", "exhausted", "coffee", "caffeine",
    "stress", "anxious", "anxiety", "chest", "racing", "breath", "dread",
    "panic", "blood", "pressure", "amlodipine", "medication", "pulse",
    "heart", "lungs", "tension", "cholesterol", "kidney", "therapy",
    "father", "smoke", "alcohol", "monitor", "review", "weeks", "fatigue",
]

KEYWORDS_10MIN = KEYWORDS_5MIN + [
    "diabetes", "metformin", "sugar", "thirst", "urination", "numb",
    "tingling", "toes", "neuropathy", "feet", "sensation", "knee",
    "stairs", "stiffness", "osteoarthritis", "eczema", "skin", "elbow",
    "itchy", "moisturiser", "steroid", "hydrocortisone", "hba1c",
    "monofilament", "paracetamol", "diet",
]


# ---------------------------------------------------------------------------
# Result container — one per flow, cached for all that flow's assertions.
# ---------------------------------------------------------------------------
@dataclass
class RecordingResult:
    flow: str                       # "30s", "1min", ...
    seconds: float
    transcript_threshold: float
    keywords: list[str]

    recording_started: bool = False
    audio_injected: bool = False
    timer_samples: list = field(default_factory=list)
    timer_advanced: bool = False
    timer_last_s: int | None = None
    note_started: bool = False
    note_completed: bool = False
    duration_display: str | None = None    # mm:ss shown after stop
    duration_display_s: int | None = None  # parsed to seconds
    transcript: str = ""
    note: str = ""
    error: str | None = None

    @property
    def hits(self) -> list[str]:
        t = self.transcript.lower()
        return [w for w in self.keywords if w in t]

    @property
    def misses(self) -> list[str]:
        t = self.transcript.lower()
        return [w for w in self.keywords if w not in t]

    @property
    def transcript_accuracy(self) -> float:
        if not self.keywords:
            return 0.0
        return len(self.hits) / len(self.keywords)


# A registry the terminal-summary hook reads to print the per-flow table.
# Keyed by flow label. Populated as each module's `result` fixture runs.
FLOW_RESULTS: dict[str, RecordingResult] = {}


# ---------------------------------------------------------------------------
# Flow helpers
# ---------------------------------------------------------------------------
def _timer_to_seconds(mmss: str | None) -> int | None:
    if not mmss or ":" not in mmss:
        return None
    try:
        m, s = mmss.split(":")
        return int(m) * 60 + int(s)
    except ValueError:
        return None


def _reach_fresh_session(heidi_app: xa11y.App) -> RecordingPage:
    """Open a brand-new Scribe session, tolerating a dirty prior state."""
    if not is_logged_in(heidi_app):
        pytest.skip("Not logged in — run tests/auth/test_login.py first")
    sidebar = Sidebar(heidi_app)
    rec = RecordingPage(heidi_app)

    last_err = None
    for attempt in range(4):
        try:
            # A previous flow may have left a session recording — end it first.
            end = heidi_app.locator("button[name='End recording']")
            if end.exists():
                end.press()
                time.sleep(3.0)
            sidebar.reset_to_scribe()
            time.sleep(1.0)
            heidi_app.locator("button[name='New session']").wait_visible(timeout=10.0)
            if sidebar.new_session():
                heidi_app.locator("button[name*='Transcribe']").wait_visible(timeout=10.0)
                return rec
            last_err = f"new_session() returned False (attempt {attempt + 1})"
        except Exception as e:
            last_err = repr(e)
        time.sleep(2.0)
    pytest.fail(f"Could not reach a fresh session after retries: {last_err}")


def run_recording_flow(
    heidi_app: xa11y.App,
    flow: str,
    seconds: float,
    clip: str,
    keywords: list[str],
    transcript_threshold: float,
) -> RecordingResult:
    """Run ONE full recording flow and return a cached RecordingResult.

    Steps: fresh session -> start -> inject audio -> record `seconds`
    (sampling the timer) -> stop -> wait for note generation -> read the
    verbatim transcript + generated note -> compute accuracy.

    Never raises for a flow-level failure: it records what happened into the
    result so each downstream assertion can report its own PASS/FAIL cleanly.
    """
    res = RecordingResult(
        flow=flow, seconds=seconds,
        transcript_threshold=transcript_threshold, keywords=keywords,
    )
    FLOW_RESULTS[flow] = res

    clip_path = ASSETS / clip
    if not clip_path.exists():
        pytest.skip(f"Clip missing: {clip_path} (run scripts/setup_audio.sh)")

    injector = audio.AudioInjector(heidi_app)
    try:
        rec = _reach_fresh_session(heidi_app)

        # Prepare audio injection BEFORE recording starts. On Windows this
        # selects Heidi's input device (must happen pre-record); on macOS it
        # routes the system default I/O to BlackHole. Same call both places.
        res.audio_injected = injector.prepare()

        rec.start_recording()
        res.recording_started = rec.is_recording()

        if res.audio_injected:
            injector.play(clip_path, seconds)

        res.timer_samples = rec.wait_recording(seconds, sample_every=60.0)

        readable: list[int] = [
            s for _, v in res.timer_samples
            if (s := _timer_to_seconds(v)) is not None
        ]
        if len(readable) >= 2:
            first_s, last_s = readable[0], readable[-1]
            res.timer_last_s = last_s
            res.timer_advanced = last_s > first_s

        rec.stop_recording()
        # Capture the frozen duration display right after stopping, before the
        # note view can replace the timer node.
        res.duration_display = rec.duration_display()
        res.duration_display_s = _timer_to_seconds(res.duration_display)
        res.note_started = rec.wait_note_generation(timeout=90.0)
        res.note_completed = rec.wait_note_complete(timeout=240.0)

        res.transcript = rec.transcript_text()
        res.note = rec.note_text()
    except Exception as e:  # keep the result usable for reporting
        res.error = repr(e)
    finally:
        injector.cleanup()

    return res
