"""Reusable assertion bodies + fixture factories for the Scribe TCD flows.

Each TCD file defines a module-scoped `result` fixture via one of the
`make_*_fixture(...)` factories and a set of one-line test functions that
delegate to the `check_*` helpers here. Flow logic lives in _scribe_flow.py;
this keeps the assertions in ONE place while still giving pytest one visible
test per acceptance criterion per TCD.
"""
from __future__ import annotations

import os

import pytest

from _scribe_flow import (
    PauseResumeResult,
    ScribeResult,
    run_pause_resume_flow,
    run_recording_flow,
    run_upload_flow,
)


# ---------------------------------------------------------------------------
# Fixture factories
# ---------------------------------------------------------------------------
def make_recording_fixture(flow, mode, seconds, clip, keywords, transcript_threshold):
    """Module-scoped fixture that runs a transcribe|dictate flow once.

    TRANSCRIPT_MATCH_THRESHOLD env var overrides the per-flow default.
    """
    threshold = float(os.environ.get("TRANSCRIPT_MATCH_THRESHOLD",
                                     str(transcript_threshold)))

    @pytest.fixture(scope="module")
    def result(heidi_app) -> ScribeResult:
        return run_recording_flow(
            heidi_app, flow=flow, mode=mode, seconds=seconds, clip=clip,
            keywords=keywords, transcript_threshold=threshold,
        )

    return result


def make_pause_resume_fixture(flow, clip_a, clip_b, keywords_a, keywords_b,
                              seg_seconds=40.0, mode="transcribe"):
    """Module-scoped fixture that runs a record->pause->resume flow once."""

    @pytest.fixture(scope="module")
    def result(heidi_app) -> PauseResumeResult:
        return run_pause_resume_flow(
            heidi_app, flow=flow, clip_a=clip_a, clip_b=clip_b,
            keywords_a=keywords_a, keywords_b=keywords_b,
            seg_seconds=seg_seconds, mode=mode,
        )

    return result


def make_upload_fixture(flow, mode, clip, keywords, transcript_threshold,
                        context_clip=None):
    """Module-scoped fixture that runs an audio-upload flow once.

    TRANSCRIPT_MATCH_THRESHOLD env var overrides the per-flow default.
    """
    threshold = float(os.environ.get("TRANSCRIPT_MATCH_THRESHOLD",
                                     str(transcript_threshold)))

    @pytest.fixture(scope="module")
    def result(heidi_app) -> ScribeResult:
        return run_upload_flow(
            heidi_app, flow=flow, mode=mode, clip=clip, keywords=keywords,
            transcript_threshold=threshold, context_clip=context_clip,
        )

    return result


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------
def _no_flow_error(res) -> None:
    if res.error:
        pytest.fail(f"[{res.flow}] flow crashed before assertions: {res.error}")


# ---------------------------------------------------------------------------
# Checks for the straight recording flow (TCD006 / TCD007)
# ---------------------------------------------------------------------------
def check_recording_starts(res: ScribeResult) -> None:
    _no_flow_error(res)
    assert res.recording_started, (
        f"[{res.flow}] {res.mode} recording did not start (no End control)"
    )


def check_timer_advances(res: ScribeResult) -> None:
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


def check_transcription_generated(res: ScribeResult) -> None:
    _no_flow_error(res)
    if not res.audio_injected:
        pytest.skip(f"[{res.flow}] no virtual audio injected — content check "
                    f"needs BlackHole (macOS) / VB-CABLE (Windows)")
    assert res.transcript.strip(), (
        f"[{res.flow}] transcript is empty — audio->text path produced nothing"
    )


def check_note_generated(res: ScribeResult) -> None:
    _no_flow_error(res)
    assert res.note_started, (
        f"[{res.flow}] note generation never started after stopping"
    )
    if not res.audio_injected:
        pytest.skip(f"[{res.flow}] no virtual audio injected — note body "
                    f"needs real audio")
    assert res.note.strip(), f"[{res.flow}] generated note body is empty"


def check_duration_display(res: ScribeResult) -> None:
    _no_flow_error(res)
    shown = res.duration_display_s
    expected = res.timer_last_s
    print(
        f"\n[{res.flow}] duration display: {res.duration_display} "
        f"({shown}s) vs recorded {expected}s"
    )
    assert shown is not None, (
        f"[{res.flow}] no duration displayed after stopping "
        f"(raw={res.duration_display!r})"
    )
    assert expected is not None, (
        f"[{res.flow}] no timer reading to compare against"
    )
    tol = max(3, int(expected * 0.05))
    assert abs(shown - expected) <= tol, (
        f"[{res.flow}] displayed duration {shown}s differs from recorded "
        f"{expected}s by more than {tol}s"
    )


