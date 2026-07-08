"""Reusable assertion bodies + fixture factory for the per-duration flows.

Each duration file (test_30s.py, test_1min.py, ...) defines a module-scoped
`result` fixture via `make_result_fixture(...)` and a set of one-line test
functions that delegate to the `check_*` helpers here. This keeps the flow
logic in ONE place while still giving pytest one visible test per assertion
per duration.
"""
from __future__ import annotations

import os

import pytest

from _flow import RecordingResult, run_recording_flow


def make_result_fixture(flow, seconds, clip, keywords, transcript_threshold):
    """Build a module-scoped fixture that runs the flow once and caches it.

    TRANSCRIPT_MATCH_THRESHOLD env var overrides the per-flow default (handy
    for a quick smoke run, e.g. 0.6).
    """
    threshold = float(os.environ.get("TRANSCRIPT_MATCH_THRESHOLD",
                                     str(transcript_threshold)))

    @pytest.fixture(scope="module")
    def result(heidi_app) -> RecordingResult:
        return run_recording_flow(
            heidi_app, flow=flow, seconds=seconds, clip=clip,
            keywords=keywords, transcript_threshold=threshold,
        )

    return result


def _no_flow_error(res: RecordingResult) -> None:
    if res.error:
        pytest.fail(f"[{res.flow}] flow crashed before assertions: {res.error}")


# --- individual checks (one per visible test) -------------------------------
def check_recording_starts(res: RecordingResult) -> None:
    _no_flow_error(res)
    assert res.recording_started, (
        f"[{res.flow}] recording did not start (no 'End recording' control)"
    )


def check_timer_advances(res: RecordingResult) -> None:
    _no_flow_error(res)
    assert res.timer_advanced, (
        f"[{res.flow}] recording timer did not advance — session may have "
        f"stalled. samples={res.timer_samples}"
    )
    floor = min(120, int(res.seconds * 0.5))
    assert res.timer_last_s is not None and res.timer_last_s >= floor, (
        f"[{res.flow}] timer only reached {res.timer_last_s}s (expected "
        f">= {floor}s). samples={res.timer_samples}"
    )


def check_transcription_generated(res: RecordingResult) -> None:
    _no_flow_error(res)
    if not res.audio_injected:
        pytest.skip(f"[{res.flow}] no BlackHole audio injected — content check "
                    f"needs real audio (run scripts/setup_audio.sh + reboot)")
    assert res.transcript.strip(), (
        f"[{res.flow}] transcript is empty — audio->text path produced nothing"
    )


def check_note_generated(res: RecordingResult) -> None:
    _no_flow_error(res)
    assert res.note_started, (
        f"[{res.flow}] note generation never started after stopping"
    )
    if not res.audio_injected:
        pytest.skip(f"[{res.flow}] no BlackHole audio injected — note body "
                    f"needs real audio")
    # Per Benny 2026-07: note is asserted NON-EMPTY only (SOAP note normalises
    # spoken words, so keyword accuracy on it is intentionally not gated).
    assert res.note.strip(), f"[{res.flow}] generated note body is empty"


def check_transcript_accuracy(res: RecordingResult) -> None:
    _no_flow_error(res)
    if not res.audio_injected:
        pytest.skip(f"[{res.flow}] no BlackHole audio injected — accuracy check "
                    f"needs real audio")
    acc = res.transcript_accuracy
    print(
        f"\n[{res.flow}] transcript accuracy: {acc:.1%} "
        f"({len(res.hits)}/{len(res.keywords)}) "
        f"threshold={res.transcript_threshold:.0%} misses={res.misses}"
    )
    assert acc >= res.transcript_threshold, (
        f"[{res.flow}] transcript accuracy {acc:.1%} below threshold "
        f"{res.transcript_threshold:.0%}. Missed {res.misses}.\n"
        f"Transcript (first 800):\n{res.transcript[:800]}"
    )
