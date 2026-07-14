"""Shared Scribe-flow engine for the TCD00x per-case E2E tests.

Mirrors the design of tests/recording/_flow.py but is SELF-CONTAINED (the
recording domain is left untouched per Benny) and adds two things the TCD
cases need:

  1. A recording `mode`: "transcribe" | "dictate" (TCD006 vs TCD007, etc).
  2. A pause/resume flow that records segment A, pauses, resumes, records
     segment B, and lets the caller assert BOTH segments survived the pause
     boundary (TCD015 context / TCD016 transcript).

Why the "run once, assert many" shape:

The flows are SLOW (a 5-min case records ~5 min of real audio). We must NOT
re-run the flow per assertion. Each test *file* runs its flow exactly ONCE via
a module-scoped `result` fixture, caches everything into a result dataclass,
and the individual `test_*` functions each assert ONE fact against that cache.

This module is NOT collected by pytest (filename doesn't match test_*.py).

Audio is injected via the platform virtual device (macOS BlackHole /
Windows VB-CABLE — see lib/audio.py). Without it the structural checks
(start/timer/stop) still run and the content checks skip cleanly.

Run from Ghostty (needs Accessibility + Screen Recording), logged in, Heidi
foreground. A >600s run must be launched with Hermes background=true.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import xa11y

from lib import audio
from lib.login import is_logged_in
from pages import ScribePage

# assets/ lives at the repo root: tests/scribe/_scribe_flow.py -> ../../assets
ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"

# ---------------------------------------------------------------------------
# Keyword pools (spoken content per clip) — used for transcript accuracy.
# The 5-min consult pool matches assets/consult_5min.wav (same clip the
# recording domain uses), so TCD006/007 reuse a known-good asset.
# ---------------------------------------------------------------------------
KEYWORDS_5MIN = [
    "headache", "forehead", "afternoon", "evening", "light", "sensitivity",
    "sleep", "waking", "morning", "exhausted", "coffee", "caffeine",
    "stress", "anxious", "anxiety", "chest", "racing", "breath", "dread",
    "panic", "blood", "pressure", "amlodipine", "medication", "pulse",
    "heart", "lungs", "tension", "cholesterol", "kidney", "therapy",
    "father", "smoke", "alcohol", "monitor", "review", "weeks", "fatigue",
]

# Two DISTINCT keyword sets for the pause/resume clips. Segment A is spoken
# before the pause, segment B after resume. Asserting both proves nothing was
# dropped across the pause boundary. See scripts/make_pause_resume_clips.sh —
# the clips are generated with macOS `say` so their content is deterministic.
KEYWORDS_PAUSE_SEG_A = [
    "headache", "migraine", "forehead", "morning", "nausea", "light",
]
KEYWORDS_PAUSE_SEG_B = [
    "diabetes", "insulin", "thirst", "fatigue", "blurred", "vision",
]


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------
@dataclass
class ScribeResult:
    """One recording flow (transcribe or dictate), cached for all assertions."""
    flow: str                       # "tcd006", "tcd007", ...
    mode: str                       # "transcribe" | "dictate"
    seconds: float
    transcript_threshold: float
    keywords: list[str]

    recording_started: bool = False
    audio_injected: bool = False
    is_upload: bool = False
    context_uploaded: bool = False
    timer_samples: list = field(default_factory=list)
    timer_advanced: bool = False
    timer_last_s: int | None = None
    note_started: bool = False
    note_completed: bool = False
    duration_display: str | None = None
    duration_display_s: int | None = None
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


@dataclass
class PauseResumeResult:
    """One record -> pause -> resume flow, cached for all assertions."""
    flow: str                       # "tcd015", "tcd016"
    mode: str                       # "transcribe"
    seg_seconds: float
    keywords_a: list[str]
    keywords_b: list[str]

    recording_started: bool = False
    audio_injected: bool = False
    paused: bool = False
    resumed: bool = False
    seg_a_timer_s: int | None = None
    seg_b_timer_s: int | None = None
    note_started: bool = False
    note_completed: bool = False
    transcript: str = ""
    note: str = ""
    has_error_banner: bool = False
    error: str | None = None

    def _hits(self, keywords: list[str]) -> list[str]:
        t = self.transcript.lower()
        return [w for w in keywords if w in t]

    @property
    def seg_a_hits(self) -> list[str]:
        return self._hits(self.keywords_a)

    @property
    def seg_b_hits(self) -> list[str]:
        return self._hits(self.keywords_b)


# Registries the terminal-summary hook (conftest.py) reads for the tables.
SCRIBE_RESULTS: dict[str, ScribeResult] = {}
PAUSE_RESUME_RESULTS: dict[str, PauseResumeResult] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _timer_to_seconds(timer: str | None) -> int | None:
    if not timer or ":" not in timer:
        return None
    try:
        parts = [int(part) for part in timer.split(":")]
    except ValueError:
        return None
    if len(parts) == 2:
        m, s = parts
        return m * 60 + s
    if len(parts) == 3:
        h, m, s = parts
        return h * 3600 + m * 60 + s
    return None


def _reach_fresh_session(heidi_app: xa11y.App) -> ScribePage:
    """Bring Heidi to the foreground and open a BRAND-NEW Scribe session.

    Every flow must start from a fresh session (Benny's rule) — never reuse a
    dirty prior session. We also ALWAYS activate Heidi first: a backgrounded
    WKWebView blanks its AX tree (CLAUDE.md pitfall #10), which otherwise makes
    is_logged_in() falsely report 'not logged in' and skip the whole flow.
    """
    from lib import activate_app
    import subprocess as _sp

    def _force_front():
        # `open -a` un-minimises and raises the window (more reliable than
        # osascript 'activate', which can't restore a minimised window or reach
        # another Space). Follow with activate_app for good measure.
        try:
            _sp.run(["open", "-a", "Heidi"], capture_output=True, timeout=8)
        except Exception:
            pass
        activate_app("Heidi")

    # Foreground Heidi and give the AX tree time to repopulate, then check login
    # with retries. A backgrounded/minimised WKWebView returns a ~stub tree.
    logged_in = False
    for _ in range(6):
        _force_front()
        time.sleep(2.5)
        if is_logged_in(heidi_app):
            logged_in = True
            break
    if not logged_in:
        try:
            seen = [
                (b.name or "").strip()
                for b in heidi_app.locator("button").elements()
                if (b.name or "").strip()
            ]
        except Exception as e:
            seen = [f"<enumeration failed: {e!r}>"]
        pytest.skip(
            "Heidi's AX tree is empty — the window is not frontmost on the "
            "ACTIVE Space (macOS blanks a backgrounded/minimised/off-Space "
            "WKWebView tree; CLAUDE.md pitfall #10). Un-minimise Heidi, put it "
            "on the SAME Space as the terminal, and don't switch away. "
            "Buttons visible: " + repr(seen[:20])
        )

    rec = ScribePage(heidi_app)

    last_err = None
    for attempt in range(4):
        try:
            activate_app("Heidi")
            # End any leftover recording so New session isn't blocked.
            if rec.is_recording():
                rec.stop_recording()
                time.sleep(3.0)
            rec.open()
            time.sleep(1.0)
            # ALWAYS start a new session — do not reuse the current one.
            heidi_app.locator("button[name='New session']").wait_visible(timeout=10.0)
            if rec.new_session():
                # new_session() already waits for a session-view marker; if it
                # returned True we're in a fresh session.
                return rec
            last_err = f"new_session() returned False (attempt {attempt + 1})"
        except Exception as e:
            last_err = repr(e)
        time.sleep(2.0)
    pytest.fail(f"Could not reach a fresh session after retries: {last_err}")


def _start_mode(rec: ScribePage, mode: str) -> None:
    if mode == "dictate":
        rec.start_dictating()
    else:
        rec.start_transcribing()


# ---------------------------------------------------------------------------
# Flow 1: straight recording (transcribe or dictate) — TCD006 / TCD007
# ---------------------------------------------------------------------------
def run_recording_flow(
    heidi_app: xa11y.App,
    flow: str,
    seconds: float,
    clip: str,
    keywords: list[str],
    transcript_threshold: float,
    mode: str = "transcribe",
) -> ScribeResult:
    """Run ONE full recording flow and return a cached ScribeResult.

    Steps: fresh session -> start (transcribe|dictate) -> inject audio ->
    record `seconds` (sampling the timer) -> stop -> wait for note generation
    -> read the verbatim transcript + generated note -> compute accuracy.

    Never raises for a flow-level failure: it records what happened so each
    downstream assertion reports its own PASS/FAIL cleanly.
    """
    res = ScribeResult(
        flow=flow, mode=mode, seconds=seconds,
        transcript_threshold=transcript_threshold, keywords=keywords,
    )
    SCRIBE_RESULTS[flow] = res

    clip_path = ASSETS / clip
    if not clip_path.exists():
        pytest.skip(f"Clip missing: {clip_path} (run scripts/setup_audio.sh)")

    injector = audio.AudioInjector(heidi_app)
    try:
        rec = _reach_fresh_session(heidi_app)
        res.audio_injected = injector.prepare()

        _start_mode(rec, mode)
        res.recording_started = rec.is_recording()

        if res.audio_injected:
            injector.play(clip_path, seconds)

        res.timer_samples = rec.wait_recording(seconds, sample_every=60.0)

        readable = [
            s for _, v in res.timer_samples
            if (s := _timer_to_seconds(v)) is not None
        ]
        if len(readable) >= 2:
            res.timer_last_s = readable[-1]
            res.timer_advanced = readable[-1] > readable[0]

        rec.stop_recording()
        res.duration_display = rec.duration_display()
        res.duration_display_s = _timer_to_seconds(res.duration_display)
        res.note_started = rec.wait_note_generation(timeout=90.0)
        res.note_completed = rec.wait_note_complete(timeout=240.0)

        res.transcript = rec.transcript_text()
        res.note = rec.note_text()
    except Exception as e:
        res.error = repr(e)
    finally:
        injector.cleanup()

    return res


# ---------------------------------------------------------------------------
# Flow 2: record -> pause -> resume — TCD015 / TCD016
# ---------------------------------------------------------------------------
def run_pause_resume_flow(
    heidi_app: xa11y.App,
    flow: str,
    clip_a: str,
    clip_b: str,
    keywords_a: list[str],
    keywords_b: list[str],
    seg_seconds: float = 40.0,
    mode: str = "transcribe",
) -> PauseResumeResult:
    """Record segment A, pause, resume, record segment B, stop, read transcript.

    Two DISTINCT clips are injected either side of the pause so the caller can
    assert content from BOTH segments is present in the final transcript — i.e.
    nothing was dropped across the pause boundary.
    """
    res = PauseResumeResult(
        flow=flow, mode=mode, seg_seconds=seg_seconds,
        keywords_a=keywords_a, keywords_b=keywords_b,
    )
    PAUSE_RESUME_RESULTS[flow] = res

    clip_a_path = ASSETS / clip_a
    clip_b_path = ASSETS / clip_b
    missing = [str(p) for p in (clip_a_path, clip_b_path) if not p.exists()]
    if missing:
        pytest.skip(
            f"Pause/resume clips missing: {missing} "
            f"(run scripts/make_pause_resume_clips.sh)"
        )

    injector = audio.AudioInjector(heidi_app)
    try:
        rec = _reach_fresh_session(heidi_app)
        res.audio_injected = injector.prepare()

        _start_mode(rec, mode)
        res.recording_started = rec.is_recording()

        # --- Segment A ---
        if res.audio_injected:
            injector.play(clip_a_path, seg_seconds)
        rec.wait_recording(seg_seconds, sample_every=30.0)
        res.seg_a_timer_s = _timer_to_seconds(rec.recording_timer())
        if res.audio_injected:
            injector.stop_playback()

        # --- Pause ---
        res.paused = rec.pause_recording()
        time.sleep(4.0)

        # --- Resume + Segment B ---
        res.resumed = rec.resume_recording()
        time.sleep(1.0)
        if res.audio_injected:
            injector.play(clip_b_path, seg_seconds)
        rec.wait_recording(seg_seconds, sample_every=30.0)
        res.seg_b_timer_s = _timer_to_seconds(rec.recording_timer())
        if res.audio_injected:
            injector.stop_playback()

        # --- Stop + note generation ---
        rec.stop_recording()
        res.note_started = rec.wait_note_generation(timeout=90.0)
        res.note_completed = rec.wait_note_complete(timeout=240.0)
        res.has_error_banner = rec.has_transcript_error()

        # Wait for the transcript to actually populate, then read it stably
        # (reading too early grabs the 'transcript will appear here' placeholder
        # + sidebar noise). transcript_text() returns the longest static_text.
        rec.wait_for_transcript_content(min_chars=100, timeout=180.0)
        rec.open_tab("Transcript")
        prev, stable = "", 0
        for _ in range(20):
            cur = rec.transcript_text()
            if cur and cur == prev:
                stable += 1
                if stable >= 2:
                    break
            else:
                stable = 0
            prev = cur
            time.sleep(3.0)
        res.transcript = prev
        res.note = rec.note_text()
    except Exception as e:
        res.error = repr(e)
    finally:
        injector.cleanup()

    return res


# ---------------------------------------------------------------------------
# Flow 3: audio upload (transcribe or dictate) — TCD004 / TCD005 / TCD008
# ---------------------------------------------------------------------------
def run_upload_flow(
    heidi_app: xa11y.App,
    flow: str,
    clip: str,
    keywords: list[str],
    transcript_threshold: float,
    mode: str = "transcribe",
    context_clip: str | None = None,
) -> ScribeResult:
    """Upload an audio file through the 'Upload a recording' dialog, then wait
    for transcript + note generation and score accuracy.

    Unlike the live-recording flows this injects NO microphone audio — the
    content comes from the uploaded file itself. `mode` picks the dialog's
    Transcribe/Dictate segmented control (TCD004 vs TCD005). `context_clip`,
    if given, is a stub hook for TCD008 (context upload) — not yet wired.

    Reuses ScribeResult: recording_started/timer fields stay False (there's no
    live timer); the meaningful assertions are transcript/note/accuracy.
    """
    res = ScribeResult(
        flow=flow, mode=mode, seconds=0,
        transcript_threshold=transcript_threshold, keywords=keywords,
    )
    # Uploads have no live mic audio, but the content DID come from a real file,
    # so downstream content checks should run (not skip). Mark audio present.
    res.audio_injected = True
    res.is_upload = True
    SCRIBE_RESULTS[flow] = res

    clip_path = ASSETS / clip
    if not clip_path.exists():
        pytest.skip(f"Clip missing: {clip_path} (run scripts/setup_audio.sh)")

    try:
        rec = _reach_fresh_session(heidi_app)

        # For TCD008: upload the CONTEXT file FIRST (on the Context tab), before
        # the audio — so the context is attached to the session when the note
        # generates. Audio upload immediately kicks off processing, so it must
        # come after.
        if context_clip:
            ctx_path = ASSETS / context_clip
            if not ctx_path.exists():
                pytest.skip(f"Context file missing: {ctx_path}")
            res.context_uploaded = rec.upload_context(ctx_path)
            # Context upload can be slow to finish; give it a moment, then
            # return to the Note view so the Transcribe caret (which only shows
            # in the main record view, not the Context tab) is available for the
            # audio upload step.
            time.sleep(3.0)
            rec.open_tab("Note")
            time.sleep(1.5)

        if not rec.upload_audio(clip_path, mode=mode.capitalize()):
            res.error = "upload_audio() failed to drive the upload dialog / picker"
            return res
        res.recording_started = True  # upload accepted -> processing started

        # After upload the app auto-enters note generation. The transcript for an
        # UPLOAD lands progressively; dictate can finish LATER than transcribe.
        # Wait for the note to complete, then read the transcript from the
        # Transcript tab, re-reading until it STOPS GROWING (stable) so we get
        # the full text — not a mid-stream snapshot or the placeholder.
        res.note_started = rec.wait_note_generation(timeout=120.0)
        res.note_completed = rec.wait_for_note_content(min_chars=80, timeout=300.0)
        rec.wait_for_transcript_content(min_chars=200, timeout=240.0)

        # Read the Transcript tab and wait for it to stabilise across reads.
        # transcript_text() now returns the longest static_text (the real body).
        rec.open_tab("Transcript")
        prev, stable = "", 0
        for _ in range(20):
            cur = rec.transcript_text()
            if cur and cur == prev:
                stable += 1
                if stable >= 2:      # two identical reads in a row = settled
                    break
            else:
                stable = 0
            prev = cur
            time.sleep(3.0)
        res.transcript = prev
        res.note = rec.note_text()
    except Exception as e:
        res.error = repr(e)

    return res
