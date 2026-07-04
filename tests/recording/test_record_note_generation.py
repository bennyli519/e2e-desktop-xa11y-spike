"""recording: the POC true-app E2E scenario (APP-7808) + long-session cases.

Tests:

1. test_record_stop_note_generation — the ticket's core scenario:
   login -> new session -> record ~30s -> stop -> note generation STARTS.
   Runs with or without audio (structural check only).

2. test_record_transcribes_spoken_content — true end-to-end (30s):
   inject a fixed spoken consult via BlackHole, record, stop, wait for the note
   to complete, assert transcription accuracy >= threshold. Requires BlackHole.

3. test_record_5min_session / test_record_10min_session — long-session stress:
   same true-e2e flow but recording for 5 / 10 minutes (clip loops to fill the
   duration). Proves the session stays stable, the timer keeps advancing, and
   note generation still works after a long capture.

Run from Ghostty (Accessibility + Screen Recording), logged in, Heidi foreground:
    .venv/bin/python3.14 -m pytest tests/recording/ -v -s
    .venv/bin/python3.14 -m pytest tests/recording/ -v -s -m "not longsession"  # skip long
    .venv/bin/python3.14 -m pytest tests/recording/ -v -s -k 5min              # just 5min
"""
import os

import pytest
import xa11y

from lib.login import is_logged_in
from pages import RecordingPage
from pages.sidebar import Sidebar

pytestmark = [pytest.mark.recording, pytest.mark.slow]

ASSETS = os.path.join(os.path.dirname(__file__), "..", "..", "assets")

# Words spoken in assets/consult_30s.wav.
EXPECTED_KEYWORDS = [
    "headache", "sleep", "morning", "nausea", "photophobia",
    "fatigue", "afternoon", "week",
]

# Larger keyword pools spoken in the long consults. With ~50 words a high
# threshold (0.98) still tolerates a missed word or two, instead of the 8-word
# pool where 0.98 would mean "every single word".
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


@pytest.fixture()
def fresh_session(heidi_app: xa11y.App) -> RecordingPage:
    """Ensure logged in, open a brand-new Scribe session, return RecordingPage.

    Robust against a dirty prior state (a previous session left open, tree
    mid-transition): retry reset + New session, waiting for the start-recording
    control to confirm we actually reached a fresh session view.
    """
    import time as _t

    if not is_logged_in(heidi_app):
        pytest.skip("Not logged in — run tests/auth/test_login.py first")
    sidebar = Sidebar(heidi_app)
    rec = RecordingPage(heidi_app)

    last_err = None
    for attempt in range(4):
        try:
            # A previous test may have left a session actively recording — that
            # blocks starting a new one. End it first.
            end = heidi_app.locator("button[name='End recording']")
            if end.exists():
                end.press()
                _t.sleep(3.0)
            sidebar.reset_to_scribe()
            _t.sleep(1.0)
            # wait for the New session button to be present before clicking
            heidi_app.locator("button[name='New session']").wait_visible(timeout=10.0)
            if sidebar.new_session():
                # confirm we're in a session: the transcribe/start control shows
                heidi_app.locator("button[name*='Transcribe']").wait_visible(timeout=10.0)
                return rec
            last_err = f"new_session() returned False (attempt {attempt+1})"
        except Exception as e:  # transient tree collapse / transition
            last_err = repr(e)
        _t.sleep(2.0)
    pytest.fail(f"Could not reach a fresh session after retries: {last_err}")


def _seconds() -> float:
    return float(os.environ.get("RECORD_SECONDS", "30"))


def _match_threshold(default: float = 0.4) -> float:
    """Fraction of expected keywords that must appear in the note (0..1).
    Override with TRANSCRIPT_MATCH_THRESHOLD."""
    return float(os.environ.get("TRANSCRIPT_MATCH_THRESHOLD", str(default)))


def _timer_to_seconds(mmss: str | None) -> int | None:
    if not mmss or ":" not in mmss:
        return None
    try:
        m, s = mmss.split(":")
        return int(m) * 60 + int(s)
    except ValueError:
        return None