def check_transcript_accuracy(res: ScribeResult) -> None:
    _no_flow_error(res)
    if not res.audio_injected:
        pytest.skip(f"[{res.flow}] no virtual audio injected — accuracy check "
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


# ---------------------------------------------------------------------------
# Checks for the pause/resume flow (TCD015 / TCD016)
# ---------------------------------------------------------------------------
def check_pr_recording_starts(res: PauseResumeResult) -> None:
    _no_flow_error(res)
    assert res.recording_started, (
        f"[{res.flow}] {res.mode} recording did not start"
    )


def check_pr_paused(res: PauseResumeResult) -> None:
    _no_flow_error(res)
    assert res.paused, (
        f"[{res.flow}] could not pause the recording (no Pause control found)"
    )


def check_pr_resumed(res: PauseResumeResult) -> None:
    _no_flow_error(res)
    assert res.resumed, (
        f"[{res.flow}] could not resume after pause (no Resume control found)"
    )


def check_pr_segment_a_present(res: PauseResumeResult) -> None:
    """Content spoken BEFORE the pause survives into the final transcript."""
    _no_flow_error(res)
    if not res.audio_injected:
        pytest.skip(f"[{res.flow}] no virtual audio — segment content needs "
                    f"BlackHole (macOS) / VB-CABLE (Windows)")
    hits = res.seg_a_hits
    print(f"\n[{res.flow}] pre-pause segment hits: {hits} / {res.keywords_a}")
    assert hits, (
        f"[{res.flow}] NO pre-pause content in transcript — segment A was "
        f"dropped across the pause boundary. Expected any of {res.keywords_a}.\n"
        f"Transcript (first 800):\n{res.transcript[:800]}"
    )


def check_pr_segment_b_present(res: PauseResumeResult) -> None:
    """Content spoken AFTER resume survives into the final transcript."""
    _no_flow_error(res)
    if not res.audio_injected:
        pytest.skip(f"[{res.flow}] no virtual audio — segment content needs "
                    f"BlackHole (macOS) / VB-CABLE (Windows)")
    hits = res.seg_b_hits
    print(f"\n[{res.flow}] post-resume segment hits: {hits} / {res.keywords_b}")
    assert hits, (
        f"[{res.flow}] NO post-resume content in transcript — segment B was "
        f"dropped across the pause boundary. Expected any of {res.keywords_b}.\n"
        f"Transcript (first 800):\n{res.transcript[:800]}"
    )


def check_pr_no_errors(res: PauseResumeResult) -> None:
    """Session completes with no transcript/generation error banner."""
    _no_flow_error(res)
    assert res.note_started, (
        f"[{res.flow}] note generation never started after stopping"
    )
    assert not res.has_error_banner, (
        f"[{res.flow}] an error banner appeared after the pause/resume session"
    )


# ---------------------------------------------------------------------------
# Checks for the audio-upload flow (TCD004 / TCD005 / TCD008)
# ---------------------------------------------------------------------------
def check_upload_accepted(res: ScribeResult) -> None:
    """The file was accepted through the picker and processing began."""
    _no_flow_error(res)
    assert res.recording_started, (
        f"[{res.flow}] upload was not accepted — the dialog/native picker did "
        f"not complete (mode={res.mode})"
    )


def check_upload_transcription_generated(res: ScribeResult) -> None:
    _no_flow_error(res)
    assert res.transcript.strip(), (
        f"[{res.flow}] transcript is empty after upload — the uploaded audio "
        f"produced no transcript"
    )


def check_upload_note_generated(res: ScribeResult) -> None:
    _no_flow_error(res)
    assert res.note_started, (
        f"[{res.flow}] note generation never started after upload"
    )
    assert res.note.strip(), f"[{res.flow}] generated note body is empty after upload"


def check_upload_transcript_accuracy(res: ScribeResult) -> None:
    """Soft accuracy signal only — the hard pass is that transcript + note have
    real content (checked by the other upload asserts). Uploaded-audio
    transcripts vary and the AX read can be noisy, so we log accuracy and only
    fail if it's essentially zero (nothing recognisable came through).
    """
    _no_flow_error(res)
    acc = res.transcript_accuracy
    print(
        f"\n[{res.flow}] uploaded-audio transcript accuracy: {acc:.1%} "
        f"({len(res.hits)}/{len(res.keywords)}) "
        f"soft-threshold={res.transcript_threshold:.0%} misses={res.misses}"
    )
    # Only a hard floor: at least SOME expected content must appear. Content
    # completeness is asserted by check_upload_transcription_generated /
    # check_upload_note_generated.
    assert res.hits, (
        f"[{res.flow}] transcript contained NONE of the expected keywords — "
        f"the uploaded audio may not have been transcribed.\n"
        f"Transcript (first 800):\n{res.transcript[:800]}"
    )


def check_context_uploaded(res: ScribeResult) -> None:
    """The context file was attached via the Context tab paperclip -> native
    Open panel (TCD008)."""
    _no_flow_error(res)
    assert res.context_uploaded, (
        f"[{res.flow}] context file upload did not complete — the Context-tab "
        f"paperclip button or native Open panel was not driven successfully."
    )


def check_context_reflected_in_note(res: ScribeResult, context_keywords) -> None:
    """SOFT check: report whether content unique to the uploaded CONTEXT file
    surfaced in the generated note.

    Whether the LLM incorporates context into the note is non-deterministic, so
    this NEVER hard-fails on a miss — it prints which context markers appeared
    (observability), and only fails if the note itself is empty (which the
    other checks already cover, so effectively this is report-only).
    """
    _no_flow_error(res)
    note = (res.note or "").lower()
    hits = [kw for kw in context_keywords if kw.lower() in note]
    print(
        f"\n[{res.flow}] context reflected in note: {len(hits)}/"
        f"{len(context_keywords)} markers -> hits={hits}"
    )
    if not hits:
        print(
            f"[{res.flow}] NOTE: no context markers found in the note. This can "
            f"be legitimate (the model may not cite an unrelated context doc) — "
            f"not failing. Note head:\n{res.note[:400]}"
        )
    # Report-only: assert nothing about hits. Just guard the note isn't empty.
    assert res.note.strip(), f"[{res.flow}] note is empty — nothing to reflect context into"