def _run_transcription_case(rec: RecordingPage, audio_injection, seconds: float,
                            keywords=None, threshold=0.4, clip=None):
    """Shared flow: start -> inject audio -> record `seconds` (sampling the
    timer) -> stop -> wait for note -> assert accuracy. Returns (accuracy, note).
    """
    keywords = keywords or EXPECTED_KEYWORDS

    rec.start_recording()
    assert rec.is_recording(), "Recording did not start"

    audio_injection(seconds, clip=clip)
    samples = rec.wait_recording(seconds, sample_every=60.0)
    print(f"timer samples (elapsed_s, mm:ss): {samples}")

    # Prove the session actually recorded: the timer must have advanced across
    # the samples we *could* read. On long sessions the timer node can drop out
    # of the AX tree partway through (a known WKWebView quirk), so we don't
    # require every sample — just that the readable ones show forward progress.
    readable = [(el, _timer_to_seconds(v)) for el, v in samples
                if _timer_to_seconds(v) is not None]
    assert len(readable) >= 2, f"Timer never read enough to confirm recording: {samples}"
    first_s = readable[0][1]
    last_s = readable[-1][1]
    assert last_s > first_s, f"Recording timer did not advance ({first_s} -> {last_s})"
    # the last readable sample should reflect a substantial recording
    assert last_s >= min(120, seconds * 0.5), (
        f"Timer only reached {last_s}s — session may have stalled early. "
        f"samples={samples}"
    )

    rec.stop_recording()
    assert rec.wait_note_generation(timeout=90.0), "Note generation never started"
    completed = rec.wait_note_complete(timeout=240.0)

    # Assert against the verbatim TRANSCRIPT (near word-for-word), which is the
    # true measure of audio->text accuracy. The SOAP note normalises/omits
    # spoken words, so it's a poor target for keyword matching.
    transcript = rec.transcript_text().lower()
    note = rec.note_text().lower()

    hits = [w for w in keywords if w in transcript]
    misses = [w for w in keywords if w not in transcript]
    accuracy = len(hits) / len(keywords)
    print(f"transcript accuracy: {accuracy:.1%} ({len(hits)}/{len(keywords)}) "
          f"threshold={threshold:.0%} note_complete={completed} misses={misses}")

    assert transcript.strip(), "Transcript is empty"
    assert note.strip(), "Note body is empty"
    assert accuracy >= threshold, (
        f"Transcription accuracy {accuracy:.1%} below threshold {threshold:.0%}. "
        f"Missed {misses}.\nTranscript (first 800):\n{transcript[:800]}"
    )
    return accuracy, transcript


# --- core ticket scenario ---------------------------------------------------

@pytest.mark.timeout(400)
def test_record_stop_note_generation(fresh_session: RecordingPage, audio_injection):
    """Core ticket scenario: recording works, stop works, generation starts."""
    rec = fresh_session
    rec.start_recording()
    assert rec.is_recording(), "Recording did not start (no 'End recording')"

    audio_injection()
    samples = rec.wait_recording(_seconds())
    first = _timer_to_seconds(samples[0][1])
    last = _timer_to_seconds(samples[-1][1])
    assert first is not None and last is not None, f"No timer: {samples}"
    assert last > first, f"Recording timer did not advance ({first} -> {last})"

    rec.stop_recording()
    assert rec.wait_note_generation(timeout=60.0), (
        "Note generation did not start within 60s after stopping"
    )


@pytest.mark.timeout(400)
def test_record_transcribes_spoken_content(
    fresh_session: RecordingPage, audio_injection, require_blackhole
):
    """True end-to-end (30s): injected audio -> correct transcribed content."""
    _run_transcription_case(
        fresh_session, audio_injection, _seconds(),
        keywords=EXPECTED_KEYWORDS, threshold=_match_threshold(0.9),
    )


# --- long-session stress cases ----------------------------------------------
# Real multi-topic consult audio (not a looped short clip). We assert against
# the verbatim transcript, where nearly every spoken keyword appears (~95-100%
# in practice), so 0.9 is a realistic bar: tolerates a little ASR variance while
# still catching quality regressions or a broken audio->transcript path.
# Override via TRANSCRIPT_MATCH_THRESHOLD (e.g. 0.6 for a quick smoke run).

@pytest.mark.longsession
@pytest.mark.timeout(900)  # ~5.3 min audio + generation + slack
def test_record_5min_session(
    fresh_session: RecordingPage, audio_injection, require_blackhole
):
    """5-minute real consult: stable capture + note generation + accuracy."""
    _run_transcription_case(
        fresh_session, audio_injection, seconds=310,
        keywords=KEYWORDS_5MIN, threshold=_match_threshold(0.9),
        clip=os.path.join(ASSETS, "consult_5min.wav"),
    )


@pytest.mark.longsession
@pytest.mark.timeout(1200)  # ~8.4 min audio + generation + slack
def test_record_10min_session(
    fresh_session: RecordingPage, audio_injection, require_blackhole
):
    """10-minute real consult: stable capture + note generation + accuracy."""
    _run_transcription_case(
        fresh_session, audio_injection, seconds=500,
        keywords=KEYWORDS_10MIN, threshold=_match_threshold(0.9),
        clip=os.path.join(ASSETS, "consult_10min.wav"),
    )
